"""
Analyze OCR errors from the existing evaluation to identify specific failure patterns.
"""

import json
from collections import defaultdict
from config import RESULTS_DIR

# Load the evaluation report
with open(str(RESULTS_DIR / "clean_ocr_evaluation_report.json"), 'r') as f:
    report = json.load(f)

trials = report['trials']

# Analyze error patterns
error_analysis = {
    'no_ocr': [],
    'length_error': [],
    'substitution_error': [],
    'confusion': [],
    'correct': []
}

char_confusions = defaultdict(int)
prefix_issues = []
suffix_issues = []

for trial in trials:
    error_type = trial.get('error_type')
    ground_truth = trial.get('ground_truth')
    ocr_result = trial.get('ocr_result')
    
    if error_type:
        error_analysis[error_type].append({
            'image_path': trial['image_path'],
            'ground_truth': ground_truth,
            'ocr_result': ocr_result,
            'confidence': trial['confidence']
        })
        
        # Analyze specific patterns
        if error_type == 'substitution_error' and ocr_result and ground_truth:
            # Find character confusions
            for i, (gt_char, ocr_char) in enumerate(zip(ground_truth, ocr_result)):
                if gt_char != ocr_char:
                    char_confusions[f"{gt_char}->{ocr_char}"] += 1
        
        if error_type == 'length_error' and ocr_result and ground_truth:
            # Check for prefix/suffix issues
            if ocr_result.startswith(ground_truth):
                suffix_issues.append((ground_truth, ocr_result))
            elif ground_truth in ocr_result:
                # Find where ground truth appears
                idx = ocr_result.find(ground_truth)
                if idx > 0:
                    prefix_issues.append((ground_truth, ocr_result, ocr_result[:idx]))
    else:
        error_analysis['correct'].append({
            'image_path': trial['image_path'],
            'ground_truth': ground_truth,
            'ocr_result': ocr_result,
            'confidence': trial['confidence']
        })

print("="*60)
print("OCR ERROR ANALYSIS")
print("="*60)

print(f"\nTotal samples: {report['total_samples']}")
print(f"Exact matches: {report['exact_matches']} ({report['exact_accuracy']*100:.1f}%)")
print(f"Character accuracy: {report['avg_character_accuracy']*100:.1f}%")

print(f"\nError breakdown:")
for error_type, errors in error_analysis.items():
    print(f"  {error_type}: {len(errors)}")

print(f"\nTop character confusions:")
for confusion, count in sorted(char_confusions.items(), key=lambda x: -x[1])[:10]:
    print(f"  {confusion}: {count}")

print(f"\nPrefix issues (OCR adds text before plate):")
for i, (gt, ocr, prefix) in enumerate(prefix_issues[:10]):
    print(f"  {i+1}. GT: {gt}, OCR: {ocr}, Prefix: '{prefix}'")

print(f"\nSuffix issues (OCR adds text after plate):")
for i, (gt, ocr) in enumerate(suffix_issues[:10]):
    print(f"  {i+1}. GT: {gt}, OCR: {ocr}")

print(f"\nNo-OCR samples (first 10):")
for i, error in enumerate(error_analysis['no_ocr'][:10]):
    print(f"  {i+1}. {error['image_path']}")

# Save detailed analysis
with open(str(RESULTS_DIR / "ocr_error_analysis.json"), 'w') as f:
    json.dump({
        'error_analysis': error_analysis,
        'char_confusions': dict(char_confusions),
        'prefix_issues': prefix_issues,
        'suffix_issues': suffix_issues
    }, f, indent=2)

print(f"\nDetailed analysis saved to: outputs/ocr_error_analysis.json")
