"""
test_track_evidence_isolation.py

SIH26127: regression guard for the "cross-track OCR contamination" question
raised against docs/OCR_REAL_ACCURACY_AUDIT.md's track-161 finding. The
investigation (docs/CROSS_TRACK_CONTAMINATION_INVESTIGATION.md) found NO
shared-state leak - track evidence buffers (track_ocr_readings and friends
in pipeline.run_video_to_db()) are function-local dicts keyed by track_id,
with no possible key aliasing. These tests lock that property in with real
multi-vehicle/lifecycle scenarios rather than just static reasoning, so a
future refactor that DOES introduce a leak (e.g. someone "optimizing" these
dicts to module level, or reusing a mutable default argument) fails loudly
here instead of silently corrupting plate results the way the audit found.

Each fake vehicle's crop is stamped with a distinct pixel "marker" value
(not a real plate image) and FakeMarkerOCR reads the marker back out and
maps it to that vehicle's real plate text - so if any crop /
reading / vote ever gets attributed to the wrong track, the marker->plate
mapping catches it immediately, deterministically, with no fuzzy-matching
ambiguity.
"""

import os
import sys
import types
import numpy as np

_STUB_MODULES = []
for _name in ("ultralytics", "paddleocr", "torch", "torchvision",
              "torchvision.models", "torchvision.transforms"):
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)
        _STUB_MODULES.append(_name)
sys.modules["ultralytics"].YOLO = object
sys.modules["paddleocr"].PaddleOCR = object

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import atexit


def cleanup_stub_modules():
    for module_name in _STUB_MODULES:
        if module_name in sys.modules:
            del sys.modules[module_name]


atexit.register(cleanup_stub_modules)

import pipeline  # noqa: E402
from pipeline import _pad_plate_bbox  # noqa: E402
from database.observation_store import ObservationStore  # noqa: E402

# SIH26127 (2026-09-14): pipeline.run_video_to_db() pads every plate bbox by
# PLATE_CROP_PAD_RATIO (see pipeline._pad_plate_bbox) before cropping from
# the ORIGINAL frame - it does not crop exactly at the vehicle/plate bbox
# the detector reported. These marker-based fixtures used to fill only the
# exact, unpadded bbox with each vehicle's marker value, so the real
# (padded) crop pipeline.py actually takes included a border of the frame's
# black (0) background outside the marker - diluting the crop's mean pixel
# value and making MarkerOCR see a wrong, unrecognized "marker" that was
# never a real cross-track leak, just this fixture not accounting for
# padding. Filling the PADDED region instead (using the real production
# padding function, not a guessed margin) makes every crop the pipeline
# actually takes 100% pure marker, regardless of how PLATE_CROP_PAD_RATIO
# is tuned in the future.
_FRAME_W, _FRAME_H = 500, 100


def _fill_marker(frame, bbox, marker):
    px1, py1, px2, py2 = _pad_plate_bbox(bbox, _FRAME_W, _FRAME_H)
    frame[py1:py2, px1:px2] = marker


def _isolated_db_path(tmp_name):
    path = os.path.join("/tmp", tmp_name)
    if os.path.exists(path):
        os.remove(path)
    return path


# ---------------------------------------------------------------------------
# Fakes: marker-stamped crops so identity is unambiguous, not fuzzy-matched.
# ---------------------------------------------------------------------------

class MarkerVehicleDetector:
    """Multiple simultaneous, spatially well-separated tracks, each frame's
    vehicle region filled with a distinct constant pixel value (the
    'marker') so downstream code can be checked for identity leaks with
    exact equality instead of visual/fuzzy inspection."""

    def __init__(self, track_specs, n_frames):
        # track_specs: {track_id: (bbox, marker_value)}
        self.track_specs = track_specs
        self.n_frames = n_frames

    def track_video(self, video_path):
        for i in range(self.n_frames):
            frame = np.zeros((100, 500, 3), dtype=np.uint8)
            dets = []
            for track_id, (bbox, marker) in self.track_specs.items():
                _fill_marker(frame, bbox, marker)
                dets.append({
                    "track_id": track_id, "bbox": bbox,
                    "confidence": 0.9, "vehicle_type": "car",
                })
            yield i, frame, dets

    def crop(self, frame, bbox):
        x1, y1, x2, y2 = bbox
        return frame[y1:y2, x1:x2]


class MarkerPlateDetector:
    """The 'plate' is the whole vehicle crop (marker preserved exactly)."""

    def detect_on_array(self, arr):
        h, w = arr.shape[:2]
        return [{"bbox": [0, 0, w, h], "confidence": 0.9}]

    def crop_array(self, arr, bbox):
        x1, y1, x2, y2 = bbox
        return arr[y1:y2, x1:x2]


class MarkerOCR:
    """Reads the marker value back out of a crop's mean pixel value and
    maps it to that vehicle's real plate text - any crop whose marker
    doesn't match a known vehicle raises loudly rather than silently
    returning a plausible-looking wrong answer, since that would defeat
    the point of this test."""

    def __init__(self, marker_to_plate):
        self.marker_to_plate = marker_to_plate

    def read(self, crop_img, return_debug=False):
        marker = int(round(float(crop_img.mean())))
        text = self.marker_to_plate.get(marker)
        assert text is not None, (
            f"MarkerOCR saw an unrecognized marker value {marker} - this would "
            f"mean a crop came from neither vehicle's designated frame region, "
            f"which should be impossible with the fixed synthetic frame layout."
        )
        conf = 0.95
        if return_debug:
            return text, conf, {
                "preprocessing_mode": "original", "ocr_candidate_count": 1,
                "quality": {"quality_score": 0.9, "blur_score": 500.0,
                            "brightness": 120.0, "contrast": 70.0},
            }
        return text, conf


def test_concurrent_multiple_vehicles_never_cross_contaminate():
    """3 vehicles, simultaneously visible across 20 frames, each with its
    own distinct plate. Track 101 must never receive track 102/103's OCR
    evidence, and vice versa - checked via exact plate_text equality, not
    similarity, so any leak (even a single wrong record) fails the test."""
    pipeline.get_appearance_vector = lambda crop: [0.0]

    track_specs = {
        101: ([0, 0, 50, 50], 40),
        102: ([200, 0, 250, 50], 120),
        103: ([400, 0, 450, 50], 200),
    }
    marker_to_plate = {40: "TN10AB1234", 120: "KA02MM9091", 200: "UP22AT3248"}

    db_path = _isolated_db_path("test_isolation_concurrent.db")
    store = ObservationStore(db_path=db_path)
    records, _ = pipeline.run_video_to_db(
        "fake.mp4",
        MarkerVehicleDetector(track_specs, n_frames=20),
        MarkerPlateDetector(),
        MarkerOCR(marker_to_plate),
        "CAM_ISOLATION_TEST", 13.08, 80.27, store, write_annotated=False,
    )
    store.close()

    assert len(records) == 3
    by_track = {int(r["track_id"]): r for r in records}
    assert set(by_track.keys()) == {101, 102, 103}

    assert by_track[101]["plate_text"] == "TN10AB1234"
    assert by_track[102]["plate_text"] == "KA02MM9091"
    assert by_track[103]["plate_text"] == "UP22AT3248"

    # each track's plate must be its OWN and only its own - no other
    # vehicle's plate text should appear anywhere in its record
    other_plates_101 = {"KA02MM9091", "UP22AT3248"}
    other_plates_102 = {"TN10AB1234", "UP22AT3248"}
    other_plates_103 = {"TN10AB1234", "KA02MM9091"}
    assert by_track[101]["plate_text"] not in other_plates_101
    assert by_track[102]["plate_text"] not in other_plates_102
    assert by_track[103]["plate_text"] not in other_plates_103

    # re-open the DB fresh to prove this held after persistence too, not
    # just in the in-memory records list
    store2 = ObservationStore(db_path=db_path)
    rows = {int(r["track_id"]): r for r in store2.all_observations()}
    store2.close()
    assert rows[101]["plate_text"] == "TN10AB1234"
    assert rows[102]["plate_text"] == "KA02MM9091"
    assert rows[103]["plate_text"] == "UP22AT3248"


def test_track_lifecycle_new_track_does_not_inherit_old_tracks_evidence():
    """Track 101 appears, gets OCR evidence, and disappears; a NEW track
    102 (different vehicle, different plate) appears afterward. 102 must
    start with zero evidence of its own, never inheriting 101's readings -
    this is what would happen if track buffers were accidentally shared
    across track lifecycles instead of being fresh per track_id."""
    pipeline.get_appearance_vector = lambda crop: [0.0]

    class SequentialVehicleDetector:
        def track_video(self, video_path):
            # frames 0-9: only track 101 visible
            for i in range(10):
                frame = np.zeros((100, 500, 3), dtype=np.uint8)
                _fill_marker(frame, [0, 0, 50, 50], 40)
                yield i, frame, [{"track_id": 101, "bbox": [0, 0, 50, 50],
                                   "confidence": 0.9, "vehicle_type": "car"}]
            # frames 10-19: track 101 gone, NEW track 102 (different vehicle) visible
            for i in range(10, 20):
                frame = np.zeros((100, 500, 3), dtype=np.uint8)
                _fill_marker(frame, [200, 0, 250, 50], 120)
                yield i, frame, [{"track_id": 102, "bbox": [200, 0, 250, 50],
                                   "confidence": 0.9, "vehicle_type": "car"}]

        def crop(self, frame, bbox):
            x1, y1, x2, y2 = bbox
            return frame[y1:y2, x1:x2]

    marker_to_plate = {40: "TN10AB1234", 120: "KA02MM9091"}
    db_path = _isolated_db_path("test_isolation_lifecycle.db")
    store = ObservationStore(db_path=db_path)
    records, _ = pipeline.run_video_to_db(
        "fake.mp4", SequentialVehicleDetector(), MarkerPlateDetector(),
        MarkerOCR(marker_to_plate),
        "CAM_ISOLATION_TEST", 13.08, 80.27, store, write_annotated=False,
    )
    store.close()

    by_track = {int(r["track_id"]): r for r in records}
    assert set(by_track.keys()) == {101, 102}
    assert by_track[101]["plate_text"] == "TN10AB1234"
    assert by_track[101]["first_seen_frame"] == 0
    assert by_track[101]["last_seen_frame"] == 9
    # the critical assertion: track 102 must be its OWN vehicle's plate,
    # never 101's - a shared/leftover buffer would show TN10AB1234 here
    assert by_track[102]["plate_text"] == "KA02MM9091"
    assert by_track[102]["first_seen_frame"] == 10
    assert by_track[102]["temporal_support"] == by_track[102]["temporal_support"]  # sanity: field exists
    assert by_track[102]["temporal_support"] > 0
