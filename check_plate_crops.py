from database.observation_store import ObservationStore

store = ObservationStore()
obs = store.by_plate('TN09CX7134')

print(f'Total observations for TN09CX7134: {len(obs)}')
print('\nPlate crop paths:')
for o in obs:
    print(f'Camera: {o["camera_id"]}, Timestamp: {o["timestamp"]}')
    print(f'  Plate crop path: {o.get("plate_crop_path")}')
    print(f'  Annotated output: {o.get("annotated_output")}')
    print()

store.close()