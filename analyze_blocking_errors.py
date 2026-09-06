"""
Analyze specific errors blocking 90% accuracy target.
Identify patterns in remaining failures to determine if 90% is achievable.
"""

import json
import sys
import os
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent

def analyze_blocking_errors(report_path):
    """Analyze remaining errors to identify what's blocking 90% target."""
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    results = report.get("results", [])
    total_samples = report.get("total_samples", 0)
    exact_matches = report.get("exact_matches", 0)
    current_accuracy = report.get("exact_match_accuracy", 0)
    
    print("="*80)
    print("BLOCKING ERRORS ANALYSIS FOR 90% TARGET")
    print("="*80)
    
    # Calculate what's needed for 90%
    needed_for_90 = int(total_samples * 0.90)
    needed_improvement = needed_for_90 - exact_matches
    
    print(f"\nCurrent Status:")
    print(f"  Total samples: {total_samples}")
    print(f"  Current matches: {exact_matches} ({current_accuracy}%)")
    print(f"  Target for 90%: {needed_for_90} matches")
    print(f"  Additional matches needed: {needed_improvement}")
    print(f"  Current failures: {total_samples - exact_matches}")
    
    # Analyze remaining failures
    failures = [r for r in results if not r.get("match", False)]
    
    print(f"\n" + "="*80)
    print("FAILURE BREAKDOWN")
    print("="*80)
    
    # Categorize by confidence
    high_conf_failures = [f for f in failures if f.get("confidence", 0) >= 0.9]
    medium_conf_failures = [f for f in failures if 0.7 <= f.get("confidence", 0) < 0.9]
    low_conf_failures = [f for f in failures if f.get("confidence", 0) < 0.7]
    
    print(f"\nHigh confidence failures (>=0.9): {len(high_conf_failures)}")
    print(f"Medium confidence failures (0.7-0.9): {len(medium_conf_failures)}")
    print(f"Low confidence failures (<0.7): {len(low_conf_failures)}")
    
    # Analyze high-confidence failures (these are the hardest to fix)
    print(f"\n" + "="*80)
    print("HIGH-CONFIDENCE FAILURES (OCR is confident but wrong)")
    print("="*80)
    
    for i, failure in enumerate(high_conf_failures[:20]):  # Show first 20
        ground_truth = failure.get("ground_truth", "")
        ocr_text = failure.get("ocr_text", "")
        confidence = failure.get("confidence", 0)
        
        # Calculate character differences
        if len(ground_truth) == len(ocr_text):
            diff_count = sum(1 for a, b in zip(ground_truth, ocr_text) if a != b)
            diff_type = f"{diff_count} char difference(s)"
        else:
            diff_type = f"length mismatch ({len(ground_truth)} vs {len(ocr_text)})"
        
        print(f"  {ground_truth} -> {ocr_text} (conf: {confidence:.3f}, {diff_type})")
    
    if len(high_conf_failures) > 20:
        print(f"  ... and {len(high_conf_failures) - 20} more high-confidence failures")
    
    # Analyze character-level errors in high-confidence failures
    print(f"\n" + "="*80)
    print("CHARACTER-LEVEL ERROR ANALYSIS (HIGH-CONFIDENCE FAILURES)")
    print("="*80)
    
    char_errors = Counter()
    position_errors = defaultdict(Counter)
    
    for failure in high_conf_failures:
        ground_truth = failure.get("ground_truth", "")
        ocr_text = failure.get("ocr_text", "")
        
        if len(ground_truth) == len(ocr_text):
            for i, (gt_char, ocr_char) in enumerate(zip(ground_truth, ocr_text)):
                if gt_char != ocr_char:
                    error_pair = f"{gt_char}->{ocr_char}"
                    char_errors[error_pair] += 1
                    position_errors[i][error_pair] += 1
    
    print(f"\nMost common character errors in high-confidence failures:")
    for error_pair, count in char_errors.most_common(10):
        print(f"  {error_pair}: {count} occurrences")
    
    print(f"\nErrors by position (0-indexed):")
    for pos, errors in sorted(position_errors.items()):
        print(f"  Position {pos}: {dict(errors.most_common(3))}")
    
    # Analyze low-confidence failures (these might be fixable)
    print(f"\n" + "="*80)
    print("LOW-CONFIDENCE FAILURES (Might be fixable with better preprocessing)")
    print("="*80)
    
    for i, failure in enumerate(low_conf_failures[:10]):  # Show first 10
        ground_truth = failure.get("ground_truth", "")
        ocr_text = failure.get("ocr_text", "")
        confidence = failure.get("confidence", 0)
        
        print(f"  {ground_truth} -> {ocr_text} (conf: {confidence:.3f})")
    
    if len(low_conf_failures) > 10:
        print(f"  ... and {len(low_conf_failures) - 10} more low-confidence failures")
    
    # Calculate potential improvement scenarios
    print(f"\n" + "="*80)
    print("POTENTIAL IMPROVEMENT SCENARIOS")
    print("="*80)
    
    # Scenario 1: Fix all low-confidence failures
    potential_low_conf_fix = len(low_conf_failures)
    potential_accuracy = ((exact_matches + potential_low_conf_fix) / total_samples) * 100
    print(f"  Fix all low-confidence failures: {potential_accuracy:.1f}% (+{potential_low_conf_fix} matches)")
    
    # Scenario 2: Fix half of high-confidence failures
    potential_high_conf_fix = len(high_conf_failures) // 2
    potential_accuracy2 = ((exact_matches + potential_low_conf_fix + potential_high_conf_fix) / total_samples) * 100
    print(f"  Fix low-confidence + half high-confidence: {potential_accuracy2:.1f}% (+{potential_low_conf_fix + potential_high_conf_fix} matches)")
    
    # Scenario 3: Fix all medium-confidence failures
    potential_medium_conf_fix = len(medium_conf_failures)
    potential_accuracy3 = ((exact_matches + potential_low_conf_fix + potential_medium_conf_fix) / total_samples) * 100
    print(f"  Fix low + medium confidence failures: {potential_accuracy3:.1f}% (+{potential_low_conf_fix + potential_medium_conf_fix} matches)")
    
    # Analysis of whether 90% is achievable
    print(f"\n" + "="*80)
    print("90% ACHIEVABILITY ASSESSMENT")
    print("="*80)
    
    total_fixable = len(low_conf_failures) + len(medium_conf_failures)
    remaining_high_conf = len(high_conf_failures)
    
    if total_fixable >= needed_improvement:
        print(f"  [OK] 90% IS ACHIEVABLE by fixing low/medium confidence failures")
        print(f"     Need to fix: {needed_improvement} out of {total_fixable} fixable failures")
        print(f"     Success rate required: {(needed_improvement/total_fixable)*100:.1f}% on fixable cases")
    else:
        additional_needed = needed_improvement - total_fixable
        print(f"  [WARNING] 90% REQUIRES fixing some high-confidence failures")
        print(f"     Fixable (low+medium conf): {total_fixable}")
        print(f"     Additional high-confidence fixes needed: {additional_needed} out of {remaining_high_conf}")
        print(f"     High-confidence fix rate required: {(additional_needed/remaining_high_conf)*100:.1f}%")
    
    # Specific error patterns that are blocking
    print(f"\n" + "="*80)
    print("SPECIFIC BLOCKING PATTERNS")
    print("="*80)
    
    # Look for systematic errors
    systematic_errors = []
    for error_pair, count in char_errors.most_common(5):
        if count >= 3:  # If same error appears 3+ times
            systematic_errors.append((error_pair, count))
    
    if systematic_errors:
        print(f"  Systematic character errors found:")
        for error_pair, count in systematic_errors:
            print(f"    {error_pair}: {count} times - could be addressed with normalization")
    else:
        print(f"  No systematic character errors - failures are diverse")
    
    # Check for plate format issues
    non_standard_plates = []
    for failure in failures:
        ground_truth = failure.get("ground_truth", "")
        # Check if ground truth follows standard pattern
        import re
        if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$", ground_truth):
            non_standard_plates.append(ground_truth)
    
    if non_standard_plates:
        print(f"\n  Non-standard plate formats in failures: {len(non_standard_plates)}")
        print(f"    Examples: {non_standard_plates[:5]}")
    
    return {
        "needed_for_90": needed_for_90,
        "needed_improvement": needed_improvement,
        "high_conf_failures": len(high_conf_failures),
        "medium_conf_failures": len(medium_conf_failures),
        "low_conf_failures": len(low_conf_failures),
        "fixable_failures": total_fixable,
        "achievable_90": total_fixable >= needed_improvement
    }

if __name__ == "__main__":
    report_path = os.path.join(PROJECT_ROOT, "outputs", "clean_ocr_evaluation_report.json")
    
    analysis = analyze_blocking_errors(report_path)