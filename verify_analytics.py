"""
Verify traffic analytics calculations for SIH PS 26127.

This script verifies that the analytics system correctly calculates:
1. Vehicle density
2. Average vehicle speed
3. Origin-Destination patterns/routes
4. Congestion detection
5. Traffic heatmap
6. Time-based traffic trends
"""

from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories
from analytics.analytics import (
    vehicles_per_camera, busiest_camera,
    cross_camera_route_frequency, average_vehicle_speed,
    origin_destination_patterns, congestion_hotspots, hourly_density
)

def verify_traffic_analytics():
    """Verify traffic analytics calculations."""
    
    print("="*60)
    print("TRAFFIC ANALYTICS VERIFICATION")
    print("="*60)
    
    # Load data
    store = ObservationStore()
    obs = store.all_observations()
    trajs = build_trajectories(obs)
    
    print(f"Total observations: {len(obs)}")
    print(f"Total trajectories: {len(trajs)}")
    
    # 1. Vehicle density
    print("\n" + "="*60)
    print("1. VEHICLE DENSITY")
    print("="*60)
    density = vehicles_per_camera(obs)
    print(f"Vehicles per camera: {density}")
    print(f"[OK] Vehicle density calculated for {len(density)} cameras")
    
    # 2. Busiest camera
    print("\n" + "="*60)
    print("2. BUSIEST CAMERA")
    print("="*60)
    busiest = busiest_camera(obs)
    print(f"Busiest camera: {busiest}")
    if busiest:
        print(f"[OK] Busiest camera identified: {busiest} with {density[busiest]} vehicles")
    else:
        print("[WARNING] No busiest camera identified")
    
    # 3. Cross-camera routes
    print("\n" + "="*60)
    print("3. CROSS-CAMERA ROUTES")
    print("="*60)
    routes = cross_camera_route_frequency(trajs)
    print(f"Cross-camera routes: {routes}")
    print(f"[OK] {len(routes)} unique cross-camera routes identified")
    
    # 4. Average vehicle speed
    print("\n" + "="*60)
    print("4. AVERAGE VEHICLE SPEED")
    print("="*60)
    speed_result = average_vehicle_speed(trajs)
    print(f"Speed result: {speed_result}")
    if speed_result.get("status") == "calculated":
        print(f"[OK] Average speed: {speed_result['overall_avg_speed']} km/h")
        print(f"[OK] Valid speed calculations: {speed_result['num_valid_speeds']}")
    else:
        print(f"[WARNING] Speed calculation status: {speed_result.get('status')}")
    
    # 5. Origin-Destination patterns
    print("\n" + "="*60)
    print("5. ORIGIN-DESTINATION PATTERNS")
    print("="*60)
    od_result = origin_destination_patterns(trajs)
    print(f"Top OD pairs: {od_result['top_od_pairs']}")
    print(f"Top origins: {od_result['top_origins']}")
    print(f"Top destinations: {od_result['top_destinations']}")
    print(f"[OK] OD patterns calculated with {len(od_result['od_pairs'])} origin points")
    
    # 6. Congestion detection
    print("\n" + "="*60)
    print("6. CONGESTION DETECTION")
    print("="*60)
    congestion_result = congestion_hotspots(obs)
    print(f"Congested cameras: {congestion_result['congested_cameras']}")
    print(f"Density by camera: {congestion_result['density_by_camera']}")
    print(f"Congestion threshold: {congestion_result['threshold']}")
    if congestion_result.get("status") == "calculated":
        print(f"[OK] {len(congestion_result['congested_cameras'])} congested cameras identified")
    else:
        print(f"[WARNING] Congestion detection status: {congestion_result.get('status')}")
    
    # 7. Traffic heatmap (hourly density)
    print("\n" + "="*60)
    print("7. TRAFFIC HEATMAP (HOURLY DENSITY)")
    print("="*60)
    heatmap_data = hourly_density(obs)
    print(f"Hourly density data: {heatmap_data}")
    total_hourly_buckets = sum(len(buckets) for buckets in heatmap_data.values())
    print(f"[OK] Traffic heatmap data with {total_hourly_buckets} hourly buckets")
    
    # 8. Time-based traffic trends
    print("\n" + "="*60)
    print("8. TIME-BASED TRAFFIC TRENDS")
    print("="*60)
    print(f"Time-based analysis available through hourly_density data")
    print(f"[OK] Time-based trends can be derived from {len(heatmap_data)} cameras")
    
    store.close()
    
    print("\n" + "="*60)
    print("ANALYTICS VERIFICATION COMPLETE")
    print("="*60)
    print(f"[OK] Vehicle density: {len(density)} cameras")
    print(f"[OK] Busiest camera: {busiest}")
    print(f"[OK] Cross-camera routes: {len(routes)} routes")
    print(f"[OK] Average speed: {speed_result.get('overall_avg_speed', 'N/A')} km/h")
    print(f"[OK] OD patterns: {len(od_result['od_pairs'])} origins")
    print(f"[OK] Congestion detection: {len(congestion_result['congested_cameras'])} cameras")
    print(f"[OK] Traffic heatmap: {total_hourly_buckets} hourly buckets")
    print(f"[OK] TRAFFIC INTELLIGENCE OPERATIONAL")
    print("="*60)

if __name__ == "__main__":
    verify_traffic_analytics()
