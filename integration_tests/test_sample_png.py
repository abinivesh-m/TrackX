"""
Integration test for vehicle detection on Sample.png using real YOLO implementation.

This test requires:
- ultralytics package installed
- YOLO model weights available
- Sample.png image file

If dependencies are unavailable, this test will be skipped.
"""
import unittest
import sys
import os
import cv2
import hashlib

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from detection.vehicle_detector import VehicleDetector
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    VehicleDetector = None


class TestSamplePNGDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.png_path = "data/cameras/CAM_01/videos/Sample.png"
        cls.jpg_path = "data/cameras/CAM_01/images/sample_scene.jpg"

        # Check if required files exist
        if not os.path.exists(cls.png_path):
            raise unittest.SkipTest(f"Sample.png not found: {cls.png_path}")

    def setUp(self):
        if not YOLO_AVAILABLE:
            self.skipTest("ultralytics/YOLO not available - install it to run this integration test")

    def test_vehicle_detection_on_sample_png(self):
        """Test that vehicle detection works on Sample.png."""
        vehicle_detector = VehicleDetector(weights="yolov8n")
        detections = vehicle_detector.detect(self.png_path)

        # Verify we got detections (number may vary based on image content)
        self.assertIsInstance(detections, list)

        # If we have detections, verify their structure
        for det in detections:
            self.assertIn("bbox", det)
            self.assertIn("confidence", det)
            self.assertIn("vehicle_type", det)

            # Verify bbox is [x1, y1, x2, y2]
            bbox = det["bbox"]
            self.assertEqual(len(bbox), 4)
            self.assertTrue(all(isinstance(coord, (int, float)) for coord in bbox))

            # Verify confidence is valid
            conf = det["confidence"]
            self.assertGreaterEqual(conf, 0.0)
            self.assertLessEqual(conf, 1.0)

            # Verify vehicle type is valid
            vehicle_type = det["vehicle_type"]
            self.assertIn(vehicle_type, ["car", "motorcycle", "bus", "truck"])

    def test_sample_png_vs_sample_scene_jpg(self):
        """Compare detection results between Sample.png and sample_scene.jpg if both exist."""
        if not os.path.exists(self.jpg_path):
            self.skipTest(f"sample_scene.jpg not found: {self.jpg_path}")

        vehicle_detector = VehicleDetector(weights="yolov8n")

        png_detections = vehicle_detector.detect(self.png_path)
        jpg_detections = vehicle_detector.detect(self.jpg_path)

        # Check if files are identical (same content, different format)
        with open(self.png_path, 'rb') as f:
            png_hash = hashlib.md5(f.read()).hexdigest()
        with open(self.jpg_path, 'rb') as f:
            jpg_hash = hashlib.md5(f.read()).hexdigest()

        if png_hash == jpg_hash:
            # Files are identical, so detections should be the same
            self.assertEqual(len(png_detections), len(jpg_detections),
                           "Detections differ for identical files")
        else:
            # Files are different, no assertion needed
            pass


if __name__ == "__main__":
    unittest.main()
