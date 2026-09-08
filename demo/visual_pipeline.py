"""
demo/visual_pipeline.py

DAY 1 — Phase 1: the real visual input layer.

    local images/video per camera (data/cameras/<CAM_ID>/...)
      -> camera simulation          (demo.camera_simulator)     [NEW]
      -> vehicle detection          (detection.vehicle_detector.VehicleDetector) [REUSED, untouched]
      -> plate detection            (detection.detect_plates.PlateDetector)      [REUSED, untouched -
                                      only invoked if a REAL trained weights
                                      file is found, see find_plate_weights()]
      -> OCR                        (recognition.ocr_reader.PlateOCR)           [REUSED, untouched]
      -> Indian plate normalization (recognition.plate_normalizer)  [NEW, conservative]
      -> structured observation result, ONE FLAT RECORD PER VEHICLE  [NEW]
      -> annotated frame            (demo.annotate)                [NEW]

Deliberately NOT wired in (per the Day-1 brief): trajectory, fusion,
database, analytics, gis, dashboard. Deliberately NOT Phase 2: RTSP,
Kafka, cloud, auth, prediction, chatbot.

STRUCTURED OUTPUT SCHEMA - one flat dict per detected vehicle, chosen to
line up with database.observation_store.ObservationStore's existing
columns (plate_text/confidence/camera_id/timestamp/track_id/vehicle_type)
so Day 2 can map straight into it without restructuring:

    camera_id, timestamp, source_file, source_type, frame_index,
    vehicle_bbox, vehicle_class, vehicle_confidence, track_id,
    plate_bbox, raw_plate_text, normalized_plate_text, ocr_confidence,
    plate_status, plate_status_reason, annotated_output, appearance_vector

DAY 2 UPDATE: this module now DOES write into ObservationStore (the
missing bridge to outputs/results/observations.db) and now computes
appearance_vector from the real VEHICLE crop (recognition.appearance -
previously only ever run on the much less informative plate crop,
per that module's own documented limitation). Both are additive: the
JSON dump (outputs/results/<CAM>_visual_results.json) and everything
about Day 1's detection/OCR path are unchanged.

Run:
    python -m demo.visual_pipeline --camera CAM_01
    python -m demo.visual_pipeline --camera CAM_01 --frame-sample 3
    python -m demo.visual_pipeline --camera CAM_01 --no-db   # JSON only, skip the database write

First-time setup (creates the data/cameras/CAM_0X/{images,videos} folders):
    python -m demo.visual_pipeline --setup-dirs
"""
import argparse
import glob
import json
import os
from datetime import datetime

import cv2

from detection.vehicle_detector import VehicleDetector
from detection.detect_plates import PlateDetector
from recognition.ocr_reader import try_init_ocr
from recognition.plate_normalizer import normalize_indian_plate
from recognition.appearance import get_appearance_vector

from demo.camera_simulator import get_camera_feed, sample_frame_indices, ensure_camera_dirs, CameraFeedNotFound
from demo.annotate import annotate_frame
from config import PROJECT_ROOT, RESULTS_DIR as CONFIG_RESULTS_DIR, DB_PATH_STR

ANNOTATED_DIR = str(CONFIG_RESULTS_DIR / "annotated")
RESULTS_DIR = str(CONFIG_RESULTS_DIR)
PLATE_CROPS_DIR = str(CONFIG_RESULTS_DIR / "plate_crops")

# Candidate locations for a REAL trained plate-detector checkpoint.
# Deliberately never defaults to a stock COCO checkpoint (e.g. yolov8n.pt)
# here - COCO has no license-plate class, so using it as the plate
# detector would silently fabricate "plate" boxes that are actually
# random COCO objects. If none of these exist, plate detection is
# reported as unavailable rather than faked.
PLATE_WEIGHT_CANDIDATES = [
    str(PROJECT_ROOT / "models" / "best_plate_detector.pt"),
    str(PROJECT_ROOT / "models" / "plate_detector.pt"),
    str(PROJECT_ROOT / "models" / "best.pt"),
    str(PROJECT_ROOT / "detection" / "runs" / "detect" / "plate_train" / "weights" / "best.pt"),
    # ONNX export - ultralytics.YOLO() loads this directly via ONNX Runtime.
    # Listed last so a real .pt (fine-tunable, usually more current) wins if
    # both exist; this is the one weight file actually present as of
    # 2026-09-07 (best_plate_detector.pt is referenced throughout the repo's
    # docs/config but is not on disk - see docs/CLAUDE_PHASE0_AUDIT.md).
    str(PROJECT_ROOT / "models" / "best.onnx"),
]

_NO_PLATE_FIELDS = {
    "plate_bbox": None,
    "raw_plate_text": None,
    "normalized_plate_text": None,
    "ocr_confidence": None,
    "data_source": "REAL_INFERENCE",  # SIH Requirement: Data source tagging
}


def find_plate_weights(explicit_path=None):
    """Returns a path to a real plate-detector checkpoint, or None if none exists."""
    if explicit_path:
        return explicit_path if os.path.isfile(explicit_path) else None
    for c in PLATE_WEIGHT_CANDIDATES:
        if os.path.isfile(c):
            return c
    for c in sorted(glob.glob(str(PROJECT_ROOT / "detection" / "runs" / "**" / "weights" / "best.pt"), recursive=True)):
        return c
    return None


def build_plate_fields(vehicle_crop, plate_detector, ocr, vehicle_bbox, camera_id, 
                        frame_index, source_file, original_frame, track_id=None):
    """
    Returns the plate_* fields (see module docstring schema) for ONE
    vehicle crop. plate_detector may be None (no real weights found) -
    in that case plate_status="unavailable" is reported, never a
    fabricated detection. ocr may ALSO be None (PaddleOCR failed to
    initialize, see recognition.ocr_reader.try_init_ocr) - that is a
    separate, distinguishable "unavailable" reason from missing plate
    weights, so a caller/judge can tell which component is actually
    missing.

    Day 4 (SIH26127): Now saves real plate crop to disk and returns plate_crop_path.
    Plate bbox coordinates are converted from vehicle crop space to original frame space.
    The plate crop is created from the ORIGINAL frame using frame-space coordinates.
    """
    if plate_detector is None:
        return {
            **_NO_PLATE_FIELDS,
            "plate_status": "unavailable",
            "plate_status_reason": (
                "no trained plate-detector weights found - integration point is wired, "
                "just needs a real fine-tuned model at one of: " + ", ".join(PLATE_WEIGHT_CANDIDATES)
            ),
        }

    plate_dets = plate_detector.detect_on_array(vehicle_crop)
    if not plate_dets:
        return {**_NO_PLATE_FIELDS, "plate_status": "plate_not_detected", "plate_status_reason": None}

    # Select the best plate detection using a scoring mechanism
    vehicle_area = vehicle_crop.shape[0] * vehicle_crop.shape[1]
    scored_dets = []
    
    for det in plate_dets:
        x1, y1, x2, y2 = det["bbox"]
        bbox_area = (x2 - x1) * (y2 - y1)
        area_ratio = bbox_area / vehicle_area
        confidence = det["confidence"]
        
        # Calculate plate aspect ratio (width/height)
        plate_aspect = (x2 - x1) / (y2 - y1) if (y2 - y1) > 0 else 0
        
        # Score calculation:
        # - Prefer smaller area ratios (actual plates vs vehicle)
        # - Prefer higher confidence
        # - Prefer typical plate aspect ratios (2:1 to 4:1 for Indian plates)
        # - Penalize very small or very large boxes
        
        area_score = 1.0 - min(area_ratio, 1.0)  # Smaller area ratio is better
        confidence_score = confidence
        
        # Aspect ratio score: typical plates are 2:1 to 4:1
        if 2.0 <= plate_aspect <= 4.0:
            aspect_score = 1.0
        elif 1.5 <= plate_aspect <= 5.0:
            aspect_score = 0.7
        else:
            aspect_score = 0.3
        
        # Size score: plates should be reasonably sized (not too small)
        bbox_width = x2 - x1
        bbox_height = y2 - y1
        if 20 <= bbox_width <= 200 and 10 <= bbox_height <= 100:
            size_score = 1.0
        elif 10 <= bbox_width <= 300 and 5 <= bbox_height <= 150:
            size_score = 0.7
        else:
            size_score = 0.3
        
        # Combined score (weighted)
        total_score = (area_score * 0.3 + confidence_score * 0.4 + 
                      aspect_score * 0.2 + size_score * 0.1)
        
        scored_dets.append({
            "det": det,
            "score": total_score,
            "area_ratio": area_ratio,
            "aspect": plate_aspect
        })
    
    if not scored_dets:
        return {**_NO_PLATE_FIELDS, "plate_status": "plate_not_detected", "plate_status_reason": None}
    
    # Sort by total score (descending)
    scored_dets.sort(key=lambda d: d["score"], reverse=True)
    best = scored_dets[0]["det"]
    
    # Convert plate bbox from vehicle crop coordinates to original frame coordinates
    vx1, vy1, vx2, vy2 = vehicle_bbox
    px1, py1, px2, py2 = best["bbox"]
    plate_bbox_frame = [vx1 + px1, vy1 + py1, vx1 + px2, vy1 + py2]

    # Crop from ORIGINAL frame using frame-space coordinates
    plate_crop = plate_detector.crop_array(original_frame, plate_bbox_frame)
    if plate_crop is None or plate_crop.size == 0:
        return {
            **_NO_PLATE_FIELDS,
            "plate_bbox": plate_bbox_frame,
            "plate_status": "plate_not_detected",
            "plate_status_reason": None,
        }

    # Save plate crop to disk with unique filename including track_id
    os.makedirs(PLATE_CROPS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    track_suffix = f"_track{track_id}" if track_id is not None else ""
    plate_crop_filename = f"{camera_id}_frame{frame_index}{track_suffix}_{timestamp}.jpg"
    plate_crop_path = os.path.join(PLATE_CROPS_DIR, plate_crop_filename)
    cv2.imwrite(plate_crop_path, plate_crop)

    if ocr is None:
        return {
            "plate_bbox": plate_bbox_frame,  # Frame coordinates
            "plate_crop_path": plate_crop_path,
            "raw_plate_text": None,
            "normalized_plate_text": None,
            "ocr_confidence": None,
            "plate_status": "detected_no_ocr",  # Plate detected but OCR unavailable
            "plate_status_reason": (
                "plate box was detected but the OCR engine failed to initialize "
                "(PaddleOCR could not reach its model CDN or another init error - "
                "see console/log output from try_init_ocr() for the exact cause). "
                "Vehicle detection and the plate location are still real; only the "
                "plate text itself is unavailable this run."
            ),
            "pattern_matched": False,
            "data_source": "REAL_INFERENCE",  # SIH Requirement: Data source tagging
        }

    raw_text, ocr_conf = ocr.read(plate_crop)
    if not raw_text:
        return {
            **_NO_PLATE_FIELDS,
            "plate_bbox": plate_bbox_frame,  # Frame coordinates
            "plate_crop_path": plate_crop_path,
            "plate_status": "ocr_failed",
            "plate_status_reason": "OCR engine ran but produced no text",
        }

    normalized, pattern_matched = normalize_indian_plate(raw_text)
    return {
        "plate_bbox": plate_bbox_frame,  # Frame coordinates, not vehicle crop coordinates
        "raw_plate_text": raw_text,  # Keep original OCR output for debugging
        "normalized_plate_text": normalized,  # Use this for display/matching (without IND)
        "normalized_plate": normalized,  # Also store as normalized_plate for consistency with pipeline
        "ocr_confidence": ocr_conf,
        "plate_crop_path": plate_crop_path,
        "plate_status": "detected",
        "plate_status_reason": None,
        "pattern_matched": pattern_matched,  # bonus field, not in the core schema
        "data_source": "REAL_INFERENCE",  # SIH Requirement: Data source tagging
    }


def _vehicle_observation(v_det, frame, camera_id, source_file, source_type, frame_index,
                          vehicle_detector, plate_detector, ocr, timestamp):
    """Builds ONE flat observation record for one detected vehicle."""
    crop = vehicle_detector.crop(frame, v_det["bbox"])
    if crop is None or crop.size == 0:
        plate_fields = {**_NO_PLATE_FIELDS, "plate_status": "not_found", "plate_status_reason": None}
        appearance_vector = None
    else:
        plate_fields = build_plate_fields(crop, plate_detector, ocr, v_det["bbox"], 
                                          camera_id, frame_index, source_file, 
                                          original_frame=frame, track_id=v_det.get("track_id"))
        # DAY 2: appearance embedding now runs on the VEHICLE crop (this
        # `crop`), not the plate crop - fixes the limitation recognition/
        # appearance.py's own docstring flags ("ideally this embedding
        # should run on the full vehicle bounding box"). get_appearance_vector
        # returns None on an empty/invalid crop rather than raising, so a
        # failure here degrades to "no appearance evidence for this
        # observation" instead of crashing the frame.
        try:
            appearance_vector = get_appearance_vector(crop)
        except Exception:
            appearance_vector = None

    obs = {
        "camera_id": camera_id,
        "timestamp": timestamp,
        "source_file": source_file,
        "source_type": source_type,
        "frame_index": frame_index,
        "vehicle_bbox": v_det["bbox"],
        "vehicle_class": v_det["vehicle_type"],
        "vehicle_confidence": v_det["confidence"],
        "track_id": v_det.get("track_id"),
        "appearance_vector": appearance_vector,
        "source": "real_inference",  # Mark as real AI inference (not synthetic demo data)
        "data_source": "REAL_INFERENCE",  # SIH Requirement: Data source tagging
    }
    obs.update(plate_fields)
    return obs


def process_image(image_path, camera_id, vehicle_detector, plate_detector, ocr):
    """Returns a list of flat vehicle observations (may be empty) for one image."""
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"[demo] could not read image, skipping: {image_path}")
        return []

    ts = datetime.now().isoformat()
    vehicle_dets = vehicle_detector.detect(image_path)
    observations = [
        _vehicle_observation(v, frame, camera_id, image_path, "image", None,
                              vehicle_detector, plate_detector, ocr, ts)
        for v in vehicle_dets
    ]

    # Create separate annotated images for each observation to prevent mismatch
    os.makedirs(ANNOTATED_DIR, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    
    if observations:
        # Create one annotated image per vehicle observation
        for i, obs in enumerate(observations):
            # Annotate frame with only this vehicle's observation
            single_obs_annotated = annotate_frame(frame, camera_id, [obs], 
                                                    frame_label=f"{base_name}_vehicle{i+1}")
            out_name = f"{camera_id}_{base_name}_vehicle{i+1}_annotated.jpg"
            out_path = os.path.join(ANNOTATED_DIR, out_name)
            cv2.imwrite(out_path, single_obs_annotated)
            obs["annotated_output"] = out_path
    else:
        # If no vehicles, create a single annotated frame for the image
        annotated = annotate_frame(frame, camera_id, observations, frame_label=base_name)
        out_name = f"{camera_id}_{base_name}_annotated.jpg"
        out_path = os.path.join(ANNOTATED_DIR, out_name)
        cv2.imwrite(out_path, annotated)
        # No observations to assign path to

    if not observations:
        print(f"[demo] {camera_id}: no vehicles found in {image_path} (annotated frame still saved)")

    return observations


def process_video(video_path, camera_id, vehicle_detector, plate_detector, ocr,
                   frame_sample=5, max_frames=None):
    """
    Frame-by-frame processing via VehicleDetector.track_video(), which is
    already a lazy generator (stream=True under the hood in ultralytics) -
    the whole video is never loaded into memory at once.

    frame_sample: only run plate detection + OCR (the expensive part) on
    every Nth frame (policy lives in demo.camera_simulator.sample_frame_indices).
    max_frames: hard cap for demo/testing speed; None = whole video.

    Returns a flat list of vehicle observations across all sampled frames.
    """
    should_process = sample_frame_indices(frame_sample, max_frames)
    observations = []
    os.makedirs(ANNOTATED_DIR, exist_ok=True)
    video_base = os.path.splitext(os.path.basename(video_path))[0]

    for frame_idx, frame, vehicle_dets in vehicle_detector.track_video(video_path):
        if max_frames is not None and frame_idx >= max_frames:
            break
        if not should_process(frame_idx):
            continue

        ts = datetime.now().isoformat()
        frame_observations = [
            _vehicle_observation(v, frame, camera_id, video_path, "video", frame_idx,
                                  vehicle_detector, plate_detector, ocr, ts)
            for v in vehicle_dets
        ]

        # Create observation-specific annotated images for video frames too
        if frame_observations:
            for i, obs in enumerate(frame_observations):
                single_obs_annotated = annotate_frame(frame, camera_id, [obs],
                    frame_label=f"{video_base}_frame{frame_idx}_vehicle{i+1}")
                out_name = f"{camera_id}_{video_base}_frame{frame_idx}_vehicle{i+1}_annotated.jpg"
                out_path = os.path.join(ANNOTATED_DIR, out_name)
                cv2.imwrite(out_path, single_obs_annotated)
                obs["annotated_output"] = out_path
        else:
            # If no vehicles in this frame, create a single annotated frame
            annotated = annotate_frame(frame, camera_id, frame_observations,
                frame_label=f"{video_base}_frame{frame_idx}")
            out_name = f"{camera_id}_{video_base}_frame{frame_idx}_annotated.jpg"
            out_path = os.path.join(ANNOTATED_DIR, out_name)
            cv2.imwrite(out_path, annotated)

        observations.extend(frame_observations)

    return observations


def run_camera(camera_id, frame_sample=5, max_frames=None, plate_weights=None,
                vehicle_weights=None, write_to_db=True, db_path=None, fresh=False):
    feed = get_camera_feed(camera_id)  # raises CameraFeedNotFound if the camera folder is missing entirely

    if fresh:
        from database.observation_store import ObservationStore
        store = ObservationStore(db_path=db_path or DB_PATH_STR)
        try:
            store.delete_camera_observations(camera_id)
        finally:
            store.close()
        # Remove only generated artifacts for this camera. Source media is never touched.
        for directory in (ANNOTATED_DIR, PLATE_CROPS_DIR):
            if os.path.isdir(directory):
                for name in os.listdir(directory):
                    if name.startswith(f"{camera_id}_"):
                        try:
                            os.remove(os.path.join(directory, name))
                        except OSError:
                            pass
    if not feed.has_media:
        print(f"[demo] {camera_id}: folder exists but has no images/videos yet")

    weights_path = find_plate_weights(plate_weights)
    print(f"[demo] plate detector weights: {weights_path or 'NONE FOUND - plate detection will be skipped'}")

    vehicle_weights = vehicle_weights or str(PROJECT_ROOT / "yolov8n.pt")
    vehicle_detector = VehicleDetector(weights=vehicle_weights)
    plate_detector = PlateDetector(weights=weights_path) if weights_path else None

    # OCR is only ever consumed when a plate box was actually found (see
    # build_plate_fields above), so there is no reason to pay PaddleOCR's
    # (potentially failing) model-download cost when there's no plate
    # detector to feed it in the first place. When a plate detector IS
    # configured, try_init_ocr() still can't crash the run even if OCR
    # itself fails to come up - see its docstring.
    ocr = try_init_ocr() if plate_detector is not None else None
    if plate_detector is not None and ocr is None:
        print(f"[demo] WARNING: plate detector is configured but OCR failed to "
              f"initialize - plate boxes will still be detected, but plate text "
              f"will be reported as unavailable this run.")

    observations = []
    for img_path in feed.images:
        observations.extend(process_image(img_path, camera_id, vehicle_detector, plate_detector, ocr))

    for vid_path in feed.videos:
        observations.extend(
            process_video(vid_path, camera_id, vehicle_detector, plate_detector, ocr,
                           frame_sample=frame_sample, max_frames=max_frames)
        )

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_json = os.path.join(RESULTS_DIR, f"{camera_id}_visual_results.json")
    with open(out_json, "w") as f:
        json.dump(observations, f, indent=2)

    n_written = None
    if write_to_db:
        n_written = write_observations_to_db(observations, db_path=db_path)

    return observations, out_json, weights_path, n_written


def write_observations_to_db(observations, db_path=None):
    """
    THE BRIDGE (Day 2, Task 5): writes every vehicle observation produced by
    this pipeline into the EXISTING ObservationStore/observations.db, using
    ObservationStore.add_visual_observation() (see database/observation_store.py) -
    no second database, no manual SQLite, no bypassing the existing
    abstraction. Every vehicle observation is written, including ones with
    plate_status "not_found"/"unavailable" - a vehicle sighting without a
    readable plate is still real evidence the vehicle was there, and is
    still useful for appearance-based matching / vehicle counts; it is
    never fabricated into a fake plate to make it "count."

    Returns the number of rows written (0 for an empty observations list -
    still a normal, successful call, not an error).
    """
    from database.observation_store import ObservationStore

    store = ObservationStore(db_path=db_path) if db_path else ObservationStore()
    try:
        return store.add_visual_observations(observations)
    finally:
        store.close()


def _summarize(camera_id, observations, out_json, n_written=None):
    n_vehicles = len(observations)
    n_plates_detected = sum(1 for o in observations if o["plate_status"] == "detected")
    n_ocr_reads = sum(1 for o in observations if o.get("raw_plate_text"))
    print(f"[demo] {camera_id}: {n_vehicles} vehicle observation(s)")
    print(f"[demo] {camera_id}: {n_plates_detected} plate box(es) detected, {n_ocr_reads} OCR read(s)")
    print(f"[demo] structured results: {out_json}")
    print(f"[demo] annotated frames dir: {ANNOTATED_DIR}/")
    if n_written is not None:
        print(f"[demo] written to database: {n_written} observation(s) -> outputs/results/observations.db")
    else:
        print("[demo] database write skipped (--no-db)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="TrackX visual input layer (Day 1 detection + Day 2 database bridge)")
    p.add_argument("--camera", help="camera id, e.g. CAM_01")
    p.add_argument("--frame-sample", type=int, default=5, help="process every Nth video frame (default 5)")
    p.add_argument("--max-frames", type=int, default=None, help="cap video frames processed")
    p.add_argument("--plate-weights", default=None, help="path to a REAL trained plate-detector .pt file")
    p.add_argument("--vehicle-weights", default=None, help="pretrained COCO vehicle weights (defaults to project yolov8n.pt)")
    p.add_argument("--fresh", action="store_true",
                   help="replace this camera's generated observations and artifacts before processing")
    p.add_argument("--no-db", action="store_true",
                    help="skip writing to observations.db (JSON output only)")
    p.add_argument("--setup-dirs", action="store_true",
                    help="create data/cameras/CAM_0X/{images,videos} folders and exit")
    args = p.parse_args()

    if args.setup_dirs:
        created = ensure_camera_dirs()
        print(f"[demo] camera folders ready under data/cameras/ ({len(created)} created)")
        raise SystemExit(0)

    if not args.camera:
        p.error("--camera is required (or use --setup-dirs)")

    try:
        observations, out_json, weights_used, n_written = run_camera(
            args.camera,
            frame_sample=args.frame_sample,
            max_frames=args.max_frames,
            plate_weights=args.plate_weights,
            vehicle_weights=args.vehicle_weights,
            write_to_db=not args.no_db,
        )
    except CameraFeedNotFound as e:
        print(f"[demo] {e}")
        raise SystemExit(1)

    _summarize(args.camera, observations, out_json, n_written=n_written)
