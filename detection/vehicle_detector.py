"""
Vehicle detection and tracking utilities for TrackX.

Provides:
    - VehicleDetector
    - _iou
    - deduplicate_vehicle_detections

Vehicle classes:
    car
    motorcycle
    bus
    truck
"""

from typing import Dict, List, Iterator, Tuple, Any

from ultralytics import YOLO


# COCO class IDs used by YOLO
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


def _iou(box_a, box_b) -> float:
    """
    Calculate Intersection over Union (IoU) between two bounding boxes.

    Bounding box format:
        [x1, y1, x2, y2]

    Returns:
        float in range [0, 1]
    """

    if len(box_a) != 4 or len(box_b) != 4:
        raise ValueError("Bounding boxes must contain exactly 4 values")

    ax1, ay1, ax2, ay2 = map(float, box_a)
    bx1, by1, bx2, by2 = map(float, box_b)

    # Normalize malformed/reversed boxes safely
    ax1, ax2 = min(ax1, ax2), max(ax1, ax2)
    ay1, ay2 = min(ay1, ay2), max(ay1, ay2)

    bx1, bx2 = min(bx1, bx2), max(bx1, bx2)
    by1, by2 = min(by1, by2), max(by1, by2)

    # Intersection rectangle
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)

    intersection = inter_w * inter_h

    # Areas
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def deduplicate_vehicle_detections(
    detections: List[Dict[str, Any]],
    iou_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Remove duplicate vehicle detections using IoU.

    If two vehicle detections overlap enough, they are treated as
    the same physical detection and only the highest-confidence
    detection is retained.

    IMPORTANT:
        Vehicle class is intentionally ignored during duplicate
        suppression.

    Example:
        car  confidence=0.49
        truck confidence=0.46

    If IoU >= threshold, only the car is retained.

    Args:
        detections:
            List of detection dictionaries containing at least:
                bbox
                confidence

        iou_threshold:
            IoU above which two detections are considered duplicates.

    Returns:
        Deduplicated list of detections.
    """

    if not detections:
        return []

    if not 0.0 <= iou_threshold <= 1.0:
        raise ValueError("iou_threshold must be between 0 and 1")

    # Work on copies so the caller's list is never modified.
    candidates = [dict(det) for det in detections]

    # Highest confidence first.
    candidates.sort(
        key=lambda det: float(det.get("confidence", 0.0)),
        reverse=True,
    )

    kept = []

    for candidate in candidates:
        candidate_bbox = candidate.get("bbox")

        if candidate_bbox is None:
            # Don't crash because of malformed external input.
            kept.append(candidate)
            continue

        duplicate = False

        for existing in kept:
            existing_bbox = existing.get("bbox")

            if existing_bbox is None:
                continue

            overlap = _iou(candidate_bbox, existing_bbox)

            if overlap >= iou_threshold:
                duplicate = True
                break

        if not duplicate:
            kept.append(candidate)

    return kept


class VehicleDetector:
    """
    YOLO-based vehicle detector and tracker.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf: float = 0.25,
        **kwargs  # Accept 'weights' as alias for backward compatibility
    ):
        """
        Initialize the detector.

        Args:
            model_path:
                YOLO model weights.

            conf:
                Detection confidence threshold.
            
            **kwargs:
                Additional arguments for backward compatibility (e.g., 'weights' as alias for 'model_path')
        """

        # Support 'weights' as alias for 'model_path' for backward compatibility
        if 'weights' in kwargs:
            model_path = kwargs['weights']

        self.model = YOLO(model_path)
        self.conf = conf

        # Fallback tracking state for when ByteTrack doesn't assign IDs
        self._fallback_tracks = {}  # Maps fallback_id -> bbox from previous frame
        self._next_fallback_id = 1  # Counter for generating new fallback IDs

    def detect(self, frame):
        """
        Run vehicle detection on a single frame.

        Returns:
            List of vehicle detections.
        """

        results = self.model.predict(
            source=frame,
            conf=self.conf,
            verbose=False,
        )

        if not results:
            return []

        result = results[0]

        if result.boxes is None:
            return []

        detections = []

        for box in result.boxes:
            cls_id = int(box.cls[0])

            if cls_id not in VEHICLE_CLASSES:
                continue

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append(
                {
                    "bbox": [
                        int(x1),
                        int(y1),
                        int(x2),
                        int(y2),
                    ],
                    "confidence": round(
                        float(box.conf[0]),
                        3,
                    ),
                    "vehicle_type": VEHICLE_CLASSES[cls_id],
                }
            )

        return deduplicate_vehicle_detections(detections)

    def _match_fallback_track(self, bbox: List[int], iou_threshold: float = 0.3) -> int:
        """
        Match a detection against previous fallback tracks using IoU.

        Args:
            bbox: Current detection bbox [x1, y1, x2, y2]
            iou_threshold: Minimum IoU to consider it the same vehicle

        Returns:
            Existing fallback ID if matched, or None if no match
        """
        best_match_id = None
        best_iou = iou_threshold

        for fallback_id, prev_bbox in self._fallback_tracks.items():
            iou = _iou(bbox, prev_bbox)
            if iou > best_iou:
                best_iou = iou
                best_match_id = fallback_id

        return best_match_id

    @staticmethod
    def crop(frame, bbox):
        """
        Crop a bounding box from a frame.

        Args:
            frame: numpy array (H, W, C)
            bbox: [x1, y1, x2, y2]

        Returns:
            Cropped numpy array, or None if bbox is invalid
        """
        if frame is None or frame.size == 0:
            return None
        if bbox is None or len(bbox) != 4:
            return None

        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]

        # Clamp to frame boundaries
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        return frame[y1:y2, x1:x2]

    def track_video(
        self,
        video_path: str,
    ) -> Iterator[Tuple[int, Any, List[Dict[str, Any]]]]:
        """
        Run YOLO detection + ByteTrack over an entire video.

        Yields:
            (
                frame_index,
                original_frame,
                vehicle_detections
            )

        Each vehicle detection always contains:

            {
                "bbox": [x1, y1, x2, y2],
                "confidence": float,
                "vehicle_type": str,
                "track_id": int or str  # Always present
            }

        ByteTrack IDs are preserved across frames when possible.
        For detections without ByteTrack IDs, fallback tracking ensures
        consistent IDs across frames using IoU matching.
        """

        # Reset fallback tracking state for new video
        self._fallback_tracks = {}
        self._next_fallback_id = 1

        results = self.model.track(
            source=video_path,
            conf=self.conf,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
            stream=True,
        )

        for frame_idx, result in enumerate(results):

            frame_dets = []

            boxes = result.boxes

            if boxes is None:
                yield frame_idx, result.orig_img, []
                # Clear fallback tracks when no detections
                self._fallback_tracks = {}
                continue

            # YOLO may return detections before tracker IDs
            # have been assigned.
            ids = boxes.id

            for box_index, box in enumerate(boxes):

                cls_id = int(box.cls[0])

                # Ignore person, bicycle, etc.
                if cls_id not in VEHICLE_CLASSES:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                bbox = [int(x1), int(y1), int(x2), int(y2)]

                detection = {
                    "bbox": bbox,
                    "confidence": round(
                        float(box.conf[0]),
                        3,
                    ),
                    "vehicle_type": VEHICLE_CLASSES[cls_id],
                }

                # Always assign a track_id
                if ids is not None:
                    track_id = ids[box_index]

                    if track_id is not None:
                        # Use ByteTrack ID when available
                        detection["track_id"] = int(
                            track_id.item()
                            if hasattr(track_id, "item")
                            else track_id
                        )
                    else:
                        # ByteTrack didn't assign ID, use fallback
                        fallback_id = self._match_fallback_track(bbox)
                        if fallback_id is None:
                            fallback_id = self._next_fallback_id
                            self._next_fallback_id += 1
                        detection["track_id"] = f"fallback_{fallback_id}"
                else:
                    # No IDs at all from ByteTrack, use fallback
                    fallback_id = self._match_fallback_track(bbox)
                    if fallback_id is None:
                        fallback_id = self._next_fallback_id
                        self._next_fallback_id += 1
                    detection["track_id"] = f"fallback_{fallback_id}"

                frame_dets.append(detection)

            # Remove overlapping duplicate detections.
            frame_dets = deduplicate_vehicle_detections(
                frame_dets
            )

            # Update fallback tracks for next frame
            # Only update for detections that used fallback IDs
            self._fallback_tracks = {}
            for det in frame_dets:
                track_id = det["track_id"]
                if isinstance(track_id, str) and track_id.startswith("fallback_"):
                    fallback_num = int(track_id.split("_")[1])
                    self._fallback_tracks[fallback_num] = det["bbox"]

            yield (
                frame_idx,
                result.orig_img,
                frame_dets,
            )