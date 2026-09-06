"""
Audit the OCR dataset for quality and authenticity issues.
Check for ground truth alignment, image quality, and potential data problems.
"""

import json
import os
import cv2
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_PATH = os.path.join(PROJECT_ROOT, "data", "ocr_eval", "clean_evaluation_dataset.json")

# Load dataset
with open(DATASET_PATH, 'r') as f:
    dataset = json.load(f)

# Handle both list and dict formats
if isinstance(dataset, list):
    entries = dataset
    metadata = {}
else:
    entries = dataset.get("entries", [])
    metadata = dataset.get("metadata", {})

print("="*60)
print("OCR DATASET QUALITY AUDIT")
print("="*60)
print(f"Total entries: {len(entries)}")
print(f"Metadata: {metadata}")
print()

# Check for various quality issues
issues = {
    'missing_images': [],
    'invalid_images': [],
    'blank_ground_truth': [],
    'short_ground_truth': [],
    'suspicious_patterns': [],
    'test_artifacts': [],
    'duplicate_hashes': [],
}

hash_counts = {}
suspicious_prefixes = ['CAM_TEST', 'test_', 'TEST', 'unit', 'UNIT']

for i, entry in enumerate(entries):
    image_path = entry.get("image")  # Changed from "image_path" to "image"
    ground_truth = entry.get("ground_truth")
    image_hash = entry.get("image_hash")
    
    # Check for missing images
    if not os.path.exists(image_path):
        issues['missing_images'].append((i, image_path))
        continue
    
    # Check for test artifacts
    if any(prefix in image_path.upper() for prefix in suspicious_prefixes):
        issues['test_artifacts'].append((i, image_path))
    
    # Check for blank or invalid ground truth
    if not ground_truth or len(ground_truth.strip()) == 0:
        issues['blank_ground_truth'].append((i, image_path, ground_truth))
    
    # Check for suspiciously short ground truth
    if ground_truth and len(ground_truth) < 5:
        issues['short_ground_truth'].append((i, image_path, ground_truth))
    
    # Check for duplicate hashes
    if image_hash:
        if image_hash in hash_counts:
            hash_counts[image_hash].append((i, image_path))
        else:
            hash_counts[image_hash] = [(i, image_path)]
    
    # Try to load and validate image
    try:
        img = cv2.imread(image_path)
        if img is None:
            issues['invalid_images'].append((i, image_path))
        else:
            h, w = img.shape[:2]
            # Check for suspiciously small images
            if h < 20 or w < 50:
                issues['suspicious_patterns'].append((i, image_path, f"Small size: {h}x{w}"))
    except Exception as e:
        issues['invalid_images'].append((i, image_path))

# Find duplicate hashes
for hash_val, occurrences in hash_counts.items():
    if len(occurrences) > 1:
        issues['duplicate_hashes'].append((hash_val, occurrences))

# Report findings
print("ISSUES FOUND:")
print(f"  Missing images: {len(issues['missing_images'])}")
print(f"  Invalid/corrupt images: {len(issues['invalid_images'])}")
print(f"  Blank ground truth: {len(issues['blank_ground_truth'])}")
print(f"  Short ground truth (<5 chars): {len(issues['short_ground_truth'])}")
print(f"  Test artifacts (CAM_TEST, etc.): {len(issues['test_artifacts'])}")
print(f"  Suspicious patterns: {len(issues['suspicious_patterns'])}")
print(f"  Duplicate image hashes: {len(issues['duplicate_hashes'])}")

print("\n" + "="*60)
print("DETAILED ISSUES")
print("="*60)

if issues['missing_images']:
    print(f"\nMISSING IMAGES ({len(issues['missing_images'])}):")
    for i, path in issues['missing_images'][:10]:  # Show first 10
        print(f"  [{i}] {path}")

if issues['test_artifacts']:
    print(f"\nTEST ARTIFACTS ({len(issues['test_artifacts'])}):")
    for i, path in issues['test_artifacts'][:10]:
        print(f"  [{i}] {path}")

if issues['duplicate_hashes']:
    print(f"\nDUPLICATE HASHES ({len(issues['duplicate_hashes'])}):")
    for hash_val, occurrences in issues['duplicate_hashes'][:5]:
        print(f"  Hash: {hash_val}")
        for i, path in occurrences:
            print(f"    [{i}] {path}")

# Save audit report
audit_report = {
    'timestamp': '2026-08-26T14:10:00',
    'total_entries': len(entries),
    'metadata': metadata,
    'issues': {k: len(v) for k, v in issues.items()},
    'details': issues
}

with open(os.path.join(PROJECT_ROOT, "outputs", "ocr_dataset_audit.json"), 'w') as f:
    json.dump(audit_report, f, indent=2)

print(f"\nDetailed audit saved to: outputs/ocr_dataset_audit.json")
print("="*60)
