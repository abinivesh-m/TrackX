"""
seed_alert_demo.py

Comprehensive demo data seeding script for the TrackX alert system.

This script creates realistic demo data to demonstrate:
1. Blacklisted vehicles with different severities
2. Sample observations across multiple cameras
3. Vehicle trajectories that trigger various alert types
4. Route anomalies and suspicious patterns

Usage:
    python demo/seed_alert_demo.py [--clean]

Options:
    --clean: Clear existing demo data before seeding
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.blacklist_store import BlacklistStore
from database.observation_store import ObservationStore
from database.alert_store import AlertStore
from config import DB_PATH_STR

# Demo blacklist plates with realistic scenarios
BLACKLISTED_PLATES = [
    {
        "plate": "TN10AB1234",
        "description": "Reported stolen vehicle - Red Honda City",
        "severity": "HIGH"
    },
    {
        "plate": "KA05CD5678",
        "description": "Wanted in hit-and-run case",
        "severity": "HIGH"
    },
    {
        "plate": "MH02EF9012",
        "description": "Suspicious vehicle - known trafficking suspect",
        "severity": "HIGH"
    },
    {
        "plate": "DL03GH3456",
        "description": "Vehicle involved in robbery investigation",
        "severity": "MEDIUM"
    },
    {
        "plate": "AP28IJ7890",
        "description": "Expired registration - repeated violations",
        "severity": "LOW"
    }
]

# Camera network coordinates (from network.camera_network.CAMERAS)
CAMERA_LOCATIONS = {
    "CAM_01": {"lat": 13.0827, "long": 80.2707, "name": "Anna Salai Junction"},
    "CAM_02": {"lat": 13.0845, "long": 80.2720, "name": "Mount Road Intersection"},
    "CAM_03": {"lat": 13.0800, "long": 80.2680, "name": "Marina Beach Road"},
    "CAM_04": {"lat": 13.0860, "long": 80.2750, "name": "T Nagar Signal"},
    "CAM_05": {"lat": 13.0780, "long": 80.2660, "name": "Chepauk Area"}
}

# Sample observations creating realistic scenarios
def create_demo_observations():
    """Create realistic demo observations across cameras."""
    observations = []
    base_time = datetime.now() - timedelta(hours=2)
    
    # Scenario 1: Blacklisted vehicle TN10AB1234 moving across city
    blacklisted_traj = [
        {"camera": "CAM_01", "time_offset": 0, "plate": "TN10AB1234", "confidence": 0.92},
        {"camera": "CAM_02", "time_offset": 15, "plate": "TN10AB1234", "confidence": 0.89},
        {"camera": "CAM_03", "time_offset": 30, "plate": "TN10AB1234", "confidence": 0.94},
    ]
    
    # Scenario 2: Normal vehicle for comparison
    normal_traj = [
        {"camera": "CAM_01", "time_offset": 5, "plate": "TN11XY5678", "confidence": 0.95},
        {"camera": "CAM_04", "time_offset": 20, "plate": "TN11XY5678", "confidence": 0.91},
    ]
    
    # Scenario 3: Another blacklisted vehicle KA05CD5678
    blacklisted_traj2 = [
        {"camera": "CAM_02", "time_offset": 10, "plate": "KA05CD5678", "confidence": 0.88},
        {"camera": "CAM_05", "time_offset": 25, "plate": "KA05CD5678", "confidence": 0.90},
    ]
    
    # Scenario 4: Vehicle with impossible travel (anomaly demo)
    anomaly_traj = [
        {"camera": "CAM_01", "time_offset": 0, "plate": "TN33ZZ9999", "confidence": 0.93},
        {"camera": "CAM_05", "time_offset": 2, "plate": "TN33ZZ9999", "confidence": 0.91},  # Too fast!
    ]
    
    # Scenario 5: Repeated camera sighting (loitering)
    loitering_traj = [
        {"camera": "CAM_03", "time_offset": 0, "plate": "TN44AA1111", "confidence": 0.89},
        {"camera": "CAM_03", "time_offset": 10, "plate": "TN44AA1111", "confidence": 0.92},
        {"camera": "CAM_03", "time_offset": 20, "plate": "TN44AA1111", "confidence": 0.90},
    ]
    
    # Scenario 6: Additional normal traffic
    additional_traffic = [
        {"camera": "CAM_01", "time_offset": 2, "plate": "TN22BB3333", "confidence": 0.87},
        {"camera": "CAM_02", "time_offset": 18, "plate": "TN22BB3333", "confidence": 0.91},
        {"camera": "CAM_04", "time_offset": 35, "plate": "TN22BB3333", "confidence": 0.88},
        {"camera": "CAM_02", "time_offset": 8, "plate": "TN55CC4444", "confidence": 0.94},
        {"camera": "CAM_03", "time_offset": 22, "plate": "TN55CC4444", "confidence": 0.89},
        {"camera": "CAM_05", "time_offset": 12, "plate": "TN66DD5555", "confidence": 0.92},
    ]
    
    all_trajectories = [blacklisted_traj, normal_traj, blacklisted_traj2, 
                       anomaly_traj, loitering_traj, additional_traffic]
    
    for traj in all_trajectories:
        for obs in traj:
            camera_info = CAMERA_LOCATIONS[obs["camera"]]
            timestamp = (base_time + timedelta(minutes=obs["time_offset"])).isoformat()
            
            observations.append({
                "plate_text": obs["plate"],
                "normalized_plate": obs["plate"].replace(" ", "").upper(),
                "confidence": obs["confidence"],
                "camera_id": obs["camera"],
                "timestamp": timestamp,
                "lat": camera_info["lat"],
                "long": camera_info["long"],
                "source": "demo_synthetic",
                "direction": "unknown",
                "data_source": "SYNTHETIC_DEMO",
                "vehicle_type": "car",
                "track_id": f"track_{obs['plate']}_{obs['camera']}",
                "raw_plate_text": obs["plate"],
                "ocr_confidence": obs["confidence"],
                "plate_status": "detected",
                "vehicle_bbox": [100, 150, 300, 350],
                "plate_bbox": [120, 200, 280, 240],
                "vehicle_confidence": 0.95,
                "frame_index": 1,
                "source_file": f"demo/{obs['camera']}.jpg",
                "source_type": "image"
            })
    
    return observations

def seed_blacklist(store, clean=False):
    """Seed blacklist with demo plates."""
    if clean:
        print("[CLEANING] Clearing existing blacklist...")
        # Note: BlacklistStore doesn't have a clear_all method, so we'll just add new entries
    
    print("[SEEDING] Blacklist with demo plates...")
    for plate_info in BLACKLISTED_PLATES:
        plate_id = store.add_plate(
            plate_info["plate"],
            description=plate_info["description"],
            severity=plate_info["severity"]
        )
        print(f"  [ADDED] {plate_info['plate']} ({plate_info['severity']}) - ID: {plate_id}")
    
    active = store.all_active()
    print(f"Total active blacklist entries: {len(active)}")

def seed_observations(store, clean=False):
    """Seed observations with demo data."""
    if clean:
        print("[CLEANING] Clearing existing observations...")
        # Delete all observations for demo cameras
        for camera_id in CAMERA_LOCATIONS.keys():
            deleted = store.delete_camera_observations(camera_id)
            print(f"  [DELETED] {deleted} observations from {camera_id}")
    
    print("[SEEDING] Observations with demo data...")
    observations = create_demo_observations()
    
    for obs in observations:
        store.add(obs)
    
    print(f"Added {len(observations)} demo observations")
    
    # Verify
    all_obs = store.all_observations()
    print(f"Total observations in database: {len(all_obs)}")

def seed_alerts(store, clean=False):
    """Seed alerts with demo data (optional - alerts are usually generated dynamically)."""
    if clean:
        print("[CLEANING] Clearing existing alerts...")
        # AlertStore doesn't have a clear_all method
    
    print("[INFO] Alerts are typically generated dynamically from trajectories.")
    print("[INFO] Use the dashboard or run_demo.py to generate alerts from observations.")

def main():
    parser = argparse.ArgumentParser(description="Seed TrackX alert system with demo data")
    parser.add_argument("--clean", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()
    
    print("="*60)
    print("TrackX Alert System Demo Data Seeding")
    print("="*60)
    print(f"Database: {DB_PATH_STR}")
    print(f"Clean existing data: {args.clean}")
    print("="*60)
    
    # Initialize stores
    blacklist_store = BlacklistStore()
    observation_store = ObservationStore()
    alert_store = AlertStore()
    
    try:
        # Seed blacklist
        print("\n[1/3] Seeding Blacklist...")
        seed_blacklist(blacklist_store, args.clean)
        
        # Seed observations
        print("\n[2/3] Seeding Observations...")
        seed_observations(observation_store, args.clean)
        
        # Seed alerts (informational)
        print("\n[3/3] Alert System Info...")
        seed_alerts(alert_store, args.clean)
        
        # Summary
        print("\n" + "="*60)
        print("Demo data seeding completed successfully!")
        print("="*60)
        print(f"Blacklisted plates: {len(blacklist_store.all_active())}")
        print(f"Observations: {len(observation_store.all_observations())}")
        print(f"Database: {DB_PATH_STR}")
        print("\nNext steps:")
        print("  1. Run: python run_demo.py --visual-only")
        print("  2. Or start dashboard: streamlit run dashboard/dashboard.py")
        print("  3. View alerts in the Alerts tab")
        print("="*60)
        
    except Exception as e:
        print(f"\nERROR: Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        blacklist_store.close()
        observation_store.close()
        alert_store.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
