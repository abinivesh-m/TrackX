"""
backend/tests/test_webcam_stream.py

Real tests for the WS /api/v1/observations/webcam-stream/{camera_id}
endpoint - the SIH26127 "Live Webcam + Phone Number-Plate Demo" backend.

Uses the app's real TestClient WebSocket support (starlette's
websocket_connect), real YOLO detection - no mocked inference. A test
"browser frame" is a real JPEG-encoded image, base64'd exactly the way the
frontend will send it.

No auth header is sent, matching the existing (already-proven)
/live-stream/{camera_id} WebSocket endpoint's own precedent: neither
WebSocket endpoint in this router is behind get_current_user.
"""
import base64
import os

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

BUS_JPG = "/tmp/bus.jpg"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _jpeg_b64(frame) -> str:
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _blank_frame_b64():
    frame = (128 * np.ones((120, 160, 3))).astype("uint8")
    return _jpeg_b64(frame)


def _real_bus_frame_b64():
    if not os.path.isfile(BUS_JPG):
        pytest.skip(f"Real-content test image not present at {BUS_JPG}")
    return _jpeg_b64(cv2.imread(BUS_JPG))


def _reset_session_lock():
    """Every test below opens/closes its own websocket cleanly, which
    already releases the module-level single-session lock via the
    endpoint's own finally-block - this exists only as an extra safety net
    so one test's assertion failure (which can skip the finally-driven
    context-manager exit's normal flow in edge cases) can't leave a stale
    lock that fails every later test with an unrelated "already running"
    error."""
    import app.api.v1.observations as obs_module
    with obs_module._webcam_session_lock:
        obs_module._webcam_session_active = False


class TestWebcamStreamLifecycle:
    def setup_method(self):
        _reset_session_lock()

    def teardown_method(self):
        _reset_session_lock()

    def test_ready_message_on_connect(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "ready"
            assert msg["camera_id"] == "CAM_WEBCAM_TEST"
            assert "plate_detector_available" in msg
            assert "ocr_available" in msg

    def test_real_frame_produces_real_result(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            ws.receive_json()  # ready
            ws.send_json({"type": "frame", "jpeg_b64": _real_bus_frame_b64()})
            result = ws.receive_json()
            assert result["type"] == "result"
            assert result["frame_idx"] == 0
            assert "vehicles" in result
            assert "timing_ms" in result
            assert result["timing_ms"]["total"] >= 0
            # A real bus photo must produce at least one real detection -
            # this is a real-inference assertion, not just "didn't crash".
            assert len(result["vehicles"]) >= 1
            for v in result["vehicles"]:
                assert v["vehicle_type"] in ("car", "motorcycle", "bus", "truck")
                assert v["plate_state"] in ("UNKNOWN", "LOW_CONFIDENCE", "TENTATIVE", "VERIFIED")

    def test_multiple_frames_increment_frame_idx(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            ws.receive_json()
            for expected_idx in range(3):
                ws.send_json({"type": "frame", "jpeg_b64": _blank_frame_b64()})
                result = ws.receive_json()
                assert result["frame_idx"] == expected_idx

    def test_malformed_frame_reports_error_and_stays_connected(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            ws.receive_json()
            ws.send_json({"type": "frame", "jpeg_b64": "not-valid-base64-jpeg-data!!!"})
            err = ws.receive_json()
            assert err["type"] == "frame_error"
            # Session must still be usable after one bad frame.
            ws.send_json({"type": "frame", "jpeg_b64": _blank_frame_b64()})
            result = ws.receive_json()
            assert result["type"] == "result"

    def test_empty_jpeg_b64_reports_error(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            ws.receive_json()
            ws.send_json({"type": "frame", "jpeg_b64": ""})
            err = ws.receive_json()
            assert err["type"] == "frame_error"

    def test_unknown_message_type_reports_frame_error(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            ws.receive_json()
            ws.send_json({"type": "ping"})
            err = ws.receive_json()
            assert err["type"] == "frame_error"

    def test_stop_message_ends_session(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            ws.receive_json()
            ws.send_json({"type": "stop"})
            # Connection should close cleanly with no further messages.

    def test_many_consecutive_bad_frames_closes_session(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_WEBCAM_TEST") as ws:
            ws.receive_json()
            saw_fatal_error = False
            for _ in range(15):
                ws.send_json({"type": "frame", "jpeg_b64": "!!!not-real-data!!!"})
                msg = ws.receive_json()
                if msg["type"] == "error":
                    saw_fatal_error = True
                    break
                assert msg["type"] == "frame_error"
            assert saw_fatal_error, "expected the session to give up after many consecutive bad frames"


class TestWebcamStreamConcurrency:
    """Only one live webcam session may be active at a time - see
    webcam_stream()'s module docstring for why."""

    def setup_method(self):
        _reset_session_lock()

    def teardown_method(self):
        _reset_session_lock()

    def test_second_concurrent_session_is_rejected(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_A") as ws1:
            ready1 = ws1.receive_json()
            assert ready1["type"] == "ready"

            with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_B") as ws2:
                msg2 = ws2.receive_json()
                assert msg2["type"] == "error"
                assert "already running" in msg2["detail"].lower()

            # First session must be completely unaffected by the rejected
            # second connection attempt.
            ws1.send_json({"type": "frame", "jpeg_b64": _blank_frame_b64()})
            result = ws1.receive_json()
            assert result["type"] == "result"

    def test_session_slot_freed_after_disconnect(self, client):
        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_A") as ws1:
            ws1.receive_json()
        # ws1's context manager has exited (client side closed), but the
        # SERVER-side handler's cleanup (its finally block releasing
        # _webcam_session_active) runs as a background task/thread - there
        # is real, inherent scheduling latency between "client closed its
        # side" and "server's finally block actually ran", in any async
        # system. Asserting the very next connection attempt succeeds with
        # zero delay assumes an instant-synchronicity guarantee nothing
        # actually provides, and makes this test flaky on the exact thing
        # it's trying to prove, not a real product bug (see
        # observations.py's webcam_stream(): the whole handler is one
        # try/except WebSocketDisconnect/finally that unconditionally
        # releases the lock on every exit path). Poll for the REAL
        # postcondition - the slot has actually been released - bounded to
        # a couple of seconds, which still fails this test hard if cleanup
        # never happens (the real invariant), just without demanding
        # impossible zero-latency.
        import time as _time
        import app.api.v1.observations as obs_module
        deadline = _time.time() + 2.0
        while _time.time() < deadline:
            with obs_module._webcam_session_lock:
                if not obs_module._webcam_session_active:
                    break
            _time.sleep(0.02)
        else:
            pytest.fail("session slot was never released within 2s of client disconnect")

        with client.websocket_connect("/api/v1/observations/webcam-stream/CAM_A") as ws2:
            ready = ws2.receive_json()
            assert ready["type"] == "ready"
