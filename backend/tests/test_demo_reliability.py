"""
backend/tests/test_demo_reliability.py

SIH26127 "Department Selection Final Demo Freeze" - Mode 1 (recorded-CCTV
upload) reliability check: run POST /ingest-video several times in a row
against the SAME camera with real video content and confirm every run
succeeds independently, with no state bleeding between runs (stale
output-file collisions, or one run's observations silently vanishing
because a later run overwrote them).

Real inference, real assertions - not mocked. Skipped (not failed) if the
real detector can't be constructed in this environment, matching every
other real-inference test in this repo.
"""
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
    import tempfile
    import numpy as np
    path = tempfile.mktemp(suffix=".mp4")
    frame = (128 * np.ones((120, 160, 3))).astype("uint8")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (160, 120))
    for _ in range(2):
        writer.write(frame)
    writer.release()
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


class TestThreeConsecutiveUploadCycles:
    """SIH26127 requirement: run at least 3 consecutive upload/process
    cycles and confirm each one succeeds with isolated results."""

    @classmethod
    def setup_class(cls):
        import sys
        for mod_name in (
            "ultralytics", "paddleocr",
            "detection.vehicle_detector", "detection.detect_plates",
            "recognition.ocr_reader",
        ):
            sys.modules.pop(mod_name, None)
        try:
            from detection.vehicle_detector import VehicleDetector
            VehicleDetector(model_path="yolov8n.pt")
        except Exception as e:
            pytest.skip(f"Vehicle detector unavailable in this environment: {e}")

    def test_three_consecutive_runs_each_succeed_and_stay_isolated(self, client, auth_headers, isolated_db):
        video_bytes = _tiny_valid_video_bytes()
        cumulative_observations_stored = 0

        # Baseline BEFORE any of these 3 runs - _UPLOAD_DIR is a real,
        # shared-across-the-whole-test-session directory (not isolated
        # per test the way the DB is above), so it can legitimately
        # already contain unrelated leftover files from other test
        # sessions/environments. The real per-run check is "did THIS run
        # leave anything new behind", via a before/after diff - not "is
        # the directory empty", which assumes a pristine starting state
        # this test has no right to assume.
        import app.api.v1.observations as obs_module
        baseline = set(obs_module._UPLOAD_DIR.glob("*")) if obs_module._UPLOAD_DIR.exists() else set()

        for run_index in range(3):
            resp = client.post(
                "/api/v1/observations/ingest-video",
                headers=auth_headers,
                data={"camera_id": "CAM_01"},
                files={"file": (f"clip_{run_index}.mp4", video_bytes, "video/mp4")},
            )
            assert resp.status_code == 200, f"run {run_index} failed: {resp.text}"
            body = resp.json()
            stats = body["statistics"]
            # A blank-frame clip legitimately produces zero vehicles every
            # time - the real assertion here is that every run completes
            # cleanly and independently, not that it finds a vehicle.
            assert stats["frames_processed"] == 2
            assert stats["vehicles_detected"] == 0
            assert stats["observations_stored"] == 0
            assert body["observations"] == []

            # No NEW temp upload file left behind by this run.
            after = set(obs_module._UPLOAD_DIR.glob("*")) if obs_module._UPLOAD_DIR.exists() else set()
            new_files = after - baseline
            assert new_files == set(), f"run {run_index} leaked temp upload file(s): {new_files}"

            cumulative_observations_stored += stats["observations_stored"]

        # Confirm the isolated DB reflects exactly the sum of all 3 runs -
        # no run silently overwrote or duplicated another's (0 vehicles
        # each here, so the real check is that all 3 requests were each
        # individually accepted and processed rather than the 2nd/3rd
        # being rejected or corrupted by leftover state from the 1st).
        from database.observation_store import ObservationStore
        store = ObservationStore()
        try:
            persisted = [o for o in store.all_observations() if o["camera_id"] == "CAM_01"]
        finally:
            store.close()
        assert len(persisted) == cumulative_observations_stored == 0

    def test_three_consecutive_runs_with_real_vehicle_content_each_produce_distinct_sources(self, client, auth_headers, isolated_db):
        """Same real-content video (a real bus photo, looped into a short
        clip) uploaded 3 times in a row to the same camera - each run must
        be individually recorded and attributable to its OWN upload, never
        merged into or overwritten by another run's records."""
        video_path = "/tmp/bus_test.mp4"
        if not os.path.isfile(video_path):
            pytest.skip(f"Real-content test video not present at {video_path}")
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        run_summaries = []
        for run_index in range(3):
            resp = client.post(
                "/api/v1/observations/ingest-video",
                headers=auth_headers,
                data={"camera_id": "CAM_02"},
                files={"file": (f"bus_run_{run_index}.mp4", video_bytes, "video/mp4")},
            )
            assert resp.status_code == 200, f"run {run_index} failed: {resp.text}"
            body = resp.json()
            assert body["statistics"]["vehicles_detected"] >= 1, f"run {run_index}: expected a real detection"
            run_summaries.append(body)

        # Every run's video_filename is preserved even though they all
        # shared the same uploaded bytes - confirms each run is tracked as
        # its own distinct event, not deduplicated/merged.
        filenames = [r["video_filename"] for r in run_summaries]
        assert filenames == ["bus_run_0.mp4", "bus_run_1.mp4", "bus_run_2.mp4"]

        # Each run that produced an annotated video got its OWN output file
        # (server-generated names are uuid-based per upload - see
        # observations.py's ingest_video()) - no run's annotated video
        # silently overwrote another's.
        annotated_urls = [r["annotated_video_url"] for r in run_summaries if r["annotated_video_url"]]
        assert len(annotated_urls) == len(set(annotated_urls)), (
            f"expected 3 distinct annotated video URLs, got collisions: {annotated_urls}"
        )

        from database.observation_store import ObservationStore
        store = ObservationStore()
        try:
            persisted = [o for o in store.all_observations() if o["camera_id"] == "CAM_02"]
        finally:
            store.close()
        total_expected = sum(r["statistics"]["observations_stored"] for r in run_summaries)
        assert len(persisted) == total_expected, (
            "observation count across 3 runs doesn't match the sum of each run's own "
            "reported observations_stored - suggests cross-run contamination"
        )
