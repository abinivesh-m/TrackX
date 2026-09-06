"""
Test edge cases for the TrackX pipeline

These tests verify edge case handling without requiring real YOLO/PaddleOCR.
"""
import sys
import os
import numpy as np
import tempfile
import shutil
import unittest
import types

# Add stub imports for ultralytics/paddleocr
if "ultralytics" not in sys.modules:
    fake_ultralytics = types.ModuleType("ultralytics")
    class _FakeYOLO:
        def __init__(self, *a, **kw): pass
    fake_ultralytics.YOLO = _FakeYOLO
    sys.modules["ultralytics"] = fake_ultralytics

if "paddleocr" not in sys.modules:
    fake_paddleocr = types.ModuleType("paddleocr")
    class _FakePaddleOCR:
        def __init__(self, *a, **kw): pass
    fake_paddleocr.PaddleOCR = _FakePaddleOCR
    sys.modules["paddleocr"] = fake_paddleocr

# Store references to our stubs for cleanup
_STUB_MODULES = ["ultralytics", "paddleocr"]

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from demo import visual_pipeline as vp


# Module-level cleanup to prevent pollution
def cleanup_stub_modules():
    """Clean up stub modules from sys.modules to prevent pollution across test runs."""
    for module_name in _STUB_MODULES:
        if module_name in sys.modules:
            del sys.modules[module_name]

# Register cleanup to run at module unload (when pytest/unittest finishes this module)
import atexit
atexit.register(cleanup_stub_modules)


class TestEdgeCases(unittest.TestCase):
    """Test edge case handling in the TrackX pipeline."""

    def test_no_vehicle_detection(self):
        """Test that no vehicle detection is handled correctly."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        # Create a stub detector that returns no detections
        class NoVehicleDetector:
            def detect(self, image_path):
                return []
            def track_video(self, video_path):
                yield 0, frame, []

        detector = NoVehicleDetector()
        dets = detector.detect("dummy.jpg")
        self.assertEqual(len(dets), 0)

    def test_vehicle_but_no_plate(self):
        """Test that vehicle detected but no plate found is handled correctly."""
        vehicle_crop = np.zeros((100, 100, 3), dtype=np.uint8)
        original_frame = np.zeros((200, 200, 3), dtype=np.uint8)

        class NoPlateDetector:
            def detect_on_array(self, array):
                return []  # No plates detected

        fields = vp.build_plate_fields(
            vehicle_crop, NoPlateDetector(), None,
            vehicle_bbox=[10, 10, 60, 60],
            camera_id="CAM_01",
            frame_index=0,
            source_file="test.jpg",
            original_frame=original_frame,
            track_id=1
        )

        self.assertEqual(fields.get('plate_status'), 'plate_not_detected')
        self.assertIsNone(fields.get('plate_bbox'))
        self.assertIsNone(fields.get('raw_plate_text'))

    def test_plate_but_ocr_unavailable(self):
        """Test that plate detected but OCR unavailable is handled correctly."""
        vehicle_crop = np.zeros((100, 100, 3), dtype=np.uint8)
        original_frame = np.zeros((200, 200, 3), dtype=np.uint8)

        class HasPlateDetector:
            def detect_on_array(self, array):
                return [{"bbox": [10, 10, 40, 20], "confidence": 0.9}]
            @staticmethod
            def crop_array(image_array, bbox):
                x1, y1, x2, y2 = bbox
                h, w = image_array.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                return image_array[y1:y2, x1:x2]

        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "outputs/results/plate_crops"), exist_ok=True)
        old_cwd = os.getcwd()
        os.chdir(tmp)

        try:
            fields = vp.build_plate_fields(
                vehicle_crop, HasPlateDetector(), None,  # OCR = None
                vehicle_bbox=[10, 10, 60, 60],
                camera_id="CAM_01",
                frame_index=0,
                source_file="test.jpg",
                original_frame=original_frame,
                track_id=1
            )

            self.assertEqual(fields.get('plate_status'), 'detected_no_ocr')
            self.assertIsNotNone(fields.get('plate_bbox'))
            self.assertIsNone(fields.get('raw_plate_text'))
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_ocr_failure_empty_text(self):
        """Test that OCR returning empty text is handled correctly."""
        vehicle_crop = np.zeros((100, 100, 3), dtype=np.uint8)
        original_frame = np.zeros((200, 200, 3), dtype=np.uint8)

        class HasPlateDetector:
            def detect_on_array(self, array):
                return [{"bbox": [10, 10, 40, 20], "confidence": 0.9}]
            @staticmethod
            def crop_array(image_array, bbox):
                x1, y1, x2, y2 = bbox
                h, w = image_array.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                return image_array[y1:y2, x1:x2]

        class FailingOCR:
            def read(self, crop):
                return "", 0.0  # Returns empty text

        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "outputs/results/plate_crops"), exist_ok=True)
        old_cwd = os.getcwd()
        os.chdir(tmp)

        try:
            fields = vp.build_plate_fields(
                vehicle_crop, HasPlateDetector(), FailingOCR(),
                vehicle_bbox=[10, 10, 60, 60],
                camera_id="CAM_01",
                frame_index=0,
                source_file="test.jpg",
                original_frame=original_frame,
                track_id=1
            )

            self.assertEqual(fields.get('plate_status'), 'ocr_failed')
            self.assertIsNotNone(fields.get('plate_bbox'))
            self.assertIsNone(fields.get('raw_plate_text'))
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_tracker_unavailable_no_track_id(self):
        """Test that missing track_id is handled correctly."""
        class StubVehicleDetector:
            @staticmethod
            def crop(frame, bbox):
                x1, y1, x2, y2 = bbox
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                return frame[y1:y2, x1:x2]

        obs = vp._vehicle_observation(
            v_det={"bbox": [10, 10, 60, 60], "confidence": 0.9, "vehicle_type": "car"},  # No track_id
            frame=np.zeros((100, 100, 3), dtype=np.uint8),
            camera_id="CAM_01", source_file="test.jpg", source_type="image", frame_index=None,
            vehicle_detector=StubVehicleDetector(), plate_detector=None,
            ocr=None, timestamp="2026-01-01T00:00:00",
        )

        self.assertIsNone(obs.get('track_id'))
        self.assertEqual(obs.get('vehicle_class'), 'car')

    def test_low_confidence_detection(self):
        """Test that low confidence detection is handled correctly."""
        class StubVehicleDetector:
            @staticmethod
            def crop(frame, bbox):
                x1, y1, x2, y2 = bbox
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                return frame[y1:y2, x1:x2]

        obs = vp._vehicle_observation(
            v_det={"bbox": [10, 10, 60, 60], "confidence": 0.05, "vehicle_type": "car", "track_id": 1},
            frame=np.zeros((100, 100, 3), dtype=np.uint8),
            camera_id="CAM_01", source_file="test.jpg", source_type="image", frame_index=None,
            vehicle_detector=StubVehicleDetector(), plate_detector=None,
            ocr=None, timestamp="2026-01-01T00:00:00",
        )

        self.assertEqual(obs.get('vehicle_confidence'), 0.05)
        self.assertEqual(obs.get('track_id'), 1)


if __name__ == "__main__":
    unittest.main()
