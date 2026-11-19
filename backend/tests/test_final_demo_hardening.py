"""
backend/tests/test_final_demo_hardening.py

SIH26127 "Final Demo Hardening" audit (2026-09-10) - regression tests for
the real bugs found and fixed while investigating the user's live report:
"Live Detections: 0 now visible" with a vehicle clearly in frame, "OCR
unavailable in this deployment", and Admin Console -> System showing
"Detection / OCR Engine - healthy - unavailable".

1. GET /health's model status used to be fabricated: yolo_vehicle/
   yolo_plate were hardcoded `True` ("Usually available", never actually
   checked) and `paddleocr` only checked whether the PACKAGE was
   importable, not whether OCR actually initialized. Since the overall
   status was `"healthy" if any(models.values())`, this made the AI
   engine report "healthy" NO MATTER WHAT - even with OCR genuinely
   unavailable - producing the self-contradictory "healthy - unavailable"
   text an operator could see in Admin Console -> System.
2. A construction failure in `_get_plate_detector()` used to propagate
   uncaught out of the webcam-stream WebSocket handler (no try/except
   around that one call site, unlike vehicle_detector's), silently killing
   the session with no message ever reaching the browser.
3. The webcam-stream WebSocket's single-session lock could be held forever
   by an abandoned connection (browser killed/reloaded without a clean
   close frame) - `await websocket.receive_json()` has no timeout by
   default, so the "finally" block that releases the lock never runs,
   permanently blocking every later real connection attempt with "A live
   webcam session is already running" until the backend process itself is
   restarted. This is the confirmed root cause of "webcam works once, then
   won't reconnect".

Uses the app's real TestClient WebSocket support and real YOLO/PaddleOCR
inference where relevant - no mocked detection results.
"""
import base64

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _reset_session_lock():
    import app.api.v1.observations as obs_module
    with obs_module._webcam_session_lock:
        obs_module._webcam_session_active = False


def _blank_frame_b64():
    frame = (128 * np.ones((120, 160, 3))).astype("uint8")
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return base64.b64encode(buf.tobytes()).decode("ascii")


class TestHealthModelStatusIsReal:
    """The core regression test for the confirmed 'healthy - unavailable'
    bug: overall model status must never say 'healthy' while a component
    that get_model_status() itself reports unavailable exists, and the
    real reason must be surfaced, not silently dropped."""

    def test_get_model_status_reflects_actual_singletons(self):
        from app.api.v1.observations import get_model_status, _get_vehicle_detector, _get_plate_detector, _get_ocr

        status = get_model_status()
        # Every field is a real attempted-construction result of the SAME
        # singletons the live pipeline uses - not a separate opinion.
        assert status["vehicle_detector"]["available"] == (_get_vehicle_detector() is not None)
        assert status["plate_detector"]["available"] == (_get_plate_detector() is not None)
        assert status["ocr"]["available"] == (_get_ocr() is not None)
        for component in ("vehicle_detector", "plate_detector", "ocr"):
            if not status[component]["available"]:
                assert status[component]["reason"], (
                    f"{component} is reported unavailable but has no real reason attached - "
                    f"this is exactly the silently-swallowed-failure bug this audit fixed."
                )

    def test_check_models_status_can_never_be_healthy_with_a_real_unavailable_component(self, monkeypatch):
        """Directly reproduces the confirmed bug: force one real component
        unavailable (simulating the user's actual environment) and assert
        the overall status honestly reflects that - never 'healthy'."""
        from app.api.v1 import health as health_module
        from app.api.v1 import observations as obs_module

        def fake_status(trigger_load=True):
            return {
                "vehicle_detector": {"available": True, "reason": None},
                "plate_detector": {"available": True, "reason": None},
                "ocr": {"available": False, "reason": "PaddleOCR's own constructor called sys.exit(...) - simulated for this test"},
            }

        monkeypatch.setattr(obs_module, "get_model_status", fake_status)
        result = health_module.check_models()

        assert result["status"] != "healthy", (
            "check_models() reported 'healthy' while OCR was reported unavailable - "
            "this is exactly the fabricated-status bug ('healthy - unavailable' in the UI) this test guards against."
        )
        assert result["models"]["paddleocr"] is False
        assert "paddleocr" in result["reasons"]
        assert "sys.exit" in result["reasons"]["paddleocr"]

    def test_check_models_status_healthy_only_when_everything_real_is_available(self, monkeypatch):
        from app.api.v1 import health as health_module
        from app.api.v1 import observations as obs_module

        monkeypatch.setattr(obs_module, "get_model_status", lambda trigger_load=True: {
            "vehicle_detector": {"available": True, "reason": None},
            "plate_detector": {"available": True, "reason": None},
            "ocr": {"available": True, "reason": None},
        })
        result = health_module.check_models()
        assert result["status"] == "healthy"
        assert result["reasons"] == {}

    def test_root_health_endpoint_ai_engine_and_ocr_engine_never_disagree(self, client, monkeypatch):
        """Reproduces the exact AdminPage.tsx display bug: ai_engine and
        ocr_engine used to be computed from different signals and could be
        concatenated into a self-contradictory "healthy - unavailable"."""
        from app.api.v1 import observations as obs_module

        monkeypatch.setattr(obs_module, "get_model_status", lambda trigger_load=True: {
            "vehicle_detector": {"available": True, "reason": None},
            "plate_detector": {"available": False, "reason": "no weights file found (test)"},
            "ocr": {"available": False, "reason": "plate detector unavailable (test)"},
        })
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        if body["ocr_engine"] == "unavailable":
            assert body["ai_engine"] != "healthy", (
                f"ai_engine={body['ai_engine']!r} but ocr_engine={body['ocr_engine']!r} - "
                f"exactly the 'healthy - unavailable' contradiction this audit fixed."
            )
        assert "model_reasons" in body


class TestPlateDetectorFailureDoesNotCrashSession:
    """_get_plate_detector() used to have no try/except at all - a real
    construction exception would propagate uncaught out of every call
    site, including the webcam-stream WebSocket, killing the session with
    no message ever reaching the browser."""

    def setup_method(self):
        _reset_session_lock()

    def teardown_method(self):
        _reset_session_lock()

    def test_plate_detector_construction_exception_is_caught_and_remembered(self, monkeypatch):
        import app.api.v1.observations as obs_module

        # monkeypatch.setattr (not plain assignment) so these module-level
        # singleton-bookkeeping globals are automatically restored after
        # this test, regardless of pass/fail - a plain assignment here
        # previously leaked a permanently-broken plate detector into every
        # OTHER test that runs later in the same pytest session (including
        # the real-inference ingest-video test), a real regression caught
        # while writing this very test.
        monkeypatch.setattr(obs_module, "_plate_detector", None)
        monkeypatch.setattr(obs_module, "_plate_detector_init_attempted", False)
        monkeypatch.setattr(obs_module, "_plate_detector_init_error", None)

        # Patch what the real function calls internally by patching find_plate_weights
        # to return a path, and PlateDetector to explode - exercises the real code path.
        import demo.visual_pipeline as vp_module
        monkeypatch.setattr(vp_module, "find_plate_weights", lambda: "/nonexistent/weights.pt")

        import detection.detect_plates as dp_module

        class ExplodingPlateDetector:
            def __init__(self, weights):
                raise RuntimeError("simulated corrupt weights file")

        monkeypatch.setattr(dp_module, "PlateDetector", ExplodingPlateDetector)

        result = obs_module._get_plate_detector()
        assert result is None
        assert obs_module._plate_detector_init_error is not None
        assert "simulated corrupt weights file" in obs_module._plate_detector_init_error

        # Second call must not re-attempt (and re-crash) - it should just
        # return the remembered None, matching _get_ocr()'s "attempt once"
        # performance contract.
        result2 = obs_module._get_plate_detector()
        assert result2 is None

    def test_webcam_stream_session_survives_plate_detector_failure(self, client, monkeypatch):
        """End-to-end: even if plate detection is completely broken, a
        live webcam session must still start, report the real reason, and
        keep producing real vehicle detections (vehicle detection has no
        dependency on the plate detector)."""
        import app.api.v1.observations as obs_module

        monkeypatch.setattr(obs_module, "_get_plate_detector", lambda: None)
        monkeypatch.setattr(obs_module, "_plate_detector_init_error", "simulated: no plate weights available")

        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            ready = ws.receive_json()
            assert ready["type"] == "ready"
            assert ready["plate_detector_available"] is False
            assert ready["plate_detector_reason"] == "simulated: no plate weights available"
            assert ready["ocr_available"] is False

            ws.send_json({"type": "frame", "jpeg_b64": _blank_frame_b64()})
            result = ws.receive_json()
            assert result["type"] == "result", "vehicle detection must still work with no plate detector"


class TestWebcamSessionIdleTimeoutReleasesLock:
    """Confirmed root cause of 'webcam opens once, then won't open again':
    an abandoned WebSocket (no clean close frame) held the single-session
    lock forever because receive_json() has no timeout. Verifies the fix:
    a session idle past _WEBCAM_IDLE_TIMEOUT_SECONDS is treated as
    abandoned and the lock is released for the next real session."""

    def setup_method(self):
        _reset_session_lock()

    def teardown_method(self):
        _reset_session_lock()

    def test_idle_session_times_out_and_frees_the_lock(self, client, monkeypatch):
        import app.api.v1.observations as obs_module
        # Real timeout, but short - this test genuinely waits it out rather
        # than mocking asyncio.wait_for, so it exercises the real code path.
        monkeypatch.setattr(obs_module, "_WEBCAM_IDLE_TIMEOUT_SECONDS", 1)

        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_IDLE_TEST") as ws1:
            ready = ws1.receive_json()
            assert ready["type"] == "ready"
            # Deliberately send nothing and just wait past the timeout -
            # simulates a browser tab that vanished without a close frame.
            timeout_msg = ws1.receive_json()
            assert timeout_msg["type"] == "error"
            assert "idle" in timeout_msg["detail"].lower()

        # The lock must now be free for a brand new session - this is the
        # actual symptom the user reported ("second time not opening").
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_IDLE_TEST") as ws2:
            ready2 = ws2.receive_json()
            assert ready2["type"] == "ready", (
                "a new session was rejected as 'already running' after the previous "
                "one went idle - the stale-lock bug this audit fixed."
            )
