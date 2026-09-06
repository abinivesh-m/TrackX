"""
Create clean train/validation/test split from the expanded dataset.
Ensure no data leakage between splits using ground truth uniqueness.
"""

import json
import random
from pathlib import Path
from collections import defaultdict

def load_current_manifest():
    """Load the current dataset manifest."""
    manifest_path = Path("data/ocr_eval/dataset_audit_manifest.json")
    with open(manifest_path, 'r') as f:
        return json.load(f)

def analyze_ground_truths(manifest):
    """Analyze ground truth distribution and duplicates."""
    gt_counts = defaultdict(list)
    
    for entry in manifest["usable_manifest"]:
        gt = entry["ground_truth"]
        gt_counts[gt].append(entry)
    
    print("Ground Truth Analysis:")
    print(f"Total unique ground truths: {len(gt_counts)}")
    print(f"Total entries: {len(manifest['usable_manifest'])}")
    
    # Show some statistics
    duplicate_counts = {gt: len(entries) for gt, entries in gt_counts.items() if len(entries) > 1}
    print(f"Ground truths with duplicates: {len(duplicate_counts)}")
    
    if duplicate_counts:
        print("\nTop 10 most common ground truths:")
        sorted_gts = sorted(duplicate_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for gt, count in sorted_gts:
            print(f"  {gt}: {count} entries")
    
    return gt_counts

def create_clean_split(manifest, gt_counts, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15):
    """
    Create clean train/validation/test split ensuring no ground truth leakage.
    
    Strategy: Group by ground truth, then assign entire groups to splits
    to ensure the same plate number never appears in multiple splits.
    """
    
    # Group entries by ground truth
    gt_groups = {}
    for entry in manifest["usable_manifest"]:
        gt = entry["ground_truth"]
        if gt not in gt_groups:
            gt_groups[gt] = []
        gt_groups[gt].append(entry)
    
    # Convert to list and shuffle
    gt_list = list(gt_groups.keys())
    random.shuffle(gt_list)
    
    # Calculate split sizes
    total_gts = len(gt_list)
    train_size = int(total_gts * train_ratio)
    val_size = int(total_gts * val_ratio)
    
    # Split ground truths
    train_gts = set(gt_list[:train_size])
    val_gts = set(gt_list[train_size:train_size + val_size])
    test_gts = set(gt_list[train_size + val_size:])
    
    # Assign entries to splits based on their ground truth
    train_entries = []
    val_entries = []
    test_entries = []
    
    for gt, entries in gt_groups.items():
        if gt in train_gts:
            train_entries.extend(entries)
        elif gt in val_gts:
            val_entries.extend(entries)
        elif gt in test_gts:
            test_entries.extend(entries)
    
    # Verify no leakage
    train_gt_set = set(e["ground_truth"] for e in train_entries)
    val_gt_set = set(e["ground_truth"] for e in val_entries)
    test_gt_set = set(e["ground_truth"] for e in test_entries)
    
    assert len(train_gt_set & val_gt_set) == 0, "Train/Val leakage detected!"
    assert len(train_gt_set & test_gt_set) == 0, "Train/Test leakage detected!"
    assert len(val_gt_set & test_gt_set) == 0, "Val/Test leakage detected!"
    
    print(f"\nSplit Results:")
    print(f"Train: {len(train_entries)} entries ({len(train_gt_set)} unique plates)")
    print(f"Validation: {len(val_entries)} entries ({len(val_gt_set)} unique plates)")
    print(f"Test: {len(test_entries)} entries ({len(test_gt_set)} unique plates)")
    print(f"Total: {len(train_entries) + len(val_entries) + len(test_entries)} entries")
    
    return train_entries, val_entries, test_entries

def save_split_datasets(train_entries, val_entries, test_entries):
    """Save the split datasets to JSON files."""
    
    def create_dataset(entries, split_name):
        return {
            "metadata": {
                "created": "2026-09-05T14:30:00",
                "total_entries": len(entries),
                "unique_ground_truths": len(set(e["ground_truth"] for e in entries)),
                "split": split_name,
                "source": "expanded_dataset_clean_split",
                "leakage_prevention": "ground_truth_grouping"
            },
            "entries": entries
        }
    
    # Save train dataset
    train_dataset = create_dataset(train_entries, "train")
    with open("data/ocr_eval/train_dataset_clean.json", 'w') as f:
        json.dump(train_dataset, f, indent=2)
    
    # Save validation dataset
    val_dataset = create_dataset(val_entries, "validation")
    with open("data/ocr_eval/validation_dataset_clean.json", 'w') as f:
        json.dump(val_dataset, f, indent=2)
    
    # Save test dataset
    test_dataset = create_dataset(test_entries, "test")
    with open("data/ocr_eval/test_dataset_clean.json", 'w') as f:
        json.dump(test_dataset, f, indent=2)
    
    print("\nDatasets saved:")
    print("  - data/ocr_eval/train_dataset_clean.json")
    print("  - data/ocr_eval/validation_dataset_clean.json")
    print("  - data/ocr_eval/test_dataset_clean.json")

def main():
    print("=" * 60)
    print("Creating Clean Train/Validation/Test Split")
    print("=" * 60)
    
    # Load current manifest
    manifest = load_current_manifest()
    
    # Analyze ground truths
    gt_counts = analyze_ground_truths(manifest)
    
    # Create clean split
    train_entries, val_entries, test_entries = create_clean_split(manifest, gt_counts)
    
    # Save datasets
    save_split_datasets(train_entries, val_entries, test_entries)
    
    print("\n" + "=" * 60)
    print("Clean split created successfully with zero data leakage")
    print("=" * 60)

if __name__ == "__main__":
    main()