"""
Create a proper train/evaluation split from the precropped dataset.
This ensures zero overlap and 500+ genuinely verified evaluation samples.
"""

import json
import random
from pathlib import Path
from collections import defaultdict
from config import PROJECT_ROOT

EXTERNAL_DATA_BASE = PROJECT_ROOT.parent  # folder containing State-wise_OLX / google_images if present

def create_train_eval_split():
    """Create clean train/evaluation split from precropped data."""

    base_path = PROJECT_ROOT
    
    # Load precropped dataset
    precropped_path = base_path / "data" / "ocr_eval" / "precropped_dataset.json"
    with open(precropped_path, 'r') as f:
        precropped_data = json.load(f)
    
    entries = precropped_data.get("entries", [])
    print(f"Total precropped entries: {len(entries)}")
    
    # Group by ground truth to avoid splitting same plate across train/eval
    ground_truth_groups = defaultdict(list)
    for entry in entries:
        gt = entry.get("ground_truth")
        if gt:
            ground_truth_groups[gt].append(entry)
    
    print(f"Unique ground truths: {len(ground_truth_groups)}")
    
    # Convert to list and shuffle
    gt_list = list(ground_truth_groups.keys())
    random.shuffle(gt_list)
    
    # Split: 80% training, 20% evaluation (with minimum 500 for evaluation)
    eval_count = max(500, int(len(gt_list) * 0.2))
    train_count = len(gt_list) - eval_count
    
    print(f"Split: {train_count} training plates, {eval_count} evaluation plates")
    
    # Create splits
    eval_gts = set(gt_list[:eval_count])
    train_gts = set(gt_list[eval_count:])
    
    train_entries = []
    eval_entries = []
    
    for gt, group_entries in ground_truth_groups.items():
        if gt in eval_gts:
            eval_entries.extend(group_entries)
        else:
            train_entries.extend(group_entries)
    
    print(f"Training entries: {len(train_entries)}")
    print(f"Evaluation entries: {len(eval_entries)}")
    
    # Verify zero overlap
    train_gt_set = set(entry.get("ground_truth") for entry in train_entries)
    eval_gt_set = set(entry.get("ground_truth") for entry in eval_entries)
    overlap = train_gt_set & eval_gt_set
    
    print(f"Ground truth overlap verification: {len(overlap)} overlaps")
    assert len(overlap) == 0, "Train/eval overlap detected!"
    
    # Save training dataset
    train_output = base_path / "data" / "ocr_eval" / "training_dataset.json"
    train_data = {
        "metadata": {
            "created": "2026-08-26T14:50:00.000000",
            "total_entries": len(train_entries),
            "unique_ground_truths": len(train_gt_set),
            "split": "training",
            "source": "precropped_dataset_split"
        },
        "entries": train_entries
    }
    
    with open(train_output, 'w') as f:
        json.dump(train_data, f, indent=2)
    
    print(f"Saved training dataset to {train_output}")
    
    # Save evaluation dataset
    eval_output = base_path / "data" / "ocr_eval" / "clean_evaluation_dataset.json"
    evaluation_data = {
        "metadata": {
            "created": "2026-08-26T14:50:00.000000",
            "total_entries": len(eval_entries),
            "unique_ground_truths": len(eval_gt_set),
            "split": "evaluation",
            "source": "precropped_dataset_split"
        },
        "entries": eval_entries
    }
    
    with open(eval_output, 'w') as f:
        json.dump(evaluation_data, f, indent=2)
    
    print(f"Saved evaluation dataset to {eval_output}")
    
    # Verify all entries are real images
    missing_images = 0
    for entry in eval_entries:
        img_path = entry.get("image_path")
        if not Path(img_path).exists():
            missing_images += 1
    
    print(f"Evaluation dataset: {missing_images} missing images")
    
    if missing_images == 0:
        print("SUCCESS: All evaluation images exist!")
    else:
        print(f"WARNING: {missing_images} evaluation images are missing")
    
    return train_entries, eval_entries

if __name__ == "__main__":
    create_train_eval_split()