# TrackX — Live Webcam Demo + Department-Selection Demo Freeze
**SIH26127 (Bharat Electronics Limited) — City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics**
Date: 2026-09-10

Proof this pass never touched production detection/OCR/tracking logic:

```
pipeline.py sha256: 21b0d294a43b51668b7983f393ef83045a1f03411a0dac3b0ce19133fd87b267
pipeline.py mtime:  2026-09-09 09:26 UTC (unchanged since before this session)
```

Regression baseline before this pass: `254 passed, 3 skipped` (root `tests/`) + `44 passed` (`backend/tests/`) = **298 passed, 3 skipped**.
Regression after this pass: **321 passed, 3 skipped, 0 failed** (23 new tests added, 0 removed, 0 broken).

---

## 1. Existing architecture (inspected before writing any code)

- **Detection/tracking**: `detection/vehicle_detector.py`'s `VehicleDetector.track_video(video_path)` — YOLOv8 + ByteTrack (`config/bytetrack_trackx.yaml`) over an entire video **file path**, `persist=True, stream=True`.
- **Plate detection**: `detection/detect_plates.py`'s `PlateDetector.detect_on_array()` — runs on a vehicle's own crop, not the whole frame.
- **Adaptive quality/preprocessing**: `recognition/plate_quality.py` + `recognition/ocr_reader.py`'s `preprocess_plate_crop()`.
- **OCR**: `recognition/ocr_reader.py`'s `PlateOCR.read()` (PaddleOCR) + `vote_plate_text()` (multi-frame fusion).
- **Plate state machine**: `pipeline._plate_status_for_track()` / `pipeline._plate_state_for_track()` (`UNKNOWN → LOW_CONFIDENCE → TENTATIVE → VERIFIED`).
- **Batch orchestration**: `pipeline.run_video_to_db()` — the one function every other real-inference endpoint calls; reads an entire video file frame-by-frame via `track_video()`, finalizes per-track records after the loop, writes to `ObservationStore`.
- **The "real WebSocket" endpoint** (`WS /api/v1/observations/live-stream/{camera_id}`): **misleadingly named for this task's purposes** — it does **not** accept an external live source. It re-processes a real video **already sitting on the server's disk** (`data/cameras/<CAM_ID>/videos/`) frame-by-frame and pushes each frame's real detections out over the socket as they're computed. It is one-directional (server → client only) and was **never wired to any frontend** before this pass (confirmed: no `WebSocket` usage existed anywhere in `frontend/src`).
- **Frontend**: `VideoDemoPage.tsx` already had two working, honest tabs — "Camera Media" (processes files already in a camera's folder) and "Upload Video" (`POST /ingest-video`, synchronous). **No fabricated aggregate "accuracy" number was found anywhere in the existing frontend** — every value already shown is a real per-run statistic or per-detection field. This was audited, not assumed.

**Conclusion from inspection**: a real live *webcam* had no path into the pipeline at all. `track_video()` only accepts a file path, and the plate detector only ever runs on a vehicle's own crop (never the whole frame) — so a phone showing *only* a close-up plate with no vehicle body **cannot** be detected by the current architecture. This is stated plainly in-app (LiveWebcamPage's "Demo Notes" panel) rather than worked around with a fake vehicle box.

---

## 2. Webcam architecture chosen, and why

**Chosen: Option A — browser `getUserMedia()` → canvas → JPEG → new dedicated WebSocket → backend real inference → JSON detections back → canvas overlay drawn client-side.**

Rejected alternatives and why:
- **Option B (backend opens the webcam directly via OpenCV)** — wrong physical model: the backend can run anywhere (this cloud sandbox, a cloud VM, a different machine from the operator's laptop), but the *webcam* is always physically attached to whatever machine the *browser* runs on. Only the browser is guaranteed to be colocated with the camera.
- **Reusing `/live-stream/{camera_id}` as-is** — architecturally impossible without a rewrite: that endpoint is push-only (server → client) and reads from a server-side file path, not from a client-supplied frame stream. It was reused *conceptually* (same envelope style, same `on_frame`-derived live-vote pattern already present in `pipeline.run_video_to_db()`), never copy-pasted differently.

**New backend pieces, each an *addition*, not a rewrite:**

1. `detection/vehicle_detector.py` — extracted the existing per-frame box→detection conversion logic out of `track_video()`'s loop body into `_detections_from_track_result()` (behavior-preserving refactor; full existing test suite re-verified green after this step, in isolation, before anything else was built on top of it). Added `track_frame(frame)` — ultralytics' own officially-documented `model.track(frame, persist=True)` pattern for live, one-frame-at-a-time tracking — and `start_new_live_session()` (resets this detector's IoU-fallback bookkeeping for a new session). **Zero behavior change to `track_video()`** — same detections, same track IDs, verified by the pre-existing test suite (`tests/test_vehicle_dedup.py`, `test_day1_visual_pipeline.py`, `test_day4_plate_crop.py`, `test_track_evidence_isolation.py`, `test_pipeline_db_integration.py`, `test_edge_cases.py`, `test_false_merge_regression.py` — 90/90 still passing after the refactor, before anything else was touched).
2. `live_webcam.py` (**new file**) — `LiveWebcamSession`, which re-runs the *exact same* imported functions `pipeline.run_video_to_db()` already uses per frame (`filter_spatial_outlier_readings`, `_plate_relative_position`, `_pad_plate_bbox`, `_plate_status_for_track`, `_plate_state_for_track`, `vote_plate_text`, `normalize_indian_plate`), just called incrementally across separate `process_frame()` calls instead of inside one loop over a video file. `pipeline.py` itself was **never edited** (see sha256 above) — everything reused is *imported*.
3. `backend/app/api/v1/observations.py` — new `WS /api/v1/observations/webcam-stream/{camera_id}` endpoint appended after the existing `live-stream` endpoint. Bidirectional JSON protocol (client sends captured frames, server sends back real per-frame results). Enforces **one active session at a time** (explicit, documented limitation — see §16) because ultralytics' `persist=True` tracker state lives on the shared singleton `VehicleDetector`, and two concurrent live sessions on it would interleave and corrupt both sessions' track IDs.
4. `frontend/vite.config.ts` — **real infra bug fixed**: the `/api` dev-proxy entry had `changeOrigin: true` but not `ws: true`. Both the new `webcam-stream` endpoint *and* the pre-existing (never-before-connected) `live-stream` endpoint live under `/api/...`, so in `npm run dev` a WebSocket upgrade to either would have failed to connect at all — a real gap that had simply never been exercised before, since nothing used to open a WebSocket from the frontend. Verified fixed against the real running dev server (see §8).

**Frontend, new page**: `frontend/src/pages/LiveWebcamPage.tsx`, route `/live-webcam`, sidebar entry "Live Webcam Demo" (`Capture & Recognition` group, next to "Detection Pipeline").

---

## 3. Files changed

| File | Type | What changed |
|---|---|---|
| `detection/vehicle_detector.py` | modified | Extracted `_detections_from_track_result()`; added `track_frame()`, `start_new_live_session()`. `track_video()` behavior unchanged. |
| `live_webcam.py` | **new** | `LiveWebcamSession` — per-session live temporal fusion, reusing `pipeline.py`'s functions. |
| `backend/app/api/v1/observations.py` | modified | Added `WS /webcam-stream/{camera_id}`; added `numpy` import. |
| `frontend/vite.config.ts` | modified | Added `ws: true` to the `/api` dev-proxy entry (real bug fix). |
| `frontend/src/pages/LiveWebcamPage.tsx` | **new** | The Part A physical webcam demo page. |
| `frontend/src/pages/VideoDemoPage.tsx` | modified | Added a third tab, "Live Stream (WS)" — Part B Mode 2 (connects to the existing `live-stream` endpoint). |
| `frontend/src/App.tsx` | modified | Added `/live-webcam` route. |
| `frontend/src/components/layout/Sidebar.tsx` | modified | Added "Live Webcam Demo" nav entry. |
| `tests/test_webcam_live_session.py` | **new** | 11 real-inference tests for `track_frame`/`LiveWebcamSession`. |
| `backend/tests/test_webcam_stream.py` | **new** | 10 real tests for the new WS endpoint (real detection, malformed frames, concurrency guard, lifecycle). |
| `backend/tests/test_demo_reliability.py` | **new** | 2 real tests — 3 consecutive `/ingest-video` cycles, confirming no cross-run state contamination. |

**Not changed**: `pipeline.py`, `recognition/*`, `config/bytetrack_trackx.yaml`, the database schema, and every other existing page/endpoint.

All 11 changed/new source files have been synced to `TrackX\` on your Windows machine (`abinivesh-m`, folder `C:\Users\abini\OneDrive\Desktop\sih26127\TrackX`).

---

## 4. WebSocket protocols

### `WS /api/v1/observations/webcam-stream/{camera_id}` (new, Part A)

```
server → client, once, right after accept:
  {"type":"ready","camera_id":"...","plate_detector_available":bool,"ocr_available":bool}

client → server, per captured frame:
  {"type":"frame","jpeg_b64":"<base64 jpeg>"}

server → client, per processed frame:
  {"type":"result","frame_idx":int,"elapsed_seconds":float,
   "vehicles":[{track_id, bbox, vehicle_type, vehicle_confidence,
                plate_bbox, plate_text, plate_status, plate_state,
                ocr_confidence, temporal_support, final_fusion_score,
                plate_quality_score, blur_score, preprocessing_mode,
                first_seen_frame}],
   "timing_ms":{"vehicle_detect":..,"plate_detect_and_ocr":..,"total":..}}

server → client, one bad frame (session stays open):
  {"type":"frame_error","detail":"..."}

server → client, fatal (connection then closes):
  {"type":"error","detail":"..."}   # e.g. "a live webcam session is already running"

client → server, to end:
  {"type":"stop"}
```

### `WS /api/v1/observations/live-stream/{camera_id}` (pre-existing, now wired up — Part B Mode 2)

Unchanged protocol (`started` / `frame` / `done` / `error`), documented in the code already; only the *frontend client* is new (`VideoDemoPage.tsx`'s "Live Stream (WS)" tab).

---

## 5. Camera lifecycle & error handling (LiveWebcamPage.tsx)

Handled, each verified by real browser test (see §8):
- `navigator.mediaDevices` unavailable → "This browser does not support camera access..."
- `NotAllowedError` → "Camera permission was denied..."
- `NotFoundError` → "No camera was found on this device." (**verified live** — see screenshot §8)
- `NotReadableError` → "...may already be in use by another application..."
- WebSocket connect failure → "Could not connect to the live processing backend."
- A second concurrent session → server sends `{"type":"error", detail: "...already running..."}`, shown in-page; the *first* session is unaffected (verified by test).
- Component unmount (operator navigates away) or clicking **Stop** → camera tracks stopped (`MediaStreamTrack.stop()`), WebSocket closed, capture interval cleared — the camera light goes off; verified no lingering interval/socket in code review and in the Playwright run (page teardown produced no errors).

---

## 6. Actual results — real inference evidence (not simulated)

All of the below is real model output, captured directly from this session's tool calls (not summarized from memory):

**`track_frame()` on a real photo (`/tmp/bus.jpg`, ultralytics' own bus demo image), 3 repeated calls:**
```
0 [('1', 'bus', 0.873)]
1 [('1', 'bus', 0.873)]
2 [('1', 'bus', 0.873)]
```
Same track_id (`1`) persisted across all 3 calls via `persist=True` — the whole point of the new entry point.

**`LiveWebcamSession` on real frames from the existing proven CCTV video (`data/cameras/CAM_01/videos/anpr_test1.mp4`), showing the plate-state machine genuinely progressing frame-by-frame (never VERIFIED on frame 0):**

| Frame | Track | Plate text | Status | State | Temporal support |
|---|---|---|---|---|---|
| 0 | 3 | UP14FS3664 | recognized | TENTATIVE | 1 |
| 3 | 3 | UP14FS3664 | recognized | TENTATIVE | 2 |
| 6 | 3 | UP14FS3664 | recognized | **VERIFIED** | **3** |
| 0 | 3 | UP16BA8695 | recognized | TENTATIVE | 1 |
| 3 | 3 | UP16BA8695 | recognized | TENTATIVE | 2 |
| 6 | 3 | UP16BA8695 | recognized | **VERIFIED** | **3** |
| 0 | 3 | UP1496 | recognized | TENTATIVE | 1 |
| 4 | 3 | UP1496 | **low_confidence** | LOW_CONFIDENCE | 2 |

That third example is worth calling out: when the real evidence genuinely doesn't support a confident read, the system honestly *demotes* to `LOW_CONFIDENCE` rather than forcing a plate — exactly the non-fabrication behavior required.

**End-to-end through the real running backend + real vite dev-server proxy** (a genuine Python WebSocket client, not the pytest in-process TestClient):
```
frame 0: vehicles=[('1', 'car', 'TENTATIVE')]  timing_ms={'vehicle_detect': 100.1, 'plate_detect_and_ocr': 316.6, 'total': 416.7}
frame 1: vehicles=[('6','car','UNKNOWN'), ('1','car','TENTATIVE'), ('7','car','UNKNOWN'), ('8','truck','UNKNOWN')]  total=551.1ms
frame 2: ...same 4 tracks, track 1 still TENTATIVE...  total=139.9ms
```

**Mode 2 (existing `live-stream` endpoint, now wired to the frontend) — real smoke test through the same real proxy:**
```
STARTED: {'video': 'anpr_test1.mp4', 'camera_id': 'CAM_01'}
frame 0: vehicles_in_frame=1 fps_so_far=3.15
frame 1: vehicles_in_frame=2 fps_so_far=4.51
frame 2: vehicles_in_frame=3 fps_so_far=3.51
```

---

## 7. End-to-end latency & FPS — honestly separated, never merged

Real measured per-frame timing (`timing_ms` above): **~90ms–700ms total per frame** depending on how many vehicles/plate crops are in view (first frame of a session is slower — model warm-up). This is the **real, measured "Processing FPS"** the UI derives (`1000 / avg_latency_ms`).

**"Camera FPS"** (how often the browser *attempts* to capture a frame) is fixed by design at ~2/s (`CAPTURE_INTERVAL_MS = 500`) and is measured from real `performance.now()` timestamps, not assumed from camera hardware specs.

These two numbers are **never averaged or conflated** anywhere in the UI — verified live: on a synthetic test camera with a trivially fast pipeline (blank/no vehicle), the real browser test measured **Camera FPS: 2, Processing FPS: 13.4** simultaneously, correctly showing the pipeline had spare capacity relative to the deliberately-throttled capture rate. Backpressure (a new frame is only ever sent once the previous one's result has returned) guarantees Processing FPS reflects genuinely completed work, never a growing backlog.

---

## 8. Visual QA — a real browser was actually driven, not just compiled

`npm run typecheck` and `npm run build` both pass cleanly. Beyond that (per your explicit "compiles ≠ tested" instruction), this session:

1. Started the **real backend** (`uvicorn backend.app.main:app`) — confirmed `yolo_vehicle`, `yolo_plate`, and `PaddleOCR` all report `healthy`/`true` via `/health`.
2. Started the **real frontend dev server** (`npm run dev`, port 3000, using the fixed `ws:true` proxy).
3. Drove a **real Chromium browser** (Playwright, headless) through the actual login flow, then `/live-webcam`, using Chromium's built-in synthetic **fake camera device** (`--use-fake-device-for-media-stream`) so `getUserMedia()` succeeds with a real (synthetic-pattern) video track — this exercises the real frontend JS path (capture → canvas → WebSocket → backend → overlay), not a mock of it.

**Screenshot — live session connected, real metrics:**
"● CAMERA CONNECTED · Source: Laptop Webcam · Mode: LIVE · Camera: CAM_WEBCAM_01" — the actual live (synthetic) camera feed renders in the video element; sidebar correctly highlights "Live Webcam Demo"; **"0 now visible / No vehicle currently in view"** is the correct, honest result for this synthetic test pattern (it contains no real vehicle) — confirming the system does not fabricate a detection just because a session is live.

Measured in the same real browser session: **Camera FPS: 2, Processing FPS: 13.4, Frames Sent: 12, Tracks Seen: 0, Vehicles Now: 0** — all real, all zero where zero is correct.

**Screenshot — camera-not-found handled gracefully (real browser, real error):**
Running the identical flow *without* the fake-camera flag (headless Chromium genuinely has no camera device) produced: **"● NOT CONNECTED"** status and a clear on-screen message, **"No camera was found on this device."** — no crash, no blank page, "Start Webcam" remains clickable to retry.

Console errors observed during the live-camera run: two `net::ERR_TUNNEL_CONNECTION_FAILED` entries, both from an unrelated external resource fetch (not from any of this session's own code paths) — no JavaScript exceptions (`pageerror`) were raised at any point across all three browser runs.

**What could NOT be tested from this session**: the literal physical scenario (a real phone showing a real plate, held up to a real laptop webcam). This sandbox has no camera hardware, and the desktop-bridge tools available here don't expose webcam capture. §10 below is the exact procedure to run that real test yourself.

---

## 9. Test results

```
python -m pytest tests/ backend/tests/ -q
...
321 passed, 3 skipped, 0 failed
```
(was 298 passed / 3 skipped before this pass — 23 new tests, 0 removed, 0 regressed)

New tests, real-inference, no mocking of YOLO/ByteTrack/PaddleOCR:
- `tests/test_webcam_live_session.py` (11): blank-frame → no fabricated detections; real bus photo → real detection + persisted track_id; `start_new_live_session()` resets fallback bookkeeping; `LiveWebcamSession` never returns `VERIFIED` on a single frame; multi-track evidence isolation; stale-track evidence expiry; **zero plate-crop files written to disk in live mode** (confirmed by directory diff).
- `backend/tests/test_webcam_stream.py` (10): `ready` message on connect; real frame → real detection over the actual WebSocket; malformed/empty frame → `frame_error`, session stays usable; unknown message type handled; `stop` message ends session cleanly; 10 consecutive bad frames → fatal `error`; **second concurrent session correctly rejected** while the first keeps working; session slot freed after disconnect.
- `backend/tests/test_demo_reliability.py` (2): 3 consecutive `/ingest-video` cycles each succeed independently with **zero new temp-file leakage per run** (methodology bug in my own first draft of this test caught and fixed mid-session — see note below); 3 consecutive real-vehicle uploads produce 3 distinct `video_filename`s, 3 distinct annotated-video URLs (no collision), and a DB count exactly matching the sum of each run's own reported count (no cross-run contamination).

**One honest note on this session's own process**: my first version of the 3-consecutive-cycle test asserted the upload-temp-file directory was *empty* after each run and failed — investigation showed the "leftover" file was dated **2026-09-08**, two days before this session, from unrelated earlier work, not a bug in `/ingest-video` (which already cleans up its own temp file via a `finally` block, confirmed by re-reading the code). The test's assumption (a pristine starting directory) was wrong, not the application; fixed to a proper before/after diff and re-verified passing. Reporting this rather than quietly fixing it, per your standing instruction to report accurately.

**Database hygiene**: my own manual verification (§6, §8) briefly wrote 6 real observation rows into your actual dev database (`outputs/results/observations.db`, camera `CAM_01`) while smoke-testing the pre-existing `live-stream` endpoint through a real client. These were identified precisely (ids 409–414, timestamps `2026-09-10T12:12:51.*`) and deleted; the database is back to its exact prior count of **408** observations.

---

## 10. Exact commands to run the demo

**Backend** (from the repo root):
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

**Frontend** (from `frontend/`):
```bash
npm install   # only if dependencies changed
npm run dev
```
Open **http://localhost:3000**, log in as `admin@trackx.com` / `admin123`.

- **Part A (physical webcam demo)**: sidebar → **Live Webcam Demo** (`/live-webcam`).
- **Part B Mode 1 (primary, recorded CCTV)**: sidebar → **Detection Pipeline** → **Upload Video** tab (unchanged, already reliable).
- **Part B Mode 2 (real-time validation stream)**: sidebar → **Detection Pipeline** → **Live Stream (WS)** tab (new) → pick a camera with a video (e.g. `CAM_01`) → **Connect & Stream**.

---

## 11. Exact physical setup instructions (Part A)

1. Open `/live-webcam` in a real browser on the machine whose webcam you want to use (Chrome/Edge/Firefox — not this sandbox).
2. Click **Start Webcam**, allow the camera permission prompt.
3. Wait for **"● CAMERA CONNECTED"**.
4. On your phone, open a photo or video of a **complete vehicle** (car/bus/truck/motorcycle) with its plate clearly visible — **not** a close-up of just the plate (the current architecture detects plates only inside a vehicle's own bounding box; see §1).
5. Hold the phone steady, filling a reasonable portion of the webcam frame, well-lit, not at a sharp angle.
6. Watch the right-hand "Live Detections" panel: a Track ID and vehicle type should appear within ~1–2 real capture cycles; the plate row should start as `TENTATIVE` and only become `VERIFIED` after several consecutive real readings agree (this is the state machine genuinely progressing, not a fixed delay).
7. Move the phone slightly — the same Track ID should persist (ByteTrack's normal short-occlusion tolerance).
8. Pull the phone out of frame — the vehicle should disappear from "Live Detections" within roughly `TRACK_EVIDENCE_EXPIRY_FRAMES` (90) processed frames of the track no longer being seen (at ~2 processed frames/sec that's on the order of a minute of true absence, tuned generously so it doesn't discard a track during a brief real-world glance-away; reduce `TRACK_EVIDENCE_EXPIRY_FRAMES` in `live_webcam.py` if you want faster visual "forgetting" for the demo, though the track already vanishes from the *current* list the instant ByteTrack itself stops reporting it — the expiry constant only governs how long OCR evidence memory is retained for a track that might return).
9. Click **Stop** when done — the camera indicator light should turn off immediately.

If you see *"a live webcam session is already running"*: another browser tab/window still has an open session — close it first (only one live session is supported at a time by design; see §16).

---

## 12–13. Backend/frontend/OCR/track results

Covered with real data in §6–§9 above (no separate fabricated section — every number already shown there is a real, reproduced tool-call result from this session).

---

## 14. Known limitations (stated plainly, not worked around)

1. **Only one live webcam session at a time.** Ultralytics' `persist=True` tracker state lives on the shared `VehicleDetector` singleton; concurrent sessions would corrupt each other's track IDs. A second connection is cleanly rejected with a clear message rather than silently producing wrong results.
2. **Plate-only (no-vehicle) frames are not detected.** The plate detector only ever runs inside a vehicle's own bounding box — this is true of the *existing*, unmodified architecture, not something this pass introduced or could safely change without touching `pipeline.py`'s core detection flow. Per your own instruction ("never fake a vehicle box"), this was left as an honest, documented constraint rather than worked around.
3. **ByteTrack's own internal ID counter is not hard-reset between live sessions.** A new session's real ByteTrack IDs may continue upward from a previous session instead of restarting at 1 — cosmetic numbering only, not a correctness issue (documented in `start_new_live_session()`'s own docstring).
4. **Live webcam observations are not persisted to the main database**, by deliberate design — an ad hoc physical demo session must never be able to contaminate the recorded-CCTV-upload flow's data or Vehicle Intelligence/Trajectory search results with un-vetted live-demo noise. If you want live-webcam results feeding the rest of the app later, that's a real, separate design decision to make deliberately, not a default.
5. **No per-job/run identifier column was added to the observations schema.** Assessed per your explicit instruction ("assess but do not rush... avoid unnecessary migrations before the demo"): every observation is already tied to `camera_id` + `timestamp` + `source` (the uploaded video's path, which is a fresh UUID-derived filename per upload — see `ingest_video()`'s `safe_name = uuid4().hex + ext`), which the 3-consecutive-run test (§9) confirmed is already sufficient to keep runs distinguishable and uncontaminated in practice. A dedicated `run_id` column remains a reasonable future improvement, not a demo blocker.
6. **This session could not physically test with a real webcam and a real phone.** Every claim in §6–§8 is either a real model-inference result on real image/video content, or a real browser session using Chromium's synthetic fake-camera device — genuine end-to-end mechanism proof, but not a substitute for you actually running §11.
7. **The validated OCR benchmark remains 37 real plates / 48.6% exact-match** (per your standing instruction — see `docs/AWIROS_VERIFICATION_AND_TRAINING_DECISION_2026-09-09.md`). Nothing in this pass changes that number, claims a higher one, or displays any aggregate "accuracy" anywhere in the UI (checked by grep across `frontend/src` — the only "accuracy" text is generic pre-existing marketing copy on `TrajectoryPage.tsx` with no attached number, unrelated to this pass).

## 15. Part B design/audit notes

- **"No AI-generated website look"**: this app's design system (`frontend/src/index.css`, `tailwind.config.js`) already explicitly documents and implements the operations-console aesthetic your spec asked for (flat surfaces, no gradients/glassmorphism, sharp corners, a real `.live-dot.is-live` blink for genuine live-feed state) — confirmed by reading it, not assumed. `LiveWebcamPage.tsx` and the new "Live Stream (WS)" tab reuse these exact classes; nothing was redesigned.
- **Backend endpoint verification**: `POST /ingest-video` and `WS /live-stream/{camera_id}` were both exercised for real in this session (§6, §9) — both work correctly, including CORS/auth (`ingest-video` requires the existing bearer-token auth; `live-stream` and the new `webcam-stream` intentionally do not, matching the existing endpoint's own precedent, not a new gap this pass introduced).
- **Reliability > new features**: per your closing instruction, this pass stops here — the webcam demo works reliably end-to-end for what could be tested from this environment, and Part B's Mode 1/Mode 2/reliability items are addressed. No further feature work was started.
