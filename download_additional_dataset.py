"""
Download additional Indian license plate images from legal/public sources to expand dataset.
Target: Reach 1000+ genuine Indian license plate images for OCR training.
"""

import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download
import json
import shutil
from PIL import Image
import hashlib

def download_huggingface_dataset():
    """Download Indian license plate dataset from Hugging Face."""
    print("Downloading Indian license plate dataset from Hugging Face...")
    
    try:
        # Download the Datacluster Indian license plate dataset (sample subset)
        # This is available for academic/research use with attribution
        local_path = snapshot_download(
            repo_id="Dataclusterlabspvtltd/indian-number-plates-dataset",
            repo_type="dataset",
            local_dir="data/ocr_eval/huggingface_import",
            local_dir_use_symlinks=False
        )
        print(f"Dataset downloaded to: {local_path}")
        return local_path
    except Exception as e:
        print(f"Failed to download from Hugging Face: {e}")
        return None

def process_downloaded_dataset(source_dir):
    """Process downloaded dataset and extract plate crops."""
    print(f"Processing downloaded dataset from {source_dir}...")
    
    target_dir = Path("data/ocr_eval/plate_crops_additional")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    processed_images = []
    
    # Walk through the downloaded directory
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                source_path = Path(root) / file
                
                try:
                    # Try to open and validate the image
                    img = Image.open(source_path)
                    img.verify()  # Verify it's a valid image
                    
                    # Reopen after verify (verify closes the file)
                    img = Image.open(source_path)
                    
                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Generate hash for deduplication
                    img_bytes = img.tobytes()
                    img_hash = hashlib.sha256(img_bytes).hexdigest()
                    
                    # Check if this image already exists in our dataset
                    existing_hash = check_hash_exists(img_hash)
                    if existing_hash:
                        print(f"Skipping duplicate image: {file} (hash: {img_hash[:8]}...)")
                        continue
                    
                    # Copy to target directory with unique name
                    target_name = f"hf_{file}"
                    target_path = target_dir / target_name
                    img.save(target_path, 'JPEG', quality=95)
                    
                    # Extract plate number from filename if possible
                    # Datacluster dataset uses filename as plate number
                    plate_number = file.split('.')[0].upper()
                    
                    processed_images.append({
                        "image_path": str(target_path.absolute()),
                        "ground_truth": plate_number,
                        "image_hash": img_hash,
                        "source": "HuggingFace_Datacluster",
                        "verification_status": "filename_based"
                    })
                    
                    print(f"Processed: {file} -> {plate_number}")
                    
                except Exception as e:
                    print(f"Error processing {file}: {e}")
                    continue
    
    return processed_images

def check_hash_exists(image_hash):
    """Check if an image with this hash already exists in our dataset."""
    # Check existing manifest
    manifest_path = Path("data/ocr_eval/dataset_audit_manifest.json")
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            for entry in manifest.get("usable_manifest", []):
                if entry.get("sha256") == image_hash:
                    return True
    return False

def update_dataset_with_new_images(new_images):
    """Update dataset manifest with new images."""
    manifest_path = Path("data/ocr_eval/dataset_audit_manifest.json")
    
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
    else:
        manifest = {
            "audit_timestamp": "2026-09-05T00:00:00",
            "total_audited": 0,
            "usable_count": 0,
            "excluded_corrupt_count": 0,
            "excluded_duplicate_count": 0,
            "excluded_unannotated_count": 0,
            "usable_evaluation_count": 0,
            "usable_training_count": 0,
            "excluded_corrupt": [],
            "excluded_duplicates": [],
            "excluded_unannotated": [],
            "usable_manifest": []
        }
    
    # Add new images to manifest
    for img_data in new_images:
        filename = Path(img_data["image_path"]).name
        
        # Get image dimensions
        try:
            img = Image.open(img_data["image_path"])
            width, height = img.size
            aspect_ratio = width / height if height > 0 else 0
        except:
            width, height, aspect_ratio = 0, 0, 0
        
        manifest["usable_manifest"].append({
            "filename": filename,
            "height": height,
            "width": width,
            "aspect_ratio": round(aspect_ratio, 2),
            "ground_truth": img_data["ground_truth"],
            "split": "additional",  # Mark as additional for now
            "source": img_data["source"],
            "sha256": img_data["image_hash"]
        })
    
    # Update counts
    manifest["total_audited"] = len(manifest["usable_manifest"])
    manifest["usable_count"] = len(manifest["usable_manifest"])
    manifest["audit_timestamp"] = "2026-09-05T14:00:00"
    
    # Save updated manifest
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"Updated manifest: {len(new_images)} new images added")
    print(f"Total images in dataset: {manifest['usable_count']}")

def main():
    print("=" * 60)
    print("Indian License Plate Dataset Expansion")
    print("=" * 60)
    
    # Download dataset
    downloaded_dir = download_huggingface_dataset()
    
    if downloaded_dir:
        # Process downloaded images
        new_images = process_downloaded_dataset(downloaded_dir)
        
        if new_images:
            # Update dataset manifest
            update_dataset_with_new_images(new_images)
            
            print("\n" + "=" * 60)
            print(f"Successfully added {len(new_images)} new images to dataset")
            print("=" * 60)
        else:
            print("No new images were processed")
    else:
        print("Failed to download dataset")
        print("\nAlternative: You can manually download datasets from:")
        print("1. Kaggle: https://www.kaggle.com/datasets/umar1103/final-licence")
        print("2. Place images in: data/ocr_eval/plate_crops_additional/")
        print("3. Run this script again to process them")

if __name__ == "__main__":
    main()