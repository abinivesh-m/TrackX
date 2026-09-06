"""
what_if_simulator.py

What-If Simulator for TrackX.

This module allows users to explore how changing assumptions affects
spatio-temporal plausibility assessments. It demonstrates that TrackX
is performing actual reasoning rather than using hardcoded thresholds.

Users can adjust:
- Distance between cameras
- Observed travel time
- Speed margin/tolerance
- Speed limit assumptions

And immediately see how these changes affect:
- Required speed
- Expected travel time range
- Plausibility assessment
- Transition status

This is crucial for SIH demonstrations to show judges that the system
is reasoning dynamically.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import json

from intelligence.spatio_temporal import (
    calculate_spatial_temporal_plausibility,
    SpatioTemporalResult
)
from network.camera_network import CAMERAS, ROAD_GRAPH, _get_edge


class WhatIfScenario:
    """
    A what-if scenario for exploring spatio-temporal reasoning.
    
    Allows adjustment of key parameters to see how they affect
    plausibility assessments.
    """
    
    def __init__(
        self,
        camera_a: str,
        camera_b: str,
        timestamp_a: datetime,
        timestamp_b: datetime,
        base_distance_km: Optional[float] = None,
        base_speed_limit_kmph: Optional[float] = None
    ):
        self.camera_a = camera_a
        self.camera_b = camera_b
        self.timestamp_a = timestamp_a
        self.timestamp_b = timestamp_b
        
        # Get base values from existing road graph
        edge = _get_edge(camera_a, camera_b)
        if edge:
            self.base_distance_km = edge["distance_km"]
            self.base_speed_limit_kmph = edge["speed_limit_kmph"]
        else:
            # Fallback to haversine if no edge exists
            from network.camera_network import haversine_km
            cam_a_info = CAMERAS.get(camera_a, {})
            cam_b_info = CAMERAS.get(camera_b, {})
            if cam_a_info and cam_b_info:
                self.base_distance_km = haversine_km(
                    cam_a_info["lat"], cam_a_info["long"],
                    cam_b_info["lat"], cam_b_info["long"]
                )
            else:
                self.base_distance_km = 1.0  # Default fallback
            self.base_speed_limit_kmph = 40.0  # Default fallback
        
        # Allow override of base values
        self.distance_km = base_distance_km if base_distance_km is not None else self.base_distance_km
        self.speed_limit_kmph = base_speed_limit_kmph if base_speed_limit_kmph is not None else self.base_speed_limit_kmph
        
        # Adjustable parameters
        self.speed_margin = 1.3  # Default 30% above speed limit
        self.min_reasonable_speed = 10.0  # km/h minimum reasonable speed
        
        # Results cache
        self.current_result = None
        self.param_history = []
    
    def adjust_distance(self, new_distance_km: float) -> Dict:
        """
        Adjust the distance between cameras and recalculate plausibility.
        
        Returns the new spatio-temporal result.
        """
        old_distance = self.distance_km
        self.distance_km = new_distance_km
        
        result = self._recalculate_with_custom_edge()
        
        self._record_change("distance", old_distance, new_distance_km, result)
        
        return result.to_dict()
    
    def adjust_travel_time(self, new_elapsed_seconds: float) -> Dict:
        """
        Adjust the observed travel time and recalculate plausibility.
        
        Returns the new spatio-temporal result.
        """
        old_time = (self.timestamp_b - self.timestamp_a).total_seconds()
        new_timestamp_b = self.timestamp_a + timedelta(seconds=new_elapsed_seconds)
        
        old_timestamp_b = self.timestamp_b
        self.timestamp_b = new_timestamp_b
        
        result = calculate_spatial_temporal_plausibility(
            self.camera_a, self.camera_b,
            self.timestamp_a, self.timestamp_b,
            speed_margin=self.speed_margin
        )
        
        self._record_change("travel_time", old_time, new_elapsed_seconds, result)
        
        # Restore original timestamp for further adjustments
        self.timestamp_b = old_timestamp_b
        
        return result.to_dict()
    
    def adjust_speed_margin(self, new_margin: float) -> Dict:
        """
        Adjust the speed margin tolerance and recalculate plausibility.
        
        Returns the new spatio-temporal result.
        """
        old_margin = self.speed_margin
        self.speed_margin = new_margin
        
        result = calculate_spatial_temporal_plausibility(
            self.camera_a, self.camera_b,
            self.timestamp_a, self.timestamp_b,
            speed_margin=self.speed_margin
        )
        
        self._record_change("speed_margin", old_margin, new_margin, result)
        
        return result.to_dict()
    
    def adjust_speed_limit(self, new_speed_limit_kmph: float) -> Dict:
        """
        Adjust the assumed speed limit and recalculate plausibility.
        
        Returns the new spatio-temporal result.
        """
        old_limit = self.speed_limit_kmph
        self.speed_limit_kmph = new_speed_limit_kmph
        
        result = self._recalculate_with_custom_edge()
        
        self._record_change("speed_limit", old_limit, new_speed_limit_kmph, result)
        
        return result.to_dict()
    
    def _recalculate_with_custom_edge(self) -> SpatioTemporalResult:
        """
        Recalculate plausibility using custom distance/speed limit.
        
        This temporarily modifies the road graph for calculation,
        then restores it.
        """
        # Save original edge
        original_edge = ROAD_GRAPH.get((self.camera_a, self.camera_b))
        original_edge_reversed = ROAD_GRAPH.get((self.camera_b, self.camera_a))
        
        # Create custom edge
        custom_edge = {
            "distance_km": self.distance_km,
            "speed_limit_kmph": self.speed_limit_kmph
        }
        
        # Temporarily add custom edge
        ROAD_GRAPH[(self.camera_a, self.camera_b)] = custom_edge
        
        try:
            result = calculate_spatial_temporal_plausibility(
                self.camera_a, self.camera_b,
                self.timestamp_a, self.timestamp_b,
                speed_margin=self.speed_margin
            )
        finally:
            # Restore original edge
            if original_edge is not None:
                ROAD_GRAPH[(self.camera_a, self.camera_b)] = original_edge
            else:
                del ROAD_GRAPH[(self.camera_a, self.camera_b)]
            
            if original_edge_reversed is not None:
                ROAD_GRAPH[(self.camera_b, self.camera_a)] = original_edge_reversed
            elif (self.camera_b, self.camera_a) in ROAD_GRAPH:
                del ROAD_GRAPH[(self.camera_b, self.camera_a)]
        
        self.current_result = result
        return result
    
    def _record_change(self, param_type: str, old_value: float, new_value: float, result: SpatioTemporalResult):
        """Record a parameter change for history tracking."""
        self.param_history.append({
            "param_type": param_type,
            "old_value": old_value,
            "new_value": new_value,
            "result": result.to_dict(),
            "timestamp": datetime.now().isoformat()
        })
    
    def get_current_assessment(self) -> Dict:
        """Get the current plausibility assessment."""
        if self.current_result is None:
            self.current_result = self._recalculate_with_custom_edge()
        
        return {
            "scenario": {
                "camera_a": self.camera_a,
                "camera_b": self.camera_b,
                "timestamp_a": self.timestamp_a.isoformat(),
                "timestamp_b": self.timestamp_b.isoformat(),
                "distance_km": self.distance_km,
                "speed_limit_kmph": self.speed_limit_kmph,
                "speed_margin": self.speed_margin,
                "elapsed_seconds": (self.timestamp_b - self.timestamp_a).total_seconds()
            },
            "assessment": self.current_result.to_dict(),
            "base_values": {
                "base_distance_km": self.base_distance_km,
                "base_speed_limit_kmph": self.base_speed_limit_kmph
            },
            "change_count": len(self.param_history)
        }
    
    def get_parameter_sensitivity(self) -> Dict:
        """
        Analyze how sensitive the plausibility assessment is to parameter changes.
        
        Returns a summary of which parameters most affect the assessment.
        """
        if not self.param_history:
            return {"message": "No parameter changes recorded yet"}
        
        sensitivity = {
            "distance_changes": [],
            "time_changes": [],
            "margin_changes": [],
            "speed_limit_changes": []
        }
        
        for change in self.param_history:
            param_type = change["param_type"]
            old_val = change["old_value"]
            new_val = change["new_value"]
            result = change["result"]
            
            entry = {
                "from": old_val,
                "to": new_val,
                "change_percent": ((new_val - old_val) / old_val * 100) if old_val != 0 else 0,
                "new_plausibility": result["is_plausible"],
                "new_confidence": result["confidence"],
                "new_assessment": result["assessment"] if "assessment" in result else "N/A"
            }
            
            if param_type == "distance":
                sensitivity["distance_changes"].append(entry)
            elif param_type == "travel_time":
                sensitivity["time_changes"].append(entry)
            elif param_type == "speed_margin":
                sensitivity["margin_changes"].append(entry)
            elif param_type == "speed_limit":
                sensitivity["speed_limit_changes"].append(entry)
        
        return sensitivity
    
    def reset_to_base(self) -> Dict:
        """Reset all parameters to base values from road graph."""
        self.distance_km = self.base_distance_km
        self.speed_limit_kmph = self.base_speed_limit_kmph
        self.speed_margin = 1.3
        
        result = self._recalculate_with_custom_edge()
        
        return {
            "message": "Reset to base values",
            "assessment": result.to_dict()
        }


def create_demo_scenario(scenario_type: str) -> WhatIfScenario:
    """
    Create pre-configured demo scenarios for what-if exploration.
    
    Args:
        scenario_type: "normal", "impossible", "suspicious", "edge_case"
    
    Returns:
        Configured WhatIfScenario ready for exploration
    """
    base_time = datetime(2026, 8, 24, 10, 0, 0)
    
    if scenario_type == "normal":
        # Normal plausible transition
        return WhatIfScenario(
            "CAM_01", "CAM_02",
            base_time,
            base_time + timedelta(seconds=170)  # Normal time for 1.4km
        )
    
    elif scenario_type == "impossible":
        # Impossible transition
        return WhatIfScenario(
            "CAM_01", "CAM_04",
            base_time,
            base_time + timedelta(seconds=30)  # 3.5km in 30s = impossible
        )
    
    elif scenario_type == "suspicious":
        # Suspicious but possible
        return WhatIfScenario(
            "CAM_01", "CAM_02",
            base_time,
            base_time + timedelta(seconds=60)  # Faster than normal
        )
    
    elif scenario_type == "edge_case":
        # Edge case - right at the boundary
        return WhatIfScenario(
            "CAM_01", "CAM_04",
            base_time,
            base_time + timedelta(seconds=170)  # 3.5km in 170s = ~74 km/h (at 60km/h limit)
        )
    
    else:
        raise ValueError(f"Unknown scenario type: {scenario_type}")


def simulate_counterfactuals(
    camera_a: str,
    camera_b: str,
    timestamp_a: datetime,
    timestamp_b: datetime
) -> Dict:
    """
    Generate counterfactual explanations for why a transition might be invalid.
    
    This implements the Phase 7 requirement: when an impossible transition
    is detected, generate competing explanations of what would need to be true.
    
    Returns:
        Dict with primary explanation and alternative explanations
    """
    # First, get the actual assessment
    actual_result = calculate_spatial_temporal_plausibility(
        camera_a, camera_b, timestamp_a, timestamp_b
    )
    
    if actual_result.is_plausible:
        return {
            "status": "PLAUSIBLE",
            "message": "Transition is already plausible - no counterfactuals needed",
            "actual_assessment": actual_result.to_dict()
        }
    
    # Generate counterfactual explanations
    scenario = WhatIfScenario(camera_a, camera_b, timestamp_a, timestamp_b)
    
    counterfactuals = []
    
    # Counterfactual 1: What if the travel time was longer?
    current_elapsed = (timestamp_b - timestamp_a).total_seconds()
    required_time_for_plausibility = (actual_result.distance_km / 
                                     (actual_result.expected_time_max_seconds / 3600)) * 3600
    
    if required_time_for_plausibility > current_elapsed:
        counterfactuals.append({
            "explanation": "LONGER_TRAVEL_TIME",
            "description": f"If the vehicle took {required_time_for_plausibility:.1f}s instead of {current_elapsed:.1f}s",
            "required_change": f"+{required_time_for_plausibility - current_elapsed:.1f}s",
            "feasibility": "HIGH" if required_time_for_plausibility < 600 else "LOW"
        })
    
    # Counterfactual 2: What if the distance was shorter?
    current_distance = actual_result.distance_km
    required_distance_for_current_time = (actual_result.required_speed_kmph * 
                                         (current_elapsed / 3600))
    
    if required_distance_for_current_time < current_distance:
        counterfactuals.append({
            "explanation": "SHORTER_DISTANCE",
            "description": f"If the cameras were only {required_distance_for_current_time:.1f}km apart instead of {current_distance:.1f}km",
            "required_change": f"-{current_distance - required_distance_for_current_time:.1f}km",
            "feasibility": "MEDIUM"  # Camera positions don't change easily
        })
    
    # Counterfactual 3: What if speed limit was higher?
    current_speed_limit = actual_result.road_edge["speed_limit_kmph"] if actual_result.road_edge else 40.0
    required_speed_limit = actual_result.required_speed_kmph / 1.3  # Reverse the margin calculation
    
    if required_speed_limit > current_speed_limit:
        counterfactuals.append({
            "explanation": "HIGHER_SPEED_LIMIT",
            "description": f"If the speed limit was {required_speed_limit:.1f} km/h instead of {current_speed_limit:.1f} km/h",
            "required_change": f"+{required_speed_limit - current_speed_limit:.1f} km/h",
            "feasibility": "LOW"  # Speed limits are regulatory
        })
    
    # Counterfactual 4: What if there's a timestamp error?
    counterfactuals.append({
        "explanation": "TIMESTAMP_ERROR",
        "description": "If either camera's timestamp is incorrect",
        "required_change": "Timestamp correction needed",
        "feasibility": "MEDIUM"  # Camera clock sync issues are possible
    })
    
    # Counterfactual 5: What if it's a cloned plate?
    counterfactuals.append({
        "explanation": "CLONED_PLATE",
        "description": "If the same plate is on two different vehicles",
        "required_change": "Identity investigation needed",
        "feasibility": "HIGH"  # This is often the actual explanation
    })
    
    # Rank counterfactuals by feasibility
    feasibility_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    counterfactuals.sort(key=lambda x: feasibility_order.get(x["feasibility"], 3))
    
    return {
        "status": "IMPOSSIBLE",
        "actual_assessment": actual_result.to_dict(),
        "primary_explanation": counterfactuals[0] if counterfactuals else "UNKNOWN",
        "alternative_explanations": counterfactuals[1:] if len(counterfactuals) > 1 else [],
        "total_counterfactuals": len(counterfactuals)
    }


if __name__ == "__main__":
    # Test the what-if simulator
    from datetime import datetime, timedelta
    
    base_time = datetime(2026, 8, 24, 10, 0, 0)
    
    print("=== What-If Simulator Demo ===\n")
    
    # Create an impossible scenario
    scenario = create_demo_scenario("impossible")
    print("Initial impossible scenario:")
    assessment = scenario.get_current_assessment()
    print(f"Is plausible: {assessment['assessment']['is_plausible']}")
    print(f"Required speed: {assessment['assessment']['required_speed_kmph']:.1f} km/h")
    print(f"Reason: {assessment['assessment']['reason']}")
    print()
    
    # What if we adjust the travel time?
    print("Adjusting travel time to 200s:")
    result = scenario.adjust_travel_time(200)
    # Create a temporary SpatioTemporalResult-like object for the assessment
    class TempResult:
        def __init__(self, data):
            self.data = data
        def get_assessment(self):
            if not self.data['is_plausible']:
                return "IMPOSSIBLE TRANSITION"
            elif self.data['confidence'] < 0.5:
                return "SUSPICIOUS TRANSITION"
            else:
                return "PLAUSIBLE TRANSITION"
    
    temp_result = TempResult(result)
    print(f"New assessment: {temp_result.get_assessment()}")
    print(f"New confidence: {result['confidence']:.3f}")
    print(f"Required speed: {result['required_speed_kmph']:.1f} km/h")
    print()
    
    # What if we adjust the distance?
    print("Adjusting distance to 1.0km:")
    result = scenario.adjust_distance(1.0)
    temp_result2 = TempResult(result)
    print(f"New assessment: {temp_result2.get_assessment()}")
    print(f"New confidence: {result['confidence']:.3f}")
    print(f"Required speed: {result['required_speed_kmph']:.1f} km/h")
    print()
    
    # Reset
    print("Resetting to base values:")
    print(scenario.reset_to_base())
    print()
    
    # Counterfactual analysis
    print("=== Counterfactual Analysis ===")
    counterfactuals = simulate_counterfactuals(
        "CAM_01", "CAM_04",
        base_time,
        base_time + timedelta(seconds=30)
    )
    print(f"Status: {counterfactuals['status']}")
    if counterfactuals['primary_explanation']:
        print(f"Primary explanation: {counterfactuals['primary_explanation']['explanation']}")
        print(f"Description: {counterfactuals['primary_explanation']['description']}")
        print(f"\nAlternative explanations ({len(counterfactuals['alternative_explanations'])}):")
        for alt in counterfactuals['alternative_explanations']:
            print(f"  - {alt['explanation']}: {alt['description']}")
