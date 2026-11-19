# TrackX — File-by-File Guide (what each part of the codebase actually does)

**Purpose:** a plain-language walkthrough of every major file in the pipeline, in the order data actually flows through them: Camera → Detection → OCR → Matching → Map → Intelligence → API → UI. Written for you to skim before a judge asks "walk me through your code," not as a replacement for the deeper audit report (`TRACKX_FINAL_PRE_SIH_AUDIT_2026-09-17.md`).

Every file below is real, working code unless explicitly marked otherwise.

---

## 1. Camera ingestion — getting frames into the system

**`network/rtsp_camera.py`**
Talks to your actual physical camera. `resolve_camera_source()` figures out whether a camera ID means a live RTSPS URL or a local file/folder. `resolve_rtsp_url()` builds the real connection string (`rtsps://<user>:<pass>@192.168.137.2:554/...`) from environment variables — the password is never hardcoded. `redact_rtsp_url()` is what makes sure that URL prints as `rtsps://****@192.168.137.2:...` anywhere it might show up in logs, UI, or docs. `probe_rtsp_connectivity()` is the quick "can I even reach this camera" check used by the camera status page. `open_camera_frames()` is the actual frame generator the live pipeline reads from.

**`network/ffmpeg_frame_source.py`**
Underneath `rtsp_camera.py`, this is what actually decodes the RTSPS stream — it launches FFmpeg as a subprocess and reads raw frames from its stdout via `iter_frames_via_ffmpeg()`. `DEFAULT_STALL_TIMEOUT_SECONDS = 15.0` means if no frame arrives for 15 seconds, it gives up rather than hanging forever. Known limitation, left alone on purpose: **no auto-reconnect** — if the camera briefly drops, the stream just ends and needs to be restarted from the UI. `-hwaccel cuda` is hardcoded, so this assumes an NVIDIA GPU is present.

**`network/camera_network.py`**
This is the "map" of your camera network — not detection code, just topology. `CAMERAS` is the hardcoded dict of your 7 cameras (CAM_01–07) with lat/long, name, road, direction. `ROAD_GRAPH` is ~18 hardcoded edges between camera pairs with real-world distance, speed limit, road type — this is what lets the system reason about whether a vehicle could plausibly have travelled from one camera to another in the time observed. `is_spatially_connected()` and `is_temporally_feasible()` (with a 1.3× speed-limit margin for traffic variance) are the actual plausibility checks used elsewhere. `CAMERA_RELIABILITY` is a manually-estimated per-camera confidence weight (CAM_01: 0.95, etc.) — hand-tuned, not learned from data, and the code says so honestly. `bearing_deg()`/`compass_direction()` compute direction of travel; `detect_impossible_travel()` flags physically-impossible camera-to-camera jumps.

**`demo/camera_simulator.py`**
This is what "Camera Media" processing reads from for any camera that isn't your live RTSPS feed. It has no detection logic at all — `list_camera_media()` just lists whatever image/video files sit in `data/cameras/<CAM_ID>/images/` and `.../videos/`, alphabetically, so whatever files are physically in that folder are what get processed when someone clicks "Start Detection Pipeline" for that camera. This is why replacing CAM_02's stored photo with a real one this morning was enough to fix it — no code change was needed, just the file on disk.

---

## 2. Detection — finding vehicles and plates in a frame

**`detection/vehicle_detector.py`**
Runs YOLO + ByteTrack on a frame or video. `track_frame()` handles a single frame (used by the live RTSPS path); `track_video()` handles a whole video file with `ultralytics`' `stream=True` mode so it doesn't load the whole video into memory at once. This assigns each vehicle a `track_id` that persists across frames — that's what lets the system say "this is the same car across 40 frames," not just "a car."

**`detection/detect_plates.py`**
A second, smaller detector specifically for license plates within a vehicle's bounding box. `find_plate_weights()` resolves which trained model file to load, defensively (checks a few candidate paths rather than assuming one fixed location).

**`recognition/plate_quality.py`**
Before even trying OCR, scores the cropped plate image on blur, brightness, and contrast using real OpenCV metrics — not guesses. A plate crop that's too blurry or too dark gets flagged early rather than wasting an OCR pass on something unreadable.

---

## 3. OCR — reading the plate text

**`recognition/ocr_reader.py`**
The core OCR engine, real PaddleOCR under the hood (not a mock/stub). A few things worth knowing cold:
- `preprocess_plate_crop()` — adaptive preprocessing, only applies certain image transforms when the quality score says they're needed, rather than always applying the same fixed filter.
- `OCR_SAMPLE_INTERVAL = 3` — during video processing, OCR doesn't run on every single frame (too slow); it samples every 3rd frame.
- `OCR_EARLY_STOP_MIN_READINGS = 7` and `OCR_EARLY_STOP_CONFIDENCE = 0.90` — if a track already has 7+ readings and they're agreeing at 90%+ confidence, the system stops spending compute on more OCR passes for that vehicle. This is a real performance optimization, not a shortcut on accuracy.
- `vote_plate_text()` — this is the actual "intelligence" layer of the OCR, and it's a genuine three-stage process: (1) whole-string voting across all readings of the same track, (2) confidence-weighted correction of commonly-confused characters (0/O, 1/I, 8/B, etc.) at each character position, (3) fragment clustering for cases where different readings caught different parts of the plate clearly. This is the part of the system that turns "12 noisy OCR readings of one plate" into one best-guess answer plus a confidence and reading count — it's legitimately more sophisticated than "just trust the OCR."

**`recognition/plate_normalizer.py`**
A regex gate for the real Indian plate format (`SSDDL[LL]NNNN` — state code, district code, 1–2 letters, 4 digits). A reading that doesn't match this shape at all gets rejected/flagged rather than accepted as-is.

---

## 4. The plate-state and confidence system (this is the part to get right when a judge asks about accuracy)

These live inside **`pipeline.py`**, the file that actually runs the full detect → OCR → fuse → write-to-DB sequence (`run_video_to_db()`), for both the live RTSPS path and the Camera Media/batch path.

- `LOW_CONFIDENCE_THRESHOLD = 0.55` — a single OCR reading below this confidence doesn't get treated as reliable on its own.
- `PLATE_STATE_VERIFIED_MIN_READINGS = 3` **and** `PLATE_STATE_VERIFIED_MIN_CONFIDENCE = 0.70` — both must be true (it's an AND, not an OR) for a plate to be marked **VERIFIED**. Otherwise it's TENTATIVE, LOW_CONFIDENCE, or UNKNOWN depending on how far short it falls.
- **Important distinction if a judge probes this**: `confidence` here is OCR model confidence, not measured real-world accuracy. Your actual hand-graded exact-match accuracy (from `docs/OCR_REAL_ACCURACY_AUDIT.md`, 15/35 real samples) is ~42.9%. These are two different numbers measuring two different things — don't let the two get conflated in an answer.
- `pipeline.py` is also where every observation gets tagged `data_source = "REAL_INFERENCE"` — this happens because the *inference itself* ran for real, regardless of whether the input photo/video was staged. That's the nuance behind this morning's CAM_02 investigation: the tag says "real inference ran," not "the input was guaranteed to be a live camera capture."
- `plate_crops_dir = RESULTS_DIR / "plate_crops"` — every plate crop the system is confident enough to act on gets saved to disk here (`outputs/results/plate_crops/`), which is what backs the "evidence" shown in the UI.

**`recognition/appearance.py`**
Separate from plate reading — this generates a 512-dimensional visual "fingerprint" of each vehicle using a pretrained ResNet18 (ImageNet weights), with a plain OpenCV color-histogram fallback if the model path isn't available. This is real, not randomly generated — it's what lets multi-camera matching use "does this look like the same car" as one signal, not just plate text.

---

## 5. Database — where everything gets written

**`database/observation_store.py`**
The core SQLite-backed store (`ObservationStore`). Every observation row carries a `data_source` field — `REAL_INFERENCE` or `DEMO_SYNTHETIC` — and `all_observations(real_only=True)` filters out the synthetic ones when a caller asks for it. This one flag is the backbone of the whole "never present fake data as real" design across the app. Seven sibling store files follow the same pattern for their own data: `alert_store.py`, `route_anomaly_store.py`, `congestion_store.py`, `camera_store.py`, `blacklist_store.py`, `vehicle_registry.py`, `backup_manager.py`.

---

## 6. Intelligence — turning individual detections into a story

**`intelligence/trajectory.py`**
`build_trajectories()` — links a vehicle's observations across multiple cameras into a single path. `MAX_CANDIDATE_GAP_SECONDS = 7200` (2 hours) — two sightings more than 2 hours apart aren't even considered as candidates for the same trip.

**`intelligence/fusion.py`**
`is_match()` — the actual scoring function that decides "is this the same vehicle at two different cameras." It's a weighted combination of four real signals: plate text similarity (0.45), visual appearance (0.25), temporal plausibility (0.15), spatial plausibility (0.15), with `MATCH_THRESHOLD = 0.55`. It also explicitly rejects any match that would require an impossible speed between the two sightings. This is the part of the system that justifies calling it "multi-camera trajectory fusion" rather than just "same plate text found twice."

**`intelligence/anomaly_scoring.py`** and **`intelligence/spatio_temporal.py`**
Real, substantive code built on the same road-graph primitives as `camera_network.py` — not stubs. These score things like unusual routes or unusual timing against the expected road network behavior.

**`intelligence/route_hypothesis.py`**
Real, complete code — but **not called by any API endpoint**. It exists and works if you called it directly in Python, but nothing in the running app currently triggers it. Don't describe this as a live feature if asked; it's an honest gap, not something to hide, but also not something to claim.

**`intelligence/alerts.py`**
`CAMERA_OFFLINE_HOURS = 24` lives here — this is the threshold both the CAMERA_OFFLINE alert and the Dashboard's "Active Cameras" status share, on purpose, so they never disagree with each other.

---

## 7. Backend API — what the frontend actually talks to

**`backend/app/api/v1/observations.py`**
The live-stream endpoint. `/live-stream/{camera_id}` is a WebSocket that calls `resolve_camera_source()` and streams annotated frames to the browser in real time — this is what CAM_01's live feed page runs on. `_draw_live_annotations()` draws the green vehicle box you see live; it intentionally does *not* draw a red plate-crop box (that's a simpler, faster annotation function than the one used for batch/uploaded-video results, which is why the live view looks a bit less detailed than a processed video). `/camera-source/{camera_id}?probe=true` is the camera connectivity status check. `/process-camera` is the file-based (Camera Media) entry point — separate code path from the live WebSocket, but both eventually call into `pipeline.py`.

**`backend/app/api/v1/cameras.py`**
Computes the real, non-fabricated camera status shown on the Dashboard and Camera Network pages. `_camera_status()` is a genuine three-way state: NOT_CONFIGURED (never produced an observation), OFFLINE (has observations, but none in the last 24h), ONLINE (observation within 24h). As of this morning's fix, `_camera_health_map()` passes `real_only=True`, so a camera can't appear ONLINE purely off old seeded demo data.

**`backend/app/api/v1/gis.py`, `congestion.py`, `analytics.py`**
All three correctly call the observation store with `real_only=True` — the city-wide traffic views never mix synthetic data into what's presented as real.

**`backend/app/api/v1/alerts.py`, `route_anomaly.py`**
Deliberately *not* filtered by `real_only` — same pattern as `vehicles.py`'s search, which is also intentionally unfiltered. The data is tagged (so the frontend can show a DEMO/OPERATIONAL badge), just not filtered out server-side. This is a conscious design choice, not an oversight — see the audit report if you want the full reasoning.

---

## 8. Frontend — what judges actually see

**`frontend/src/pages/DashboardPage.tsx`**
The Operations Center — real counts pulled from the API, not hardcoded. This is also where the "Active Cameras X/7" KPI and the honest "Online (recent observations) / No data yet" split live.

**`frontend/src/pages/CamerasPage.tsx`**
Shows each camera's real status via `/cameras/health` (correctly uses the health endpoint, not the raw unfiltered `/cameras` list).

**`frontend/src/pages/VehiclesPage.tsx`**
Search by plate; color-codes `plate_state` (VERIFIED green, LOW_CONFIDENCE red, TENTATIVE/UNKNOWN amber) — this is where you'll find this morning's clean `UP22AT3248` / 93.7% CAM_02 result.

**`frontend/src/pages/TrajectoryPage.tsx`**
Multi-camera path reconstruction on a map. Minor known gap: the map popup shows `plate_state` as plain text, not color-coded like VehiclesPage — cosmetic, not a data problem.

**`frontend/src/pages/AlertsPage.tsx`**
Has a genuinely working `SyntheticDataBadge` and a DEMO/OPERATIONAL watchlist split — this is one of the better honesty-in-UI features in the app, worth pointing to directly if a judge asks how you avoid misleading users.

---

## Quick answer key: "is X real or fake?"

| Component | Real or demo? |
|---|---|
| CAM_01 live detection | Real — physical RTSPS camera |
| CAM_02–07 "not connected" labels | Real — honestly not faked online |
| CAM_02's photo (as of this morning) | Real — swapped from an AI-generated test image to an actual traffic photo |
| YOLO detection, OCR, tracking | Real, on whatever image/video is fed in |
| OCR accuracy number to quote | ~40–43% exact-match, hand-graded (not the OCR model's own confidence score) |
| `route_hypothesis.py` | Real code, not wired to any endpoint — don't claim it live |
| Trajectory/fusion multi-camera matching | Real, 4-signal weighted scoring |
| RTSPS auto-reconnect | Does not exist — known, accepted limitation |

---

*Generated 2026-09-18, morning of the institutional round. Pairs with `TRACKX_FINAL_PRE_SIH_AUDIT_2026-09-17.md` for the full audit and Q&A prep.*
