"""
test_route_hypothesis.py

Comprehensive tests for the route hypothesis engine.

Tests the ability of TrackX to construct and validate multiple possible
route interpretations, transforming it from a simple tracker into a
reasoning system.

Run with: python -m pytest tests/test_route_hypothesis.py -v
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.route_hypothesis import (
    generate_route_hypotheses,
    analyze_route_alternatives,
    validate_trajectory_route,
    RouteHypothesis
)


BASE_TIME = datetime(2026, 8, 24, 10, 0, 0)


def _obs(plate, camera, ts, vec=None):
    return {
        "plate_text": plate,
        "camera_id": camera,
        "timestamp": ts.isoformat(),
        "lat": 0.0,
        "long": 0.0,
        "appearance_vector": json.dumps(vec) if vec else None,
    }


def _vec(seed=1):
    import numpy as np
    rng = np.random.RandomState(seed)
    return rng.normal(size=64).tolist()


def test_single_observation_hypothesis():
    """Test that a single observation creates a trivial hypothesis."""
    obs = [_obs("TN10AB1234", "CAM_01", BASE_TIME, _vec(1))]
    
    hypotheses = generate_route_hypotheses(obs, global_id=1)
    
    assert len(hypotheses) == 1
    assert len(hypotheses[0].observation_sequence) == 1
    assert hypotheses[0].plate_identity == "TN10AB1234"
    assert hypotheses[0].route_path == "CAM_01"


def test_valid_route_hypothesis():
    """Test that a valid multi-camera route gets high confidence."""
    vec = _vec(42)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
        _obs("TN10AB1234", "CAM_03", BASE_TIME + timedelta(seconds=386), vec),
    ]
    
    hypotheses = generate_route_hypotheses(obs, global_id=1)
    
    assert len(hypotheses) >= 1
    best = hypotheses[0]
    
    assert len(best.observation_sequence) == 3
    assert "CAM_01" in best.route_path
    assert "CAM_02" in best.route_path
    assert "CAM_03" in best.route_path
    assert best.overall_confidence > 0.5  # Should be reasonably confident


def test_impossible_route_hypothesis():
    """Test that an impossible route gets rejected or low confidence."""
    vec = _vec(43)
    obs = [
        _obs("TN99ZZ0000", "CAM_01", BASE_TIME, vec),
        _obs("TN99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=30), vec),  # Too fast
    ]
    
    hypotheses = generate_route_hypotheses(obs, global_id=2)
    
    assert len(hypotheses) >= 1
    best = hypotheses[0]
    
    # Should have low confidence due to impossible transition
    assert best.overall_confidence < 0.5
    assert best.get_status() in ["LOW CONFIDENCE", "REJECTED"]


def test_hypothesis_status_classification():
    """Test that hypothesis status is classified correctly."""
    # High confidence
    vec = _vec(44)
    obs_high = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    hypotheses_high = generate_route_hypotheses(obs_high, global_id=3)
    assert hypotheses_high[0].get_status() in ["HIGH CONFIDENCE", "MEDIUM CONFIDENCE"]
    
    # Low confidence
    vec = _vec(45)
    obs_low = [
        _obs("TN99ZZ0000", "CAM_01", BASE_TIME, vec),
        _obs("TN99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=30), vec),
    ]
    hypotheses_low = generate_route_hypotheses(obs_low, global_id=4)
    assert hypotheses_low[0].get_status() in ["LOW CONFIDidence", "REJECTED"]


def test_rejection_reason():
    """Test that rejection reasons are provided for low-confidence hypotheses."""
    vec = _vec(46)
    obs = [
        _obs("TN99ZZ0000", "CAM_01", BASE_TIME, vec),
        _obs("TN99ZZ0000", "CAM_04", BASE_TIME + timedelta(seconds=30), vec),
    ]
    
    hypotheses = generate_route_hypotheses(obs, global_id=5)
    best = hypotheses[0]
    
    if best.overall_confidence < 0.4:
        reason = best.get_rejection_reason()
        assert reason is not None
        assert len(reason) > 0


def test_hypothesis_to_dict():
    """Test that RouteHypothesis can be serialized to dict."""
    vec = _vec(47)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    
    hypotheses = generate_route_hypotheses(obs, global_id=6)
    hypothesis_dict = hypotheses[0].to_dict()
    
    # Check that all important fields are present
    assert "global_id" in hypothesis_dict
    assert "plate_identity" in hypothesis_dict
    assert "route_path" in hypothesis_dict
    assert "observation_count" in hypothesis_dict
    assert "identity_confidence" in hypothesis_dict
    assert "temporal_confidence" in hypothesis_dict
    assert "spatial_confidence" in hypothesis_dict
    assert "overall_confidence" in hypothesis_dict
    assert "status" in hypothesis_dict


def test_hop_details():
    """Test that hop details are generated correctly."""
    vec = _vec(48)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
        _obs("TN10AB1234", "CAM_03", BASE_TIME + timedelta(seconds=386), vec),
    ]
    
    hypotheses = generate_route_hypotheses(obs, global_id=7)
    hop_details = hypotheses[0].to_dict()["hop_details"]
    
    # Should have 2 hops for 3 observations
    assert len(hop_details) == 2
    
    # Check first hop
    assert hop_details[0]["camera_a"] == "CAM_01"
    assert hop_details[0]["camera_b"] == "CAM_02"
    assert "identity_score" in hop_details[0]
    assert "spatio_temporal" in hop_details[0]


def test_analyze_route_alternatives():
    """Test the route alternatives analysis function."""
    vec = _vec(49)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    
    analysis = analyze_route_alternatives(obs, global_id=8)
    
    assert "status" in analysis
    assert "explanation" in analysis
    assert "best_hypothesis" in analysis
    assert analysis["status"] in ["ACCEPTED", "REJECTED", "NO_VALID_ROUTE"]


def test_validate_trajectory_route():
    """Test validation of existing trajectory dicts."""
    vec = _vec(50)
    trajectory = {
        "global_id": 9,
        "observations": [
            _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
            _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
        ],
        "match_scores": [0.85],
        "match_breakdowns": [{}]
    }
    
    validation = validate_trajectory_route(trajectory)
    
    assert "global_id" in validation
    assert "route_analysis" in validation
    assert validation["global_id"] == 9


def test_confidence_calculation():
    """Test that confidence scores are calculated correctly."""
    vec = _vec(51)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    
    hypotheses = generate_route_hypotheses(obs, global_id=10)
    best = hypotheses[0]
    
    # All confidence scores should be between 0 and 1
    assert 0 <= best.identity_confidence <= 1
    assert 0 <= best.temporal_confidence <= 1
    assert 0 <= best.spatial_confidence <= 1
    assert 0 <= best.overall_confidence <= 1


def test_hypotheses_sorted_by_confidence():
    """Test that hypotheses are returned sorted by confidence (highest first)."""
    vec = _vec(52)
    obs = [
        _obs("TN10AB1234", "CAM_01", BASE_TIME, vec),
        _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(seconds=170), vec),
    ]
    
    hypotheses = generate_route_hypotheses(obs, global_id=11)
    
    # Check that they're sorted by confidence
    if len(hypotheses) > 1:
        for i in range(len(hypotheses) - 1):
            assert hypotheses[i].overall_confidence >= hypotheses[i + 1].overall_confidence


if __name__ == "__main__":
    test_single_observation_hypothesis()
    test_valid_route_hypothesis()
    test_impossible_route_hypothesis()
    test_hypothesis_status_classification()
    test_rejection_reason()
    test_hypothesis_to_dict()
    test_hop_details()
    test_analyze_route_alternatives()
    test_validate_trajectory_route()
    test_confidence_calculation()
    test_hypotheses_sorted_by_confidence()
    print("all route hypothesis tests passed")
