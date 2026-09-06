from database.observation_store import ObservationStore

store = ObservationStore()
db_observations = store.all_observations()

print("Simulating dashboard camera selection with actual data:")
print("=" * 80)

# Test what happens when user selects CAM_01
camera_id = "CAM_01"
print(f"\nUser selects: {camera_id}")

camera_obs = [o for o in db_observations if o.get("camera_id") == camera_id]
print(f"Total observations for {camera_id}: {len(camera_obs)}")

# Count by pipeline type
visual_pipeline_count = sum(1 for o in camera_obs if o.get('plate_status') is not None)
pipeline_count = sum(1 for o in camera_obs if o.get('plate_status') is None)

print(f"From visual_pipeline (has plate_status): {visual_pipeline_count}")
print(f"From pipeline.py (no plate_status): {pipeline_count}")

if camera_obs:
    def sort_key(o):
        plate_status = o.get("plate_status")
        if plate_status == "detected":
            status_priority = 0
        elif plate_status == "detected_no_ocr":
            status_priority = 1
        elif plate_status == "ocr_failed":
            status_priority = 2
        else:
            status_priority = 3  # This includes None!
        return (status_priority, -int(o.get("id") or 0))
    
    obs = min(camera_obs, key=sort_key)
    
    print(f"\nDashboard would select observation ID: {obs['id']}")
    print(f"  plate_status: {obs.get('plate_status')}")
    print(f"  plate_text: {obs.get('plate_text')}")
    print(f"  source_file: {obs.get('source_file')}")
    print(f"  source: {obs.get('source')}")
    print(f"  track_id: {obs.get('track_id')}")
    print(f"  sort_key: {sort_key(obs)}")
    
    # Show what would be displayed
    if obs.get('plate_status') == 'detected':
        display = f"Plate: {obs.get('normalized_plate')} (OCR confidence: {obs.get('ocr_confidence')})"
    elif obs.get('plate_status') is None:
        display = "Plate: NOT DETECTED (plate_status is None - treated as failed)"
    else:
        display = f"Plate status: {obs.get('plate_status')}"
    
    print(f"  Dashboard display: {display}")

store.close()
