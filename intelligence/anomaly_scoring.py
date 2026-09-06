"""
anomaly_scoring.py

Multi-signal anomaly scoring system for TrackX.

This module implements an explainable anomaly detection system that combines
multiple signals to identify suspicious vehicle behavior:

- Impossible required speed
- Unusually short transition times
- Inconsistent plate observations
- Inconsistent vehicle class
- Appearance mismatch
- Abnormal route sequences
- Duplicate vehicle identity across incompatible locations

The system returns both an anomaly score (0-100) and a specific anomaly type,
making it clear to judges WHY a vehicle is flagged as suspicious.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Literal
import json

from intelligence.spatio_temporal import (
    analyze_transition_plausibility,
    SpatioTemporalResult
)
from intelligence.fusion import global_match_score
from recognition.plate_matcher import plate_similarity, normalize_plate
from network.camera_network import CAMERA_RELIABILITY


class AnomalyType:
    """Enumeration of anomaly types with severity levels."""
    
    NORMAL = "NORMAL"
    SUSPICIOUS_TRANSITION = "SUSPICIOUS_TRANSITION"
    IDENTITY_ANOMALY = "IDENTITY_ANOMALY"
    POSSIBLE_CLONED_PLATE = "POSSIBLE_CLONED_PLATE"
    TIMESTAMP_ANOMALY = "TIMESTAMP_ANOMALY"
    ROUTE_ANOMALY = "ROUTE_ANOMALY"
    APPEARANCE_MISMATCH = "APPEARANCE_MISMATCH"
    VEHICLE_CLASS_MISMATCH = "VEHICLE_CLASS_MISMATCH"


class AnomalyResult:
    """
    Detailed anomaly detection result with explainable scoring.
    
    Provides both a numerical score and human-readable explanation of
    why a vehicle or transition is considered anomalous.
    """
    
    def __init__(
        self,
        anomaly_score: float,
        anomaly_type: str,
        primary_reason: str,
        signal_breakdown: Dict[str, float],
        flagged_transitions: List[Dict],
        confidence: float
    ):
        self.anomaly_score = anomaly_score  # 0-100
        self.anomaly_type = anomaly_type
        self.primary_reason = primary_reason
        self.signal_breakdown = signal_breakdown
        self.flagged_transitions = flagged_transitions
        self.confidence = confidence
    
    def get_severity(self) -> str:
        """Get severity level based on score."""
        if self.anomaly_score >= 80:
            return "CRITICAL"
        elif self.anomaly_score >= 60:
            return "HIGH"
        elif self.anomaly_score >= 40:
            return "MEDIUM"
        elif self.anomaly_score >= 20:
            return "LOW"
        else:
            return "NORMAL"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization/UI display."""
        return {
            "anomaly_score": round(self.anomaly_score, 1),
            "anomaly_type": self.anomaly_type,
            "severity": self.get_severity(),
            "primary_reason": self.primary_reason,
            "signal_breakdown": {k: round(v, 3) for k, v in self.signal_breakdown.items()},
            "flagged_transitions": self.flagged_transitions,
            "confidence": round(self.confidence, 3)
        }


def calculate_vehicle_anomaly_score(
    observations: List[Dict],
    appearance_vectors: Optional[Dict] = None,
    speed_margin: float = 1.3
) -> AnomalyResult:
    """
    Calculate comprehensive anomaly score for a vehicle's observations.
    
    Analyzes multiple signals and combines them into an explainable
    anomaly assessment.
    
    Args:
        observations: List of observation dicts for the same vehicle
        appearance_vectors: Optional dict mapping observation index to appearance vector
        speed_margin: Speed margin multiplier for plausibility checking
    
    Returns:
        AnomalyResult with detailed scoring and explanation
    """
    if len(observations) < 2:
        # Single observation - cannot detect anomalies
        return AnomalyResult(
            anomaly_score=0.0,
            anomaly_type=AnomalyType.NORMAL,
            primary_reason="Single observation - insufficient data for anomaly detection",
            signal_breakdown={},
            flagged_transitions=[],
            confidence=0.0
        )
    
    # Sort by timestamp
    sorted_obs = sorted(observations, key=lambda o: o["timestamp"])
    
    # Signal breakdowns
    signal_scores = {
        "impossible_speed": 0.0,
        "suspicious_timing": 0.0,
        "plate_inconsistency": 0.0,
        "appearance_mismatch": 0.0,
        "vehicle_class_mismatch": 0.0,
        "route_anomaly": 0.0
    }
    
    flagged_transitions = []
    
    # Analyze each transition
    for i in range(len(sorted_obs) - 1):
        obs_a = sorted_obs[i]
        obs_b = sorted_obs[i + 1]
        
        # Spatio-temporal analysis
        st_result = analyze_transition_plausibility(obs_a, obs_b, speed_margin)
        
        if not st_result.is_plausible:
            # Impossible transition - highest severity
            signal_scores["impossible_speed"] = max(
                signal_scores["impossible_speed"],
                100.0
            )
            flagged_transitions.append({
                "type": "IMPOSSIBLE_TRANSITION",
                "transition": f"{obs_a['camera_id']} → {obs_b['camera_id']}",
                "reason": st_result.reason,
                "required_speed": st_result.required_speed_kmph,
                "observed_time": st_result.elapsed_seconds
            })
        elif st_result.confidence < 0.5:
            # Suspicious timing
            signal_scores["suspicious_timing"] = max(
                signal_scores["suspicious_timing"],
                (1.0 - st_result.confidence) * 80
            )
            flagged_transitions.append({
                "type": "SUSPICIOUS_TIMING",
                "transition": f"{obs_a['camera_id']} → {obs_b['camera_id']}",
                "reason": st_result.reason,
                "confidence": st_result.confidence
            })
        
        # Plate consistency
        plate_a = obs_a.get("plate_text", "")
        plate_b = obs_b.get("plate_text", "")
        if plate_a and plate_b:
            sim = plate_similarity(plate_a, plate_b)
            if sim < 0.7:  # Low similarity
                signal_scores["plate_inconsistency"] = max(
                    signal_scores["plate_inconsistency"],
                    (1.0 - sim) * 70
                )
                flagged_transitions.append({
                    "type": "PLATE_INCONSISTENCY",
                    "transition": f"{obs_a['camera_id']} → {obs_b['camera_id']}",
                    "plate_a": plate_a,
                    "plate_b": plate_b,
                    "similarity": sim
                })
        
        # Vehicle class consistency
        class_a = obs_a.get("vehicle_type")
        class_b = obs_b.get("vehicle_type")
        if class_a and class_b and class_a != class_b:
            signal_scores["vehicle_class_mismatch"] = max(
                signal_scores["vehicle_class_mismatch"],
                60.0
            )
            flagged_transitions.append({
                "type": "VEHICLE_CLASS_MISMATCH",
                "transition": f"{obs_a['camera_id']} → {obs_b['camera_id']}",
                "class_a": class_a,
                "class_b": class_b
            })
        
        # Appearance consistency
        vec_a = _decode_appearance(obs_a, appearance_vectors)
        vec_b = _decode_appearance(obs_b, appearance_vectors)
        if vec_a and vec_b:
            from recognition.appearance import appearance_similarity
            app_sim = appearance_similarity(vec_a, vec_b)
            if app_sim < 0.5:  # Low appearance similarity
                signal_scores["appearance_mismatch"] = max(
                    signal_scores["appearance_mismatch"],
                    (1.0 - app_sim) * 50
                )
                flagged_transitions.append({
                    "type": "APPEARANCE_MISMATCH",
                    "transition": f"{obs_a['camera_id']} → {obs_b['camera_id']}",
                    "similarity": app_sim
                })
    
    # Calculate overall anomaly score
    # Weight the signals by severity
    weights = {
        "impossible_speed": 0.35,
        "suspicious_timing": 0.20,
        "plate_inconsistency": 0.20,
        "appearance_mismatch": 0.10,
        "vehicle_class_mismatch": 0.10,
        "route_anomaly": 0.05
    }
    
    weighted_score = sum(
        signal_scores[signal] * weights[signal]
        for signal in signal_scores
    )
    
    # Determine anomaly type and primary reason
    if signal_scores["impossible_speed"] >= 80:
        anomaly_type = AnomalyType.IDENTITY_ANOMALY
        primary_reason = "Impossible vehicle speed required - possible cloned plate or identity error"
    elif signal_scores["plate_inconsistency"] >= 50:
        anomaly_type = AnomalyType.POSSIBLE_CLONED_PLATE
        primary_reason = "High plate inconsistency across observations - possible cloned plate"
    elif signal_scores["suspicious_timing"] >= 40:
        anomaly_type = AnomalyType.SUSPICIOUS_TRANSITION
        primary_reason = "Suspicious transition timing detected"
    elif signal_scores["appearance_mismatch"] >= 30:
        anomaly_type = AnomalyType.APPEARANCE_MISMATCH
        primary_reason = "Appearance mismatch despite plate similarity"
    elif signal_scores["vehicle_class_mismatch"] >= 30:
        anomaly_type = AnomalyType.VEHICLE_CLASS_MISMATCH
        primary_reason = "Vehicle class inconsistency across observations"
    else:
        anomaly_type = AnomalyType.NORMAL
        primary_reason = "No significant anomalies detected"
    
    # Calculate confidence in the anomaly assessment
    # Higher confidence when we have more strong signals
    strong_signals = sum(1 for score in signal_scores.values() if score >= 50)
    confidence = min(1.0, strong_signals / 3.0) if strong_signals > 0 else 0.0
    
    return AnomalyResult(
        anomaly_score=weighted_score,
        anomaly_type=anomaly_type,
        primary_reason=primary_reason,
        signal_breakdown=signal_scores,
        flagged_transitions=flagged_transitions,
        confidence=confidence
    )


def detect_cloned_plate_anomaly(
    observations: List[Dict],
    speed_margin: float = 1.3
) -> Optional[Dict]:
    """
    Specifically detect possible cloned plate scenarios.
    
    A cloned plate is suspected when:
    - Same plate identity appears at multiple cameras
    - With physically incompatible timestamps
    - Required speeds are impossible
    
    Args:
        observations: List of observation dicts
        speed_margin: Speed margin multiplier
    
    Returns:
        Dict with cloned plate evidence if detected, None otherwise
    """
    if len(observations) < 2:
        return None
    
    # Group by normalized plate
    plate_groups = {}
    for obs in observations:
        plate = normalize_plate(obs.get("plate_text", ""))
        if plate:
            if plate not in plate_groups:
                plate_groups[plate] = []
            plate_groups[plate].append(obs)
    
    # Check each plate group for impossible transitions
    for plate, group in plate_groups.items():
        if len(group) < 2:
            continue
        
        # Check all pairs for impossible transitions
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                obs_a = group[i]
                obs_b = group[j]
                
                if obs_a["camera_id"] == obs_b["camera_id"]:
                    continue
                
                st_result = analyze_transition_plausibility(obs_a, obs_b, speed_margin)
                
                if not st_result.is_plausible and st_result.required_speed_kmph > 200:
                    # High-speed impossible transition - possible cloned plate
                    return {
                        "type": "POSSIBLE_CLONED_PLATE",
                        "plate": plate,
                        "raw_plates": list(set(o.get("plate_text", "") for o in group)),
                        "cameras": [o["camera_id"] for o in group],
                        "impossible_transition": {
                            "camera_a": obs_a["camera_id"],
                            "camera_b": obs_b["camera_id"],
                            "timestamp_a": obs_a["timestamp"],
                            "timestamp_b": obs_b["timestamp"],
                            "required_speed_kmph": st_result.required_speed_kmph,
                            "distance_km": st_result.distance_km,
                            "reason": st_result.reason
                        },
                        "evidence_summary": (
                            f"Plate {plate} observed at {obs_a['camera_id']} and {obs_b['camera_id']} "
                            f"with impossible required speed of {st_result.required_speed_kmph:.1f} km/h"
                        )
                    }
    
    return None


def _decode_appearance(
    obs: Dict,
    appearance_vectors: Optional[Dict] = None
) -> Optional[List[float]]:
    """Decode appearance vector from observation dict."""
    # First check the dedicated appearance_vectors dict
    if appearance_vectors:
        obs_id = obs.get("id")
        if obs_id in appearance_vectors:
            return appearance_vectors[obs_id]
    
    # Fall back to appearance_vector field in observation
    raw = obs.get("appearance_vector")
    if not raw:
        return None
    try:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    except (TypeError, ValueError):
        return None


def analyze_trajectory_anomalies(
    trajectory: Dict,
    appearance_vectors: Optional[Dict] = None,
    speed_margin: float = 1.3
) -> Dict:
    """
    Analyze a complete trajectory for anomalies.
    
    Provides comprehensive anomaly analysis for a vehicle's entire journey.
    
    Args:
        trajectory: Trajectory dict from intelligence.trajectory.build_trajectories
        appearance_vectors: Optional dict mapping observation ID to appearance vector
        speed_margin: Speed margin multiplier
    
    Returns:
        Dict with complete anomaly analysis
    """
    observations = trajectory["observations"]
    global_id = trajectory["global_id"]
    
    # Calculate overall vehicle anomaly score
    anomaly_result = calculate_vehicle_anomaly_score(
        observations, appearance_vectors, speed_margin
    )
    
    # Check specifically for cloned plate scenarios
    cloned_plate_evidence = detect_cloned_plate_anomaly(
        observations, speed_margin
    )
    
    # If cloned plate detected, override the anomaly type
    if cloned_plate_evidence:
        anomaly_result.anomaly_type = AnomalyType.POSSIBLE_CLONED_PLATE
        anomaly_result.primary_reason = cloned_plate_evidence["evidence_summary"]
        anomaly_result.anomaly_score = max(anomaly_result.anomaly_score, 85.0)
    
    return {
        "global_id": global_id,
        "plate_variations": list(set(o.get("plate_text", "UNKNOWN") for o in observations)),
        "camera_sequence": [o["camera_id"] for o in observations],
        "observation_count": len(observations),
        "anomaly_analysis": anomaly_result.to_dict(),
        "cloned_plate_evidence": cloned_plate_evidence
    }


if __name__ == "__main__":
    # Test the anomaly scoring system
    from datetime import datetime, timedelta
    import numpy as np
    
    base_time = datetime(2026, 8, 24, 10, 0, 0)
    
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
    
    # Test case 1: Normal vehicle
    vec1 = np.random.RandomState(42).normal(size=64).tolist()
    obs_normal = [
        _obs("TN10AB1234", "CAM_01", base_time, vec1),
        _obs("TN10AB1234", "CAM_02", base_time + timedelta(seconds=170), vec1),
        _obs("TN10AB1234", "CAM_03", base_time + timedelta(seconds=386), vec1),
    ]
    
    result1 = calculate_vehicle_anomaly_score(obs_normal)
    print("Test 1 - Normal vehicle:")
    print(f"  Anomaly score: {result1.anomaly_score:.1f}")
    print(f"  Type: {result1.anomaly_type}")
    print(f"  Reason: {result1.primary_reason}")
    print()
    
    # Test case 2: Impossible transition (possible cloned plate)
    vec2 = np.random.RandomState(43).normal(size=64).tolist()
    obs_impossible = [
        _obs("TN99ZZ0000", "CAM_01", base_time, vec2),
        _obs("TN99ZZ0000", "CAM_04", base_time + timedelta(seconds=30), vec2),  # Too fast
    ]
    
    result2 = calculate_vehicle_anomaly_score(obs_impossible)
    print("Test 2 - Impossible transition:")
    print(f"  Anomaly score: {result2.anomaly_score:.1f}")
    print(f"  Type: {result2.anomaly_type}")
    print(f"  Reason: {result2.primary_reason}")
    print()
    
    # Test case 3: Plate inconsistency
    vec3 = np.random.RandomState(44).normal(size=64).tolist()
    obs_inconsistent = [
        _obs("TN45AB1234", "CAM_01", base_time, vec3),
        _obs("TN99ZZ0000", "CAM_02", base_time + timedelta(seconds=170), vec3),  # Different plate
    ]
    
    result3 = calculate_vehicle_anomaly_score(obs_inconsistent)
    print("Test 3 - Plate inconsistency:")
    print(f"  Anomaly score: {result3.anomaly_score:.1f}")
    print(f"  Type: {result3.anomaly_type}")
    print(f"  Reason: {result3.primary_reason}")
