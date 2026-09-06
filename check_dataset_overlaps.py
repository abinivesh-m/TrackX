"""
Check for overlaps between OCR datasets using image hashes and ground truths.
"""

import json
from pathlib import Path
from collections import defaultdict

def load_dataset_hashes(dataset_path):
    """Load image hashes and ground truths from a dataset."""
    try:
        with open(dataset_path, 'r') as f:
            data = json.load(f)
        
        entries = data if isinstance(data, list) else data.get('entries', [])
        
        hashes = set()
        ground_truths = set()
        
        for entry in entries:
            # Collect image hashes
            img_hash = entry.get('image_hash')
            if img_hash:
                hashes.add(img_hash)
            
            # Collect ground truths
            gt = entry.get('ground_truth')
            if gt:
                ground_truths.add(gt)
        
        return {
            'path': str(dataset_path),
            'hashes': hashes,
            'ground_truths': ground_truths,
            'total_entries': len(entries)
        }
    except Exception as e:
        return {
            'path': str(dataset_path),
            'error': str(e),
            'hashes': set(),
            'ground_truths': set(),
            'total_entries': 0
        }

def find_overlaps():
    """Find overlaps between all datasets."""
    base_path = Path(__file__).resolve().parent
    data_dir = base_path / "data" / "ocr_eval"
    
    # Load all datasets
    datasets = {}
    for json_file in data_dir.glob("*.json"):
        dataset_name = json_file.name
        datasets[dataset_name] = load_dataset_hashes(json_file)
    
    # Check for overlaps
    overlaps = []
    
    dataset_names = list(datasets.keys())
    for i in range(len(dataset_names)):
        for j in range(i + 1, len(dataset_names)):
            ds1 = datasets[dataset_names[i]]
            ds2 = datasets[dataset_names[j]]
            
            # Skip if either dataset had an error
            if 'error' in ds1 or 'error' in ds2:
                continue
            
            # Check hash overlaps
            hash_overlap = ds1['hashes'] & ds2['hashes']
            
            # Check ground truth overlaps
            gt_overlap = ds1['ground_truths'] & ds2['ground_truths']
            
            if hash_overlap or gt_overlap:
                overlaps.append({
                    'dataset1': dataset_names[i],
                    'dataset2': dataset_names[j],
                    'hash_overlap_count': len(hash_overlap),
                    'ground_truth_overlap_count': len(gt_overlap),
                    'hash_overlap_samples': list(hash_overlap)[:5],  # First 5 for reference
                    'ground_truth_overlap_samples': list(gt_overlap)[:5]
                })
    
    return datasets, overlaps

def main():
    datasets, overlaps = find_overlaps()
    
    print("=== DATASET OVERLAP ANALYSIS ===")
    
    # Print dataset info
    print("\nDataset Summary:")
    for name, ds in datasets.items():
        if 'error' in ds:
            print(f"  {name}: ERROR - {ds['error']}")
        else:
            print(f"  {name}: {ds['total_entries']} entries, {len(ds['hashes'])} unique hashes, {len(ds['ground_truths'])} unique ground truths")
    
    # Print overlaps
    print("\n=== OVERLAPS FOUND ===")
    if not overlaps:
        print("No overlaps found between datasets.")
    else:
        for overlap in overlaps:
            print(f"\n{overlap['dataset1']} <-> {overlap['dataset2']}:")
            print(f"  Hash overlaps: {overlap['hash_overlap_count']}")
            if overlap['hash_overlap_count'] > 0:
                print(f"    Sample hashes: {overlap['hash_overlap_samples']}")
            print(f"  Ground truth overlaps: {overlap['ground_truth_overlap_count']}")
            if overlap['ground_truth_overlap_count'] > 0:
                print(f"    Sample ground truths: {overlap['ground_truth_overlap_samples']}")
    
    # Check for concerning overlaps
    print("\n=== CONCERNING OVERLAPS (TRAINING/EVALUATION) ===")
    concerning_overlaps = []
    for overlap in overlaps:
        # Check if one dataset is evaluation and another is training/precropped
        ds1 = overlap['dataset1']
        ds2 = overlap['dataset2']
        
        if overlap['hash_overlap_count'] > 0 or overlap['ground_truth_overlap_count'] > 0:
            concerning_overlaps.append(overlap)
            print(f"\n{ds1} <-> {ds2}:")
            print(f"  {overlap['hash_overlap_count']} hash overlaps, {overlap['ground_truth_overlap_count']} ground truth overlaps")
    
    if not concerning_overlaps:
        print("No concerning overlaps found.")

if __name__ == "__main__":
    main()