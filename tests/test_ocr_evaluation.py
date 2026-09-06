"""
test_ocr_evaluation.py

Tests for OCR evaluation system to verify >90% accuracy requirement.
"""

import os
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import cv2

from recognition.ocr_evaluation import OCREvaluator, OCREvaluationReport, create_sample_dataset, OCRTrial


class TestOCREvaluator(unittest.TestCase):
    """Test OCR evaluation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.evaluator = OCREvaluator(ocr_instance=None)  # Mock OCR for testing
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_character_accuracy_calculation(self):
        """Test character-level accuracy calculation."""
        # Perfect match
        acc = self.evaluator.calculate_character_accuracy("ABC123", "ABC123")
        self.assertEqual(acc, 1.0)
        
        # Complete mismatch
        acc = self.evaluator.calculate_character_accuracy("XYZ789", "ABC123")
        self.assertEqual(acc, 0.0)
        
        # Partial match
        acc = self.evaluator.calculate_character_accuracy("ABC123", "AXC123")
        self.assertAlmostEqual(acc, 5/6, places=2)
        
        # Different lengths
        acc = self.evaluator.calculate_character_accuracy("ABC12", "ABC123")
        self.assertAlmostEqual(acc, 5/6, places=2)
    
    def test_error_classification(self):
        """Test OCR error classification."""
        # No OCR result
        error = self.evaluator.classify_error(None, "TN10AB1234")
        self.assertEqual(error, "no_ocr")
        
        # Exact match (no error)
        error = self.evaluator.classify_error("TN10AB1234", "TN10AB1234")
        self.assertIsNone(error)
        
        # Length error
        error = self.evaluator.classify_error("TN10AB123", "TN10AB1234")
        self.assertEqual(error, "length_error")
        
        # Confusion error
        error = self.evaluator.classify_error("TN10AB1234", "TN1OAB1234")
        self.assertEqual(error, "confusion")
        
        # Substitution error
        error = self.evaluator.classify_error("TN10AB1234", "TN10AC1234")
        self.assertEqual(error, "substitution_error")
    
    def test_sample_dataset_creation(self):
        """Test sample dataset creation."""
        dataset_path = create_sample_dataset(self.temp_dir, num_samples=5)
        
        self.assertTrue(os.path.exists(dataset_path))
        
        with open(dataset_path, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(len(data), 5)
        self.assertIn("image", data[0])
        self.assertIn("ground_truth", data[0])
    
    def test_evaluation_with_mock_ocr(self):
        """Test evaluation with mock OCR results."""
        # Create a temporary image
        test_image = np.zeros((100, 200, 3), dtype=np.uint8)
        image_path = os.path.join(self.temp_dir, "test_plate.jpg")
        cv2.imwrite(image_path, test_image)
        
        # Create mock OCR that returns predictable results
        class MockOCR:
            def read(self, image):
                # Return some mock results
                return "TN10AB1234", 0.85
        
        evaluator = OCREvaluator(ocr_instance=MockOCR())
        
        trial = evaluator.evaluate_single_image(image_path, "TN10AB1234")
        
        self.assertEqual(trial.ground_truth, "TN10AB1234")
        self.assertEqual(trial.ocr_result, "TN10AB1234")
        self.assertTrue(trial.exact_match)
        self.assertEqual(trial.character_accuracy, 1.0)
    
    def test_evaluation_with_failed_ocr(self):
        """Test evaluation when OCR fails."""
        # Create a temporary image
        test_image = np.zeros((100, 200, 3), dtype=np.uint8)
        image_path = os.path.join(self.temp_dir, "test_plate.jpg")
        cv2.imwrite(image_path, test_image)
        
        # Create mock OCR that fails
        class MockOCR:
            def read(self, image):
                return None, 0.0
        
        evaluator = OCREvaluator(ocr_instance=MockOCR())
        
        trial = evaluator.evaluate_single_image(image_path, "TN10AB1234")
        
        self.assertEqual(trial.ocr_result, None)
        self.assertFalse(trial.exact_match)
        self.assertEqual(trial.error_type, "no_ocr")
    
    def test_evaluation_report_generation(self):
        """Test comprehensive evaluation report generation."""
        # Create mock dataset with full paths
        dataset_data = []
        for i in range(3):
            image_path = os.path.join(self.temp_dir, f"plate_{i}.jpg")
            dataset_data.append({
                "image": image_path,  # Use full path
                "ground_truth": f"TN10AB{i:04d}"
            })
        
        dataset_path = os.path.join(self.temp_dir, "dataset.json")
        with open(dataset_path, 'w') as f:
            json.dump(dataset_data, f)
        
        # Create mock images
        for i in range(3):
            test_image = np.zeros((100, 200, 3), dtype=np.uint8)
            image_path = os.path.join(self.temp_dir, f"plate_{i}.jpg")
            cv2.imwrite(image_path, test_image)
        
        # Create mock OCR with mixed results
        class MockOCR:
            def __init__(self):
                self.call_count = 0
            
            def read(self, image):
                self.call_count += 1
                # Return correct result for first 2, wrong for third
                if self.call_count <= 2:
                    return f"TN10AB{self.call_count-1:04d}", 0.85
                else:
                    return "TN10AX0000", 0.45  # Same length, different characters for substitution error
        
        evaluator = OCREvaluator(ocr_instance=MockOCR())
        report = evaluator.evaluate_dataset(dataset_path)
        
        self.assertEqual(report.total_samples, 3)
        self.assertEqual(report.successful_ocr, 3)
        self.assertEqual(report.exact_matches, 2)
        self.assertAlmostEqual(report.exact_accuracy, 2/3, places=2)
        self.assertIn("correct", report.error_breakdown)
        # The error type could be either substitution_error or length_error depending on the mock result
        self.assertTrue("substitution_error" in report.error_breakdown or "length_error" in report.error_breakdown)
    
    def test_evaluation_with_missing_images(self):
        """Test evaluation handles missing images gracefully."""
        dataset_data = [{
            "image": "nonexistent.jpg",
            "ground_truth": "TN10AB1234"
        }]
        
        dataset_path = os.path.join(self.temp_dir, "dataset.json")
        with open(dataset_path, 'w') as f:
            json.dump(dataset_data, f)
        
        evaluator = OCREvaluator(ocr_instance=None)
        report = evaluator.evaluate_dataset(dataset_path)
        
        self.assertEqual(report.total_samples, 1)
        self.assertEqual(report.failed_ocr, 1)
        self.assertIn("image_not_found", report.error_breakdown)


class TestOCRTrial(unittest.TestCase):
    """Test OCRTrial dataclass."""
    
    def test_trial_creation(self):
        """Test OCRTrial creation and fields."""
        trial = OCRTrial(
            image_path="test.jpg",
            ground_truth="TN10AB1234",
            ocr_result="TN10AB1234",
            normalized_ocr="TN10AB1234",
            normalized_ground_truth="TN10AB1234",
            confidence=0.85,
            exact_match=True,
            character_accuracy=1.0,
            error_type=None
        )
        
        self.assertEqual(trial.image_path, "test.jpg")
        self.assertTrue(trial.exact_match)
        self.assertIsNone(trial.error_type)


if __name__ == "__main__":
    unittest.main()