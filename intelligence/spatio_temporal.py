"""
spatio_temporal.py

Spatio-temporal plausibility engine for TrackX.

This module extends the existing temporal feasibility checks with detailed
analysis of whether a vehicle transition is physically possible. Instead of
just returning a binary feasible/not-feasible, it provides explainable
reasoning about:

- Required travel speed
- Expected travel time range  
- Whether the transition is impossible
- Specific reasons for rejection

This is the core intelligence that prevents TrackX from blindly trusting
vehicle identity across cameras without questioning physical plausibility.
"""

from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Literal
import math

from network.camera_network import (
    CAMERAS, 
    ROAD_GRAPH, 
    _get_edge, 
    haversine_km,
    is_spatially_connected,
    is_temporally_feasible
)


class SpatioTemporalResult:
    """
    Detailed result of spatio-temporal plausibility analysis.
    
    Provides explainable reasoning about whether a vehicle transition
    between cameras is physically possible.
    """
    
    def __init__(
        self,
        is_plausible: bool,
        camera_a: str,
        camera_b: str,
        timestamp_a: datetime,
        timestamp_b: datetime,
        distance_km: float,
        elapsed_seconds: float,
        required_speed_kmph: float,
        expected_time_min_seconds: float,
        expected_time_max_seconds: float,
        spatial_connected: bool,
        road_edge: Optional[Dict],
        reason: str,
        confidence: float
    ):
        self.is_plausible = is_plausible
        self.camera_a = camera_a
        self.camera_b = camera_b
        self.timestamp_a = timestamp_a
        self.timestamp_b = timestamp_b
        self.distance_km = distance_km
        self.elapsed_seconds = elapsed_seconds
        self.required_speed_kmph = required_speed_kmph
        self.expected_time_min_seconds = expected_time_min_seconds
        self.expected_time_max_seconds = expected_time_max_seconds
        self.spatial_connected = spatial_connected
        self.road_edge = road_edge
        self.reason = reason
        self.confidence = confidence
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization/UI display."""
        return {
            "is_plausible": self.is_plausible,
            "camera_a": self.camera_a,
            "camera_b": self.camera_b,
            "timestamp_a": self.timestamp_a.isoformat(),
            "timestamp_b": self.timestamp_b.isoformat(),
            "distance_km": round(self.distance_km, 3),
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "required_speed_kmph": round(self.required_speed_kmph, 1),
            "expected_time_min_seconds": round(self.expected_time_min_seconds, 1),
            "expected_time_max_seconds": round(self.expected_time_max_seconds, 1),
            "spatial_connected": self.spatial_connected,
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
            "expected_time_range": self._format_time_range(),
            "elapsed_time_formatted": self._format_elapsed_time()
        }
    
    def _format_time_range(self) -> str:
        """Format expected time range for display."""
        if self.expected_time_min_seconds == self.expected_time_max_seconds:
            return f"{self.expected_time_min_seconds:.1f}s"
        return f"{self.expected_time_min_seconds:.1f}s–{self.expected_time_max_seconds:.1f}s"
    
    def _format_elapsed_time(self) -> str:
        """Format elapsed time for display."""
        if self.elapsed_seconds < 60:
            return f"{self.elapsed_seconds:.1f}s"
        minutes = self.elapsed_seconds / 60
        return f"{minutes:.1f}min"
    
    def get_assessment(self) -> str:
        """Get human-readable assessment."""
        if not self.spatial_connected:
            return "NO ROAD CONNECTION"
        if not self.is_plausible:
            return "IMPOSSIBLE TRANSITION"
        if self.confidence < 0.5:
            return "SUSPICIOUS TRANSITION"
        return "PLAUSIBLE TRANSITION"


def calculate_spatial_temporal_plausibility(
    camera_a: str,
    camera_b: str,
    timestamp_a: datetime,
    timestamp_b: datetime,
    speed_margin: float = 1.3
) -> SpatioTemporalResult:
    """
    Calculate detailed spatio-temporal plausibility for a vehicle transition.
    
    Args:
        camera_a: Source camera ID
        camera_b: Destination camera ID  
        timestamp_a: Observation time at camera A
        timestamp_b: Observation time at camera B
        speed_margin: Multiplier for speed limit to allow for real-world variance
                     (default 1.3 = 30% above speed limit)
    
    Returns:
        SpatioTemporalResult with detailed analysis
    """
    # Get spatial connection
    spatial_connected, _ = is_spatially_connected(camera_a, camera_b)
    road_edge = _get_edge(camera_a, camera_b)
    
    # If no road connection, it's impossible
    if not spatial_connected:
        # Calculate straight-line distance anyway for reporting
        cam_a_info = CAMERAS.get(camera_a, {})
        cam_b_info = CAMERAS.get(camera_b, {})
        if cam_a_info and cam_b_info:
            distance = haversine_km(
                cam_a_info["lat"], cam_a_info["long"],
                cam_b_info["lat"], cam_b_info["long"]
            )
        else:
            distance = 0.0
        
        elapsed = abs((timestamp_b - timestamp_a).total_seconds())
        required_speed = (distance / (elapsed / 3600)) if elapsed > 0 else float('inf')
        
        return SpatioTemporalResult(
            is_plausible=False,
            camera_a=camera_a,
            camera_b=camera_b,
            timestamp_a=timestamp_a,
            timestamp_b=timestamp_b,
            distance_km=distance,
            elapsed_seconds=elapsed,
            required_speed_kmph=required_speed,
            expected_time_min_seconds=0,
            expected_time_max_seconds=0,
            spatial_connected=False,
            road_edge=None,
            reason=f"No road connection exists between {camera_a} and {camera_b}",
            confidence=0.0
        )
    
    # Calculate distance from road graph
    if road_edge:
        distance_km = road_edge["distance_km"]
        speed_limit = road_edge["speed_limit_kmph"]
    else:
        # Fallback to haversine if no edge (shouldn't happen if spatial_connected)
        cam_a_info = CAMERAS.get(camera_a, {})
        cam_b_info = CAMERAS.get(camera_b, {})
        distance_km = haversine_km(
            cam_a_info["lat"], cam_a_info["long"],
            cam_b_info["lat"], cam_b_info["long"]
        ) if cam_a_info and cam_b_info else 0.0
        speed_limit = 40.0  # Default fallback
    
    # Calculate elapsed time
    elapsed_seconds = abs((timestamp_b - timestamp_a).total_seconds())
    
    # Calculate required speed
    if elapsed_seconds > 0:
        required_speed_kmph = (distance_km / (elapsed_seconds / 3600))
    else:
        required_speed_kmph = float('inf')
    
    # Calculate expected travel time range
    # Minimum time: traveling at speed_limit * speed_margin
    # Maximum time: traveling at minimum reasonable speed (e.g., 10 km/h for urban)
    min_reasonable_speed = 10.0  # km/h
    max_plausible_speed = speed_limit * speed_margin
    
    if max_plausible_speed > 0:
        expected_time_min_seconds = (distance_km / max_plausible_speed) * 3600
    else:
        expected_time_min_seconds = 0
    
    if min_reasonable_speed > 0:
        expected_time_max_seconds = (distance_km / min_reasonable_speed) * 3600
    else:
        expected_time_max_seconds = float('inf')
    
    # Determine plausibility
    max_plausible_speed_limit = speed_limit * speed_margin
    
    if required_speed_kmph > max_plausible_speed_limit:
        # IMPOSSIBLE - required speed exceeds reasonable maximum
        is_plausible = False
        confidence = 0.0
        reason = (
            f"Impossible transition: {distance_km:.1f}km cannot be covered in "
            f"{elapsed_seconds:.1f}s. Required speed: {required_speed_kmph:.1f} km/h "
            f"exceeds plausible maximum of {max_plausible_speed_limit:.1f} km/h "
            f"(speed limit: {speed_limit} km/h)"
        )
    elif elapsed_seconds < expected_time_min_seconds:
        # SUSPICIOUS - faster than expected but not impossible
        is_plausible = True
        confidence = 0.4
        reason = (
            f"Suspicious transition: {distance_km:.1f}km covered in "
            f"{elapsed_seconds:.1f}s is faster than expected "
            f"({expected_time_min_seconds:.1f}s minimum)."
        )
    elif elapsed_seconds > expected_time_max_seconds:
        # SUSPICIOUS - slower than expected
        is_plausible = True
        confidence = 0.6
        reason = (
            f"Slow transition: {distance_km:.1f}km covered in "
            f"{elapsed_seconds:.1f}s is slower than expected "
            f"({expected_time_max_seconds:.1f}s maximum)."
        )
    else:
        # PLAUSIBLE - within expected range
        is_plausible = True
        # Higher confidence for times closer to expected
        time_range = expected_time_max_seconds - expected_time_min_seconds
        if time_range > 0:
            time_position = (elapsed_seconds - expected_time_min_seconds) / time_range
            # Confidence is highest in the middle of the range
            confidence = 1.0 - abs(time_position - 0.5) * 0.4
        else:
            confidence = 0.9
        reason = (
            f"Plausible transition: {distance_km:.1f}km covered in "
            f"{elapsed_seconds:.1f}s is within expected range "
            f"({expected_time_min_seconds:.1f}s–{expected_time_max_seconds:.1f}s)."
        )
    
    return SpatioTemporalResult(
        is_plausible=is_plausible,
        camera_a=camera_a,
        camera_b=camera_b,
        timestamp_a=timestamp_a,
        timestamp_b=timestamp_b,
        distance_km=distance_km,
        elapsed_seconds=elapsed_seconds,
        required_speed_kmph=required_speed_kmph,
        expected_time_min_seconds=expected_time_min_seconds,
        expected_time_max_seconds=expected_time_max_seconds,
        spatial_connected=spatial_connected,
        road_edge=road_edge,
        reason=reason,
        confidence=confidence
    )


def analyze_transition_plausibility(
    obs_a: Dict,
    obs_b: Dict,
    speed_margin: float = 1.3
) -> SpatioTemporalResult:
    """
    Analyze plausibility of a transition between two observations.
    
    Convenience wrapper that extracts camera IDs and timestamps from
    observation dictionaries.
    
    Args:
        obs_a: First observation dict (must have camera_id, timestamp)
        obs_b: Second observation dict (must have camera_id, timestamp)
        speed_margin: Speed margin multiplier for plausibility checking
    
    Returns:
        SpatioTemporalResult with detailed analysis
    """
    timestamp_a = datetime.fromisoformat(obs_a["timestamp"])
    timestamp_b = datetime.fromisoformat(obs_b["timestamp"])
    
    return calculate_spatial_temporal_plausibility(
        camera_a=obs_a["camera_id"],
        camera_b=obs_b["camera_id"],
        timestamp_a=timestamp_a,
        timestamp_b=timestamp_b,
        speed_margin=speed_margin
    )


def detect_impossible_transitions(
    observations: list,
    speed_margin: float = 1.3
) -> list:
    """
    Scan a list of observations for impossible transitions.
    
    Returns a list of transition analyses flagged as impossible.
    
    Args:
        observations: List of observation dicts sorted by timestamp
        speed_margin: Speed margin multiplier for plausibility checking
    
    Returns:
        List of SpatioTemporalResult objects where is_plausible=False
    """
    impossible_transitions = []
    
    for i in range(len(observations)):
        for j in range(i + 1, len(observations)):
            obs_a = observations[i]
            obs_b = observations[j]
            
            # Skip same camera
            if obs_a["camera_id"] == obs_b["camera_id"]:
                continue
            
            result = analyze_transition_plausibility(obs_a, obs_b, speed_margin)
            
            if not result.is_plausible:
                impossible_transitions.append({
                    "result": result,
                    "obs_a_index": i,
                    "obs_b_index": j,
                    "plate_a": obs_a.get("plate_text"),
                    "plate_b": obs_b.get("plate_text")
                })
    
    return impossible_transitions


if __name__ == "__main__":
    # Test the spatio-temporal analysis
    from datetime import datetime, timedelta
    
    base_time = datetime(2026, 8, 24, 10, 0, 0)
    
    # Test case 1: Normal plausible transition
    result1 = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_02",
        base_time,
        base_time + timedelta(seconds=170)
    )
    print("Test 1 - Normal transition:")
    print(f"  Assessment: {result1.get_assessment()}")
    print(f"  Reason: {result1.reason}")
    print(f"  Required speed: {result1.required_speed_kmph:.1f} km/h")
    print()
    
    # Test case 2: Impossible transition (too fast)
    result2 = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_04",
        base_time,
        base_time + timedelta(seconds=60)  # 3.5km in 60s = 210 km/h
    )
    print("Test 2 - Impossible transition:")
    print(f"  Assessment: {result2.get_assessment()}")
    print(f"  Reason: {result2.reason}")
    print(f"  Required speed: {result2.required_speed_kmph:.1f} km/h")
    print()
    
    # Test case 3: No road connection
    result3 = calculate_spatial_temporal_plausibility(
        "CAM_01", "CAM_99",  # Non-existent camera
        base_time,
        base_time + timedelta(seconds=300)
    )
    print("Test 3 - No road connection:")
    print(f"  Assessment: {result3.get_assessment()}")
    print(f"  Reason: {result3.reason}")
