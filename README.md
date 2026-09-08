# SIH26127 — TrackX: City-Wide AI Vehicle Tracking (PS 26127)

**Status**: functional core platform (ANPR pipeline, multi-camera trajectory, traffic analytics,
congestion/route-anomaly detection, blacklist alerts, GIS, auth/RBAC/audit) with two honest,
currently-open gaps: OCR accuracy is below the >90% SIH target (see `docs/OCR_EVALUATION.md`), and
the trained plate-detector/LPRNet weight files (`models/best_plate_detector.pt`,
`models/lprnet_indian.pth`) are **not present in every checkout** — only `models/best.onnx` is
guaranteed to be there, and the code now auto-detects and uses it when the `.pt`/`.pth` files are
absent (see `demo/visual_pipeline.find_plate_weights()` / `backend/app/core/config._resolve_plate_weights()`).
See `docs/CLAUDE_PHASE0_AUDIT.md` for the full, current-as-of-checkout audit — read that before
trusting any older report at the repo root or under `docs/`, several of which describe an earlier
Streamlit-based UI and model-weight state that no longer match this checkout.

**This project has two working UIs that serve different purposes** — a **React + FastAPI**
web app (`frontend/` + `backend/`) that is the current, actively-developed product surface with
auth, RBAC, congestion/route-anomaly pages, and a persisted database, and the original **CLI /
Python pipeline** (`pipeline.py`, `demo/visual_pipeline.py`, `intelligence/`, `analytics/`, `gis/`)
that the FastAPI backend itself calls into for its real detection/trajectory/analytics logic. There
is **no Streamlit dashboard in this repo anymore** — an earlier version of this README described
`dashboard/dashboard.py` as the primary demo UI; that folder was removed when the project moved to
the React+FastAPI stack, and running instructions further down have been corrected accordingly.

## Project Structure

```
sih26127/
├── requirements.txt         <- root/CLI-pipeline Python deps
├── pipeline.py               <- CLI entry point (detection + OCR + schema output / DB write)
│
├── backend/                  <- FastAPI web API (the product's server)
│   ├── app/
│   │   ├── main.py           <- registers all /api/v1/* routers
│   │   ├── api/v1/           <- auth, cameras, vehicles, analytics, alerts, observations,
│   │   │                         admin, trajectory, gis, health, road_network,
│   │   │                         congestion, route_anomaly
│   │   ├── core/              (config, database, security, cache, logging, monitoring)
│   │   ├── models/, schemas/, services/, websocket/
│   ├── alembic/               <- DB migrations (Postgres/PostGIS in prod, SQLite in dev)
│   └── tests/
│
├── frontend/                  <- React + TypeScript + Vite web UI (the product's client)
│   └── src/
│       ├── pages/              (Dashboard, Vehicles, Trajectory, GIS, Analytics, Congestion,
│       │                        RouteAnomaly, Alerts, Cameras, Admin, Login)
│       ├── services/api.ts     <- typed client for every /api/v1/* endpoint
│       └── components/
│
├── detection/                <- YOLO plate + vehicle detection
│   ├── detect_plates.py
│   ├── vehicle_detector.py
│   ├── train_yolo.py
│   └── validate_dataset.py
│
├── recognition/               <- reading plate text + vehicle appearance
│   ├── ocr_reader.py           (LPRNet primary / PaddleOCR secondary, with fallback)
│   ├── lprnet_ocr.py
│   ├── plate_matcher.py        (fuzzy match + normalization)
│   └── appearance.py           (vehicle re-id fingerprint)
│
├── network/                   <- camera locations + road graph (Haversine + hand-tuned ROAD_GRAPH)
│   └── camera_network.py
│
├── intelligence/               <- the core "brain": identity fusion + trajectory + anomalies
│   ├── fusion.py                (Global Match Score)
│   ├── trajectory.py            (reconstructs per-vehicle routes)
│   ├── alerts.py                (blacklist + anomaly detection)
│   ├── anomaly_scoring.py, spatio_temporal.py, route_hypothesis.py
│
├── database/                   <- sqlite stores backing the CLI pipeline AND the FastAPI routes
│   ├── observation_store.py     (all camera observations - what analytics/congestion/route-anomaly
│   │                             endpoints actually read from)
│   ├── alert_store.py, blacklist_store.py, camera_store.py, vehicle_registry.py
│   ├── congestion_store.py      (persisted congestion events + thresholds)
│   └── route_anomaly_store.py   (persisted route anomalies + investigation status)
│
├── analytics/
│   └── analytics.py             (traffic density, route frequency, multi-factor congestion model)
│
├── gis/
│   └── gis_map.py               (Folium interactive map)
│
├── demo/                        <- offline/video-file demo flows (camera-folder simulation, seeding)
│
├── data/                        (raw/processed/sample footage - not committed, .gitignore'd)
├── models/                      (trained weight files - .pt/.pth NOT committed, see status note above)
├── outputs/                     (generated at runtime: db, crops, maps)
└── tests/, integration_tests/
```

Everything is a proper Python package now (`__init__.py` in each folder), so
imports are explicit about where each piece lives — e.g. `intelligence/fusion.py`
imports from `recognition.plate_matcher` and `network.camera_network`.

**Why this structure**: when a judge asks "where's your matching logic" or
"show me the trajectory code," you point to `intelligence/` directly instead of
digging through one flat folder. It also means you can hand off `recognition/`
to one teammate and `intelligence/` to another without them stepping on each
other's files.

---

## Setup

```bash
cd sih26127
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## v3 pipeline change: vehicle-first, not plate-first

`pipeline.py` was rewritten. It now runs:

```
video -> vehicle detection + tracking (pretrained COCO YOLO, detection/vehicle_detector.py)
       -> for each tracked vehicle: plate detection WITHIN that vehicle's crop
       -> OCR each plate reading
       -> group all readings by track_id, vote on the best plate text
          (recognition/ocr_reader.py's vote_plate_text(), now actually wired in)
       -> appearance embedding from the VEHICLE crop, not the plate crop
       -> one final record per tracked vehicle
```

This fixes the earlier issue where appearance.py was extracting a "vehicle
fingerprint" from a tiny plate crop instead of the actual car. Vehicle
detection uses a stock pretrained YOLO (COCO classes: car/truck/bus/
motorcycle) - no fine-tuning needed for this part, only your plate detector
needs the custom-trained weights.

`--vehicle_weights` defaults to plain `yolov8n.pt` (auto-downloads on first
run). `--plate_weights` should point to your fine-tuned plate model from
`detection/train_yolo.py`.

---

## Day 1 — Detection + OCR pipeline

**Run everything from the project root** (the `sih26127/` folder itself, not
inside any subfolder) — this matters because of how the package imports work.

### Hour 1 — dataset validation

Get a labeled plate dataset first — the fastest path is a free Roboflow
Universe account: search for a "license plate detection" dataset (e.g.
search "license plate" on universe.roboflow.com), export it in **YOLOv8**
format, and unzip it. That export already includes a matching `data.yaml`
in the layout `detection/data.yaml.example` describes, so you usually
don't need to write one by hand — just point `--data_dir`/`--data` at
wherever you unzipped it.

```bash
python -m detection.validate_dataset --data_dir /path/to/downloaded/dataset
```

This only reads yaml/text/image files (no ultralytics/torch needed), and
catches the mistakes that otherwise waste an hour of training time: a
missing `data.yaml`, images with no matching label file, label lines with
the wrong number of fields, class ids outside your declared class count,
and the classic "pasted in raw pixel coordinates instead of normalized
0-1 YOLO coordinates" mistake.

### Hour 2 — YOLO sanity training

```bash
python -m detection.train_yolo --data /path/to/dataset/data.yaml
```

Fine-tunes a stock `yolov8n.pt` (transfer learning, not training from
scratch) on your dataset. Defaults to 30 epochs with early stopping if
validation loss stalls — override with `--epochs`, `--model` (try
`yolov8s.pt` for more accuracy at the cost of speed), `--imgsz`. Output
lands at `detection/runs/detect/plate_train/weights/best.pt` — which is
already one of the paths `demo/visual_pipeline.find_plate_weights()`
checks automatically, so once training finishes you just re-run the
pipeline/dashboard, no extra config needed.

A few hundred to a few thousand labeled images and 10-30 epochs on
`yolov8n.pt` is enough to get real, non-fabricated plate boxes for a
demo — it won't be production-grade, and it's fine to say that plainly
to a judge.

### Hour 3 — full pipeline test

Pipeline now expects a video (needs multiple frames for tracking to work):

```bash
python pipeline.py \
    --video data/sample_videos/cam1_footage.mp4 \
    --plate_weights detection/runs/detect/plate_train/weights/best.pt \
    --camera_id CAM_01 \
    --lat 13.0827 \
    --long 80.2707
```

---

## Day 2 — Multi-camera identity + trajectory

Feed each camera's footage through the pipeline into the shared database:

```python
from database.observation_store import ObservationStore
from detection.vehicle_detector import VehicleDetector
from detection.detect_plates import PlateDetector
from recognition.ocr_reader import try_init_ocr
from pipeline import run_on_video

vehicle_detector = VehicleDetector()  # pretrained, no weights arg needed
plate_detector = PlateDetector(weights="detection/runs/detect/plate_train/weights/best.pt")
ocr = try_init_ocr()  # None (not a crash) if PaddleOCR can't reach its model CDN
store = ObservationStore()

records, appearance_vectors = run_on_video(
    "cam1_footage.mp4", vehicle_detector, plate_detector, ocr,
    "CAM_01", 13.0827, 80.2707,
)
store.add_many(records, list(appearance_vectors.values()))
```

Then reconstruct trajectories, check analytics/alerts, and generate the map —
**always run these as modules (`-m`) from the project root**:

```bash
python -m intelligence.trajectory
python -m analytics.analytics
python -m intelligence.alerts
python -m gis.gis_map TN10AB1234
```

Map opens at `outputs/results/city_map.html`.

---

## Web App (React + FastAPI) — this is what you show the judges

**There is no Streamlit dashboard in this repo anymore.** An earlier version of this section said
to run `streamlit run dashboard/dashboard.py` — that folder was removed when the project moved to a
real client/server app. Run the backend and frontend as two processes, both from the project root
(the backend adds the project root to `sys.path` itself, same as the CLI pipeline does):

```bash
# Terminal 1 - FastAPI backend (serves /api/v1/*, auto-creates a dev SQLite DB + admin user)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# API docs at http://localhost:8000/docs
# Dev login: admin@trackx.com / admin123 (see backend/app/core/config.py - CHANGE for anything
# beyond a local demo; the app prints a security warning about this on every startup)

# Terminal 2 - React frontend (Vite dev server)
cd frontend
npm install
npm run dev
# Opens on http://localhost:5173 by default; set VITE_API_URL if the backend isn't on
# http://localhost:8000/api/v1
```

Pages: Dashboard (live system overview), Vehicles (plate search + full trajectory with explainable
evidence breakdown), Trajectory, GIS (interactive map), Analytics (density, OD patterns, average
speed, congestion), Congestion (bottleneck detection with configurable thresholds), RouteAnomaly
(suspicious-transition detection against the real road topology), Alerts (blacklist + anomaly feed),
Cameras, and Admin (RBAC, audit log, blacklist management). All of these call real FastAPI endpoints
backed by the same `database/`, `intelligence/`, `analytics/`, and `network/` modules the CLI
pipeline uses — not mock data.

The CLI pipeline and demo scripts below are still the right tool for offline processing, batch
video ingestion, and local experimentation without standing up the web app.

---

## End-to-End Demo

A comprehensive demo script is provided that runs the complete pipeline:

```bash
# LPRNet is the primary OCR engine for Indian plates, with PaddleOCR as
# an optional fallback for non-Indian plates
python run_demo.py --camera CAM_01
```

This demo:
1. Runs vehicle detection → plate detection → tracking → OCR
2. Persists results to the database
3. Builds multi-camera trajectories
4. Calculates traffic analytics (speed, OD patterns, congestion)
5. Generates alerts (blacklist + route anomalies)
6. Creates GIS map with trajectory visualization
7. Runs OCR accuracy evaluation

**Demo outputs**:
- Database: `outputs/results/observations.db`
- GIS Map: `outputs/results/city_map.html`
- OCR Report: `outputs/demo_ocr_evaluation.json`
- Dashboard-ready results

**OCR performance** (measured 2026-09-05 on the authoritative 731-crop
benchmark in `data/ocr_eval/authoritative_benchmark.json`; see
`FINAL_PRODUCT_VERIFICATION.md` and `SIH_COMPLIANCE.md`):
- LPRNet (primary engine): **34.2% exact-match** (250/731), 81.9% character accuracy
- PaddleOCR 2.7.3 (secondary engine, Python 3.11): **46.8% exact-match** (342/731)
- Deterministic fusion (format-valid + confidence): **50.2% exact-match** (367/731)
- Status: Below the 90% exact-match SIH target - documented limitation with a
  quantified ceiling analysis (see `SIH_COMPLIANCE.md`)
- The previously claimed "72.4% PaddleOCR" figure was NOT reproduced (vanilla
  PaddleOCR measures 47.4% on the same 551-file set); it is reported as
  NOT VERIFIED in `FINAL_PRODUCT_VERIFICATION.md`.
- Path to >90%: retraining LPRNet on legible ANPR-resolution Indian plates plus
  per-vehicle multi-frame voting (see `OCR_IMPROVEMENT_PLAN.md`)

## Alert System Demo

A dedicated alert system demonstration is available to showcase the complete alert workflow:

```bash
# Run the complete alert system demo
python demo/run_alert_demo.py --clean

# Optionally launch the dashboard automatically
python demo/run_alert_demo.py --clean --dashboard
```

This alert demo:
1. Seeds the database with 5 blacklisted vehicles (different severity levels)
2. Creates 18 realistic observations across 5 camera locations
3. Builds 11 vehicle trajectories with realistic movement patterns
4. Generates 4 alerts (3 blacklist matches, 1 repeated camera sighting)
5. Persists all alerts to the database with full details
6. Displays comprehensive alert summary with SIH requirement verification

**Alert Demo Features**:
- Blacklist detection with fuzzy matching (85% similarity threshold)
- Route anomaly detection (impossible travel, suspicious patterns)
- Repeated camera detection (loitering identification)
- Database persistence for all alerts
- Multi-severity classification (HIGH/MEDIUM/LOW)
- Complete integration with dashboard alert management

**Dashboard Alert Management**:
- **Active Alerts Tab**: View real-time generated alerts with severity indicators
- **Blacklist Management Tab**: Add/remove vehicles from watchlist with descriptions
- **Alert History Tab**: View and resolve historical alerts with filtering

See `ALERT_SYSTEM_GUIDE.md` for comprehensive alert system documentation.

## OCR Evaluation

Run OCR accuracy evaluation on the clean evaluation dataset:

```bash
python -m recognition.ocr_evaluation --dataset data/ocr_eval/clean_evaluation_dataset.json --output outputs/ocr_evaluation_report.json
```

The evaluation provides:
- Exact-match accuracy
- Character-level accuracy
- Error breakdown (confusion, length errors, etc.)
- SIH requirement compliance check

The clean evaluation dataset contains 538 unique verified Indian license plates with ground truth annotations from external sources, with all contaminated entries removed.

---

## Day 1 → Day 2 bridge: camera folder to database (SIH26127)

`demo/visual_pipeline.py` (Day 1) simulates a camera as a local folder and
runs real YOLO vehicle detection + (if trained weights exist) plate
detection + PaddleOCR on it, producing one flat observation dict per
vehicle. Originally this stopped at a JSON dump
(`outputs/results/<CAM_ID>_visual_results.json`) — the database was never
touched.

**Day 2 closes that gap.** `demo/visual_pipeline.py` now also writes every
observation into the SAME `observations.db` used by the rest of the stack,
via a new bridge method on the existing store
(`ObservationStore.add_visual_observation` /
`database/observation_store.py`) — no second database, no manual SQL. The
observations table gained new nullable columns (via an idempotent
migration) for the extra provenance the real pipeline captures: source
file/frame, detection bboxes, raw vs. normalized plate text, plate-detector
status, and the annotated frame path. The original 9-column schema and
every original method are untouched.

The vehicle-appearance embedding (`recognition/appearance.py`) now also
runs on the real vehicle crop from `demo/visual_pipeline.py` (previously
only wired up that way in the older `pipeline.py` path).

```bash
# process a camera's folder AND write the results into observations.db
python -m demo.visual_pipeline --camera CAM_01

# JSON output only, skip the database write
python -m demo.visual_pipeline --camera CAM_01 --no-db
```

From the dashboard, the **Live / Video Ingestion** tab lets you pick a
camera, click **Start AI Processing**, and see the real result (annotated
frame, detected vehicle class/confidence, track ID, plate text if read) -
this calls the exact same `demo.visual_pipeline.run_camera()` function, not
a simulated/hardcoded result. It also shows a **System Health** panel
reporting whether YOLO/PaddleOCR/the plate detector/the database are
actually available in the current environment, computed live rather than
hardcoded.

**Model weights, stated plainly:** `.pt`/`.pth` weight files are
`.gitignore`'d (see `.gitignore` - large binaries don't belong in git) and
are **not guaranteed to be present in a given checkout** - whether
`models/best_plate_detector.pt` exists depends on whether it was shared out
of band (drive link, release asset) into this specific copy of the repo.
What IS guaranteed to be present is `models/best.onnx` (an ONNX export,
committed as the one shipped artifact - see `models/README.md`), and the
plate-detector resolution logic (`demo.visual_pipeline.find_plate_weights()`,
mirrored in `backend/app/core/config.py`) now checks for it automatically
after the `.pt` candidates, so plate detection works out of the box even in
a checkout that only has the ONNX file. It's loaded via
`ultralytics.YOLO(path_to_onnx)`, which runs it directly through ONNX
Runtime - no `.pt` weights or retraining required for it to function.
`models/lprnet_indian.pth` is a different situation: `models/README.md`
itself documents this checkpoint as "Required for Production... requires
training" - it was never a shipped artifact, unlike the plate detector.
`recognition/lprnet_ocr.py` deliberately refuses to fall back to a
random-weight model if this file is missing (that would poison every
downstream tracker/alert with confident-but-wrong reads), so LPRNet stays
disabled and `recognition/ocr_reader.py` falls through to PaddleOCR instead.
The training scripts (`detection/validate_dataset.py`,
`detection/train_yolo.py`) remain the path to retrain/improve the plate
detector on your own footage - retraining needs a labeled dataset and the
real ML stack (`ultralytics`/`torch`). Vehicle detection, tracking, OCR, and
the full database/intelligence/web-app bridge all work out of the box with a
stock COCO YOLO for vehicles. Nothing fabricates a plate box or plate text
if no plate-detector weight file is present at all - plate detection reports
`plate_status: "unavailable"` instead.

**OCR resilience:** `recognition/ocr_reader.try_init_ocr()` wraps PaddleOCR
construction so a CDN-unreachable environment reports
`plate_status: "unavailable"` (with a reason distinguishing "no plate
detector" from "plate box found but OCR engine down") instead of taking
the whole process down — PaddleOCR's constructor calls `sys.exit()`
internally on that failure, which is not a catchable `Exception`. OCR is
also now only initialized when a plate detector actually exists, since
it's never used otherwise.

**Camera coverage:** all seven camera folders under `data/cameras/` ship
with footage - `CAM_01` contains real sample footage; `CAM_02`-`CAM_07`
include `CAM_0X_coimbatore_traffic.mp4` clips plus footage produced by
`scripts/generate_7_camera_videos.py` for the 7-camera demo. The dashboard
and `run_camera()` still treat a missing/empty folder as "no input
available" for that camera, not an error.

Run the tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---


## Important honesty notes (say these out loud if a judge asks)

- `recognition/appearance.py` now uses a pretrained ImageNet ResNet18 embedding,
  and as of the v3 pipeline change, it runs on the actual VEHICLE crop (from
  `vehicle_detector.py`), not the plate crop. This is a real fix. It's still
  NOT a trained vehicle Re-ID model (VeRi-776/OSNet-style) — say plainly:
  "generic pretrained visual embedding on the correct vehicle-level crop; would
  upgrade to a trained Re-ID model with more time/data."
- `detection/vehicle_detector.py` uses a stock pretrained COCO YOLO for vehicle
  detection + ByteTrack for tracking — no training needed, this part works
  out of the box. Only the plate detector (`detection/detect_plates.py`) is
  your custom fine-tuned model.
- `recognition/ocr_reader.py`'s `vote_plate_text()` is now actually wired into
  the pipeline — multiple OCR readings per tracked vehicle get voted into one
  final plate text, instead of trusting a single frame.
- `network/camera_network.py`'s `ROAD_GRAPH` and `CAMERA_RELIABILITY` values
  are manual placeholder estimates — replace with your actual filming layout,
  and be honest that reliability scores are estimated, not learned from data.
- `intelligence/fusion.py` now weights the plate signal by OCR confidence AND
  camera reliability — a low-confidence read from a known-bad-angle camera
  counts for less, and that weight shifts to appearance/temporal/spatial
  instead of just being lost.
- `intelligence/trajectory.py` uses a greedy best-score-first assignment, not
  a global optimum solver (Hungarian algorithm) — explainable and good enough
  for this scale.
- We deliberately did NOT build: a trained Re-ID model, a backend API with
  auth, or async processing. These require either training data/GPU time we
  don't have, or infrastructure a judge isn't evaluating. If asked, describe
  these as the clear next steps for a production version.

---

## Fixes applied when assembling this folder (read once, then ignore)

A handful of files were written assuming a flatter folder layout than the
one we're actually using. These are now fixed — noting them here so nobody
"fixes" them back to the broken version later:

- **Import paths**: `intelligence/trajectory.py`, `intelligence/alerts.py`,
  `analytics/analytics.py`, and `gis/gis_map.py` all had bare imports
  (`from fusion import ...`, `from observation_store import ...`) left over
  from before the package structure existed. These are now package-qualified
  (`from intelligence.fusion import ...`, `from database.observation_store
  import ...`, etc.) to match this layout.
- **`recognition/plate_matcher.py` was missing entirely** — both `fusion.py`
  and `alerts.py` import `plate_similarity` from it. Added a normalized
  edit-distance matcher with a small discount for OCR-confusable character
  pairs (O/0, I/1, B/8, S/5, Z/2, G/6, D/0). Tune `CONFUSABLE_PAIRS` or the
  substitution cost against your real OCR error patterns if you have time.
- **Output paths**: `database/observation_store.py` and `gis/gis_map.py`
  used `../outputs/...`, which writes *outside* the project folder when run
  from the root as instructed. Changed to `outputs/results/...` (and both
  now create the directory if missing).
- **Appearance signal was silently dead**: `build_trajectories()` used to
  require a separate `appearance_vectors` dict keyed by database row id, but
  no caller anywhere (dashboard, alerts, analytics, gis_map) ever passed one
  in — so `appearance_similarity()` always scored `0.0`, meaning 25% of the
  fusion score never actually did anything. Fixed by decoding each
  observation's own `appearance_vector` JSON column directly instead of
  relying on a side-channel dict. If your live demo now returns different
  match confidences than earlier test runs, this is why — it's now using
  the appearance signal it was designed to use.
- **`__init__.py`** added to every package folder (`analytics/`,
  `dashboard/`, `database/`, `detection/`, `gis/`, `intelligence/`,
  `network/`, `recognition/`) so the package imports resolve reliably.
- **`dashboard/dashboard.py`** inserts the project root into `sys.path` at
  import time, since Streamlit only adds the script's own folder — without
  this, running it from `dashboard/` would break every `database.*` /
  `intelligence.*` / `analytics.*` / `network.*` import.
