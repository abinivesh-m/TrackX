"""
backend/tests/test_multicamera_trajectory_endpoints.py

SIH26127 multi-camera trajectory audit - endpoint-level tests for the two
real fixes made to the trajectory/vehicle search API surface:

1. backend/app/api/v1/trajectory.py's /search (TrajectoryPage.tsx) used to
   recompute its OWN straight-line-distance / hardcoded-130kmh-threshold
   logic, completely separate from backend/app/api/v1/vehicles.py's
   /search (VehiclesPage.tsx), which already used the real road-graph-
   aware intelligence/spatio_temporal.py engine. The two pages could show
   DIFFERENT distance/speed/anomaly numbers for the SAME plate. Fixed by
   having trajectory.py reuse vehicles.py's _build_hops_and_segments() -
   these tests prove the two endpoints now agree.
2. Local (camera-scoped) Track ID and plate_state were computed and
   persisted by the real pipeline but never surfaced through either
   endpoint's hop data - the SIH26127 spec's core multi-camera identity
   requirement ("CAM_01 Track 142, CAM_02 Track 37..."). Fixed by adding
   them to _build_hops_and_segments()'s hop dict.

Uses a real isolated sqlite db (never the shared dev db) populated with
observation rows shaped exactly like pipeline.run_video_to_db()'s real
output schema (same fields ObservationStore.add() persists for a real
video run) - not the ORM-based VehicleService path other tests in this
file's directory exercise, which is a separate, currently-unused code path
from the live /api/v1/vehicles and /api/v1/trajectory routers actually
mounted in app.main.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
import database.observation_store as observation_store_module
from database.observation_store import ObservationStore


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_multicam_observations.db")
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


BASE_TIME = datetime(2026, 9, 10, 10, 0, 0)


def _seed_clean_multicam_trip(isolated_db):
    """CAM_01 -> CAM_02 -> CAM_03, same plate, distinct local track_ids per
    camera, real road-graph-plausible timing (matches the spec's own
    worked example format)."""
    store = ObservationStore(db_path=isolated_db)
    hops = [
        ("CAM_01", 0, "142"),
        ("CAM_02", 157, "37"),   # 0.5km @ CAM_01->CAM_02, well within plausible window
        ("CAM_03", 368, "81"),   # 2.5km @ CAM_02->CAM_03, well within plausible window
    ]
    for cam, gap, track_id in hops:
        store.add({
            "plate_text": "TN10AB1234",
            "normalized_plate": "TN10AB1234",
            "confidence": 0.93,
            "camera_id": cam,
            "timestamp": (BASE_TIME + timedelta(seconds=gap)).isoformat(),
            "lat": None,   # deliberately absent - endpoint must fall back to CAMERAS lookup
            "long": None,
            "track_id": track_id,
            "vehicle_type": "car",
            "plate_state": "VERIFIED",
            "data_source": "REAL_INFERENCE",
        })
    store.close()


def _seed_impossible_transition(isolated_db):
    """CAM_01 -> CAM_04 (3.5km, 40kmph limit) in 10 seconds - physically
    impossible (would require ~1260 km/h)."""
    store = ObservationStore(db_path=isolated_db)
    for cam, gap, track_id in [("CAM_01", 0, "5"), ("CAM_04", 10, "9")]:
        store.add({
            "plate_text": "TN99IM0000",
            "normalized_plate": "TN99IM0000",
            "confidence": 0.9,
            "camera_id": cam,
            "timestamp": (BASE_TIME + timedelta(seconds=gap)).isoformat(),
            "lat": None,
            "long": None,
            "track_id": track_id,
            "vehicle_type": "car",
            "plate_state": "VERIFIED",
            "data_source": "REAL_INFERENCE",
        })
    store.close()


class TestVehiclesAndTrajectorySearchAgree:
    """Regression test for the duplicate-implementation bug: the SAME plate
    must produce the SAME distance/speed/camera-sequence on both pages."""

    def test_total_distance_and_camera_sequence_match_across_endpoints(self, client, auth_headers, isolated_db):
        _seed_clean_multicam_trip(isolated_db)

        vehicles_resp = client.get(
            "/api/v1/vehicles/search", params={"plate": "TN10AB1234"}, headers=auth_headers
        )
        trajectory_resp = client.get(
            "/api/v1/trajectory/search", params={"plate": "TN10AB1234"}, headers=auth_headers
        )
        assert vehicles_resp.status_code == 200, vehicles_resp.text
        assert trajectory_resp.status_code == 200, trajectory_resp.text

        v = vehicles_resp.json()["trajectory"]
        t = trajectory_resp.json()

        assert v["camera_sequence"] == ["CAM_01", "CAM_02", "CAM_03"]
        assert [hop["camera_id"] for hop in t["trajectory"]] == ["CAM_01", "CAM_02", "CAM_03"]

        # Both endpoints must now report the SAME real road-graph-based
        # total distance for the same plate (0.5 + 2.5 = 3.0 km) - this is
        # exactly the inconsistency the fix eliminates.
        assert v["total_distance_km"] == t["total_distance_km"] == 3.0

    def test_local_track_id_and_plate_state_surfaced_on_both_endpoints(self, client, auth_headers, isolated_db):
        """SIH26127 core requirement: local (camera-scoped) track IDs must
        be visible per hop, and must genuinely differ across cameras."""
        _seed_clean_multicam_trip(isolated_db)

        vehicles_resp = client.get(
            "/api/v1/vehicles/search", params={"plate": "TN10AB1234"}, headers=auth_headers
        )
        trajectory_resp = client.get(
            "/api/v1/trajectory/search", params={"plate": "TN10AB1234"}, headers=auth_headers
        )

        v_hops = vehicles_resp.json()["trajectory"]["hops"]
        t_hops = trajectory_resp.json()["trajectory"]

        assert [h["local_track_id"] for h in v_hops] == ["142", "37", "81"]
        assert [h["local_track_id"] for h in t_hops] == ["142", "37", "81"]
        assert all(h["plate_state"] == "VERIFIED" for h in v_hops)
        assert all(h["plate_state"] == "VERIFIED" for h in t_hops)

    def test_route_direction_present_when_coordinates_available(self, client, auth_headers, isolated_db):
        """Direction/bearing between consecutive real camera locations must
        be computed and surfaced (network/camera_network.py's
        bearing_deg()/compass_direction(), newly added by this audit)."""
        _seed_clean_multicam_trip(isolated_db)

        resp = client.get("/api/v1/vehicles/search", params={"plate": "TN10AB1234"}, headers=auth_headers)
        hops = resp.json()["trajectory"]["hops"]

        segments_with_direction = [
            h["segment_from_prev"] for h in hops[1:]
            if h.get("segment_from_prev") and h["segment_from_prev"].get("route_direction")
        ]
        assert len(segments_with_direction) == 2, "both real segments should have a computed compass direction"
        for seg in segments_with_direction:
            assert seg["route_bearing_deg"] is not None
            assert 0.0 <= seg["route_bearing_deg"] < 360.0


class TestImpossibleTravelTimeAnomalyLanguage:
    """SIH26127 spec requires the exact phrase 'SUSPICIOUS TRAVEL-TIME
    ANOMALY' for a physically impossible transition, and 'Normal
    transition' / 'Suspicious transition' otherwise - never
    'Criminal vehicle' or 'Confirmed illegal activity'."""

    def test_impossible_transition_flagged_with_required_language(self, client, auth_headers, isolated_db):
        _seed_impossible_transition(isolated_db)

        resp = client.get("/api/v1/trajectory/search", params={"plate": "TN99IM0000"}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert len(body["anomaly_flags"]) >= 1
        assert any("SUSPICIOUS TRAVEL-TIME ANOMALY" in flag for flag in body["anomaly_flags"])
        assert not any("criminal" in flag.lower() or "confirmed illegal" in flag.lower()
                       for flag in body["anomaly_flags"])

        anomalous_hop = body["trajectory"][1]
        assert anomalous_hop["assessment"] == "SUSPICIOUS TRAVEL-TIME ANOMALY"

    def test_normal_transition_labeled_correctly(self, client, auth_headers, isolated_db):
        _seed_clean_multicam_trip(isolated_db)

        resp = client.get("/api/v1/trajectory/search", params={"plate": "TN10AB1234"}, headers=auth_headers)
        body = resp.json()

        assert body["anomaly_flags"] == []
        for hop in body["trajectory"][1:]:
            assert hop["assessment"] in ("Normal transition", "Suspicious transition")
            assert "SUSPICIOUS TRAVEL-TIME ANOMALY" not in hop["assessment"]


class TestPlatesDoNotMergeAtEndpointLevel:
    def test_different_plates_return_independent_trajectories(self, client, auth_headers, isolated_db):
        store = ObservationStore(db_path=isolated_db)
        store.add({
            "plate_text": "TN10AB1234", "normalized_plate": "TN10AB1234", "confidence": 0.9,
            "camera_id": "CAM_01", "timestamp": BASE_TIME.isoformat(), "lat": None, "long": None,
            "track_id": "1", "vehicle_type": "car",
        })
        store.add({
            "plate_text": "KA05XY7777", "normalized_plate": "KA05XY7777", "confidence": 0.9,
            "camera_id": "CAM_01", "timestamp": (BASE_TIME + timedelta(seconds=5)).isoformat(),
            "lat": None, "long": None, "track_id": "2", "vehicle_type": "car",
        })
        store.close()

        resp_a = client.get("/api/v1/trajectory/search", params={"plate": "TN10AB1234"}, headers=auth_headers)
        resp_b = client.get("/api/v1/trajectory/search", params={"plate": "KA05XY7777"}, headers=auth_headers)

        assert resp_a.json()["observation_count"] == 1
        assert resp_b.json()["observation_count"] == 1
        assert resp_a.json()["trajectory"][0]["plate_text"] != resp_b.json()["trajectory"][0]["plate_text"]
