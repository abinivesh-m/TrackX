from database.observation_store import ObservationStore
from network.camera_network import CAMERAS

store = ObservationStore()
observations = store.all_observations()

print(f'Updating coordinates for {len(observations)} observations...')

updated_count = 0
for obs in observations:
    cam_id = obs['camera_id']
    cam_info = CAMERAS.get(cam_id)
    
    if cam_info:
        new_lat = cam_info['lat']
        new_long = cam_info['long']
        old_lat = obs.get('lat')
        old_long = obs.get('long')
        
        if old_lat != new_lat or old_long != new_long:
            # Update the observation
            store.conn.execute(
                'UPDATE observations SET lat = ?, long = ? WHERE id = ?',
                (new_lat, new_long, obs['id'])
            )
            updated_count += 1
            print(f'Updated {cam_id}: ({old_lat}, {old_long}) -> ({new_lat}, {new_long})')

store.conn.commit()
print(f'\nTotal updated: {updated_count} observations')
store.close()