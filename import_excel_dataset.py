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
from database.blacklist_store import BlacklistStore
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
            # Map Excel columns to observation schema based on actual Excel structure
            plate_number = str(row.get('plate_number', f'EXCEL-{idx}')).upper()
            vehicle_type = str(row.get('vehicle_type', 'car'))
            state_code = str(row.get('state_code', 'TN'))
            
            # Generate a realistic timestamp based on index
            base_time = datetime(2026, 9, 7, 9, 0, 0)
            timestamp = (base_time + pd.Timedelta(minutes=idx*0.5)).isoformat()
            
            # Distribute across cameras
            camera_id = f"CAM_{(idx % 7) + 1:02d}"
            
            obs = {
                "normalized_plate_text": plate_number,
                "raw_plate_text": plate_number,
                "normalized_plate": plate_number,
                "ocr_confidence": 0.92,
                "confidence": 0.92,
                "plate_status": "detected",
                "camera_id": camera_id,
                "timestamp": timestamp,
                "lat": CAMERAS[camera_id]["lat"],
                "long": CAMERAS[camera_id]["long"],
                "track_id": f"EXCEL-{idx}",
                "vehicle_class": vehicle_type,
                "vehicle_type": vehicle_type,
                "vehicle_confidence": 0.9,
                "vehicle_bbox": [80, 120, 420, 640],
                "plate_bbox": [200, 130, 320, 180],
                "source_file": f"excel_dataset_{idx}.jpg",
                "source_type": "excel",
                "frame_index": idx % 100,
                "source": "excel_import",
                "data_source": "SIH_ANPR_DATASET",
            }
            
            observations.append(obs)
        
        # Add observations to database
        if observations:
            store.add_visual_observations(observations)
            print(f"\nSuccessfully imported {len(observations)} observations to database")
            print(f"Database location: {db_path}")
            
            # Add watchlist vehicles to blacklist
            blacklist_store = BlacklistStore(db_path=db_path)
            watchlist_count = 0
            
            for idx, row in df.iterrows():
                watchlist_status = str(row.get('watchlist_status', '')).upper()
                if watchlist_status in ['YES', 'TRUE', '1', 'WATCHLIST']:
                    plate_number = str(row.get('plate_number', '')).upper()
                    watchlist_reason = str(row.get('watchlist_reason', 'Excel dataset watchlist'))
                    
                    if plate_number:
                        try:
                            blacklist_store.add_plate(
                                plate_number,
                                description=watchlist_reason,
                                severity="HIGH"
                            )
                            watchlist_count += 1
                        except:
                            pass  # Plate might already exist
            
            blacklist_store.close()
            print(f"Added {watchlist_count} vehicles to blacklist from watchlist")
            
        else:
            print("No observations to import")
        
        store.close()
        
    except Exception as e:
        print(f"Error importing Excel data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    excel_path = r"C:\Users\abini\Downloads\SIH_ANPR_10000_vehicle_demo_dataset.xlsx"
    
    if os.path.exists(excel_path):
        import_excel_to_database(excel_path)
    else:
        print(f"Excel file not found: {excel_path}")
        print("Please update the path in the script or provide the correct path.")
