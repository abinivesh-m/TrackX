# TrackX — Day 2 Status Report

**Read this before the demo.** It says exactly what's real, what's fixed,
and what needs your machine (not this sandbox) to actually execute.

## Environment constraint (important)

This sandbox has **no network access at all** — not just PaddleOCR's model
CDN, everything (confirmed: `pip install` to PyPI is blocked, `host_not_allowed`).
So in this session:

- `torch`, `ultralytics`, `paddleocr`, `paddlepaddle` are **not installed**
  and could not be installed here.
- No YOLO weights could be downloaded here.
- I could not literally run `streamlit run dashboard/dashboard.py` or a
  fresh end-to-end YOLO pass here.

Everything below reflects what I could actually verify in this environment,
not what a prior transcript claimed. On your own machine (which has real
internet), `pip install -r requirements.txt` should give you the real stack,
and the pipeline should run for real — nothing in the code fakes that path.

## What I found already working (from the zip you gave me)

The project architecture is already merged and largely solid:
- Vehicle detection with real cross-class dedup, verified against a real
  logged bug (IoU 0.963 between "car" 0.492 / "truck" 0.46 on the same
  physical car) — regression test exists and passes.
- The Day-2 database bridge (`ObservationStore.add_visual_observation(s)`)
  correctly maps the visual pipeline's flat schema into the existing
  `observations` table, additive migration, never fabricates a plate.
- `dashboard.py` already used `use_column_width` (not `use_container_width`)
  for `st.image`, already wires "Live / Video Ingestion" → `run_camera()`,
  already reports library/model/DB health honestly, and has **no**
  `st.stop()` blocking that tab.
- `intelligence/trajectory.py`, `fusion.py`, `alerts.py`, `analytics.py`,
  `gis_map.py` are intact and untouched.

## The one real bug I found and fixed

`run_camera()` unconditionally constructed `PlateOCR()` (which wraps
`PaddleOCR(...)`) *before* checking whether a plate detector even existed.
PaddleOCR's constructor downloads its models on first use; if that fails,
PaddleOCR calls `sys.exit()` internally — a `SystemExit`, which is **not**
a subclass of `Exception`, so nothing in the codebase (or in Streamlit)
would have caught it. That would have silently killed the whole process,
whether or not a plate detector was even configured.

Fixed in `recognition/ocr_reader.py` (`try_init_ocr()`), `demo/visual_pipeline.py`,
and `pipeline.py`:
- OCR is now only initialized when a plate detector is actually present
  (it's otherwise never used).
- Initialization is wrapped to catch both `SystemExit` and ordinary
  `Exception`, returning `None` instead of taking the process down.
- `build_plate_fields()` now has a **distinct** `plate_status="unavailable"`
  reason for "plate box found, but OCR engine unavailable" vs. "no plate
  detector weights at all" — so a judge/log reader can tell which
  component is actually missing.
- Added regression tests (`TestTryInitOcr`, plus a `build_plate_fields`
  case for `ocr=None`) proving this degrades gracefully instead of
  crashing.

Also fixed: `tests/test_vehicle_dedup.py` only passed when run as part of
the full suite (it relied on another test file having already stubbed
`ultralytics` into `sys.modules`). It now stubs it itself, so it's correct
standalone.

## Test suite

```
python3 -m unittest discover -s tests -p "test_*.py" -v
```
**63/63 passing** (52 original + 4 OCR-resilience + 7 dataset-validator),
and each test file also passes standalone, not just via discovery. No
existing test was weakened to make this pass.

## Plate-detector training scripts (added this session)

The README referenced `detection/train_yolo.py` and
`detection/validate_dataset.py` but neither actually existed in the repo.
Both are now written and tested:

- `detection/validate_dataset.py` — checks a YOLO-format dataset (from
  e.g. a Roboflow Universe export) for the mistakes that otherwise waste
  training time: missing `data.yaml`, unmatched image/label pairs,
  malformed label lines, out-of-range class ids, and raw pixel
  coordinates pasted in instead of normalized 0-1 YOLO coordinates. No
  ultralytics/torch dependency, so it runs anywhere. Fully tested in this
  sandbox against both well-formed and deliberately-broken synthetic
  datasets (7 passing tests, `tests/test_validate_dataset.py`).
- `detection/train_yolo.py` — thin wrapper around `ultralytics`'
  fine-tuning loop; writes to `detection/runs/detect/plate_train/weights/best.pt`,
  which is already one of the paths the rest of the pipeline checks
  automatically. **Could not be executed in this sandbox** (no
  `ultralytics`/`torch`, no network) — syntax-checked only. Run it for
  real on your machine once you have a dataset.
- `detection/data.yaml.example` — documents the expected dataset folder
  layout.
- Added `pyyaml` to `requirements.txt` (needed by the validator; it's
  also already a transitive dependency of `ultralytics`, but the
  validator itself has no ML dependency so it's worth declaring
  explicitly).

## Real end-to-end proof (within this sandbox's limits)

The zip already contained a genuine prior YOLO run's output —
`outputs/results/CAM_01_visual_results.json` and its annotated frame — a
real photo with a real detection box (`car 0.492`) and an honest
`"plate: N/A (no detector)"` label (visible in the annotated JPG). That
output had never actually been bridged into the database. I ran it
through the real bridge in this session:

- `write_observations_to_db()` → wrote 1 row into a fresh
  `outputs/results/observations.db`
- `ObservationStore.all_observations()` reads it back correctly
- `build_trajectories()` → 1 trajectory
- `scan_trajectories_for_alerts()` → 0 alerts (correctly, no blacklist
  match), and did **not** crash on a `None` plate_text (I checked —
  `plate_similarity()` and `appearance_similarity()` both handle `None`
  safely)
- `vehicles_per_camera()` / `busiest_camera()` → correct

This proves the full **camera output → database → trajectory → alerts →
analytics** chain is wired correctly and won't crash on real "plate not
read" data. `observations.db` in this zip now has that real row in it —
open the dashboard's other tabs against it and you'll see it.

## What still needs your machine, honestly

1. **Install the real stack**: `pip install -r requirements.txt` (this
   needs internet you have and I don't, here).
2. **Run a fresh real pass**: `python -m demo.visual_pipeline --camera CAM_01`
   — this will download real YOLOv8 weights and re-detect on
   `sample_scene.jpg` / `sample_clip.mp4` for real.
3. **Boot the dashboard for real**: `streamlit run dashboard/dashboard.py`
   from the project root — I could not execute this here (no `streamlit`
   package, no network to get it), so please do a real smoke-test of all
   4 tabs on your end before your demo.
4. **Plate detection remains "NOT CONFIGURED"** until you actually run
   `detection/train_yolo.py` on a real labeled dataset — the script exists
   and is ready now, but running it needs the real ML stack + your own
   dataset, neither available here. See the README's "Hour 1/Hour 2"
   section for the fastest path (a free Roboflow Universe export already
   matches the expected folder layout).
5. Confirm PaddleOCR's CDN (`bj.bcebos.com`) is actually reachable on
   your network before the demo; if it isn't, you'll now see a clean
   `"OCR engine failed to initialize"` status instead of a crash — but
   OCR itself still won't work until that's reachable.
