from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories
from network.camera_network import CAMERAS

# Get observations
store = ObservationStore()
observations = store.all_observations()

# Check for TN09CX7134
target_plate = 'TN09CX7134'
matching_obs = [obs for obs in observations if obs.get('plate_text') == target_plate or obs.get('normalized_plate') == target_plate]

print(f'Total observations in database: {len(observations)}')
print(f'Observations for {target_plate}: {len(matching_obs)}')

if matching_obs:
    print(f'\nObservations for {target_plate}:')
    for obs in matching_obs:
        cam_id = obs['camera_id']
        cam_info = CAMERAS.get(cam_id, {})
        print(f'  Camera: {cam_id} - {cam_info.get("name", "Unknown")}')
        print(f'    Location: {cam_info.get("location", "Unknown")}')
        print(f'    Coordinates: ({cam_info.get("lat", 0):.4f}, {cam_info.get("long", 0):.4f})')
        print(f'    Timestamp: {obs["timestamp"]}')
        print(f'    Plate: {obs.get("plate_text", "UNKNOWN")}')
        print()

# Build trajectories to see if they connect
trajectories = build_trajectories(observations)
target_trajectories = [t for t in trajectories if any(o.get('plate_text') == target_plate or o.get('normalized_plate') == target_plate for o in t['observations'])]

print(f'Total trajectories built: {len(trajectories)}')
print(f'Trajectories for {target_plate}: {len(target_trajectories)}')

if target_trajectories:
    for i, traj in enumerate(target_trajectories):
        print(f'\nTrajectory {i+1}:')
        print(f'  Total observations: {len(traj["observations"])}')
        print(f'  Cameras visited: {sorted(set(o["camera_id"] for o in traj["observations"]))}')
        for obs in traj['observations']:
            cam_id = obs['camera_id']
            cam_info = CAMERAS.get(cam_id, {})
            print(f'    {cam_id} ({cam_info.get("name", "Unknown")}) at {obs["timestamp"]}')

# Check camera distribution
print(f'\nCamera Network Analysis:')
print(f'Total cameras in network: {len(CAMERAS)}')
print(f'Camera locations:')
for cam_id, info in CAMERAS.items():
    print(f'  {cam_id}: {info.get("name", "Unknown")} at ({info["lat"]:.4f}, {info["long"]:.4f})')

store.close()