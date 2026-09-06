import json
import os
from pathlib import Path

# Load the dataset
with open('data/ocr_eval/clean_evaluation_dataset.json', 'r') as f:
    data = json.load(f)

print(f"Total entries: {len(data)}")
print(f"Unique ground truths: {len(set(d['ground_truth'] for d in data))}")
print(f"Unique images: {len(set(d['image'] for d in data))}")

# Check for missing images
missing_images = []
for entry in data:
    image_path = entry['image']
    if not os.path.exists(image_path):
        missing_images.append(image_path)

print(f"Missing images: {len(missing_images)}")
if missing_images[:5]:
    print("Sample missing images:")
    for img in missing_images[:5]:
        print(f"  {img}")

# Check for potential duplicates (same ground truth, similar paths)
from collections import defaultdict
gt_to_entries = defaultdict(list)
for entry in data:
    gt_to_entries[entry['ground_truth']].append(entry)

duplicates = {gt: entries for gt, entries in gt_to_entries.items() if len(entries) > 1}
print(f"Ground truths with multiple entries: {len(duplicates)}")

# Check for suspicious patterns
suspicious = []
for entry in data:
    gt = entry['ground_truth']
    # Check for obviously fake patterns
    if len(gt) != 10:  # Indian plates are typically 10 chars
        suspicious.append(entry)
    # Check for repeated characters
    if len(set(gt)) < 3:
        suspicious.append(entry)

print(f"Suspicious entries (wrong length or low diversity): {len(suspicious)}")
