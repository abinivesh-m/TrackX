"""
Analyze error patterns in PaddleOCR results to identify improvement opportunities.
"""

import json
import sys
import os
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent

def analyze_errors(report_path):
    """Analyze error patterns in OCR results."""
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    results = report.get("results", [])
    error_breakdown = report.get("error_breakdown", {})
    
    print("="*80)
    print("ERROR PATTERN ANALYSIS")
    print("="*80)
    
    # Overall statistics
    total_samples = report.get("total_samples", 0)
    exact_matches = report.get("exact_matches", 0)
    accuracy = report.get("exact_match_accuracy", 0)
    
    print(f"\nOVERALL STATISTICS:")
    print(f"Total samples: {total_samples}")
    print(f"Exact matches: {exact_matches} ({accuracy}%)")
    print(f"Error breakdown: {error_breakdown}")
    
    # Analyze specific error types
    substitution_errors = []
    confusion_errors = []
    no_ocr_errors = []
    
    for result in results:
        if result.get("match", False):
            continue
            
        ground_truth = result.get("ground_truth", "")
        ocr_text = result.get("ocr_text", "")
        confidence = result.get("confidence", 0)
        
        if ocr_text is None:
            no_ocr_errors.append(result)
            continue
            
        # Character-level analysis
        if len(ground_truth) == len(ocr_text):
            # Check for single character substitutions
            diff_count = sum(1 for a, b in zip(ground_truth, ocr_text) if a != b)
            if diff_count == 1:
                # Find the substitution
                for i, (a, b) in enumerate(zip(ground_truth, ocr_text)):
                    if a != b:
                        substitution_errors.append({
                            "ground_truth": ground_truth,
                            "ocr_text": ocr_text,
                            "position": i,
                            "expected": a,
                            "got": b,
                            "confidence": confidence
                        })
                        break
            else:
                confusion_errors.append({
                    "ground_truth": ground_truth,
                    "ocr_text": ocr_text,
                    "diff_count": diff_count,
                    "confidence": confidence
                })
        else:
            confusion_errors.append({
                "ground_truth": ground_truth,
                "ocr_text": ocr_text,
                "diff_count": abs(len(ground_truth) - len(ocr_text)),
                "confidence": confidence
            })
    
    print(f"\n" + "="*80)
    print("SUBSTITUTION ERRORS (Single character mistakes):")
    print("="*80)
    
    # Count most common substitutions
    substitution_pairs = Counter()
    for error in substitution_errors:
        pair = f"{error['expected']} -> {error['got']}"
        substitution_pairs[pair] += 1
    
    print(f"Total substitution errors: {len(substitution_errors)}")
    print("\nMost common substitutions:")
    for pair, count in substitution_pairs.most_common(10):
        print(f"  {pair}: {count}")
    
    # Show examples
    print(f"\nExamples of substitution errors:")
    for i, error in enumerate(substitution_errors[:5]):
        print(f"  {error['ground_truth']} -> {error['ocr_text']} (pos {error['position']}, conf {error['confidence']:.3f})")
    
    print(f"\n" + "="*80)
    print("CONFUSION ERRORS (Multiple character mistakes):")
    print("="*80)
    
    print(f"Total confusion errors: {len(confusion_errors)}")
    
    # Analyze by confidence
    low_conf_confusion = [e for e in confusion_errors if e['confidence'] < 0.7]
    high_conf_confusion = [e for e in confusion_errors if e['confidence'] >= 0.7]
    
    print(f"  Low confidence (<0.7): {len(low_conf_confusion)}")
    print(f"  High confidence (>=0.7): {len(high_conf_confusion)}")
    
    print(f"\nExamples of confusion errors:")
    for i, error in enumerate(confusion_errors[:5]):
        print(f"  {error['ground_truth']} -> {error['ocr_text']} (diff {error['diff_count']}, conf {error['confidence']:.3f})")
    
    print(f"\n" + "="*80)
    print("NO OCR ERRORS:")
    print("="*80)
    
    print(f"Total no OCR errors: {len(no_ocr_errors)}")
    for error in no_ocr_errors:
        print(f"  {error['image_path']}")
    
    print(f"\n" + "="*80)
    print("CONFIDENCE ANALYSIS:")
    print("="*80)
    
    # Analyze confidence distribution
    confidences = [r.get("confidence", 0) for r in results if r.get("confidence", 0) > 0]
    
    if confidences:
        print(f"Average confidence: {sum(confidences)/len(confidences):.3f}")
        print(f"Min confidence: {min(confidences):.3f}")
        print(f"Max confidence: {max(confidences):.3f}")
        
        # Confidence buckets
        buckets = {
            "0.0-0.5": 0,
            "0.5-0.7": 0,
            "0.7-0.8": 0,
            "0.8-0.9": 0,
            "0.9-1.0": 0
        }
        
        for conf in confidences:
            if conf < 0.5:
                buckets["0.0-0.5"] += 1
            elif conf < 0.7:
                buckets["0.5-0.7"] += 1
            elif conf < 0.8:
                buckets["0.7-0.8"] += 1
            elif conf < 0.9:
                buckets["0.8-0.9"] += 1
            else:
                buckets["0.9-1.0"] += 1
        
        print(f"\nConfidence distribution:")
        for bucket, count in buckets.items():
            print(f"  {bucket}: {count} ({count/len(confidences)*100:.1f}%)")
    
    print(f"\n" + "="*80)
    print("RECOMMENDATIONS:")
    print("="*80)
    
    print("\n1. Focus on common character substitutions:")
    for pair, count in substitution_pairs.most_common(5):
        print(f"   - {pair}: appears {count} times")
    
    print("\n2. Address high-confidence confusion errors:")
    print(f"   - {len(high_conf_confusion)} errors with confidence >= 0.7")
    print(f"   - These may need better preprocessing or model fine-tuning")
    
    print("\n3. Improve preprocessing for low-confidence cases:")
    print(f"   - {len(low_conf_confusion)} errors with confidence < 0.7")
    print(f"   - Consider multi-pass OCR with different preprocessing")
    
    return {
        "substitution_errors": len(substitution_errors),
        "confusion_errors": len(confusion_errors),
        "no_ocr_errors": len(no_ocr_errors),
        "common_substitutions": dict(substitution_pairs.most_common(10))
    }

if __name__ == "__main__":
    report_path = os.path.join(PROJECT_ROOT, "outputs", "clean_ocr_evaluation_report.json")
    
    analysis = analyze_errors(report_path)