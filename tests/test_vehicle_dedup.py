"""
tests/test_vehicle_dedup.py

Regression test for the duplicate-detection bug found on
data/cameras/CAM_01/images/sample_scene.jpg: real YOLOv8n produced two
overlapping boxes for the same physical car - "car" 0.492 and "truck" 0.46,
IoU 0.963 - because Ultralytics' NMS is per-class, and this vehicle was
ambiguous between two of our tracked classes.

Pure logic test, no ultralytics/torch needed - deduplicate_vehicle_detections()
and _iou() operate on plain dicts/tuples.
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# detection/vehicle_detector.py does `from ultralytics import YOLO` at module
# import time. This file only exercises the pure dict/tuple logic
# (deduplicate_vehicle_detections, _iou) and never touches YOLO itself, but
# the import still has to succeed. Stub it here directly (same approach as
# tests/test_day1_visual_pipeline.py) so this file is a correct, independent
# test module and passes whether it's run alone or as part of a full
# discovery run - it previously only worked by accident, piggybacking on
# whatever test module happened to stub ultralytics first in the same
# process.
if "ultralytics" not in sys.modules:
    fake_ultralytics = types.ModuleType("ultralytics")

    class _FakeYOLO:
        def __init__(self, *a, **kw):
            pass

    fake_ultralytics.YOLO = _FakeYOLO
    sys.modules["ultralytics"] = fake_ultralytics

# Store references to our stubs for cleanup
_STUB_MODULES = ["ultralytics"]

from detection.vehicle_detector import deduplicate_vehicle_detections, _iou


# Module-level cleanup to prevent pollution
def cleanup_stub_modules():
    """Clean up stub modules from sys.modules to prevent pollution across test runs."""
    for module_name in _STUB_MODULES:
        if module_name in sys.modules:
            del sys.modules[module_name]

# Register cleanup to run at module unload (when pytest/unittest finishes this module)
import atexit
atexit.register(cleanup_stub_modules)


class TestIoU(unittest.TestCase):
    def test_identical_boxes(self):
        self.assertEqual(_iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)

    def test_no_overlap(self):
        self.assertEqual(_iou([0, 0, 10, 10], [20, 20, 30, 30]), 0.0)

    def test_partial_overlap(self):
        # two 10x10 boxes overlapping in a 5x10 region -> intersection 50,
        # union = 100+100-50 = 150 -> iou = 1/3
        iou = _iou([0, 0, 10, 10], [5, 0, 15, 10])
        self.assertAlmostEqual(iou, 1 / 3, places=4)

    def test_real_reported_case(self):
        # the actual boxes from the sample_scene.jpg double-detection
        car_box = [219, 129, 1228, 953]
        truck_box = [203, 132, 1243, 956]
        self.assertGreater(_iou(car_box, truck_box), 0.9)


class TestDeduplicateVehicleDetections(unittest.TestCase):
    def test_same_vehicle_different_classes_collapses_to_one(self):
        dets = [
            {"bbox": [219, 129, 1228, 953], "confidence": 0.492, "vehicle_type": "car"},
            {"bbox": [203, 132, 1243, 956], "confidence": 0.46, "vehicle_type": "truck"},
        ]
        result = deduplicate_vehicle_detections(dets)
        self.assertEqual(len(result), 1)
        # higher-confidence detection wins
        self.assertEqual(result[0]["vehicle_type"], "car")
        self.assertEqual(result[0]["confidence"], 0.492)

    def test_two_genuinely_separate_vehicles_both_kept(self):
        dets = [
            {"bbox": [0, 0, 100, 100], "confidence": 0.9, "vehicle_type": "car"},
            {"bbox": [500, 500, 600, 600], "confidence": 0.8, "vehicle_type": "truck"},
        ]
        result = deduplicate_vehicle_detections(dets)
        self.assertEqual(len(result), 2)

    def test_empty_input(self):
        self.assertEqual(deduplicate_vehicle_detections([]), [])

    def test_single_detection_passthrough(self):
        dets = [{"bbox": [0, 0, 10, 10], "confidence": 0.5, "vehicle_type": "bus"}]
        self.assertEqual(deduplicate_vehicle_detections(dets), dets)

    def test_three_way_overlap_keeps_only_highest_confidence(self):
        dets = [
            {"bbox": [10, 10, 110, 110], "confidence": 0.7, "vehicle_type": "car"},
            {"bbox": [12, 12, 112, 112], "confidence": 0.9, "vehicle_type": "truck"},
            {"bbox": [8, 8, 108, 108], "confidence": 0.6, "vehicle_type": "bus"},
        ]
        result = deduplicate_vehicle_detections(dets)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], 0.9)

    def test_below_threshold_overlap_keeps_both(self):
        # boxes overlapping only slightly (below DUPLICATE_IOU_THRESHOLD)
        # are plausibly two different adjacent vehicles, not a duplicate
        dets = [
            {"bbox": [0, 0, 100, 100], "confidence": 0.9, "vehicle_type": "car"},
            {"bbox": [90, 0, 190, 100], "confidence": 0.8, "vehicle_type": "car"},
        ]
        result = deduplicate_vehicle_detections(dets, iou_threshold=0.6)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
