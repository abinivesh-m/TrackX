"""
Comprehensive OCR benchmark comparing LPRNet, PaddleOCR, and fusion on the clean dataset.
This provides honest, measured results for the SIH-26127 requirements.
"""

import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import time
from collections import defaultdict

# Import OCR engines
from recognition.lprnet_ocr import try_init_lprnet
from recognition.ocr_reader import PlateOCR, vote_plate_text

def load_clean_dataset(dataset_path: str) -> List[Dict]:
    """Load the clean test dataset."""
    with open(dataset_path, 'r') as f:
        data = json.load(f)
    return data['entries']

def evaluate_single_engine(ocr_engine, dataset: List[Dict], engine_name: str) -> Dict:
    """
    Evaluate a single OCR engine on the dataset.
    
    Returns comprehensive metrics including:
    - Exact match accuracy
    - Character accuracy
    - Error breakdown
    - Processing time
    - Confidence distribution
    """
    results = {
        'engine_name': engine_name,
        'total_samples': len(dataset),
        'successful_ocr': 0,
        'failed_ocr': 0,
        'exact_matches': 0,
        'character_matches': 0,
        'total_characters': 0,
        'errors': defaultdict(int),
        'processing_times': [],
        'confidences': [],
        'detailed_results': []
    }
    
    print(f"\nEvaluating {engine_name}...")
    
    for entry in dataset:
        # Handle both image_path and filename formats
        if 'image_path' in entry:
            image_path = entry['image_path']
        elif 'filename' in entry:
            # Construct path from filename, try multiple possible locations
            filename = entry['filename']
            possible_paths = [
                f"data/ocr_eval/plate_crops_external/{filename}",
                f"data/ocr_eval/plate_crops_additional/{filename}",
                f"data/ocr_eval/huggingface_import/{filename}"
            ]
            image_path = None
            for path in possible_paths:
                if Path(path).exists():
                    image_path = path
                    break
            if not image_path:
                results['failed_ocr'] += 1
                results['errors']['file_not_found'] += 1
                continue
        else:
            results['failed_ocr'] += 1
            results['errors']['invalid_entry'] += 1
            continue
            
        ground_truth = entry['ground_truth']
        
        # Load image
        try:
            img = cv2.imread(image_path)
            if img is None:
                results['failed_ocr'] += 1
                results['errors']['image_load_failed'] += 1
                continue
        except Exception as e:
            results['failed_ocr'] += 1
            results['errors']['image_load_failed'] += 1
            continue
        
        # Run OCR
        start_time = time.time()
        try:
            # Handle different OCR engine interfaces
            if hasattr(ocr_engine, 'read_plate'):
                # LPRNet interface
                text, confidence = ocr_engine.read_plate(img)
            elif hasattr(ocr_engine, 'read'):
                # PlateOCR interface
                text, confidence = ocr_engine.read(img)
            else:
                raise AttributeError("OCR engine has no recognized read method")
            processing_time = time.time() - start_time
            results['processing_times'].append(processing_time)
            
            if text and confidence > 0:
                results['successful_ocr'] += 1
                results['confidences'].append(confidence)
                
                # Normalize both text and ground truth
                normalized_text = ''.join(c for c in text.upper() if c.isalnum())
                normalized_gt = ''.join(c for c in ground_truth.upper() if c.isalnum())
                
                # Exact match check
                if normalized_text == normalized_gt:
                    results['exact_matches'] += 1
                    error_type = 'correct'
                else:
                    # Character-level comparison
                    char_matches = sum(1 for a, b in zip(normalized_text, normalized_gt) if a == b)
                    results['character_matches'] += char_matches
                    results['total_characters'] += max(len(normalized_text), len(normalized_gt))
                    
                    # Categorize error
                    if len(normalized_text) != len(normalized_gt):
                        error_type = 'length_error'
                    elif sum(1 for a, b in zip(normalized_text, normalized_gt) if a != b) == 1:
                        error_type = 'substitution_error'
                    else:
                        error_type = 'confusion'
                    
                    results['errors'][error_type] += 1
            else:
                results['failed_ocr'] += 1
                results['errors']['no_ocr'] += 1
                
        except Exception as e:
            results['failed_ocr'] += 1
            results['errors']['ocr_exception'] += 1
            continue
        
        # Store detailed result
        results['detailed_results'].append({
            'image_path': image_path,
            'filename': entry.get('filename', ''),
            'ground_truth': ground_truth,
            'predicted_text': text if text else None,
            'confidence': confidence if confidence else 0.0,
            'processing_time': processing_time,
            'error_type': error_type if text and confidence > 0 else 'no_ocr'
        })
    
    # Calculate derived metrics
    results['exact_match_accuracy'] = results['exact_matches'] / results['total_samples'] if results['total_samples'] > 0 else 0
    results['character_accuracy'] = results['character_matches'] / results['total_characters'] if results['total_characters'] > 0 else 0
    results['success_rate'] = results['successful_ocr'] / results['total_samples'] if results['total_samples'] > 0 else 0
    results['avg_processing_time'] = np.mean(results['processing_times']) if results['processing_times'] else 0
    results['avg_confidence'] = np.mean(results['confidences']) if results['confidences'] else 0
    
    return results

def evaluate_fusion(lprnet_engine, paddleocr_engine, dataset: List[Dict]) -> Dict:
    """
    Evaluate fusion approach using both LPRNet and PaddleOCR with voting.
    """
    results = {
        'engine_name': 'LPRNet_PaddleOCR_Fusion',
        'total_samples': len(dataset),
        'successful_ocr': 0,
        'failed_ocr': 0,
        'exact_matches': 0,
        'character_matches': 0,
        'total_characters': 0,
        'errors': defaultdict(int),
        'processing_times': [],
        'confidences': [],
        'detailed_results': []
    }
    
    print(f"\nEvaluating LPRNet + PaddleOCR Fusion...")
    
    for entry in dataset:
        # Handle both image_path and filename formats
        if 'image_path' in entry:
            image_path = entry['image_path']
        elif 'filename' in entry:
            # Construct path from filename, try multiple possible locations
            filename = entry['filename']
            possible_paths = [
                f"data/ocr_eval/plate_crops_external/{filename}",
                f"data/ocr_eval/plate_crops_additional/{filename}",
                f"data/ocr_eval/huggingface_import/{filename}"
            ]
            image_path = None
            for path in possible_paths:
                if Path(path).exists():
                    image_path = path
                    break
            if not image_path:
                results['failed_ocr'] += 1
                results['errors']['file_not_found'] += 1
                continue
        else:
            results['failed_ocr'] += 1
            results['errors']['invalid_entry'] += 1
            continue
            
        ground_truth = entry['ground_truth']
        
        # Load image
        try:
            img = cv2.imread(image_path)
            if img is None:
                results['failed_ocr'] += 1
                results['errors']['image_load_failed'] += 1
                continue
        except Exception as e:
            results['failed_ocr'] += 1
            results['errors']['image_load_failed'] += 1
            continue
        
        # Run OCR with both engines
        start_time = time.time()
        ocr_results = []
        
        try:
            if lprnet_engine:
                lprnet_text, lprnet_conf = lprnet_engine.read_plate(img)
                if lprnet_text and lprnet_conf > 0:
                    ocr_results.append((lprnet_text, lprnet_conf))
        except Exception as e:
            pass
        
        try:
            if paddleocr_engine:
                paddleocr_text, paddleocr_conf = paddleocr_engine.read(img)
                if paddleocr_text and paddleocr_conf > 0:
                    ocr_results.append((paddleocr_text, paddleocr_conf))
        except Exception as e:
            pass
        
        processing_time = time.time() - start_time
        results['processing_times'].append(processing_time)
        
        # Apply voting
        if ocr_results:
            fused_text, fused_conf, vote_count = vote_plate_text(ocr_results)
            
            if fused_text:
                results['successful_ocr'] += 1
                results['confidences'].append(fused_conf)
                
                # Normalize both text and ground truth
                normalized_text = ''.join(c for c in fused_text.upper() if c.isalnum())
                normalized_gt = ''.join(c for c in ground_truth.upper() if c.isalnum())
                
                # Exact match check
                if normalized_text == normalized_gt:
                    results['exact_matches'] += 1
                    error_type = 'correct'
                else:
                    # Character-level comparison
                    char_matches = sum(1 for a, b in zip(normalized_text, normalized_gt) if a == b)
                    results['character_matches'] += char_matches
                    results['total_characters'] += max(len(normalized_text), len(normalized_gt))
                    
                    # Categorize error
                    if len(normalized_text) != len(normalized_gt):
                        error_type = 'length_error'
                    elif sum(1 for a, b in zip(normalized_text, normalized_gt) if a != b) == 1:
                        error_type = 'substitution_error'
                    else:
                        error_type = 'confusion'
                    
                    results['errors'][error_type] += 1
            else:
                results['failed_ocr'] += 1
                results['errors']['no_ocr'] += 1
        else:
            results['failed_ocr'] += 1
            results['errors']['no_ocr'] += 1
        
        # Store detailed result
        results['detailed_results'].append({
            'image_path': image_path,
            'filename': entry.get('filename', ''),
            'ground_truth': ground_truth,
            'predicted_text': fused_text if ocr_results else None,
            'confidence': fused_conf if ocr_results else 0.0,
            'vote_count': vote_count if ocr_results else 0,
            'processing_time': processing_time,
            'error_type': error_type if ocr_results and fused_text else 'no_ocr'
        })
    
    # Calculate derived metrics
    results['exact_match_accuracy'] = results['exact_matches'] / results['total_samples'] if results['total_samples'] > 0 else 0
    results['character_accuracy'] = results['character_matches'] / results['total_characters'] if results['total_characters'] > 0 else 0
    results['success_rate'] = results['successful_ocr'] / results['total_samples'] if results['total_samples'] > 0 else 0
    results['avg_processing_time'] = np.mean(results['processing_times']) if results['processing_times'] else 0
    results['avg_confidence'] = np.mean(results['confidences']) if results['confidences'] else 0
    
    return results

def generate_benchmark_report(lprnet_results, paddleocr_results, fusion_results) -> Dict:
    """Generate comprehensive benchmark report."""
    
    report = {
        'benchmark_timestamp': '2026-09-05T15:00:00',
        'dataset_info': {
            'total_samples': lprnet_results['total_samples'],
            'dataset_path': 'data/ocr_eval/test_dataset_clean.json'
        },
        'engines_tested': [],
        'comparison': {},
        'sih_compliance': {
            'target_accuracy': 0.90,
            'best_achieved_accuracy': 0.0,
            'compliance_status': 'NOT_MET'
        }
    }
    
    # Add individual engine results
    for results in [lprnet_results, paddleocr_results, fusion_results]:
        engine_summary = {
            'name': results['engine_name'],
            'exact_match_accuracy': round(results['exact_match_accuracy'] * 100, 2),
            'character_accuracy': round(results['character_accuracy'] * 100, 2) if results['character_accuracy'] > 0 else 0,
            'success_rate': round(results['success_rate'] * 100, 2),
            'avg_confidence': round(results['avg_confidence'], 3),
            'avg_processing_time': round(results['avg_processing_time'], 4),
            'error_breakdown': dict(results['errors'])
        }
        report['engines_tested'].append(engine_summary)
        
        # Track best accuracy
        if results['exact_match_accuracy'] > report['sih_compliance']['best_achieved_accuracy']:
            report['sih_compliance']['best_achieved_accuracy'] = results['exact_match_accuracy']
    
    # Check SIH compliance
    if report['sih_compliance']['best_achieved_accuracy'] >= 0.90:
        report['sih_compliance']['compliance_status'] = 'MET'
    
    # Comparison analysis
    report['comparison']['best_engine'] = max(report['engines_tested'], key=lambda x: x['exact_match_accuracy'])
    report['comparison']['accuracy_range'] = {
        'min': min(e['exact_match_accuracy'] for e in report['engines_tested']),
        'max': max(e['exact_match_accuracy'] for e in report['engines_tested'])
    }
    
    return report

def main():
    print("=" * 70)
    print("TrackX OCR Engine Benchmark - SIH-26127")
    print("=" * 70)
    
    # Load clean test dataset
    dataset_path = "data/ocr_eval/test_dataset_clean.json"
    if not Path(dataset_path).exists():
        print(f"Error: Dataset not found at {dataset_path}")
        print("Please run create_clean_dataset_split.py first")
        return
    
    dataset = load_clean_dataset(dataset_path)
    print(f"Loaded {len(dataset)} test samples")
    
    # Initialize OCR engines
    print("\nInitializing OCR engines...")
    
    # Try LPRNet
    lprnet_engine = try_init_lprnet("models/lprnet_indian.pth")
    if lprnet_engine:
        print("[OK] LPRNet initialized successfully")
    else:
        print("[FAIL] LPRNet not available (no trained weights)")
    
    # Try PaddleOCR
    try:
        paddleocr_engine = PlateOCR()
        if paddleocr_engine.engine_type == "paddleocr":
            print("[OK] PaddleOCR initialized successfully")
        else:
            print(f"[FAIL] PaddleOCR not available (using {paddleocr_engine.engine_type})")
            paddleocr_engine = None
    except Exception as e:
        print(f"[FAIL] PaddleOCR initialization failed: {e}")
        paddleocr_engine = None
    
    # Run benchmarks
    results = {}
    
    if lprnet_engine:
        results['lprnet'] = evaluate_single_engine(lprnet_engine, dataset, "LPRNet")
    
    if paddleocr_engine:
        results['paddleocr'] = evaluate_single_engine(paddleocr_engine, dataset, "PaddleOCR")
    
    if lprnet_engine and paddleocr_engine:
        results['fusion'] = evaluate_fusion(lprnet_engine, paddleocr_engine, dataset)
    
    # Generate report
    if results:
        lprnet_results = results.get('lprnet', {
            'engine_name': 'LPRNet', 
            'exact_match_accuracy': 0, 'character_accuracy': 0, 'success_rate': 0, 
            'avg_confidence': 0, 'avg_processing_time': 0, 'errors': {}, 'total_samples': len(dataset)
        })
        paddleocr_results = results.get('paddleocr', {
            'engine_name': 'PaddleOCR',
            'exact_match_accuracy': 0, 'character_accuracy': 0, 'success_rate': 0, 
            'avg_confidence': 0, 'avg_processing_time': 0, 'errors': {}, 'total_samples': len(dataset)
        })
        fusion_results = results.get('fusion', {
            'engine_name': 'LPRNet_PaddleOCR_Fusion',
            'exact_match_accuracy': 0, 'character_accuracy': 0, 'success_rate': 0, 
            'avg_confidence': 0, 'avg_processing_time': 0, 'errors': {}, 'total_samples': len(dataset)
        })
        
        report = generate_benchmark_report(lprnet_results, paddleocr_results, fusion_results)
        
        # Save report
        output_path = "outputs/ocr_benchmark_report.json"
        Path("outputs").mkdir(exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n" + "=" * 70)
        print("BENCHMARK RESULTS")
        print("=" * 70)
        
        for engine in report['engines_tested']:
            print(f"\n{engine['name']}:")
            print(f"  Exact Match Accuracy: {engine['exact_match_accuracy']}%")
            print(f"  Character Accuracy: {engine['character_accuracy']}%")
            print(f"  Success Rate: {engine['success_rate']}%")
            print(f"  Average Confidence: {engine['avg_confidence']}")
            print(f"  Average Processing Time: {engine['avg_processing_time']}s")
            print(f"  Error Breakdown: {engine['error_breakdown']}")
        
        print(f"\nSIH-26127 Compliance:")
        print(f"  Target: 90% exact-match accuracy")
        print(f"  Best Achieved: {report['sih_compliance']['best_achieved_accuracy']*100:.2f}%")
        print(f"  Status: {report['sih_compliance']['compliance_status']}")
        
        print(f"\nBest Engine: {report['comparison']['best_engine']['name']}")
        print(f"\nDetailed report saved to: {output_path}")
        
        if report['sih_compliance']['compliance_status'] == 'NOT_MET':
            print("\n[WARNING] SIH requirement NOT MET - 90% accuracy target not achieved")
            print("   This is an honest report of actual measured performance.")
    else:
        print("No OCR engines were available for benchmarking")

if __name__ == "__main__":
    main()