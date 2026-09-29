
import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

import cv2

from detection.vehicle_detector import VehicleDetector
from detection.detect_plates import PlateDetector
from recognition.ocr_reader import vote_plate_text, try_init_ocr
from recognition.appearance import get_appearance_vector
from recognition.plate_matcher import normalize_plate
from recognition.plate_normalizer import normalize_indian_plate
from config import RESULTS_DIR
from network.rtsp_camera import redact_rtsp_url
LOW_CONFIDENCE_THRESHOLD = 0.55

ANNOTATED_VIDEO_DIR = str(RESULTS_DIR / "annotated_videos")


OCR_SAMPLE_INTERVAL = 3
OCR_EARLY_STOP_MIN_READINGS = 7
OCR_EARLY_STOP_CONFIDENCE = 0.90


PLATE_CROP_PAD_RATIO = 0.12
PLATE_CROP_PAD_MIN_PX = 3


def _pad_plate_bbox(bbox, frame_w, frame_h,
                     ratio=PLATE_CROP_PAD_RATIO, min_px=PLATE_CROP_PAD_MIN_PX):
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1
    pad_x = max(min_px, round(w * ratio))
    pad_y = max(min_px, round(h * ratio))
    return [
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(frame_w, x2 + pad_x),
        min(frame_h, y2 + pad_y),
    ]

PLATE_POSITION_OUTLIER_MAX_DEVIATION = 0.35
PLATE_POSITION_OUTLIER_MIN_READINGS = 3


def _plate_relative_position(plate_bbox_frame, vehicle_bbox):
    """
    Returns (rel_cx, rel_cy): the plate bbox's center as a fraction of the
    tracked vehicle's own bbox width/height (frame-space coordinates for
    both). 0.5 would be dead-center; a plate detection belonging to a
    physically different, adjacent vehicle sharing the same crop tends to
    land far outside this track's own established range, since it is not
    the tracked vehicle's own plate. Returns None if the vehicle bbox has
    zero width/height (degenerate box - should not normally happen).
    """
    vx1, vy1, vx2, vy2 = vehicle_bbox
    vw = vx2 - vx1
    vh = vy2 - vy1
    if vw <= 0 or vh <= 0:
        return None
    px1, py1, px2, py2 = plate_bbox_frame
    pcx = (px1 + px2) / 2.0
    pcy = (py1 + py2) / 2.0
    return ((pcx - vx1) / vw, (pcy - vy1) / vh)


def _spatial_outlier_keep_mask(positions,
                                max_deviation=PLATE_POSITION_OUTLIER_MAX_DEVIATION,
                                min_readings=PLATE_POSITION_OUTLIER_MIN_READINGS):

    if len(positions) < min_readings:
        return [True] * len(positions)

    known = [p for p in positions if p is not None]
    if len(known) < min_readings:
        return [True] * len(positions)

    xs = sorted(p[0] for p in known)
    ys = sorted(p[1] for p in known)
    median_x = xs[len(xs) // 2]
    median_y = ys[len(ys) // 2]

    mask = []
    for pos in positions:
        if pos is None:
            mask.append(True)
            continue
        dx = abs(pos[0] - median_x)
        dy = abs(pos[1] - median_y)
        mask.append(not (dx > max_deviation or dy > max_deviation))

    # Same defensive guard as filter_spatial_outlier_readings(): never let
    # every index look like an outlier relative to each other.
    if not any(mask):
        return [True] * len(positions)
    return mask


def filter_spatial_outlier_readings(readings, positions,
                                     max_deviation=PLATE_POSITION_OUTLIER_MAX_DEVIATION,
                                     min_readings=PLATE_POSITION_OUTLIER_MIN_READINGS):
    if len(readings) != len(positions):
        return readings

    mask = _spatial_outlier_keep_mask(positions, max_deviation, min_readings)
    kept = [r for r, keep in zip(readings, mask) if keep]

    # Never let the filter remove every reading - if somehow all of them
    # look like outliers relative to each other (should not happen with a
    # real median, but guarded defensively), fall back to the untouched
    # original list rather than losing the track's plate entirely.
    return kept if kept else readings


def _plate_status_for_track(ocr_available, has_plate_bbox, record_text, ocr_conf):
    """
    Single place that decides the honest plate_status tier for one
    finished track, shared by the API response builder and the annotated
    video writer so both surfaces agree with each other.

        unavailable       - no OCR engine this run (plate_detector may
                             still have found a box)
        no_plate_detected - plate detector never found a plate box on
                             this vehicle across the whole track
        detected_not_read - a plate box was found, but OCR never produced
                             usable text for it
        low_confidence     - OCR produced text, but below
                             LOW_CONFIDENCE_THRESHOLD - shown as
                             "verification required", never as fact
        recognized         - OCR produced text at or above the threshold
    """
    if not ocr_available:
        return "unavailable"
    if not has_plate_bbox:
        return "no_plate_detected"
    if not record_text:
        return "detected_not_read"
    if (ocr_conf or 0.0) < LOW_CONFIDENCE_THRESHOLD:
        return "low_confidence"
    return "recognized"


# A track's voted plate is only ever reported as the strongest state,
# VERIFIED, once it has BOTH a confident vote AND enough independent
# frames actually supporting it - "Do not mark a plate VERIFIED based on
# one weak frame" (SIH26127 requirement). Below that bar but still
# text-bearing/plausible, it's TENTATIVE - a real read, just not yet
# backed by enough repeated evidence to present as settled.
PLATE_STATE_VERIFIED_MIN_READINGS = 3
PLATE_STATE_VERIFIED_MIN_CONFIDENCE = 0.70


def _plate_state_for_track(plate_status, temporal_support, combined_confidence):
    """
    Coarse, judge/demo-facing 4-state rollup (UNKNOWN / LOW_CONFIDENCE /
    TENTATIVE / VERIFIED) requested for the SIH26127 "quality-aware
    temporal evidence" story. plate_status (_plate_status_for_track above)
    stays the detailed, "why" reason code already used by the DB/API/
    annotated video - this is a simpler summary layered on top of it, not
    a replacement.
    """
    if plate_status in ("unavailable", "no_plate_detected", "detected_not_read"):
        return "UNKNOWN"
    if plate_status == "low_confidence":
        return "LOW_CONFIDENCE"
    # plate_status == "recognized" from here on - still need real temporal
    # depth before calling it VERIFIED rather than just TENTATIVE.
    if temporal_support >= PLATE_STATE_VERIFIED_MIN_READINGS and (combined_confidence or 0.0) >= PLATE_STATE_VERIFIED_MIN_CONFIDENCE:
        return "VERIFIED"
    return "TENTATIVE"


# SIH26127 Priority 2 sub-part: plate-assisted track continuity. A window
# (in frames) within which a NEW track starting shortly after an OLD track
# ended is even considered as a possible continuation of the same physical
# vehicle. This is a heuristic, not derived from track_buffer directly
# (track_buffer is an internal ByteTrack "how long to keep a lost track
# alive" parameter in a different unit-space) - kept deliberately short
# (3s @ 25fps) so this only ever fires on genuine short occlusions, not on
# a vehicle that left and a different one later coincidentally matching.
PLATE_CONTINUITY_MAX_GAP_FRAMES = 75
# Two bboxes are only considered spatially plausible as the same vehicle
# reappearing if their centers are within this many multiples of the
# average of the two boxes' own size - a real vehicle moving normally for
# up to ~3 seconds won't jump many times its own length; a false link from
# two different vehicles that happen to share a plate misread would.
PLATE_CONTINUITY_MAX_SPATIAL_RATIO = 4.0
# Evidence tiers strong enough to even be considered for continuity -
# LOW_CONFIDENCE/UNKNOWN plates aren't trustworthy enough to link identity
# on ("Only merge when evidence is strong").
_CONTINUITY_ELIGIBLE_PLATE_STATES = ("TENTATIVE", "VERIFIED")


def _bbox_center_and_scale(bbox):
    if not bbox or len(bbox) != 4:
        return None
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    scale = max(((x2 - x1) + (y2 - y1)) / 2.0, 1.0)
    return cx, cy, scale


def link_plate_continuity(records):
    """
    Additive, non-destructive post-pass over one run's finished records:
    flags pairs of DIFFERENT track_ids as likely the same physical vehicle
    across a short gap (e.g. a temporary occlusion that ByteTrack itself
    could not bridge - see docs/TRACKING_TUNING.md for why track_buffer
    alone doesn't fully solve this). Never merges track_ids, never rewrites
    plate text, never changes any existing field - only adds
    `continuity_linked_track_id` / `continuity_confidence` /
    `continuity_evidence` to the records it links, leaving everything else
    untouched. Camera-local track identity (track_id) and this
    cross-gap "same vehicle, probably" signal are kept explicitly separate
    fields, per the requirement to not conflate them.

    A pair (A ends, B starts) is only linked when ALL of the following
    hold - "only merge when evidence is strong", not a blind plate-text
    match:
      1. Both A and B have plate_state in TENTATIVE/VERIFIED (real,
         reasonably-evidenced OCR, not a low-confidence guess)
      2. B starts strictly after A ends, within
         PLATE_CONTINUITY_MAX_GAP_FRAMES frames (time continuity)
      3. Same vehicle_type (a car track is never linked to a truck track)
      4. Plate identity matches - exact normalized-text match, or fuzzy
         match via recognition.plate_matcher.plate_similarity() at a high
         threshold (handles a residual single-character OCR difference
         between the two tracks' independently-voted texts)
      5. Spatial continuity - A's LAST seen bbox and B's FIRST seen bbox
         are close relative to their own size (see
         PLATE_CONTINUITY_MAX_SPATIAL_RATIO) - this is what keeps this
         from linking two different vehicles on opposite sides of frame
         that happen to share a plate misread

    Returns the same `records` list, mutated in place (also returned for
    convenience). Records are matched at most once each (first strong
    match wins) - this is a simple, auditable pass, not a full assignment
    optimization.
    """
    from recognition.plate_matcher import plate_similarity

    eligible = [
        r for r in records
        if r.get("plate_state") in _CONTINUITY_ELIGIBLE_PLATE_STATES
        and r.get("normalized_plate")
        and r.get("last_seen_bbox") and r.get("first_seen_bbox")
    ]
    # ends (candidate "A" - the track that finished) sorted so earlier
    # gaps are considered first; nothing fancier than first-match-wins.
    already_linked = set()

    for a in eligible:
        if a["track_id"] in already_linked:
            continue
        for b in eligible:
            if a is b or b["track_id"] in already_linked:
                continue
            if a["track_id"] == b["track_id"]:
                continue
            gap = b["first_seen_frame"] - a["last_seen_frame"]
            if gap <= 0 or gap > PLATE_CONTINUITY_MAX_GAP_FRAMES:
                continue
            if a.get("vehicle_type") != b.get("vehicle_type"):
                continue

            plate_a, plate_b = a["normalized_plate"], b["normalized_plate"]
            if plate_a == plate_b:
                sim = 1.0
            else:
                sim = plate_similarity(plate_a, plate_b)
            if sim < 0.90:
                continue

            a_center = _bbox_center_and_scale(a["last_seen_bbox"])
            b_center = _bbox_center_and_scale(b["first_seen_bbox"])
            if a_center is None or b_center is None:
                continue
            ax, ay, ascale = a_center
            bx, by, bscale = b_center
            dist = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
            avg_scale = (ascale + bscale) / 2.0
            spatial_ratio = dist / avg_scale
            if spatial_ratio > PLATE_CONTINUITY_MAX_SPATIAL_RATIO:
                continue

            # All checks passed - strong evidence, link both directions.
            confidence = round(sim * max(0.0, 1.0 - spatial_ratio / PLATE_CONTINUITY_MAX_SPATIAL_RATIO), 3)
            evidence = {
                "gap_frames": gap,
                "plate_similarity": round(sim, 3),
                "spatial_ratio": round(spatial_ratio, 2),
                "reason": "matching plate identity + spatial + time continuity across a short gap",
            }
            a["continuity_linked_track_id"] = b["track_id"]
            a["continuity_confidence"] = confidence
            a["continuity_evidence"] = evidence
            b["continuity_linked_track_id"] = a["track_id"]
            b["continuity_confidence"] = confidence
            b["continuity_evidence"] = evidence
            already_linked.add(a["track_id"])
            already_linked.add(b["track_id"])
            break

    return records


def estimate_direction(bbox_history, min_movement_px=15):
    """
    coarse movement direction from a track's bbox centers over time.
    bbox_history: list of [x1,y1,x2,y2] in frame order.

    deliberately conservative - with too little movement or too few frames
    to judge, returns "stationary_or_unclear" rather than guessing. this is
    NOT a real velocity/heading estimate, just a rough left/right/up/down
    signal for display - don't feed this into anything safety-critical.
    """
    if len(bbox_history) < 2:
        return "unknown"

    def center(b):
        x1, y1, x2, y2 = b
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    cx0, cy0 = center(bbox_history[0])
    cx1, cy1 = center(bbox_history[-1])
    dx, dy = cx1 - cx0, cy1 - cy0

    if abs(dx) < min_movement_px and abs(dy) < min_movement_px:
        return "stationary_or_unclear"

    if abs(dx) >= abs(dy):
        return "left_to_right" if dx > 0 else "right_to_left"
    else:
        return "top_to_bottom" if dy > 0 else "bottom_to_top"


# SIH26127 credential-leak fix: pipeline.py used to write
# record["source"] = video_path verbatim - harmless for a local file path,
# but once video_path can be a real camera's credentialed RTSP(S) URL (see
# network/rtsp_camera.py's resolve_camera_source()), that would write the
# camera's username/password straight into the observations DB and, from
# there, the observations API/UI. Reuses the exact same, already-tested
# redact_rtsp_url() logic (network/rtsp_camera.py) rather than duplicating
# a second credential-masking regex here - a local file path has no
# userinfo/"@" segment, so it passes through completely unchanged.
def _safe_source_label(source):
    return redact_rtsp_url(source)


def make_record(text, conf, cam_id, lat, lng, track_id=None, vehicle_type=None, ts=None):
    return {
        "plate_text": text,
        "confidence": conf,
        "camera_id": cam_id,
        "timestamp": (ts or datetime.now()).isoformat(),
        "lat": lat,
        "long": lng,
        "track_id": track_id,
        "vehicle_type": vehicle_type,
    }


def run_on_video(video_path, vehicle_detector, plate_detector, ocr,
                  cam_id, lat, lng, fps_assumed=25):
    """
    returns (records, appearance_vectors) where appearance_vectors is a dict
    keyed by the record's position in the records list (matches how
    observation_store expects to receive them alongside add_many()).
    """
    # per track_id: collect (plate_text, confidence) readings across frames,
    # plus keep the best-quality vehicle crop seen so far for the appearance vector
    track_ocr_readings = defaultdict(list)
    track_best_crop = {}
    track_best_crop_conf = defaultdict(float)
    track_vehicle_type = {}
    track_first_frame = {}

    base_time = datetime.now()

    for frame_idx, frame, vehicle_dets in vehicle_detector.track_video(video_path):
        print(f"[pipeline] Frame {frame_idx}: {len(vehicle_dets)} vehicle detections")
        for v_det in vehicle_dets:
            track_id = v_det.get("track_id")
            print(f"[pipeline]   Detection: bbox={v_det['bbox']}, conf={v_det['confidence']}, type={v_det['vehicle_type']}, track_id={track_id}")
            # The detector now always returns a track_id (either real ByteTrack ID or fallback ID)
            # No need for temporary ID assignment anymore
            vehicle_crop = vehicle_detector.crop(frame, v_det["bbox"])
            if vehicle_crop.size == 0:
                print(f"[pipeline]   Skipping: vehicle_crop.size == 0")
                continue

            track_vehicle_type[track_id] = v_det["vehicle_type"]
            if track_id not in track_first_frame:
                track_first_frame[track_id] = frame_idx

            # keep the highest-confidence vehicle crop for this track as the
            # one we'll use for the appearance embedding later
            if v_det["confidence"] > track_best_crop_conf[track_id]:
                track_best_crop[track_id] = vehicle_crop
                track_best_crop_conf[track_id] = v_det["confidence"]

            # run plate detection WITHIN this vehicle crop, not the whole frame
            plate_dets = plate_detector.detect_on_array(vehicle_crop)
            
            # Filter plate detections using improved scoring mechanism
            vehicle_area = vehicle_crop.shape[0] * vehicle_crop.shape[1]
            scored_dets = []
            
            for p_det in plate_dets:
                x1, y1, x2, y2 = p_det["bbox"]
                bbox_area = (x2 - x1) * (y2 - y1)
                area_ratio = bbox_area / vehicle_area
                confidence = p_det["confidence"]
                
                # Calculate plate aspect ratio (width/height)
                plate_aspect = (x2 - x1) / (y2 - y1) if (y2 - y1) > 0 else 0
                
                # Score calculation matching visual_pipeline.py
                area_score = 1.0 - min(area_ratio, 1.0)
                confidence_score = confidence
                
                if 2.0 <= plate_aspect <= 4.0:
                    aspect_score = 1.0
                elif 1.5 <= plate_aspect <= 5.0:
                    aspect_score = 0.7
                else:
                    aspect_score = 0.3
                
                bbox_width = x2 - x1
                bbox_height = y2 - y1
                if 20 <= bbox_width <= 200 and 10 <= bbox_height <= 100:
                    size_score = 1.0
                elif 10 <= bbox_width <= 300 and 5 <= bbox_height <= 150:
                    size_score = 0.7
                else:
                    size_score = 0.3
                
                total_score = (area_score * 0.3 + confidence_score * 0.4 + 
                              aspect_score * 0.2 + size_score * 0.1)
                
                scored_dets.append({
                    "det": p_det,
                    "score": total_score
                })
            
            if not scored_dets:
                continue
            
            # Sort by total score (descending)
            scored_dets.sort(key=lambda d: d["score"], reverse=True)
            valid_plate_dets = [d["det"] for d in scored_dets]
            
            # Only use the best-scoring plate detection
            if valid_plate_dets:
                p_det = valid_plate_dets[0]
                plate_crop = plate_detector.crop_array(vehicle_crop, p_det["bbox"])
                if plate_crop.size == 0:
                    continue
                text, ocr_conf = ocr.read(plate_crop)
                if text:
                    track_ocr_readings[track_id].append((text, ocr_conf))

    # build one final record per track, using voted plate text + best appearance crop
    records = []
    appearance_vectors = {}

    for track_id, readings in track_ocr_readings.items():
        best_text, best_conf = vote_plate_text(readings)
        if not best_text or len(best_text) < 4:
            continue

        frame_time = base_time + timedelta(seconds=track_first_frame[track_id] / fps_assumed)
        record = make_record(
            text=best_text,
            conf=best_conf,
            cam_id=cam_id,
            lat=lat,
            lng=lng,
            track_id=str(track_id),
            vehicle_type=track_vehicle_type.get(track_id),
            ts=frame_time,
        )

        idx = len(records)
        records.append(record)

        crop = track_best_crop.get(track_id)
        if crop is not None:
            appearance_vectors[idx] = get_appearance_vector(crop)

    return records, appearance_vectors


def run_video_to_db(video_path, vehicle_detector, plate_detector, ocr,
                     cam_id, lat, lng, store, fps_assumed=25, write_annotated=True,
                     on_frame=None, frame_source=None):
    """
    Day 3 Priority 1 fix: run_on_video() only ever returned records in
    memory / wrote outputs/records.json - trajectory/analytics/alerts/
    dashboard all read from the sqlite ObservationStore, which a real video
    run never actually populated (only demo/seed_demo_data.py did). This
    function does the same detection/OCR work as run_on_video(), plus keeps
    the extra per-track provenance (bbox history for direction, best vehicle
    bbox/confidence, first-seen frame index, normalized plate text) and
    writes each finished record straight into `store`.

    Day 4 (SIH26127): Now saves real plate crops to disk and stores plate_crop_path.
    Plate bbox coordinates are converted from vehicle crop space to original frame space.

    SIH26127 pipeline-correctness pass: also records every per-frame vehicle
    and plate detection (frame_vehicle_dets / frame_plate_dets below) as it
    goes, so that after this single real inference pass finishes it can
    hand off to write_annotated_video() for a second, inference-free pass
    that re-decodes the same video and draws the ACTUAL recorded detections
    onto an actual output video file - see that function's docstring for
    why this is a separate pass instead of writing frames while iterating.

    frame_source: SIH26127 real-camera fix (2026-09-15) - optional
    (frame_idx, frame, vehicle_detections)-yielding iterable/generator, the
    exact same shape vehicle_detector.track_video(video_path) yields (see
    network.rtsp_camera.open_camera_frames()'s docstring, which documents
    this contract explicitly). When provided, frames are pulled from this
    instead of vehicle_detector.track_video(video_path) - this is what lets
    a real RTSPS camera's frames (read via the ffmpeg bridge, since
    ultralytics/OpenCV's own stream loader cannot read RTSPS) flow through
    this exact same detection/OCR/fusion/DB-write logic. video_path is
    still required and still used for annotated-video output naming and as
    the record's source label either way. When omitted (every existing
    caller - the recorded-CCTV-upload flow, demo/visual_pipeline.py, a
    plain rtsp:// camera, or a local simulated_video source), behavior is
    completely unchanged.

    Returns (records, annotated_video_path). annotated_video_path is None
    if write_annotated=False or if the annotated video could not be
    produced (e.g. video re-open failed) - callers must handle None rather
    than assuming a video always exists.
    """
    track_ocr_readings = defaultdict(list)
    # SIH26127 "FALSE TRACK MERGE" pass: parallel, same-index-order list of
    # each reading's plate-vs-vehicle relative position - see
    # filter_spatial_outlier_readings() above for why this exists.
    track_plate_positions = defaultdict(list)
    # SIH26127 "FALSE TRACK MERGE" pass (track154 follow-up): the spatial-
    # outlier filter above fixes the VOTED TEXT, but the "best" plate crop
    # image/bbox saved for display (track_best_plate_crop_path / plate_bbox
    # on the record) was picked independently, purely by raw per-frame OCR
    # confidence - a real, confirmed gap: on track154, the contaminating
    # reading from the adjacent red car had the highest single-frame
    # confidence (0.97) of ANY reading on the track, so the saved crop and
    # plate_bbox were the red car's own plate, even after the voted text was
    # already correctly fixed to come from the silver car's own readings.
    # This same-index-order list (aligned with track_ocr_readings /
    # track_plate_positions) keeps what's needed to pick the best crop AFTER
    # the same spatial-outlier mask is known, instead of during the frame
    # loop before it can be computed.
    track_reading_plate_meta = defaultdict(list)
    track_best_crop = {}
    track_best_crop_conf = defaultdict(float)
    track_best_bbox = {}
    track_vehicle_type = {}
    track_first_frame = {}
    track_last_frame = {}
    track_bbox_history = defaultdict(list)
    track_best_plate_bbox = {}
    track_best_plate_crop = {}  # Day 4: store best plate crop
    track_best_plate_crop_path = {}  # Day 4: store plate crop path
    track_best_plate_confidence = {}  # plate DETECTOR confidence (p_det["confidence"]),
                                       # distinct from ocr_confidence (OCR text-reading
                                       # confidence) - the detector score was already being
                                       # computed below and discarded; this just keeps it.

    # Priority 3 perf bookkeeping (see OCR_* constants above) - per-track
    # count of plate-crop opportunities seen so far, and the set of tracks
    # whose OCR result is already stable/confident enough to stop reading.
    track_plate_attempt_count = defaultdict(int)
    track_ocr_stopped = set()
    track_ocr_calls_made = defaultdict(int)  # for the perf log at the end
    track_plate_opportunities = defaultdict(int)

    # SIH26127 "Adaptive Multi-Frame ANPR Intelligence" evidence: per-track
    # list of per-reading quality/preprocessing metadata, parallel to
    # track_ocr_readings (same index order) - used to build the
    # evidence/explainability structure attached to each finished record.
    track_ocr_evidence = defaultdict(list)  # [{"quality_score","preprocessing_mode","blur_score","brightness","contrast","frame_idx"}]

    # Per-frame detection log, used only to build the annotated output
    # video after this pass finishes. Small (bbox + a few scalars per
    # detection), never holds frame image data.
    frame_vehicle_dets = defaultdict(list)   # frame_idx -> [{"track_id","bbox","vehicle_type","confidence"}]
    frame_plate_dets = defaultdict(dict)     # frame_idx -> {track_id: {"bbox","raw_text","ocr_conf","has_ocr"}}

    # Day 4: Create plate crops directory
    plate_crops_dir = str(RESULTS_DIR / "plate_crops")
    os.makedirs(plate_crops_dir, exist_ok=True)

    base_time = datetime.now()

    # SIH26127 real-camera fix: use the caller-supplied frame source (the
    # real RTSPS ffmpeg bridge, for a camera that needs it) when given,
    # otherwise fall back to the existing, unchanged behavior - see
    # frame_source's docstring entry above for the full contract.
    _frames = frame_source if frame_source is not None else vehicle_detector.track_video(video_path)

    for frame_idx, frame, vehicle_dets in _frames:
        for v_det in vehicle_dets:
            track_id = v_det.get("track_id")
            # The detector now always returns a track_id (either real ByteTrack ID or fallback ID)
            # No need for temporary ID assignment anymore
            vehicle_crop = vehicle_detector.crop(frame, v_det["bbox"])
            if vehicle_crop is None or vehicle_crop.size == 0:
                continue

            track_vehicle_type[track_id] = v_det["vehicle_type"]
            if track_id not in track_first_frame:
                track_first_frame[track_id] = frame_idx
            track_last_frame[track_id] = frame_idx
            track_bbox_history[track_id].append(v_det["bbox"])

            frame_vehicle_dets[frame_idx].append({
                "track_id": track_id,
                "bbox": v_det["bbox"],
                "vehicle_type": v_det["vehicle_type"],
                "confidence": v_det["confidence"],
            })

            if v_det["confidence"] > track_best_crop_conf[track_id]:
                track_best_crop[track_id] = vehicle_crop
                track_best_crop_conf[track_id] = v_det["confidence"]
                track_best_bbox[track_id] = v_det["bbox"]

            plate_dets = plate_detector.detect_on_array(vehicle_crop)
            
            # Filter plate detections using improved scoring mechanism
            vehicle_area = vehicle_crop.shape[0] * vehicle_crop.shape[1]
            scored_dets = []
            
            for p_det in plate_dets:
                x1, y1, x2, y2 = p_det["bbox"]
                bbox_area = (x2 - x1) * (y2 - y1)
                area_ratio = bbox_area / vehicle_area
                confidence = p_det["confidence"]
                
                # Calculate plate aspect ratio (width/height)
                plate_aspect = (x2 - x1) / (y2 - y1) if (y2 - y1) > 0 else 0
                
                # Score calculation matching visual_pipeline.py
                area_score = 1.0 - min(area_ratio, 1.0)
                confidence_score = confidence
                
                if 2.0 <= plate_aspect <= 4.0:
                    aspect_score = 1.0
                elif 1.5 <= plate_aspect <= 5.0:
                    aspect_score = 0.7
                else:
                    aspect_score = 0.3
                
                bbox_width = x2 - x1
                bbox_height = y2 - y1
                if 20 <= bbox_width <= 200 and 10 <= bbox_height <= 100:
                    size_score = 1.0
                elif 10 <= bbox_width <= 300 and 5 <= bbox_height <= 150:
                    size_score = 0.7
                else:
                    size_score = 0.3
                
                total_score = (area_score * 0.3 + confidence_score * 0.4 + 
                              aspect_score * 0.2 + size_score * 0.1)
                
                scored_dets.append({
                    "det": p_det,
                    "score": total_score
                })
            
            if not scored_dets:
                continue
            
            # Sort by total score (descending)
            scored_dets.sort(key=lambda d: d["score"], reverse=True)
            valid_plate_dets = [d["det"] for d in scored_dets]
            
            # Only use the best-scoring plate detection
            if valid_plate_dets:
                p_det = valid_plate_dets[0]
                # Convert plate bbox from vehicle crop to frame coordinates FIRST
                vx1, vy1, vx2, vy2 = v_det["bbox"]
                px1, py1, px2, py2 = p_det["bbox"]
                plate_bbox_frame = [vx1 + px1, vy1 + py1, vx1 + px2, vy1 + py2]
                # Small contextual padding to compensate for the plate
                # detector's own box sometimes clipping a leading/trailing
                # character - see PLATE_CROP_PAD_RATIO / _pad_plate_bbox above.
                frame_h, frame_w = frame.shape[:2]
                plate_bbox_frame = _pad_plate_bbox(plate_bbox_frame, frame_w, frame_h)
                
                # Crop from ORIGINAL frame using frame-space coordinates
                plate_crop = plate_detector.crop_array(frame, plate_bbox_frame)
                if plate_crop is None or plate_crop.size == 0:
                    continue
                
                # Handle OCR None gracefully - don't skip the vehicle, just don't read text
                if ocr is not None:
                    track_plate_opportunities[track_id] += 1
                    attempt_num = track_plate_attempt_count[track_id]
                    track_plate_attempt_count[track_id] += 1

                    # Priority 3: decide whether to actually spend an OCR
                    # call on this frame's crop, or skip it (sampling /
                    # early-stop) - see OCR_* constants for rationale.
                    should_run_ocr = (
                        track_id not in track_ocr_stopped
                        and attempt_num % OCR_SAMPLE_INTERVAL == 0
                    )

                    if should_run_ocr:
                        track_ocr_calls_made[track_id] += 1
                        text, ocr_conf, ocr_debug = ocr.read(plate_crop, return_debug=True)
                        frame_plate_dets[frame_idx][track_id] = {
                            "bbox": plate_bbox_frame, "raw_text": text,
                            "ocr_conf": ocr_conf, "has_ocr": True,
                        }
                        if text:
                            track_ocr_readings[track_id].append((text, ocr_conf))
                            track_plate_positions[track_id].append(
                                _plate_relative_position(plate_bbox_frame, v_det["bbox"])
                            )
                            # SIH26127 "FALSE TRACK MERGE" pass (track154
                            # follow-up): same-index-order metadata needed to
                            # re-pick the best CROP/BBOX after the frame loop,
                            # from only the non-spatial-outlier readings - see
                            # track_reading_plate_meta declaration above.
                            track_reading_plate_meta[track_id].append({
                                "plate_crop": plate_crop.copy(),
                                "plate_bbox_frame": plate_bbox_frame,
                                "ocr_conf": ocr_conf,
                                "plate_detector_confidence": p_det["confidence"],
                                "frame_idx": frame_idx,
                            })
                            _q = ocr_debug.get("quality") or {}
                            track_ocr_evidence[track_id].append({
                                "frame_idx": frame_idx,
                                "text": text,
                                "confidence": ocr_conf,
                                "preprocessing_mode": ocr_debug.get("preprocessing_mode"),
                                "ocr_candidate_count": ocr_debug.get("ocr_candidate_count"),
                                "quality_score": _q.get("quality_score"),
                                "blur_score": _q.get("blur_score"),
                                "brightness": _q.get("brightness"),
                                "contrast": _q.get("contrast"),
                            })
                            # keep the plate bbox tied to whichever reading ends up
                            # winning the vote isn't tracked per-reading here - as a
                            # reasonable proxy, keep the bbox from the highest
                            # single-frame OCR confidence seen for this track
                            if track_id not in track_best_plate_bbox or ocr_conf > track_best_plate_bbox[track_id][1]:
                                track_best_plate_bbox[track_id] = (plate_bbox_frame, ocr_conf)
                                track_best_plate_crop[track_id] = plate_crop
                                track_best_plate_confidence[track_id] = p_det["confidence"]

                                # Save plate crop to disk with unique filename
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                                plate_crop_filename = f"{cam_id}_frame{frame_idx}_track{track_id}_{timestamp}.jpg"
                                plate_crop_path = os.path.join(plate_crops_dir, plate_crop_filename)
                                cv2.imwrite(plate_crop_path, plate_crop)
                                track_best_plate_crop_path[track_id] = plate_crop_path

                            # Early stop: once this track already has a
                            # stable, confident voted result, further OCR
                            # calls on the same plate add no information.
                            if (
                                track_id not in track_ocr_stopped
                                and len(track_ocr_readings[track_id]) >= OCR_EARLY_STOP_MIN_READINGS
                            ):
                                _early_text, _early_conf = vote_plate_text(track_ocr_readings[track_id])
                                if _early_text and _early_conf >= OCR_EARLY_STOP_CONFIDENCE:
                                    track_ocr_stopped.add(track_id)
                    else:
                        # Deliberately skipped this frame's OCR call
                        # (sampling or early-stop) - still record that a
                        # plate box exists here, honestly marked as not
                        # read, never fabricated as a real OCR attempt.
                        frame_plate_dets[frame_idx][track_id] = {
                            "bbox": plate_bbox_frame, "raw_text": None,
                            "ocr_conf": None, "has_ocr": False,
                        }
                        # first plate crop seen for a track that never gets
                        # an OCR reading (e.g. very short-lived track) still
                        # needs a saved crop so plate_crop_path isn't empty
                        if track_id not in track_best_plate_crop_path:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                            plate_crop_filename = f"{cam_id}_frame{frame_idx}_track{track_id}_{timestamp}.jpg"
                            plate_crop_path = os.path.join(plate_crops_dir, plate_crop_filename)
                            cv2.imwrite(plate_crop_path, plate_crop)
                            track_best_plate_crop_path[track_id] = plate_crop_path
                            track_best_plate_bbox.setdefault(track_id, (plate_bbox_frame, 0.0))
                            track_best_plate_crop.setdefault(track_id, plate_crop)
                            track_best_plate_confidence.setdefault(track_id, p_det["confidence"])
                else:
                    # OCR unavailable but plate detected - record plate bbox without OCR text
                    frame_plate_dets[frame_idx][track_id] = {
                        "bbox": plate_bbox_frame, "raw_text": None,
                        "ocr_conf": None, "has_ocr": False,
                    }
                    if track_id not in track_best_plate_bbox:
                        track_best_plate_bbox[track_id] = (plate_bbox_frame, 0.0)
                        track_best_plate_crop[track_id] = plate_crop
                        track_best_plate_confidence[track_id] = p_det["confidence"]

                        # Save plate crop to disk even without OCR
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        plate_crop_filename = f"{cam_id}_frame{frame_idx}_track{track_id}_{timestamp}.jpg"
                        plate_crop_path = os.path.join(plate_crops_dir, plate_crop_filename)
                        cv2.imwrite(plate_crop_path, plate_crop)
                        track_best_plate_crop_path[track_id] = plate_crop_path

        # SIH26127 "real video streaming" priority: optional per-frame
        # callback, invoked once per processed frame with exactly the
        # data already computed for this frame above (frame_vehicle_dets/
        # frame_plate_dets) - nothing new is computed for this, it's a
        # live view into the same real inference this function always
        # does, not a separate/duplicated pass. A live "best guess so
        # far" plate text per track is included via a cheap partial vote
        # over readings seen up to this frame - genuinely partial/live,
        # not the final temporally-fused value (that only exists after
        # the whole track finishes, below). If on_frame returns False
        # (e.g. the streaming client disconnected), processing stops
        # early rather than continuing to burn GPU/CPU on a run nobody
        # is watching; whatever tracks/records exist so far are still
        # finalized normally after the loop.
        if on_frame is not None:
            _live_vehicles = []
            for _v in frame_vehicle_dets.get(frame_idx, []):
                _tid = _v["track_id"]
                _live_plate = None
                if track_ocr_readings.get(_tid):
                    _live_plate, _live_conf = vote_plate_text(track_ocr_readings[_tid])
                else:
                    _live_conf = 0.0
                _live_vehicles.append({
                    "track_id": _tid,
                    "bbox": _v["bbox"],
                    "vehicle_type": _v["vehicle_type"],
                    "confidence": _v["confidence"],
                    "plate_bbox": (frame_plate_dets.get(frame_idx, {}).get(_tid) or {}).get("bbox"),
                    "plate_text_live": _live_plate,
                    "plate_confidence_live": round(_live_conf, 3) if _live_plate else None,
                })
            _elapsed = (datetime.now() - base_time).total_seconds()
            _cont = on_frame(frame_idx, frame, _live_vehicles, _elapsed)
            if _cont is False:
                break

    records = []
    pending_writes = []  # (record, appearance_vector) - see link_plate_continuity() call below

    # Create records for ALL tracked vehicles, not just those with OCR readings
    # This ensures vehicles are recorded even when OCR is unavailable
    for track_id in track_vehicle_type.keys():
        # Only proceed if we have at least a vehicle detection for this track
        if track_id not in track_best_bbox:
            continue
            
        # Handle OCR readings if available
        if track_id in track_ocr_readings and track_ocr_readings[track_id]:
            # SIH26127 "FALSE TRACK MERGE" pass: drop any reading whose plate
            # position is a spatial outlier relative to this track's own
            # established plate position BEFORE voting on the text - see
            # filter_spatial_outlier_readings() above. Conservative by design:
            # a track with consistent plate positioning (the overwhelming
            # majority) is completely unaffected.
            _readings_for_vote = filter_spatial_outlier_readings(
                track_ocr_readings[track_id], track_plate_positions[track_id]
            )

            # SIH26127 "FALSE TRACK MERGE" pass (track154 follow-up): the
            # filter above fixes the VOTED TEXT, but track_best_plate_bbox /
            # track_best_plate_crop_path were picked in real time during the
            # frame loop purely by raw per-frame OCR confidence, with no
            # spatial check - confirmed on track154 to independently pick a
            # contaminating, adjacent-vehicle reading (it had the single
            # highest confidence of any reading on the track) even after the
            # text vote itself was already correctly fixed. Re-pick here from
            # only the same non-outlier indices used for the text vote, so
            # the saved crop/bbox always matches the evidence the voted text
            # actually came from.
            _plate_mask = _spatial_outlier_keep_mask(track_plate_positions[track_id])
            _meta_list = track_reading_plate_meta.get(track_id, [])
            if _meta_list and len(_meta_list) == len(_plate_mask):
                _candidates = [m for m, keep in zip(_meta_list, _plate_mask) if keep]
                if not _candidates:
                    _candidates = _meta_list  # defensive: never end up with nothing
                _best_meta = max(_candidates, key=lambda m: m["ocr_conf"])
                _current_best_bbox = track_best_plate_bbox.get(track_id, (None, None))[0]
                if _best_meta["plate_bbox_frame"] != _current_best_bbox:
                    _ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    _fname = f"{cam_id}_frame{_best_meta['frame_idx']}_track{track_id}_{_ts}.jpg"
                    _path = os.path.join(plate_crops_dir, _fname)
                    cv2.imwrite(_path, _best_meta["plate_crop"])
                    track_best_plate_bbox[track_id] = (_best_meta["plate_bbox_frame"], _best_meta["ocr_conf"])
                    track_best_plate_crop[track_id] = _best_meta["plate_crop"]
                    track_best_plate_crop_path[track_id] = _path
                    track_best_plate_confidence[track_id] = _best_meta["plate_detector_confidence"]

            best_text, best_conf, vote_evidence = vote_plate_text(
                _readings_for_vote, return_evidence=True
            )
            if best_text and len(best_text) >= 4:
                # Use Indian plate normalizer for proper IND handling BEFORE creating record
                normalized_plate, pattern_matched = normalize_indian_plate(best_text)
                # SIH26127 bug fix (2026-09-15, verified against a real CAM_01
                # run): pattern_matched was computed above but never checked
                # before this used to unconditionally accept ANY OCR text as
                # a real plate, regardless of whether it actually matched a
                # real Indian plate shape (SSDDL[LL]NNNN). Confirmed live:
                # the plate detector locking onto CAM_01's own on-screen
                # timestamp overlay and OCR reading it as "IS09Z0261" was
                # being recorded as a normal recognized plate. raw_text is
                # still kept either way (never hidden - useful for
                # debugging what OCR actually saw); only the fields callers
                # treat as a trustworthy plate number are gated now.
                record_text = normalized_plate if pattern_matched else None
                record_conf = best_conf if pattern_matched else 0.0
                raw_text = best_text
                ocr_conf = best_conf
            else:
                # OCR failed or text too short
                record_text = None
                record_conf = 0.0
                raw_text = None
                ocr_conf = 0.0
        else:
            # No OCR readings (OCR unavailable or no plate detected)
            record_text = None
            record_conf = 0.0
            raw_text = None
            ocr_conf = 0.0
            vote_evidence = {}

        # SIH26127 "Plate Quality-Aware Processing" / explainability:
        # aggregate the real per-reading quality/preprocessing metadata
        # collected during the frame loop into per-track summary fields -
        # never invented, just summarized from what OCR actually saw.
        quality_readings = track_ocr_evidence.get(track_id, [])
        if quality_readings:
            _scores = [q["quality_score"] for q in quality_readings if q.get("quality_score") is not None]
            avg_plate_quality_score = round(sum(_scores) / len(_scores), 3) if _scores else None
            _blur = [q["blur_score"] for q in quality_readings if q.get("blur_score") is not None]
            avg_blur_score = round(sum(_blur) / len(_blur), 2) if _blur else None
            _bright = [q["brightness"] for q in quality_readings if q.get("brightness") is not None]
            avg_brightness_score = round(sum(_bright) / len(_bright), 2) if _bright else None
            _contrast = [q["contrast"] for q in quality_readings if q.get("contrast") is not None]
            avg_contrast_score = round(sum(_contrast) / len(_contrast), 2) if _contrast else None
            # most-used preprocessing variant across this track's readings -
            # "which strategy was selected", not a per-frame log (that full
            # log is available via track_ocr_evidence for anyone building a
            # richer per-frame evidence view; see docs/OCR_EVALUATION.md).
            _mode_counts = defaultdict(int)
            for q in quality_readings:
                if q.get("preprocessing_mode"):
                    _mode_counts[q["preprocessing_mode"]] += 1
            dominant_preprocessing_mode = max(_mode_counts, key=_mode_counts.get) if _mode_counts else None
            ocr_candidate_count = sum(q.get("ocr_candidate_count") or 0 for q in quality_readings)
        else:
            avg_plate_quality_score = None
            avg_blur_score = None
            avg_brightness_score = None
            avg_contrast_score = None
            dominant_preprocessing_mode = None
            ocr_candidate_count = 0

        frame_time = base_time + timedelta(seconds=track_first_frame[track_id] / fps_assumed)
        record = make_record(
            text=record_text or "unavailable",  # Use normalized text (without IND) as main plate_text
            conf=record_conf,
            cam_id=cam_id,
            lat=lat,
            lng=lng,
            track_id=str(track_id),
            vehicle_type=track_vehicle_type.get(track_id),
            ts=frame_time,
        )

        record["normalized_plate"] = record_text  # Store normalized text (without IND)
        record["raw_plate_text"] = raw_text  # Store raw OCR output for debugging
        record["ocr_confidence"] = ocr_conf  # Store OCR confidence
        record["source"] = _safe_source_label(video_path)
        record["frame_index"] = track_first_frame[track_id]
        record["vehicle_confidence"] = track_best_crop_conf.get(track_id)
        record["vehicle_bbox"] = track_best_bbox.get(track_id)
        plate_bbox_entry = track_best_plate_bbox.get(track_id)
        record["plate_bbox"] = plate_bbox_entry[0] if plate_bbox_entry else None
        record["plate_confidence"] = track_best_plate_confidence.get(track_id)  # plate DETECTOR confidence, distinct from ocr_confidence
        record["plate_crop_path"] = track_best_plate_crop_path.get(track_id)  # Day 4
        record["direction"] = estimate_direction(track_bbox_history.get(track_id, []))
        record["data_source"] = "REAL_INFERENCE"  # SIH Requirement: Data source tagging

        # Temporal span (SIH26127 requirement #11: First Seen / Last Seen
        # in the detection results table) - real frame indices/timestamps
        # from this track's actual detections, not estimates.
        first_frame = track_first_frame[track_id]
        last_frame = track_last_frame.get(track_id, first_frame)
        record["first_seen_frame"] = first_frame
        record["last_seen_frame"] = last_frame
        record["first_seen_timestamp"] = (base_time + timedelta(seconds=first_frame / fps_assumed)).isoformat()
        record["last_seen_timestamp"] = (base_time + timedelta(seconds=last_frame / fps_assumed)).isoformat()
        # Real first/last bbox for this track (not the best-confidence bbox
        # above) - needed for plate-assisted continuity's spatial-proximity
        # check (link_plate_continuity() below): where was this vehicle
        # when the track STARTED and ENDED, not where it looked clearest.
        _bbox_hist = track_bbox_history.get(track_id, [])
        record["first_seen_bbox"] = _bbox_hist[0] if _bbox_hist else None
        record["last_seen_bbox"] = _bbox_hist[-1] if _bbox_hist else None

        # Honest confidence tiering (SIH26127 requirement #6: never present
        # a low-confidence OCR read as a final fact) - shared logic with
        # the annotated video writer below via _plate_status_for_track().
        record["plate_status"] = _plate_status_for_track(
            ocr_available=ocr is not None,
            has_plate_bbox=plate_bbox_entry is not None,
            record_text=record_text,
            ocr_conf=ocr_conf,
        )

        # "Adaptive Multi-Frame ANPR Intelligence" evidence fields - real
        # measured quality/preprocessing/temporal-fusion data, not
        # decorative metadata. temporal_support/final_fusion_score come
        # straight from vote_plate_text()'s own evidence dict, so the
        # number shown here is exactly what the vote was based on.
        record["plate_quality_score"] = avg_plate_quality_score
        record["blur_score"] = avg_blur_score
        record["brightness_score"] = avg_brightness_score
        record["contrast_score"] = avg_contrast_score
        record["preprocessing_mode"] = dominant_preprocessing_mode
        record["ocr_candidate_count"] = ocr_candidate_count
        record["temporal_support"] = vote_evidence.get("num_readings", 0)
        record["final_fusion_score"] = vote_evidence.get("final_confidence")
        record["plate_state"] = _plate_state_for_track(
            plate_status=record["plate_status"],
            temporal_support=vote_evidence.get("num_readings", 0),
            combined_confidence=vote_evidence.get("final_confidence"),
        )

        crop = track_best_crop.get(track_id)
        appearance_vector = get_appearance_vector(crop) if crop is not None else None

        # Not written to `store` yet - link_plate_continuity() below needs
        # the FULL set of this run's records (it looks across track pairs,
        # not just one track at a time), so all writes are deferred until
        # after that pass runs.
        pending_writes.append((record, appearance_vector))
        records.append(record)

    # SIH26127 Priority 2 sub-part: plate-assisted continuity - additive
    # only, never rewrites plate_text/track_id, see link_plate_continuity()
    # docstring. Runs across this run's whole record set, then every
    # record (continuity fields included) is written to the DB once.
    link_plate_continuity(records)
    for record, appearance_vector in pending_writes:
        store.add(record, appearance_vector)

    # Priority 3 perf log: how many OCR calls were actually made vs how
    # many plate-crop opportunities existed, so the sampling/early-stop
    # behavior is visible and auditable in every run, not just claimed.
    total_opportunities = sum(track_plate_opportunities.values())
    total_ocr_calls = sum(track_ocr_calls_made.values())
    if total_opportunities > 0:
        saved_pct = 100.0 * (1 - total_ocr_calls / total_opportunities)
        print(
            f"[pipeline] OCR call reduction: {total_ocr_calls}/{total_opportunities} "
            f"plate-crop opportunities actually OCR'd ({saved_pct:.1f}% calls skipped via "
            f"sampling/early-stop), {len(track_ocr_stopped)} track(s) hit early-stop"
        )

    annotated_video_path = None
    if write_annotated:
        os.makedirs(ANNOTATED_VIDEO_DIR, exist_ok=True)
        video_base = os.path.splitext(os.path.basename(video_path))[0]
        out_name = f"{cam_id}_{video_base}_{int(base_time.timestamp())}_annotated.mp4"
        annotated_video_path = write_annotated_video(
            video_path, cam_id, frame_vehicle_dets, frame_plate_dets,
            output_path=os.path.join(ANNOTATED_VIDEO_DIR, out_name),
        )

    return records, annotated_video_path


def write_annotated_video(video_path, cam_id, frame_vehicle_dets, frame_plate_dets, output_path):
    """
    Second, INFERENCE-FREE pass over the same video: re-decodes every frame
    (cheap - just cv2 decode, no YOLO/OCR) and draws, via the existing
    demo.annotate.annotate_frame() (reused unmodified), exactly the
    detections that were actually recorded for that frame_idx during the
    real detection/tracking/OCR pass in run_video_to_db() above.

    Why a second pass instead of writing frames while detecting: the
    voted/normalized final plate text for a track is only known once its
    OCR readings across the WHOLE video have been aggregated (vote_plate_text
    runs after the loop) - writing frames during the first pass would mean
    either freezing the annotated video's frame order/timing to whatever
    the streaming tracker yields (fine) but showing only whatever partial
    OCR state existed AT that instant. That's exactly what this function
    does anyway (see below) - so the split is really about keeping the
    real inference pass focused on inference, and video-writing (and its
    own failure modes: codec issues, disk space, permissions) fully
    separate and non-fatal to the inference results.

    Every box/label drawn here is frame-true: a vehicle appears only in
    frames it was actually detected in, and a plate box/text appears only
    in the specific frame OCR actually ran and produced (or failed to
    produce) that reading - nothing is extrapolated or replayed into
    frames where it wasn't actually seen.

    Output is re-encoded to H.264 via ffmpeg (when available) so it plays
    directly in a browser <video> tag - OpenCV's own mp4v writer produces
    MPEG-4 Part 2, which most browsers refuse to play natively.

    Returns the final output path, or None if the video could not be
    re-opened, had zero decodable frames, or writing otherwise failed -
    never raises, so a failure here degrades the API response (no
    annotated_video_url) rather than failing the whole ingest request.
    """
    import shutil
    import subprocess
    from demo.annotate import annotate_frame

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        cap.release()
        return None

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    raw_path = output_path + ".raw.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(raw_path, fourcc, fps, (width, height))
    if not writer.isOpened():
        cap.release()
        return None

    frame_idx = 0
    frames_written = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        vehicle_list = frame_vehicle_dets.get(frame_idx, [])
        plate_map = frame_plate_dets.get(frame_idx, {})

        observations = []
        for v in vehicle_list:
            track_id = v["track_id"]
            obs = {
                "vehicle_bbox": v["bbox"],
                "vehicle_class": v["vehicle_type"],
                "vehicle_confidence": v["confidence"],
                "track_id": track_id,
            }
            plate_info = plate_map.get(track_id)
            if plate_info is None:
                obs["plate_status"] = "plate_not_detected"
            elif not plate_info["has_ocr"]:
                obs["plate_bbox"] = plate_info["bbox"]
                obs["plate_status"] = "detected_no_ocr"
            elif plate_info["raw_text"]:
                normalized, _ = normalize_indian_plate(plate_info["raw_text"])
                obs["plate_bbox"] = plate_info["bbox"]
                obs["normalized_plate_text"] = normalized
                obs["ocr_confidence"] = plate_info["ocr_conf"]
                obs["plate_status"] = "detected"
            else:
                obs["plate_bbox"] = plate_info["bbox"]
                obs["plate_status"] = "ocr_failed"
            observations.append(obs)

        annotated = annotate_frame(frame, cam_id, observations, frame_label=f"Frame {frame_idx}")
        writer.write(annotated)
        frames_written += 1
        frame_idx += 1

    cap.release()
    writer.release()

    if frames_written == 0:
        try:
            os.remove(raw_path)
        except OSError:
            pass
        return None

    # Re-encode to H.264 for browser playback. If ffmpeg isn't available or
    # the transcode fails, fall back to serving the raw mp4v file rather
    # than losing the annotated video entirely - it just may not play in
    # every browser (still downloadable/playable in VLC etc.).
    if shutil.which("ffmpeg"):
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", raw_path,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    output_path,
                ],
                check=True,
                timeout=300,
            )
            os.remove(raw_path)
            return output_path
        except Exception:
            # transcode failed - keep the raw file as the deliverable
            try:
                if os.path.isfile(output_path):
                    os.remove(output_path)
                os.rename(raw_path, output_path)
            except OSError:
                return raw_path
            return output_path
    else:
        os.rename(raw_path, output_path)
        return output_path


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--vehicle_weights", default="yolov8n.pt",
                    help="pretrained COCO weights, no fine-tuning needed for vehicle detection")
    p.add_argument("--plate_weights", default=None,
                    help="your fine-tuned plate detector; omit to auto-detect "
                         "via demo.visual_pipeline.find_plate_weights() "
                         "(checks models/best_plate_detector.pt, "
                         "detection/runs/.../best.pt, models/best.onnx, in "
                         "that order)")
    p.add_argument("--camera_id", required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--long", type=float, required=True)
    p.add_argument("--out", default=str(RESULTS_DIR / "records.json"))
    p.add_argument("--to-db", action="store_true", help="write to observation database instead of JSON")
    args = p.parse_args()

    # Use the same plate weight discovery logic as visual_pipeline.py
    # to avoid silently loading a generic YOLO model as a plate detector.
    # If the caller passed --plate_weights explicitly, respect it (but
    # validate it exists); otherwise auto-detect from the same candidate
    # list visual_pipeline.py uses, so a repo with only models/best.onnx
    # (no best_plate_detector.pt) still gets real plate detection instead
    # of silently skipping it.
    from demo.visual_pipeline import find_plate_weights
    plate_weights_path = find_plate_weights(explicit_path=args.plate_weights)
    if args.plate_weights and plate_weights_path is None:
        print(f"[pipeline] WARNING: Specified plate weights not found: {args.plate_weights}")
    
    vehicle_detector = VehicleDetector(model_path=args.vehicle_weights)
    plate_detector = PlateDetector(weights=plate_weights_path) if plate_weights_path else None
    ocr = try_init_ocr() if plate_detector is not None else None
    
    if plate_detector is None:
        print("[pipeline] WARNING: No valid plate detector weights found - "
              "plate detection will be skipped. Vehicle detection will continue.")
    elif ocr is None:
        print("[pipeline] WARNING: Plate detector is configured but OCR failed to "
              "initialize - plate boxes will still be detected, but plate text "
              "will be reported as unavailable this run.")

    if args.to_db:
        from database.observation_store import ObservationStore
        store = ObservationStore()
        records, annotated_video_path = run_video_to_db(
            args.video, vehicle_detector, plate_detector, ocr,
            args.camera_id, args.lat, args.long, store,
        )
        store.close()
        print(f"got {len(records)} vehicle records (written to database)")
        for r in records:
            print(r)
        print(f"annotated output video: {annotated_video_path or 'NOT PRODUCED'}")
    else:
        records, appearance_vectors = run_on_video(
            args.video, vehicle_detector, plate_detector, ocr,
            args.camera_id, args.lat, args.long,
        )

        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(records, f, indent=2)

        print(f"got {len(records)} vehicle records (deduplicated via tracking), saved to {args.out}")
        for r in records:
            print(r)
