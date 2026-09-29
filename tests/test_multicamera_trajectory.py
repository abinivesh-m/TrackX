"""
test_multicamera_trajectory.py

SIH26127 "Multi-Camera Vehicle Trajectory Final Demo" - targeted tests for
the requirements that weren't already covered by test_intelligence.py
(same-plate linking, different-plates-must-not-merge, blacklist/alert
scanning) or test_spatio_temporal.py (travel-time/speed/impossible-travel
plausibility, already comprehensively tested at the
calculate_spatial_temporal_plausibility level).

This file focuses on what those two didn't test:
  1. Camera-local Track IDs genuinely differ across cameras for the SAME
     physical vehicle, and cross-camera identity must come from plate +
     timing + topology + appearance - never from track_id equality.
  2. Chronological ordering survives even when input observations arrive
     out of order (a real possibility - DB rows aren't guaranteed sorted).
  3. Distance calculation is road-graph-aware when a road connection
     exists, and honestly falls back to (and flags) straight-line distance
     when it doesn't - never presenting one as the other.
  4. Direction/bearing between camera locations (network/camera_network.py's
     bearing_deg()/compass_direction(), added by this audit - no such
     calculation existed anywhere before) is geometrically correct and
     never fabricated when coordinates are missing.
  5. Low-confidence OCR evidence must NOT be enough, on its own, to force a
     strong cross-camera identity match - demonstrated against the real
     fusion engine (intelligence/fusion.py), not a mock.

No db, no OCR/CNN deps - pure Python against real camera ids from
network.camera_network, same pattern as test_intelligence.py /
test_spatio_temporal.py.

Run with: python -m pytest tests/test_multicamera_trajectory.py -v
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.trajectory import build_trajectories
from intelligence.fusion import global_match_score, is_match, MATCH_THRESHOLD
from intelligence.spatio_temporal import calculate_spatial_temporal_plausibility
from network.camera_network import bearing_deg, compass_direction, _get_edge, CAMERAS

BASE_TIME = datetime(2026, 8, 24, 10, 0, 0)


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
    }
    if vec is not None:
        obs["appearance_vector"] = json.dumps(vec)
    if track_id is not None:
        obs["track_id"] = track_id
    return obs


# ---------------------------------------------------------------------------
# 1. Camera-local Track IDs differ across cameras but identity still links
# ---------------------------------------------------------------------------

def test_local_track_ids_differ_across_cameras_but_identity_still_links():
    """
    Exactly the scenario the spec calls out by name: CAM_01 Track 142,
    CAM_02 Track 37, CAM_03 Track 81 are the SAME physical vehicle. Camera-
    local track_ids must never be assumed equal across cameras, yet
    plate+timing+topology+appearance evidence must still link them into
    ONE trajectory - and each observation's OWN local track_id must be
    preserved untouched (never overwritten to a shared/global value).
    """
    vec = _vec(seed=1)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec=vec, track_id="142"),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec=vec, track_id="37"),
        _obs("TN10AB1234", "CAM_03", BASE_TIME + timedelta(seconds=386), vec=vec, track_id="81"),
    ]
    trajs = build_trajectories(obs)
    assert len(trajs) == 1, "same vehicle across 3 real cameras must reconstruct into one trajectory"

    linked = trajs[0]["observations"]
    assert [o["camera_id"] for o in linked] == ["CAM_01", "CAM_02", "CAM_03"]
    # the whole point: local track ids are NOT unified into one shared id
    assert [o.get("track_id") for o in linked] == ["142", "37", "81"]
    assert len({o.get("track_id") for o in linked}) == 3, \
        "local track ids must stay genuinely distinct per camera, not collapsed"


def test_identical_local_track_id_string_across_cameras_does_not_imply_same_vehicle():
    """
    The inverse of the above: two DIFFERENT physical vehicles that happen
    to share the same camera-LOCAL track_id label (e.g. both are "track 1"
    at their respective camera, which is completely normal - local track
    counters restart per camera/session) must NOT be treated as the same
    vehicle just because that label matches. Different plates, different
    appearance, must stay separate.
    """
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec=_vec(seed=1), track_id="1"),
        _obs("KA99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=200), vec=_vec(seed=99), track_id="1"),
    ]
    trajs = build_trajectories(obs)
    assert len(trajs) == 2, "matching local track_id label alone must never merge two different vehicles"


# ---------------------------------------------------------------------------
# 2. Chronological ordering survives out-of-order input
# ---------------------------------------------------------------------------

def test_chronological_ordering_survives_scrambled_input():
    """DB rows are not guaranteed to arrive in timestamp order (concurrent
    camera uploads, out-of-order inserts). build_trajectories() must still
    produce a trajectory whose observations are in real chronological
    order, matching the spec's required CAM_01 -> CAM_02 -> CAM_03 timeline
    presentation."""
    vec = _vec(seed=5)
    hop_a = _obs("TN10AB1234", "CAM_01", BASE_TIME, vec=vec, track_id="a")
    hop_b = _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec=vec, track_id="b")
    hop_c = _obs("TN10AB1234", "CAM_03", BASE_TIME + timedelta(seconds=386), vec=vec, track_id="c")

    # deliberately scrambled: C, A, B
    trajs = build_trajectories([hop_c, hop_a, hop_b])
    assert len(trajs) == 1
    observed = trajs[0]["observations"]
    timestamps = [o["timestamp"] for o in observed]
    assert timestamps == sorted(timestamps), "trajectory observations must come out chronologically ordered"
    assert [o["camera_id"] for o in observed] == ["CAM_01", "CAM_02", "CAM_03"]


# ---------------------------------------------------------------------------
# 3. Distance: road-graph-aware when connected, honestly flagged when not
# ---------------------------------------------------------------------------

def test_distance_uses_real_road_graph_when_cameras_are_connected():
    """CAM_01 <-> CAM_02 has a real, explicit road-graph edge
    (network/camera_network.py ROAD_GRAPH) of 0.5km - the plausibility
    engine must report exactly that road distance (not a straight-line
    haversine approximation) and mark the segment as spatially connected."""
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02", BASE_TIME, BASE_TIME + timedelta(seconds=100)
    )
    edge = _get_edge("CAM_01", "CAM_02")
    assert result.spatial_connected is True
    assert result.distance_km == edge["distance_km"] == 0.5


def test_distance_falls_back_to_straight_line_and_flags_no_road_connection():
    """CAM_01 <-> CAM_06 has NO road-graph edge. The engine must never
    silently invent a road distance for an unconnected pair - it computes
    straight-line distance ONLY for reporting purposes and explicitly
    marks spatial_connected=False / is_plausible=False, so callers can
    never present that number as a real road distance."""
    assert _get_edge("CAM_01", "CAM_06") is None, "test assumes these cameras have no road-graph edge"
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_06", BASE_TIME, BASE_TIME + timedelta(seconds=300)
    )
    assert result.spatial_connected is False
    assert result.is_plausible is False
    assert result.get_assessment() == "NO ROAD CONNECTION"
    # straight-line distance is still reported (for transparency), but never
    # as a stand-in for a real road distance - spatial_connected says so.
    assert result.distance_km > 0


# ---------------------------------------------------------------------------
# 4. Direction / bearing between camera locations
# ---------------------------------------------------------------------------

def test_bearing_and_compass_direction_are_geometrically_correct():
    # due north: same longitude, higher latitude -> bearing ~0 degrees
    assert round(bearing_deg(10.0, 76.0, 11.0, 76.0)) == 0
    assert compass_direction(bearing_deg(10.0, 76.0, 11.0, 76.0)) == "North"

    # due east: same latitude, higher longitude -> bearing ~90 degrees
    east_bearing = bearing_deg(10.0, 76.0, 10.0, 77.0)
    assert 85 < east_bearing < 95
    assert compass_direction(east_bearing) == "East"

    # due south -> ~180 degrees
    assert round(bearing_deg(11.0, 76.0, 10.0, 76.0)) == 180
    assert compass_direction(180) == "South"


def test_bearing_between_real_adjacent_cameras():
    """Sanity check against the real camera network, not synthetic points -
    CAM_01 (Gandhipuram) -> CAM_02 (Tidel Park) should compute some real,
    non-None bearing derived from their actual stored coordinates."""
    a, b = CAMERAS["CAM_01"], CAMERAS["CAM_02"]
    brg = bearing_deg(a["lat"], a["long"], b["lat"], b["long"])
    assert brg is not None
    assert 0.0 <= brg < 360.0
    assert compass_direction(brg) in {
        "North", "North-East", "East", "South-East",
        "South", "South-West", "West", "North-West",
    }


def test_bearing_never_fabricated_for_identical_or_missing_coordinates():
    """Zero displacement (or missing coordinates, handled by callers passing
    None through) must yield None, never a guessed direction."""
    assert bearing_deg(11.0, 76.0, 11.0, 76.0) is None
    assert compass_direction(None) is None


# ---------------------------------------------------------------------------
# 5. Low-confidence OCR must not force a strong cross-camera identity
# ---------------------------------------------------------------------------

def test_low_confidence_ocr_alone_does_not_force_a_strong_match():
    """
    Two observations with imperfect-but-plausible plate similarity (a
    realistic single-character OCR drift) and a physically easy,
    fast-legal transition (so temporal/spatial signals are already near-
    maximal) - but VERY low OCR confidence on both reads. The engine must
    NOT treat this as a confident cross-camera identity match just because
    the raw plate strings are similar; confidence-weighted redistribution
    (intelligence/fusion.py's global_match_score) must keep the total
    below MATCH_THRESHOLD.
    """
    obs_a = _obs("TN10AB1234", "CAM_01", BASE_TIME, confidence=0.05)
    obs_b = _obs("TN10AB1230", "CAM_02", BASE_TIME + timedelta(seconds=170), confidence=0.05)

    matched, score, breakdown = is_match(obs_a, obs_b)
    assert matched is False, f"low-confidence OCR evidence should not clear MATCH_THRESHOLD (got score={score})"
    assert score < MATCH_THRESHOLD
    assert breakdown["confidence_label"] == "NO_MATCH"
    # the mechanism must be visible/explainable, not just the outcome
    assert breakdown["ocr_confidence_used"] < 0.2


def test_high_confidence_ocr_with_same_evidence_does_cross_threshold():
    """Contrast case proving the low-confidence result above is really
    about confidence, not about the transition itself being implausible -
    identical plates/timing/cameras, only the OCR confidence changes."""
    obs_a = _obs("TN10AB1234", "CAM_01", BASE_TIME, confidence=0.95)
    obs_b = _obs("TN10AB1230", "CAM_02", BASE_TIME + timedelta(seconds=170), confidence=0.95)

    matched, score, breakdown = is_match(obs_a, obs_b)
    assert matched is True
    assert score >= MATCH_THRESHOLD


if __name__ == "__main__":
    test_local_track_ids_differ_across_cameras_but_identity_still_links()
    test_identical_local_track_id_string_across_cameras_does_not_imply_same_vehicle()
    test_chronological_ordering_survives_scrambled_input()
    test_distance_uses_real_road_graph_when_cameras_are_connected()
    test_distance_falls_back_to_straight_line_and_flags_no_road_connection()
    test_bearing_and_compass_direction_are_geometrically_correct()
    test_bearing_between_real_adjacent_cameras()
    test_bearing_never_fabricated_for_identical_or_missing_coordinates()
    test_low_confidence_ocr_alone_does_not_force_a_strong_match()
    test_high_confidence_ocr_with_same_evidence_does_cross_threshold()
    print("all multi-camera trajectory tests passed")
