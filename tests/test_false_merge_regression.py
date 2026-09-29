"""
test_false_merge_regression.py

SIH26127 "FALSE TRACK MERGE FIX" pass (2026-09-09), Part B7 regression tests.

Root cause actually confirmed for the real Track 154 failure (docs/*, see
pipeline.py's filter_spatial_outlier_readings() / _spatial_outlier_keep_mask()
comments): this was NOT a classic ByteTrack identity false-merge (two
vehicles collapsed into one track ID) and NOT a classic ID-switch. Exact
per-frame vehicle-bbox trajectories (real CCTV data) proved the vehicle
tracking itself stayed smooth and correct throughout track 154's whole
lifetime. The actual bug was one level deeper: the PLATE detector, running
inside track 154's own (correctly tracked, slightly generous) vehicle crop,
sporadically picked up a different, physically adjacent vehicle's plate
(confirmed with real full-frame images - two cars stopped side-by-side near
a signal). So the fix target is cross-vehicle PLATE-READING contamination
within one track's own evidence, not ByteTrack's track-ID assignment logic
(which is untouched this session - see docs/TRACKING_TUNING.md for why
blind re-tuning wasn't warranted once this root cause was confirmed).

These tests map onto the brief's B7 scenario list as follows:

  1. two different vehicles crossing / side-by-side sharing one
     over-inclusive vehicle box -> test_track154_exact_real_scenario,
     test_two_vehicles_side_by_side_full_pipeline
  2. two nearby vehicles (boundary case)               -> test_boundary_just_inside_vs_just_outside_threshold
  3. different vehicle classes                          -> not applicable to this filter (it is
     purely plate-position-based, blind to vehicle_type) - see module docstring note in
     test_filter_is_blind_to_vehicle_class
  4. similar-looking vehicles (same appearance)          -> test_filter_is_position_based_not_appearance_based
  5. same/duplicate OCR text                             -> test_duplicate_text_still_filtered_if_position_is_anomalous
  6. temporary occlusion (gaps in readings)               -> test_sparse_readings_below_min_still_safe
  7. detector box fluctuation (normal jitter)             -> test_normal_bbox_jitter_never_falsely_filtered
  8. vehicle entering/exiting frame (degenerate bbox)     -> test_degenerate_vehicle_bbox_position_always_kept

All of these exercise the REAL, shipped functions in pipeline.py (no
reimplementation / no mocking of the logic under test).
"""

import os
import sys
import types
import numpy as np
import pytest

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
from database.observation_store import ObservationStore  # noqa: E402


def _isolated_db_path(tmp_name):
    path = os.path.join("/tmp", tmp_name)
    if os.path.exists(path):
        os.remove(path)
    return path


# ---------------------------------------------------------------------------
# 1. Exact real-coordinate regression lock for the actual Track 154 failure.
# ---------------------------------------------------------------------------

# Real (text, ocr_conf) readings and real (rel_cx, rel_cy) plate positions
# captured directly from a real, full, non-instrumented run_video_to_db()
# pass over the real anpr_test1.mp4 CCTV clip for track 154 (silver hatchback
# UP16CD5633, contaminated twice by an adjacent red SUV's own plate
# UP14FS3664) - see docs/ for the full investigation. Hardcoded here
# deliberately as a frozen regression fixture, NOT as a "make this one plate
# pass" special case: nothing in pipeline.py knows about this specific plate
# text or track id, the filter only ever looks at position.
TRACK154_REAL_READINGS = [
    ("UP16OO5633", 0.864), ("UP16O5633", 0.888), ("UP16CO5633", 0.939),
    ("UP16CO5633", 0.926), ("UP16CO5633", 0.848), ("14FS3664", 0.973),
    ("14FS3664", 0.971), ("UP16CD5633", 0.855), ("UP16CO5633", 0.923),
    ("UP16O5633", 0.952), ("UP16CO5633", 0.891), ("UP16CD5633", 0.844),
    ("UP16CD5633", 0.928),
]
TRACK154_REAL_POSITIONS = [
    (0.7250639386189258, 0.7236363636363636), (0.7406015037593985, 0.7347670250896058),
    (0.7776717557251909, 0.7639296187683284), (0.7755102040816326, 0.7735042735042735),
    (0.7853260869565217, 0.7829131652661064), (0.09304347826086956, 0.9445945945945946),
    (0.10490693739424704, 0.9485488126649076), (0.8097560975609757, 0.7893401015228426),
    (0.8133748055987559, 0.782608695652174), (0.8185907046476761, 0.7843822843822844),
    (0.8237410071942446, 0.7834821428571429), (0.8291666666666667, 0.7903225806451613),
    (0.8568435754189944, 0.8259023354564756),
]
# indices 5 and 6 are the two contaminating "14FS3664" (red SUV) readings.
CONTAMINATING_INDICES = {5, 6}


def test_track154_exact_real_scenario():
    """Frozen regression lock: replaying the real track 154 evidence through
    the shipped filter must drop exactly the 2 contaminating readings and
    keep all 11 legitimate ones - matching the confirmed real full-pipeline
    result (temporal_support 13 -> 11)."""
    filtered = pipeline.filter_spatial_outlier_readings(
        TRACK154_REAL_READINGS, TRACK154_REAL_POSITIONS
    )
    assert len(filtered) == 11
    filtered_texts = [t for t, _ in filtered]
    assert "14FS3664" not in filtered_texts
    # every legitimate (non-contaminating) reading must survive untouched
    kept_expected = [r for i, r in enumerate(TRACK154_REAL_READINGS) if i not in CONTAMINATING_INDICES]
    assert filtered == kept_expected


def test_track154_crop_selection_also_excludes_contamination():
    """The companion bug found and fixed alongside the text-vote filter:
    _spatial_outlier_keep_mask() must mark the two contaminating (red SUV)
    indices False so the "best crop/bbox" re-selection (pipeline.py,
    run_video_to_db finalization) never picks the highest-confidence
    reading blindly - which on this exact real track was the contaminating
    one (0.973, the single highest confidence of any reading on the
    track)."""
    mask = pipeline._spatial_outlier_keep_mask(TRACK154_REAL_POSITIONS)
    assert len(mask) == len(TRACK154_REAL_POSITIONS)
    for i in CONTAMINATING_INDICES:
        assert mask[i] is False, f"index {i} (contaminating reading) should be filtered"
    for i in range(len(mask)):
        if i not in CONTAMINATING_INDICES:
            assert mask[i] is True, f"index {i} (legitimate reading) should be kept"

    # the highest-confidence reading overall is one of the contaminating
    # ones (0.973) - naive argmax-by-confidence (the old, buggy behavior)
    # would pick it; the mask must steer selection away from it.
    naive_best_idx = max(range(len(TRACK154_REAL_READINGS)),
                          key=lambda i: TRACK154_REAL_READINGS[i][1])
    assert naive_best_idx in CONTAMINATING_INDICES
    kept_indices = [i for i, keep in enumerate(mask) if keep]
    masked_best_idx = max(kept_indices, key=lambda i: TRACK154_REAL_READINGS[i][1])
    assert masked_best_idx not in CONTAMINATING_INDICES


# ---------------------------------------------------------------------------
# 2. Boundary case: just inside vs just outside the deviation threshold.
# ---------------------------------------------------------------------------

def test_boundary_just_inside_vs_just_outside_threshold():
    thresh = pipeline.PLATE_POSITION_OUTLIER_MAX_DEVIATION
    base_readings = [("AB", 0.9), ("AB", 0.9), ("AB", 0.9), ("AB", 0.9)]
    base_positions = [(0.5, 0.5), (0.5, 0.5), (0.5, 0.5), (0.5, 0.5)]

    just_inside = base_positions + [(0.5 + thresh - 0.01, 0.5)]
    readings_inside = base_readings + [("AB", 0.9)]
    kept_inside = pipeline.filter_spatial_outlier_readings(readings_inside, just_inside)
    assert len(kept_inside) == 5  # nothing filtered - within tolerance

    just_outside = base_positions + [(0.5 + thresh + 0.01, 0.5)]
    readings_outside = base_readings + [("ZZ", 0.9)]
    kept_outside = pipeline.filter_spatial_outlier_readings(readings_outside, just_outside)
    assert len(kept_outside) == 4  # the one clear outlier is dropped
    assert ("ZZ", 0.9) not in kept_outside


# ---------------------------------------------------------------------------
# 3. The filter is blind to vehicle_type - it never receives it, so a
#    different-class "contaminating" detection is caught (or not) purely by
#    position, same as any other case. Documented explicitly rather than
#    silently assumed.
# ---------------------------------------------------------------------------

def test_filter_is_blind_to_vehicle_class():
    import inspect
    sig = inspect.signature(pipeline.filter_spatial_outlier_readings)
    assert "vehicle_type" not in sig.parameters and "vehicle_class" not in sig.parameters
    sig2 = inspect.signature(pipeline._spatial_outlier_keep_mask)
    assert "vehicle_type" not in sig2.parameters


# ---------------------------------------------------------------------------
# 4. Similar-looking (same-appearance) vehicles: the filter must still catch
#    contamination purely from position, proving it is NOT relying on any
#    text/appearance dissimilarity to notice the problem.
# ---------------------------------------------------------------------------

def test_filter_is_position_based_not_appearance_based():
    # 5 consistent readings near one position, 2 outlier readings that
    # happen to have IDENTICAL text to the legitimate ones (so a
    # text-similarity heuristic would see nothing wrong) but a wildly
    # different position - the filter must still drop them.
    readings = [("SAME1234", 0.9)] * 5 + [("SAME1234", 0.95)] * 2
    positions = [(0.7, 0.7)] * 5 + [(0.05, 0.95)] * 2
    filtered = pipeline.filter_spatial_outlier_readings(readings, positions)
    assert len(filtered) == 5


# ---------------------------------------------------------------------------
# 5. Duplicate/identical OCR text at an anomalous position must still be
#    filtered - text identity must never be treated as evidence the
#    reading is legitimate.
# ---------------------------------------------------------------------------

def test_duplicate_text_still_filtered_if_position_is_anomalous():
    readings = [("UP16CD5633", 0.9), ("UP16CD5633", 0.91), ("UP16CD5633", 0.89),
                ("UP16CD5633", 0.99)]  # last one: same text, but...
    positions = [(0.7, 0.7), (0.72, 0.71), (0.71, 0.69),
                 (0.05, 0.95)]  # ...wildly different position
    filtered = pipeline.filter_spatial_outlier_readings(readings, positions)
    assert len(filtered) == 3
    assert filtered == [("UP16CD5633", 0.9), ("UP16CD5633", 0.91), ("UP16CD5633", 0.89)]


# ---------------------------------------------------------------------------
# 6. Sparse readings (temporary occlusion producing gaps) below
#    PLATE_POSITION_OUTLIER_MIN_READINGS: must stay safe (no filtering
#    attempted with insufficient evidence to establish "normal").
# ---------------------------------------------------------------------------

def test_sparse_readings_below_min_still_safe():
    min_readings = pipeline.PLATE_POSITION_OUTLIER_MIN_READINGS
    readings = [("AB1234", 0.9), ("ZZ9999", 0.99)][: max(1, min_readings - 1)]
    positions = [(0.7, 0.7), (0.05, 0.95)][: max(1, min_readings - 1)]
    filtered = pipeline.filter_spatial_outlier_readings(readings, positions)
    assert filtered == readings  # untouched - not enough evidence yet


# ---------------------------------------------------------------------------
# 7. Normal detector-box jitter (small, sub-threshold position noise) must
#    never be falsely flagged as contamination.
# ---------------------------------------------------------------------------

def test_normal_bbox_jitter_never_falsely_filtered():
    import random
    rng = random.Random(42)
    positions = [(0.7 + rng.uniform(-0.03, 0.03), 0.75 + rng.uniform(-0.03, 0.03))
                 for _ in range(10)]
    readings = [("UP16CD5633", 0.85 + i * 0.01) for i in range(10)]
    filtered = pipeline.filter_spatial_outlier_readings(readings, positions)
    assert len(filtered) == 10  # normal jitter is well under the 0.35 threshold


# ---------------------------------------------------------------------------
# 8. Vehicle entering/exiting frame: a degenerate (zero-area) vehicle bbox
#    yields position=None from _plate_relative_position(); such readings
#    must always be kept (absence of position evidence is not itself
#    evidence of contamination).
# ---------------------------------------------------------------------------

def test_degenerate_vehicle_bbox_position_always_kept():
    assert pipeline._plate_relative_position([10, 10, 20, 20], [5, 5, 5, 20]) is None  # zero width
    assert pipeline._plate_relative_position([10, 10, 20, 20], [5, 5, 20, 5]) is None  # zero height

    readings = [("AB1234", 0.9)] * 4 + [("AB1234", 0.9)]
    positions = [(0.7, 0.7)] * 4 + [None]  # last vehicle mid-exit-frame -> degenerate bbox -> None
    filtered = pipeline.filter_spatial_outlier_readings(readings, positions)
    assert len(filtered) == 5  # the None-position reading is always kept


# ---------------------------------------------------------------------------
# Full-pipeline integration test: two physically adjacent vehicles sharing
# one generously-sized vehicle bbox (the real track154 mechanism), built
# with the same marker-crop synthetic harness used by
# test_track_evidence_isolation.py, but this time deliberately WITH a
# shared/overlapping crop region so contamination CAN occur, and verifying
# the final record attributes the plate (text AND crop/bbox) only to the
# dominant vehicle's own evidence.
# ---------------------------------------------------------------------------

class TwoAdjacentVehiclesDetector:
    """One tracked vehicle (track 500) whose reported bbox is generously
    sized (mirroring a real, loose vehicle detection box), with a SECOND,
    different vehicle's plate-marker painted into a corner of that same
    box on a minority of frames - exactly the real track154 mechanism:
    correct, stable vehicle tracking, contaminated only at the
    plate-detection-within-crop stage."""

    def __init__(self, n_frames=13, contaminated_frames=(5, 6)):
        self.n_frames = n_frames
        self.contaminated_frames = set(contaminated_frames)
        # track 500's own vehicle bbox: large and stable across all frames
        self.vehicle_bbox = [200, 100, 600, 400]

    def track_video(self, video_path):
        for i in range(self.n_frames):
            frame = np.zeros((500, 800, 3), dtype=np.uint8)
            if i in self.contaminated_frames:
                # Real track154 mechanism: the real, shipped pipeline only
                # ever keeps the SINGLE best-scoring plate detection per
                # frame (see run_video_to_db()'s scored_dets logic) - the
                # actual bug was frames where the plate detector's best pick
                # THAT frame was a different, physically adjacent vehicle's
                # plate (own plate not the winning candidate that frame,
                # e.g. a worse angle/glare), not both plates competing at
                # once. Mirrored here: on a contaminated frame, only the
                # OTHER vehicle's marker is painted - own plate region
                # stays background (undetectable that frame), exactly like
                # the real failure.
                # margin (like test_track_evidence_isolation.py's
                # MarkerVehicleDetector) so pipeline.py's plate-crop padding
                # (_pad_plate_bbox) doesn't dilute the marker mean with
                # background (0) pixels
                other_px1, other_py1, other_px2, other_py2 = 210, 380, 260, 398
                frame[other_py1 - 25:other_py2 + 25, other_px1 - 25:other_px2 + 25] = 222
            else:
                # normal frame: track 500's OWN plate region, consistent
                # relative position (~0.78, 0.78 of the vehicle bbox),
                # marker value 77
                own_px1, own_py1, own_px2, own_py2 = 510, 330, 560, 360
                frame[own_py1 - 25:own_py2 + 25, own_px1 - 25:own_px2 + 25] = 77
            yield i, frame, [{"track_id": 500, "bbox": self.vehicle_bbox,
                               "confidence": 0.9, "vehicle_type": "car"}]

    def crop(self, frame, bbox):
        x1, y1, x2, y2 = bbox
        return frame[y1:y2, x1:x2]


class TwoRegionPlateDetector:
    """Detects BOTH marker regions independently as separate plate
    candidates when both are present in a frame (mirroring a real plate
    detector finding more than one plausible plate-shaped region inside one
    generous vehicle crop) - own plate always first/primary."""

    def detect_on_array(self, arr):
        dets = []
        # own plate region (marker 77), in VEHICLE-CROP-relative coords
        own = (510 - 200, 330 - 100, 560 - 200, 360 - 100)
        if arr[own[1]:own[3], own[0]:own[2]].max() > 0:
            dets.append({"bbox": list(own), "confidence": 0.9})
        other = (210 - 200, 380 - 100, 260 - 200, 398 - 100)
        if other[1] >= 0 and arr[other[1]:other[3], other[0]:other[2]].max() > 0:
            dets.append({"bbox": list(other), "confidence": 0.9})
        return dets

    def crop_array(self, arr, bbox):
        x1, y1, x2, y2 = bbox
        return arr[y1:y2, x1:x2]


class TwoVehicleMarkerOCR:
    def __init__(self, marker_to_plate):
        self.marker_to_plate = marker_to_plate

    def read(self, crop_img, return_debug=False):
        marker = int(round(float(crop_img.mean())))
        text = self.marker_to_plate.get(marker)
        conf = 0.99 if marker == 222 else 0.85  # contaminating reading: HIGHEST confidence,
                                                   # exactly like the real track154 case, so a
                                                   # naive "pick highest confidence" selection
                                                   # would be fooled if the fix didn't work
        if text is None:
            if return_debug:
                return None, 0.0, {"preprocessing_mode": "original", "ocr_candidate_count": 0,
                                    "quality": {"quality_score": 0.0, "blur_score": 0.0,
                                                "brightness": 0.0, "contrast": 0.0}}
            return None, 0.0
        if return_debug:
            return text, conf, {
                "preprocessing_mode": "original", "ocr_candidate_count": 1,
                "quality": {"quality_score": 0.9, "blur_score": 500.0,
                            "brightness": 120.0, "contrast": 70.0},
            }
        return text, conf


def test_two_vehicles_side_by_side_full_pipeline():
    """End-to-end: track 500's own plate must win the vote AND the
    saved crop/bbox, despite the contaminating adjacent vehicle's reading
    having strictly higher per-frame OCR confidence on every occurrence -
    the exact real track154 failure mode, reproduced synthetically and run
    through the real, unmodified run_video_to_db()."""
    pipeline.get_appearance_vector = lambda crop: [0.0]

    marker_to_plate = {77: "TN10AB1234", 222: "KA02MM9091"}
    db_path = _isolated_db_path("test_false_merge_two_adjacent.db")
    store = ObservationStore(db_path=db_path)
    records, _ = pipeline.run_video_to_db(
        "fake.mp4",
        TwoAdjacentVehiclesDetector(n_frames=13, contaminated_frames=(5, 6)),
        TwoRegionPlateDetector(),
        TwoVehicleMarkerOCR(marker_to_plate),
        "CAM_FALSE_MERGE_TEST", 13.08, 80.27, store, write_annotated=False,
    )
    store.close()

    by_track = {int(r["track_id"]): r for r in records}
    assert 500 in by_track
    rec = by_track[500]

    # the voted text must be track 500's OWN plate, never the contaminant's
    assert rec["plate_text"] == "TN10AB1234"
    assert rec["plate_text"] != "KA02MM9091"

    # the saved crop/bbox must ALSO be track 500's own plate region, not the
    # contaminant's - even though the contaminant had higher confidence
    assert rec["plate_crop_path"] is not None
    import cv2
    saved_crop = cv2.imread(rec["plate_crop_path"])
    assert saved_crop is not None
    assert int(round(float(saved_crop.mean()))) == 77, (
        "saved plate_crop_path must show track 500's OWN plate (marker 77), "
        "not the contaminating adjacent vehicle's plate (marker 222)"
    )


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(pytest.main([__file__, "-v"]))
