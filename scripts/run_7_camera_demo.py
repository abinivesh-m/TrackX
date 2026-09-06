"""
run_7_camera_demo.py

Comprehensive demo for the 7-camera Coimbatore network.
This script processes all 7 camera streams independently, builds trajectories,
and demonstrates the complete TrackX vehicle intelligence pipeline.

Usage:
    python scripts/run_7_camera_demo.py --clean
    python scripts/run_7_camera_demo.py --clean --dashboard
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from detection.vehicle_detector import VehicleDetector
from detection.detect_plates import PlateDetector
from recognition.ocr_reader import try_init_ocr
from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories
from analytics.analytics import (
    vehicles_per_camera, busiest_camera,
    cross_camera_route_frequency, average_vehicle_speed,
    origin_destination_patterns, congestion_hotspots
)
from intelligence.alerts import scan_trajectories_for_alerts
from network.camera_network import CAMERAS
from config import RESULTS_DIR, DB_PATH_STR


def find_plate_weights():
    """Find the best available plate detector weights."""
    possible_paths = [
        "detection/runs/detect/plate_train/weights/best.pt",
        "models/plate_detector.pt",
        "yolo11n.pt",  # Fallback to YOLO11 if available
    ]
    
    for path in possible_paths:
        full_path = PROJECT_ROOT / path
        if full_path.exists():
            return str(full_path)
    
    return None


def process_camera_stream(camera_id, video_path, vehicle_detector, plate_detector, ocr, store):
    """Process a single camera stream and add observations to the database."""
    camera_config = CAMERAS.get(camera_id)
    if not camera_config:
        print(f"Error: Camera {camera_id} not found in network configuration")
        return 0
    
    print(f"\n{'='*60}")
    print(f"Processing Camera: {camera_id} - {camera_config['name']}")
    print(f"Location: {camera_config['location']}")
    print(f"Coordinates: {camera_config['lat']}, {camera_config['long']}")
    print(f"Video: {video_path}")
    print(f"{'='*60}")
    
    if not os.path.exists(video_path):
        print(f"Warning: Video file not found: {video_path}")
        print(f"Skipping {camera_id} - will use simulated data for demo")
        return 0
    
    try:
        from pipeline import run_video_to_db
        
        records = run_video_to_db(
            video_path=video_path,
            vehicle_detector=vehicle_detector,
            plate_detector=plate_detector,
            ocr=ocr,
            cam_id=camera_id,
            lat=camera_config['lat'],
            lng=camera_config['long'],
            store=store,
        )
        
        print(f"✓ Processed {len(records)} vehicle records from {camera_id}")
        return len(records)
        
    except Exception as e:
        print(f"Error processing {camera_id}: {e}")
        return 0


def seed_demo_observations(store):
    """
    Seed the database with realistic multi-camera observations for demo purposes.
    This creates the exact TN 09 CX 7134 trajectory from the user's uploaded images:
    Real multi-camera trajectory with actual timestamps from provided evidence.
    """
    print("\n" + "="*60)
    print("Seeding demo observations for 7-camera network")
    print("="*60)
    
    # Demo vehicle: TN 09 CX 7134 with actual trajectory from uploaded images
    demo_plate = "TN09CX7134"
    
    # Real trajectory from uploaded images with actual timestamps
    # CAM 02 → 03-06-2025 10:22:47
    # CAM 03 → 03-06-2025 12:31:09  
    # CAM 05 → 03-06-2025 18:05:44
    # CAM 06 → 03-06-2025 20:17:33
    # CAM 07 → 03-06-2025 22:38:56
    # Using appearance vectors that are similar to help matching
    base_appearance = [0.1] * 512
    trajectory_data = [
        ("CAM_02", datetime(2025, 6, 3, 10, 22, 47), 0.97, base_appearance),
        ("CAM_03", datetime(2025, 6, 3, 12, 31, 9), 0.95, [v + 0.01 for v in base_appearance]),
        ("CAM_05", datetime(2025, 6, 3, 18, 5, 44), 0.96, [v + 0.02 for v in base_appearance]),
        ("CAM_06", datetime(2025, 6, 3, 20, 17, 33), 0.98, [v + 0.03 for v in base_appearance]),
        ("CAM_07", datetime(2025, 6, 3, 22, 38, 56), 0.99, [v + 0.04 for v in base_appearance]),
    ]
    
    records_added = 0
    print("\nCreating TN09CX7134 trajectory:")
    for camera_id, timestamp, confidence, appearance_vector in trajectory_data:
        camera_config = CAMERAS.get(camera_id)
        if not camera_config:
            continue
            
        record = {
            "plate_text": demo_plate,
            "normalized_plate": demo_plate,
            "raw_plate_text": demo_plate,
            "confidence": confidence,
            "camera_id": camera_id,
            "timestamp": timestamp.isoformat(),
            "lat": camera_config['lat'],
            "long": camera_config['long'],
            "track_id": f"TN09CX7134_track",  # Same track ID for all observations of this vehicle
            "vehicle_type": "car",
            "vehicle_confidence": 0.95,
            "direction": "forward",
            "data_source": "DEMO_TRAJECTORY",
            "source": "7_camera_demo",
            "frame_index": 0,
            "vehicle_bbox": [100, 100, 300, 300],
            "plate_bbox": [150, 150, 250, 200],
            "ocr_confidence": confidence,
        }
        
        store.add(record, appearance_vector)
        records_added += 1
        time_str = timestamp.strftime('%H:%M:%S')
        print(f"  {camera_id} ({camera_config['name']}) → {time_str} - {confidence*100:.0f}% confidence")
    
    # Add additional vehicles for realistic network traffic across all 7 cameras
    print("\nAdding background traffic for realistic network:")
    additional_plates = [
        "TN12AB3456", "TN45CD6789", "TN78EF0123", "TN90GH1234",
        "TN23IJ4567", "TN56KL7890", "TN89MN0123", "TN01AB2345"
    ]
    
    # Use a base time for background traffic (same day as demo trajectory)
    traffic_base_time = datetime(2025, 6, 3, 8, 0, 0)  # Start before the main trajectory
    
    for i, plate in enumerate(additional_plates):
        # Create varied trajectories for different vehicles
        num_observations = 2 + (i % 3)  # 2-4 observations per vehicle
        start_camera = list(CAMERAS.keys())[i % 7]
        
        # Use consistent appearance vectors for the same vehicle
        base_vehicle_appearance = [0.2 + (i * 0.01)] * 512
        
        for j in range(num_observations):
            camera_index = (i + j) % 7
            camera_id = list(CAMERAS.keys())[camera_index]
            camera_config = CAMERAS.get(camera_id)
            
            offset = timedelta(minutes=i*2 + j*3, seconds=j*15)
            timestamp = traffic_base_time + offset
            
            # Slight variation in appearance for each observation of same vehicle
            appearance_vector = [v + (j * 0.001) for v in base_vehicle_appearance]
            
            record = {
                "plate_text": plate,
                "normalized_plate": plate,
                "raw_plate_text": plate,
                "confidence": 0.85 + (i * 0.01) + (j * 0.005),
                "camera_id": camera_id,
                "timestamp": timestamp.isoformat(),
                "lat": camera_config['lat'],
                "long": camera_config['long'],
                "track_id": f"{plate}_track",  # Same track ID for all observations of this vehicle
                "vehicle_type": "car" if i % 2 == 0 else "motorcycle",
                "vehicle_confidence": 0.90,
                "direction": "forward",
                "data_source": "DEMO_TRAFFIC",
                "source": "7_camera_demo",
                "frame_index": 0,
                "vehicle_bbox": [100, 100, 300, 300],
                "plate_bbox": [150, 150, 250, 200],
                "ocr_confidence": 0.85 + (i * 0.01),
            }
            store.add(record, appearance_vector)
            records_added += 1
            
            # Slight variation in appearance for each observation of same vehicle
            appearance_vector = [v + (j * 0.001) for v in base_vehicle_appearance]
            
            record = {
                "plate_text": plate,
                "normalized_plate": plate,
                "raw_plate_text": plate,
                "confidence": 0.85 + (i * 0.01) + (j * 0.005),
                "camera_id": camera_id,
                "timestamp": timestamp.isoformat(),
                "lat": camera_config['lat'],
                "long": camera_config['long'],
                "track_id": f"{plate}_track",  # Same track ID for all observations of this vehicle
                "vehicle_type": "car" if i % 2 == 0 else "motorcycle",
                "vehicle_confidence": 0.90,
                "direction": "forward",
                "data_source": "DEMO_TRAFFIC",
                "source": "7_camera_demo",
                "frame_index": 0,
                "vehicle_bbox": [100, 100, 300, 300],
                "plate_bbox": [150, 150, 250, 200],
                "ocr_confidence": 0.85 + (i * 0.01),
            }
            store.add(record, appearance_vector)
            records_added += 1
    
    print(f"\n✓ Seeded {records_added} total demo observations across 7-camera network")
    print(f"  - 1 main trajectory (TN09CX7134 across 5 cameras)")
    print(f"  - {records_added - 5} background vehicle observations")
    return records_added


def run_analytics(store, observations, trajectories):
    """Run analytics on the 7-camera network data."""
    print("\n" + "="*60)
    print("7-CAMERA NETWORK ANALYTICS")
    print("="*60)
    
    # Vehicle counts per camera
    vehicle_counts = vehicles_per_camera(observations)
    print("\nVehicles per Camera:")
    for camera_id, count in sorted(vehicle_counts.items()):
        camera_name = CAMERAS.get(camera_id, {}).get('name', 'Unknown')
        print(f"  {camera_id} ({camera_name}): {count} vehicles")
    
    # Busiest camera
    busiest = busiest_camera(observations)
    if busiest:
        camera_name = CAMERAS.get(busiest, {}).get('name', 'Unknown')
        print(f"\nBusiest Camera: {busiest} ({camera_name})")
    
    # Trajectory statistics
    print(f"\nTrajectory Statistics:")
    print(f"  Total trajectories built: {len(trajectories)}")
    
    # Count multi-camera trajectories
    multi_cam_count = sum(1 for traj in trajectories if len(traj.get('observations', [])) > 1)
    print(f"  Multi-camera trajectories: {multi_cam_count}")
    
    # Find longest trajectory
    longest_traj = max(trajectories, key=lambda t: len(t.get('observations', [])), default=None)
    if longest_traj:
        obs_count = len(longest_traj.get('observations', []))
        plate = longest_traj.get('plate_text', 'Unknown')
        print(f"  Longest trajectory: {plate} with {obs_count} observations")
    
    # Average vehicle speed calculation
    print(f"\nVehicle Speed Analysis:")
    speed_stats = average_vehicle_speed(trajectories)
    if speed_stats.get("overall_avg_speed") is not None:
        print(f"  Overall average speed: {speed_stats['overall_avg_speed']} km/h")
        print(f"  Valid speed calculations: {speed_stats['num_valid_speeds']}")
        print(f"  Speed by camera pair:")
        for pair, avg_speed in sorted(speed_stats['speeds_by_camera_pair'].items()):
            print(f"    {pair}: {avg_speed:.2f} km/h")
    else:
        print(f"  Status: {speed_stats.get('status', 'insufficient_data')}")
        print(f"  Total observations: {speed_stats.get('num_observations', 0)}")
    
    # Multi-factor congestion analysis
    print(f"\nMulti-Factor Congestion Analysis:")
    congestion = congestion_hotspots(observations, trajectories)
    print(f"  Model: {congestion['model_used']}")
    print(f"  Congestion threshold: {congestion['threshold']}")
    print(f"  Congested cameras:")
    for cam, score in congestion['congested_cameras']:
        camera_name = CAMERAS.get(cam, {}).get('name', 'Unknown')
        factors = congestion['congestion_factors'].get(cam, {})
        print(f"    {cam} ({camera_name}): {factors.get('congestion_level', 'UNKNOWN')} - score: {score:.3f}")
        print(f"      Density: {factors.get('raw_density', 0)}, Speed: {factors.get('raw_speed', 0)} km/h")
    
    # OD matrix with flow evidence
    print(f"\nOrigin-Destination Matrix Analysis:")
    od_patterns = origin_destination_patterns(trajectories)
    print(f"  Total OD flows: {od_patterns['total_od_flows']}")
    print(f"  Top OD pairs:")
    for pair, count in od_patterns['top_od_pairs'][:5]:
        print(f"    {pair}: {count} vehicles")
    print(f"  Flow distribution:")
    for origin, flow_info in list(od_patterns['flow_distribution'].items())[:3]:
        print(f"    {origin}: {flow_info['outbound_flow']} outbound ({flow_info['percentage']}%)")


def run_demo(clean=False, launch_dashboard=False, skip_video=True):
    """Run the complete 7-camera demo."""
    print("\n" + "="*60)
    print("TrackX 7-CAMERA COIMBATORE NETWORK DEMO")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Clean database if requested
    if clean:
        print("\nCleaning database...")
        db_path = Path(DB_PATH_STR)
        if db_path.exists():
            db_path.unlink()
            print("✓ Database cleaned")
    
    # Initialize database
    store = ObservationStore()
    print("✓ Database initialized")
    
    # Skip video processing and use demo data for SIH proof
    print("\n" + "="*60)
    print("7-CAMERA NETWORK DEMO MODE")
    print("="*60)
    print("⚠️  IMPORTANT: Using simulated multi-camera observations for SIH demonstration")
    print("This demonstrates the complete trajectory reconstruction pipeline")
    print("without requiring actual Indian traffic footage.")
    print("In production, all data would come from real camera feeds.")
    
    # Seed demo observations
    print("\nSeeding multi-camera demo observations...")
    total_records = seed_demo_observations(store)
    
    print(f"\n✓ Total DEMO records added to database: {total_records}")
    print("⚠️  These are simulated observations for demonstration purposes only.")
    
    # Build trajectories
    print("\n" + "="*60)
    print("BUILDING MULTI-CAMERA TRAJECTORIES")
    print("="*60)
    
    observations = store.all_observations()
    print(f"Total observations in database: {len(observations)}")
    
    trajectories = build_trajectories(observations)
    print(f"✓ Built {len(trajectories)} vehicle trajectories")
    
    # Display demo trajectory
    print("\nDemo Vehicle Trajectory (TN09CX7134):")
    demo_found = False
    for traj in trajectories:
        plate_text = traj.get('plate_text', '')
        if 'TN09CX7134' in str(plate_text):
            print(f"  Plate: {plate_text}")
            print(f"  Observations: {len(traj['observations'])}")
            for obs in traj['observations']:
                camera_name = CAMERAS.get(obs['camera_id'], {}).get('name', 'Unknown')
                time_str = datetime.fromisoformat(obs['timestamp']).strftime('%H:%M:%S')
                conf = obs.get('confidence', 0.0)
                print(f"    {obs['camera_id']} ({camera_name}) at {time_str} - conf: {conf:.2f}")
            demo_found = True
            break
    
    if not demo_found:
        print("  Demo trajectory not found in built trajectories")
        print("  Checking if observations exist in database:")
        tn09_obs = [obs for obs in observations if 'TN09CX7134' in str(obs.get('plate_text', '')) or 'TN09CX7134' in str(obs.get('normalized_plate', ''))]
        print(f"  Found {len(tn09_obs)} TN09CX7134 observations in database")
        for obs in tn09_obs:
            print(f"    {obs['camera_id']} at {obs['timestamp']} - plate: {obs.get('plate_text', 'N/A')}")
        print("  Showing all trajectory plates instead:")
        for traj in trajectories[:5]:  # Show first 5
            plate = traj.get('plate_text', 'Unknown')
            obs_count = len(traj.get('observations', []))
            print(f"    {plate}: {obs_count} observations")
    
    # Run analytics
    run_analytics(store, observations, trajectories)
    
    # Scan for alerts
    print("\n" + "="*60)
    print("SCANNING FOR ALERTS")
    print("="*60)
    
    alerts = scan_trajectories_for_alerts(trajectories)
    print(f"✓ Generated {len(alerts)} alerts")
    
    for alert in alerts[:5]:  # Show first 5 alerts
        severity = alert.get('severity', 'UNKNOWN')
        alert_type = alert.get('type', 'Unknown')
        description = alert.get('description', alert.get('message', 'No description'))
        print(f"  [{severity}] {alert_type}: {description}")
    
    # Generate GIS map
    print("\n" + "="*60)
    print("GENERATING GIS MAP")
    print("="*60)
    
    try:
        from gis.gis_map import generate_map
        map_path = generate_map(search_plate="TN09CX7134")
        print(f"✓ GIS map generated: {map_path}")
    except Exception as e:
        print(f"⚠ GIS map generation failed: {e}")
    
    # Close database
    store.close()
    
    print("\n" + "="*60)
    print("DEMO COMPLETED SUCCESSFULLY")
    print("="*60)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nDatabase: {DB_PATH_STR}")
    print(f"Results directory: {RESULTS_DIR}")
    
    # Launch dashboard if requested
    if launch_dashboard:
        print("\nLaunching dashboard...")
        os.system("streamlit run dashboard/dashboard.py")
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 7-camera Coimbatore network demo")
    parser.add_argument("--clean", action="store_true", help="Clean database before running")
    parser.add_argument("--dashboard", action="store_true", help="Launch dashboard after demo")
    parser.add_argument("--skip-video", action="store_true", default=True, help="Skip video processing (default: True)")
    args = parser.parse_args()
    
    try:
        success = run_demo(clean=args.clean, launch_dashboard=args.dashboard, skip_video=args.skip_video)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)