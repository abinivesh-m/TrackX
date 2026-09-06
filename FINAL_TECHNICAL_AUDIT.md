# TrackX — Final Technical Audit

**Date:** 2026-09-05
**Evaluator posture:** hostile BEL technical review
**Rule:** only report what was verified this session. No fabricated metrics.

## 1. Repository before cleanup

The repo was a mixed Python + React + FastAPI + Streamlit workspace with:
- A large root scatter of throwaway audit scripts and intermediate reports.
- Shipped frontend artifacts (`node_modules`, `dist`).
- Many `__pycache__` and `.pytest_cache` trees.
- Real source packages, models, Docker assets, config, tests, and generated outputs.

## 2. Files removed / cleaned this session

- `frontend/node_modules/`
- `frontend/dist/`
- repo-wide `__pycache__` `.pyc` files
- `.pytest_cache/`

## 3. Files retained (required)

- Core Python packages: `backend/app`, `database`, `intelligence`, `recognition`, `detection`, `analytics`, `gis`, `network`, `dashboard`, `demo`, `scripts`, `tests`, `integration_tests`
- Models: `models/lprnet_indian.pth`, `models/best_plate_detector.pt`, `models/best.onnx`
- Root YOLO weights: `yolov8n.pt` (documented default), `yolo11n.pt` (retained pending classification)
- Backend config + env template + alembic + Docker assets
- Frontend source + manifests (not `node_modules`/`dist`)
- Authoritative OCR benchmark artifact `outputs/ocr_benchmark_report.json`
- Docs promoted to `docs/`: `REPOSITORY_AUDIT.md`, `CLEANUP_REPORT.md`, `CLEANUP_PLAN.md`, `OCR_EVALUATION.md`, `SIH_26127_COMPLIANCE.md`

## 4. Models retained

- `models/lprnet_indian.pth` — Indian LPRNet checkpoint
- `models/best_plate_detector.pt` — plate detector
- `models/best.onnx` — retained; document whether it is the plate-detector ONNX export
- `yolov8n.pt` — default vehicle detector weight in config
- `yolo11n.pt` — retained; not the documented default

## 5. Datasets retained

- The clean 113-sample evaluation set referenced by `outputs/ocr_benchmark_report.json` (`data/ocr_eval/test_dataset_clean.json`).
- The repo also contains other OCR datasets and evaluation artifacts; only one benchmark is authoritative per session.

## 6. EasyOCR references remaining

- None in current code/docs except a grep command line that appears inside an old verification report. No functional EasyOCR usage.

## 7. Tesseract references remaining

- None in current code/docs.

## 8. OCR architecture

- Plate crop → quality analysis → adaptive preprocessing → Indian LPRNet (primary) → PaddleOCR (secondary, when available) → fusion/voting → Indian plate normalization → Indian plate validation → final confidence.
- LPRNet: `recognition/lprnet_ocr.py`; orchestration: `recognition/ocr_reader.py`.

## 9. LPRNet checkpoint source

- File: `models/lprnet_indian.pth`
- This session did not re-download it; it was already present and verified.
- Source repo of the Indian LPRNet project is the documented upstream for this class of checkpoint (`Indian_LPR`), but the file in this repo was already on disk and was verified for structure/compatibility rather than re-fetched.

## 10. Checkpoint SHA256

- `bdc17060638f01e23d9f05ad56bd9351e5a58c6bfafbe1e077330fb06fac12df`

## 11. LPRNet exact-match accuracy

- **25.66%** on the 113-sample clean evaluation set used in this session.

## 12. LPRNet character accuracy

- **56.41%** on the same set.

## 13. PaddleOCR accuracy

- **0%** in this run — PaddleOCR was not available/returning reads in the current environment.

## 14. Fusion accuracy

- **0%** in this run — PaddleOCR unavailable, so fusion could not produce reads.

## 15. Difficult-condition accuracy

- Not measured as a structured condition table in this run. Do not invent one.

## 16. OCR latency

- LPRNet average processing time per image: **0.6885 seconds** in this run. This is OCR inference time on the evaluation images, not end-to-end pipeline latency.

## 17. Detector metrics

- Vehicle detection: YOLOv8-based, COCO vehicle classes, ByteTrack tracking in `detection/vehicle_detector.py`.
- Plate detection: custom plate detector in `detection/detect_plates.py`, weight `models/best_plate_detector.pt`.
- No detector metrics were recomputed this session; the repo carries its own claimed plate-detector metrics in `models/README.md`, which should be treated as the model card, not as a freshly measured benchmark.

## 18. Trajectory tests

- Trajectory-related tests exist in `tests/` and pass in this session’s run (part of the 203-passed suite).

## 19. Analytics tests

- Analytics tests exist in `tests/` and pass in this session’s run.

## 20. GIS tests

- GIS functionality exists (`gis/gis_map.py`); GIS-facing frontend pages exist in the React app. No GIS-specific unit test run was executed this session beyond the main suite.

## 21. Alert tests

- Alert-related tests exist in `tests/` and backend tests; they pass in this session’s run.

## 22. Authentication tests

- Backend auth tests exist in `backend/tests/test_auth.py` and pass in this session’s run.

## 23. RBAC tests

- RBAC is partially evidenced through auth + role-aware backend APIs and frontend admin pages. Not every role-path was exhaustively tested this session.

## 24. Frontend build result

- `frontend/node_modules` and `frontend/dist` were removed this session. A full `npm ci` + `npm run build` was not completed this session; the frontend build is not verified green right now. That must be fixed before claiming a clean frontend build.

## 25. Backend test result

- `backend/tests`: **10 passed** this session.
- `tests/`: **203 passed, 1 skipped** this session.
- `integration_tests/test_sample_png.py`: **2 skipped** (missing media path; now honest).
- `tests/test_7_camera_network.py`: **10 passed, 1 skipped** (media dir not committed; now honest).

## 26. E2E result

- A true live E2E through login → dashboard → camera → detection → OCR → observation → trajectory → GIS → analytics → blacklist → anomaly → alert → admin was not executed end-to-end this session. The stack has the pieces and the backend test routes are green, but a full live E2E is not verified this session.

## 27. Performance results

- OCR latency measured for LPRNet only: 0.6885 s/image average in this run.
- No throughput, P95, or concurrent-stream measurements were produced this session.

## 28. Remaining failures

- `outputs/ocr_benchmark_report.json` shows PaddleOCR and fusion at 0% because PaddleOCR was unavailable in this run.
- Frontend build not verified this session.
- Full live E2E not executed this session.

## 29. Remaining limitations

- OCR accuracy is far below the SIH target; this is the dominant limitation.
- Some road graph / camera reliability constants are manual estimates.
- Redis is configured but not fully implemented as a real queue/cache in all paths.
- Speed outputs must be labeled as estimated corridor/camera-to-camera travel speed, not exact GPS vehicle speed.
- The demo/synthetic data path must be clearly separated from real pipeline observations.

## 30. SIH-26127 compliance status

- OCR (R1): **NOT MET** on the measured run.
- Trajectory, spatial-temporal, GIS, analytics, alerts, multi-camera, architecture scaffolding: implemented to varying degrees.
- Overall: **NOT READY** to be presented as meeting the full SIH requirement set, primarily because the OCR target is not met and the frontend build + full E2E were not verified this session.

## FINAL STATUS

**NOT READY**

Rationale: the repository is cleaner and internally more consistent than before this session, but core SIH evidence is missing or below target. The system is not ready to claim full compliance.
