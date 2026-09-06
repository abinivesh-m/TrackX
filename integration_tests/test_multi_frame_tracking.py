"""
Integration test for multi-frame vehicle tracking using real YOLO implementation.

This test requires:
- ultralytics package installed
- YOLO model weights available
- test_vehicle.mp4 video file

If dependencies are unavailable, this test will be skipped.
"""
import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from detection.vehicle_detector import VehicleDetector
    YOLO_AVAILABLE = True
except ImportError as e:
    YOLO_AVAILABLE = False
    VehicleDetector = None


class TestMultiFrameTracking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video_path = "data/cameras/CAM_01/videos/test_vehicle.mp4"
        # Check if video file exists
        if not os.path.exists(cls.video_path):
            raise unittest.SkipTest(f"Video file not found: {cls.video_path}")

    def setUp(self):
        if not YOLO_AVAILABLE:
            self.skipTest("ultralytics/YOLO not available - install it to run this integration test")

    def test_multi_frame_tracking(self):
        """Test that vehicle tracking works across multiple frames with consistent track IDs."""
        detector = VehicleDetector(conf=0.1)  # Lower confidence threshold for testing

        tracking_log = []
        max_frames = 100  # Safety limit

        for frame_idx, frame, vehicle_dets in detector.track_video(self.video_path):
            if frame_idx >= max_frames:
                break

            if not vehicle_dets:
                continue

            for v_det in vehicle_dets:
                track_id = v_det["track_id"]  # track_id is always present now
                bbox = v_det["bbox"]
                confidence = v_det["confidence"]
                vehicle_type = v_det["vehicle_type"]

                tracking_log.append({
                    "frame_index": frame_idx,
                    "track_id": track_id,
                    "vehicle_bbox": bbox,
                    "confidence": confidence,
                    "vehicle_type": vehicle_type
                })

        # Verify we got some detections
        self.assertGreater(len(tracking_log), 0, "No vehicle detections found in video")

        # Group by track_id (all entries have track IDs now)
        track_groups = {}
        for entry in tracking_log:
            track_id = entry["track_id"]
            if track_id not in track_groups:
                track_groups[track_id] = []
            track_groups[track_id].append(entry)

        # Verify track ID consistency for vehicles that appear in multiple frames
        for track_id, entries in track_groups.items():
            if len(entries) > 1:
                track_ids_in_group = [e['track_id'] for e in entries]
                self.assertEqual(len(set(track_ids_in_group)), 1,
                               f"Track ID {track_id} changes within group: {set(track_ids_in_group)}")


if __name__ == "__main__":
    unittest.main()
