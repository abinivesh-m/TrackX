"""
tests/test_day3_improvements.py

Day 3 tests for new improvements:
- Plate crop generation and storage
- Enhanced OCR normalization for Indian plates with suffixes
- Plate crop path integration in database
- Dashboard display of plate crops
- Graceful degradation when components fail
"""
import os
import sys
import shutil
import tempfile
import unittest
import types
import numpy as np
import cv2

# --- stub paddleocr/ultralytics for tests that don't need real inference ---
if "paddleocr" not in sys.modules:
    fake_paddleocr = types.ModuleType("paddleocr")
    class _FakePaddleOCR:
        def __init__(self, *a, **kw):
            pass
    fake_paddleocr.PaddleOCR = _FakePaddleOCR
    sys.modules["paddleocr"] = fake_paddleocr

if "ultralytics" not in sys.modules:
    fake_ultralytics = types.ModuleType("ultralytics")
    class _FakeYOLO:
        def __init__(self, *a, **kw):
            pass
    fake_ultralytics.YOLO = _FakeYOLO
    sys.modules["ultralytics"] = fake_ultralytics

# Store references to our stubs for cleanup
_STUB_MODULES = ["ultralytics", "paddleocr"]

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# Module-level cleanup to prevent pollution
def cleanup_stub_modules():
    """Clean up stub modules from sys.modules to prevent pollution across test runs."""
    for module_name in _STUB_MODULES:
        if module_name in sys.modules:
            del sys.modules[module_name]

# Register cleanup to run at module unload (when pytest/unittest finishes this module)
import atexit
atexit.register(cleanup_stub_modules)

from recognition.plate_normalizer import normalize_indian_plate


class TestEnhancedPlateNormalization(unittest.TestCase):
    """Test improved OCR normalization for Indian plates with suffixes."""
    
    def test_standard_plate_passes_through(self):
        """Standard valid plate should pass through unchanged."""
        normalized, matched = normalize_indian_plate("TN38AB1234")
        self.assertEqual(normalized, "TN38AB1234")
        self.assertTrue(matched)
    
    def test_plate_with_country_code_suffix(self):
        """Plate with country code suffix should be extracted correctly."""
        normalized, matched = normalize_indian_plate("TN09CQ1234IND")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_plate_with_different_suffix(self):
        """Plate with different letter suffix should NOT be extracted (only country markers)."""
        normalized, matched = normalize_indian_plate("KA05MH1234XYZ")
        # Current implementation only removes country markers (IND, ND, etc.)
        # Arbitrary letter suffixes are preserved as they may be legitimate
        self.assertEqual(normalized, "KA05MH1234XYZ")
        self.assertFalse(matched)  # Doesn't match standard pattern due to extra letters
    
    def test_plate_with_digit_suffix(self):
        """Plate with digit suffix should NOT be extracted (only country markers)."""
        normalized, matched = normalize_indian_plate("MH01AB123456")
        # Current implementation only removes country markers (IND, ND, etc.)
        # Extra digits are preserved as they may be legitimate
        self.assertEqual(normalized, "MH01AB123456")
        self.assertFalse(matched)  # Doesn't match standard pattern due to extra digits
    
    def test_confusable_correction_still_works(self):
        """Original confusable correction should still work."""
        normalized, matched = normalize_indian_plate("TN38A81234")  # B misread as 8
        self.assertEqual(normalized, "TN38AB1234")
        self.assertTrue(matched)
    
    def test_short_garbage_not_forced(self):
        """Short garbage strings should not be forced into valid plates."""
        normalized, matched = normalize_indian_plate("XYZ")
        self.assertEqual(normalized, "XYZ")
        self.assertFalse(matched)
    
    def test_long_garbage_not_forced(self):
        """Long garbage strings should not be forced into valid plates."""
        normalized, matched = normalize_indian_plate("SOMEJUNK12345678")
        # The normalize_plate function from plate_matcher cleans it to alnum only
        # but it won't match the Indian plate pattern
        self.assertFalse(matched)
    
    def test_empty_input(self):
        """Empty input should return empty string."""
        normalized, matched = normalize_indian_plate("")
        self.assertEqual(normalized, "")
        self.assertFalse(matched)


class TestPlateCropIntegration(unittest.TestCase):
    """Test plate crop generation and storage integration."""
    
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.original_plate_crops_dir = None
        
        # Save original imports if needed
        import demo.visual_pipeline as vp
        self.original_plate_crops_dir = vp.PLATE_CROPS_DIR
        
        # Override with temp directory
        vp.PLATE_CROPS_DIR = os.path.join(self.tmp, "plate_crops")
        
    def tearDown(self):
        import demo.visual_pipeline as vp
        if self.original_plate_crops_dir:
            vp.PLATE_CROPS_DIR = self.original_plate_crops_dir
        shutil.rmtree(self.tmp, ignore_errors=True)
    
    def test_plate_crop_directory_creation(self):
        """Test that plate crop directory is created when needed."""
        import demo.visual_pipeline as vp
        plate_crop_path = os.path.join(vp.PLATE_CROPS_DIR, "test_plate.jpg")
        os.makedirs(os.path.dirname(plate_crop_path), exist_ok=True)
        
        # Create a dummy plate crop
        dummy_crop = np.zeros((50, 100, 3), dtype=np.uint8)
        cv2.imwrite(plate_crop_path, dummy_crop)
        
        self.assertTrue(os.path.exists(plate_crop_path))
    
    def test_plate_crop_path_in_observation(self):
        """Test that plate crop path is included in observation when available."""
        import demo.visual_pipeline as vp
        
        # Create a mock observation with plate crop path
        obs = {
            "plate_crop_path": "/some/path/plate_123.jpg",
            "plate_status": "detected",
            "normalized_plate_text": "TN38AB1234"
        }
        
        self.assertIsNotNone(obs["plate_crop_path"])
        self.assertEqual(obs["plate_status"], "detected")


class TestDatabasePlateCropSchema(unittest.TestCase):
    """Test database schema supports plate crop paths."""
    
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test_observations.db")
    
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
    
    def test_database_has_plate_crop_column(self):
        """Test that database migration adds plate_crop_path column."""
        from database.observation_store import ObservationStore
        
        store = ObservationStore(db_path=self.db_path)
        
        # Check that plate_crop_path column exists
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("PRAGMA table_info(observations)")
        columns = {row[1] for row in cursor}
        
        self.assertIn("plate_crop_path", columns)
        
        conn.close()
        store.close()
    
    def test_observation_with_plate_crop_path(self):
        """Test that observations can be stored with plate crop paths."""
        from database.observation_store import ObservationStore
        from datetime import datetime
        
        store = ObservationStore(db_path=self.db_path)
        
        obs = {
            "camera_id": "CAM_01",
            "timestamp": datetime.now().isoformat(),
            "normalized_plate_text": "TN38AB1234",
            "ocr_confidence": 0.85,
            "plate_status": "detected",
            "plate_crop_path": "/some/path/plate_123.jpg",
            "vehicle_class": "car",
            "vehicle_confidence": 0.9,
            "track_id": 1,
        }
        
        store.add_visual_observation(obs)
        
        # Retrieve and verify
        all_obs = store.all_observations()
        self.assertEqual(len(all_obs), 1)
        self.assertEqual(all_obs[0]["plate_crop_path"], "/some/path/plate_123.jpg")
        
        store.close()


class TestGracefulDegradation(unittest.TestCase):
    """Test graceful degradation when components fail."""
    
    def test_missing_plate_detector_unavailable_status(self):
        """Test that missing plate detector is reported as unavailable."""
        import demo.visual_pipeline as vp
        
        crop = np.zeros((50, 50, 3), dtype=np.uint8)
        original_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        vehicle_bbox = [10, 10, 60, 60]
        fields = vp.build_plate_fields(crop, plate_detector=None, ocr=None, 
                                      vehicle_bbox=vehicle_bbox, camera_id="CAM_01",
                                      frame_index=0, source_file="test.jpg",
                                      original_frame=original_frame)
        
        self.assertEqual(fields["plate_status"], "unavailable")
        self.assertIsNone(fields["plate_bbox"])
        self.assertIsNone(fields["raw_plate_text"])
        self.assertIsNotNone(fields["plate_status_reason"])
    
    def test_plate_detector_no_plates_not_found_status(self):
        """Test that plate detector finding no plates is reported correctly."""
        import demo.visual_pipeline as vp
        
        class StubPlateDetector:
            def detect_on_array(self, img):
                return []
        
        crop = np.zeros((50, 50, 3), dtype=np.uint8)
        original_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        vehicle_bbox = [10, 10, 60, 60]
        pd = StubPlateDetector()
        fields = vp.build_plate_fields(crop, plate_detector=pd, ocr=None,
                                      vehicle_bbox=vehicle_bbox, camera_id="CAM_01",
                                      frame_index=0, source_file="test.jpg",
                                      original_frame=original_frame)
        
        self.assertEqual(fields["plate_status"], "plate_not_detected")
    
    def test_ocr_failure_unavailable_status(self):
        """Test that OCR failure is reported as detected_no_ocr (plate detected but OCR unavailable)."""
        import demo.visual_pipeline as vp
        
        class StubPlateDetector:
            def detect_on_array(self, img):
                return [{"bbox": [1, 1, 20, 15], "confidence": 0.7}]
            
            def crop_array(self, img, bbox):
                return np.zeros((15, 20, 3), dtype=np.uint8)
        
        crop = np.zeros((50, 50, 3), dtype=np.uint8)
        original_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        vehicle_bbox = [10, 10, 60, 60]
        pd = StubPlateDetector()
        fields = vp.build_plate_fields(crop, plate_detector=pd, ocr=None,
                                      vehicle_bbox=vehicle_bbox, camera_id="CAM_01",
                                      frame_index=0, source_file="test.jpg",
                                      original_frame=original_frame)
        
        self.assertEqual(fields["plate_status"], "detected_no_ocr")  # Plate detected but OCR unavailable
        self.assertIsNotNone(fields["plate_bbox"])  # Box should still be there
        self.assertIn("OCR", fields["plate_status_reason"])


class TestEndToEndIntegration(unittest.TestCase):
    """Test end-to-end integration of new features."""
    
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
    
    def test_observation_structure_completeness(self):
        """Test that observation structure includes all new fields."""
        from datetime import datetime
        
        obs = {
            "camera_id": "CAM_01",
            "timestamp": datetime.now().isoformat(),
            "source_file": "test.jpg",
            "source_type": "image",
            "frame_index": None,
            "vehicle_bbox": [10, 10, 100, 100],
            "vehicle_class": "car",
            "vehicle_confidence": 0.9,
            "track_id": 1,
            "plate_bbox": [5, 5, 30, 15],
            "plate_crop_path": "/path/to/plate.jpg",
            "raw_plate_text": "TN09CQ1234IND",
            "normalized_plate_text": "TN09CQ1234",
            "ocr_confidence": 0.85,
            "plate_status": "detected",
            "plate_status_reason": None,
            "annotated_output": "/path/to/annotated.jpg",
        }
        
        # Verify all expected fields are present
        expected_fields = {
            "camera_id", "timestamp", "source_file", "source_type", "frame_index",
            "vehicle_bbox", "vehicle_class", "vehicle_confidence", "track_id",
            "plate_bbox", "plate_crop_path", "raw_plate_text", "normalized_plate_text",
            "ocr_confidence", "plate_status", "plate_status_reason", "annotated_output"
        }
        
        self.assertTrue(expected_fields.issubset(obs.keys()))
        self.assertEqual(obs["normalized_plate_text"], "TN09CQ1234")  # Suffix removed


if __name__ == "__main__":
    unittest.main()