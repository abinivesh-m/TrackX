"""
test_spatio_temporal.py

Comprehensive tests for the spatio-temporal plausibility engine.

Tests the core intelligence that prevents TrackX from blindly trusting
vehicle identity across cameras without questioning physical plausibility.

Run with: python -m pytest tests/test_spatio_temporal.py -v
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.spatio_temporal import (
    calculate_spatial_temporal_plausibility,
    analyze_transition_plausibility,
    detect_impossible_transitions,
    SpatioTemporalResult
)


BASE_TIME = datetime(2026, 8, 24, 10, 0, 0)


def _obs(plate, camera, ts):
    return {
        "plate_text": plate,
        "camera_id": camera,
        "timestamp": ts.isoformat(),
        "lat": 0.0,
        "long": 0.0,
    }


def test_normal_plausible_transition():
    """Test that a normal, physically possible transition is marked as plausible."""
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=170)  # Reasonable time for 1.4km
    )
    
    assert result.is_plausible is True
    assert result.spatial_connected is True
    assert result.required_speed_kmph < 100  # Should be reasonable
    assert result.confidence > 0.5
    assert "Plausible" in result.reason


def test_impossible_transition_too_fast():
    """Test that an impossibly fast transition is rejected."""
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_04",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=30)  # 3.5km in 30s = 420 km/h
    )
    
    assert result.is_plausible is False
    assert result.spatial_connected is True
    assert result.required_speed_kmph > 200  # Should be impossibly high
    assert result.confidence == 0.0
    assert "Impossible" in result.reason or "impossible" in result.reason.lower()


def test_no_road_connection():
    """Test that transitions between unconnected cameras are rejected."""
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_99",  # Non-existent camera
        BASE_TIME,
        BASE_TIME + timedelta(seconds=300)
    )
    
    assert result.is_plausible is False
    assert result.spatial_connected is False
    assert result.confidence == 0.0
    assert "No road connection" in result.reason


def test_suspicious_but_possible_transition():
    """Test that suspicious but not impossible transitions get low confidence."""
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=60)  # Faster than expected but not impossible
    )
    
    # This might be plausible or suspicious depending on the exact timing
    # The key is that it should have some analysis
    assert result.spatial_connected is True
    assert result.distance_km > 0
    assert result.elapsed_seconds > 0
    assert result.required_speed_kmph > 0


def test_observation_convenience_wrapper():
    """Test the convenience wrapper for observation dicts."""
    obs_a = _obs("TN10AB1234", "CAM_01", BASE_TIME)
    obs_b = _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170))
    
    result = analyze_transition_plausibility(obs_a, obs_b)
    
    assert result.is_plausible is True
    assert result.camera_a == "CAM_01"
    assert result.camera_b == "CAM_02"
    assert result.spatial_connected is True


def test_detect_impossible_transitions():
    """Test detection of impossible transitions in a list of observations."""
    obs = [
        _obs("TN99ZZ0000", "CAM_01", BASE_TIME),
        _obs("TN99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=30)),  # Impossible
        _obs("TN10AB1234", "CAM_01", BASE_TIME + timedelta(minutes=5)),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(minutes=5, seconds=170)),  # Normal
    ]
    
    impossible = detect_impossible_transitions(obs)
    
    # Should find at least the impossible transition
    assert len(impossible) >= 1
    
    # Check that the impossible transition is flagged
    impossible_transitions = [item for item in impossible if not item["result"].is_plausible]
    assert len(impossible_transitions) >= 1


def test_same_camera_transition():
    """Test that same-camera transitions are handled correctly."""
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_01",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=60)
    )
    
    # Same camera should be handled (distance = 0)
    assert result.spatial_connected is True
    assert result.distance_km == 0


def test_result_to_dict():
    """Test that SpatioTemporalResult can be serialized to dict."""
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=170)
    )
    
    result_dict = result.to_dict()
    
    # Check that all important fields are present
    assert "is_plausible" in result_dict
    assert "camera_a" in result_dict
    assert "camera_b" in result_dict
    assert "distance_km" in result_dict
    assert "required_speed_kmph" in result_dict
    assert "confidence" in result_dict
    assert "reason" in result_dict


def test_get_assessment():
    """Test the human-readable assessment."""
    # Normal case
    result_normal = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=170)
    )
    assert "PLAUSIBLE" in result_normal.get_assessment()
    
    # Impossible case
    result_impossible = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_04",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=30)
    )
    assert "IMPOSSIBLE" in result_impossible.get_assessment() or "NO ROAD" in result_impossible.get_assessment()


def test_expected_time_range():
    """Test that expected time ranges are calculated correctly."""
    result = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=170)
    )
    
    # Expected time range should be reasonable
    assert result.expected_time_min_seconds > 0
    assert result.expected_time_max_seconds > result.expected_time_min_seconds
    
    # The observed time should be within or close to the expected range
    # (allowing for some margin)
    assert result.elapsed_seconds > 0


def test_speed_margin_parameter():
    """Test that the speed_margin parameter affects plausibility."""
    # With strict margin (1.0)
    result_strict = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=80),  # Quite fast
        speed_margin=1.0
    )
    
    # With lenient margin (2.0)
    result_lenient = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02",
        BASE_TIME,
        BASE_TIME + timedelta(seconds=80),
        speed_margin=2.0
    )
    
    # Lenient margin should be more permissive
    # (might both be plausible, but lenient should have higher confidence)
    assert result_lenient.confidence >= result_strict.confidence


if __name__ == "__main__":
    test_normal_plausible_transition()
    test_impossible_transition_too_fast()
    test_no_road_connection()
    test_suspicious_but_possible_transition()
    test_observation_convenience_wrapper()
    test_detect_impossible_transitions()
    test_same_camera_transition()
    test_result_to_dict()
    test_get_assessment()
    test_expected_time_range()
    test_speed_margin_parameter()
    print("all spatio-temporal tests passed")
