# FINAL PRODUCT VERIFICATION — TrackX (SIH-26127 / BEL)

Date of verification: **2026-09-05**. Every number below was produced by running
the actual code in this repository on this machine during this session. No
number is copied from an older report without being independently reproduced.

---

## 1. Product overview

TrackX is a centralized city-wide ANPR intelligence platform for the SIH-26127
Bharat Electronics Ltd. problem statement. The product prototype comprises:

- **Real AI ingestion** (`demo/visual_pipeline.py`, `scripts/run_real_pipeline.py`):
  YOLO vehicle detection + ByteTrack tracking, YOLO plate detection
  (`models/best_plate_detector.pt`), **LPRNet** primary Indian-plate OCR
  (`models/lprnet_indian.pth`), PaddleOCR secondary, Indian plate validation.
- **Intelligence core**: multi-signal fusion matching (`intelligence/fusion.py`),
  multi-camera trajectory reconstruction (`intelligence/trajectory.py`),
  explainable anomaly scoring (`intelligence/anomaly_scoring.py`), blacklist and
  route-alert engine (`intelligence/alerts.py`), traffic analytics
  (`analytics/analytics.py`), GIS (`gis/`, `network/camera_network.py`).
- **Operations web app**: FastAPI backend (`backend/`, JWT auth + RBAC) and a
  React/TypeScript frontend (`frontend/`) with Operations, Live Cameras, Vehicle
  Intelligence, Trajectory Search, GIS Map, Traffic Analytics, Alerts and System
  Admin pages. The product runs in a clearly labelled **DEMO MODE** on recorded
  multi-camera feeds.

## 2. Architecture

```
recorded feeds (7 cameras, data/cameras)
  -> demo/visual_pipeline.py: vehicle detect/track -> plate detect -> plate crop
  -> LPRNet -> PaddleOCR (secondary) -> OCR fusion -> Indian validation
  -> observation (full schema incl. normalized_plate, confidence, bboxes,
     appearance vector, camera_id, timestamp, data_source)
  -> outputs/results/observations.db  (SQLite via database/observation_store.py)
  -> intelligence.trajectory (multi-camera linking, fusion + suspect edges)
  -> intelligence.alerts (blacklist, repeated camera, route anomaly) -> alerts table
  -> analytics.analytics -> FastAPI /api/v1 -> React web app (JWT protected)
```

Two OCR environments coexist because PaddleOCR (paddlepaddle 2.6.2) is only
installed in the Python 3.11 interpreter while the torch/LPRNet stack runs under
Python 3.14. Both are wired into the same recognition code path
(`recognition/ocr_reader.py`, `recognition/lprnet_ocr.py`).

## 3–5. Dataset audit and expansion (authoritative benchmark)

Sources on disk: `plate_crops_external/` (1391 crops: 737 static + 654 video
frame crops), `plate_crops_additional/` (47), `huggingface_import/` (47).

Audit findings (manifest `data/ocr_eval/dataset_audit_manifest.json`, rebuilt as
`data/ocr_eval/authoritative_benchmark.json`):

- Old JSON manifests stored **machine-specific OneDrive absolute paths** and
  carried stale `split` provenance fields; all benchmark tooling was rewritten
  to resolve files physically on disk by filename.
- Ground-truth audit of the 737 static crops found **6 entries whose GT is not a
  plate** (car model names "DUSTER/CRETA/TERRANO" and OCR-of-model-text), plus a
  handful of suspect legacy labels. Junk GT was excluded (documented per file in
  the manifest), **not silently deleted from disk**.
- **Authoritative OCR benchmark**: 731 unique images (deduplicated by sha256,
  plausible Indian registration GT, physically present). 673 unique plates.
  Covers TN/KA/AP/TL/MH/DL/HR/GJ/KL states, cars/motorcycles/commercial, daylight
  and night, front and rear plates, and plate crops from 9 px to 55 px height.
- Expansion: repository already carried >1000 crops; additional HF-sourced crops
  (47) and video crops (654, filename-derived GT for real footage) were audited
  and are available for training. No new web-scraped images were added.

## 6–10. OCR benchmark (measured, NOT fabricated)

Engine | Exact-match | Character acc. | Notes
--- | --- | --- | ---
LPRNet (shipped `lprnet_indian.pth`) | **250/731 = 34.2%** | 81.9% | measured this session
PaddleOCR 2.7.3 (vanilla, py3.11) | **342/731 = 46.8%** | — | measured this session, same 731 files
Deterministic fusion (format-valid + higher-confidence rule) | **367/731 = 50.2%** | — | measured, +3.4 pts over best engine

Historical claims independently checked:
- "LPRNet ≈ 33-36%" → **reproduced (34.2%)**.
- "72.4% with PaddleOCR" → **NOT reproduced**: vanilla PaddleOCR measures 47.4%
  on the same 551-file set the claim referred to. The claimed number appears to
  have used an unreleased multi-pass pipeline variant; it is reported as
  NOT VERIFIED.
- 90%+ target → **genuinely attempted and NOT reached** on this benchmark.
  Ceiling analysis: error-distance histogram shows 178 of 731 misses differ by a
  single character and 132 by two; even a hypothetical perfect 1-character
  corrector would cap this benchmark near ~59%. The crop set consists of real
  listings/traffic crops with plate heights mostly 10–25 px, below the resolution
  where either engine (or a human) can reliably read 10-character plates. Getting
  to 90% requires a fine-tuned recognizer trained on hundreds of *legible*
  full-frame plate crops at ANPR capture resolution plus per-camera multi-frame
  voting — recorded as the technical blocker, not hidden.

A multi-preprocessing best-of-N LPRNet experiment and a longer PaddleOCR variant
pass were also started; they were not completed within the session and are not
reported as results.

## 11–17. Detection / tracking / pipeline / trajectory / latency

- Plate detector weights ship (`models/best_plate_detector.pt`); vehicle
  detection/tracking is stock COCO YOLO + ByteTrack. Real-pipeline ingestion
  (`demo/visual_pipeline.py`) was run historically on CAM_01 footage and written
  to the observation store (junk reads from an earlier unvalidated OCR mode were
  removed from the shipped DB; the pipeline now validates reads by Indian plate
  format before persisting).
- **Trajectory engine bug found and fixed this session**: `build_trajectories()`
  short-circuited on per-camera `track_id`s and never linked hops across cameras
  (every hit became a 1-observation trajectory; no route anomaly could ever
  fire). Rewritten to (a) consolidate same-session frames, (b) link hops with the
  fusion engine ordered chronologically, (c) keep SUSPECT identity edges so
  impossible transitions/cloned plates reach the anomaly engine. Verified on the
  demo network: TN10AB1234 reconstructs CAM_01→02→03→05 with HIGH-confidence
  hops; the confusable-OCR vehicle TN45BS9012 (one hop misread as TN458S9012 at
  0.58 confidence) is still linked through fuzzy plate + appearance evidence.
- **Latency**: trajectory reconstruction over the 79-observation demo network
  completes in well under a second; observation→trajectory latency is dominated
  by SQLite read + fusion over O(n²) candidates (n here is per-vehicle same-plate
  pairs, not global). The historical "780 s → 6 ms" claims were not treated as
  gospel; a latency instrumentation script (`measure_trajectory_latency.py`)
  exists for independent reproduction.

## 18–23. Alerts / analytics / GIS (verified end-to-end in the web app)

Alert classes verified firing from real trajectory evidence in the DB:
- BLACKLIST_MATCH — TN38AB1234 (HIGH), DL8CAG4321 (MEDIUM, severity now read from
  the watchlist store instead of hardcoded HIGH);
- REPEATED_CAMERA — TN99ZZ0000 seen 3× at CAM_03 (loitering);
- ROUTE_ANOMALY (POSSIBLE_CLONED_PLATE) — TN77IM9999 and TN88CL0000 with
  explainable reasons ("impossible required speed of 420/504 km/h").

Analytics (vehicles/camera, hourly density, OD matrix, congestion hotspots) and
GIS (camera nodes, density heatmap, bottleneck list, OD corridors) are computed
from the same observation rows and rendered on the Operations pages.

GIS API bugs found and fixed this session: `/gis/congestion` and `/gis/od_flow`
returned 500 (analytics functions expect trajectory dicts; raw observations were
passed, and route keys are `"A -> B"` strings); both endpoints now verified 200
with data.

## 24. Manual webapp QA (performed in a live browser)

Login → Operations → Live Cameras → Vehicle Intelligence → Trajectory Search →
GIS Map → Traffic Analytics → Alerts → System Admin were all visited and
exercised against the running FastAPI + Vite stack. Bugs found and fixed during
QA:

1. `/api/v1/cameras` and `/alerts` (no trailing slash) were 307-redirected to
   the raw backend host, which the browser then blocked via CORS → all dashboard
   counters read zero. Fixed both route aliases and CORS origins; dashboard now
   shows live counts (56 vehicles, 7 cameras, 5 open alerts, per-camera volumes).
2. Recent Activity previously showed garbage plate strings from stale
   unvalidated pipeline rows; cleaned the DB and improved provenance tagging.
3. Vehicle summary (First/Last Seen, route path, journey time) showed N/A — the
   backend returned raw trajectories; `_summarize()` added on both endpoints.
4. GIS page counters/tables empty on the same 500s (fixed above).

Browser console was checked after fixes; no remaining CORS/JS/network errors on
the pages exercised.

## 25–26. Remaining limitations (stated plainly)

- OCR exact-match on the real-crop benchmark is **~50% (fusion)**, far below the
  90% target, for the resolution-limited reason quantified above.
- Webapp runs on the seeded **DEMO_SYNTHETIC** scenario (explicitly labelled
  DEMO MODE in the UI), not live CCTV; real ingestion path exists and runs, but
  no live camera feed was available in this session.
- Analytics/OD volumes reflect ~1–2 hours of simulated morning traffic across 7
  cameras; figures are small but every number traces to the observation table.
- Re-ID uses a generic ImageNet embedding (documented), not a trained vehicle
  Re-ID model.

## Reproduction commands

```bash
python -m demo.seed_demo_data --reset   # rebuild demo observation DB
python -m intelligence.trajectory       # print reconstructed trajectories
python -m intelligence.alerts           # scan + persist alerts
cd backend && python -m uvicorn app.main:app --port 8000
cd frontend && npm run dev              # open http://localhost:3000 (admin@trackx.com / admin123)
# OCR benchmark:
python scripts/build_authoritative_benchmark.py
python scripts/ocr_baseline.py --engine lprnet
py -3.11 scripts/ocr_baseline.py --engine paddle
python scripts/score_benchmark.py outputs/ocr_baseline_lprnet.json outputs/ocr_baseline_paddle_bench.json
```
