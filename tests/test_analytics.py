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
    hourly_density,
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


def test_vehicles_per_camera_dedupes_repeated_per_frame_rows_of_the_same_track():
    """SIH26127 'Final Data Integrity' audit (2026-09-11): the real bug -
    demo/visual_pipeline.py's process_video() writes ONE ROW PER SAMPLED
    FRAME for the same physical vehicle (unlike pipeline.py's
    run_video_to_db(), which writes one row per finished track). The same
    real vehicle (track_id=1, one video file) sampled across 5 frames must
    still count as ONE vehicle, not five."""
    observations = [
        {"camera_id": "CAM_01", "source": "video1.mp4", "track_id": 1, "timestamp": f"2026-01-01T10:0{i}:00"}
        for i in range(5)
    ]
    assert vehicles_per_camera(observations) == {"CAM_01": 1}


def test_vehicles_per_camera_does_not_merge_same_track_id_from_different_sources():
    """The other half of the same fix: track_id numbering resets per
    pipeline run, so two DIFFERENT real vehicles from two different
    uploaded videos on the same camera can both be track_id=1 - this is a
    real, confirmed collision found in this project's own database (CAM_01
    track_id 4 and 5, two different video files). Deduping on track_id
    alone would wrongly merge them into fewer vehicles than actually
    exist; `source` must keep them apart."""
    observations = [
        {"camera_id": "CAM_01", "source": "video1.mp4", "track_id": 1, "timestamp": "2026-01-01T10:00:00"},
        {"camera_id": "CAM_01", "source": "video2.mp4", "track_id": 1, "timestamp": "2026-01-01T11:00:00"},
    ]
    assert vehicles_per_camera(observations) == {"CAM_01": 2}


def test_vehicles_per_camera_counts_rows_with_no_track_id_individually():
    """A row with no track_id (e.g. older/seeded data) has nothing to
    dedupe against - it must still be counted, exactly as before this fix,
    not silently dropped."""
    observations = [
        {"camera_id": "CAM_01", "source": None, "track_id": None, "timestamp": "2026-01-01T10:00:00"},
        {"camera_id": "CAM_01", "source": None, "track_id": None, "timestamp": "2026-01-01T10:01:00"},
    ]
    assert vehicles_per_camera(observations) == {"CAM_01": 2}


def test_hourly_density_dedupes_within_each_hour_but_not_across_hours():
    """A track sampled several times within ONE hour counts once; the same
    track_id legitimately spanning two different hour buckets counts once
    per hour it actually appears in (still real, not fabricated - a
    vehicle that was genuinely observed in both hours)."""
    observations = [
        {"camera_id": "CAM_01", "source": "video1.mp4", "track_id": 7, "timestamp": "2026-01-01T10:05:00"},
        {"camera_id": "CAM_01", "source": "video1.mp4", "track_id": 7, "timestamp": "2026-01-01T10:07:00"},
        {"camera_id": "CAM_01", "source": "video1.mp4", "track_id": 7, "timestamp": "2026-01-01T10:09:00"},
        {"camera_id": "CAM_01", "source": "video1.mp4", "track_id": 7, "timestamp": "2026-01-01T11:02:00"},
    ]
    result = hourly_density(observations)
    assert result["CAM_01"]["2026-01-01 10:00"] == 1
    assert result["CAM_01"]["2026-01-01 11:00"] == 1


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
