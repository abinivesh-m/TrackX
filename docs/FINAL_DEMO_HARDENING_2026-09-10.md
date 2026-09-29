# TrackX — Final Department Demo Hardening
**SIH26127 — Bharat Electronics Limited | 2026-09-10**

Investigation into your live report: Live Webcam Demo showed "0 now visible" with a real vehicle in frame, a badge saying "OCR unavailable in this deployment", and Admin Console → System showing the self-contradictory "Detection / OCR Engine — healthy - unavailable". You also reported the webcam connecting once, then failing to reconnect.

I could not run code directly on your Windows machine this session (the remote-device shell reported "the isolated Linux environment on this device failed to start" every time I tried it — not something I could work around from here). Everything below is either (a) a bug I found by reading the actual code and can show you exactly where it is, or (b) something I reproduced and fixed with real, verified tests — in this cloud sandbox, using your real code, real YOLO/PaddleOCR models, and a real browser. Nothing here is guessed or assumed.

---

## 1. Root cause of "healthy - unavailable" — CONFIRMED, FIXED

This one I found with certainty and it's a real bug, not an environment quirk.

`backend/app/api/v1/health.py`'s `check_models()` used to be:

```python
models = {
    "lprnet": False,
    "paddleocr": PADDLEOCR_AVAILABLE,   # only checks the PACKAGE imports, not that OCR actually works
    "yolo_vehicle": True,   # "Usually available" — never actually checked
    "yolo_plate": True,     # "Usually available" — never actually checked
}
return {"status": "healthy" if any(models.values()) else "unavailable", "models": models}
```

`yolo_vehicle`/`yolo_plate` were hardcoded `True` — literally never checked, despite the function's own docstring claiming "every field here is a REAL check". Because the overall status was `"healthy" if any(...)`, those two hardcoded flags alone made this **always** report "healthy", no matter what.

Separately, `backend/app/main.py`'s `/health` endpoint builds two display strings from that same (broken) status:
```python
"ai_engine": model_status["status"],                                    # always "healthy"
"ocr_engine": " + ".join(ocr_engines) if ocr_engines else "unavailable", # correctly "unavailable" when OCR is genuinely down
```
and `AdminPage.tsx` renders them concatenated: `` `${health.ai_engine} - ${health.ocr_engine}` ``. That's the exact mechanism that produced **"healthy - unavailable"** on your screen — two different signals, one fabricated, glued into one string.

**Fix:** `check_models()` now calls a new `get_model_status()` in `observations.py` that does a **real attempted construction of the exact singleton objects the live pipeline uses** (the same `_get_vehicle_detector()`/`_get_plate_detector()`/`_get_ocr()` your webcam and video-upload endpoints call) — never a guess. Overall status is `"healthy"` only if all three are really available, `"degraded"` if some are, `"unavailable"` if none are. The real reason each unavailable component failed is now returned too (`model_reasons`), not silently dropped.

**Verified (real test, this session):**
```
GET /api/v1/health →
{"ai_engine": "healthy", "ocr_engine": "PaddleOCR",
 "models": {"lprnet": false, "paddleocr": true, "yolo_vehicle": true, "yolo_plate": true},
 "model_reasons": {}}
```
New regression test `test_check_models_status_can_never_be_healthy_with_a_real_unavailable_component` directly forces one component down and asserts the status can never say "healthy" again — this is the test that would have caught the original bug.

**Admin Console → System** now shows three separate real cards (Vehicle Detection, Plate Detection, OCR), each with its own READY/UNAVAILABLE + real reason, instead of one blended line. Screenshot attached (`admin_system_after_fix.png`).

---

## 2. Root cause of "OCR unavailable in this deployment" on your machine — PARTIALLY DIAGNOSED, HONEST LIMIT

The badge itself is **not fabricated** — `recognition/ocr_reader.py`'s `try_init_ocr()` genuinely tries to construct PaddleOCR and reports `None` if it can't, and it always has (this was already correct code, not a bug). What I could not do is see **why** it fails specifically on your Windows machine, because I have no shell access there.

What I *can* tell you with certainty: in this cloud sandbox, with the exact same code, PaddleOCR initializes successfully in ~1.4 seconds (cached models already present) and reads real plate crops. So the code path itself is not broken — the failure is specific to your machine's Python environment (PaddleOCR package not installed there, or it's installed but can't reach its model-weight CDN `bj.bcebos.com` and has no cached copy under `~/.paddleocr`).

**What I fixed regardless:** the app now tells you *why*, not just *that*. `try_init_ocr()` sets a new `LAST_OCR_INIT_ERROR` with the real exception text (package not installed vs. `sys.exit` from a CDN-unreachable model download vs. some other construction error). This reason now flows through to:
- the webcam-stream WebSocket's `ready` message (`ocr_reason`, `plate_detector_reason`)
- `GET /health`'s `model_reasons`
- Admin Console → System (shown under each unavailable card)
- the Live Webcam page's status bar (hover the warning badge for the full text)

**What you should do next:** open the Live Webcam Demo page on your machine and read the exact reason text next to "OCR unavailable" — it will now tell you precisely which of the two cases it is, instead of a dead end. If it says the package isn't installed: `pip install paddleocr` in the same Python environment the backend runs from. If it says a CDN/model-download failure: PaddleOCR needs one successful internet connection to `bj.bcebos.com` to download and cache its models (or you can copy an already-populated `~/.paddleocr` folder from a machine that has one, e.g. this session's — ask me and I can package it for you).

---

## 3. Root cause of "0 now visible" with a real vehicle in frame — investigated, one confirmed contributing bug fixed, core pipeline proven correct

This took the most investigation. Here's everything I actually did and found, in order:

**a) Proved the detection code itself works**, using the *exact* frame content from your own screenshot (the phone showing a car, cropped from the image you sent) run through the real `VehicleDetector.track_frame()`:
```
[{'bbox': [554, 256, 771, 398], 'confidence': 0.814, 'vehicle_type': 'car', 'track_id': 1}]
```

**b) Proved the full backend transport path works**, by writing a real Python WebSocket client that connects to the actual `/api/v1/observations/webcam-stream/CAM_WEBCAM_01` endpoint and sends that same frame exactly the way your browser does (base64 JPEG over the JSON protocol). Result: real detection, real plate bbox (confidence 0.862), real timing.

**c) Proved the full real-browser path works end-to-end**, which is the strongest test I could run without your physical webcam: I launched a real headless Chromium browser, gave it a **fake camera device fed from a real video** of that same phone-showing-a-car image, logged into your actual running app, clicked "Start Webcam", and let the real `getUserMedia()` → canvas → WebSocket → YOLO → plate detector pipeline run for 6 real seconds. Result:
```
CAMERA CONNECTED · Mode: LIVE · 1 now visible · Track #5 · Car · Plate detected, not read
```
This is about as close to your physical test as I can get from a cloud sandbox, and it worked correctly.

**d) Found and fixed a real, general gap while doing (c):** on my first attempt, a video-format quirk in my test tooling (not your app) caused the fake camera to report a degenerate 2×2 pixel frame instead of a real one. The app had **zero validation for this** — it silently captured and sent that useless 2×2 frame forever, showing exactly "CAMERA CONNECTED" + "0 now visible" + no error, with **11 frames successfully sent** and **zero explanation**. This is a real, generalizable blind spot: any cause of a degenerate camera frame (a webcam driver defaulting to a placeholder size, a permission/format glitch, camera in use elsewhere) would produce exactly your symptom with no diagnostic. Fixed: the app now checks captured frame dimensions and shows a clear red warning ("Camera is reporting an abnormally small video size (WxH)px...") instead of silently sending useless data. Screenshot attached (`degenerate_frame_warning.png`) — this is a real screenshot of the fix catching this exact failure mode.

**e) Also fixed (found while auditing the same code):** `frame_error` messages from the backend — sent whenever a single frame fails to decode or fails during processing — used to be **silently swallowed by the frontend** (`if (msg.type === 'frame_error') { ...; return }` with no UI update at all). If any real per-frame exception were happening on your machine, you would have seen exactly what you saw: "CAMERA CONNECTED" forever, "0 vehicles" forever, zero error text. Fixed: frame errors are now counted and the last one's real detail is shown in the status bar.

**Honest bottom line:** I've proven the detection/pipeline code is correct through three independent real tests (direct call, real WebSocket, real browser+fake camera). I could not reproduce your *exact* "0 vehicles" failure with your *exact* hardware, because I don't have access to your machine. But I've closed the two concrete blind spots that would have made **any** underlying cause on your machine invisible to you (degenerate frame size, and silently-swallowed frame errors) — so when you re-run this on your machine, you will now either see it work, or see a specific, actionable reason it isn't, instead of a silent dead end.

---

## 4. Root cause of "webcam opens once, then won't open again" — CONFIRMED, FIXED

Found by reading `webcam_stream()`'s session-lock code: only one live webcam session is allowed at a time (deliberate, documented design — concurrent sessions would corrupt each other's ByteTrack state). The lock is released in a `finally` block when the WebSocket closes.

The bug: `await websocket.receive_json()` has **no timeout**. If a browser tab disappears without sending a clean close frame — a hard refresh, the tab being killed, a laptop sleeping, a network drop — the backend just waits forever for a message that will never come. The `finally` block never runs. The lock stays held **permanently**, until the whole backend process is restarted. Every later real connection attempt then gets "A live webcam session is already running" — even though nothing is actually live. This is the exact symptom you reported.

**Fix:** the receive loop now has a 20-second idle timeout (`asyncio.wait_for`). A real live session always sends a frame roughly every 500ms, so this never affects normal use — only a genuinely abandoned connection ever hits it, and when it does, the lock is released and logged.

**Verified with a real test** (not mocked): a session is opened, deliberately never sends another message, the test genuinely waits past a shortened timeout, and asserts a **second, brand-new session can then connect successfully** — reproducing your exact "second time not opening" scenario and confirming it's fixed.

---

## 5. Files changed

| File | What changed |
|---|---|
| `backend/app/api/v1/observations.py` | New `get_model_status()` (single source of truth for real model status + reasons); `_get_vehicle_detector()`/`_get_plate_detector()` rewritten to attempt-once and remember the real failure reason instead of crashing call sites uncaught; webcam-stream WS: idle-timeout lock release, real per-frame structured logging, `plate_detector_reason`/`ocr_reason` in the ready message, real exception text in frame_error |
| `backend/app/api/v1/health.py` | `check_models()` now uses real per-component checks instead of hardcoded/package-only checks; surfaces real `reasons` |
| `backend/app/main.py` | `/health` endpoint's `ai_engine`/`ocr_engine`/`model_reasons` now come from the same real source, can no longer disagree |
| `recognition/ocr_reader.py` | New `LAST_OCR_INIT_ERROR` module variable capturing the real OCR init failure reason (package missing vs. CDN unreachable vs. other), without changing `try_init_ocr()`'s existing return contract |
| `frontend/src/pages/LiveWebcamPage.tsx` | Shows real plate-detector/OCR unavailability reasons (not just booleans, and no longer conflated); frame_error count + last error now visible; new degenerate-capture-size warning |
| `frontend/src/pages/AdminPage.tsx` | System tab: one fabricated "healthy - unavailable" card replaced with three real per-component cards |
| `backend/tests/test_final_demo_hardening.py` | **NEW** — 7 regression tests for every bug above |
| `RUNNING.md` | Fixed a real doc inaccuracy found while testing: the frontend runs on **port 3000** (set in `vite.config.ts`), not Vite's 5173 default as the doc previously said |

---

## 6. Model loading status (real, this session)

```
GET /api/v1/health (this cloud sandbox, cached models present):
  vehicle_detector: available, reason: null
  plate_detector:   available, reason: null
  ocr:              available, reason: null
```

## 7. Real webcam test result (real browser, fake camera fed a real image)

```
CAMERA CONNECTED · Mode: LIVE
Track #5 · Car
Plate detected, not read
Frames Sent: (several, real round trips) · 1 now visible
```

## 8. Actual detected vehicle

`vehicle_type: car, confidence: 0.814, bbox: [554, 256, 771, 398]` — from your own screenshot's frame content, run through the real, unmodified YOLO detector.

## 9. Actual OCR result

Plate region was detected (`plate_detector_confidence: 0.862`) but not read as text within the single test frame — expected and honest: this build's plate-state machine requires multiple consistent readings before promoting text (see §10); a one-frame smoke test correctly shows `detected_not_read`, not a fabricated plate.

## 10. Temporal state progression

Unchanged, not touched this session — `UNKNOWN → LOW_CONFIDENCE → TENTATIVE → VERIFIED`, driven by `pipeline._plate_status_for_track()`/`_plate_state_for_track()`, reused (not reimplemented) by `live_webcam.py`. No regression — covered by the existing, still-passing `test_webcam_stream.py` suite.

## 11. Trajectory / GIS result

Not touched this session. Confirmed no regression: `tests/test_multicamera_trajectory.py` (10 tests) and `backend/tests/test_multicamera_trajectory_endpoints.py` (6 tests) from the previous hardening pass all still pass.

## 12. Admin changes

- **System tab:** fixed (see §1) — three real per-component cards.
- **Security / Database / Audit Logs tabs:** left as-is, deliberately. These already say plainly "not configurable/available/implemented in this build" — that's honest, not fabricated, so they don't violate the no-fabrication rule you set. Implementing real 2FA/session-timeout/backup/audit-logging is real new feature work, which conflicts with your explicit "do NOT add new large features after this" instruction and the priority order you gave (truthful health ranked above removing unfinished admin UI). I did not hide them from the nav either, since a judge clicking into them sees an honest, calm "not in this build" message rather than a dead 404 or a missing menu item — which I judged the safer choice for a live demo, but happy to hide them from the sidebar entirely if you'd rather.

## 13. Tests

- Baseline (before this session's changes): 340 passed, 9 skipped, 0 failed.
- New: 7 tests added in `backend/tests/test_final_demo_hardening.py` (all real: real health-status forcing, real WebSocket sessions, a real 1-second idle-timeout wait, real plate-detector-crash simulation).
- Final: **347 passed, 9 skipped, 0 failed.** Zero regressions.
- Frontend: `npm run typecheck` clean, `npm run build` succeeds.

## 14. Performance

No measurable change — the only added per-request cost is `GET /health` now forcing model singleton construction on its *first* call after a backend restart (a few seconds, one time only, since these are the same lazy singletons the pipeline already reuses afterward) instead of returning fabricated status instantly. Every other endpoint's performance is unchanged.

## 15. Remaining limitations (honest)

- **I still cannot tell you the exact reason OCR is unavailable on your specific Windows machine** — I don't have shell access there this session. The app will now tell you the real reason itself the next time you load the Live Webcam page or Admin → System.
- **I could not 100% reproduce your exact "0 vehicles" failure** with your exact hardware — only proven the pipeline code is correct via three independent real tests, and closed two real blind spots that would have hidden *any* cause of it from you.
- Admin Security/Database/Audit Logs remain unimplemented (honestly labeled) — see §12.
- The pre-existing 84 `DEMO_SYNTHETIC` seeded rows and map-tile-rendering-needs-network limitation from the previous hardening pass are unchanged.

---

## What to do next on your machine

1. Pull these 8 changed files (already synced to your `TrackX` folder — confirmed 0 rejected).
2. Restart your backend (`uvicorn app.main:app --reload`), open Admin Console → System — read the real reason next to any red card.
3. Open Live Webcam Demo — if OCR/plate detection show unavailable, hover (or just read) the red/amber badge for the exact reason and act on it (install `paddleocr`, or get one successful connection to `bj.bcebos.com`).
4. Try the webcam again — if a session ever gets stuck, it now self-releases after 20 idle seconds instead of needing a backend restart.
5. If "0 vehicles" still happens with a real vehicle clearly in frame, you'll now see either a red "abnormally small video size" warning (camera driver issue — try a different browser/camera) or, if that's not it, frame-error text with the real exception — send that text to me and I can pinpoint the actual cause immediately instead of guessing.
