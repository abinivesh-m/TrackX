"""
Evaluate OCR on pre-cropped plate dataset.

This script evaluates OCR accuracy on the pre-cropped plate dataset
extracted from external XML annotations to achieve >90% accuracy.
"""

import json
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import using module syntax
import recognition.ocr_reader as ocr_reader_module
import recognition.plate_normalizer as plate_normalizer_module

def load_precropped_dataset(dataset_path):
    """Load the pre-cropped dataset."""
    with open(dataset_path, 'r') as f:
        data = json.load(f)
    
    # Handle both old format (dict with entries) and new format (dict with metadata + entries)
    if isinstance(data, dict):
        if 'entries' in data:
            return data
        else:
            # Old format without entries key
            return {'entries': data}
    return data

def evaluate_precropped_ocr(dataset_path, output_path):
    """Evaluate OCR on pre-cropped dataset."""
    
    # Load dataset
    print(f"Loading dataset from {dataset_path}...")
    dataset = load_precropped_dataset(dataset_path)
    
    entries = dataset.get("entries", [])
    metadata = dataset.get("metadata", {})
    
    print(f"Dataset metadata: {metadata}")
    print(f"Total entries: {len(entries)}")
    
    # Initialize OCR reader
    print("Initializing OCR reader...")
    ocr = ocr_reader_module.PlateOCR()
    
    # Evaluation metrics
    total_samples = len(entries)
    exact_matches = 0
    character_accuracy_sum = 0
    confidence_sum = 0
    no_ocr_count = 0
    error_breakdown = {
        "no_ocr": 0,
        "substitution_error": 0,
        "confusion": 0,
        "length_error": 0,
        "correct": 0
    }
    
    results = []
    
    # Process each entry
    for i, entry in enumerate(entries):
        if (i + 1) % 50 == 0:
            print(f"Processing {i + 1}/{len(entries)}...")
        
        image_path = entry.get("image_path")
        ground_truth = entry.get("ground_truth")
        
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            error_breakdown["no_ocr"] += 1
            no_ocr_count += 1
            continue
        
        # Read image
        import cv2
        image = cv2.imread(image_path)
        if image is None:
            print(f"Failed to read image: {image_path}")
            error_breakdown["no_ocr"] += 1
            no_ocr_count += 1
            continue
        
        # Run OCR
        ocr_text, confidence = ocr.read(image)
        
        if ocr_text is None:
            error_breakdown["no_ocr"] += 1
            no_ocr_count += 1
            results.append({
                "image_path": image_path,
                "ground_truth": ground_truth,
                "ocr_text": None,
                "normalized_ground_truth": plate_normalizer_module.normalize_indian_plate(ground_truth),
                "normalized_ocr": None,
                "confidence": 0.0,
                "match": False,
                "error_type": "no_ocr"
            })
            continue
        
        # Normalize
        normalized_ground = plate_normalizer_module.normalize_indian_plate(ground_truth)
        normalized_ocr = plate_normalizer_module.normalize_indian_plate(ocr_text)
        
        # Check exact match
        is_match = (normalized_ocr == normalized_ground)
        
        if is_match:
            exact_matches += 1
            error_breakdown["correct"] += 1
        else:
            # Classify error
            if len(normalized_ocr) != len(normalized_ground):
                error_breakdown["length_error"] += 1
            else:
                # Check for character substitutions
                substitutions = sum(1 for a, b in zip(normalized_ocr, normalized_ground) if a != b)
                if substitutions == 1:
                    error_breakdown["substitution_error"] += 1
                else:
                    error_breakdown["confusion"] += 1
        
        # Calculate character accuracy
        if len(normalized_ground) > 0:
            char_accuracy = sum(1 for a, b in zip(normalized_ocr, normalized_ground) if a == b) / len(normalized_ground)
            character_accuracy_sum += char_accuracy
        
        confidence_sum += confidence
        
        results.append({
            "image_path": image_path,
            "ground_truth": ground_truth,
            "ocr_text": ocr_text,
            "normalized_ground_truth": normalized_ground,
            "normalized_ocr": normalized_ocr,
            "confidence": confidence,
            "match": is_match,
            "error_type": "correct" if is_match else "mismatch"
        })
    
    # Calculate final metrics
    successful_ocr = total_samples - no_ocr_count
    exact_match_accuracy = (exact_matches / total_samples) * 100 if total_samples > 0 else 0
    average_character_accuracy = (character_accuracy_sum / total_samples) * 100 if total_samples > 0 else 0
    average_confidence = confidence_sum / total_samples if total_samples > 0 else 0
    
    # Create report
    report = {
        "timestamp": metadata.get("created"),
        "dataset_info": metadata,
        "total_samples": total_samples,
        "successful_ocr": successful_ocr,
        "failed_ocr": no_ocr_count,
        "exact_matches": exact_matches,
        "exact_match_accuracy": round(exact_match_accuracy, 1),
        "average_character_accuracy": round(average_character_accuracy, 1),
        "average_confidence": round(average_confidence, 3),
        "error_breakdown": error_breakdown,
        "sih_requirement_met": exact_match_accuracy >= 90.0,
        "results": results
    }
    
    # Save report
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "="*60)
    print("OCR EVALUATION SUMMARY")
    print("="*60)
    print(f"Total samples: {total_samples}")
    print(f"Successful OCR: {successful_ocr} ({successful_ocr/total_samples*100:.1f}%)")
    print(f"Failed OCR: {no_ocr_count} ({no_ocr_count/total_samples*100:.1f}%)")
    print(f"Exact matches: {exact_matches} ({exact_match_accuracy:.1f}%)")
    print(f"Average character accuracy: {average_character_accuracy:.1f}%")
    print(f"Average confidence: {average_confidence:.3f}")
    print("\nError breakdown:")
    for error_type, count in error_breakdown.items():
        print(f"  {error_type}: {count} ({count/total_samples*100:.1f}%)")
    print("="*60)
    
    if exact_match_accuracy >= 90.0:
        print("[PASS] SIH REQUIREMENT MET: OCR accuracy {:.1f}% >= 90%".format(exact_match_accuracy))
    else:
        print("[FAIL] SIH REQUIREMENT NOT MET: OCR accuracy {:.1f}% < 90%".format(exact_match_accuracy))
    print("="*60)
    
    print(f"\nReport saved to: {output_path}")
    
    return report

if __name__ == "__main__":
    dataset_path = os.path.join(PROJECT_ROOT, "data", "ocr_eval", "clean_evaluation_dataset.json")
    output_path = os.path.join(PROJECT_ROOT, "outputs", "clean_ocr_evaluation_report.json")
    
    evaluate_precropped_ocr(dataset_path, output_path)
