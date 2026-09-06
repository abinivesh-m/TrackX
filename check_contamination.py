import json

# Load the dataset
with open('data/ocr_eval/clean_evaluation_dataset.json', 'r') as f:
    data = json.load(f)

# Check for CAM_TEST contamination
cam_test_entries = [entry for entry in data if 'CAM_TEST' in entry['image']]
print(f"CAM_TEST entries (test fixture contamination): {len(cam_test_entries)}")
if cam_test_entries:
    print("Sample CAM_TEST entries:")
    for entry in cam_test_entries[:5]:
        print(f"  {entry['image']} - GT: {entry['ground_truth']}")

# Check for very small crops (unusable)
small_crops = []
for entry in data:
    # Extract size from filename patterns or check actual images
    # For now, let's just flag suspiciously small dimensions based on our inspection
    if '15x10' in str(entry) or '20x15' in str(entry) or '20x20' in str(entry):
        small_crops.append(entry)

print(f"\nPotentially unusable small crops: {len(small_crops)}")

# Check for frameNone (tracking failures)
frame_none_entries = [entry for entry in data if 'frameNone' in entry['image']]
print(f"\nframeNone entries (tracking failures): {len(frame_none_entries)}")

# Check for trackfallback (fallback tracking)
track_fallback_entries = [entry for entry in data if 'trackfallback' in entry['image']]
print(f"trackfallback entries (fallback tracking): {len(track_fallback_entries)}")

# Summary
print(f"\nTotal entries: {len(data)}")
print(f"Potentially contaminated or problematic: {len(cam_test_entries) + len(small_crops) + len(frame_none_entries) + len(track_fallback_entries)}")
