"""
Integration test for real OCR using actual PaddleOCR implementation.

This test requires:
- paddleocr package installed
- PaddleOCR model weights available (may require network access for first download)
- A plate crop image file

If dependencies are unavailable or PaddleOCR cannot initialize, this test will be skipped.
"""
import unittest
import sys
import os
import cv2
import glob
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    PaddleOCR = None


class TestRealOCR(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Dynamically discover the newest valid CAM_01 plate crop
        plate_crops_dir = "outputs/results/plate_crops"
        if not os.path.isdir(plate_crops_dir):
            raise unittest.SkipTest(f"Plate crops directory not found: {plate_crops_dir}")
        
        # Find all CAM_01 plate crop files
        cam01_pattern = os.path.join(plate_crops_dir, "CAM_01_*.jpg")
        cam01_files = glob.glob(cam01_pattern)
        
        if not cam01_files:
            raise unittest.SkipTest(f"No CAM_01 plate crop files found in {plate_crops_dir}")
        
        # Sort by modification time to get the newest file
        cam01_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        cls.plate_crop_path = cam01_files[0]
        
        # Verify the file actually exists and is readable
        if not os.path.exists(cls.plate_crop_path):
            raise unittest.SkipTest(f"Discovered plate crop file does not exist: {cls.plate_crop_path}")

    def setUp(self):
        if not PADDLEOCR_AVAILABLE:
            self.skipTest("paddleocr not available - install it to run this integration test")

    def test_real_ocr_on_plate_crop(self):
        """Test that PaddleOCR can read text from an actual plate crop."""
        img = cv2.imread(self.plate_crop_path)
        self.assertIsNotNone(img, f"Failed to read plate crop: {self.plate_crop_path}")

        # Try to initialize PaddleOCR - this may fail if network is unavailable
        try:
            ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        except Exception as e:
            self.skipTest(f"PaddleOCR initialization failed (likely network/model issue): {e}")

        # Run OCR
        result = ocr.ocr(img, cls=True)

        # We don't assert specific results since OCR accuracy varies,
        # but we verify the API works and returns a valid structure
        self.assertIsNotNone(result, "OCR returned None")

        if result and result[0]:
            # If we got results, verify the structure
            for line in result[0]:
                text = line[1][0]
                conf = line[1][1]
                self.assertIsInstance(text, str)
                self.assertIsInstance(conf, (int, float))
                self.assertGreaterEqual(conf, 0.0)
                self.assertLessEqual(conf, 1.0)

                # Test normalization
                from recognition.plate_normalizer import normalize_indian_plate
                normalized, matched = normalize_indian_plate(text)
                self.assertIsInstance(normalized, str)
                self.assertIsInstance(matched, bool)
        else:
            # No text detected - this is acceptable for some images
            pass


if __name__ == "__main__":
    unittest.main()
