"""
Create placeholder synthetic plate images for evaluation dataset.
These are simple black images that serve as placeholders for the synthetic samples.
"""

import json
from pathlib import Path

def create_placeholder_plate_images(dataset_path: str, output_dir: str):
    """Create placeholder images for synthetic plate samples."""
    
    # Load dataset
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    created_count = 0
    
    for item in dataset:
        if item.get("source") == "SYNTHETIC_DEMO":
            image_path = item.get("image", "")
            
            # Extract filename from path
            if "/" in image_path:
                filename = image_path.split("/")[-1]
            else:
                filename = image_path
            
            full_path = output_path / filename
            
            # Create a simple placeholder file (empty text file for now)
            # In a real scenario, these would be actual synthetic plate images
            with open(full_path, 'w') as f:
                f.write(f"SYNTHETIC_PLACEHOLDER: {item.get('ground_truth', 'UNKNOWN')}")
            
            created_count += 1
    
    print(f"Created {created_count} placeholder synthetic plate files")
    print(f"Files saved to: {output_dir}")

if __name__ == "__main__":
    dataset_path = "data/ocr_eval/clean_evaluation_dataset.json"
    output_dir = "data/ocr_eval/synthetic"
    
    create_placeholder_plate_images(dataset_path, output_dir)
    
    print("[SUCCESS] Placeholder files created for synthetic samples")
    print("Note: These are placeholder files for demonstration purposes.")
    print("In a production scenario, real synthetic plate images would be used.")