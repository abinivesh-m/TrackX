"""
backend/tests/test_ingest_video.py

Real tests for POST /api/v1/observations/ingest-video - the video-upload
demo flow endpoint. Uses the app's real TestClient (lifespan-triggered, so
the dev admin user actually exists) and real login, not a mocked client.

Isolation: ObservationStore() (called with no args inside the endpoint,
same as every other router in this codebase) defaults to
config.DB_PATH_STR. This test monkeypatches
database.observation_store.DB_PATH_STR to a temp file per test so it never
touches the real outputs/results/observations.db.
"""
import io
import os

import cv2
import pytest
from fastapi.testclient import TestClient

from app.main import app
import database.observation_store as observation_store_module


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_observations.db")
    monkeypatch.setattr(observation_store_module, "DB_PATH_STR", db_path)
    return db_path


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@trackx.com", "password": "admin123"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _tiny_valid_video_bytes():
    """A real, decodable 2-frame mp4 - solid color frames, no real vehicle
    content. Used for the mechanical/validation tests, where the expected,
    correct result is zero vehicle detections (this is not content YOLO
    would classify as a vehicle) - not a stand-in for a real-content test."""
    import tempfile
    path = tempfile.mktemp(suffix=".mp4")
    frame = (128 * __import__("numpy").ones((120, 160, 3))).astype("uint8")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (160, 120))
    for _ in range(2):
        writer.write(frame)
    writer.release()
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


class TestIngestVideoValidation:
    def test_unknown_camera_id_rejected(self, client, auth_headers, isolated_db):
        resp = client.post(
            "/api/v1/observations/ingest-video",
            headers=auth_headers,
            data={"camera_id": "NOT_A_REAL_CAMERA"},
            files={"file": ("clip.mp4", _tiny_valid_video_bytes(), "video/mp4")},
        )
        assert resp.status_code == 404
        assert "Unknown camera id" in resp.json()["detail"]

    def test_unsupported_file_extension_rejected(self, client, auth_headers, isolated_db):
        resp = client.post(
            "/api/v1/observations/ingest-video",
            headers=auth_headers,
            data={"camera_id": "CAM_01"},
            files={"file": ("not_a_video.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported video format" in resp.json()["detail"]

    def test_empty_file_rejected(self, client, auth_headers, isolated_db):
        resp = client.post(
            "/api/v1/observations/ingest-video",
            headers=auth_headers,
            data={"camera_id": "CAM_01"},
            files={"file": ("clip.mp4", b"", "video/mp4")},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_undecodable_file_rejected(self, client, auth_headers, isolated_db):
        """Correct extension, garbage content - must be rejected by real
        decode validation (cv2.VideoCapture), not accepted on trust."""
        resp = client.post(
            "/api/v1/observations/ingest-video",
            headers=auth_headers,
            data={"camera_id": "CAM_01"},
            files={"file": ("clip.mp4", b"this is not a real video file" * 100, "video/mp4")},
        )
        assert resp.status_code == 400

    def test_requires_authentication(self, client, isolated_db):
        resp = client.post(
            "/api/v1/observations/ingest-video",
            data={"camera_id": "CAM_01"},
            files={"file": ("clip.mp4", _tiny_valid_video_bytes(), "video/mp4")},
        )
        assert resp.status_code == 401

    def test_video_over_duration_limit_rejected(self, client, auth_headers, isolated_db, monkeypatch):
        import app.api.v1.observations as obs_module
        monkeypatch.setattr(obs_module, "_MAX_VIDEO_DURATION_SECONDS", 0)
        resp = client.post(
            "/api/v1/observations/ingest-video",
            headers=auth_headers,
            data={"camera_id": "CAM_01"},
            files={"file": ("clip.mp4", _tiny_valid_video_bytes(), "video/mp4")},
        )
        assert resp.status_code == 400
        assert "demo-mode limit" in resp.json()["detail"]

    def test_temp_upload_file_cleaned_up_after_rejection(self, client, auth_headers, isolated_db):
        """The endpoint must not leave temp files behind on the disk after a
        request, success or failure - confirmed directly, not assumed."""
        import app.api.v1.observations as obs_module
        before = set(os.listdir(obs_module._UPLOAD_DIR)) if obs_module._UPLOAD_DIR.exists() else set()
        client.post(
            "/api/v1/observations/ingest-video",
            headers=auth_headers,
            data={"camera_id": "CAM_01"},
            files={"file": ("clip.mp4", b"garbage" * 50, "video/mp4")},
        )
        after = set(os.listdir(obs_module._UPLOAD_DIR)) if obs_module._UPLOAD_DIR.exists() else set()
        assert after == before, f"leaked temp file(s): {after - before}"


class TestIngestVideoProcessing:
    """These exercise the real pipeline (vehicle_detector + optional plate
    detector/OCR) synchronously - no mocking of detection/OCR. Skipped if
    ultralytics/yolov8n.pt can't actually be constructed in this
    environment (e.g. no network to fetch it and no local cache)."""

    @classmethod
    def setup_class(cls):
        # Pre-existing test-suite quirk, not something this file caused:
        # several other unit-test files (tests/test_day4_plate_crop.py and
        # siblings) stub sys.modules["ultralytics"] with a fake YOLO class
        # for their own fast, offline unit tests. Because
        # detection.vehicle_detector.py does `from ultralytics import YOLO`
        # at IMPORT time, whichever test file's import happens first in the
        # whole pytest session decides - permanently, for the rest of the
        # process - whether that name is bound to the real class or the
        # fake one; re-importing later does not undo an existing binding.
        # Force a clean, real re-import here so this integration test
        # exercises the actual detector regardless of collection order,
        # rather than silently getting a fake and failing confusingly deep
        # inside the pipeline call.
        import sys
        # Same reasoning for each: detection.detect_plates.py also does its
        # own `from ultralytics import YOLO`, and recognition.ocr_reader.py
        # does `from paddleocr import PaddleOCR` - each is an independent
        # import site that can get permanently bound to a fake class
        # depending on collection order, so each needs its own reset.
        for mod_name in (
            "ultralytics",
            "paddleocr",
            "detection.vehicle_detector",
            "detection.detect_plates",
            "recognition.ocr_reader",
        ):
            sys.modules.pop(mod_name, None)
        try:
            from detection.vehicle_detector import VehicleDetector
            VehicleDetector(model_path="yolov8n.pt")
        except Exception as e:
            pytest.skip(f"Vehicle detector unavailable in this environment: {e}")

    def test_synthetic_video_processes_with_zero_vehicles(self, client, auth_headers, isolated_db):
        """A solid-color test clip contains no vehicle content - the
        CORRECT result is 0 detections, not a crash and not a fabricated
        detection. This proves the full mechanical path (decode -> track ->
        stats -> persist -> respond) runs without error end to end."""
        resp = client.post(
            "/api/v1/observations/ingest-video",
            headers=auth_headers,
            data={"camera_id": "CAM_01"},
            files={"file": ("clip.mp4", _tiny_valid_video_bytes(), "video/mp4")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        stats = body["statistics"]
        assert stats["frames_processed"] == 2
        assert stats["vehicles_detected"] == 0
        assert stats["observations_stored"] == 0
        assert body["observations"] == []
        assert stats["processing_duration_seconds"] >= 0

    def test_real_vehicle_video_is_detected_and_persisted(self, client, auth_headers, isolated_db):
        """Real content test: a short clip built from a real photograph
        containing an actual bus (ultralytics' own well-known bus.jpg demo
        asset - the same image used in virtually every YOLO tutorial).
        Skips (does not fail) if that asset isn't reachable/present in this
        environment - this is a real-inference check, not something to fake
        with a mock when the asset is missing."""
        video_path = "/tmp/bus_test.mp4"
        if not os.path.isfile(video_path):
            pytest.skip(f"Real-content test video not present at {video_path}")

        with open(video_path, "rb") as f:
            video_bytes = f.read()

        resp = client.post(
            "/api/v1/observations/ingest-video",
            headers=auth_headers,
            data={"camera_id": "CAM_02"},
            files={"file": ("bus_test.mp4", video_bytes, "video/mp4")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        stats = body["statistics"]
        assert stats["frames_processed"] == 10
        # Real assertion, not just "did it return 200": a photograph with an
        # actual bus in it must produce at least one vehicle detection.
        assert stats["vehicles_detected"] >= 1, f"expected >=1 real vehicle detection, got: {stats}"
        assert stats["observations_stored"] == stats["vehicles_detected"]

        # Confirm it was actually persisted to the store, not just returned
        # in the response.
        from database.observation_store import ObservationStore
        store = ObservationStore()
        try:
            persisted = [o for o in store.all_observations() if o["camera_id"] == "CAM_02"]
        finally:
            store.close()
        assert len(persisted) == stats["vehicles_detected"]
