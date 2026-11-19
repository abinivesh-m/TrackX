"""
backend/tests/test_camera_status_provenance.py

SIH26127 "Final Data Integrity" audit (2026-09-11) - regression test for a
real bug found while auditing Camera Network honesty: GET /api/v1/cameras
and GET /api/v1/cameras/{camera_id} hardcoded `"status": "ONLINE"` for
every configured camera, unconditionally - indistinguishable from a camera
that had genuinely produced a recent observation. Only GET
/api/v1/cameras/health computed real status from the observation stream.

Neither hardcoded endpoint is currently rendered by the frontend
(CamerasPage.tsx calls /cameras/health; VideoDemoPage.tsx's camera-select
dropdown never reads .status - see git history/comments in
backend/app/api/v1/cameras.py for the verification), so this wasn't
visibly misleading a user, but the raw API itself must not assert ONLINE
without a live-health basis - a judge inspecting the API directly (or any
future frontend consumer) would otherwise see a fabricated status. Fixed
by giving all three endpoints one shared, real status computation.

Uses the same isolated-sqlite-db pattern as
backend/tests/test_demo_reliability.py's `isolated_db` fixture - no
ultralytics/paddleocr/torch dependency.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import database.observation_store as observation_store_module
from database.observation_store import ObservationStore
from network.camera_network import CAMERAS


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_observations.db")
    monkeypatch.setattr(observation_store_module, "DB_PATH_STR", db_path)
    return db_path


def _add_recent_observation(db_path, camera_id):
    from datetime import datetime
    store = ObservationStore(db_path=db_path)
    store.add({
        "plate_text": "TN10AB1234", "confidence": 0.9, "camera_id": camera_id,
        "timestamp": datetime.now().isoformat(), "lat": 11.0168, "long": 76.9558,
        "track_id": "1", "data_source": "REAL_INFERENCE",
    })
    store.close()


class TestCameraStatusIsNeverHardcoded:
    def test_get_cameras_reports_not_configured_when_no_observations_exist(self, isolated_db):
        from app.api.v1 import cameras as cameras_module
        # Call the real, unpatched code path directly (no FastAPI/auth
        # plumbing needed - these are plain functions).
        health = cameras_module._camera_health_map()
        assert len(health) == len(CAMERAS)
        for cam_id in CAMERAS:
            assert health[cam_id]["status"] == "NOT_CONFIGURED", (
                f"{cam_id} has zero observations in this isolated db but "
                f"was reported as {health[cam_id]['status']!r} - status must "
                "never default to ONLINE without real observation evidence."
            )

    def test_get_cameras_and_get_camera_use_the_same_real_status_as_health(self, isolated_db):
        from app.api.v1 import cameras as cameras_module
        some_camera = next(iter(CAMERAS))
        _add_recent_observation(isolated_db, some_camera)

        health = cameras_module._camera_health_map()
        list_payload = [
            cameras_module._camera_payload(cam_id, config, health[cam_id])
            for cam_id, config in CAMERAS.items()
        ]
        single_payload = cameras_module._camera_payload(
            some_camera, CAMERAS[some_camera], health[some_camera]
        )

        by_id = {c["camera_id"]: c for c in list_payload}
        assert by_id[some_camera]["status"] == "ONLINE"
        assert by_id[some_camera]["observation_count"] == 1
        # /cameras, /cameras/{id}, and /cameras/health must never disagree -
        # they now all derive from the exact same _camera_health_map() call.
        assert single_payload["status"] == by_id[some_camera]["status"]
        assert single_payload["observation_count"] == by_id[some_camera]["observation_count"]

        other_camera = next(c for c in CAMERAS if c != some_camera)
        assert by_id[other_camera]["status"] == "NOT_CONFIGURED", (
            "a camera with zero observations must not inherit ONLINE status "
            "just because some other camera in the network is active."
        )

    def test_no_camera_endpoint_source_hardcodes_the_string_online_as_a_status_literal(self):
        # Static guard against the exact regression: a bare
        # `"status": "ONLINE"` (or single-quoted) literal anywhere in
        # cameras.py. The only legitimate appearance of the word ONLINE in
        # this file now is inside the real _camera_status() classifier.
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "app", "api", "v1", "cameras.py")
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        assert '"status": "ONLINE"' not in src
        assert "'status': 'ONLINE'" not in src
