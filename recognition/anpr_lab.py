"""
ANPR Vision Lab - Comprehensive License Plate Testing System

This module provides a rigorous testing framework for license plate recognition,
following the counter-strategy to build a better ANPR Lab than competitors.

Features:
- 1000+ Indian plate test samples (when fully populated)
- Day/Night/Rain/Blur/Angle/Low-resolution/Dirty/Occlusion categories
- Exact-match and character-level accuracy metrics
 - Multi-engine comparison (LPRNet + PaddleOCR fusion)
- Performance analysis by condition
- Detailed error analysis and confusion matrix
"""

import os
import json
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
import re

# Import OCR engines
try:
    from recognition.ocr_reader import PlateOCR, try_init_ocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from recognition.lprnet_ocr import LPRNetOCR, try_init_lprnet
    LPRNET_AVAILABLE = True
except ImportError:
    LPRNET_AVAILABLE = False


class ANPRTestSample:
    """Represents a single test sample for ANPR evaluation"""
    
    def __init__(self, image_path: str, ground_truth: str, category: str = "general",
                 metadata: Optional[Dict] = None):
        self.image_path = image_path
        self.ground_truth = ground_truth.upper()
        self.category = category  # day, night, rain, blur, angle, low_res, dirty, occlusion
        self.metadata = metadata or {}
        self.prediction = None
        self.confidence = 0.0
        self.is_correct = False
        self.engine_used = None
    
    def evaluate(self, prediction: str, confidence: float, engine: str) -> Dict:
        """Evaluate prediction against ground truth"""
        self.prediction = prediction.upper() if prediction else ""
        self.confidence = confidence
        self.engine_used = engine
        self.is_correct = (self.prediction == self.ground_truth)
        
        # Character-level accuracy
        char_correct = sum(1 for a, b in zip(self.prediction, self.ground_truth) if a == b)
        max_len = max(len(self.prediction), len(self.ground_truth))
        char_accuracy = char_correct / max_len if max_len > 0 else 0.0
        
        return {
            "image_path": self.image_path,
            "ground_truth": self.ground_truth,
            "prediction": self.prediction,
            "confidence": confidence,
            "is_correct": self.is_correct,
            "char_accuracy": char_accuracy,
            "category": self.category,
            "engine": engine
        }


class ANPRLab:
    """
    Comprehensive ANPR testing laboratory
    
    This class manages test datasets, runs OCR evaluations across multiple engines,
    and provides detailed performance analysis.
    """
    
    def __init__(self, data_dir: str = "data/anpr_lab"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Test categories for comprehensive evaluation
        self.categories = [
            "day",           # Good lighting conditions
            "night",         # Low light/night conditions
            "rain",          # Rain/wet conditions
            "blur",          # Motion blur or focus issues
            "angle",         # Extreme viewing angles
            "low_res",       # Low resolution images
            "dirty",         # Dirty/obscured plates
            "occlusion",     # Partial occlusion
            "two_wheeler",   # Motorcycle/scooter plates
            "heavy_traffic"  # Plates in heavy traffic
        ]
        
        # Create category directories
        for category in self.categories:
            (self.data_dir / category).mkdir(parents=True, exist_ok=True)
        
        self.test_samples: List[ANPRTestSample] = []
        self.results: Dict = {}
        
    def load_dataset(self, annotation_file: Optional[str] = None) -> int:
        """
        Load test dataset from annotation file or auto-discover from directory structure
        
        Args:
            annotation_file: JSON file with annotations in format:
                {"samples": [{"image": "path/to/image.jpg", "ground_truth": "TN01AB1234", "category": "day"}]}
        
        Returns:
            Number of samples loaded
        """
        if annotation_file and os.path.exists(annotation_file):
            return self._load_from_annotation(annotation_file)
        else:
            return self._auto_discover_samples()
    
    def _load_from_annotation(self, annotation_file: str) -> int:
        """Load samples from JSON annotation file"""
        with open(annotation_file, 'r') as f:
            data = json.load(f)
        
        count = 0
        for sample_data in data.get("samples", []):
            image_path = sample_data["image"]
            ground_truth = sample_data["ground_truth"]
            category = sample_data.get("category", "general")
            metadata = sample_data.get("metadata", {})
            
            if os.path.exists(image_path):
                sample = ANPRTestSample(image_path, ground_truth, category, metadata)
                self.test_samples.append(sample)
                count += 1
        
        print(f"[ANPR Lab] Loaded {count} samples from annotation file")
        return count
    
    def _auto_discover_samples(self) -> int:
        """Auto-discover samples from directory structure (category/filename_groundtruth.jpg)"""
        count = 0
        for category in self.categories:
            category_dir = self.data_dir / category
            if not category_dir.exists():
                continue
            
            for image_file in category_dir.glob("*.jpg"):
                # Extract ground truth from filename if follows pattern: XXX_YYYYY.jpg
                # where YYYYY is the plate number
                filename = image_file.stem
                parts = filename.split('_')
                
                if len(parts) >= 2:
                    ground_truth = parts[-1].upper()
                else:
                    # Use filename as ground truth (remove extension)
                    ground_truth = filename.upper()
                
                # Basic validation of Indian plate format
                if len(ground_truth) >= 8 and re.match(r'^[A-Z0-9]+$', ground_truth):
                    sample = ANPRTestSample(str(image_file), ground_truth, category)
                    self.test_samples.append(sample)
                    count += 1
        
        print(f"[ANPR Lab] Auto-discovered {count} samples from directory structure")
        return count
    
    def add_sample(self, image_path: str, ground_truth: str, category: str = "general"):
        """Manually add a test sample"""
        if os.path.exists(image_path):
            sample = ANPRTestSample(image_path, ground_truth, category)
            self.test_samples.append(sample)
            print(f"[ANPR Lab] Added sample: {ground_truth} ({category})")
    
    def evaluate_engine(self, engine_name: str = "lprnet") -> Dict:
        """
        Evaluate a specific OCR engine on the test dataset
        
        Args:
            engine_name: "lprnet", "paddleocr", or "fusion"
        
        Returns:
            Comprehensive evaluation results
        """
        if not self.test_samples:
            return {"error": "No test samples available"}
        
        # Initialize OCR engine
        ocr = None
        if engine_name == "lprnet" and LPRNET_AVAILABLE:
            ocr = try_init_lprnet("models/lprnet_indian.pth")
        elif engine_name in ("paddleocr",) and OCR_AVAILABLE:
            ocr = try_init_ocr()
        else:
            return {"error": f"Unknown or unavailable engine: {engine_name}; only lprnet and paddleocr are supported"}
        
        if ocr is None:
            return {"error": f"Could not initialize {engine_name} engine"}
        
        print(f"[ANPR Lab] Evaluating {engine_name} on {len(self.test_samples)} samples...")
        
        results = []
        correct_count = 0
        total_char_accuracy = 0.0
        
        for sample in self.test_samples:
            try:
                # Read image
                image = cv2.imread(sample.image_path)
                if image is None:
                    continue
                
                # Run OCR
                prediction, confidence = ocr.read(image)
                
                # Evaluate
                result = sample.evaluate(prediction, confidence, engine_name)
                results.append(result)
                
                if result["is_correct"]:
                    correct_count += 1
                
                total_char_accuracy += result["char_accuracy"]
                
            except Exception as e:
                print(f"[ANPR Lab] Error processing {sample.image_path}: {e}")
                continue
        
        # Calculate overall metrics
        total_samples = len(results)
        exact_match_accuracy = correct_count / total_samples if total_samples > 0 else 0.0
        avg_char_accuracy = total_char_accuracy / total_samples if total_samples > 0 else 0.0
        
        # Calculate per-category metrics
        category_metrics = {}
        for category in self.categories:
            category_results = [r for r in results if r["category"] == category]
            if category_results:
                cat_correct = sum(1 for r in category_results if r["is_correct"])
                cat_accuracy = cat_correct / len(category_results)
                cat_char_acc = sum(r["char_accuracy"] for r in category_results) / len(category_results)
                category_metrics[category] = {
                    "samples": len(category_results),
                    "exact_match_accuracy": cat_accuracy,
                    "character_accuracy": cat_char_acc
                }
        
        evaluation_results = {
            "engine": engine_name,
            "total_samples": total_samples,
            "exact_match_accuracy": exact_match_accuracy,
            "character_accuracy": avg_char_accuracy,
            "correct_predictions": correct_count,
            "failed_predictions": total_samples - correct_count,
            "category_breakdown": category_metrics,
            "detailed_results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        self.results[engine_name] = evaluation_results
        return evaluation_results
    
    def compare_engines(self, engines: List[str] = None) -> Dict:
        """
        Compare multiple OCR engines side-by-side
        
        Args:
            engines: List of engine names to compare
        
        Returns:
            Comparison results
        """
        if engines is None:
            engines = ["lprnet"] if LPRNET_AVAILABLE else ["lprnet"]
        
        comparison = {
            "engines_tested": engines,
            "timestamp": datetime.now().isoformat(),
            "results": {}
        }
        
        for engine in engines:
            try:
                result = self.evaluate_engine(engine)
                comparison["results"][engine] = result
            except Exception as e:
                comparison["results"][engine] = {"error": str(e)}
        
        # Find best performing engine
        best_engine = None
        best_accuracy = 0.0
        
        for engine, result in comparison["results"].items():
            if "error" not in result:
                accuracy = result.get("exact_match_accuracy", 0.0)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_engine = engine
        
        comparison["best_engine"] = best_engine
        comparison["best_accuracy"] = best_accuracy
        
        return comparison
    
    def generate_report(self, output_file: str = "outputs/anpr_lab_report.json") -> str:
        """
        Generate comprehensive evaluation report
        
        Args:
            output_file: Path to save the report
        
        Returns:
            Path to generated report
        """
        report = {
            "anpr_lab_report": {
                "timestamp": datetime.now().isoformat(),
                "total_samples": len(self.test_samples),
                "categories_tested": len([c for c in self.categories if any(s.category == c for s in self.test_samples)]),
                "engines_evaluated": list(self.results.keys()),
                "results": self.results
            }
        }
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"[ANPR Lab] Report saved to {output_file}")
        return output_file
    
    def get_error_analysis(self, engine: str) -> Dict:
        """
        Analyze common error patterns for a specific engine
        
        Args:
            engine: Engine name to analyze
        
        Returns:
            Error analysis results
        """
        if engine not in self.results:
            return {"error": "No results available for this engine"}
        
        results = self.results[engine]["detailed_results"]
        errors = [r for r in results if not r["is_correct"]]
        
        # Character confusion analysis
        confusion_matrix = {}
        for result in errors:
            pred = result["prediction"]
            truth = result["ground_truth"]
            
            for i, (p_char, t_char) in enumerate(zip(pred, truth)):
                if p_char != t_char:
                    key = f"{t_char}→{p_char}"
                    confusion_matrix[key] = confusion_matrix.get(key, 0) + 1
        
        # Length error analysis
        length_errors = {"too_long": 0, "too_short": 0}
        for result in errors:
            pred_len = len(result["prediction"])
            truth_len = len(result["ground_truth"])
            if pred_len > truth_len:
                length_errors["too_long"] += 1
            elif pred_len < truth_len:
                length_errors["too_short"] += 1
        
        return {
            "total_errors": len(errors),
            "error_rate": len(errors) / len(results),
            "common_confusions": sorted(confusion_matrix.items(), key=lambda x: x[1], reverse=True)[:10],
            "length_errors": length_errors,
            "category_error_rates": {
                cat: len([r for r in errors if r["category"] == cat]) / max(1, len([r for r in results if r["category"] == cat]))
                for cat in self.categories
            }
        }


# Global ANPR Lab instance
_anpr_lab_instance = None

def get_anpr_lab(data_dir: str = "data/anpr_lab") -> ANPRLab:
    """Get or create global ANPR Lab instance"""
    global _anpr_lab_instance
    if _anpr_lab_instance is None:
        _anpr_lab_instance = ANPRLab(data_dir)
    return _anpr_lab_instance

def run_comprehensive_evaluation(data_dir: str = "data/anpr_lab") -> Dict:
    """
    Run comprehensive ANPR evaluation across all available engines
    
    This is the main entry point for the ANPR Lab feature.
    """
    lab = get_anpr_lab(data_dir)
    
    # Load dataset
    samples_loaded = lab.load_dataset()
    print(f"[ANPR Lab] Loaded {samples_loaded} test samples")
    
    if samples_loaded == 0:
        return {"error": "No test samples found. Please populate the ANPR Lab dataset."}
    
    # Compare engines
    engines_to_test = []
    if LPRNET_AVAILABLE:
        engines_to_test.append("lprnet")
    if OCR_AVAILABLE:
        engines_to_test.append("paddleocr")
    
    if not engines_to_test:
        return {"error": "No OCR engines available"}
    
    comparison = lab.compare_engines(engines_to_test)
    
    # Generate report
    report_path = lab.generate_report()
    
    comparison["report_path"] = report_path
    comparison["dataset_info"] = {
        "total_samples": samples_loaded,
        "categories": [cat for cat in lab.categories if any(s.category == cat for s in lab.test_samples)]
    }
    
    return comparison