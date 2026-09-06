"""
generate_multi_camera_demo.py

Generate realistic multi-camera trajectory test data for TrackX SIH demo.

This creates auditable vehicle observations across 7 Coimbatore cameras
with realistic timing, metadata, and geographic separation to demonstrate
the multi-camera trajectory tracking capability.

Usage:
    python -m scripts.generate_multi_camera_demo
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.observation_store import ObservationStore
from network.camera_network import CAMERAS
from config import DB_PATH_STR


def generate_vehicle_trajectory(vehicle_plate, vehicle_type="Car", start_camera="CAM_01"):
    """
    Generate a realistic vehicle trajectory across multiple cameras.

    Args:
        vehicle_plate: License plate number
        vehicle_type: Type of vehicle (Car, Motorcycle, Truck, etc.)
        start_camera: Starting camera ID

    Returns:
        List of observation dictionaries
    """
    observations = []
    current_time = datetime.now()

    # Define realistic route through Coimbatore with specific timing
    route = [
        ("CAM_01", 0),    # Start at Gandhipuram Junction
        ("CAM_03", 216),  # 3m 36s later at RS Puram
        ("CAM_05", 273),  # 4m 33s later at Town Hall
        ("CAM_07", 402),  # 6m 42s later at Singanallur
    ]

    # Generate observations for each camera in the route
    for i, (camera_id, time_delay_seconds) in enumerate(route):
        camera_info = CAMERAS[camera_id]

        # Calculate realistic time between cameras
        if i > 0:
            current_time += timedelta(seconds=time_delay_seconds)

        # Create observation with enhanced metadata
        observation = {
            "camera_id": camera_id,
            "timestamp": current_time.isoformat(),
            "source_file": f"video_stream_{camera_id}_{vehicle_plate}.mp4",
            "source_type": "video",
            "frame_index": i * 150,  # Simulated frame index
            "vehicle_bbox": [100 + i*10, 100 + i*5, 300 + i*15, 300 + i*10],  # Varying bbox
            "vehicle_class": vehicle_type,
            "vehicle_confidence": 0.95 + (i * 0.01),  # Slight confidence variation
            "track_id": f"{vehicle_plate}_{i}",
            "plate_text": vehicle_plate,
            "normalized_plate": vehicle_plate.replace(" ", "").upper(),
            "normalized_plate_text": vehicle_plate.replace(" ", "").upper(),
            "ocr_confidence": 0.92 + (i * 0.01),  # Slight OCR confidence variation
            "plate_status": "detected",
            "plate_bbox": [150 + i*5, 150 + i*3, 250 + i*8, 200 + i*5],
            "lat": camera_info["lat"],
            "long": camera_info["long"],
            "appearance_vector": [0.1 + i*0.05, 0.2 + i*0.03, 0.3 + i*0.02, 0.4 + i*0.01],
            "source": "multi_camera_stream",
            "data_source": "REALISTIC_MULTI_CAMERA_DEMO",
            "camera_location": camera_info["location"],
            "camera_direction": camera_info["direction"],
            "camera_fov": camera_info["fov"],
            "video_timestamp": current_time.isoformat()
        }

        observations.append(observation)

    return observations


def generate_multiple_trajectories():
    """Generate multiple vehicle trajectories to demonstrate the system."""
    all_observations = []

    # Vehicle 1: Complete multi-camera route (CAR) - Main demo vehicle
    vehicle1_obs = generate_vehicle_trajectory("TN38AB1234", "Car", "CAM_01")
    all_observations.extend(vehicle1_obs)

    # Vehicle 2: Alternative route (MOTORCYCLE)
    vehicle2_obs = generate_vehicle_trajectory("KA01CD5678", "Motorcycle", "CAM_02")
    # Create different timing for motorcycle
    for i, obs in enumerate(vehicle2_obs):
        obs["ocr_confidence"] = 0.89 + (i * 0.02)  # Slightly lower OCR for motorcycle
        obs["vehicle_confidence"] = 0.93 + (i * 0.01)
    all_observations.extend(vehicle2_obs)

    # Vehicle 3: Heavy vehicle route (TRUCK)
    vehicle3_obs = generate_vehicle_trajectory("MH12EF9012", "Truck", "CAM_03")
    # Create slower timing for truck
    for i, obs in enumerate(vehicle3_obs):
        obs["ocr_confidence"] = 0.90 + (i * 0.015)
        obs["vehicle_confidence"] = 0.94 + (i * 0.01)
    all_observations.extend(vehicle3_obs)

    # Vehicle 4: Additional vehicle for variety (VAN)
    vehicle4_obs = generate_vehicle_trajectory("TN09AB1234", "Van", "CAM_04")
    all_observations.extend(vehicle4_obs)

    return all_observations


def main():
    print("Generating Realistic Multi-Camera Trajectory Demo Data")
    print("=" * 60)

    # Generate observations
    observations = generate_multiple_trajectories()
    print(f"Generated {len(observations)} observations across multiple cameras")

    # Show detailed trajectory summary
    print("\nDetailed Trajectory Summary:")
    from collections import defaultdict
    vehicle_trajectories = defaultdict(list)

    for obs in observations:
        vehicle_trajectories[obs['plate_text']].append(obs)

    for plate, traj_obs in sorted(vehicle_trajectories.items()):
        traj_obs_sorted = sorted(traj_obs, key=lambda x: x['timestamp'])
        print(f"\nVehicle: {plate}")
        print(f"{'Time':<12} {'Camera':<8} {'Location':<25} {'Confidence':<12} {'Type':<10}")
        print("-" * 70)
        for obs in traj_obs_sorted:
            camera_name = CAMERAS[obs['camera_id']]['name']
            location = obs.get('camera_location', 'Unknown')
            time_str = obs['timestamp'].split('T')[1][:8]
            confidence = f"{obs['ocr_confidence']:.1%}"
            vehicle_type = obs['vehicle_class']
            print(f"{time_str:<12} {obs['camera_id']:<8} {location:<25} {confidence:<12} {vehicle_type:<10}")

    # Store in database
    print(f"\nStoring observations in database: {DB_PATH_STR}")
    store = ObservationStore(db_path=DB_PATH_STR)

    try:
        count = store.add_visual_observations(observations)
        print(f"Successfully stored {count} observations in database")
    except Exception as e:
        print(f"Error storing observations: {e}")
        return 1
    finally:
        store.close()

    print("\n" + "=" * 60)
    print("Realistic Multi-Camera Trajectory Demo Data Generation Completed!")
    print("\nFor SIH Demo:")
    print("1. Run the dashboard: streamlit run dashboard/dashboard.py")
    print("2. Search for 'TN38AB1234' to see complete 4-camera trajectory")
    print("3. Observe realistic timing: 3m 36s -> 4m 33s -> 6m 42s between cameras")
    print("4. Check GIS map for Coimbatore route visualization")
    print("5. Verify auditable search results with metadata")

    return 0


if __name__ == "__main__":
    sys.exit(main())