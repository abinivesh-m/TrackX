"""
Import SIH ANPR dataset from Excel to TrackX database

This script imports vehicle data from the Excel dataset into the TrackX observation database.
"""

import pandas as pd
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.observation_store import ObservationStore
from network.camera_network import CAMERAS
from config import RESULTS_DIR

def import_excel_to_database(excel_path):
    """Import vehicle data from Excel to TrackX database"""
    
    print(f"Reading Excel file: {excel_path}")
    
    try:
        # Read Excel file
        df = pd.read_excel(excel_path)
        print(f"Found {len(df)} rows in Excel file")
        print(f"Columns: {df.columns.tolist()}")
        
        # Show first few rows
        print("\nFirst 5 rows:")
        print(df.head())
        
        # Initialize database
        db_path = str(RESULTS_DIR / "observations.db")
        store = ObservationStore(db_path=db_path)
        
        # Convert Excel data to observations
        observations = []
        
        for idx, row in df.iterrows():
            # Map Excel columns to observation schema
            # This is a generic mapping - adjust based on your Excel structure
            obs = {
                "normalized_plate_text": str(row.get('plate_number', 'UNKNOWN')).upper(),
                "raw_plate_text": str(row.get('plate_number', 'UNKNOWN')),
                "normalized_plate": str(row.get('plate_number', 'UNKNOWN')).upper(),
                "ocr_confidence": float(row.get('confidence', 0.9)),
                "confidence": float(row.get('confidence', 0.9)),
                "plate_status": "detected",
                "camera_id": str(row.get('camera_id', 'CAM_01')),
                "timestamp": str(row.get('timestamp', datetime.now().isoformat())),
                "lat": float(row.get('latitude', 11.0168)),
                "long": float(row.get('longitude', 76.9558)),
                "track_id": str(row.get('track_id', f"EXCEL-{idx}")),
                "vehicle_class": str(row.get('vehicle_type', 'car')),
                "vehicle_type": str(row.get('vehicle_type', 'car')),
                "vehicle_confidence": 0.9,
                "vehicle_bbox": [80, 120, 420, 640],
                "plate_bbox": [200, 130, 320, 180],
                "source_file": str(row.get('source_file', 'excel_import')),
                "source_type": "excel",
                "frame_index": int(row.get('frame_index', 0)),
                "source": "excel_import",
                "data_source": "EXCEL_DATASET",
            }
            
            # Use camera coordinates if camera_id is valid
            cam_id = obs["camera_id"]
            if cam_id in CAMERAS:
                obs["lat"] = CAMERAS[cam_id]["lat"]
                obs["long"] = CAMERAS[cam_id]["long"]
            
            observations.append(obs)
        
        # Add observations to database
        if observations:
            store.add_visual_observations(observations)
            print(f"\n✅ Successfully imported {len(observations)} observations to database")
            print(f"Database location: {db_path}")
        else:
            print("⚠️ No observations to import")
        
        store.close()
        
    except Exception as e:
        print(f"❌ Error importing Excel data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    excel_path = r"C:\Users\abini\Downloads\SIH_ANPR_10000_vehicle_demo_dataset.xlsx"
    
    if os.path.exists(excel_path):
        import_excel_to_database(excel_path)
    else:
        print(f"Excel file not found: {excel_path}")
        print("Please update the path in the script or provide the correct path.")
