"""
Evaluate Improved OCR Pipeline

This script runs the improved OCR pipeline on the evaluation dataset
to measure actual accuracy gains from the recent algorithmic improvements.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from recognition.ocr_reader import PlateOCR, try_init_ocr
from recognition.plate_normalizer import normalize_indian_plate


class ImprovedOCREvaluator:
    """Evaluate improved OCR pipeline on Indian license plate dataset."""
    
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.ocr = None
        self.results = []
        
    def init_ocr(self):
        """Initialize OCR engine with improvements."""
        print("[INIT] Initializing improved OCR engine...")

        try:
            from recognition.ocr_reader import PlateOCR
            self.ocr = PlateOCR(lang="en")
            print(f"[OK] OCR initialized: {self.ocr.engine_type}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OCR engine: {e}")
        
    def load_dataset(self) -> List[Dict]:
        """Load evaluation dataset with ground truth labels."""
        print(f"[LOAD] Loading dataset from {self.dataset_path}")
        
        # Try to load from JSON dataset file first
        json_file = self.dataset_path / "clean_evaluation_dataset.json"
        if json_file.exists():
            print(f"[JSON] Loading from JSON dataset: {json_file}")
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            dataset = []
            for entry in data.get('entries', []):
                dataset.append({
                    'image_path': entry['image_path'],
                    'ground_truth': entry['ground_truth'],
                    'image_name': Path(entry['image_path']).name,
                    'verification_status': entry.get('verification_status', 'unknown')
                })
            
            print(f"[OK] Loaded {len(dataset)} samples from JSON")
            return dataset
        
        # Fallback: Look for images and corresponding label files
        print("[FALLBACK] JSON not found, falling back to image/label file approach")
        dataset = []
        
        # Example: Look for images and corresponding label files
        image_files = list(self.dataset_path.glob("*.jpg")) + list(self.dataset_path.glob("*.png"))
        
        for img_file in image_files:
            # Try to find corresponding label file
            label_file = img_file.with_suffix('.txt')
            if label_file.exists():
                with open(label_file, 'r') as f:
                    ground_truth = f.read().strip()
                
                dataset.append({
                    'image_path': str(img_file),
                    'ground_truth': ground_truth,
                    'image_name': img_file.name
                })
        
        print(f"[OK] Loaded {len(dataset)} samples")
        return dataset
    
    def evaluate_sample(self, sample: Dict) -> Dict:
        """Evaluate OCR on a single sample."""
        import cv2
        
        # Load image
        image = cv2.imread(sample['image_path'])
        if image is None:
            return {
                'image_name': sample['image_name'],
                'ground_truth': sample['ground_truth'],
                'ocr_text': None,
                'confidence': 0.0,
                'error': 'Failed to load image'
            }
        
        # Run OCR
        start_time = time.time()
        ocr_text, confidence = self.ocr.read(image)
        processing_time = time.time() - start_time
        
        # Normalize results
        if ocr_text:
            normalized_text, pattern_matched = normalize_indian_plate(ocr_text)
        else:
            normalized_text = None
            pattern_matched = False
        
        # Compare with ground truth
        ground_truth = sample['ground_truth'].upper().replace(" ", "")
        if normalized_text:
            normalized_text = normalized_text.upper().replace(" ", "")
            exact_match = (normalized_text == ground_truth)
        else:
            exact_match = False
        
        # Character-level accuracy
        if normalized_text and ground_truth:
            char_accuracy = self._calculate_char_accuracy(normalized_text, ground_truth)
        else:
            char_accuracy = 0.0
        
        return {
            'image_name': sample['image_name'],
            'ground_truth': ground_truth,
            'raw_ocr_text': ocr_text,
            'normalized_text': normalized_text,
            'confidence': confidence,
            'processing_time': processing_time,
            'exact_match': exact_match,
            'char_accuracy': char_accuracy,
            'pattern_matched': pattern_matched,
            'error': None
        }
    
    def _calculate_char_accuracy(self, predicted: str, ground_truth: str) -> float:
        """Calculate character-level accuracy."""
        if not predicted or not ground_truth:
            return 0.0
        
        # Use the shorter length to avoid division by zero
        max_len = max(len(predicted), len(ground_truth))
        if max_len == 0:
            return 0.0
        
        # Count matching characters
        matches = sum(1 for p, g in zip(predicted, ground_truth) if p == g)
        
        return matches / max_len
    
    def run_evaluation(self, dataset: List[Dict]) -> Dict:
        """Run full evaluation on dataset."""
        print(f"[EVAL] Starting evaluation on {len(dataset)} samples...")
        
        exact_matches = 0
        total_char_accuracy = 0.0
        total_confidence = 0.0
        total_time = 0.0
        errors = []
        
        for i, sample in enumerate(dataset):
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i + 1}/{len(dataset)} samples")
            
            try:
                result = self.evaluate_sample(sample)
                self.results.append(result)
                
                if result['error']:
                    errors.append(result['image_name'])
                    continue
                
                if result['exact_match']:
                    exact_matches += 1
                
                total_char_accuracy += result['char_accuracy']
                total_confidence += result['confidence']
                total_time += result['processing_time']
                
            except Exception as e:
                print(f"[ERROR] Error processing {sample['image_name']}: {e}")
                errors.append(sample['image_name'])
        
        # Calculate overall metrics
        total_samples = len([r for r in self.results if not r['error']])
        
        metrics = {
            'total_samples': len(dataset),
            'successful_samples': total_samples,
            'failed_samples': len(errors),
            'exact_match_accuracy': exact_matches / total_samples if total_samples > 0 else 0.0,
            'character_accuracy': total_char_accuracy / total_samples if total_samples > 0 else 0.0,
            'average_confidence': total_confidence / total_samples if total_samples > 0 else 0.0,
            'average_processing_time': total_time / total_samples if total_samples > 0 else 0.0,
            'errors': errors
        }
        
        return metrics
    
    def generate_report(self, metrics: Dict, output_path: str = "improved_ocr_evaluation_report.json"):
        """Generate evaluation report."""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'ocr_engine': self.ocr.engine_type if self.ocr else 'unknown',
            'improvements_applied': [
                'Enhanced character confusion mappings (E<->3, A<->4, T<->7, L<->1)',
                'Adaptive multi-pass strategy (only for low confidence/invalid format)',
                'Multi-factor scoring (confidence, format, length, character distribution)'
            ],
            'metrics': metrics,
            'detailed_results': self.results
        }
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"[REPORT] Report saved to {output_path}")
        return report
    
    def print_summary(self, metrics: Dict):
        """Print evaluation summary."""
        print("\n" + "="*70)
        print("IMPROVED OCR EVALUATION SUMMARY")
        print("="*70)
        print(f"Total samples: {metrics['total_samples']}")
        print(f"Successful: {metrics['successful_samples']}")
        print(f"Failed: {metrics['failed_samples']}")
        print(f"\n[ACCURACY] ACCURACY METRICS:")
        print(f"  Exact-match accuracy: {metrics['exact_match_accuracy']:.1%}")
        print(f"  Character accuracy: {metrics['character_accuracy']:.1%}")
        print(f"  Average confidence: {metrics['average_confidence']:.3f}")
        print(f"\n[PERF] PERFORMANCE:")
        print(f"  Average processing time: {metrics['average_processing_time']:.3f}s per image")
        print(f"\n[IMPROVEMENT] IMPROVEMENT ANALYSIS:")
        print(f"  Previous accuracy: 22.7% (legacy OCR engine baseline)")
        print(f"  Current accuracy: {metrics['exact_match_accuracy']:.1%}")
        improvement = (metrics['exact_match_accuracy'] - 0.227) * 100
        print(f"  Improvement: {improvement:+.1f} percentage points")
        print("="*70)


def main():
    """Main evaluation function."""
    # Configuration
    dataset_path = "data/ocr_eval"  # Path to the evaluation dataset
    
    print("[EVAL] IMPROVED OCR PIPELINE EVALUATION")
    print("="*70)
    
    # Initialize evaluator
    evaluator = ImprovedOCREvaluator(dataset_path)
    
    try:
        # Initialize OCR
        evaluator.init_ocr()
        
        # Load dataset
        dataset = evaluator.load_dataset()
        if not dataset:
            print("❌ No samples found in dataset")
            return
        
        # Run evaluation
        metrics = evaluator.run_evaluation(dataset)
        
        # Generate report
        report = evaluator.generate_report(metrics)
        
        # Print summary
        evaluator.print_summary(metrics)
        
        print("\n[SUCCESS] Evaluation completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Evaluation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()