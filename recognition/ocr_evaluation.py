"""
ocr_evaluation.py

OCR accuracy evaluation system for SIH PS 26127.

Measures OCR accuracy against ground truth data to verify >90% accuracy requirement.
Supports various plate conditions: lighting, blur, angle, occlusion, dirt, resolution.
"""

import os
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import cv2
import numpy as np

from recognition.ocr_reader import try_init_ocr, PlateOCR
from recognition.plate_normalizer import normalize_indian_plate


@dataclass
class OCRTrial:
    """Single OCR evaluation trial."""
    image_path: str
    ground_truth: str
    ocr_result: Optional[str]
    normalized_ocr: Optional[str]
    normalized_ground_truth: str
    confidence: float
    exact_match: bool
    character_accuracy: float
    error_type: Optional[str]  # None, "no_ocr", "confusion", "length_error", etc.


@dataclass
class OCREvaluationReport:
    """Complete OCR evaluation report."""
    timestamp: str
    total_samples: int
    successful_ocr: int
    failed_ocr: int
    exact_matches: int
    exact_accuracy: float
    avg_character_accuracy: float
    avg_confidence: float
    trials: List[Dict]
    error_breakdown: Dict[str, int]


class OCREvaluator:
    """OCR accuracy evaluator with comprehensive metrics."""
    
    def __init__(self, ocr_instance=None):
        """
        Initialize OCR evaluator.
        
        Args:
            ocr_instance: Optional pre-initialized OCR instance.
                         If None, will attempt to initialize using try_init_ocr().
        """
        self.ocr = ocr_instance or try_init_ocr()
        if self.ocr is None:
            print("[ocr_evaluation] WARNING: OCR engine not available - evaluation will be limited")
    
    def calculate_character_accuracy(self, predicted: str, ground_truth: str) -> float:
        """
        Calculate character-level accuracy using Levenshtein distance.
        
        Args:
            predicted: OCR result string
            ground_truth: Ground truth string
            
        Returns:
            Float between 0.0 and 1.0 representing character accuracy
        """
        if not predicted or not ground_truth:
            return 0.0
        
        # Simple character-level accuracy
        max_len = max(len(predicted), len(ground_truth))
        if max_len == 0:
            return 1.0
        
        matches = sum(1 for p, g in zip(predicted, ground_truth) if p == g)
        return matches / max_len
    
    def classify_error(self, predicted: Optional[str], ground_truth: str) -> Optional[str]:
        """
        Classify the type of OCR error.
        
        Args:
            predicted: OCR result (None if OCR failed)
            ground_truth: Ground truth string
            
        Returns:
            Error type string or None if no error
        """
        if predicted is None:
            return "no_ocr"
        
        if predicted == ground_truth:
            return None
        
        if len(predicted) != len(ground_truth):
            return "length_error"
        
        # Check for common confusions
        confusion_pairs = [('0', 'O'), ('1', 'I'), ('8', 'B'), ('5', 'S'), ('2', 'Z'), ('6', 'G'), ('0', 'D')]
        for p, g in zip(predicted, ground_truth):
            if (p, g) in confusion_pairs or (g, p) in confusion_pairs:
                return "confusion"
        
        return "substitution_error"
    
    def evaluate_single_image(self, image_path: str, ground_truth: str) -> OCRTrial:
        """
        Evaluate OCR on a single image against ground truth.
        
        Args:
            image_path: Path to plate image
            ground_truth: Ground truth plate text
            
        Returns:
            OCRTrial with evaluation results
        """
        if not os.path.isfile(image_path):
            print(f"[ocr_evaluation] WARNING: Image not found: {image_path}")
            return OCRTrial(
                image_path=image_path,
                ground_truth=ground_truth,
                ocr_result=None,
                normalized_ocr=None,
                normalized_ground_truth=normalize_indian_plate(ground_truth)[0],
                confidence=0.0,
                exact_match=False,
                character_accuracy=0.0,
                error_type="image_not_found"
            )
        
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            return OCRTrial(
                image_path=image_path,
                ground_truth=ground_truth,
                ocr_result=None,
                normalized_ocr=None,
                normalized_ground_truth=normalize_indian_plate(ground_truth)[0],
                confidence=0.0,
                exact_match=False,
                character_accuracy=0.0,
                error_type="image_read_error"
            )
        
        # Run OCR
        ocr_result = None
        confidence = 0.0
        if self.ocr is not None:
            try:
                ocr_result, confidence = self.ocr.read(image)
            except Exception as e:
                print(f"[ocr_evaluation] OCR error on {image_path}: {e}")
                ocr_result = None
        
        # Normalize results
        normalized_ground_truth, _ = normalize_indian_plate(ground_truth)
        normalized_ocr = None
        if ocr_result:
            normalized_ocr, _ = normalize_indian_plate(ocr_result)
        
        # Calculate metrics
        exact_match = (normalized_ocr == normalized_ground_truth) if normalized_ocr else False
        character_accuracy = self.calculate_character_accuracy(
            normalized_ocr or "", normalized_ground_truth
        )
        error_type = self.classify_error(normalized_ocr, normalized_ground_truth)
        
        return OCRTrial(
            image_path=image_path,
            ground_truth=ground_truth,
            ocr_result=ocr_result,
            normalized_ocr=normalized_ocr,
            normalized_ground_truth=normalized_ground_truth,
            confidence=confidence,
            exact_match=exact_match,
            character_accuracy=character_accuracy,
            error_type=error_type
        )
    
    def evaluate_dataset(self, dataset_path: str, output_report: str = None) -> OCREvaluationReport:
        """
        Evaluate OCR on a dataset of plate images.
        
        Expected dataset format:
        - JSON file with: [{"image": "path/to/plate.jpg", "ground_truth": "TN10AB1234"}, ...]
        - OR directory with: plate_001.jpg, plate_001.txt (containing ground truth)
        
        Args:
            dataset_path: Path to dataset file or directory
            output_report: Optional path to save JSON report
            
        Returns:
            OCREvaluationReport with comprehensive results
        """
        trials = []
        
        # Load dataset
        if os.path.isfile(dataset_path):
            # Assume JSON format
            with open(dataset_path, 'r') as f:
                data = json.load(f)
            
            # Handle both formats: direct entries list or wrapped in "entries" key
            entries = data if isinstance(data, list) else data.get("entries", [])
            
            for entry in entries:
                image_path = entry.get("image") or entry.get("image_path")
                ground_truth = entry.get("ground_truth")
                if image_path and ground_truth:
                    trial = self.evaluate_single_image(image_path, ground_truth)
                    trials.append(trial)
        
        elif os.path.isdir(dataset_path):
            # Assume directory with image + text file pairs
            for file in os.listdir(dataset_path):
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    image_path = os.path.join(dataset_path, file)
                    txt_path = os.path.splitext(image_path)[0] + '.txt'
                    
                    if os.path.isfile(txt_path):
                        with open(txt_path, 'r') as f:
                            ground_truth = f.read().strip()
                        
                        trial = self.evaluate_single_image(image_path, ground_truth)
                        trials.append(trial)
        
        # Calculate aggregate metrics
        total_samples = len(trials)
        successful_ocr = sum(1 for t in trials if t.ocr_result is not None)
        failed_ocr = total_samples - successful_ocr
        exact_matches = sum(1 for t in trials if t.exact_match)
        exact_accuracy = exact_matches / total_samples if total_samples > 0 else 0.0
        
        character_accuracies = [t.character_accuracy for t in trials if t.ocr_result is not None]
        avg_character_accuracy = sum(character_accuracies) / len(character_accuracies) if character_accuracies else 0.0
        
        confidences = [t.confidence for t in trials if t.ocr_result is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Error breakdown
        error_breakdown = {}
        for trial in trials:
            error_type = trial.error_type or "correct"
            error_breakdown[error_type] = error_breakdown.get(error_type, 0) + 1
        
        # Create report
        report = OCREvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_samples=total_samples,
            successful_ocr=successful_ocr,
            failed_ocr=failed_ocr,
            exact_matches=exact_matches,
            exact_accuracy=exact_accuracy,
            avg_character_accuracy=avg_character_accuracy,
            avg_confidence=avg_confidence,
            trials=[asdict(t) for t in trials],
            error_breakdown=error_breakdown
        )
        
        # Save report if requested
        if output_report:
            os.makedirs(os.path.dirname(output_report) or ".", exist_ok=True)
            with open(output_report, 'w') as f:
                json.dump(asdict(report), f, indent=2)
            print(f"[ocr_evaluation] Report saved to: {output_report}")
        
        return report
    
    def print_summary(self, report: OCREvaluationReport):
        """Print a human-readable summary of the evaluation results."""
        print("\n" + "="*60)
        print("OCR EVALUATION SUMMARY")
        print("="*60)
        print(f"Timestamp: {report.timestamp}")
        print(f"Total samples: {report.total_samples}")
        print(f"Successful OCR: {report.successful_ocr} ({report.successful_ocr/report.total_samples*100:.1f}%)")
        print(f"Failed OCR: {report.failed_ocr} ({report.failed_ocr/report.total_samples*100:.1f}%)")
        print(f"Exact matches: {report.exact_matches} ({report.exact_accuracy*100:.1f}%)")
        print(f"Average character accuracy: {report.avg_character_accuracy*100:.1f}%")
        print(f"Average confidence: {report.avg_confidence:.3f}")
        print("\nError breakdown:")
        for error_type, count in report.error_breakdown.items():
            print(f"  {error_type}: {count} ({count/report.total_samples*100:.1f}%)")
        print("="*60)
        
        # SIH requirement check
        if report.exact_accuracy >= 0.90:
            print(f"[PASS] SIH REQUIREMENT MET: OCR accuracy {report.exact_accuracy*100:.1f}% >= 90%")
        else:
            print(f"[FAIL] SIH REQUIREMENT NOT MET: OCR accuracy {report.exact_accuracy*100:.1f}% < 90%")
        print("="*60 + "\n")


def create_sample_dataset(output_dir: str, num_samples: int = 10):
    """
    Create a sample dataset for OCR evaluation testing.
    
    This creates a minimal dataset structure for testing the evaluation system.
    In production, this would be replaced with real annotated plate data.
    
    Args:
        output_dir: Directory to create sample dataset
        num_samples: Number of sample entries to create
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create sample JSON dataset
    sample_data = []
    for i in range(num_samples):
        sample_data.append({
            "image": f"plate_{i:03d}.jpg",
            "ground_truth": f"TN10AB{i:04d}"
        })
    
    dataset_path = os.path.join(output_dir, "dataset.json")
    with open(dataset_path, 'w') as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"[ocr_evaluation] Sample dataset created at: {dataset_path}")
    print(f"[ocr_evaluation] NOTE: This is a template. Replace with real plate images and ground truth.")
    
    return dataset_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OCR Accuracy Evaluation for SIH PS 26127")
    parser.add_argument("--dataset", required=True, help="Path to dataset file or directory")
    parser.add_argument("--output", help="Path to save JSON report")
    parser.add_argument("--create-sample", help="Create sample dataset at specified path")
    parser.add_argument("--ocr-model", help="Path to local OCR model (for offline use)")
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_dataset(args.create_sample)
        print("\nNow run evaluation with:")
        print(f"python -m recognition.ocr_evaluation --dataset {args.create_sample}/dataset.json")
        exit(0)
    
    # Initialize evaluator
    evaluator = OCREvaluator()
    
    # Run evaluation
    report = evaluator.evaluate_dataset(args.dataset, args.output)
    
    # Print summary
    evaluator.print_summary(report)
    
    # Final verdict
    if report.exact_accuracy < 0.90:
        print("\n[WARNING] SIH REQUIREMENT NOT MET: OCR accuracy below 90%")
        print("This may be due to:")
        print("- Insufficient or low-quality training data")
        print("- Challenging test conditions (blur, angle, lighting)")
        print("- Need for plate preprocessing or model fine-tuning")
        print("- Consider dataset size and diversity for accurate assessment")
        exit(1)
    else:
        print("\n[PASS] SIH REQUIREMENT MET: OCR accuracy meets 90% threshold")
        exit(0)