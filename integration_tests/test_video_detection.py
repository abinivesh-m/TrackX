"""
Integration test for video detection using real YOLO implementation.

This test requires:
- ultralytics package installed
- YOLO model weights available
- test_vehicle.mp4 video file

If dependencies are unavailable, this test will be skipped.
"""
import unittest
import sys
import os
import cv2

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from detection.vehicle_detector import VehicleDetector
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    VehicleDetector = None


class TestVideoDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video_path = "data/cameras/CAM_01/videos/test_vehicle.mp4"
        # Check if video file exists
        if not os.path.exists(cls.video_path):
            raise unittest.SkipTest(f"Video file not found: {cls.video_path}")

    def setUp(self):
        if not YOLO_AVAILABLE:
            self.skipTest("ultralytics/YOLO not available - install it to run this integration test")

    def test_video_detection_on_first_frame(self):
        """Test that vehicle detection works on the first frame of a video."""
        det = VehicleDetector(conf=0.1)
        detections = det.detect(self.video_path)

        # Verify we got detections
        self.assertIsInstance(detections, list)

        # If we have detections, verify their structure
        for det_item in detections:
            self.assertIn("bbox", det_item)
            self.assertIn("confidence", det_item)
            self.assertIn("vehicle_type", det_item)

            # Verify bbox is [x1, y1, x2, y2]
            bbox = det_item["bbox"]
            self.assertEqual(len(bbox), 4)
            self.assertTrue(all(isinstance(coord, (int, float)) for coord in bbox))

            # Verify confidence is valid
            conf = det_item["confidence"]
            self.assertGreaterEqual(conf, 0.0)
            self.assertLessEqual(conf, 1.0)

            # Verify vehicle type is valid
            vehicle_type = det_item["vehicle_type"]
            self.assertIn(vehicle_type, ["car", "motorcycle", "bus", "truck"])

    def test_video_can_be_opened(self):
        """Test that the video file can be opened and read."""
        cap = cv2.VideoCapture(self.video_path)
        ret, frame = cap.read()

        self.assertTrue(ret, "Failed to read first frame from video")
        self.assertIsNotNone(frame, "Frame is None")
        self.assertGreater(frame.shape[0], 0, "Frame height is 0")
        self.assertGreater(frame.shape[1], 0, "Frame width is 0")

        cap.release()


if __name__ == "__main__":
    unittest.main()
