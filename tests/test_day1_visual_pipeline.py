"""
tests/test_day1_visual_pipeline.py

Day-1 structural/plumbing tests for the visual input layer.

WHAT THESE TESTS DO / DO NOT PROVE
-----------------------------------
- They verify the NEW Day-1 code: camera discovery + CameraFeed objects
  + frame sampling (demo/camera_simulator.py), conservative Indian plate
  normalization (recognition/plate_normalizer.py), annotation drawing
  (demo/annotate.py), and the observation-building / orchestration logic
  in demo/visual_pipeline.py (build_plate_fields, process_image,
  process_video, run_camera's helpers).
- They do NOT exercise real YOLO vehicle detection, real plate
  detection, or real PaddleOCR. `ultralytics` and `paddleocr` are not
  installed in this environment and there is no network access here to
  install them or download model weights. Both packages are stubbed
  into sys.modules below ONLY so that detection/vehicle_detector.py,
  detection/detect_plates.py and recognition/ocr_reader.py (which do
  `from ultralytics import YOLO` / `from paddleocr import PaddleOCR` at
  module import time) can be imported at all. No test below calls into
  those stubs as if they were real detectors - orchestration functions
  are exercised with hand-written stub detector/OCR objects instead,
  and stub results are never claimed to be real inference.
- Real-model verification (actual vehicle boxes, actual plate boxes,
  actual OCR reads on real footage) must happen separately, in an
  environment with ultralytics/paddleocr/paddlepaddle actually
  installed and real trained weights available.
"""
import os
import sys
import shutil
import tempfile
import types
import unittest

import numpy as np
import cv2

# --- stub ultralytics / paddleocr purely so module imports succeed ---
if "ultralytics" not in sys.modules:
    fake_ultralytics = types.ModuleType("ultralytics")

    class _FakeYOLO:
        def __init__(self, *a, **kw):
            pass

    fake_ultralytics.YOLO = _FakeYOLO
    sys.modules["ultralytics"] = fake_ultralytics

if "paddleocr" not in sys.modules:
    fake_paddleocr = types.ModuleType("paddleocr")

    class _FakePaddleOCR:
        def __init__(self, *a, **kw):
            pass

    fake_paddleocr.PaddleOCR = _FakePaddleOCR
    sys.modules["paddleocr"] = fake_paddleocr

# Store references to our stubs for cleanup
_STUB_MODULES = ["ultralytics", "paddleocr"]

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

from demo.camera_simulator import (  # noqa: E402
    list_camera_media, ensure_camera_dirs, get_camera_feed, sample_frame_indices,
    CameraFeedNotFound, CameraFeed,
)
from demo.annotate import annotate_frame  # noqa: E402
from recognition.plate_normalizer import normalize_indian_plate  # noqa: E402
from recognition import ocr_reader  # noqa: E402
from demo import visual_pipeline as vp  # noqa: E402


# ---------------------------------------------------------------------------
# OCR init resilience - the real PaddleOCR-CDN-unreachable bug
# ---------------------------------------------------------------------------
class TestTryInitOcr(unittest.TestCase):
    def test_returns_none_on_system_exit_instead_of_propagating(self):
        # SystemExit is what PaddleOCR's constructor actually raises when
        # its model CDN is unreachable - it is a BaseException, not an
        # Exception, so a naive `except Exception` would NOT catch it and
        # the process would die. try_init_ocr must catch it specifically.
        original = ocr_reader.PlateOCR
        try:
            def _boom(*a, **kw):
                raise SystemExit(1)
            ocr_reader.PlateOCR = _boom
            result = ocr_reader.try_init_ocr()
            self.assertIsNone(result)
        finally:
            ocr_reader.PlateOCR = original

    def test_returns_none_on_ordinary_exception(self):
        original = ocr_reader.PlateOCR
        try:
            def _boom(*a, **kw):
                raise RuntimeError("some other init failure")
            ocr_reader.PlateOCR = _boom
            result = ocr_reader.try_init_ocr()
            self.assertIsNone(result)
        finally:
            ocr_reader.PlateOCR = original

    def test_returns_instance_on_success(self):
        original = ocr_reader.PlateOCR
        try:
            # Create a proper stub with engine_type attribute
            class SentinelOCR:
                engine_type = "test_stub"
                def __init__(self, *a, **kw):
                    pass
            sentinel = SentinelOCR()
            ocr_reader.PlateOCR = SentinelOCR
            # Also set the availability flag to True
            ocr_reader.PADDLEOCR_AVAILABLE = True
            result = ocr_reader.try_init_ocr()
            self.assertIsInstance(result, SentinelOCR)
        finally:
            ocr_reader.PlateOCR = original
            ocr_reader.PADDLEOCR_AVAILABLE = False


# ---------------------------------------------------------------------------
# 1/2/3/12 - camera discovery, camera IDs, image/video discovery,
#            invalid + empty camera folder handling
# ---------------------------------------------------------------------------
class TestCameraDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_invalid_camera_raises(self):
        with self.assertRaises(CameraFeedNotFound):
            list_camera_media("CAM_99_DOES_NOT_EXIST", root=self.tmp)

    def test_discovers_images_and_videos(self):
        cam_dir = os.path.join(self.tmp, "CAM_01")
        os.makedirs(os.path.join(cam_dir, "images"))
        os.makedirs(os.path.join(cam_dir, "videos"))
        open(os.path.join(cam_dir, "images", "a.jpg"), "w").close()
        open(os.path.join(cam_dir, "images", "b.png"), "w").close()
        open(os.path.join(cam_dir, "images", "ignore.txt"), "w").close()  # unsupported ext
        open(os.path.join(cam_dir, "videos", "clip.mp4"), "w").close()

        images, videos = list_camera_media("CAM_01", root=self.tmp)
        self.assertEqual(len(images), 2)
        self.assertEqual(len(videos), 1)
        self.assertTrue(all(f.endswith((".jpg", ".png")) for f in images))

    def test_empty_camera_folder_returns_empty_not_error(self):
        # camera folder exists but images/ and videos/ subfolders don't
        os.makedirs(os.path.join(self.tmp, "CAM_02"))
        images, videos = list_camera_media("CAM_02", root=self.tmp)
        self.assertEqual(images, [])
        self.assertEqual(videos, [])

    def test_empty_subfolders_return_empty_lists(self):
        os.makedirs(os.path.join(self.tmp, "CAM_03", "images"))
        os.makedirs(os.path.join(self.tmp, "CAM_03", "videos"))
        images, videos = list_camera_media("CAM_03", root=self.tmp)
        self.assertEqual(images, [])
        self.assertEqual(videos, [])

    def test_ensure_camera_dirs_creates_standard_layout(self):
        ensure_camera_dirs(root=self.tmp)
        for cam in ("CAM_01", "CAM_02", "CAM_03", "CAM_04"):
            self.assertTrue(os.path.isdir(os.path.join(self.tmp, cam, "images")))
            self.assertTrue(os.path.isdir(os.path.join(self.tmp, cam, "videos")))

    def test_camera_feed_exposes_camera_id_and_media(self):
        cam_dir = os.path.join(self.tmp, "CAM_01")
        os.makedirs(os.path.join(cam_dir, "images"))
        open(os.path.join(cam_dir, "images", "a.jpg"), "w").close()

        feed = get_camera_feed("CAM_01", root=self.tmp)
        self.assertIsInstance(feed, CameraFeed)
        self.assertEqual(feed.camera_id, "CAM_01")
        self.assertEqual(len(feed.images), 1)
        self.assertEqual(feed.videos, [])
        self.assertTrue(feed.has_media)

    def test_camera_feed_no_media_flag(self):
        os.makedirs(os.path.join(self.tmp, "CAM_04"))
        feed = get_camera_feed("CAM_04", root=self.tmp)
        self.assertFalse(feed.has_media)


# ---------------------------------------------------------------------------
# frame sampling
# ---------------------------------------------------------------------------
class TestFrameSampling(unittest.TestCase):
    def test_every_nth_frame(self):
        should_process = sample_frame_indices(frame_sample=3)
        kept = [i for i in range(10) if should_process(i)]
        self.assertEqual(kept, [0, 3, 6, 9])

    def test_frame_sample_of_one_keeps_every_frame(self):
        should_process = sample_frame_indices(frame_sample=1)
        kept = [i for i in range(5) if should_process(i)]
        self.assertEqual(kept, [0, 1, 2, 3, 4])

    def test_max_frames_cap(self):
        should_process = sample_frame_indices(frame_sample=1, max_frames=3)
        kept = [i for i in range(10) if should_process(i)]
        self.assertEqual(kept, [0, 1, 2])

    def test_invalid_frame_sample_rejected(self):
        with self.assertRaises(ValueError):
            sample_frame_indices(frame_sample=0)


# ---------------------------------------------------------------------------
# Indian plate normalization
# ---------------------------------------------------------------------------
class TestIndianPlateNormalizer(unittest.TestCase):
    def test_already_valid_plate_passes_through(self):
        norm, matched = normalize_indian_plate("TN38AB1234")
        self.assertEqual(norm, "TN38AB1234")
        self.assertTrue(matched)

    def test_corrects_confusable_in_series_position(self):
        norm, matched = normalize_indian_plate("TN38A81234")  # B misread as 8
        self.assertEqual(norm, "TN38AB1234")
        self.assertTrue(matched)

    def test_does_not_force_correction_on_non_standard_length(self):
        norm, matched = normalize_indian_plate("XY12")
        self.assertEqual(norm, "XY12")
        self.assertFalse(matched)

    def test_strips_junk_characters(self):
        norm, matched = normalize_indian_plate("tn-38 ab*1234")
        self.assertEqual(norm, "TN38AB1234")
        self.assertTrue(matched)

    def test_empty_input(self):
        norm, matched = normalize_indian_plate("")
        self.assertEqual(norm, "")
        self.assertFalse(matched)

    def test_never_invents_a_plate_from_pure_garbage(self):
        # long non-plate-shaped junk should be returned cleaned but unmatched,
        # never coerced into looking like a valid plate
        norm, matched = normalize_indian_plate("###???!!!")
        self.assertEqual(norm, "")
        self.assertFalse(matched)


# ---------------------------------------------------------------------------
# annotation
# ---------------------------------------------------------------------------
class TestAnnotateFrame(unittest.TestCase):
    def test_draws_without_crashing_and_preserves_shape(self):
        frame = np.zeros((200, 300, 3), dtype=np.uint8)
        observations = [{
            "vehicle_bbox": [10, 10, 100, 100],
            "vehicle_class": "car",
            "vehicle_confidence": 0.91,
            "plate_bbox": [5, 5, 40, 20],
            "plate_status": "detected",
            "normalized_plate_text": "TN38AB1234",
            "ocr_confidence": 0.77,
        }]
        out = annotate_frame(frame, "CAM_01", observations)
        self.assertEqual(out.shape, frame.shape)
        self.assertTrue(np.array_equal(frame, np.zeros((200, 300, 3), dtype=np.uint8)))  # untouched original
        self.assertFalse(np.array_equal(out, frame))  # something was drawn

    def test_handles_unavailable_plate_status(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        observations = [{
            "vehicle_bbox": [0, 0, 50, 50], "vehicle_class": "truck", "vehicle_confidence": 0.6,
            "plate_bbox": None, "plate_status": "unavailable",
            "normalized_plate_text": None, "ocr_confidence": None,
        }]
        out = annotate_frame(frame, "CAM_02", observations)  # must not raise
        self.assertEqual(out.shape, frame.shape)

    def test_handles_not_found_plate_status(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        observations = [{
            "vehicle_bbox": [0, 0, 50, 50], "vehicle_class": "car", "vehicle_confidence": 0.8,
            "plate_bbox": None, "plate_status": "plate_not_detected",
            "normalized_plate_text": None, "ocr_confidence": None,
        }]
        out = annotate_frame(frame, "CAM_03", observations)
        self.assertEqual(out.shape, frame.shape)

    def test_handles_empty_observation_list(self):
        frame = np.zeros((80, 80, 3), dtype=np.uint8)
        out = annotate_frame(frame, "CAM_01", [])
        self.assertEqual(out.shape, frame.shape)


# ---------------------------------------------------------------------------
# stub detector/OCR objects - duck-type the real classes' interfaces,
# no ultralytics/paddleocr inference involved
# ---------------------------------------------------------------------------
class _StubVehicleDetector:
    def __init__(self, image_dets=None, video_frames=None):
        self._image_dets = image_dets or []
        self._video_frames = video_frames or []

    def detect(self, image_path):
        return self._image_dets

    def track_video(self, video_path):
        for item in self._video_frames:
            yield item

    @staticmethod
    def crop(frame, bbox):
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        return frame[y1:y2, x1:x2]


class _StubPlateDetector:
    def __init__(self, dets=None):
        self._dets = dets or []

    def detect_on_array(self, image_array):
        return self._dets

    @staticmethod
    def crop_array(image_array, bbox):
        x1, y1, x2, y2 = bbox
        h, w = image_array.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        return image_array[y1:y2, x1:x2]


class _StubOCR:
    def __init__(self, text="TN38AB1234", conf=0.85):
        self._text = text
        self._conf = conf

    def read(self, crop_img):
        return self._text, self._conf


# ---------------------------------------------------------------------------
# missing-model handling
# ---------------------------------------------------------------------------
class TestMissingModelHandling(unittest.TestCase):
    def test_no_plate_detector_reports_unavailable_not_fake_result(self):
        crop = np.zeros((50, 50, 3), dtype=np.uint8)
        original_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        fields = vp.build_plate_fields(crop, plate_detector=None, ocr=_StubOCR(),
                                     vehicle_bbox=[0, 0, 50, 50], camera_id="CAM_01",
                                     frame_index=0, source_file="test.jpg",
                                     original_frame=original_frame, track_id=None)
        self.assertEqual(fields["plate_status"], "unavailable")
        self.assertIsNone(fields["plate_bbox"])
        self.assertIsNone(fields["raw_plate_text"])
        self.assertIsNone(fields["normalized_plate_text"])
        self.assertIsNotNone(fields["plate_status_reason"])

    def test_plate_detector_finds_nothing(self):
        crop = np.zeros((50, 50, 3), dtype=np.uint8)
        original_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        pd = _StubPlateDetector(dets=[])
        fields = vp.build_plate_fields(crop, plate_detector=pd, ocr=_StubOCR(),
                                     vehicle_bbox=[0, 0, 50, 50], camera_id="CAM_01",
                                     frame_index=0, source_file="test.jpg",
                                     original_frame=original_frame, track_id=None)
        self.assertEqual(fields["plate_status"], "plate_not_detected")

    def test_find_plate_weights_uses_project_root_not_current_working_directory(self):
        # Path resolution is intentionally independent of the caller's cwd.
        # The project contains a real trained plate detector, so changing to a
        # random temp directory must not make the runtime lose that model.
        tmp = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            result = vp.find_plate_weights()
            self.assertTrue(result)
            self.assertTrue(os.path.isfile(result))
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_find_plate_weights_explicit_path_must_exist(self):
        tmp = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            self.assertIsNone(vp.find_plate_weights(explicit_path="does_not_exist.pt"))
            open("real.pt", "w").close()
            self.assertEqual(vp.find_plate_weights(explicit_path="real.pt"), "real.pt")
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_plate_detected_but_ocr_unavailable_degrades_not_crashes(self):
        # Regression test for the real bug: PaddleOCR's constructor can
        # sys.exit() (SystemExit) when it can't reach its model CDN, which
        # is not a normal Exception. recognition.ocr_reader.try_init_ocr()
        # catches that and returns None instead of letting it propagate.
        # build_plate_fields() must handle ocr=None (a plate WAS boxed, but
        # there's no engine to read it) as its own distinct "unavailable"
        # reason - never crash, and never silently claim "not_found" (which
        # would incorrectly imply there was no plate there at all).
        crop = np.zeros((50, 50, 3), dtype=np.uint8)
        original_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        pd = _StubPlateDetector(dets=[{"bbox": [1, 1, 20, 15], "confidence": 0.7}])
        fields = vp.build_plate_fields(crop, plate_detector=pd, ocr=None,
                                     vehicle_bbox=[0, 0, 50, 50], camera_id="CAM_01",
                                     frame_index=0, source_file="test.jpg",
                                     original_frame=original_frame, track_id=None)
        self.assertEqual(fields["plate_status"], "detected_no_ocr")  # Updated status
        self.assertIsNotNone(fields["plate_bbox"])  # the box itself is still real
        self.assertIsNone(fields["raw_plate_text"])
        self.assertIn("OCR", fields["plate_status_reason"])


# ---------------------------------------------------------------------------
# structured result format
# ---------------------------------------------------------------------------
class TestStructuredResultFormat(unittest.TestCase):
    REQUIRED_FIELDS = {
        "camera_id", "timestamp", "frame_index", "vehicle_bbox", "vehicle_class",
        "vehicle_confidence", "track_id", "plate_bbox", "raw_plate_text",
        "normalized_plate_text", "ocr_confidence", "plate_status",
    }

    def test_plate_detected_record_has_all_required_fields(self):
        crop = np.zeros((50, 50, 3), dtype=np.uint8)
        pd = _StubPlateDetector(dets=[{"bbox": [1, 1, 20, 15], "confidence": 0.7}])
        obs = vp._vehicle_observation(
            v_det={"bbox": [10, 10, 60, 60], "confidence": 0.9, "vehicle_type": "car", "track_id": 7},
            frame=np.zeros((100, 100, 3), dtype=np.uint8),
            camera_id="CAM_01", source_file="x.jpg", source_type="image", frame_index=None,
            vehicle_detector=_StubVehicleDetector(), plate_detector=pd,
            ocr=_StubOCR(text="TN38A81234", conf=0.6), timestamp="2026-01-01T00:00:00",
        )
        self.assertTrue(self.REQUIRED_FIELDS.issubset(obs.keys()))
        self.assertEqual(obs["track_id"], 7)
        self.assertEqual(obs["vehicle_class"], "car")
        self.assertEqual(obs["normalized_plate_text"], "TN38AB1234")
        self.assertEqual(obs["raw_plate_text"], "TN38A81234")
        self.assertTrue(obs["plate_status"], "detected")

    def test_unavailable_record_still_has_all_required_fields(self):
        obs = vp._vehicle_observation(
            v_det={"bbox": [0, 0, 20, 20], "confidence": 0.5, "vehicle_type": "bus", "track_id": None},
            frame=np.zeros((50, 50, 3), dtype=np.uint8),
            camera_id="CAM_02", source_file="x.mp4", source_type="video", frame_index=12,
            vehicle_detector=_StubVehicleDetector(), plate_detector=None,
            ocr=_StubOCR(), timestamp="2026-01-01T00:00:00",
        )
        self.assertTrue(self.REQUIRED_FIELDS.issubset(obs.keys()))
        self.assertEqual(obs["plate_status"], "unavailable")
        self.assertEqual(obs["frame_index"], 12)
        self.assertIsNone(obs["raw_plate_text"])


# ---------------------------------------------------------------------------
# pipeline orchestration (process_image / process_video)
# ---------------------------------------------------------------------------
class TestPipelineOrchestration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        img = np.full((120, 160, 3), 50, dtype=np.uint8)
        cv2.imwrite("synthetic.jpg", img)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_process_image_writes_annotated_output_and_flat_records(self):
        vd = _StubVehicleDetector(image_dets=[
            {"bbox": [10, 10, 60, 60], "confidence": 0.9, "vehicle_type": "car"},
        ])
        pd = _StubPlateDetector(dets=[{"bbox": [2, 2, 20, 10], "confidence": 0.5}])
        ocr = _StubOCR(text="KA05MH1234", conf=0.72)

        observations = vp.process_image("synthetic.jpg", "CAM_01", vd, pd, ocr)

        self.assertEqual(len(observations), 1)
        obs = observations[0]
        self.assertEqual(obs["camera_id"], "CAM_01")
        self.assertEqual(obs["plate_status"], "detected")
        self.assertTrue(os.path.isfile(obs["annotated_output"]))

    def test_process_image_with_no_vehicles_still_saves_annotated_frame(self):
        vd = _StubVehicleDetector(image_dets=[])
        observations = vp.process_image("synthetic.jpg", "CAM_01", vd, None, _StubOCR())
        self.assertEqual(observations, [])
        # annotated frame for the (empty) image should still exist
        self.assertTrue(os.path.isdir(vp.ANNOTATED_DIR))
        self.assertTrue(any(f.endswith("_annotated.jpg") for f in os.listdir(vp.ANNOTATED_DIR)))

    def test_process_video_respects_frame_sampling(self):
        frames = [
            (i, np.zeros((100, 100, 3), dtype=np.uint8),
             [{"bbox": [5, 5, 40, 40], "confidence": 0.8, "vehicle_type": "car", "track_id": 1}])
            for i in range(9)
        ]
        vd = _StubVehicleDetector(video_frames=frames)
        observations = vp.process_video("fake.mp4", "CAM_01", vd, None, _StubOCR(), frame_sample=3)
        frame_indices = sorted({o["frame_index"] for o in observations})
        self.assertEqual(frame_indices, [0, 3, 6])


if __name__ == "__main__":
    unittest.main()
