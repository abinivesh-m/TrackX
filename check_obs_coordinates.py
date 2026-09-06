from database.observation_store import ObservationStore
from network.camera_network import CAMERAS

store = ObservationStore()
obs = store.by_plate('TN09CX7134')

print(f'TN09CX7134 Trajectory Analysis:')
print(f'Total observations: {len(obs)}\n')

for o in obs:
    cam_id = o['camera_id']
    obs_lat = o.get('lat')
    obs_long = o.get('long')
    cam_info = CAMERAS.get(cam_id, {})
    cam_lat = cam_info.get('lat')
    cam_long = cam_info.get('long')
    
    print(f'Camera: {cam_id} - {cam_info.get("name", "Unknown")}')
    print(f'  Timestamp: {o["timestamp"]}')
    print(f'  Observation coords: ({obs_lat}, {obs_long})')
    print(f'  Camera definition coords: ({cam_lat}, {cam_long})')
    print(f'  Coordinates match: {obs_lat == cam_lat and obs_long == cam_long}')
    print()

store.close()