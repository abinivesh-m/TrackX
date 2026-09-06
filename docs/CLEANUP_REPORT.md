# TrackX — Cleanup Report (this session)

## Goal

Reduce repository noise and remove clearly generated/temporary/shipped artifacts while preserving everything required for a defensible SIH-26127 demo and evaluation.

## Actions taken

### Removed

- `frontend/node_modules/` — shipped dependency tree, not part of source control.
- `frontend/dist/` — built frontend bundle, regenerated only when needed.
- All `__pycache__` `.pyc` files cleaned from the repo tree.
- `.pytest_cache/` cleaned.

### Normalized / fixed (not deleted)

- `backend/.env.example` — normalized to placeholder-only; demo admin credential labeled DEMO ONLY.
- `backend/app/core/config.py` — reconciled weight paths to actual shipped artifacts:
  - `VEHICLE_WEIGHTS = yolov8n.pt`
  - `PLATE_WEIGHTS = models/best_plate_detector.pt`
  - `OCR_MODEL_PATH = models/lprnet_indian.pth`
- `backend/alembic.ini` — replaced committed placeholder PG password URL with a driver placeholder comment; real URL comes from env.
- `backend/alembic/env.py` — default fallback URL changed to a SQLite dev default; production must set `DATABASE_URL`.

### Tests fixed

- `integration_tests/test_sample_png.py` — fixed misuse of `TestCase.skipTest()` (now uses `unittest.SkipTest`).
- `tests/test_7_camera_network.py::test_camera_video_structure` — fixed so it no longer asserts non-existent committed media dirs as if present. The camera network configuration is still tested; the raw media path is treated honestly.

### Verified (do not delete)

- `models/lprnet_indian.pth` — present, SHA256 `bdc17060638f01e23d9f05ad56bd9351e5a58c6bfafbe1e077330fb06fac12df`, loads in `recognition.lprnet_ocr`.
- `models/best_plate_detector.pt` — present.
- `models/best.onnx` — retained; classify/document whether it is the ONNX export of the plate detector.
- Root `yolov8n.pt` and `yolo11n.pt` — reconciled to `yolov8n.pt` as the documented default vehicle weight in config. Keep the other only if clearly needed; otherwise archive.

## Not deleted (by design)

- Source packages under `backend/app`, `database`, `intelligence`, `recognition`, `detection`, `analytics`, `gis`, `network`, `dashboard`, `demo`, `scripts`, `tests`, `integration_tests`.
- Models in `models/`.
- Authoritative benchmark artifacts needed for OCR reproducibility.
- Dockerfiles, compose, package manifests, lockfiles.

## Remaining cleanup considerations

- Root directory still has many intermediate audit scripts and reports. Classify before deletion; promote authoritative docs to `docs/`.
- `outputs/` still contains multiple benchmark/debug artifacts. Keep one authoritative benchmark path; archive the rest.
- `Screenshots/` should be classified.
- `temp_frames/`, `logs/` should be classified.
- `data/`-equivalent evaluation data needs a clean home if a committed immutable eval tree is desired.
