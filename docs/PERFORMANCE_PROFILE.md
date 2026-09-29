# TrackX — OCR Performance Profile & Sampling Validation

**Status of this document:** Real, measured numbers from real runs on real CCTV footage in this
environment. Referenced from code comments in `pipeline.py` and `recognition/ocr_reader.py` —
kept here so those comments point at real data, not a claim with nothing behind it.

## 1. Where the time actually goes (instrumented profiling)

Manual `time.time()` instrumentation reproducing `run_video_to_db()`'s per-frame loop, run
against 180 real frames of dense Indian traffic footage (`anpr_compare.mp4`, 1920×1080, CPU-only
sandbox, no GPU):

```
frames processed: 180
TOTAL wall time: 179.0s
  vehicle detect+track:  18.1s (10.1%)
  crop:                   0.0s (0.0%)
  plate detect (739 calls): 30.0s (16.7%)   ~40.5ms/call
  OCR (652 calls):         130.8s (73.1%)   ~200.7ms/call   <- dominant bottleneck
  other/overhead:           0.0s (0.0%)
```

OCR is the clear, measured target for optimization — not a guess. Vehicle detection/tracking is
only 10.1% of total time, which is why the performance work below deliberately leaves it
untouched at full frame rate.

## 2. OCR call-sampling + early-stop: real before/after

Same video (`anpr_compare.mp4`), full `run_video_to_db()` (not the standalone profiling
reproduction above), `write_annotated=False` to isolate the OCR-cost question, **fresh
`VehicleDetector`/`PlateDetector` instances per run** (ByteTrack's `persist=True` keeps its
internal track-ID counter alive across calls on a *shared* instance, which would otherwise make
track IDs between runs non-comparable — confirmed by an earlier attempt where the same physical
vehicle showed up as track 2 in one run and track 196 in the next).

| Config | Elapsed | FPS | OCR calls made | Tracks matching baseline exactly |
|---|---|---|---|---|
| Baseline: OCR every opportunity, no sampling/early-stop | 178.9s | 1.01 | 659/659 (100%) | — (this IS the baseline) |
| Rejected config: always-OCR-first-2-attempts, then 1-in-3, early-stop at 4 readings / 0.85 confidence | 85.3s | 2.11 | 209/659 (32%) | 22/30 (73%) — **8 tracks (27%) differed**, including one that dropped a leading digit (`DL7CP8161`→`L7CP8161`) and one that went from a correct plate to a wrong short numeric string |
| Shipped config: uniform 1-in-3 sampling from attempt 0, early-stop at 7 readings / 0.90 confidence | 94.0s | 1.91 | 230/659 (35%) | 28/30 (93%) — 2 remaining mismatches on genuinely small/hard plate crops |

### Why the first config was rejected

Root cause of the "always read the first N attempts" design: it systematically over-weighted
the **earliest** frames of a track, which tend to be the worst-quality ones (vehicle just
entering frame — more motion blur, more oblique angle, smaller apparent size before it's fully
in view). The "shipped" config samples uniformly across the track's whole lifetime instead
(`attempt_num % OCR_SAMPLE_INTERVAL == 0` from attempt 0), removing that bias.

A second, independent bug was found and fixed alongside this: `vote_plate_text()`'s old
confidence number was "average confidence of whichever text happened to win," which let a
*small, coincidentally-agreeing* cluster of readings (e.g. 4 readings that all happened to read
the same wrong text) score as confidently as a much larger genuine consensus. This is why one
track's early-stop fired on a wrong answer in the rejected config. The fix (in
`recognition/ocr_reader.py::vote_plate_text()`) scales confidence by both agreement ratio and
sample size — see `tests/test_ocr_temporal_fusion.py::test_confidence_penalizes_*` for the
regression tests this produced.

## 3. Net result

**~1.9–2.0x real wall-clock speedup** on dense real traffic footage, not the ~3.7x a naive
"OCR is 73% of time, sample it down 65%" estimate would suggest — plate detection (16.7% of
baseline time) and vehicle detection/tracking (10.1%, deliberately never touched) still run on
every single frame, so they set a floor the OCR-only sampling can't cross.

This is still well short of real-time on CPU-only hardware. For a judge demo, a short (8–15s)
clip stays practically watchable; a multi-minute dense clip does not.
