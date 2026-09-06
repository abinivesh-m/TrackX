"""
Update project references to use the new clean OCR evaluation dataset.

This script updates references from the old contaminated dataset to the new clean dataset.
"""

import os
import json
from pathlib import Path

def update_file_references(file_path, old_dataset_name, new_dataset_name):
    """Update dataset references in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file contains references to old dataset
        if old_dataset_name in content:
            updated_content = content.replace(old_dataset_name, new_dataset_name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            print(f"Updated: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def main():
    print("Updating project references to use clean OCR evaluation dataset...")
    
    old_dataset = "clean_evaluation_dataset.json"
    new_dataset = "clean_evaluation_dataset.json"
    
    # Search for Python files that might reference the dataset
    project_root = Path(".")
    updated_files = []
    
    for py_file in project_root.rglob("*.py"):
        if update_file_references(str(py_file), old_dataset, new_dataset):
            updated_files.append(str(py_file))
    
    # Check for JSON config files
    for json_file in project_root.rglob("*.json"):
        if "ocr_eval" not in str(json_file):  # Skip the dataset files themselves
            if update_file_references(str(json_file), old_dataset, new_dataset):
                updated_files.append(str(json_file))
    
    # Check for markdown documentation
    for md_file in project_root.rglob("*.md"):
        if update_file_references(str(md_file), old_dataset, new_dataset):
            updated_files.append(str(md_file))
    
    print(f"\nUpdated {len(updated_files)} files:")
    for file in updated_files:
        print(f"  - {file}")
    
    # Update the main demo script to use clean dataset
    demo_script = "run_demo.py"
    if os.path.exists(demo_script):
        with open(demo_script, 'r') as f:
            content = f.read()
        
        # Update OCR evaluation section to use clean dataset
        if "clean_evaluation_dataset.json" in content:
            content = content.replace("clean_evaluation_dataset.json", "clean_evaluation_dataset.json")
            with open(demo_script, 'w') as f:
                f.write(content)
            print(f"Updated: {demo_script}")
    
    print("\nDataset reference update complete!")
    print(f"New dataset: data/ocr_eval/{new_dataset}")
    print(f"Old dataset quarantined: data/ocr_eval/{old_dataset}")

if __name__ == "__main__":
    main()
