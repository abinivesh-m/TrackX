"""
Remove ground truth overlaps between evaluation and training datasets.
This ensures zero train/evaluation contamination.
"""

import json
from pathlib import Path

def remove_overlaps_from_evaluation():
    """Remove overlapping entries from evaluation dataset."""
    
    base_path = Path(__file__).parent
    
    # Load training dataset (precropped)
    training_path = base_path / "data" / "ocr_eval" / "precropped_dataset.json"
    with open(training_path, 'r') as f:
        training_data = json.load(f)
    
    training_entries = training_data.get("entries", [])
    training_ground_truths = set(entry.get("ground_truth") for entry in training_entries)
    
    print(f"Training dataset: {len(training_entries)} entries, {len(training_ground_truths)} unique ground truths")
    
    # Load evaluation dataset (clean_evaluation)
    eval_path = base_path / "data" / "ocr_eval" / "clean_evaluation_dataset.json"
    with open(eval_path, 'r') as f:
        evaluation_data = json.load(f)
    
    eval_entries = evaluation_data if isinstance(evaluation_data, list) else evaluation_data.get("entries", [])
    
    print(f"Evaluation dataset (before): {len(eval_entries)} entries")
    
    # Remove entries that overlap with training data
    clean_eval_entries = []
    removed_count = 0
    
    for entry in eval_entries:
        gt = entry.get("ground_truth")
        if gt and gt in training_ground_truths:
            removed_count += 1
        else:
            clean_eval_entries.append(entry)
    
    print(f"Removed {removed_count} overlapping entries from evaluation dataset")
    print(f"Evaluation dataset (after): {len(clean_eval_entries)} entries")
    
    # Save cleaned evaluation dataset
    output_path = base_path / "data" / "ocr_eval" / "clean_evaluation_dataset.json"
    with open(output_path, 'w') as f:
        json.dump(clean_eval_entries, f, indent=2)
    
    print(f"Saved cleaned evaluation dataset to {output_path}")
    
    # Verify zero overlap
    eval_ground_truths = set(entry.get("ground_truth") for entry in clean_eval_entries)
    overlap = training_ground_truths & eval_ground_truths
    print(f"Verification: {len(overlap)} ground truth overlaps remaining")
    
    if len(overlap) == 0:
        print("SUCCESS: Zero train/evaluation overlap achieved!")
    else:
        print(f"WARNING: Still {len(overlap)} overlaps: {list(overlap)[:5]}")
    
    return clean_eval_entries

if __name__ == "__main__":
    remove_overlaps_from_evaluation()