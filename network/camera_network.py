"""
camera_network.py

defines the camera nodes AND the road graph between them.
this fixes the earlier bug where "temporal" and "spatial" were
actually the same number - now they're two separate checks:

    spatial feasibility  -> is there even a road connection between
                            these two cameras? (graph lookup)
    temporal feasibility -> given that connection's distance + speed
                            limit, is the observed time gap realistic?

NOTE (SIH26127): ROAD_GRAPH is now maintained in the database (RoadNetwork table)
for production deployment. The hardcoded dict below is used as the demo/bootstrap
reference and for systems without database access. For dynamic road network
management, use the admin API at /api/v1/admin/road-network
"""

import math

CAMERAS = {
    "CAM_01": {
        "lat": 11.0205, "long": 76.9667,
        "name": "Gandhipuram Junction",
        "location": "Gandhipuram Main Road",
        "direction": "North-East",
        "fov": "90 degrees",
        "coverage": "Main traffic flow towards Tidel Park",
        "road_type": "Arterial Road"
    },
    "CAM_02": {
        "lat": 11.0167, "long": 76.9707,
        "name": "Tidel Park Junction",
        "location": "Tidel Park Cross",
        "direction": "East",
        "fov": "75 degrees",
        "coverage": "Intersection traffic monitoring",
        "road_type": "Major Junction"
    },
    "CAM_03": {
        "lat": 11.0051, "long": 76.9508,
        "name": "RS Puram Signal",
        "location": "RS Puram Signal",
        "direction": "South-East",
        "fov": "80 degrees",
        "coverage": "Signal approach and departure",
        "road_type": "Signalized Intersection"
    },
    "CAM_04": {
        "lat": 11.0128, "long": 76.9889,
        "name": "Lakshmi Mills Junction",
        "location": "Lakshmi Mills Junction",
        "direction": "South",
        "fov": "85 degrees",
        "coverage": "Industrial area traffic",
        "road_type": "Industrial Junction"
    },
    "CAM_05": {
        "lat": 10.9911, "long": 76.9600,
        "name": "Town Hall Junction",
        "location": "Town Hall Area",
        "direction": "South-West",
        "fov": "95 degrees",
        "coverage": "City center traffic",
        "road_type": "City Center"
    },
    "CAM_06": {
        "lat": 11.0200, "long": 76.9680,
        "name": "Gandhipuram Bus Stand",
        "location": "Gandhipuram Bus Stand",
        "direction": "West",
        "fov": "70 degrees",
        "coverage": "Bus stand approach",
        "road_type": "Transit Hub"
    },
    "CAM_07": {
        "lat": 10.9990, "long": 77.0324,
        "name": "Singanallur Junction",
        "location": "Singanallur Junction",
        "direction": "North-West",
        "fov": "90 degrees",
        "coverage": "Highway junction traffic",
        "road_type": "Highway Junction"
    },
}

# explicit road graph: which cameras are actually connected by a road,
# with real distance + speed limit for that stretch.
# Coimbatore city road network with realistic distances and speed limits
# Enhanced with road types, traffic conditions, and physical constraints
ROAD_GRAPH = {
    # Main Trunk Road (Gandhipuram to Singanallur)
    ("CAM_01", "CAM_02"): {
        "distance_km": 0.5,
        "speed_limit_kmph": 40,
        "road_type": "arterial",
        "traffic_condition": "moderate",
        "lanes": 2,
        "has_traffic_lights": True,
        "typical_travel_time_min": 0.8
    },
    ("CAM_02", "CAM_03"): {
        "distance_km": 2.5,
        "speed_limit_kmph": 40,
        "road_type": "arterial",
        "traffic_condition": "heavy",
        "lanes": 2,
        "has_traffic_lights": True,
        "typical_travel_time_min": 3.8
    },
    ("CAM_03", "CAM_04"): {
        "distance_km": 3.5,
        "speed_limit_kmph": 40,
        "road_type": "arterial",
        "traffic_condition": "moderate",
        "lanes": 2,
        "has_traffic_lights": False,
        "typical_travel_time_min": 5.3
    },
    ("CAM_04", "CAM_05"): {
        "distance_km": 2.8,
        "speed_limit_kmph": 40,
        "road_type": "arterial",
        "traffic_condition": "light",
        "lanes": 2,
        "has_traffic_lights": True,
        "typical_travel_time_min": 4.2
    },
    ("CAM_05", "CAM_06"): {
        "distance_km": 3.5,
        "speed_limit_kmph": 35,
        "road_type": "urban",
        "traffic_condition": "heavy",
        "lanes": 1,
        "has_traffic_lights": True,
        "typical_travel_time_min": 6.0
    },
    ("CAM_06", "CAM_07"): {
        "distance_km": 7.2,
        "speed_limit_kmph": 45,
        "road_type": "highway",
        "traffic_condition": "moderate",
        "lanes": 2,
        "has_traffic_lights": False,
        "typical_travel_time_min": 9.6
    },

    # Cross connections (alternative routes)
    ("CAM_01", "CAM_03"): {
        "distance_km": 2.8,
        "speed_limit_kmph": 50,
        "road_type": "inner_road",
        "traffic_condition": "light",
        "lanes": 1,
        "has_traffic_lights": False,
        "typical_travel_time_min": 3.4
    },
    ("CAM_02", "CAM_04"): {
        "distance_km": 3.2,
        "speed_limit_kmph": 45,
        "road_type": "connector",
        "traffic_condition": "moderate",
        "lanes": 1,
        "has_traffic_lights": True,
        "typical_travel_time_min": 4.3
    },
    ("CAM_03", "CAM_05"): {
        "distance_km": 1.8,
        "speed_limit_kmph": 45,
        "road_type": "connector",
        "traffic_condition": "heavy",
        "lanes": 1,
        "has_traffic_lights": True,
        "typical_travel_time_min": 2.4
    },
    ("CAM_04", "CAM_06"): {
        "distance_km": 2.5,
        "speed_limit_kmph": 40,
        "road_type": "urban",
        "traffic_condition": "moderate",
        "lanes": 1,
        "has_traffic_lights": True,
        "typical_travel_time_min": 3.8
    },
    ("CAM_05", "CAM_07"): {
        "distance_km": 8.5,
        "speed_limit_kmph": 50,
        "road_type": "highway",
        "traffic_condition": "light",
        "lanes": 2,
        "has_traffic_lights": False,
        "typical_travel_time_min": 10.2
    },

    # Ring road connections (bypass routes)
    ("CAM_01", "CAM_05"): {
        "distance_km": 4.2,
        "speed_limit_kmph": 60,
        "road_type": "bypass",
        "traffic_condition": "light",
        "lanes": 2,
        "has_traffic_lights": False,
        "typical_travel_time_min": 4.2
    },
    ("CAM_02", "CAM_06"): {
        "distance_km": 0.5,
        "speed_limit_kmph": 55,
        "road_type": "bypass",
        "traffic_condition": "moderate",
        "lanes": 2,
        "has_traffic_lights": True,
        "typical_travel_time_min": 0.5
    },
    ("CAM_03", "CAM_07"): {
        "distance_km": 10.5,
        "speed_limit_kmph": 60,
        "road_type": "bypass",
        "traffic_condition": "light",
        "lanes": 2,
        "has_traffic_lights": False,
        "typical_travel_time_min": 10.5
    },

    # Additional long-distance connections for complete network coverage
    ("CAM_01", "CAM_04"): {
        "distance_km": 3.8,
        "speed_limit_kmph": 50,
        "road_type": "trunk",
        "traffic_condition": "moderate",
        "lanes": 2,
        "has_traffic_lights": True,
        "typical_travel_time_min": 4.6
    },
    ("CAM_02", "CAM_05"): {
        "distance_km": 3.8,
        "speed_limit_kmph": 45,
        "road_type": "connector",
        "traffic_condition": "heavy",
        "lanes": 1,
        "has_traffic_lights": True,
        "typical_travel_time_min": 5.1
    },
    ("CAM_04", "CAM_07"): {
        "distance_km": 6.5,
        "speed_limit_kmph": 50,
        "road_type": "highway",
        "traffic_condition": "moderate",
        "lanes": 2,
        "has_traffic_lights": False,
        "typical_travel_time_min": 7.8
    },
}


def _get_edge(cam_a, cam_b):
    if cam_a == cam_b:
        return {"distance_km": 0, "speed_limit_kmph": 999}
    return ROAD_GRAPH.get((cam_a, cam_b)) or ROAD_GRAPH.get((cam_b, cam_a))


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def is_spatially_connected(cam_a, cam_b):
    """
    signal 1: does a road connection even exist between these cameras?
    if two cameras aren't linked in the graph, no plate/appearance score
    should be able to override that - it's just not a valid hop.
    """
    if cam_a == cam_b:
        return True, 1.0
    edge = _get_edge(cam_a, cam_b)
    if edge is None:
        return False, 0.0
    return True, 1.0  # connected = full spatial score for now (binary v1)


def is_temporally_feasible(cam_a, cam_b, time_diff_seconds):
    """
    signal 2: GIVEN that a connection exists, is the observed time gap
    realistic for that specific road's distance + speed limit?
    """
    edge = _get_edge(cam_a, cam_b)
    if edge is None:
        return False, 0.0

    if time_diff_seconds <= 0:
        return False, 0.0

    dist_km = edge["distance_km"]
    speed_limit = edge["speed_limit_kmph"]

    if dist_km == 0:
        return True, 1.0

    time_hours = time_diff_seconds / 3600
    required_speed = dist_km / time_hours if time_hours > 0 else float("inf")

    # allow some margin above the speed limit (traffic isn't perfectly law-abiding)
    # but reject clearly impossible speeds
    max_plausible_speed = speed_limit * 1.3

    if required_speed > max_plausible_speed:
        return False, 0.0

    score = max(0.0, 1 - (required_speed / max_plausible_speed))
    return True, round(score, 3)


def calculate_travel_metrics(cam_a, cam_b, time_diff_seconds):
    """
    Calculate detailed travel metrics for physically constrained trajectory analysis.
    This addresses the counter-strategy for realistic trajectory calculations.
    
    Returns detailed travel analysis including:
    - Road distance (not just straight-line)
    - Required speed vs plausible speed
    - Travel time classification
    - Physical feasibility assessment
    """
    edge = _get_edge(cam_a, cam_b)
    if edge is None:
        return {
            "feasible": False,
            "reason": "no_road_connection",
            "road_distance_km": 0,
            "required_speed_kmph": 0,
            "max_plausible_speed_kmph": 0,
            "time_classification": "IMPOSSIBLE"
        }
    
    road_distance = edge["distance_km"]
    speed_limit = edge["speed_limit_kmph"]
    road_type = edge.get("road_type", "unknown")
    has_traffic_lights = edge.get("has_traffic_lights", False)
    typical_travel_time = edge.get("typical_travel_time_min", 0)
    
    if time_diff_seconds <= 0:
        return {
            "feasible": False,
            "reason": "invalid_time",
            "road_distance_km": road_distance,
            "required_speed_kmph": float("inf"),
            "max_plausible_speed_kmph": speed_limit * 1.3,
            "time_classification": "IMPOSSIBLE"
        }
    
    time_hours = time_diff_seconds / 3600
    required_speed = road_distance / time_hours if time_hours > 0 else float("inf")
    max_plausible_speed = speed_limit * 1.3
    
    # Calculate time classification
    time_minutes = time_diff_seconds / 60
    
    if required_speed > max_plausible_speed:
        classification = "IMPOSSIBLE"
        feasible = False
        reason = f"Required speed {required_speed:.1f} km/h exceeds max plausible {max_plausible_speed:.1f} km/h"
    elif required_speed > speed_limit:
        classification = "SUSPICIOUS"
        feasible = True
        reason = f"Speed {required_speed:.1f} km/h exceeds limit {speed_limit} km/h but within margin"
    elif time_minutes > typical_travel_time * 2:
        classification = "SLOW"
        feasible = True
        reason = f"Travel time {time_minutes:.1f} min much longer than typical {typical_travel_time:.1f} min"
    else:
        classification = "NORMAL"
        feasible = True
        reason = f"Normal travel: {required_speed:.1f} km/h within {speed_limit} km/h limit"
    
    return {
        "feasible": feasible,
        "reason": reason,
        "road_distance_km": road_distance,
        "straight_line_distance_km": haversine_km(
            CAMERAS[cam_a]["lat"], CAMERAS[cam_a]["long"],
            CAMERAS[cam_b]["lat"], CAMERAS[cam_b]["long"]
        ),
        "required_speed_kmph": required_speed,
        "max_plausible_speed_kmph": max_plausible_speed,
        "speed_limit_kmph": speed_limit,
        "time_observed_seconds": time_diff_seconds,
        "time_observed_formatted": format_time_gap(time_diff_seconds),
        "time_expected_min": typical_travel_time,
        "time_classification": classification,
        "road_type": road_type,
        "has_traffic_lights": has_traffic_lights,
        "camera_a": cam_a,
        "camera_b": cam_b
    }


def format_time_gap(seconds):
    """Format time gap in human-readable format"""
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def detect_impossible_travel(observations, max_plausible_speed_multiplier=1.3):
    """
    Detect impossible travel patterns in observations that would indicate
    cloned plates or timestamp anomalies.
    
    This is the counter-strategy feature to address the competitor's cloned plate detection.
    """
    anomalies = []
    
    for i in range(len(observations)):
        for j in range(i + 1, len(observations)):
            obs_a = observations[i]
            obs_b = observations[j]
            
            if obs_a["camera_id"] == obs_b["camera_id"]:
                continue  # Skip same camera
            
            try:
                from datetime import datetime
                time_a = datetime.fromisoformat(obs_a["timestamp"])
                time_b = datetime.fromisoformat(obs_b["timestamp"])
                time_diff = abs((time_b - time_a).total_seconds())
                
                metrics = calculate_travel_metrics(obs_a["camera_id"], obs_b["camera_id"], time_diff)
                
                if metrics["time_classification"] == "IMPOSSIBLE":
                    anomalies.append({
                        "type": "IMPOSSIBLE_TRAVEL",
                        "plate_a": obs_a.get("plate_text", "UNKNOWN"),
                        "plate_b": obs_b.get("plate_text", "UNKNOWN"),
                        "camera_a": obs_a["camera_id"],
                        "camera_b": obs_b["camera_id"],
                        "timestamp_a": obs_a["timestamp"],
                        "timestamp_b": obs_b["timestamp"],
                        "time_gap_seconds": time_diff,
                        "road_distance_km": metrics["road_distance_km"],
                        "required_speed_kmph": metrics["required_speed_kmph"],
                        "max_plausible_speed_kmph": metrics["max_plausible_speed_kmph"],
                        "reason": metrics["reason"],
                        "severity": "CRITICAL" if metrics["required_speed_kmph"] > 500 else "HIGH"
                    })
                    
            except Exception as e:
                continue
    
    return anomalies


# camera reliability: how much we trust observations from each camera.
# lower for cameras with bad angle/lighting/resolution in your actual footage.
# this is a manual estimate for the demo - in a real deployment you'd learn
# this from historical match accuracy per camera, but that needs data we
# won't have in a hackathon timeframe.
CAMERA_RELIABILITY = {
    "CAM_01": 0.95,  # Gandhipuram - high traffic, good angle
    "CAM_02": 0.90,  # Tidel Park - moderate lighting
    "CAM_03": 0.85,  # RS Puram - some shadows
    "CAM_04": 0.88,  # Lakshmi Mills - good position
    "CAM_05": 0.92,  # Town Hall - excellent coverage
    "CAM_06": 0.87,  # Bus Stand - challenging angles
    "CAM_07": 0.90,  # Singanallur - good reliability
}


def get_camera_reliability(cam_id):
    return CAMERA_RELIABILITY.get(cam_id, 0.8)  # unknown camera = conservative default
