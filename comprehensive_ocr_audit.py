"""
Comprehensive OCR Data Audit Script
Audits all OCR training and evaluation datasets, plate crops, reports, and models.
"""

import json
import os
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

class OCRDataAuditor:
    def __init__(self, base_path=None):
        self.base_path = Path(base_path) if base_path else Path(__file__).resolve().parent
        self.results = {
            "training_datasets": [],
            "evaluation_datasets": [],
            "plate_crop_dirs": [],
            "ocr_reports": [],
            "model_checkpoints": [],
            "dataset_scripts": [],
            "audit_timestamp": datetime.now().isoformat()
        }
    
    def calculate_image_hash(self, image_path):
        """Calculate SHA256 hash of an image file."""
        try:
            with open(image_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            return None
    
    def check_image_validity(self, image_path):
        """Check if an image is valid and not blank/degenerate."""
        try:
            # Basic file existence and size check
            if not os.path.exists(image_path):
                return False, "File does not exist"
            
            file_size = os.path.getsize(image_path)
            if file_size < 100:  # Less than 100 bytes is likely corrupted
                return False, f"File too small: {file_size} bytes"
            
            return True, "Valid"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def analyze_dataset(self, dataset_path, dataset_type):
        """Analyze a dataset JSON file."""
        try:
            with open(dataset_path, 'r') as f:
                data = json.load(f)
            
            # Handle both list and dict formats
            entries = data if isinstance(data, list) else data.get('entries', [])
            
            analysis = {
                "path": str(dataset_path),
                "type": dataset_type,
                "total_entries": len(entries),
                "images": 0,
                "labels": 0,
                "duplicate_ground_truths": 0,
                "invalid_images": 0,
                "blank_images": 0,
                "verified_count": 0,
                "verification_needed_count": 0,
                "cam_test_contamination": 0,
                "sources": Counter(),
                "verification_statuses": Counter(),
                "ground_truths": [],
                "image_hashes": [],
                "duplicate_hashes": 0,
                "missing_images": 0
            }
            
            ground_truth_counter = Counter()
            hash_counter = Counter()
            
            for entry in entries:
                # Count labels
                gt = entry.get('ground_truth', '')
                if gt:
                    analysis["labels"] += 1
                    analysis["ground_truths"].append(gt)
                    ground_truth_counter[gt] += 1
                
                # Check verification status
                verification_status = entry.get('verification_status', 'unknown')
                analysis["verification_statuses"][verification_status] += 1
                
                if verification_status == 'verified' or 'verified' in verification_status.lower():
                    analysis["verified_count"] += 1
                elif 'verification_needed' in verification_status.lower() or verification_status == 'VERIFICATION_NEEDED':
                    analysis["verification_needed_count"] += 1
                
                # Check source
                source = entry.get('source', 'unknown')
                analysis["sources"][source] += 1
                
                # Check for CAM_TEST contamination
                image_path = entry.get('image', entry.get('image_path', ''))
                if 'CAM_TEST' in image_path or 'test-fixture' in image_path.lower():
                    analysis["cam_test_contamination"] += 1
                
                # Analyze image if it exists
                if image_path and os.path.exists(image_path):
                    analysis["images"] += 1
                    
                    # Check image validity
                    is_valid, reason = self.check_image_validity(image_path)
                    if not is_valid:
                        if "blank" in reason.lower():
                            analysis["blank_images"] += 1
                        analysis["invalid_images"] += 1
                    
                    # Calculate hash
                    img_hash = self.calculate_image_hash(image_path)
                    if img_hash:
                        analysis["image_hashes"].append(img_hash)
                        hash_counter[img_hash] += 1
                else:
                    analysis["missing_images"] += 1
            
            # Count duplicates
            analysis["duplicate_ground_truths"] = sum(1 for count in ground_truth_counter.values() if count > 1)
            analysis["duplicate_hashes"] = sum(1 for count in hash_counter.values() if count > 1)
            
            return analysis
            
        except Exception as e:
            return {
                "path": str(dataset_path),
                "type": dataset_type,
                "error": str(e),
                "total_entries": 0
            }
    
    def find_all_datasets(self):
        """Find all OCR-related datasets and files."""
        
        # Find dataset JSON files
        data_dir = self.base_path / "data" / "ocr_eval"
        if data_dir.exists():
            for json_file in data_dir.glob("*.json"):
                dataset_analysis = self.analyze_dataset(json_file, "evaluation")
                self.results["evaluation_datasets"].append(dataset_analysis)
        
        # Find plate crop directories
        plate_crop_dirs = []
        if data_dir.exists():
            for item in data_dir.iterdir():
                if item.is_dir() and "crop" in item.name.lower():
                    crop_info = {
                        "path": str(item),
                        "name": item.name,
                        "image_count": len(list(item.glob("*.jpg")) + list(item.glob("*.png")))
                    }
                    plate_crop_dirs.append(crop_info)
                    self.results["plate_crop_dirs"].append(crop_info)
        
        # Find OCR reports
        outputs_dir = self.base_path / "outputs"
        if outputs_dir.exists():
            for json_file in outputs_dir.glob("*ocr*.json"):
                report_info = {
                    "path": str(json_file),
                    "name": json_file.name,
                    "size": json_file.stat().st_size
                }
                self.results["ocr_reports"].append(report_info)
        
        # Find model/checkpoint files
        models_dir = self.base_path / "models"
        recognition_dir = self.base_path / "recognition"
        
        potential_model_files = []
        if models_dir.exists():
            for item in models_dir.glob("*"):
                if item.is_file() and item.suffix in ['.pt', '.pth', '.onnx', '.pkl', '.h5']:
                    potential_model_files.append(item)
        
        # Check recognition directory for model files
        if recognition_dir.exists():
            for item in recognition_dir.glob("*"):
                if item.is_file() and item.suffix in ['.pt', '.pth', '.onnx', '.pkl', '.h5']:
                    potential_model_files.append(item)
        
        for model_file in potential_model_files:
            model_info = {
                "path": str(model_file),
                "name": model_file.name,
                "size": model_file.stat().st_size
            }
            self.results["model_checkpoints"].append(model_info)
        
        # Find dataset generation scripts
        script_patterns = ["*dataset*.py", "*ocr*.py", "*build*.py", "*audit*.py"]
        for pattern in script_patterns:
            for script_file in self.base_path.glob(pattern):
                if script_file.is_file() and script_file.name not in ['ocr_reader.py', 'ocr_evaluation.py']:
                    script_info = {
                        "path": str(script_file),
                        "name": script_file.name
                    }
                    self.results["dataset_scripts"].append(script_info)
    
    def generate_report(self):
        """Generate comprehensive audit report."""
        self.find_all_datasets()
        
        report = {
            "audit_summary": {
                "timestamp": self.results["audit_timestamp"],
                "total_evaluation_datasets": len(self.results["evaluation_datasets"]),
                "total_plate_crop_dirs": len(self.results["plate_crop_dirs"]),
                "total_ocr_reports": len(self.results["ocr_reports"]),
                "total_model_checkpoints": len(self.results["model_checkpoints"]),
                "total_dataset_scripts": len(self.results["dataset_scripts"])
            },
            "evaluation_datasets": self.results["evaluation_datasets"],
            "plate_crop_directories": self.results["plate_crop_dirs"],
            "ocr_reports": self.results["ocr_reports"],
            "model_checkpoints": self.results["model_checkpoints"],
            "dataset_scripts": self.results["dataset_scripts"]
        }
        
        return report

def main():
    auditor = OCRDataAuditor()
    report = auditor.generate_report()
    
    # Save report
    output_path = str(Path(__file__).resolve().parent / "comprehensive_ocr_audit_report.json")
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"Comprehensive OCR audit report saved to {output_path}")
    
    # Print summary
    print("\n=== OCR DATA AUDIT SUMMARY ===")
    print(f"Evaluation datasets found: {report['audit_summary']['total_evaluation_datasets']}")
    print(f"Plate crop directories: {report['audit_summary']['total_plate_crop_dirs']}")
    print(f"OCR reports: {report['audit_summary']['total_ocr_reports']}")
    print(f"Model checkpoints: {report['audit_summary']['total_model_checkpoints']}")
    print(f"Dataset scripts: {report['audit_summary']['total_dataset_scripts']}")
    
    print("\n=== EVALUATION DATASETS ===")
    for dataset in report["evaluation_datasets"]:
        print(f"\nDataset: {dataset['path']}")
        if 'error' in dataset:
            print(f"  ERROR: {dataset['error']}")
        else:
            print(f"  Total entries: {dataset['total_entries']}")
            print(f"  Images: {dataset['images']}")
            print(f"  Labels: {dataset['labels']}")
            print(f"  Duplicate ground truths: {dataset['duplicate_ground_truths']}")
            print(f"  Invalid images: {dataset['invalid_images']}")
            print(f"  Blank images: {dataset['blank_images']}")
            print(f"  Verified: {dataset['verified_count']}")
            print(f"  Verification needed: {dataset['verification_needed_count']}")
            print(f"  CAM_TEST contamination: {dataset['cam_test_contamination']}")
            print(f"  Duplicate image hashes: {dataset['duplicate_hashes']}")
            print(f"  Missing images: {dataset['missing_images']}")
            print(f"  Sources: {dict(dataset['sources'])}")
            print(f"  Verification statuses: {dict(dataset['verification_statuses'])}")

if __name__ == "__main__":
    main()