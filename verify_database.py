import sqlite3
import json
from config import DB_PATH_STR

conn = sqlite3.connect(DB_PATH_STR)
cursor = conn.cursor()

cursor.execute("SELECT * FROM observations")
rows = cursor.fetchall()
columns = [desc[0] for desc in cursor.description]

print(f'Total observations in database: {len(rows)}')

for row in rows:
    obs = dict(zip(columns, row))
    print(f'\n--- Observation ---')
    print(f'Camera: {obs.get("camera_id")}')
    print(f'Timestamp: {obs.get("timestamp")}')
    print(f'Plate: {obs.get("plate_text")}')
    print(f'Raw OCR: {obs.get("raw_plate_text")}')
    print(f'Normalized: {obs.get("normalized_plate")}')
    print(f'OCR Confidence: {obs.get("ocr_confidence")}')
    print(f'Vehicle: {obs.get("vehicle_type")}')
    print(f'Track ID: {obs.get("track_id")}')
    print(f'Data Source: {obs.get("data_source")}')
    print(f'Plate Status: {obs.get("plate_status")}')

conn.close()
