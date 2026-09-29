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

import os
import logging
from typing import Dict, List, Iterator, Tuple, Any

from ultralytics import YOLO

logger = logging.getLogger(__name__)


# COCO class IDs used by YOLO
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# SIH26127 screening-demo task ("FPS architecture"): auto-detect a real
# NVIDIA GPU and use it if present, instead of silently always running on
# CPU. This never installs or assumes a GPU-enabled torch build - it just
# asks whichever torch build is already installed whether CUDA is usable,
# and falls back to "cpu" (today's actual behavior, unchanged) if torch
# isn't importable, isn't CUDA-enabled, or reports no device. Computed once
# per VehicleDetector instance, not per frame - device availability doesn't
# change mid-run, and re-checking every frame would be pure overhead.
def _resolve_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info("VehicleDetector: CUDA GPU detected (%s) - using device=cuda:0", name)
            return "cuda:0"
    except Exception as e:
        logger.info("VehicleDetector: CUDA check failed (%s) - using CPU", e)
        return "cpu"
    logger.info(
        "VehicleDetector: no CUDA GPU available (this project's pinned "
        "torch==2.3.0 build is CPU-only by default, see requirements.txt) "
        "- using device=cpu"
    )
    return "cpu"

# SIH26127 Priority 2 (occlusion-aware track continuity): TrackX's own
# tuned ByteTrack config, used instead of ultralytics' packaged
# "bytetrack.yaml" default. Only track_buffer is changed (30 -> 60,
# doubling occlusion tolerance) - measured for real effect on a real
# occlusion case before shipping, see docs/TRACKING_TUNING.md. A
# match_thresh loosening (0.8 -> 0.9) was also tried and measured a
# bigger fragmentation reduction, but was NOT adopted here because it
# loosens re-association for every match in the whole video, not just
# genuine occlusion recovery, which raises the risk of merging two
# distinct nearby vehicles - track_buffer alone is a more targeted,
# safer lever (it only affects how long a LOST track is kept eligible for
# re-matching, not how strict any individual match decision is).
_TRACKX_BYTETRACK_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "bytetrack_trackx.yaml",
)


def _resolve_tracker_config(tracker_config=None):
    """Falls back to ultralytics' own packaged bytetrack.yaml if TrackX's
    tuned config file isn't present for some reason (e.g. a stripped-down
    deployment) - tracking should never hard-fail just because this one
    tuning file is missing."""
    if tracker_config is not None:
        return tracker_config
    if os.path.isfile(_TRACKX_BYTETRACK_CONFIG):
        return _TRACKX_BYTETRACK_CONFIG
    return "bytetrack.yaml"


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
        tracker_config: str = None,
        **kwargs  # Accept 'weights' as alias for backward compatibility
    ):
        """
        Initialize the detector.

        Args:
            model_path:
                YOLO model weights.

            conf:
                Detection confidence threshold.

            tracker_config:
                Path to a ByteTrack tracker YAML. Defaults to TrackX's own
                tuned config (config/bytetrack_trackx.yaml) rather than
                ultralytics' packaged default - pass an explicit path (or
                "bytetrack.yaml") to override.
            
            **kwargs:
                Additional arguments for backward compatibility (e.g., 'weights' as alias for 'model_path')
        """

        # Support 'weights' as alias for 'model_path' for backward compatibility
        if 'weights' in kwargs:
            model_path = kwargs['weights']

        self.model = YOLO(model_path)
        self.conf = conf
        self.tracker_config = _resolve_tracker_config(tracker_config)
        self.device = _resolve_device()

        # SIH26127 (2026-09-15): class filtering used to be a hardcoded
        # module-level COCO_id -> name dict (VEHICLE_CLASSES, ids
        # 2/3/5/7), which silently breaks on any checkpoint whose class
        # ids aren't COCO's - e.g. models/best_vehicle.pt, a real
        # custom-trained YOLOv11n with its OWN 5 classes at DIFFERENT ids
        # (0:'vehicle', 1:'truck', 2:'bus', 3:'motorcycle', 4:'bicycle').
        # Loading that checkpoint through the old hardcoded map would have
        # mislabeled everything (id 2 relabeled "bus" as "car") and
        # silently dropped the model's main class entirely (id 0
        # 'vehicle' was never in VEHICLE_CLASSES). Build the filter from
        # THIS checkpoint's own self.model.names instead, matched by name
        # rather than assumed id, so it's correct for both the custom
        # model and the stock COCO 'yolov8n.pt' fallback. The custom
        # model's generic 4-wheeler class is named "vehicle" in its own
        # training data - relabeled to "car" here so vehicle_type stays
        # consistent with the rest of the app (DB column, frontend
        # labels, backend/tests/test_webcam_stream.py) no matter which
        # checkpoint is active. "bicycle" is intentionally left out,
        # matching this app's existing car/motorcycle/bus/truck scope.
        _NAME_TO_LABEL = {
            "car": "car", "vehicle": "car",
            "motorcycle": "motorcycle", "motorbike": "motorcycle",
            "bus": "bus",
            "truck": "truck",
        }
        self.vehicle_classes = {}
        for cls_id, name in self.model.names.items():
            label = _NAME_TO_LABEL.get(str(name).strip().lower())
            if label:
                self.vehicle_classes[cls_id] = label
        if not self.vehicle_classes:
            logger.warning(
                "VehicleDetector: model.names=%r has no recognized vehicle "
                "classes (expected one of %s) - falling back to the COCO "
                "id map so detection doesn't silently return nothing.",
                self.model.names, sorted(set(_NAME_TO_LABEL.values())),
            )
            self.vehicle_classes = dict(VEHICLE_CLASSES)

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
            device=self.device,
        )

        if not results:
            return []

        result = results[0]

        if result.boxes is None:
            return []

        detections = []

        for box in result.boxes:
            cls_id = int(box.cls[0])

            if cls_id not in self.vehicle_classes:
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
                    "vehicle_type": self.vehicle_classes[cls_id],
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

    def _detections_from_track_result(self, result) -> List[Dict[str, Any]]:
        """
        Converts one ultralytics tracking `Result` (one frame's worth of
        boxes) into TrackX's vehicle-detection dict list, assigning /
        maintaining ByteTrack IDs (with the same IoU-based fallback-ID
        scheme used everywhere else in this class).

        SIH26127 webcam-demo extraction: this is the exact box-processing
        body that used to live only inside track_video()'s loop, pulled
        out unchanged so a NEW single-frame entry point (track_frame(),
        below - used for live webcam frames) assigns track IDs through the
        identical logic instead of a second, drifting copy of it.
        track_video()'s own external behavior is unchanged by this.
        """
        frame_dets = []
        boxes = result.boxes

        if boxes is None:
            self._fallback_tracks = {}
            return frame_dets

        # YOLO may return detections before tracker IDs have been assigned.
        ids = boxes.id

        for box_index, box in enumerate(boxes):

            cls_id = int(box.cls[0])

            # Ignore person, bicycle, etc.
            if cls_id not in self.vehicle_classes:
                continue

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bbox = [int(x1), int(y1), int(x2), int(y2)]

            detection = {
                "bbox": bbox,
                "confidence": round(
                    float(box.conf[0]),
                    3,
                ),
                "vehicle_type": self.vehicle_classes[cls_id],
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
        frame_dets = deduplicate_vehicle_detections(frame_dets)

        # Update fallback tracks for next frame - only for detections that
        # used fallback IDs.
        self._fallback_tracks = {}
        for det in frame_dets:
            track_id = det["track_id"]
            if isinstance(track_id, str) and track_id.startswith("fallback_"):
                fallback_num = int(track_id.split("_")[1])
                self._fallback_tracks[fallback_num] = det["bbox"]

        return frame_dets

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
            tracker=self.tracker_config,
            verbose=False,
            stream=True,
            device=self.device,
        )

        for frame_idx, result in enumerate(results):
            if result.boxes is None:
                yield frame_idx, result.orig_img, []
                # Clear fallback tracks when no detections
                self._fallback_tracks = {}
                continue

            frame_dets = self._detections_from_track_result(result)

            yield (
                frame_idx,
                result.orig_img,
                frame_dets,
            )

    def start_new_live_session(self):
        """
        Resets this detector's own IoU-fallback-ID bookkeeping for a brand
        new live (one-frame-at-a-time) session - e.g. a new webcam
        connection - so a new session's fallback IDs don't inherit
        bookkeeping left over from a previous one.

        This does NOT (and, short of reaching into ultralytics' private
        predictor internals, cannot) force ultralytics' own persisted
        ByteTrack track-ID counter to restart at 1 - a new live session's
        real ByteTrack IDs may continue upward from a previous session
        instead of resetting. That is a cosmetic numbering quirk, not a
        correctness issue (IDs are still unique and stable within a
        session); see track_frame()'s docstring for the underlying reason
        and why per-session model instances aren't used instead (cost of
        reloading YOLO weights per session).
        """
        self._fallback_tracks = {}
        self._next_fallback_id = 1

    def track_frame(self, frame) -> List[Dict[str, Any]]:
        """
        Run YOLO detection + ByteTrack on a SINGLE externally-supplied
        frame (e.g. one live webcam frame captured in the browser and sent
        to the backend), maintaining tracker state across repeated calls
        via ultralytics' own `persist=True` mechanism - the same
        officially-documented pattern used for frame-by-frame live
        tracking loops (as opposed to track_video()'s `persist=True` with
        `stream=True` over an entire video FILE PATH). Detections are
        converted to TrackX's dict shape via the exact same
        _detections_from_track_result() used by track_video(), so a live
        webcam frame and a video frame get identical track-ID handling.

        IMPORTANT - concurrency: ultralytics' persist=True tracker state
        lives on this detector's own `self.model` instance. Calling
        track_frame() from more than one concurrent live session on the
        SAME VehicleDetector instance would interleave and corrupt both
        sessions' track IDs. This method does not serialize that itself -
        callers (see backend/app/api/v1/observations.py's webcam-stream
        WebSocket endpoint) MUST ensure only one live session uses a given
        detector instance at a time.

        Returns: list of vehicle detections, same shape as track_video()'s
        per-frame list (bbox/confidence/vehicle_type/track_id). Returns
        an empty list (never raises, never fabricates a detection) if YOLO
        finds nothing in this frame.
        """
        results = self.model.track(
            source=frame,
            conf=self.conf,
            persist=True,
            tracker=self.tracker_config,
            verbose=False,
            device=self.device,
        )
        if not results:
            return []
        result = results[0]
        if result.boxes is None:
            self._fallback_tracks = {}
            return []
        return self._detections_from_track_result(result)