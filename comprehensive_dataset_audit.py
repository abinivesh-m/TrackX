"""
Comprehensive Dataset Audit for TrackX OCR
Audits all plate images for quality, validity, and Indian plate compliance.
"""

import os
import json
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import hashlib
from typing import Dict, List, Tuple, Set
import re

class DatasetAuditor:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.results = {
            "audit_timestamp": datetime.now().isoformat(),
            "total_images_found": 0,
            "valid_indian_plates": 0,
            "removed_images": {
                "non_plate": 0,
                "non_indian": 0,
                "corrupt": 0,
                "duplicate": 0,
                "unreadable": 0,
                "invalid_format": 0
            },
            "image_hashes": {},
            "removed_entries": [],
            "valid_entries": [],
            "state_distribution": {},
            "quality_distribution": {
                "high_quality": 0,
                "medium_quality": 0,
                "low_quality": 0
            }
        }
        
    def is_valid_indian_plate(self, text: str) -> Tuple[bool, str]:
        """
        Validate if text is a valid Indian license plate format.
        Returns (is_valid, reason)
        """
        if not text or len(text) < 6:
            return False, "too_short"
        
        # Common Indian plate patterns
        patterns = [
            r'^[A-Z]{2}\d{2}[A-Z]{2}\d{4}$',  # MH01AB1234
            r'^[A-Z]{2}\d{3}[A-Z]{2}\d{4}$',  # TN123AB1234
            r'^[A-Z]{2}\d{4}\d{4}$',           # KA05481234
            r'^[A-Z]{2}\d{2}[A-Z]{1}\d{4}$',   # MH01A1234
            r'^[A-Z]{2}\d{2}\d{4}$',           # MH011234
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True, "valid"
        
        return False, "invalid_format"
    
    def check_image_quality(self, image: np.ndarray) -> str:
        """
        Assess image quality based on resolution, brightness, and contrast.
        Returns: 'high_quality', 'medium_quality', or 'low_quality'
        """
        if image is None or image.size == 0:
            return "corrupt"
        
        h, w = image.shape[:2]
        
        # Resolution check
        if h < 30 or w < 80:
            return "low_quality"
        elif h < 50 or w < 150:
            return "medium_quality"
        
        # Brightness check
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        brightness = np.mean(gray)
        
        if brightness < 50 or brightness > 200:
            return "low_quality"
        
        # Contrast check
        contrast = np.std(gray)
        if contrast < 30:
            return "low_quality"
        elif contrast < 60:
            return "medium_quality"
        
        return "high_quality"
    
    def compute_image_hash(self, image: np.ndarray) -> str:
        """Compute perceptual hash for duplicate detection."""
        if image is None:
            return ""
        
        # Resize to small size for hash computation
        small = cv2.resize(image, (8, 8))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if len(small.shape) == 3 else small
        
        # Compute hash
        hash_str = hashlib.md5(gray.tobytes()).hexdigest()
        return hash_str
    
    def audit_dataset_file(self, dataset_file: str) -> Dict:
        """Audit a single dataset JSON file."""
        dataset_path = self.base_path / dataset_file
        
        if not dataset_path.exists():
            return {"error": f"Dataset file not found: {dataset_file}"}
        
        with open(dataset_path, 'r') as f:
            data = json.load(f)
        
        # Handle both formats: direct list or wrapped in "entries"
        entries = data if isinstance(data, list) else data.get("entries", [])
        
        print(f"\nAuditing {dataset_file}: {len(entries)} entries")
        
        for entry in entries:
            image_path = entry.get("image_path") or entry.get("image")
            ground_truth = entry.get("ground_truth")
            
            if not image_path or not ground_truth:
                self.results["removed_images"]["invalid_format"] += 1
                self.results["removed_entries"].append({
                    "entry": entry,
                    "reason": "missing_image_or_ground_truth",
                    "dataset": dataset_file
                })
                continue
            
            # Check if image file exists
            if not os.path.exists(image_path):
                self.results["removed_images"]["corrupt"] += 1
                self.results["removed_entries"].append({
                    "entry": entry,
                    "reason": "image_file_not_found",
                    "dataset": dataset_file
                })
                continue
            
            # Load and validate image
            try:
                image = cv2.imread(image_path)
                if image is None:
                    self.results["removed_images"]["corrupt"] += 1
                    self.results["removed_entries"].append({
                        "entry": entry,
                        "reason": "image_load_failed",
                        "dataset": dataset_file
                    })
                    continue
                
                self.results["total_images_found"] += 1
                
                # Check for duplicates
                img_hash = self.compute_image_hash(image)
                if img_hash in self.results["image_hashes"]:
                    self.results["removed_images"]["duplicate"] += 1
                    self.results["removed_entries"].append({
                        "entry": entry,
                        "reason": "duplicate_image",
                        "dataset": dataset_file,
                        "duplicate_of": self.results["image_hashes"][img_hash]
                    })
                    continue
                
                self.results["image_hashes"][img_hash] = image_path
                
                # Validate Indian plate format
                is_valid, reason = self.is_valid_indian_plate(ground_truth)
                if not is_valid:
                    self.results["removed_images"]["non_indian"] += 1
                    self.results["removed_entries"].append({
                        "entry": entry,
                        "reason": f"non_indian_plate_{reason}",
                        "dataset": dataset_file
                    })
                    continue
                
                # Check image quality
                quality = self.check_image_quality(image)
                if quality == "corrupt":
                    self.results["removed_images"]["corrupt"] += 1
                    self.results["removed_entries"].append({
                        "entry": entry,
                        "reason": "corrupt_image",
                        "dataset": dataset_file
                    })
                    continue
                
                self.results["quality_distribution"][quality] += 1
                
                # Count state distribution
                if len(ground_truth) >= 2:
                    state = ground_truth[:2]
                    self.results["state_distribution"][state] = self.results["state_distribution"].get(state, 0) + 1
                
                # Valid entry
                self.results["valid_indian_plates"] += 1
                self.results["valid_entries"].append({
                    "image_path": image_path,
                    "ground_truth": ground_truth,
                    "quality": quality,
                    "state": state if len(ground_truth) >= 2 else "unknown",
                    "dataset": dataset_file,
                    "hash": img_hash
                })
                
            except Exception as e:
                self.results["removed_images"]["corrupt"] += 1
                self.results["removed_entries"].append({
                    "entry": entry,
                    "reason": f"processing_error_{str(e)}",
                    "dataset": dataset_file
                })
                continue
        
        return {"processed": len(entries), "valid": self.results["valid_indian_plates"]}
    
    def audit_directory(self, directory: str) -> Dict:
        """Audit images in a directory without ground truth."""
        dir_path = self.base_path / directory
        
        if not dir_path.exists():
            return {"error": f"Directory not found: {directory}"}
        
        print(f"\nAuditing directory {directory}:")
        
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            image_files.extend(dir_path.glob(ext))
        
        print(f"Found {len(image_files)} image files")
        
        for image_file in image_files:
            try:
                image = cv2.imread(str(image_file))
                if image is None:
                    self.results["removed_images"]["corrupt"] += 1
                    continue
                
                self.results["total_images_found"] += 1
                
                # Check for duplicates
                img_hash = self.compute_image_hash(image)
                if img_hash in self.results["image_hashes"]:
                    self.results["removed_images"]["duplicate"] += 1
                    continue
                
                self.results["image_hashes"][img_hash] = str(image_file)
                
                # Check image quality
                quality = self.check_image_quality(image)
                if quality == "corrupt":
                    self.results["removed_images"]["corrupt"] += 1
                    continue
                
                self.results["quality_distribution"][quality] += 1
                
                # No ground truth - can't validate as Indian plate
                self.results["removed_images"]["non_plate"] += 1
                self.results["removed_entries"].append({
                    "image_path": str(image_file),
                    "reason": "no_ground_truth_cannot_validate",
                    "directory": directory
                })
                
            except Exception as e:
                self.results["removed_images"]["corrupt"] += 1
                continue
        
        return {"processed": len(image_files)}
    
    def generate_clean_dataset(self, output_file: str):
        """Generate a clean dataset file with only valid Indian plates."""
        clean_dataset = {
            "metadata": {
                "created": datetime.now().isoformat(),
                "total_entries": len(self.results["valid_entries"]),
                "unique_ground_truths": len(set(e["ground_truth"] for e in self.results["valid_entries"])),
                "split": "clean",
                "source": "comprehensive_audit",
                "audit_timestamp": self.results["audit_timestamp"]
            },
            "entries": self.results["valid_entries"]
        }
        
        output_path = self.base_path / output_file
        with open(output_path, 'w') as f:
            json.dump(clean_dataset, f, indent=2)
        
        print(f"\nClean dataset saved to: {output_path}")
        print(f"Valid entries: {len(self.results['valid_entries'])}")
        
        return output_path
    
    def generate_audit_report(self, output_file: str):
        """Generate comprehensive audit report."""
        output_path = self.base_path / output_file
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\nAudit report saved to: {output_file}")
        return output_path

def main():
    base_path = "data/ocr_eval"
    auditor = DatasetAuditor(base_path)
    
    print("=" * 60)
    print("COMPREHENSIVE DATASET AUDIT FOR TRACKX OCR")
    print("=" * 60)
    
    # Audit existing dataset files
    dataset_files = [
        "clean_evaluation_dataset.json",
        "precropped_dataset.json", 
        "training_dataset.json",
        "video_dataset.json"
    ]
    
    for dataset_file in dataset_files:
        result = auditor.audit_dataset_file(dataset_file)
        print(f"Result: {result}")
    
    # Audit directories without ground truth
    directories = ["plate_crops_external"]
    for directory in directories:
        result = auditor.audit_directory(directory)
        print(f"Result: {result}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Total images found: {auditor.results['total_images_found']}")
    print(f"Valid Indian plates: {auditor.results['valid_indian_plates']}")
    print(f"Removed images: {sum(auditor.results['removed_images'].values())}")
    print(f"  - Non-plate: {auditor.results['removed_images']['non_plate']}")
    print(f"  - Non-Indian: {auditor.results['removed_images']['non_indian']}")
    print(f"  - Corrupt: {auditor.results['removed_images']['corrupt']}")
    print(f"  - Duplicate: {auditor.results['removed_images']['duplicate']}")
    print(f"  - Invalid format: {auditor.results['removed_images']['invalid_format']}")
    
    print(f"\nQuality distribution:")
    print(f"  - High quality: {auditor.results['quality_distribution']['high_quality']}")
    print(f"  - Medium quality: {auditor.results['quality_distribution']['medium_quality']}")
    print(f"  - Low quality: {auditor.results['quality_distribution']['low_quality']}")
    
    print(f"\nState distribution:")
    for state, count in sorted(auditor.results['state_distribution'].items()):
        print(f"  - {state}: {count}")
    
    # Generate clean dataset
    clean_dataset_path = auditor.generate_clean_dataset("clean_indian_plates_dataset.json")
    
    # Generate audit report
    audit_report_path = auditor.generate_audit_report("comprehensive_audit_report.json")
    
    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)
    print(f"Clean dataset: {clean_dataset_path}")
    print(f"Audit report: {audit_report_path}")
    print(f"Valid Indian plates for OCR training: {auditor.results['valid_indian_plates']}")

if __name__ == "__main__":
    main()