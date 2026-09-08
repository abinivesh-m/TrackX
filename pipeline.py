"""
pipeline.py

v2: proper vehicle-first pipeline, fixing the plate-crop-as-appearance
problem flagged in review.

    video -> vehicle detection + tracking (pretrained COCO YOLO)
          -> for each vehicle track: plate detection WITHIN that vehicle crop
          -> OCR each plate reading
          -> group all OCR readings for the same track_id, vote on best text
          -> appearance embedding from the VEHICLE crop (not plate crop)
          -> one final record per track, matching our schema + track_id

this replaces the old "detect plate directly on the whole frame" approach.
detecting the plate inside the vehicle crop first is also more accurate -
less background clutter for the plate detector to get confused by.
"""

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
                     cam_id, lat, lng, store, fps_assumed=25):
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

    Returns the list of records written (same shape as run_on_video's first
    return value, plus the extra fields below), for logging/CLI use.
    """
    track_ocr_readings = defaultdict(list)
    track_best_crop = {}
    track_best_crop_conf = defaultdict(float)
    track_best_bbox = {}
    track_vehicle_type = {}
    track_first_frame = {}
    track_bbox_history = defaultdict(list)
    track_best_plate_bbox = {}
    track_best_plate_crop = {}  # Day 4: store best plate crop
    track_best_plate_crop_path = {}  # Day 4: store plate crop path
    track_best_plate_confidence = {}  # plate DETECTOR confidence (p_det["confidence"]),
                                       # distinct from ocr_confidence (OCR text-reading
                                       # confidence) - the detector score was already being
                                       # computed below and discarded; this just keeps it.

    # Day 4: Create plate crops directory
    plate_crops_dir = str(RESULTS_DIR / "plate_crops")
    os.makedirs(plate_crops_dir, exist_ok=True)

    base_time = datetime.now()

    for frame_idx, frame, vehicle_dets in vehicle_detector.track_video(video_path):
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
            track_bbox_history[track_id].append(v_det["bbox"])

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
                
                # Crop from ORIGINAL frame using frame-space coordinates
                plate_crop = plate_detector.crop_array(frame, plate_bbox_frame)
                if plate_crop is None or plate_crop.size == 0:
                    continue
                
                # Handle OCR None gracefully - don't skip the vehicle, just don't read text
                if ocr is not None:
                    text, ocr_conf = ocr.read(plate_crop)
                    if text:
                        track_ocr_readings[track_id].append((text, ocr_conf))
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
                else:
                    # OCR unavailable but plate detected - record plate bbox without OCR text
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

    records = []

    # Create records for ALL tracked vehicles, not just those with OCR readings
    # This ensures vehicles are recorded even when OCR is unavailable
    for track_id in track_vehicle_type.keys():
        # Only proceed if we have at least a vehicle detection for this track
        if track_id not in track_best_bbox:
            continue
            
        # Handle OCR readings if available
        if track_id in track_ocr_readings and track_ocr_readings[track_id]:
            best_text, best_conf = vote_plate_text(track_ocr_readings[track_id])
            if best_text and len(best_text) >= 4:
                # Use Indian plate normalizer for proper IND handling BEFORE creating record
                normalized_plate, pattern_matched = normalize_indian_plate(best_text)
                record_text = normalized_plate
                record_conf = best_conf
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
        record["source"] = video_path
        record["frame_index"] = track_first_frame[track_id]
        record["vehicle_confidence"] = track_best_crop_conf.get(track_id)
        record["vehicle_bbox"] = track_best_bbox.get(track_id)
        plate_bbox_entry = track_best_plate_bbox.get(track_id)
        record["plate_bbox"] = plate_bbox_entry[0] if plate_bbox_entry else None
        record["plate_confidence"] = track_best_plate_confidence.get(track_id)  # plate DETECTOR confidence, distinct from ocr_confidence
        record["plate_crop_path"] = track_best_plate_crop_path.get(track_id)  # Day 4
        record["direction"] = estimate_direction(track_bbox_history.get(track_id, []))
        record["data_source"] = "REAL_INFERENCE"  # SIH Requirement: Data source tagging

        crop = track_best_crop.get(track_id)
        appearance_vector = get_appearance_vector(crop) if crop is not None else None

        store.add(record, appearance_vector)
        records.append(record)

    return records


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
        records = run_video_to_db(
            args.video, vehicle_detector, plate_detector, ocr,
            args.camera_id, args.lat, args.long, store,
        )
        store.close()
        print(f"got {len(records)} vehicle records (written to database)")
        for r in records:
            print(r)
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
