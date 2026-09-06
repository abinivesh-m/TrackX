# TrackX — Phase 0 REPOSITORY AUDIT

**Date:** 2026-09-05
**Scope:** Full recursive inventory of the TrackX workspace.

## 0. Repository footprint (top-level, as seen by `ls -la`)

TrackX is a mixed Python/React/FastAPI/Streamlit workspace with a large amount of
audit/cleanup/analysis cruft at the root and a heavy generated-output tree under `outputs/`.

Notable top-level items:
- Many standalone SCRIPTS at the root (`analyze_*.py`, `benchmark_*.py`, `build_*.py`,
  `check_*.py`, `create_*.py`, `download_*.py`, `evaluate_*.py`, `extract_*.py`,
  `inspect_samples.py`, `run_audit.py`, `run_demo.py`, etc.).
- Many standalone REPORTS at the root (`*.md` and `*.json`) most of which are intermediate
  audit artifacts rather than authoritative docs.
- Two YOLO weight files at root: `yolo11n.pt`, `yolov8n.pt`.
- One SQLite DB at root: `test.db`.
- A frontend build artifact tree `frontend/dist` and `frontend/node_modules`.
- Multiple `__pycache__` trees across the repo.
- `.pytest_cache`, `.streamlit/`, `Screenshots/`, `temp_frames/`, `runs/`,
  `logs/`, `scripts/`, `demo/`, `network/`, `intelligence/`, `outputs/`.

## 1. Python source inventory

Core packages (have `__init__.py`, are importable as packages):
- `analytics/` — traffic analytics (`analytics.py`)
- `backend/app/` — FastAPI application, routers, models, schemas, services, websocket
- `backend/alembic/` — DB migrations (incl. `versions/`)
- `backend/tests/` — FastAPI tests (incl. `conftest.py`)
- `dashboard/` — Streamlit dashboard (`dashboard.py`, `system_health.py`, `theme.py`)
- `database/` — stores: observation, camera, blacklist, alert, backup, vehicle registry
- `demo/` — demo scripts (`visual_pipeline.py`, `run_alert_demo.py`, `seed_*.py`, `camera_simulator.py`)
- `detection/` — YOLO vehicle+plate detection (`vehicle_detector.py`, `detect_plates.py`, `train_yolo.py`, `validate_dataset.py`)
- `gis/` — map generation (`gis_map.py`)
- `intelligence/` — fusion, trajectory, alerts, anomaly scoring, route hypothesis, spatio-temporal
- `network/` — camera network + road graph (`camera_network.py`)
- `recognition/` — OCR + plate matching + appearance (`ocr_reader.py`, `lprnet_ocr.py`, `anpr_lab.py`, `plate_matcher.py`, `plate_normalizer.py`, `appearance.py`, `ocr_evaluation.py`, `reid_evaluation.py`)
- `scripts/` — misc scripts
- `tests/` — pytest/unittest suites
- `integration_tests/` — integration tests

Root-level Python files (many appear to be throwaway audit/analysis scripts):
- `pipeline.py`, `config.py`, `run_demo.py`, `run_audit.py`, `verify_*.py`, `benchmark_*.py`,
  `analyze_*.py`, `build_*.py`, `check_*.py`, `create_*.py`, `download_*.py`, `evaluate_*.py`,
  `extract_*.py`, `inspect_samples.py`, `measure_trajectory_latency.py`, `update_*.py`, `test_backend_config.py`,
  `backend_smoke_test.py`, `dashboard_camera_selection_test.py`, `audit_dataset.py`,
  `audit_ocr_dataset_quality.py`, `comprehensive_dataset_audit.py`, `comprehensive_ocr_audit.py`,
  `remove_dataset_overlap.py`, `_pyflakes_report.txt`, `_scan_syntax.py`, `_smoke_test.py`, etc.

## 2. TypeScript/React source inventory

- `frontend/src/` — React/TypeScript pages, services, contexts, types, components.
- `frontend/` build tooling: `vite.config.ts`, `tsconfig.json`, `tailwind.config.js`,
  `postcss.config.js`, `package.json`, `package-lock.json`, `index.html`, `nginx.conf`,
  `Dockerfile`.
- `frontend/dist/` — built frontend bundle (present).
- `frontend/node_modules/` — present (should be removed from the shipped repo).

## 3. FastAPI backend inventory

- `backend/app/main.py` — FastAPI app, lifespan, routers.
- `backend/app/api/` — v1 routers: `vehicles`, `trajectory`, `gis`, `analytics`, `alerts`,
  `cameras`, `observations`, `admin`, `deps`.
- `backend/app/core/` — `config.py`, `database.py`, `security.py`, `logger.py`.
- `backend/app/models/` — SQLAlchemy models.
- `backend/app/schemas/` — Pydantic schemas.
- `backend/app/services/` — business logic services.
- `backend/app/websocket/` — websocket manager.
- `backend/alembic/` — Alembic migrations.
- `backend/tests/` — FastAPI tests.
- `backend/seed_db.py` — creates default admin user.

## 4. Streamlit / prototype UI inventory

- `dashboard/dashboard.py` — main Streamlit dashboard (5 tabs).
- `dashboard/system_health.py` — system health page.
- `dashboard/theme.py` — Streamlit theme config.

## 5. OCR modules inventory

- `recognition/ocr_reader.py` — OCR engine wrapper. Primary: LPRNet. Secondary: PaddleOCR.
  Documented fallback chain no longer includes EasyOCR in code paths.
- `recognition/lprnet_ocr.py` — LPRNet model + `LPRNetOCR` wrapper + CTC decode.
- `recognition/anpr_lab.py` — lab-style multi-engine evaluation.
- `recognition/ocr_evaluation.py` — standalone evaluator module.
- `recognition/plate_matcher.py` — fuzzy plate similarity + normalization helpers.
- `recognition/plate_normalizer.py` — Indian plate normalization.
- `recognition/appearance.py` — appearance embedding.
- `recognition/reid_evaluation.py` — ReID-style evaluation script.

**OCR stack:**
- LPRNet (primary, Indian plates) — `models/lprnet_indian.pth`.
- PaddleOCR 2.7.x (secondary) — auto-downloads Paddle models.
- Tesseract is referenced in old reports as a historical fallback but is not in the current
  authoritative OCR code paths.

## 6. Detection modules inventory

- `detection/vehicle_detector.py` — YOLOv8/11 vehicle detector + ByteTrack tracking.
- `detection/detect_plates.py` — YOLO plate detector wrapper.
- `detection/train_yolo.py` — fine-tuning wrapper around ultralytics.
- `detection/validate_dataset.py` — validates YOLO-format dataset (no torch needed).
- `detection/data.yaml.example` — example YOLO dataset config.

Vehicle classes used: car, motorcycle, bus, truck (COCO). Plate detector is custom-trained.

## 7. Trajectory modules inventory

- `intelligence/trajectory.py` — `build_trajectories()`: multi-camera trajectory reconstruction.
- `intelligence/fusion.py` — identity match scoring (plate + appearance + temporal + spatial).
- `intelligence/alerts.py` — blacklist + route anomaly detection.
- `intelligence/anomaly_scoring.py` — anomaly scoring helpers.
- `intelligence/route_hypothesis.py` — route hypotheses.
- `intelligence/spatio_temporal.py` — spatio-temporal reasoning helpers.
- `intelligence/what_if_simulator.py` — simulator/assessment tool.

## 8. Analytics modules inventory

- `analytics/analytics.py` — traffic density, camera flow, OD patterns, congestion, route density,
  temporal trends, average corridor speed.

## 9. GIS modules inventory

- `gis/gis_map.py` — Folium-based map generation (camera locations, trajectories, heatmap, OD flow).

## 10. Alert modules inventory

- `intelligence/alerts.py` — alert generation from trajectories + blacklist.
- `database/alert_store.py` — alert persistence.
- `database/blacklist_store.py` — blacklist persistence.
- `backend/app/api/v1/alerts.py` — alert API.
- `backend/app/api/v1/admin.py` — admin endpoints incl. blacklist management.

## 11. Database inventory

- SQLite used as default/dev store; PostgreSQL+PostGIS path supported in config.
- `database/observation_store.py` — observation CRUD + bridge from visual pipeline.
- `database/camera_store.py` — camera config store.
- `database/blacklist_store.py` — blacklist.
- `database/alert_store.py` — alerts.
- `database/vehicle_registry.py` — vehicle registry.
- `database/backup_manager.py` — DB backup helper.
- `backend/alembic/` — migrations.
- `backend/trackx.db` — SQLite file present (dev DB).

## 12. Redis / event queue inventory

- `backend/app/core/config.py` — Redis host/port config present.
- `docker-compose.yml` — defines a Redis service.
- Redis is referenced as a future cache/queue component. Actual event queue implementation
  appears limited; some dashboards report Redis status as “connected” in code paths that look
  like demo-friendly stubs. Needs honest classification later.

## 13. Authentication inventory

- `backend/app/core/security.py` — JWT + password hashing.
- `backend/app/api/deps.py` / `backend/app/api/v1/deps.py` — auth dependencies.
- `backend/app/api/v1/admin.py` — admin endpoints.
- `backend/seed_db.py` — default superuser creation.
- `backend/.env` + `backend/.env.example` — env config for JWT secret, DB, Redis, etc.

## 14. RBAC inventory

- Role fields exist in user model/schemas.
- Frontend pages have role-aware UI (admin page, etc.).
- Server-side auth dependencies exist in FastAPI.

## 15. Admin inventory

- `backend/app/api/v1/admin.py` — admin API.
- `frontend/src/pages/AdminPage.tsx` — admin console UI (users/system/security/database/logs tabs).
- Dashboard admin features also exist in Streamlit side.

## 16. Monitoring inventory

- `backend/app/core/logger.py` — logging.
- `logs/` — log directory.
- System health pages report library availability.
- There are old hardcoded operational metrics in various reports/demos that must be audited.

## 17. Docker inventory

- `docker-compose.yml` — postgres + redis + backend service definitions.
- `backend/Dockerfile` — backend container build.
- `frontend/Dockerfile` + `frontend/nginx.conf` — frontend container build.

## 18. Kubernetes inventory

- Not found as a first-class artifact set. If present, likely limited. Confirmed only that the
  repo leans on Docker Compose for deployment story.

## 19. Prometheus / Grafana inventory

- Not found as configured monitoring stack in this repo. Architecture docs mention enterprise
  production architecture aspirations; this workspace does not appear to include actual
  Prometheus/Grafana configuration.

## 20. Tests inventory

- `tests/` — multiple test files (unit + integration-style).
- `backend/tests/` — FastAPI tests.
- `integration_tests/` — integration tests requiring heavier deps.
- Existing test suites rely on stubbing heavy vision libs in many places.

## 21. Datasets inventory

Data appears spread across several locations and many evaluation artifacts:
- `data/` does not exist as a top-level directory in this workspace; OCR evaluation datasets and
  crop sets appear under `outputs/crop`, `outputs/contact_sheets`, and various benchmark scripts
  reference evaluation JSON sets.
- Several benchmark/evaluation JSON files exist under `outputs/`.
- Ground-truth/plate-label JSON exists: `external_plates_info.json` (large).
- There are synthetic plate image scripts and generated contact sheets.

This repo’s dataset organization is messy and must be classified carefully; do NOT assume a clean
`data/train|validation|test` layout exists yet.

## 22. Models inventory

- `models/best_plate_detector.pt` — plate detector (present).
- `models/best.onnx` — ONNX export (present).
- `models/lprnet_indian.pth` — LPRNet Indian plate checkpoint (present).
- `models/README.md` — model docs.
- Root YOLO weights: `yolov8n.pt`, `yolo11n.pt` (present).

There is ambiguity about whether `best.onnx` and `best_plate_detector.pt` are both production
artifacts or one is stale. Needs reconciliation during cleanup.

## 23. Reports inventory (large, messy)

Many reports exist at root and in `outputs/`. Many are intermediate audit/verification artifacts.
Authoritative docs should be consolidated under `docs/`.

Highlights:
- `FINAL_VERIFICATION_REPORT.md`, `FINAL_SIH_COMPLETION_REPORT.md`, `FINAL_PRODUCT_VERIFICATION.md`,
  `FINAL_SIH_COMPLETION_REPORT.md`, `PRODUCTION_READINESS_REPORT.md`, `E2E_VERIFICATION_REPORT.md`,
  `OCR_IMPROVEMENT_PLAN.md`, `OCR_TECHNICAL_ASSESSMENT.md`, `OCR_CLEANUP_PLAN.md`, `OCR_CLEANUP_REPORT.md`,
  `CLEAN_OCR_EVALUATION_REPORT.md`, `CLEAN_OCR_FINAL_REPORT.md`, `SIH_COMPLIANCE.md`,
  `SIH_REQUIREMENT_ALIGNMENT.md`, `ARCHITECTURE_STRATEGY.md`, `DAY2_REPORT.md`, `REPAIR_REPORT.md`,
  `FIXES_SUMMARY.md`, `INVESTIGATION_SUMMARY.md`, `DATA_GOVERNANCE_PRIVACY.md`, `ALERT_SYSTEM_GUIDE.md`,
  `README.md`, `sih_requirement_verification.json`, `sih_requirement_verification.py`.

Many root-level `*.md` and `*.json` files appear to be throwaway audit outputs and should be
classified for cleanup.

## 24. Screenshots inventory

- `Screenshots/` — multiple PNG screenshots dated 2026-08-24.

These look like demo screenshots. If stale/misleading, archive or remove.

## 25. Generated outputs inventory

- `outputs/` — large generated tree:
  - `outputs/benchmark_*.json`, `outputs/clean_*.json`, `outputs/demo_ocr_evaluation.json`,
    `outputs/ocr_baseline_*.json`, `outputs/ocr_benchmark_report.json`, `outputs/records.json`,
    `outputs/reid_evaluation_report.json`
  - `outputs/contact_sheets/` — HTML contact sheets with base64-embedded images.
  - `outputs/crop/`, `outputs/logos/`, `outputs/results/`

Much of this is generated benchmark/debug output. Needs cleanup but must preserve the authoritative
benchmark set if it is the fixed evaluation set.

## 26. Documentation inventory

- `README.md` — main readme.
- `docs/` — currently only `FINAL_VALIDATION_REPORT.md` and `SIH_REQUIREMENT_MATRIX.md`.
- Many docs currently live at root instead of `docs/`.

Target: authoritative docs under `docs/`; root docs trimmed to README (+ maybe a few integrator notes).

## 27. Configuration inventory

- `backend/.env` — actual env (may contain real secrets — inspect carefully).
- `backend/.env.example` — template (exists and looks appropriate).
- `backend/alembic.ini` — Alembic config (contains a hardcoded default PG URL — audit).
- `backend/requirements.txt` — backend deps.
- `requirements.txt` — root/Python deps (appears to be the main / non-backend Python env).
- `frontend/package.json` + `package-lock.json` — frontend deps.
- `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`.

## 28. Environment files inventory

- `backend/.env` (exists — inspect).
- `backend/.env.example` (exists — keep).

## 29. Frontend build artifacts inventory

- `frontend/dist/` — built bundle.
- `frontend/node_modules/` — must be removed from repo.
- Source maps present under `frontend/dist/assets/*.js.map`.

## 30. Training artifacts inventory

- `detection/runs/` — YOLO training artifacts (present).
- `runs/` — another runs tree at root.
- Various benchmark/OCR experiment JSON under `outputs/`.
- No clear separate “production vs benchmark vs obsolete” labeling for all artifacts.

## Search summary (keyword hits)

- EasyOCR: appears in historical reports and old fallback-chain mentions; current authoritative
  code paths use LPRNet + PaddleOCR. Reports claim zero runtime EasyOCR references after cleanup.
- Tesseract: appears in old reports as historical fallback; not in current authoritative OCR paths.
- LPRNet: core OCR engine in code (`recognition/lprnet_ocr.py`, `recognition/ocr_reader.py`).
- PaddleOCR: secondary OCR engine; installed in a Python 3.11 environment per reports.
- YOLO/Ultralytics: vehicle + plate detection.
- ByteTrack: tracking in `detection/vehicle_detector.py`.
- ReID: limited — `recognition/appearance.py` uses generic pretrained embedding; not a trained
  vehicle ReID model.
- Trajectory: `intelligence/trajectory.py`.
- GIS: `gis/gis_map.py`, plus React frontend GIS pages.
- Streamlit: `dashboard/`.
- React: `frontend/`.
- FastAPI: `backend/app/`.
- Redis: config + compose, but not fully implemented as a real queue/cache in code paths reviewed.
- PostgreSQL: supported in config + migrations.
- Docker: compose + Dockerfiles present.
- Kubernetes: not found.
- Prometheus/Grafana: not found.

## Suspicious / questionable findings (to verify, not to assume)

- Root has a huge scatter of intermediate audit scripts and reports — many likely obsolete.
- `outputs/` is full of generated benchmark/debug artifacts.
- `frontend/node_modules/` and `frontend/dist/` are shipped artifacts that should be removed.
- Multiple `__pycache__` trees.
- `.pytest_cache/`.
- `Screenshots/` may be stale demo screenshots.
- `temp_frames/`, `logs/`, `scripts/` may contain temporary cruft.
- Two root YOLO weights (`yolo11n.pt`, `yolov8n.pt`) — which is actually used by default?
- `models/best.onnx` vs `models/best_plate_detector.pt` — are both current?
- `backend/.env` must be audited for real secrets.
- `backend/alembic.ini` and `backend/alembic/env.py` contain a default `trackx_password` connection
  string — needs environment-variable sourcing, not committed defaults.
- Many reports contain historical accuracy numbers; only one authoritative OCR benchmark should remain.

## Action items (Phase 1+)

1. Generate `docs/REPOSITORY_AUDIT.md` (this file is the working audit; final will be rewritten cleanly).
2. Audit and lock down secrets (`backend/.env`, `.env.example`, alembic configs, seed_db, logs, UI).
3. Create/update `backend/.env.example` if it is not already placeholder-only.
4. Remove shipped build artifacts and caches carefully:
   - `frontend/node_modules/`
   - `frontend/dist/` (regenerate via `npm run build` only when needed)
   - `__pycache__` trees
   - `.pytest_cache/`
   - obvious temp/debug outputs after classifying them
5. Reconcile models: decide production set vs stale duplicates.
6. Reconcile root YOLO weights: keep the one actually used by default.
7. Reconcile OCR artifacts: keep one authoritative benchmark + evaluation set; archive the rest.
8. Reconcile reports: promote authoritative docs to `docs/`; remove/rename intermediate root reports.
9. Classify `outputs/*` and `data`-equivalent artifacts before deletion.
10. Verify OCR engine state + LPRNet checkpoint in the current environment before finalizing claims.
