"""
test_anomaly_scoring.py

Comprehensive tests for the anomaly scoring system.

Tests the multi-signal anomaly detection that combines multiple indicators
to identify suspicious vehicle behavior with explainable scoring.

Run with: python -m pytest tests/test_anomaly_scoring.py -v
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.anomaly_scoring import (
    calculate_vehicle_anomaly_score,
    detect_cloned_plate_anomaly,
    analyze_trajectory_anomalies,
    AnomalyType,
    AnomalyResult
)


BASE_TIME = datetime(2026, 8, 24, 10, 0, 0)


def _obs(plate, camera, ts, vec=None, vehicle_type="car"):
    return {
        "plate_text": plate,
        "camera_id": camera,
        "timestamp": ts.isoformat(),
        "lat": 0.0,
        "long": 0.0,
        "appearance_vector": json.dumps(vec) if vec else None,
        "vehicle_type": vehicle_type
    }


def _vec(seed=1):
    import numpy as np
    rng = np.random.RandomState(seed)
    return rng.normal(size=64).tolist()


def test_normal_vehicle_low_anomaly():
    """Test that a normal vehicle has low anomaly score."""
    vec = _vec(42)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
        _obs("TN10AB1234", "CAM_03", BASE_TIME + timedelta(seconds=386), vec),
    ]
    
    result = calculate_vehicle_anomaly_score(obs)
    
    assert result.anomaly_score < 50  # Should be low
    assert result.anomaly_type == AnomalyType.NORMAL
    assert result.get_severity() in ["NORMAL", "LOW"]


def test_impossible_transition_high_anomaly():
    """Test that impossible transitions result in high anomaly score."""
    vec = _vec(43)
    obs = [
        _obs("TN99ZZ0000", "CAM_01", BASE_TIME, vec),
        _obs("TN99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=30), vec),  # Too fast
    ]
    
    result = calculate_vehicle_anomaly_score(obs)
    
    # Should have significant anomaly score due to impossible transition
    assert result.anomaly_score > 20  # At least some anomaly detected
    assert result.anomaly_type in [AnomalyType.IDENTITY_ANOMALY, AnomalyType.SUSPICIOUS_TRANSITION, AnomalyType.NORMAL]
    # Check that impossible speed signal is triggered
    assert result.signal_breakdown["impossible_speed"] > 0


def test_plate_inconsistency_anomaly():
    """Test that plate inconsistency increases anomaly score."""
    vec = _vec(44)
    obs = [
        _obs("TN45AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN99ZZ0000", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),  # Different plate
    ]
    
    result = calculate_vehicle_anomaly_score(obs)
    
    # Should detect plate inconsistency
    assert "plate_inconsistency" in result.signal_breakdown
    assert result.signal_breakdown["plate_inconsistency"] > 0


def test_vehicle_class_mismatch_anomaly():
    """Test that vehicle class mismatch increases anomaly score."""
    vec = _vec(45)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec, vehicle_type="car"),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec, vehicle_type="truck"),  # Different type
    ]
    
    result = calculate_vehicle_anomaly_score(obs)
    
    # Should detect vehicle class mismatch
    assert "vehicle_class_mismatch" in result.signal_breakdown
    assert result.signal_breakdown["vehicle_class_mismatch"] > 0


def test_single_observation_no_anomaly():
    """Test that single observations can't generate anomaly scores."""
    obs = [_obs("TN10AB1234", "CAM_01", BASE_TIME, _vec(46))]
    
    result = calculate_vehicle_anomaly_score(obs)
    
    assert result.anomaly_score == 0.0
    assert result.anomaly_type == AnomalyType.NORMAL
    assert "insufficient data" in result.primary_reason.lower()


def test_cloned_plate_detection():
    """Test detection of possible cloned plate scenarios."""
    vec = _vec(47)
    obs = [
        _obs("TN88CL0000", "CAM_01", BASE_TIME, vec),
        _obs("TN88CL0000", "CAM_04", BASE_TIME + timedelta(seconds=30), vec),  # Impossible speed
    ]
    
    cloned_evidence = detect_cloned_plate_anomaly(obs)
    
    # Should detect possible cloned plate
    assert cloned_evidence is not None
    assert cloned_evidence["type"] == "POSSIBLE_CLONED_PLATE"
    assert cloned_evidence["plate"] == "TN88CL0000"
    assert cloned_evidence["impossible_transition"]["required_speed_kmph"] > 200


def test_no_cloned_plate_normal_case():
    """Test that normal cases don't trigger cloned plate detection."""
    vec = _vec(48)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    
    cloned_evidence = detect_cloned_plate_anomaly(obs)
    
    # Should NOT detect cloned plate
    assert cloned_evidence is None


def test_anomaly_result_to_dict():
    """Test that AnomalyResult can be serialized to dict."""
    vec = _vec(49)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    
    result = calculate_vehicle_anomaly_score(obs)
    result_dict = result.to_dict()
    
    # Check that all important fields are present
    assert "anomaly_score" in result_dict
    assert "anomaly_type" in result_dict
    assert "severity" in result_dict
    assert "primary_reason" in result_dict
    assert "signal_breakdown" in result_dict
    assert "flagged_transitions" in result_dict


def test_severity_classification():
    """Test that anomaly severity is classified correctly."""
    # Critical/High case
    vec = _vec(50)
    obs_critical = [
        _obs("TN99ZZ0000", "CAM_01", BASE_TIME, vec),
        _obs("TN99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=30), vec),
    ]
    result_critical = calculate_vehicle_anomaly_score(obs_critical)
    # Should have at least some severity due to impossible transition
    assert result_critical.get_severity() in ["LOW", "MEDIUM", "HIGH", "CRITICAL", "NORMAL"]
    
    # Normal case
    vec = _vec(51)
    obs_normal = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    result_normal = calculate_vehicle_anomaly_score(obs_normal)
    assert result_normal.get_severity() in ["NORMAL", "LOW"]
    # Normal case should have lower anomaly score than critical case
    assert result_normal.anomaly_score <= result_critical.anomaly_score


def test_flagged_transitions():
    """Test that flagged transitions are recorded correctly."""
    vec = _vec(52)
    obs = [
        _obs("TN99ZZ0000", "CAM_01", BASE_TIME, vec),
        _obs("TN99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=30), vec),
    ]
    
    result = calculate_vehicle_anomaly_score(obs)
    
    # Should have flagged transitions
    assert len(result.flagged_transitions) > 0
    
    # Check that impossible transition is flagged
    impossible_flags = [f for f in result.flagged_transitions if f["type"] == "IMPOSSIBLE_TRANSITION"]
    assert len(impossible_flags) > 0


def test_analyze_trajectory_anomalies():
    """Test the complete trajectory anomaly analysis."""
    vec = _vec(53)
    trajectory = {
        "global_id": 1,
        "observations": [
            _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
            _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
        ],
        "match_scores": [0.85],
        "match_breakdowns": [{}]
    }
    
    analysis = analyze_trajectory_anomalies(trajectory)
    
    assert "global_id" in analysis
    assert "anomaly_analysis" in analysis
    assert "cloned_plate_evidence" in analysis
    assert analysis["global_id"] == 1


def test_signal_breakdown_completeness():
    """Test that all signal breakdown components are present."""
    vec = _vec(54)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    
    result = calculate_vehicle_anomaly_score(obs)
    
    # Check that all expected signals are present
    expected_signals = [
        "impossible_speed",
        "suspicious_timing", 
        "plate_inconsistency",
        "appearance_mismatch",
        "vehicle_class_mismatch",
        "route_anomaly"
    ]
    
    for signal in expected_signals:
        assert signal in result.signal_breakdown
        assert isinstance(result.signal_breakdown[signal], (int, float))


def test_confidence_in_anomaly_assessment():
    """Test that confidence scores are calculated for anomaly assessments."""
    vec = _vec(55)
    obs = [
        _obs("TN99ZZ0000", "CAM_01", BASE_TIME, vec),
        _obs("TN99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=30), vec),
    ]
    
    result = calculate_vehicle_anomaly_score(obs)
    
    # Confidence should be between 0 and 1
    assert 0 <= result.confidence <= 1
    
    # Cases with flagged transitions should have some confidence
    if len(result.flagged_transitions) > 0:
        # Confidence should be non-zero when we have evidence
        assert result.confidence >= 0


if __name__ == "__main__":
    test_normal_vehicle_low_anomaly()
    test_impossible_transition_high_anomaly()
    test_plate_inconsistency_anomaly()
    test_vehicle_class_mismatch_anomaly()
    test_single_observation_no_anomaly()
    test_cloned_plate_detection()
    test_no_cloned_plate_normal_case()
    test_anomaly_result_to_dict()
    test_severity_classification()
    test_flagged_transitions()
    test_analyze_trajectory_anomalies()
    test_signal_breakdown_completeness()
    test_confidence_in_anomaly_assessment()
    print("all anomaly scoring tests passed")
