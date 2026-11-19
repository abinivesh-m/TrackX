# TrackX — City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking

[![Tests](https://github.com/abinivesh-m/TrackX/actions/workflows/test.yml/badge.svg)](https://github.com/abinivesh-m/TrackX/actions/workflows/test.yml)
[![Security](https://github.com/abinivesh-m/TrackX/actions/workflows/security.yml/badge.svg)](https://github.com/abinivesh-m/TrackX/actions/workflows/security.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)

> **SIH 2026 · Problem Statement SIH26127 · Bharat Electronics Limited (BEL)**
> Team **NexussAI** (ID 178670) · Sri Krishna College of Engineering and Technology

TrackX is a centralized AI software platform that turns a city's existing CCTV/ANPR camera network into a unified vehicle-intelligence system. Instead of processing each camera in isolation, TrackX fuses **plate text + vehicle appearance + time + location** across cameras to reconstruct a single vehicle's complete journey on a GIS map, while computing city-wide traffic density, origin–destination patterns, congestion bottlenecks and real-time heatmaps, and flagging blacklisted vehicles and suspicious route anomalies.

**Live demo:** https://trackx-scoj.onrender.com · **Demo video:** https://youtu.be/nd0tCe5RH-8 · **Drive (datasets/models):** https://drive.google.com/drive/folders/1Z6f89znJKj9f1LXG2pi7tEtfIhIcJ57A

---

## ✨ Highlights

- **Three-stage OCR temporal fusion** — whole-string voting → confidence-weighted confusable-character correction (0/O, 1/I, 8/B, D/O, …) → fragment clustering. Turns 12 noisy reads of one plate into one best guess with a confidence + reading count.
- **Honest, ANDed 3-tier plate state** — `VERIFIED` requires **both** ≥3 readings **and** ≥70% confidence. `TENTATIVE` / `LOW_CONFIDENCE` / `UNKNOWN` otherwise. Confidence is OCR confidence, never overstated as real-world accuracy.
- **4-signal weighted multi-camera identity fusion** — plate text (45%) + visual appearance embedding (25%) + temporal plausibility (15%) + spatial plausibility (15%), with impossible-speed transitions explicitly rejected.
- **Real road-graph-aware trajectory math** — per-segment distances and travel-time plausibility from a real Coimbatore road graph, not straight-line haversine.
- **`data_source` discipline** — every observation tagged `REAL_INFERENCE` or `DEMO_SYNTHETIC`, with UI badges. City-wide views never mix synthetic data into what is presented as real.
- **Working auth** — JWT, PBKDF2 password hashing, audit logging, per-IP rate limiting, RBAC (admin/operator/auditor), blacklist management.
- **Reproducible accuracy auditing** — a hand-graded, evidence-backed OCR audit methodology with documented root causes and shipped fixes (see `docs/OCR_REAL_ACCURACY_AUDIT.md`). We measure and report honestly rather than inflate.

## 🏗️ Architecture

```
City CCTV (RTSPS) / recorded video
        │
        ▼
┌────────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  YOLOv8 + ByteTrack│──▶│ Plate detector   │──▶│ PaddleOCR +      │
│  (vehicle detect & │   │ (YOLO, fine-tuned│   │ temporal fusion  │
│   track)           │   │  or ONNX)        │   │ (vote_plate_text)│
└────────────────────┘   └──────────────────┘   └────────┬─────────┘
                                                         │
        ┌────────────────────────────────────────────────┘
        ▼
┌────────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ ResNet-18 vehicle  │   │ Identity fusion  │   │ Trajectory /     │
│ appearance (Re-ID) │──▶│ 4-signal score   │──▶│ road-graph + GIS │
└────────────────────┘   └──────────────────┘   └────────┬─────────┘
                                                         │
        ┌────────────────────────────────────────────────┘
        ▼
┌──────────────────────────────────────────────────────────────────┐
│ FastAPI backend · PostgreSQL/SQLite · Redis · React + Vite UI   │
│ Dashboard · Vehicles · Trajectory · GIS · Analytics · Congestion│
│ RouteAnomaly · Alerts · Cameras · Admin (RBAC + audit log)     │
└──────────────────────────────────────────────────────────────────┘
```

## 📁 Project structure

```
TrackX/
├── backend/          FastAPI app (auth, cameras, vehicles, analytics, alerts, …)
├── frontend/         React + TypeScript + Vite web UI
├── detection/        YOLO plate + vehicle detection, training, validation
├── recognition/      OCR (PaddleOCR), LPRNet, normalizer, appearance (Re-ID)
├── network/          Camera topology + Coimbatore road graph
├── intelligence/     Fusion, trajectory, anomaly scoring, alerts, route hypothesis
├── database/         SQLite/Postgres stores (observation, alert, blacklist, …)
├── analytics/        Traffic density, OD patterns, congestion model
├── gis/              Folium interactive map generation
├── demo/             Offline/video demo flows, seeding, visual pipeline
├── tests/            Unit tests (155 passing)
├── backend/tests/    API + integration tests
├── docs/             Audits, accuracy reports, tuning notes
├── models/           Model weights (best.onnx shipped; .pt via release assets)
└── pipeline.py       CLI entry point (detect → OCR → fuse → DB)
```

## 🚀 Quick start

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
# Dev login: admin@trackx.com / admin123  (change for anything beyond a local demo)
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev
# Opens http://localhost:5173
```

### CLI pipeline (offline video)
```bash
python pipeline.py --video data/sample.mp4 --plate_weights models/best.onnx --camera_id CAM_01 --lat 11.0 --long 77.0
```

### Run tests
```bash
# Root suite
python -m unittest discover -s tests -p "test_*.py"

# Backend suite
cd backend && python -m pytest tests/ -q
```

## 🎯 SIH26127 requirement coverage

| Requirement (from PS) | TrackX implementation |
|---|---|
| High-accuracy ANPR/OCR (>90% target) | PaddleOCR + multi-frame temporal fusion + adaptive preprocessing + confidence tiers (measured & audited; see `docs/OCR_REAL_ACCURACY_AUDIT.md`) |
| Single-plate trajectory tracking | `intelligence/trajectory.py` + `intelligence/fusion.py` (4-signal) on Coimbatore road graph |
| Macro traffic flow analytics | `analytics/analytics.py` — density, OD patterns, congestion, heatmaps |
| GIS-integrated dashboard | React + FastAPI + Folium/Leaflet maps |
| Real-time alert system | Blacklist + route-anomaly + repeated-camera detection, persisted |

## 🗺️ Roadmap (productionization)

TrackX is a working prototype (TRL 4–5). The following are scoped, known next steps — presented transparently rather than hidden:

- **OCR → >90%**: retrain on ANPR-resolution Indian plates + per-vehicle multi-frame voting (dataset + GPU time).
- **Horizontal scalability**: job queue for concurrent camera processing, Postgres/PostGIS in production, horizontal workers.
- **Camera onboarding**: ONVIF-style discovery instead of the current hardcoded camera dict.
- **Secrets at rest**: encrypt the RTSP credentials (currently in `.env`).
- **RTSPS auto-reconnect** on a camera drop.
- **Wire `route_hypothesis.py`** into a live endpoint (code exists, not yet exposed).
- **Learned `CAMERA_RELIABILITY`** weights from real match outcomes instead of hand-tuning.

## 🔐 Security & data integrity

- `data_source` tagging (`REAL_INFERENCE` / `DEMO_SYNTHETIC`) across DB and read endpoints, with UI badges.
- JWT auth, PBKDF2 password hashing, audit logging, per-IP rate limiting, RBAC.
- `.env` is gitignored; only `.env.example` is committed.
- No model weights (`.pt`) or databases (`.db`) are committed; `models/best.onnx` is the one shipped artifact so plate detection works out of the box.

## 📜 License

MIT — see [LICENSE](LICENSE).

## 👥 Team

NexussAI · Abinivesh M (lead) · Boobana D · Abishek M · Abhinivesh K · Nitin Kumar R · Sri Shylesh S · Mentors: M. Kalimuthu, S. Shanmuga Raju · Sri Krishna College of Engineering and Technology.