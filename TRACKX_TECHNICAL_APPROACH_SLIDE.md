# SIH PPT — Technical Approach Slide Content (SIH26127, TrackX)

Copy-paste ready. Flowchart image attached separately (`trackx_pipeline_flowchart.png`) — embed it directly under "Methodology and process for implementation."

---

## Technologies to be Used

**Programming Languages**
Python (backend, AI/ML pipeline), TypeScript/JavaScript (frontend)

**AI / Computer Vision**
- YOLOv8 (Ultralytics) — vehicle detection and license-plate region detection
- ByteTrack — multi-object tracking (persistent vehicle IDs across frames)
- PaddleOCR — license plate text recognition
- OpenCV — image quality scoring (blur/brightness/contrast) and adaptive preprocessing
- PyTorch + ResNet18 (ImageNet-pretrained) — vehicle appearance embedding for cross-camera re-identification

**Backend**
FastAPI (REST + WebSocket API), SQLAlchemy ORM, SQLite (Postgres-ready for scale), JWT-based authentication, Uvicorn ASGI server

**Frontend**
React + TypeScript, Vite, Leaflet.js (interactive GIS maps, OpenStreetMap tiles — no API key dependency)

**Video / Streaming**
RTSPS (RTSP over TLS) for live camera ingestion, FFmpeg for frame decoding, WebSocket for real-time annotated-stream delivery to the browser

**Hardware**
- CP PLUS IP camera (RTSPS-capable CCTV hardware) — real physical camera integration, not simulated
- NVIDIA CUDA GPU — auto-detected for accelerated inference, with automatic CPU fallback

**DevOps / Deployment**
Docker, Render (tested deployment path), environment-variable-based secrets management (camera credentials never hardcoded or logged)

---

## Methodology and Process for Implementation

*(See attached flowchart — two-layer pipeline: Perception → Intelligence)*

**1. Camera Ingestion** — Live RTSPS feed (TLS-secured) or recorded video/image input, decoded frame-by-frame via FFmpeg.

**2. Vehicle Detection & Tracking** — YOLOv8 detects vehicles per frame; ByteTrack assigns a persistent track ID so the same physical vehicle is followed across many frames, not re-detected from scratch each time.

**3. License Plate Detection** — A second YOLO-based detector locates the plate region within each tracked vehicle's bounding box.

**4. Quality Gate & Adaptive Preprocessing** — Every plate crop is scored on blur, brightness, and contrast (OpenCV); preprocessing is applied conditionally based on that score, not blindly to every image.

**5. OCR Recognition** — PaddleOCR reads plate text from the preprocessed crop, sampled at a fixed frame interval (not every frame) to keep throughput real-time.

**6. Temporal Fusion & Confidence Tiering** — Multiple OCR readings of the same tracked vehicle are combined through a three-stage process: whole-string voting, confidence-weighted correction of commonly confused characters, and fragment clustering. The fused result is validated against the real Indian plate format and classified into one of four confidence tiers — VERIFIED, TENTATIVE, LOW_CONFIDENCE, UNKNOWN — rather than trusting any single OCR pass.

**7. Observation Persistence** — Every result is stored with camera ID, timestamp, GPS location, confidence, and an explicit REAL_INFERENCE / DEMO_SYNTHETIC data-source tag, giving the system a built-in audit trail.

**8. Multi-Camera Identity Fusion** — Sightings of the same vehicle across different cameras are linked using a weighted, 4-signal match: plate similarity (45%), visual appearance embedding (25%), temporal plausibility (15%), and spatial/road-network plausibility (15%). Matches implying a physically impossible speed between two cameras are explicitly rejected.

**9. Trajectory & Anomaly Intelligence** — Matched sightings are assembled into full multi-camera trajectories using a real road-network graph (not straight-line distance), enabling congestion analysis, route-anomaly detection, and watchlist/blacklist alerting.

**10. Operator Interface** — Real-time dashboard, GIS trajectory map, vehicle search, and alerts console, served through a combined REST + WebSocket API to the React frontend — built for a first-time operator to understand at a glance, not just for a developer.

**Working Prototype Status:** End-to-end pipeline is implemented and running against a live physical RTSPS camera — real detection, real OCR, real database persistence, and real multi-camera trajectory search, verified and recorded end-to-end (not a mockup or simulated demo).

---

*Paired with `trackx_pipeline_flowchart.png` for the visual on this slide.*
