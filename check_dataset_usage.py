"""
Check dataset usage in current scripts to understand which datasets are actively used.
"""

import os
import re
from pathlib import Path
from collections import defaultdict

def find_dataset_references():
    """Find references to datasets in Python scripts."""
    base_path = Path(__file__).resolve().parent
    
    # Dataset files to look for
    dataset_files = [
        "precropped_dataset.json",
        "clean_evaluation_dataset.json", 
        "final_evaluation_dataset.json",
        "full_dataset.json",
        "cleaned_dataset.json",
        "comprehensive_dataset.json",
        "real_dataset.json",
        "dataset.json"
    ]
    
    references = defaultdict(list)
    
    # Search in Python files
    for py_file in base_path.glob("*.py"):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for dataset in dataset_files:
                if dataset in content:
                    references[dataset].append(str(py_file))
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
    
    # Also check in recognition directory
    for py_file in (base_path / "recognition").glob("*.py"):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for dataset in dataset_files:
                if dataset in content:
                    references[dataset].append(str(py_file))
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
    
    return references

def main():
    references = find_dataset_references()
    
    print("=== DATASET USAGE IN SCRIPTS ===")
    for dataset, files in sorted(references.items()):
        print(f"\n{dataset}:")
        for file in files:
            print(f"  - {file}")
    
    # Check for unused datasets
    all_datasets = [
        "precropped_dataset.json",
        "clean_evaluation_dataset.json", 
        "final_evaluation_dataset.json",
        "full_dataset.json",
        "cleaned_dataset.json",
        "comprehensive_dataset.json",
        "real_dataset.json",
        "dataset.json"
    ]
    
    unused = [d for d in all_datasets if d not in references]
    print("\n=== UNUSED DATASETS ===")
    for dataset in unused:
        print(f"  - {dataset}")

if __name__ == "__main__":
    main()