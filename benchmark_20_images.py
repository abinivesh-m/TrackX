"""
Benchmark 20 random images from evaluation dataset using LPRNet.

This script tests OCR performance on a sample of 20 images to measure
LPRNet engine performance.
"""

import json
import random
import sys
import os
import cv2
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import using module syntax
import recognition.ocr_reader as ocr_reader_module
import recognition.plate_normalizer as plate_normalizer_module

def load_dataset(dataset_path):
    """Load the evaluation dataset."""
    with open(dataset_path, 'r') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        if 'entries' in data:
            return data
        else:
            return {'entries': data}
    return data

def benchmark_20_images(dataset_path, num_samples=20):
    """Benchmark OCR on random sample of images."""
    
    # Load dataset
    print(f"Loading dataset from {dataset_path}...")
    dataset = load_dataset(dataset_path)
    entries = dataset.get("entries", [])
    
    print(f"Total entries in dataset: {len(entries)}")
    
    # Select random sample
    random.seed(42)  # For reproducibility
    sample_entries = random.sample(entries, min(num_samples, len(entries)))
    print(f"Selected {len(sample_entries)} random images for benchmarking")
    
    # Initialize OCR reader
    print("Initializing OCR reader...")
    ocr = ocr_reader_module.PlateOCR()
    print(f"OCR Engine: {ocr.engine_type}")
    
    # Results tracking
    results = []
    exact_matches = 0
    total_processed = 0
    
    print("\n" + "="*80)
    print("BENCHMARK RESULTS")
    print("="*80)
    print(f"{'Image':<50} {'Ground Truth':<15} {'OCR Result':<15} {'Match':<6} {'Conf':<6}")
    print("="*80)
    
    # Process each entry
    for i, entry in enumerate(sample_entries):
        image_path = entry.get("image_path")
        ground_truth = entry.get("ground_truth")
        
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            continue
        
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            print(f"Failed to read image: {image_path}")
            continue
        
        # Run OCR
        ocr_text, confidence = ocr.read(image)
        
        if ocr_text is None:
            print(f"{os.path.basename(image_path):<50} {ground_truth:<15} {'NO OCR':<15} {'NO':<6} {0.0:<6.3f}")
            results.append({
                "image": os.path.basename(image_path),
                "ground_truth": ground_truth,
                "ocr_text": None,
                "confidence": 0.0,
                "match": False
            })
            continue
        
        # Normalize
        normalized_ground = plate_normalizer_module.normalize_indian_plate(ground_truth)[0]
        normalized_ocr = plate_normalizer_module.normalize_indian_plate(ocr_text)[0]
        
        # Check exact match
        is_match = (normalized_ocr == normalized_ground)
        
        if is_match:
            exact_matches += 1
        
        total_processed += 1
        
        # Print result
        match_str = "YES" if is_match else "NO"
        print(f"{os.path.basename(image_path):<50} {ground_truth:<15} {ocr_text:<15} {match_str:<6} {confidence:<6.3f}")
        
        results.append({
            "image": os.path.basename(image_path),
            "ground_truth": ground_truth,
            "normalized_ground": normalized_ground,
            "ocr_text": ocr_text,
            "normalized_ocr": normalized_ocr,
            "confidence": confidence,
            "match": is_match
        })
    
    print("="*80)
    
    # Calculate metrics
    accuracy = (exact_matches / total_processed * 100) if total_processed > 0 else 0
    avg_confidence = sum(r["confidence"] for r in results if r["confidence"] > 0) / total_processed if total_processed > 0 else 0
    
    print(f"\nBENCHMARK SUMMARY:")
    print(f"Total images processed: {total_processed}")
    print(f"Exact matches: {exact_matches}")
    print(f"Accuracy: {accuracy:.1f}%")
    print(f"Average confidence: {avg_confidence:.3f}")
    
    # Save results
    output_path = os.path.join(PROJECT_ROOT, "outputs", "benchmark_20_images_lprnet.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump({
            "ocr_engine": ocr.engine_type,
            "total_processed": total_processed,
            "exact_matches": exact_matches,
            "accuracy": round(accuracy, 1),
            "average_confidence": round(avg_confidence, 3),
            "results": results
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")
    
    return {
        "total_processed": total_processed,
        "exact_matches": exact_matches,
        "accuracy": accuracy,
        "average_confidence": avg_confidence
    }

if __name__ == "__main__":
    dataset_path = os.path.join(PROJECT_ROOT, "data", "ocr_eval", "clean_evaluation_dataset.json")
    
    results = benchmark_20_images(dataset_path, num_samples=20)
    
    print("\n" + "="*80)
    print("LPRNET BENCHMARK RESULTS (20 images):")
    print("="*80)
    print(f"  - Total samples: {results['total_processed']}")
    print(f"  - Exact matches: {results['exact_matches']} ({results['accuracy']:.1f}%)")
    print(f"  - Average confidence: {results['average_confidence']:.3f}")
    print("="*80)