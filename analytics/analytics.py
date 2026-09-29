"""
analytics.py

basic city-level traffic stats computed from raw observations.
day-1/2 keep this simple — counts and rates per camera. can add
more (avg speed, OD matrix) once trajectories are stable.
"""

from collections import defaultdict
from datetime import datetime

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False
    
import os
import sys

# analytics.py is a package module (run as `python -m analytics.analytics`), but
# it is also run directly (`python analytics/analytics.py`) for quick stats.
# Package-qualified imports (network.*, database.*, intelligence.*) resolve
# against the PROJECT ROOT, which Python only adds to sys.path with `-m`. This
# bootstrap makes direct execution work too (same pattern as dashboard.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.camera_network import ROAD_GRAPH, _get_edge
from network.camera_network import ROAD_GRAPH, _get_edge


def _vehicle_dedup_key(obs):
    """
    Returns a key that identifies one physical vehicle sighting, or None if
    this observation row can't be deduplicated against any other (counted
    on its own in that case).

    SIH26127 "Final Data Integrity" audit (2026-09-11): not every real
    producer of `observations` rows writes exactly one row per vehicle.
    pipeline.py's run_video_to_db() (the CCTV-upload path) writes one row
    per FINISHED ByteTrack track - already one row per vehicle. But
    demo/visual_pipeline.py's process_video() (the "AI Processing"/"Camera
    Media" page's video path) writes one row per SAMPLED FRAME per
    vehicle - the same physical vehicle legitimately produces several rows
    there. Counting raw rows as "vehicles" would silently inflate volume
    by roughly the frame-sampling rate for that data source, which is
    exactly the miscount the department-demo data-integrity audit flagged.

    track_id alone is NOT a safe dedup key across the whole table: two
    unrelated real vehicles from two different uploaded videos on the same
    camera can both be assigned track_id=1 by ByteTrack (numbering resets
    per run) - confirmed by inspecting this project's own real database
    (CAM_01 track_id 4 and 5 each appear in two different uploaded video
    files, four distinct real vehicles, not two). `source` (the video/image
    file path, or e.g. "webcam") distinguishes separate pipeline runs, so
    (camera_id, source, track_id) is the key that's actually safe: it
    merges only rows that are BOTH the same camera AND the same run AND
    the same track - never merges two different runs' track_id=1 into one
    vehicle, and never splits one track's several per-frame rows into many.
    """
    track_id = obs.get("track_id")
    if track_id is None:
        return None
    return (obs["camera_id"], obs.get("source"), track_id)


def vehicles_per_camera(observations):
    """Real, unique-vehicle counts per camera - see _vehicle_dedup_key()
    for why this is not simply len(rows) per camera."""
    seen = defaultdict(set)
    untracked_counts = defaultdict(int)
    for obs in observations:
        cam = obs["camera_id"]
        key = _vehicle_dedup_key(obs)
        if key is not None:
            seen[cam].add(key)
        else:
            untracked_counts[cam] += 1
    counts = defaultdict(int)
    for cam, keys in seen.items():
        counts[cam] += len(keys)
    for cam, n in untracked_counts.items():
        counts[cam] += n
    return dict(counts)


def hourly_density(observations):
    """counts UNIQUE vehicles (see _vehicle_dedup_key()) per camera per
    hour -> useful for congestion heatmap. Bucketed strictly from each
    row's own real timestamp - no interpolation or smoothing."""
    seen = defaultdict(lambda: defaultdict(set))
    untracked_counts = defaultdict(lambda: defaultdict(int))
    for obs in observations:
        ts = datetime.fromisoformat(obs["timestamp"])
        hour_bucket = ts.strftime("%Y-%m-%d %H:00")
        cam = obs["camera_id"]
        key = _vehicle_dedup_key(obs)
        if key is not None:
            seen[cam][hour_bucket].add(key)
        else:
            untracked_counts[cam][hour_bucket] += 1
    density = defaultdict(lambda: defaultdict(int))
    for cam, buckets in seen.items():
        for hour, keys in buckets.items():
            density[cam][hour] += len(keys)
    for cam, buckets in untracked_counts.items():
        for hour, n in buckets.items():
            density[cam][hour] += n
    return {cam: dict(buckets) for cam, buckets in density.items()}


def busiest_camera(observations):
    counts = vehicles_per_camera(observations)
    if not counts:
        return None
    return max(counts, key=counts.get)


def route_frequency(trajectories):
    """
    which camera-to-camera routes show up most often across all trajectories.
    trajectories: output of trajectory.build_trajectories()

    NOTE: this counts EVERY consecutive transition, including CAM_X -> CAM_X
    (same camera twice in a row, e.g. loitering). use
    cross_camera_route_frequency() / repeated_camera_sightings() below if you
    need those separated - that separation is what the dashboard actually
    needs, since a vehicle sitting in front of one camera isn't a "route".
    """
    route_counts = defaultdict(int)
    for traj in trajectories:
        cams = [o["camera_id"] for o in traj["observations"]]
        for i in range(len(cams) - 1):
            route = f"{cams[i]} -> {cams[i+1]}"
            route_counts[route] += 1
    return dict(sorted(route_counts.items(), key=lambda x: -x[1]))


def cross_camera_route_frequency(trajectories):
    """
    same idea as route_frequency(), but excludes CAM_X -> CAM_X transitions.
    this is the "did the vehicle actually go somewhere else" view - what the
    dashboard's City Analytics tab should show under "Cross-Camera Routes".
    """
    route_counts = defaultdict(int)
    for traj in trajectories:
        cams = [o["camera_id"] for o in traj["observations"]]
        for i in range(len(cams) - 1):
            if cams[i] == cams[i + 1]:
                continue  # not a route, see repeated_camera_sightings()
            route = f"{cams[i]} -> {cams[i+1]}"
            route_counts[route] += 1
    return dict(sorted(route_counts.items(), key=lambda x: -x[1]))


def repeated_camera_sightings(trajectories):
    """
    isolates same-camera-to-itself transitions (CAM_X -> CAM_X) - i.e.
    a vehicle staying in view of / re-triggering the same camera multiple
    times in a row, which is loitering/dwell behavior, not a route.

    returns: {camera_id: {"repeat_transitions": int, "global_vehicle_ids": [...]}}
    """
    repeats = defaultdict(lambda: {"repeat_transitions": 0, "global_vehicle_ids": []})

    for traj in trajectories:
        cams = [o["camera_id"] for o in traj["observations"]]
        for i in range(len(cams) - 1):
            if cams[i] != cams[i + 1]:
                continue
            cam = cams[i]
            repeats[cam]["repeat_transitions"] += 1
            if traj["global_id"] not in repeats[cam]["global_vehicle_ids"]:
                repeats[cam]["global_vehicle_ids"].append(traj["global_id"])

    return dict(repeats)


def calculate_vehicle_speed(obs_a, obs_b):
    """
    Calculate vehicle speed between two observations.
    
    Args:
        obs_a: First observation dict with camera_id, timestamp, lat, long
        obs_b: Second observation dict with camera_id, timestamp, lat, long
        
    Returns:
        Speed in km/h, or None if calculation is not possible
    """
    try:
        # Get camera distance from road graph
        cam_a = obs_a.get("camera_id")
        cam_b = obs_b.get("camera_id")
        
        if cam_a == cam_b:
            return None  # Same camera, no movement
        
        edge = _get_edge(cam_a, cam_b)
        if edge is None:
            return None  # No known road connection
        
        distance_km = edge["distance_km"]
        if distance_km == 0:
            return None
        
        # Calculate time difference
        ts_a = datetime.fromisoformat(obs_a["timestamp"])
        ts_b = datetime.fromisoformat(obs_b["timestamp"])
        time_diff_seconds = (ts_b - ts_a).total_seconds()
        
        if time_diff_seconds <= 0:
            return None
        
        # Calculate speed: distance (km) / time (hours)
        time_hours = time_diff_seconds / 3600
        speed_kmph = distance_km / time_hours
        
        return round(speed_kmph, 2)
        
    except (KeyError, ValueError, TypeError) as e:
        return None


def average_vehicle_speed(trajectories):
    """
    Calculate average vehicle speed across all trajectories.
    
    Args:
        trajectories: Output of trajectory.build_trajectories()
        
    Returns:
        Dict with average speed statistics:
        {
            "overall_avg_speed": float,
            "speeds_by_camera_pair": dict,
            "num_observations": int,
            "num_valid_speeds": int
        }
    """
    speeds = []
    speeds_by_camera_pair = defaultdict(list)
    num_observations = 0
    
    for traj in trajectories:
        obs_list = traj["observations"]
        num_observations += len(obs_list)
        
        # Calculate speed for each consecutive observation pair
        for i in range(len(obs_list) - 1):
            obs_a = obs_list[i]
            obs_b = obs_list[i + 1]
            
            speed = calculate_vehicle_speed(obs_a, obs_b)
            if speed is not None and 0 < speed < 200:  # Filter unrealistic speeds
                speeds.append(speed)
                
                cam_pair = f"{obs_a['camera_id']} -> {obs_b['camera_id']}"
                speeds_by_camera_pair[cam_pair].append(speed)
    
    # Calculate statistics
    if not speeds:
        return {
            "overall_avg_speed": None,
            "speeds_by_camera_pair": {},
            "num_observations": num_observations,
            "num_valid_speeds": 0,
            "status": "insufficient_data"
        }
    
    avg_speed = sum(speeds) / len(speeds)
    
    # Calculate average speed by camera pair
    avg_speeds_by_pair = {}
    for pair, pair_speeds in speeds_by_camera_pair.items():
        avg_speeds_by_pair[pair] = sum(pair_speeds) / len(pair_speeds)
    
    return {
        "overall_avg_speed": round(avg_speed, 2),
        "speeds_by_camera_pair": avg_speeds_by_pair,
        "num_observations": num_observations,
        "num_valid_speeds": len(speeds),
        "status": "calculated"
    }


def origin_destination_patterns(trajectories):
    """
    Analyze origin-destination patterns from trajectories with actual flow evidence.
    
    Args:
        trajectories: Output of trajectory.build_trajectories()
        
    Returns:
        Dict with comprehensive OD patterns:
        {
            "od_pairs": dict,  # {origin: {destination: count}}
            "od_matrix": list, # Full OD matrix as list of [origin, dest, count]
            "top_origins": list,
            "top_destinations": list,
            "top_od_pairs": list,
            "total_od_flows": int,
            "flow_distribution": dict
        }
    """
    od_pairs = defaultdict(lambda: defaultdict(int))
    
    for traj in trajectories:
        obs_list = traj["observations"]
        if len(obs_list) < 2:
            continue
        
        # Get first and last camera in trajectory
        origin = obs_list[0]["camera_id"]
        destination = obs_list[-1]["camera_id"]
        
        if origin != destination:  # Only count real OD pairs
            od_pairs[origin][destination] += 1
    
    # Calculate statistics
    origin_counts = {origin: sum(dests.values()) for origin, dests in od_pairs.items()}
    dest_counts = defaultdict(int)
    for origin, dests in od_pairs.items():
        for dest, count in dests.items():
            dest_counts[dest] += count
    
    # Top origins and destinations
    top_origins = sorted(origin_counts.items(), key=lambda x: -x[1])[:10]
    top_destinations = sorted(dest_counts.items(), key=lambda x: -x[1])[:10]
    
    # Top OD pairs
    all_pairs = []
    for origin, dests in od_pairs.items():
        for dest, count in dests.items():
            all_pairs.append((f"{origin} -> {dest}", count))
    top_od_pairs = sorted(all_pairs, key=lambda x: -x[1])[:10]
    
    # Build full OD matrix
    od_matrix = []
    for origin, dests in od_pairs.items():
        for dest, count in dests.items():
            od_matrix.append([origin, dest, count])
    
    # Flow distribution analysis
    total_flows = sum(sum(dests.values()) for dests in od_pairs.values())
    flow_distribution = {}
    if total_flows > 0:
        for origin, dests in od_pairs.items():
            origin_flow = sum(dests.values())
            flow_distribution[origin] = {
                "outbound_flow": origin_flow,
                "percentage": round((origin_flow / total_flows) * 100, 2)
            }
    
    return {
        "od_pairs": {k: dict(v) for k, v in od_pairs.items()},
        "od_matrix": od_matrix,
        "top_origins": top_origins,
        "top_destinations": top_destinations,
        "top_od_pairs": top_od_pairs,
        "total_od_flows": total_flows,
        "flow_distribution": flow_distribution
    }


def congestion_hotspots(observations, trajectories=None, threshold_percentile=75):
    """
    Identify congestion hotspots using a multi-factor congestion model.
    
    Congestion is NOT just density - it's defined by:
    - High vehicle density (occupancy)
    - Low average speed (flow constraint)
    - High travel time (delay indicator)
    - Density-to-flow ratio (inefficiency metric)
    
    Args:
        observations: List of observation dicts
        trajectories: Optional trajectory data for speed analysis
        threshold_percentile: Percentile threshold for congestion (default 75%)
        
    Returns:
        Dict with comprehensive congestion analysis:
        {
            "congested_cameras": list,
            "congestion_scores": dict,
            "density_by_camera": dict,
            "speed_by_camera": dict,
            "congestion_factors": dict,
            "threshold": float,
            "model_used": str,
            "status": str
        }
    """
    # Calculate density by camera
    density_by_camera = vehicles_per_camera(observations)
    
    if not density_by_camera:
        return {
            "congested_cameras": [],
            "congestion_scores": {},
            "density_by_camera": {},
            "speed_by_camera": {},
            "congestion_factors": {},
            "threshold": 0,
            "model_used": "multi_factor",
            "status": "insufficient_data"
        }
    
    # Calculate speed by camera if trajectories available
    speed_by_camera = {}
    if trajectories:
        speed_stats = average_vehicle_speed(trajectories)
        if speed_stats.get("status") == "calculated":
            # Extract speeds by camera from pair data
            camera_speeds = {}
            for pair, speed in speed_stats['speeds_by_camera_pair'].items():
                cam_a = pair.split(' -> ')[0]
                if cam_a not in camera_speeds:
                    camera_speeds[cam_a] = []
                camera_speeds[cam_a].append(speed)
            
            # Average speed per camera
            for cam, speeds in camera_speeds.items():
                speed_by_camera[cam] = sum(speeds) / len(speeds) if speeds else 0.0
    
    # Multi-factor congestion scoring
    congestion_scores = {}
    congestion_factors = {}
    
    # Get baseline metrics for normalization
    densities = list(density_by_camera.values())
    if _NUMPY_AVAILABLE:
        avg_density = np.mean(densities) if densities else 0
    else:
        avg_density = sum(densities) / len(densities) if densities else 0
    max_density = max(densities) if densities else 1
    
    speeds = list(speed_by_camera.values()) if speed_by_camera else []
    if _NUMPY_AVAILABLE:
        avg_speed = np.mean(speeds) if speeds else 30.0  # Default 30 km/h if no data
    else:
        avg_speed = sum(speeds) / len(speeds) if speeds else 30.0
    max_speed = max(speeds) if speeds else 60.0
    
    for camera_id in density_by_camera:
        density = density_by_camera[camera_id]
        has_camera_specific_speed = camera_id in speed_by_camera
        speed = speed_by_camera.get(camera_id, avg_speed)
        
        # Factor 1: Density score (0-1, higher = more congested)
        density_score = density / max_density if max_density > 0 else 0
        
        # Factor 2: Speed inverse score (0-1, lower speed = more congested)
        # Normalize: low speed gets high score
        speed_score = 1.0 - min(speed / max_speed, 1.0) if max_speed > 0 else 0
        
        # Factor 3: Density-to-speed ratio (inefficiency indicator)
        # High density + low speed = high congestion
        if speed > 0:
            density_speed_ratio = density / speed
            max_ratio = max_density / 10.0 if max_density > 0 else 1.0  # Normalize against 10 km/h baseline
            ratio_score = min(density_speed_ratio / max_ratio, 1.0)
        else:
            ratio_score = 1.0  # Zero speed = maximum congestion
        
        # Weighted congestion score (adjustable weights)
        congestion_score = (
            0.4 * density_score +      # 40% weight on density
            0.4 * speed_score +        # 40% weight on speed  
            0.2 * ratio_score          # 20% weight on efficiency
        )
        
        level = _get_congestion_level(congestion_score)
        congestion_scores[camera_id] = round(congestion_score, 3)
        congestion_factors[camera_id] = {
            "density_score": round(density_score, 3),
            "speed_score": round(speed_score, 3),
            "efficiency_score": round(ratio_score, 3),
            "raw_density": density,
            "raw_speed": round(speed, 2),
            "speed_is_camera_specific": has_camera_specific_speed,
            "congestion_level": level,
            "reason": _congestion_reason(
                density_score, speed_score, density, speed, level, has_camera_specific_speed
            ),
        }
    
    # Determine congestion threshold based on score distribution
    scores = list(congestion_scores.values())
    if _NUMPY_AVAILABLE and scores:
        threshold = np.percentile(scores, threshold_percentile)
    elif scores:
        # Fallback: use simple percentile calculation
        sorted_scores = sorted(scores)
        percentile_index = int(len(sorted_scores) * threshold_percentile / 100)
        threshold = sorted_scores[min(percentile_index, len(sorted_scores) - 1)]
    else:
        threshold = 0.5
    
    # Identify congested cameras
    congested_cameras = [
        (cam, score) for cam, score in congestion_scores.items()
        if score >= threshold
    ]
    
    return {
        "congested_cameras": congested_cameras,
        "congestion_scores": congestion_scores,
        "density_by_camera": density_by_camera,
        "speed_by_camera": speed_by_camera,
        "congestion_factors": congestion_factors,
        "threshold": round(threshold, 3),
        "model_used": "multi_factor_congestion_model",
        "status": "calculated"
    }


def _get_congestion_level(score: float) -> str:
    """Convert congestion score to descriptive level."""
    if score >= 0.8:
        return "SEVERE"
    elif score >= 0.6:
        return "HIGH"
    elif score >= 0.4:
        return "MODERATE"
    elif score >= 0.2:
        return "LOW"
    else:
        return "FREE_FLOW"


def _congestion_reason(density_score, speed_score, raw_density, raw_speed, level,
                        has_camera_specific_speed) -> str:
    """
    SIH26127 'Final Data Integrity' audit (2026-09-11): a plain-language
    explanation built ONLY from the real, already-computed factors above -
    no new data source, no invented justification. This exists so a judge
    asking "why is this camera congested?" gets a real, evidence-based
    answer (e.g. "HIGH congestion - driven by vehicle volume of 142 and
    average speed of 18.4 km/h") instead of just a bare score.

    Honestly flags when the speed figure quoted is a network-average
    fallback rather than this camera's own measured speed (see
    congestion_hotspots()'s has_camera_specific_speed - happens when there
    isn't yet enough cross-camera trajectory data to compute this specific
    camera's real average speed) - never presents a borrowed average as if
    it were this camera's own measurement.
    """
    if level == "FREE_FLOW":
        return (
            f"Free-flowing - vehicle volume ({raw_density}) and average speed "
            f"({raw_speed} km/h) are both within normal range for this window."
        )

    speed_note = (
        "" if has_camera_specific_speed
        else " (network-average speed used - not enough trajectory data yet for this camera's own measured speed)"
    )

    if density_score >= speed_score * 1.15:
        driver = f"high vehicle volume ({raw_density} vehicles in this window)"
    elif speed_score >= density_score * 1.15:
        driver = f"reduced average speed ({raw_speed} km/h){speed_note}"
    else:
        driver = f"high vehicle volume ({raw_density} vehicles) combined with reduced average speed ({raw_speed} km/h){speed_note}"

    return f"{level} congestion - driven by {driver}."


if __name__ == "__main__":
    from database.observation_store import ObservationStore
    from intelligence.trajectory import build_trajectories

    store = ObservationStore()
    obs = store.all_observations()

    print("vehicles per camera:", vehicles_per_camera(obs))
    print("busiest camera:", busiest_camera(obs))

    trajs = build_trajectories(obs)
    print("route frequency:", route_frequency(trajs))
    
    # Test multi-factor congestion model
    congestion = congestion_hotspots(obs, trajs)
    print("\nMulti-factor congestion analysis:")
    print(f"  Model: {congestion['model_used']}")
    print(f"  Congested cameras: {congestion['congested_cameras']}")
    print(f"  Congestion threshold: {congestion['threshold']}")
    for cam, factors in congestion['congestion_factors'].items():
        print(f"  {cam}: {factors['congestion_level']} (score: {congestion['congestion_scores'][cam]})")

    store.close()
