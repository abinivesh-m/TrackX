"""
test_intelligence.py

Phase 0 audit (SIH26127): lightweight tests for the core matching/alerting
logic, independent of the seeded demo dataset - builds small observation
fixtures directly so these keep passing even if demo/seed_demo_data.py's
specific scenario data ever changes.

No db, no OCR/CNN deps - pure Python/numpy against real camera ids from
network.camera_network (needed so spatial/temporal feasibility checks have
a real road-graph edge to evaluate).

Run with: python -m pytest tests/test_intelligence.py -v
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.trajectory import build_trajectories
from intelligence.alerts import scan_trajectories_for_alerts, check_blacklist, BLACKLIST_MATCH_THRESHOLD
from database.blacklist_store import BlacklistStore


def _isolated_blacklist_store(tmp_name):
    path = os.path.join("/tmp", tmp_name)
    if os.path.exists(path):
        os.remove(path)
    return BlacklistStore(db_path=path)


BASE_TIME = datetime(2026, 8, 24, 9, 0, 0)


def _vec(seed=1, noise=0.0):
    import numpy as np
    rng = np.random.RandomState(seed)
    v = rng.normal(size=64)
    if noise:
        v = v + np.random.RandomState(seed + 1).normal(scale=noise, size=v.shape)
    return v.tolist()


def _obs(plate, camera_id, ts, confidence=0.9, vec=None, track_id=None):
    obs = {
        "plate_text": plate,
        "confidence": confidence,
        "camera_id": camera_id,
        "timestamp": ts.isoformat(),
        "lat": 0.0,
        "long": 0.0,
        "appearance_vector": json.dumps(vec) if vec is not None else None,
    }
    if track_id:
        obs["track_id"] = track_id
    return obs


def test_ocr_variation_reconstructed_as_one_global_vehicle():
    """
    Same physical vehicle, one confusable OCR misread on the middle hop
    (B -> 8), must still reconstruct into a SINGLE trajectory - this is the
    core claim of the OCR-robustness demo.
    """
    vec = _vec(seed=42)
    obs = [
        _obs("TN45BS9012", "CAM_01", BASE_TIME, confidence=0.91, vec=vec, track_id="test_vehicle_1"),
        _obs("TN458S9012", "CAM_02", BASE_TIME + timedelta(seconds=170), confidence=0.58, vec=vec, track_id="test_vehicle_1"),
        _obs("TN45BS9012", "CAM_03", BASE_TIME + timedelta(seconds=170 + 216), confidence=0.88, vec=vec, track_id="test_vehicle_1"),
    ]

    trajs = build_trajectories(obs)
    multi_hop = [t for t in trajs if len(t["observations"]) > 1]

    assert len(multi_hop) == 1
    traj = multi_hop[0]
    assert len(traj["observations"]) == 3
    plates_seen = set(o["plate_text"] for o in traj["observations"])
    assert plates_seen == {"TN45BS9012", "TN458S9012"}


def test_unrelated_vehicles_stay_separate():
    """two genuinely different plates/appearances at unconnected times must
    NOT be merged into one trajectory."""
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec=_vec(seed=1), track_id="vehicle_1"),
        _obs("KA99ZZ0000", "CAM_01", BASE_TIME + timedelta(seconds=5), vec=_vec(seed=2), track_id="vehicle_2"),
    ]
    trajs = build_trajectories(obs)
    assert len(trajs) == 2
    assert all(len(t["observations"]) == 1 for t in trajs)


def test_blacklist_matching_allows_minor_ocr_variation():
    # Phase 1 (Step 7): blacklist now lives in BlacklistStore, not a hardcoded
    # list - use an isolated temp store so this test doesn't depend on
    # whatever is (or isn't) seeded in the shared project db.
    store = _isolated_blacklist_store("test_alerts_blacklist_1.db")
    store.add_plate("TN38AB1234", description="test entry", severity="HIGH")

    is_flagged, matched, sim = check_blacklist("TN38AB1234", blacklist_store=store)
    assert is_flagged is True
    assert matched == "TN38AB1234"
    assert sim == 1.0

    # a minor OCR variation (B misread as 8) should still match
    is_flagged2, matched2, sim2 = check_blacklist("TN38A81234", blacklist_store=store)
    assert is_flagged2 is True
    assert sim2 >= BLACKLIST_MATCH_THRESHOLD

    store.close()


def test_blacklist_matching_rejects_unrelated_plate():
    store = _isolated_blacklist_store("test_alerts_blacklist_2.db")
    store.add_plate("TN38AB1234", description="test entry", severity="HIGH")

    is_flagged, matched, sim = check_blacklist("KA01ZZ9999", blacklist_store=store)
    assert is_flagged is False

    store.close()


def test_blacklisted_vehicle_generates_alert_via_full_scan():
    """Step 7 requirement: a blacklisted vehicle's trajectory produces a
    BLACKLIST_MATCH alert through the full scan_trajectories_for_alerts()
    path, not just the lower-level check_blacklist() helper."""
    store = _isolated_blacklist_store("test_alerts_blacklist_3.db")
    store.add_plate("TN38AB1234", description="test entry", severity="HIGH")

    obs = [
        _obs("TN38AB1234", "CAM_02", BASE_TIME, vec=_vec(seed=10)),
        _obs("TN38AB1234", "CAM_03", BASE_TIME + timedelta(seconds=210), vec=_vec(seed=10, noise=0.02)),
    ]
    trajs = build_trajectories(obs)
    alerts = scan_trajectories_for_alerts(trajs, blacklist_store=store, all_observations=obs)

    blacklist_alerts = [a for a in alerts if a["type"] == "BLACKLIST_MATCH"]
    assert len(blacklist_alerts) == 1
    assert blacklist_alerts[0]["plate_text"] == "TN38AB1234"

    store.close()


def test_non_blacklisted_vehicle_generates_no_blacklist_alert():
    """Step 7 requirement: a normal (non-blacklisted) vehicle must NOT
    produce a BLACKLIST_MATCH alert, even with an empty/unrelated blacklist."""
    store = _isolated_blacklist_store("test_alerts_blacklist_4.db")
    store.add_plate("TN38AB1234", description="unrelated entry", severity="HIGH")

    obs = [
        _obs("KA05XY7777", "CAM_01", BASE_TIME, vec=_vec(seed=11)),
        _obs("KA05XY7777", "CAM_02", BASE_TIME + timedelta(seconds=170), vec=_vec(seed=11, noise=0.02)),
    ]
    trajs = build_trajectories(obs)
    alerts = scan_trajectories_for_alerts(trajs, blacklist_store=store, all_observations=obs)

    blacklist_alerts = [a for a in alerts if a["type"] == "BLACKLIST_MATCH"]
    assert len(blacklist_alerts) == 0

    store.close()


def test_missing_plate_search_returns_no_trajectory():
    obs = [_obs("TN10AB1234", "CAM_01", BASE_TIME, vec=_vec(seed=1))]
    trajs = build_trajectories(obs)
    matches = [t for t in trajs
               if any(o["plate_text"] == "ZZ99XX9999" for o in t["observations"])]
    assert matches == []


def test_repeated_camera_alert_fires_for_same_camera_loitering():
    plate = "TN99ZZ0000"
    vec = _vec(seed=7)
    obs = [
        _obs(plate, "CAM_03", BASE_TIME, vec=vec),
        _obs(plate, "CAM_03", BASE_TIME + timedelta(seconds=90), vec=vec),
        _obs(plate, "CAM_03", BASE_TIME + timedelta(seconds=200), vec=vec),
    ]
    trajs = build_trajectories(obs)
    alerts = scan_trajectories_for_alerts(trajs, all_observations=obs)

    repeated = [a for a in alerts if a["type"] == "REPEATED_CAMERA_SIGHTING"]
    assert len(repeated) == 1
    assert repeated[0]["camera_id"] == "CAM_03"
    assert repeated[0]["count"] == 3


if __name__ == "__main__":
    test_ocr_variation_reconstructed_as_one_global_vehicle()
    test_unrelated_vehicles_stay_separate()
    test_blacklist_matching_allows_minor_ocr_variation()
    test_blacklist_matching_rejects_unrelated_plate()
    test_blacklisted_vehicle_generates_alert_via_full_scan()
    test_non_blacklisted_vehicle_generates_no_blacklist_alert()
    test_missing_plate_search_returns_no_trajectory()
    test_repeated_camera_alert_fires_for_same_camera_loitering()
    print("all intelligence tests passed")
