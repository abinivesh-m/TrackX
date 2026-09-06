"""
test_analytics.py

Phase 0 audit (SIH26127): lightweight tests for the analytics logic the
dashboard depends on to correctly separate cross-camera ROUTES from
same-camera REPEATED SIGHTINGS - the specific bug called out in the audit
(CAM_03 -> CAM_03 was being counted as a "route").

Pure data-in/data-out tests against small hand-built trajectory fixtures -
no db, no OCR/CNN deps needed.

Run with: python -m pytest tests/test_analytics.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.analytics import (
    cross_camera_route_frequency,
    repeated_camera_sightings,
    route_frequency,
    vehicles_per_camera,
    busiest_camera,
)


def _traj(global_id, camera_sequence):
    """minimal trajectory fixture: only the fields these functions read"""
    return {
        "global_id": global_id,
        "observations": [{"camera_id": c} for c in camera_sequence],
    }


def test_cross_camera_routes_exclude_same_camera_transitions():
    trajs = [
        _traj(1, ["CAM_01", "CAM_02", "CAM_03"]),
        _traj(2, ["CAM_01", "CAM_02"]),
        _traj(11, ["CAM_03", "CAM_03", "CAM_03"]),  # pure loitering, no real route
    ]
    routes = cross_camera_route_frequency(trajs)

    assert "CAM_03 -> CAM_03" not in routes
    assert routes["CAM_01 -> CAM_02"] == 2
    assert routes["CAM_02 -> CAM_03"] == 1


def test_repeated_camera_sightings_isolates_same_camera_activity():
    trajs = [
        _traj(1, ["CAM_01", "CAM_02", "CAM_03"]),
        _traj(11, ["CAM_03", "CAM_03", "CAM_03"]),
    ]
    repeats = repeated_camera_sightings(trajs)

    assert "CAM_01" not in repeats
    assert repeats["CAM_03"]["repeat_transitions"] == 2
    assert repeats["CAM_03"]["global_vehicle_ids"] == [11]


def test_cross_camera_and_repeated_are_a_full_partition_of_route_frequency():
    """
    every transition counted by the old combined route_frequency() must land
    in EXACTLY ONE of (cross-camera routes, repeated sightings) - nothing
    silently dropped, nothing double-counted.
    """
    trajs = [
        _traj(1, ["CAM_01", "CAM_02", "CAM_03"]),
        _traj(6, ["CAM_02", "CAM_03"]),
        _traj(11, ["CAM_03", "CAM_03", "CAM_03"]),
    ]
    combined_total = sum(route_frequency(trajs).values())
    cross_total = sum(cross_camera_route_frequency(trajs).values())
    repeat_total = sum(d["repeat_transitions"] for d in repeated_camera_sightings(trajs).values())

    assert combined_total == cross_total + repeat_total


def test_cross_camera_routes_dynamic_not_hardcoded():
    """swap in a totally different camera topology and confirm the output
    tracks the input data rather than any baked-in demo values."""
    trajs = [_traj(1, ["CAM_99", "CAM_100"]), _traj(2, ["CAM_99", "CAM_100"])]
    routes = cross_camera_route_frequency(trajs)
    assert routes == {"CAM_99 -> CAM_100": 2}


def test_no_observations_returns_empty_not_crash():
    assert vehicles_per_camera([]) == {}
    assert busiest_camera([]) is None
    assert cross_camera_route_frequency([]) == {}
    assert repeated_camera_sightings([]) == {}


if __name__ == "__main__":
    test_cross_camera_routes_exclude_same_camera_transitions()
    test_repeated_camera_sightings_isolates_same_camera_activity()
    test_cross_camera_and_repeated_are_a_full_partition_of_route_frequency()
    test_cross_camera_routes_dynamic_not_hardcoded()
    test_no_observations_returns_empty_not_crash()
    print("all analytics tests passed")
