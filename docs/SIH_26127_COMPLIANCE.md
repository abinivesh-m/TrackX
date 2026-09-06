# TrackX — SIH-26127 Compliance Map

**Problem statement:** City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics
**Organization:** BEL
**Theme:** Smart Automation
**Category:** Software

This document maps each requirement to status, evidence, measured metric where available, and limitation.
It is written to be shown to a technical evaluator. It does not inflate results.

## R1 — High-accuracy ANPR/OCR for Indian plates

- **Status:** PARTIAL
- **Evidence:** `recognition/lprnet_ocr.py`, `recognition/ocr_reader.py`, `models/lprnet_indian.pth`
- **Measured:** LPRNet exact-match 25.66%, character accuracy 56.41% on the 113-sample clean evaluation set used in the current run (`outputs/ocr_benchmark_report.json`, `docs/OCR_EVALUATION.md`)
- **SIH target:** >90% exact-plate recognition
- **Compliance:** NOT MET
- **Limitation:** LPRNet loads and runs but does not meet the accuracy target in the current state. PaddleOCR was not available in the current run, so fusion could not be measured here. This gap must not be presented as achieved.

## R2 — Single plate trajectory tracking across cameras

- **Status:** IMPLEMENTED
- **Evidence:** `intelligence/trajectory.py`, `tests/` trajectory-related tests, backend vehicle/trajectory APIs
- **Measured:** Trajectory building is functional on stored observations.
- **Limitation:** Trajectory quality depends on observation quality, OCR quality, and plate normalization. If OCR is weak, trajectories can still be built but links may be imperfect.

## R3 — Spatial-temporal vehicle tracking

- **Status:** IMPLEMENTED
- **Evidence:** `intelligence/fusion.py`, `intelligence/spatio_temporal.py`, `network/camera_network.py`
- **Measured:** Fusion uses plate + appearance + temporal + spatial signals; temporal feasibility and spatial connectivity helpers exist and are tested.
- **Limitation:** Some constants/road graph values are manual estimates, not learned from real traffic data.

## R4 — GIS visualization

- **Status:** IMPLEMENTED
- **Evidence:** `gis/gis_map.py`, React GIS pages, Streamlit map views
- **Measured:** Map generation produces trajectories and camera markers.
- **Limitation:** Basemap availability depends on external tile service; the UI should degrade gracefully and must not claim live data from a configured source if it is not actually available.

## R5 — Traffic analytics

- **Status:** IMPLEMENTED
- **Evidence:** `analytics/analytics.py`, backend analytics API
- **Measured:** Density, camera flow, OD patterns, congestion, route density, temporal trends, average corridor speed are computed from observations.
- **Limitation:** Speed should be labeled as estimated corridor/camera-to-camera travel speed, not exact GPS vehicle speed.

## R6 — Density analytics

- **Status:** IMPLEMENTED
- **Evidence:** `analytics/analytics.py`
- **Limitation:** Depends on quality/availability of real observations in the current DB.

## R7 — Origin-destination patterns

- **Status:** IMPLEMENTED
- **Evidence:** `analytics/analytics.py`
- **Limitation:** As above; only as good as the observed trajectory links.

## R8 — Congestion analysis

- **Status:** IMPLEMENTED
- **Evidence:** `analytics/analytics.py`
- **Limitation:** Requires real observations and camera topology.

## R9 — Route density

- **Status:** IMPLEMENTED
- **Evidence:** `analytics/analytics.py`
- **Limitation:** Same dependency on real data.

## R10 — Real-time blacklist alerts

- **Status:** IMPLEMENTED
- **Evidence:** `intelligence/alerts.py`, `database/blacklist_store.py`, `database/alert_store.py`, backend alert APIs, frontend alert pages
- **Measured:** Blacklist detection and alert generation exist and are integrated.
- **Limitation:** Real-time behavior depends on ingestion + DB + frontend refresh. Alert demo data must be clearly labeled if used.

## R11 — Suspicious route anomalies

- **Status:** IMPLEMENTED
- **Evidence:** `intelligence/alerts.py`, `intelligence/anomaly_scoring.py`
- **Measured:** Impossible travel time and suspicious route logic exist.
- **Limitation:** Thresholds must be configurable and not presented as finely tuned to real city data unless they are.

## R12 — Scalable architecture

- **Status:** PARTIAL
- **Evidence:** FastAPI backend, React frontend, Docker Compose for postgres + redis + backend + frontend, SQLite dev path, Redis config present
- **Limitation:** Redis is configured but not fully implemented as a real queue/cache in all code paths. Full production scaling has not been load-tested in this repo.

## R13 — Multi-camera support

- **Status:** IMPLEMENTED
- **Evidence:** `network/camera_network.py`, 7-camera Coimbatore network definition, multi-camera trajectory logic
- **Limitation:** Not all cameras have committed media under `data/cameras/*`; the network config is real, the raw footage ingestion is deployment-dependent.

## Claims that must not be presented as achieved

- >90% OCR accuracy — NOT achieved in the current measured run.
- Exact GPS vehicle speed — not provided; only estimated corridor/camera-to-camera travel speed.
- 100+ cameras, sub-5-second trajectory, 99.9% uptime — not measured here.

## Honest summary

TrackX implements the core platform behavior for SIH-26127: multi-camera ANPR observation handling, trajectory reconstruction, traffic analytics, GIS visualization, blacklist and anomaly alerts, and a usable admin/auth frontend+backend. The main weakness is OCR accuracy. That weakness is real and must be reported as such.
