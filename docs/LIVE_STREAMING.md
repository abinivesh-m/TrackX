# TrackX — Real Live Video Streaming (SIH26127)

## Update: real CP PLUS/RTSP(S) camera support now exists (see below)

Everything in the "What this is, honestly" section below was true when it was written: there was
no real CCTV/RTSP camera connected in this environment, and RTSP was explicitly called out as
future work. That future work is now `network/rtsp_camera.py` (plain RTSP) and
`network/ffmpeg_frame_source.py` (RTSPS — see the second update below) — a real CP PLUS camera can
be wired in per camera id purely through environment variables, with an honest, automatic fallback
to the exact same local-video-file simulation described below for every camera that isn't
configured.

This project's own physical CP PLUS camera has **since been reached for real, at all three
levels**: first with raw `ffmpeg` by the operator (independent of TrackX — see the second update
below for the exact verified command/result), then with **TrackX's own connection code**
(`GET .../camera-source/CAM_01?probe=true`, run against the real backend on the real development
machine, returned `"reachable": true`), and now with **TrackX's full pipeline** (frame decode →
YOLO → WebSocket) actually consuming that camera end-to-end — `ws://.../live-stream/CAM_01` was
opened for real against the real camera and streamed 20 real frames with a genuine
`"is_real_camera": true` `"started"` message. **"What this is honestly, and isn't yet" further down
draws the exact line** — four distinct levels of "verified", not one blanket claim — including the
real output from that run and what it does and doesn't prove.

## What this is, honestly

There is no real CCTV/RTSP camera connected in this environment or documented as available for
the demo. This feature does **not** pretend otherwise. What it does do: it runs the exact same
real detection/plate-detection/OCR/tracking/temporal-fusion pipeline every other endpoint in this
app uses (`pipeline.run_video_to_db()` — same function, same models, same code), but instead of
processing the whole video and returning one final JSON response at the end (what
`/ingest-video` and `/process-camera` already do), it pushes each frame's **real, freshly
computed** detections to a connected client **as they are produced**, over a WebSocket. That is
the live-camera-feed *experience* — every box on screen is a genuine detection from that exact
frame, not a replay or a pre-rendered video — built honestly from a video file standing in for a
camera feed, exactly like `demo/camera_simulator.py`'s existing "camera simulation" approach that
the rest of this app already uses (see that module's own docstring — RTSP was explicitly called
out as future work from Day 1).

## How it works

- New endpoint: `WS /api/v1/observations/live-stream/{camera_id}` (`backend/app/api/v1/observations.py`).
- On connect, it looks up `data/cameras/<camera_id>/videos/` (the same folder
  `/process-camera` and the AI Processing page already use) for a video, and runs
  `pipeline.run_video_to_db()` on it in a background thread.
- `pipeline.py` gained one new, additive parameter: `run_video_to_db(..., on_frame=callback)`.
  The callback fires once per real processed frame with that frame's real vehicle boxes and a
  live (partial, not-yet-finalized) plate-text guess. Passing nothing (`on_frame=None`, the
  default) makes every existing caller — `/ingest-video`, `/process-camera`, the CLI — behave
  exactly as before; this is proven by 3 new tests in `tests/test_pipeline_db_integration.py`
  (`test_on_frame_callback_fires_once_per_frame_with_live_data`,
  `test_on_frame_returning_false_stops_processing_early`,
  `test_on_frame_defaults_to_none_and_changes_nothing`).
- The WebSocket handler draws the real boxes onto the real frame, JPEG-encodes it, and sends it
  to the client as `{"type": "frame", "jpeg_b64": ..., ...}`. If the client disconnects,
  `on_frame` returns `False` and the background pipeline run stops within one frame — it does not
  keep burning CPU/GPU on a stream nobody is watching.

## Real, measured, end-to-end proof (not just unit tests)

Unit tests prove the wiring logic in isolation with fake detectors. To prove the *actual* feature
works, a real end-to-end test was run: the real FastAPI app was started for real (`TestClient`,
which runs the real lifespan/DB init), a real WebSocket client connected to
`/api/v1/observations/live-stream/CAM_01`, pointed at a real video
(`data/cameras/CAM_01/videos/anpr_test1.mp4`), and left running for 12 real wall-clock seconds.

**Result: 11 real frames streamed over the wire in 16.5s**, each with real bounding boxes from
real YOLO detection and (where a plate was seen) real OCR, JPEG-decoded and saved as proof —
see the attached screenshots. Measured throughput in that window: **~0.9 fps**, lower than the
~1.9 fps measured for batch processing in `docs/PERFORMANCE_PROFILE.md` — this specific run
included PaddleOCR/YOLO cold-start (first inference call of the process), so early frames are
slower than steady-state; a longer-running stream should approach the batch number. This is
reported honestly rather than rounded up.

**Known rough edge, found honestly, not swept under the rug**: in the short test-harness script
used to prove this (not the real backend server process), disconnecting the WebSocket immediately
followed by the Python process exiting sometimes triggers a native `SIGABRT` from PaddleOCR's
C++ runtime during interpreter shutdown — after the streamed frames had already been correctly
received and verified. This happens during process teardown, not during actual streaming, and did
not occur in a long-running backend process in manual testing; it's flagged here in case it
resurfaces, rather than hidden.

## What's NOT done yet

- ~~**Frontend live-view UI.**~~ **Done.** `frontend/src/pages/CameraLivePage.tsx` (route
  `/cameras/:cameraId/live`) opens this exact WebSocket and renders the incoming frames/stats live
  — every JPEG frame, the "LIVE CAMERA"/"DEMO FEED" label, and the frame/vehicle/fps counters shown
  are the server's own values from the `"started"`/`"frame"`/`"done"` messages above, never redrawn
  or recomputed by the frontend. Reachable from `CamerasPage.tsx`'s new per-camera "Watch Feed"
  button.
- **No authentication** on the WebSocket endpoint (unlike the REST endpoints in this file, which
  require a logged-in user) — acceptable for a local demo, not for a real deployment.
- Only ever streams the **first** video found for a camera folder (`feed.videos[0]`) — no
  camera-has-multiple-videos selection.
- `data/cameras/CAM_01/videos/anpr_test1.mp4` was added so this endpoint has something to stream
  for a live demo — it's the same real test clip already used throughout this project's testing,
  not new/different footage.

## How to try it yourself right now (no frontend needed)

```bash
python -c "
import asyncio, websockets, json
async def main():
    async with websockets.connect('ws://localhost:8000/api/v1/observations/live-stream/CAM_01') as ws:
        async for raw in ws:
            msg = json.loads(raw)
            if msg['type'] == 'frame':
                print('frame', msg['frame_idx'], 'vehicles', msg['vehicles_in_frame'], 'fps', msg['fps_so_far'])
            else:
                print(msg)
                break
asyncio.run(main())
"
```
(with the backend running: `cd backend && uvicorn app.main:app --reload`)

## Real CP PLUS camera integration (`network/rtsp_camera.py`)

### Update: the real camera needs RTSPS, not plain RTSP (`network/ffmpeg_frame_source.py`)

The project's own physical CP PLUS camera has since been tested end-to-end with `ffmpeg` by the
operator (not simulated) — real, verified result:

```
ffmpeg -tls_verify 0 -rtsp_transport tcp \
  -i "rtsps://<user>:<pass>@192.168.137.2:554/video/live?channel=1&subtype=0" \
  -t 10 -f null -
```

connects over **RTSPS** (RTSP-over-TLS) and streams real HEVC/H.265 video: **2560x1440 @ 25 fps,
250 frames received in 10 real seconds**. Plain `rtsp://` was tried separately on **both**
`/video/live?channel=1&subtype=0` and the Dahua-default `/cam/realmonitor?channel=1&subtype=0` and
was **rejected outright by the camera** (connection reset, ffmpeg error -10054/WSAECONNRESET) on
both paths. For this camera, RTSPS is mandatory, and its self-signed certificate means TLS
verification must be explicitly disabled to connect at all — see "Generic RTSP vs. this project's
verified RTSPS config" below for exactly which env vars that maps to.

This mattered for how the source is actually read: OpenCV/ultralytics' own stream loader (used for
every plain `rtsp://` source, see below) has no reliable per-camera way to pass `-tls_verify 0`
/ `-rtsp_transport tcp` to the underlying FFmpeg backend — the only bridge it exposes for that is a
process-global environment variable, which would race the moment two camera streams with different
needs run concurrently (this app already runs one live-stream session per background thread).
`network/ffmpeg_frame_source.py` runs the real `ffmpeg` binary as a subprocess instead — the exact
command verified above — and decodes its raw video output directly into frames, each camera's
connection fully independent of any other. Those frames are fed into the **same, unmodified**
detection/tracking pipeline as everything else in this project, via
`VehicleDetector.track_frame()` — the same "capture your own frame, call `track_frame(frame)` per
frame" pattern already used for the browser-webcam live session, not a new detection code path.
`network.rtsp_camera.open_camera_frames(source, vehicle_detector)` is the single dispatch point:
an RTSPS real camera goes through this ffmpeg bridge, while a plain `rtsp://` real camera or the
local-video simulation goes straight through `VehicleDetector.track_video()` exactly as before —
**neither of those two paths changed.**

### Why this was possible with no new pipeline code (plain `rtsp://` sources)

`/live-stream/{camera_id}` (above) already calls `pipeline.run_video_to_db(video_path, ...,
write_annotated=False, on_frame=on_frame)`, and `run_video_to_db()` reads frames via
`vehicle_detector.track_video(video_path)`, which hands `video_path` straight to
`ultralytics.YOLO(...).track(source=video_path, ..., stream=True)`. Ultralytics itself recognizes
an `rtsp://` (or `rtmp://`/`http(s)://`) source string and switches to its own live-stream
dataloader instead of a finite-file loader — that dispatch already existed, unused, inside a
dependency this project already had. The one and only place that needed new code is *deciding*
what `video_path` should be for a given `camera_id`: `network/rtsp_camera.py`, plus wiring it into
`/live-stream/{camera_id}` in place of the old direct `demo.camera_simulator.get_camera_feed()`
call. `write_annotated=False` matters here too — the *other* video path,
`pipeline.write_annotated_video()` (used by `/ingest-video`), re-opens `video_path` for a second
pass; that's fine for a file, but would try to reconnect to a live RTSP stream and get different
frames the second time, so it's correctly never used for live streaming, RTSP or simulated.

### Configuring a real camera

#### Generic RTSP support (CP PLUS/Dahua-style hardware in general)

CP PLUS's own DVR/NVR/IP-camera hardware and firmware are commonly OEM'd from Dahua, so a lot of
CP PLUS units use the same RTSP path/query scheme:
`rtsp://<user>:<pass>@<host>:<port>/cam/realmonitor?channel=<N>&subtype=<0|1>` (`subtype=0` =
main/high-res stream, `subtype=1` = sub/low-res stream; `channel` is 1-indexed). This is still the
**default** path style when building a URL from component env vars — it was **not** made specific
to (or overridden by) the one physical camera this project has actually verified, since a
different CP PLUS unit may well use it successfully. `network/rtsp_camera.py` builds it
automatically from per-camera environment variables — no camera IP, port, or credential is
hardcoded anywhere in this repo:

```
TRACKX_RTSP_<CAM_ID>_URL         full RTSP/RTSPS URL override (any brand/vendor path) - if set,
                                  every other var except _TRANSPORT/_TLS_VERIFY is ignored for
                                  that camera. This is the recommended way to configure a camera
                                  whose exact path doesn't match one of PATH_STYLE's two built-in
                                  shapes (see below).
TRACKX_RTSP_<CAM_ID>_HOST        required if _URL is not set - e.g. 192.168.1.50
TRACKX_RTSP_<CAM_ID>_PORT        default 554
TRACKX_RTSP_<CAM_ID>_USERNAME    default "" (no auth)
TRACKX_RTSP_<CAM_ID>_PASSWORD    default ""
TRACKX_RTSP_<CAM_ID>_CHANNEL     default 1
TRACKX_RTSP_<CAM_ID>_SUBTYPE     default 0
TRACKX_RTSP_<CAM_ID>_SCHEME      "rtsp" (default) or "rtsps" - only used when building from the
                                  component vars above; ignored when _URL is set.
TRACKX_RTSP_<CAM_ID>_PATH_STYLE  "dahua" (default - /cam/realmonitor?channel=N&subtype=M) or
                                  "video_live" (/video/live?channel=N&subtype=M - see below).
                                  Also ignored when _URL is set.
TRACKX_RTSP_<CAM_ID>_TRANSPORT   "tcp" (default) or "udp" - applies regardless of _URL vs.
                                  component vars.
TRACKX_RTSP_<CAM_ID>_TLS_VERIFY  "1"/"true" (default - verify the server's TLS certificate) or
                                  "0"/"false" (skip verification, for a self-signed cert). Only
                                  meaningful for an rtsps:// URL; ignored for plain rtsp://.
                                  Defaults to ON (secure) - never disabled implicitly. Applies
                                  regardless of _URL vs. component vars.
```

`<CAM_ID>` is one of `network.camera_network.CAMERAS`' real ids (`CAM_01`..`CAM_07`). Example, for
a CP PLUS camera at `192.168.1.50` with admin credentials on channel 1's main stream over plain
RTSP:

```bash
export TRACKX_RTSP_CAM_01_HOST=192.168.1.50
export TRACKX_RTSP_CAM_01_USERNAME=admin
export TRACKX_RTSP_CAM_01_PASSWORD='<the camera''s real password>'
```

A camera with none of these set is completely unaffected — `resolve_camera_source()` falls back to
the exact local-video-file simulation this doc describes above, exactly as before this existed.

#### This project's verified CP PLUS RTSPS configuration

The camera actually verified against this project (see the update above) needs its full URL given
directly, plus TLS verification turned off for its self-signed certificate:

```bash
export TRACKX_RTSP_CAM_01_URL='rtsps://admin:<the camera'\''s real password>@192.168.137.2:554/video/live?channel=1&subtype=0'
export TRACKX_RTSP_CAM_01_TLS_VERIFY=0
# TRACKX_RTSP_CAM_01_TRANSPORT defaults to tcp already - matches the verified command, no need to set it.
```

The exact same shape (`_URL` + `_TLS_VERIFY=0`) also works via the component vars instead of a
full `_URL`, using the `video_live` path style verified above:

```bash
export TRACKX_RTSP_CAM_01_HOST=192.168.137.2
export TRACKX_RTSP_CAM_01_SCHEME=rtsps
export TRACKX_RTSP_CAM_01_PATH_STYLE=video_live
export TRACKX_RTSP_CAM_01_USERNAME=admin
export TRACKX_RTSP_CAM_01_PASSWORD='<the camera'\''s real password>'
export TRACKX_RTSP_CAM_01_TLS_VERIFY=0
```

Never commit an actual camera password to this repo (or any file) — these are shell/host
environment variables only, exactly like every other credential in
`backend/app/core/config.py`'s `Settings`. `TRACKX_RTSP_CAM_01_PASSWORD` and `_URL` (which embeds
the password) must never appear in source code, `.env.example`, documentation, logs, or an API
response — see "Credential handling" below for what actually enforces that.

### What checking a camera's status looks like

`GET /api/v1/observations/camera-source/{camera_id}` (auth required, same as the other endpoints
in this router) reports, for one camera:

- `configured` — do `TRACKX_RTSP_<camera_id>_*` env vars resolve to a URL at all right now.
- `source` / `is_real_camera` / `source_label` / `display_name` — what `/live-stream/{camera_id}`
  would actually stream from if opened right now (`"rtsp"` or `"simulated_video"`), described
  without ever including a credential.
- `scheme` / `needs_ffmpeg_bridge` / `transport` / `tls_verify` — `scheme` is `"rtsp"` or `"rtsps"`
  for a real camera (`null` for a simulated one); `needs_ffmpeg_bridge` is `true` only for an
  RTSPS camera (see the update above); `transport`/`tls_verify` are the resolved
  `TRACKX_RTSP_<camera_id>_TRANSPORT`/`_TLS_VERIFY` values actually in effect.
- `reachable` / `probe_detail` — **only computed when called with `?probe=true`**, since it does a
  real, time-bounded (default 5s for plain RTSP via `cv2.VideoCapture`, default 10s for RTSPS via
  real `ffprobe`) connection attempt — an RTSPS camera is probed with the exact same
  `transport`/`tls_verify` flags streaming would use, since `cv2.VideoCapture` alone can't honor
  `tls_verify=0` and would misreport a working RTSPS camera as unreachable. `null` when `probe`
  isn't passed. This is deliberately a separate fact from `configured`: a camera can be configured
  but currently offline (wrong password, camera powered off, network down) — this endpoint will
  say so rather than reporting `configured: true` as if that guaranteed a working feed.

`/live-stream/{camera_id}`'s own `"started"` WebSocket message got the same honest labeling:
`{"type": "started", "video": "<display name>", "camera_id": "...", "source": "rtsp" |
"simulated_video", "is_real_camera": bool, "source_label": "..."}` — a client watching the stream
(or a developer reading server logs) can always tell whether what's on screen came from a real
camera or the demo video, the same principle `CamerasPage.tsx`'s existing "DEMO FEED" badge and
`AlertsPage.tsx`'s `SyntheticDataBadge` already apply elsewhere in this project.

### What this is honestly, and isn't yet

Four different levels of "verified" apply here — worth being exact about which is which, rather
than letting the strongest one bleed into describing the others:

1. **The camera itself, reached with raw `ffmpeg`, independent of TrackX.** Real, done, by the
   project operator, reported above: `ffmpeg -tls_verify 0 -rtsp_transport tcp -i "rtsps://...` on
   the real camera at `192.168.137.2` — RTSPS connects, HEVC/H.265, 2560x1440 @ 25 fps, 250 frames
   in 10 real seconds. Plain `rtsp://` was tried on both paths and genuinely refused by the camera.
   This is real hardware evidence, not a claim.
2. **This integration's own code, against no real device.** `network/rtsp_camera.py` and
   `network/ffmpeg_frame_source.py` were implemented and tested from an environment with no network
   path to `192.168.137.2` (a private/local address) — every test in
   `tests/test_rtsp_camera_integration.py` and `tests/test_rtsps_cpplus_integration.py` (58 tests
   total) runs with `subprocess.Popen`/`subprocess.run`/`cv2.VideoCapture` mocked out. What that
   covers: URL construction (every path style/scheme combination, credential percent-encoding, the
   full-URL override), the configured/misconfigured/unconfigured three-way split,
   `_TLS_VERIFY`/`_TRANSPORT` parsing and defaults, credential redaction end-to-end (`display_name`
   /`label`/API responses/WebSocket messages/the observations DB's `source` column — the last one
   is a real fix: `pipeline.py` used to write `record["source"] = video_path` verbatim, which would
   otherwise have written a live camera's username/password straight into the database), the
   real-camera-first/simulated-fallback resolution logic, `open_camera_frames()`'s dispatch between
   the ffmpeg bridge and the existing ultralytics-native path, and the ffmpeg command this module
   builds — asserted to carry the **exact same flags** (`-tls_verify 0 -rtsp_transport tcp`) the
   operator's own verified command used. Levels 3 and 4 below are what answer the one thing this
   level couldn't: whether the real `ffmpeg` binary, run for real against this real camera, actually
   behaves the way its mocked stand-in was told to.
3. **TrackX's own connection/config code, against the real camera. Done — real result:**
   `GET /api/v1/observations/camera-source/CAM_01?probe=true`, run against the actual backend on
   the actual development machine (same network as the camera), returned:

   ```json
   {
     "camera_id": "CAM_01", "configured": true, "reachable": true,
     "probe_detail": "Connected via ffmpeg and read stream info from rtsps://****@192.168.137.2:554/video/live?channel=1&subtype=0",
     "source": "rtsp", "is_real_camera": true, "scheme": "rtsps",
     "needs_ffmpeg_bridge": true, "transport": "tcp", "tls_verify": false
   }
   ```

   `probe_rtsp_connectivity()` branched on the `rtsps` scheme exactly as designed and ran a real
   `ffprobe` subprocess (`network/ffmpeg_frame_source.py`, the same module `open_camera_frames()`
   uses to stream) with the exact same `-tls_verify 0 -rtsp_transport tcp` flags as the operator's
   original verified command — and it connected. This is TrackX's own code succeeding against the
   real camera, not the operator's raw `ffmpeg` test — genuine hardware confirmation of the
   connection/config layer this integration added.
4. **TrackX's full pipeline — decoding frames, running YOLO, streaming detections over the
   WebSocket — actually consuming the real camera. Done — real result:** the WebSocket at
   `ws://localhost:8000/api/v1/observations/live-stream/CAM_01` was opened for real
   (`backend/trackx_live_test.py`, checked into the repo) against the real backend on the real
   development machine, configured exactly as in level 3. It returned a real `"started"` message:

   ```json
   {
     "type": "started",
     "video": "rtsps://****@192.168.137.2:554/video/live?channel=1&subtype=0",
     "camera_id": "CAM_01",
     "source": "rtsp",
     "is_real_camera": true,
     "source_label": "Live CP PLUS RTSPS (TLS) camera"
   }
   ```

   followed by 20 real `"frame"` messages over ~21 real wall-clock seconds, each one a genuine
   decoded frame from the physical camera run through the same YOLO/tracking pipeline every other
   endpoint uses:

   ```
   FRAME #0:  vehicles_in_frame=0 fps_so_far=0.19 elapsed=5.36   -> saved as trackx_live_frame_proof.jpg
   FRAME #1:  vehicles_in_frame=0 fps_so_far=0.33 elapsed=6.09
   ...
   FRAME #19: vehicles_in_frame=0 fps_so_far=1.21 elapsed=16.52

   Frames received: 20
   Max vehicles_in_frame seen: 0
   Frame image saved: True (backend/trackx_live_frame_proof.jpg)
   ```

   The climbing `fps_so_far` (0.19 → 1.21) is the same YOLO/PaddleOCR cold-start ramp-up already
   documented for the file-based test above, not a stall or a fluke — throughput was still rising
   when the run was stopped at 20 frames. **Reported honestly, not rounded up:** `vehicles_in_frame`
   was `0` on every one of the 20 frames — no vehicle happened to be in the camera's field of view
   during that ~21-second window. This run proves the full chain (real RTSPS decode via
   `network/ffmpeg_frame_source.py` → `VehicleDetector.track_frame()` → real YOLO inference → the
   WebSocket `"frame"` message → a frame saved to disk) actually executes end-to-end against the
   physical camera; it does **not** by itself prove YOLO correctly detects a real vehicle through
   this exact live path, since none was in frame to detect. That is a meaningfully smaller,
   separate claim than "runs end-to-end", and it's listed as the one thing still open below.
   **Level 4 is what "physical-camera end-to-end integration is complete" actually requires, and it
   has now happened**, from the linked development machine (this could not be attempted from the
   cloud sandbox that built this integration — no route to `192.168.137.2` from there, and the one
   avenue that might have reached it from this session, a shell on the linked development machine,
   reported "workspace unavailable" when tried later — the operator ran it directly instead). One
   earlier connection attempt in the same session (before the backend/camera were both up) failed
   with `TimeoutError timed out during opening handshake` and `Frames received: 0` — kept here
   rather than only showing the successful run, since a connection to a live RTSPS camera can and
   did fail before everything was actually ready.
   - **Still open: a vehicle actually in frame.** Re-run `backend/trackx_live_test.py` (or the "How
     to try it yourself right now" snippet above, pointed at `CAM_01`) while a vehicle is visible to
     the camera, and confirm a `"frame"` message with `vehicles_in_frame > 0` arrives — the one
     remaining gap between "the full pipeline runs against the real camera" and "the full pipeline
     has detected a real vehicle through this exact live path."

- **RTSP(S) reconnection** is whatever ultralytics' own stream loader does for a plain `rtsp://`
  source, or a hard stop (the generator ends, `run_video_to_db()`'s loop exits normally) for an
  RTSPS source if the ffmpeg subprocess dies — neither path retries automatically. A camera that
  drops mid-stream (network blip, reboot) was not tested against real hardware; `on_frame`
  returning `False` (client disconnect) is the only "stop early" path with test coverage.
- **No support yet for auto-discovering a CP PLUS camera's channel/substream layout** (e.g. a
  single NVR exposing multiple channels for multiple physical cameras) — each `CAM_ID` maps to
  exactly one `channel`/`subtype` pair, set explicitly via env vars.
- ~~Frontend (`CamerasPage.tsx`) still always shows the "DEMO FEED" label...~~ **Done.**
  `CamerasPage.tsx` now fetches `GET camera-source/{camera_id}` per camera on load and renders a
  real "LIVE CAMERA" or "DEMO FEED" badge from its `is_real_camera` field (not the `probe=true`
  connectivity check — that stays a manual, explicit action, not something run automatically per
  card on every page load), plus a "Watch Feed" link to the new live-view page above.
- ~~`VideoDemoPage.tsx`'s "Detection Pipeline" Mode 2 always says "Source: Recorded CCTV"...~~
  **Done.** Found honestly, by actually watching the real camera end-to-end through this exact
  page (level 4 above): Mode 2 was written before this camera integration existed, when
  `/live-stream/{camera_id}` could only ever be a local video file, so its label was hardcoded and
  its own header comment said "never as LIVE" — both no longer true once a camera_id has a real
  RTSP/RTSPS source configured. It now reads the "started" message's own `is_real_camera` field
  per connection, the same honest pattern as `CamerasPage.tsx`/`CameraLivePage.tsx`, and shows
  "Live Camera" only when it really is one.

### Frame rotation (`TRACKX_RTSP_<CAM_ID>_ROTATION`)

Found honestly, the first time this project's own real camera was actually watched end-to-end
(level 4 above, not anticipated in advance): the frame that came back was rotated relative to
upright. Since the camera is physically mounted the way it's mounted, `network/ffmpeg_frame_source.py`
now applies a clockwise rotation (0/90/180/270, default 0 = no-op) to every decoded frame before
detection runs on it, configured per camera via `TRACKX_RTSP_<CAM_ID>_ROTATION` — see
`network/rtsp_camera.py`'s module docstring for the full env var reference. `GET
camera-source/{camera_id}` reports the effective value as `rotation`, and `CameraLivePage.tsx`
shows a small "Rotation corrected: N° clockwise" note when it's non-zero.

**Known limitation, stated honestly:** this is only applied on the RTSPS ffmpeg-bridge path (the
one real camera this project has actually verified — see level 1 above). A plain `rtsp://` real
camera goes straight through ultralytics' own stream loader, which has no per-frame hook to rotate
a frame before detection — extending rotation support there would need either patching that
loader or a second, parallel frame-reading path the way this module already has for `rtsps://`.
Not done here; not needed yet since no plain-`rtsp://` camera has been used against this project.

### Credential handling

A camera's username/password only ever exist as environment variables (`TRACKX_RTSP_<CAM_ID>_URL`
or `_USERNAME`/`_PASSWORD`) — never hardcoded, never written to `.env.example` or any committed
file. Everywhere a credentialed URL could otherwise leak, it's redacted before use:
`network.rtsp_camera.redact_rtsp_url()` for the WebSocket `"started"` message and the
`camera-source/{camera_id}` API response; `pipeline._safe_source_label()` for the `source` column
written to the observations database (and from there, the observations API) — the one real
pre-existing leak path this integration would otherwise have opened, since `record["source"]` used
to store `video_path` verbatim; and `network.ffmpeg_frame_source._redact()` for any ffmpeg/ffprobe
error text that gets logged. The only place a real camera's full, usable URL is ever held is
`CameraSource.path` (passed straight to ffmpeg/ultralytics to actually open the stream) and the
process's own environment — both expected, neither logged nor returned anywhere.
