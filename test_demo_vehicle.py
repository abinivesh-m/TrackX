"""
Test script to verify demo vehicle data
"""
from database.observation_store import ObservationStore
from config import DB_PATH_STR
from intelligence.trajectory import build_trajectories

store = ObservationStore(DB_PATH_STR)
obs = store.by_plate('TN09CX7134')
print(f'Found {len(obs)} observations for TN09CX7134')
for o in obs:
    print(f"  {o['camera_id']} @ {o['timestamp']} - {o['plate_text']}")

trajectories = build_trajectories(obs)
print(f'\nBuilt {len(trajectories)} trajectories')
for t in trajectories:
    print(f"  Global Vehicle #{t['global_id']}: {len(t['observations'])} observations, {len(t['match_breakdowns'])} breakdowns")
    # Check if breakdowns have the required fields
    for i, breakdown in enumerate(t['match_breakdowns']):
        print(f"    Breakdown {i}: total={breakdown.get('total', 'MISSING')}, confidence_label={breakdown.get('confidence_label', 'MISSING')}")

store.close()