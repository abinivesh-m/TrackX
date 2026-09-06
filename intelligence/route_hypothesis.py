"""
route_hypothesis.py

Route hypothesis engine for TrackX.

Instead of simply matching observations pairwise, this module constructs
multiple possible route hypotheses for a vehicle and validates each one
based on:

- Chronological order consistency
- Temporal plausibility of each hop
- Spatial connectivity of the route
- Identity consistency across the route
- Overall route confidence

This transforms TrackX from a simple tracker into a reasoning system that
can explain WHY a particular route is accepted or rejected.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

from intelligence.spatio_temporal import (
    calculate_spatial_temporal_plausibility,
    analyze_transition_plausibility,
    SpatioTemporalResult
)
from intelligence.fusion import global_match_score
from network.camera_network import CAMERAS, ROAD_GRAPH, is_spatially_connected


class RouteHypothesis:
    """
    A complete route hypothesis with confidence scores and validation.
    
    Represents one possible interpretation of a vehicle's journey through
    the camera network, with full explainability.
    """
    
    def __init__(
        self,
        observation_sequence: List[Dict],
        plate_identity: str,
        global_id: int,
        hop_scores: List[float],
        hop_breakdowns: List[Dict],
        spatio_temporal_results: List[SpatioTemporalResult]
    ):
        self.observation_sequence = observation_sequence
        self.plate_identity = plate_identity
        self.global_id = global_id
        self.hop_scores = hop_scores
        self.hop_breakdowns = hop_breakdowns
        self.spatio_temporal_results = spatio_temporal_results
        
        # Calculate aggregate scores
        self.identity_confidence = self._calculate_identity_confidence()
        self.temporal_confidence = self._calculate_temporal_confidence()
        self.spatial_confidence = self._calculate_spatial_confidence()
        self.overall_confidence = self._calculate_overall_confidence()
        self.route_path = " -> ".join(obs["camera_id"] for obs in observation_sequence)
    
    def _calculate_identity_confidence(self) -> float:
        """Average identity confidence across all hops."""
        if not self.hop_scores:
            return 0.0
        return sum(self.hop_scores) / len(self.hop_scores)
    
    def _calculate_temporal_confidence(self) -> float:
        """Average temporal plausibility confidence across all hops."""
        if not self.spatio_temporal_results:
            return 0.0
        return sum(r.confidence for r in self.spatio_temporal_results) / len(self.spatio_temporal_results)
    
    def _calculate_spatial_confidence(self) -> float:
        """Check if all hops are spatially connected."""
        if not self.spatio_temporal_results:
            return 0.0
        connected_count = sum(1 for r in self.spatio_temporal_results if r.spatial_connected)
        return connected_count / len(self.spatio_temporal_results)
    
    def _calculate_overall_confidence(self) -> float:
        """Weighted combination of all confidence factors."""
        # Prioritize identity and temporal/spatial plausibility
        weights = {
            "identity": 0.5,
            "temporal": 0.25,
            "spatial": 0.25
        }
        return (
            weights["identity"] * self.identity_confidence +
            weights["temporal"] * self.temporal_confidence +
            weights["spatial"] * self.spatial_confidence
        )
    
    def get_status(self) -> str:
        """Get human-readable status of this hypothesis."""
        if self.overall_confidence >= 0.85:
            return "HIGH CONFIDENCE"
        elif self.overall_confidence >= 0.65:
            return "MEDIUM CONFIDENCE"
        elif self.overall_confidence >= 0.4:
            return "LOW CONFIDENCE"
        else:
            return "REJECTED"
    
    def get_rejection_reason(self) -> Optional[str]:
        """Get primary reason for rejection if confidence is low."""
        if self.overall_confidence >= 0.4:
            return None
        
        reasons = []
        
        # Check for impossible transitions
        impossible_hops = [
            i for i, r in enumerate(self.spatio_temporal_results)
            if not r.is_plausible
        ]
        if impossible_hops:
            cam_a = self.observation_sequence[impossible_hops[0]]["camera_id"]
            cam_b = self.observation_sequence[impossible_hops[0] + 1]["camera_id"]
            reasons.append(f"Impossible transition {cam_a} -> {cam_b}")
        
        # Check for spatial disconnects
        disconnected_hops = [
            i for i, r in enumerate(self.spatio_temporal_results)
            if not r.spatial_connected
        ]
        if disconnected_hops:
            cam_a = self.observation_sequence[disconnected_hops[0]]["camera_id"]
            cam_b = self.observation_sequence[disconnected_hops[0] + 1]["camera_id"]
            reasons.append(f"No road connection {cam_a} -> {cam_b}")
        
        # Check for low identity confidence
        if self.identity_confidence < 0.5:
            reasons.append(f"Low identity confidence ({self.identity_confidence:.2f})")
        
        # Check for low temporal confidence
        if self.temporal_confidence < 0.5:
            reasons.append(f"Low temporal plausibility ({self.temporal_confidence:.2f})")
        
        return "; ".join(reasons) if reasons else "Overall confidence too low"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization/UI display."""
        return {
            "global_id": self.global_id,
            "plate_identity": self.plate_identity,
            "route_path": self.route_path,
            "observation_count": len(self.observation_sequence),
            "identity_confidence": round(self.identity_confidence, 3),
            "temporal_confidence": round(self.temporal_confidence, 3),
            "spatial_confidence": round(self.spatial_confidence, 3),
            "overall_confidence": round(self.overall_confidence, 3),
            "status": self.get_status(),
            "rejection_reason": self.get_rejection_reason(),
            "hop_details": self._get_hop_details()
        }
    
    def _get_hop_details(self) -> List[Dict]:
        """Get detailed information for each hop in the route."""
        details = []
        for i in range(len(self.observation_sequence) - 1):
            obs_a = self.observation_sequence[i]
            obs_b = self.observation_sequence[i + 1]
            
            hop_detail = {
                "hop_index": i,
                "camera_a": obs_a["camera_id"],
                "camera_b": obs_b["camera_id"],
                "timestamp_a": obs_a["timestamp"],
                "timestamp_b": obs_b["timestamp"],
                "identity_score": round(self.hop_scores[i], 3) if i < len(self.hop_scores) else 0.0,
                "identity_breakdown": self.hop_breakdowns[i] if i < len(self.hop_breakdowns) else {},
                "spatio_temporal": self.spatio_temporal_results[i].to_dict() if i < len(self.spatio_temporal_results) else {}
            }
            details.append(hop_detail)
        
        return details


def generate_route_hypotheses(
    observations: List[Dict],
    global_id: int,
    max_hops: int = 10,
    speed_margin: float = 1.3
) -> List[RouteHypothesis]:
    """
    Generate and validate route hypotheses for a set of observations.
    
    This function creates multiple possible interpretations of how observations
    might be connected, then validates each one based on spatio-temporal
    plausibility and identity consistency.
    
    Args:
        observations: List of observation dicts (should be for same vehicle)
        global_id: Global vehicle ID for this hypothesis set
        max_hops: Maximum number of hops to consider in a route
        speed_margin: Speed margin multiplier for plausibility checking
    
    Returns:
        List of RouteHypothesis objects, sorted by overall confidence
    """
    if len(observations) < 2:
        # Single observation - trivial hypothesis
        return [RouteHypothesis(
            observation_sequence=observations,
            plate_identity=observations[0].get("plate_text", "UNKNOWN"),
            global_id=global_id,
            hop_scores=[],
            hop_breakdowns=[],
            spatio_temporal_results=[]
        )]
    
    # Sort observations by timestamp
    sorted_obs = sorted(observations, key=lambda o: o["timestamp"])
    
    # Generate single primary hypothesis (chronological sequence)
    # In a more sophisticated version, we could generate multiple permutations
    hypotheses = []
    
    # Build the primary chronological hypothesis
    hop_scores = []
    hop_breakdowns = []
    spatio_temporal_results = []
    
    for i in range(len(sorted_obs) - 1):
        obs_a = sorted_obs[i]
        obs_b = sorted_obs[i + 1]
        
        # Calculate identity score using existing fusion engine
        vec_a = _decode_appearance(obs_a)
        vec_b = _decode_appearance(obs_b)
        
        score, breakdown = global_match_score(obs_a, obs_b, vec_a, vec_b)
        hop_scores.append(score)
        hop_breakdowns.append(breakdown)
        
        # Calculate spatio-temporal plausibility
        st_result = analyze_transition_plausibility(obs_a, obs_b, speed_margin)
        spatio_temporal_results.append(st_result)
    
    primary_hypothesis = RouteHypothesis(
        observation_sequence=sorted_obs,
        plate_identity=sorted_obs[0].get("plate_text", "UNKNOWN"),
        global_id=global_id,
        hop_scores=hop_scores,
        hop_breakdowns=hop_breakdowns,
        spatio_temporal_results=spatio_temporal_results
    )
    
    hypotheses.append(primary_hypothesis)
    
    # Sort by overall confidence (highest first)
    hypotheses.sort(key=lambda h: h.overall_confidence, reverse=True)
    
    return hypotheses


def _decode_appearance(obs: Dict) -> Optional[List[float]]:
    """Decode appearance vector from observation dict."""
    raw = obs.get("appearance_vector")
    if not raw:
        return None
    try:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    except (TypeError, ValueError):
        return None


def analyze_route_alternatives(
    observations: List[Dict],
    global_id: int,
    speed_margin: float = 1.3
) -> Dict:
    """
    Analyze alternative route interpretations and return best explanation.
    
    This function provides the judge-ready explanation of why a particular
    route interpretation was chosen or rejected.
    
    Args:
        observations: List of observation dicts
        global_id: Global vehicle ID
        speed_margin: Speed margin multiplier
    
    Returns:
        Dict with analysis results including best hypothesis and alternatives
    """
    hypotheses = generate_route_hypotheses(observations, global_id, speed_margin=speed_margin)
    
    if not hypotheses:
        return {
            "status": "NO_VALID_ROUTE",
            "reason": "Could not generate any valid route hypotheses",
            "hypotheses": []
        }
    
    best_hypothesis = hypotheses[0]
    
    # Analyze if the best hypothesis is acceptable
    if best_hypothesis.overall_confidence >= 0.65:
        status = "ACCEPTED"
        explanation = f"Route accepted with {best_hypothesis.get_status()}"
    else:
        status = "REJECTED"
        explanation = f"Route rejected: {best_hypothesis.get_rejection_reason()}"
    
    return {
        "status": status,
        "explanation": explanation,
        "best_hypothesis": best_hypothesis.to_dict(),
        "alternative_count": len(hypotheses) - 1,
        "all_hypotheses": [h.to_dict() for h in hypotheses]
    }


def validate_trajectory_route(
    trajectory: Dict,
    speed_margin: float = 1.3
) -> Dict:
    """
    Validate an existing trajectory with route hypothesis analysis.
    
    This function extends the existing trajectory reconstruction with
    detailed route validation and explainability.
    
    Args:
        trajectory: Trajectory dict from intelligence.trajectory.build_trajectories
        speed_margin: Speed margin multiplier
    
    Returns:
        Dict with validation results and route analysis
    """
    observations = trajectory["observations"]
    global_id = trajectory["global_id"]
    
    analysis = analyze_route_alternatives(observations, global_id, speed_margin)
    
    return {
        "global_id": global_id,
        "plate_variations": list(set(o.get("plate_text", "UNKNOWN") for o in observations)),
        "camera_sequence": [o["camera_id"] for o in observations],
        "observation_count": len(observations),
        "route_analysis": analysis
    }


if __name__ == "__main__":
    # Test the route hypothesis engine
    from datetime import datetime, timedelta
    import numpy as np
    
    base_time = datetime(2026, 8, 24, 10, 0, 0)
    
    # Create test observations
    def _obs(plate, camera, ts, vec=None):
        return {
            "plate_text": plate,
            "camera_id": camera,
            "timestamp": ts.isoformat(),
            "lat": 0.0,
            "long": 0.0,
            "appearance_vector": json.dumps(vec) if vec else None,
        }
    
    # Test case 1: Valid route
    vec = np.random.RandomState(42).normal(size=64).tolist()
    obs1 = [
        _obs("TN10AB1234", "CAM_01", base_time, vec),
        _obs("TN10AB1234", "CAM_02", base_time + timedelta(seconds=170), vec),
        _obs("TN10AB1234", "CAM_03", base_time + timedelta(seconds=386), vec),
    ]
    
    hypotheses1 = generate_route_hypotheses(obs1, global_id=1)
    print("Test 1 - Valid route:")
    print(f"  Best hypothesis status: {hypotheses1[0].get_status()}")
    print(f"  Overall confidence: {hypotheses1[0].overall_confidence:.3f}")
    print(f"  Route: {hypotheses1[0].route_path}")
    print()
    
    # Test case 2: Impossible route
    obs2 = [
        _obs("TN99ZZ0000", "CAM_01", base_time, vec),
        _obs("TN99ZZ0000", "CAM_04", base_time + timedelta(seconds=30), vec),  # Too fast
    ]
    
    hypotheses2 = generate_route_hypotheses(obs2, global_id=2)
    print("Test 2 - Impossible route:")
    print(f"  Best hypothesis status: {hypotheses2[0].get_status()}")
    print(f"  Rejection reason: {hypotheses2[0].get_rejection_reason()}")
    print(f"  Overall confidence: {hypotheses2[0].overall_confidence:.3f}")
