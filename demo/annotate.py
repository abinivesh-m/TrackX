"""
annotate.py

Draws Day-1 visual pipeline results onto a frame: camera ID, vehicle
bbox/class/confidence, plate bbox, OCR text/confidence, plate status.
Pure OpenCV drawing - no detection/OCR logic lives here, so it's easy to
unit test with synthetic frames + fake observation dicts.

Consumes the FLAT per-vehicle observation schema (see
demo/visual_pipeline.py's _vehicle_observation()):
    vehicle_bbox, vehicle_class, vehicle_confidence, track_id,
    plate_bbox, raw_plate_text, normalized_plate_text, ocr_confidence,
    plate_status, plate_status_reason, plate_crop_path

Day 4.5 (SIH26127): Now draws plate zoom inset as CCTV-style overlay
on the main frame instead of showing a separate image.
"""
import cv2
import os

VEHICLE_COLOR = (0, 200, 0)         # green, BGR
PLATE_COLOR = (0, 0, 255)           # red, BGR
CAMERA_LABEL_COLOR = (0, 255, 255)  # yellow, BGR
UNAVAILABLE_COLOR = (180, 180, 180)  # grey, BGR
FONT = cv2.FONT_HERSHEY_SIMPLEX
INSET_SCALE = 3.0                   # Scale factor for plate zoom inset
INSET_WIDTH = 300                   # Target width for inset
INSET_HEIGHT = 150                  # Target height for inset
INSET_BORDER_COLOR = (255, 255, 255)  # white, BGR
INSET_BORDER_THICKNESS = 2


def draw_plate_inset(frame, plate_crop, plate_bbox, position="bottom-right", max_insets=4):
    """
    Draws a zoomed plate inset on the frame connected to the plate bbox.
    
    Args:
        frame: Main frame to draw on
        plate_crop: The actual plate crop image (from original frame)
        plate_bbox: Plate bbox coordinates in frame space [x1, y1, x2, y2]
        position: Where to place the inset ("bottom-right", "bottom-left", "top-right", "top-left")
        max_insets: Maximum number of insets to allow (prevents overlapping)
    
    Returns:
        Modified frame with inset drawn
    """
    if plate_crop is None or plate_crop.size == 0:
        return frame
    
    h, w = frame.shape[:2]
    
    # Calculate aspect ratio and resize while preserving it
    crop_h, crop_w = plate_crop.shape[:2]
    aspect_ratio = crop_w / crop_h if crop_h > 0 else 1.0
    
    # Calculate target dimensions preserving aspect ratio
    if aspect_ratio > INSET_WIDTH / INSET_HEIGHT:
        # Width is the limiting factor
        target_w = INSET_WIDTH
        target_h = int(INSET_WIDTH / aspect_ratio)
    else:
        # Height is the limiting factor
        target_h = INSET_HEIGHT
        target_w = int(INSET_HEIGHT * aspect_ratio)
    
    # Ensure minimum dimensions
    target_w = max(target_w, 100)
    target_h = max(target_h, 50)
    
    # Resize with high-quality interpolation
    try:
        resized_crop = cv2.resize(plate_crop, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
    except cv2.error:
        # If resize fails, return original frame
        return frame
    
    # Calculate inset position
    border = 10
    if position == "bottom-right":
        inset_x = w - INSET_WIDTH - border
        inset_y = h - INSET_HEIGHT - border
    elif position == "bottom-left":
        inset_x = border
        inset_y = h - INSET_HEIGHT - border
    elif position == "top-right":
        inset_x = w - INSET_WIDTH - border
        inset_y = border + 30  # Account for header
    elif position == "top-left":
        inset_x = border
        inset_y = border + 30  # Account for header
    else:
        inset_x = w - INSET_WIDTH - border
        inset_y = h - INSET_HEIGHT - border
    
    # Ensure inset stays within frame bounds
    inset_x = max(border, min(inset_x, w - INSET_WIDTH - border))
    inset_y = max(border + 30, min(inset_y, h - INSET_HEIGHT - border))
    
    # Check if the inset region is within frame bounds
    if inset_y + INSET_HEIGHT > h or inset_x + INSET_WIDTH > w:
        # If inset would go out of bounds, adjust position or skip
        if inset_y + INSET_HEIGHT > h:
            inset_y = h - INSET_HEIGHT - border
        if inset_x + INSET_WIDTH > w:
            inset_x = w - INSET_WIDTH - border
    
    # Ensure final position is valid
    if inset_y < 0 or inset_x < 0 or inset_y + target_h > h or inset_x + target_w > w:
        # Skip drawing if still out of bounds
        return frame
    
    # Draw inset background (semi-transparent black)
    overlay = frame.copy()
    cv2.rectangle(overlay, (inset_x, inset_y), 
                 (inset_x + target_w, inset_y + target_h), 
                 (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    
    # Draw the resized plate crop
    frame[inset_y:inset_y + target_h, inset_x:inset_x + target_w] = resized_crop
    
    # Draw border around inset
    cv2.rectangle(frame, (inset_x, inset_y), 
                 (inset_x + target_w, inset_y + target_h), 
                 INSET_BORDER_COLOR, INSET_BORDER_THICKNESS)
    
    # Draw connecting line from plate bbox to inset
    px1, py1, px2, py2 = plate_bbox
    plate_center_x = (px1 + px2) // 2
    plate_center_y = (py1 + py2) // 2
    
    inset_center_x = inset_x + target_w // 2
    inset_center_y = inset_y + target_h // 2
    
    # Draw line
    cv2.line(frame, (plate_center_x, plate_center_y), 
            (inset_center_x, inset_center_y), 
            INSET_BORDER_COLOR, 1)
    
    # Draw small circles at connection points
    cv2.circle(frame, (plate_center_x, plate_center_y), 3, INSET_BORDER_COLOR, -1)
    cv2.circle(frame, (inset_center_x, inset_center_y), 3, INSET_BORDER_COLOR, -1)
    
    return frame


def annotate_frame(frame, camera_id, vehicle_observations, frame_label=None):
    """
    frame: BGR numpy array. Returns an annotated COPY; original untouched.

    vehicle_observations: list of flat dicts, each expected to have at
    least "vehicle_bbox", "vehicle_class", "vehicle_confidence", and the
    plate_* fields (plate_bbox/plate_status/normalized_plate_text/
    ocr_confidence/plate_crop_path) - all optional/None when unavailable.
    
    Day 4.5: Now draws plate zoom inset as CCTV-style overlay on the main frame.
    Fixed: Multiple vehicles now get different inset positions to prevent overlap.
    """
    out = frame.copy()

    header = camera_id if not frame_label else f"{camera_id} | {frame_label}"
    cv2.putText(out, header, (10, 25), FONT, 0.7, CAMERA_LABEL_COLOR, 2)

    # Define inset positions for multiple vehicles to prevent overlap
    inset_positions = ["bottom-right", "bottom-left", "top-right", "top-left"]
    
    # Count vehicles with plates to assign positions
    plate_vehicle_count = 0

    for v in vehicle_observations:
        x1, y1, x2, y2 = v["vehicle_bbox"]
        cv2.rectangle(out, (x1, y1), (x2, y2), VEHICLE_COLOR, 2)

        label = f'{v.get("vehicle_class", "vehicle")} {v.get("vehicle_confidence", 0):.2f}'
        cv2.putText(out, label, (x1, max(15, y1 - 8)), FONT, 0.5, VEHICLE_COLOR, 2)
        
        # Add Track ID if available
        track_id = v.get("track_id")
        if track_id is not None:
            track_label = f"Track ID: {track_id}"
            cv2.putText(out, track_label, (x1, max(15, y1 - 25)), FONT, 0.5, VEHICLE_COLOR, 2)

        plate_status = v.get("plate_status")
        plate_bbox = v.get("plate_bbox")
        plate_crop_path = v.get("plate_crop_path")

        if plate_status in ["detected", "detected_no_ocr"] and plate_bbox:
            # plate_bbox is now in frame coordinates (fixed in Day 4)
            px1, py1, px2, py2 = plate_bbox
            cv2.rectangle(out, (px1, py1), (px2, py2), PLATE_COLOR, 2)

            # Always display normalized plate text (without IND artifacts)
            normalized_text = v.get("normalized_plate_text")
            if normalized_text:
                ocr_conf = v.get("ocr_confidence") or 0
                text_label = f"{normalized_text} ({ocr_conf:.2f})"
                cv2.putText(out, text_label, (px1, min(out.shape[0] - 5, py2 + 18)),
                            FONT, 0.5, PLATE_COLOR, 2)
            elif plate_status == "detected_no_ocr":
                # Show plate detected but OCR unavailable
                text_label = "PLATE DETECTED (OCR UNAVAILABLE)"
                cv2.putText(out, text_label, (px1, min(out.shape[0] - 5, py2 + 18)),
                            FONT, 0.4, PLATE_COLOR, 1)
            
            # Load and draw plate inset if crop path exists
            if plate_crop_path and os.path.isfile(plate_crop_path):
                plate_crop = cv2.imread(plate_crop_path)
                if plate_crop is not None and plate_crop.size > 0:
                    # Assign position based on vehicle index to prevent overlap
                    position = inset_positions[plate_vehicle_count % len(inset_positions)]
                    out = draw_plate_inset(out, plate_crop, plate_bbox, position=position)
                    plate_vehicle_count += 1
                    
        elif plate_status == "unavailable":
            cv2.putText(out, "plate: N/A (no detector)", (x1, min(out.shape[0] - 5, y2 + 18)),
                        FONT, 0.45, UNAVAILABLE_COLOR, 1)
        elif plate_status == "plate_not_detected":
            cv2.putText(out, "plate: not found", (x1, min(out.shape[0] - 5, y2 + 18)),
                        FONT, 0.45, UNAVAILABLE_COLOR, 1)
        elif plate_status == "ocr_failed":
            cv2.putText(out, "plate: OCR failed", (x1, min(out.shape[0] - 5, y2 + 18)),
                        FONT, 0.45, UNAVAILABLE_COLOR, 1)

    return out
