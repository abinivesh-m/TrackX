"""
live_webcam.py

Frame-by-frame live webcam processing for the SIH26127 "Live Webcam +
Phone Number-Plate Demo" backend.

Provides ``LiveWebcamSession``, a small stateful wrapper around the real
detection/OCR stack that the ``/api/v1/observations/webcam-stream/{camera_id}``
WebSocket endpoint (see backend/app/api/v1/observations.py) drives one frame
at a time.  A session keeps per-track OCR history across frames so the
plate-state rollup (UNKNOWN / LOW_CONFIDENCE / TENTATIVE / VERIFIED) can
reflect real temporal evidence instead of a single frame.

This module lives at the project root (not under backend/) because
backend/app/main.py inserts the project root onto sys.path before importing
the backend, and observations.py does ``from live_webcam import LiveWebcamSession``.
"""

import time
from collections import defaultdict
from typing import Any, Dict, List


# Plate-state constants (mirrored from pipeline.py so the webcam demo agrees
# with the batch pipeline on what VERIFIED means). Defined locally to avoid
# importing the heavy pipeline module (and its ultralytics/PaddleOCR deps)
# at import time.
LOW_CONFIDENCE_THRESHOLD = 0.55
PLATE_STATE_VERIFIED_MIN_READINGS = 3
PLATE_STATE_VERIFIED_MIN_CONFIDENCE = 0.70


def _plate_state_for_track(plate_status, temporal_support, combined_confidence):
    if plate_status in ("unavailable", "no_plate_detected", "detected_not_read"):
        return "UNKNOWN"
    if plate_status == "low_confidence":
        return "LOW_CONFIDENCE"
    if (temporal_support >= PLATE_STATE_VERIFIED_MIN_READINGS
            and (combined_confidence or 0.0) >= PLATE_STATE_VERIFIED_MIN_CONFIDENCE):
        return "VERIFIED"
    return "TENTATIVE"


class LiveWebcamSession:
    """Stateful per-session processor for live webcam frames."""

    def __init__(self, vehicle_detector, plate_detector, ocr, camera_id):
        self.vehicle_detector = vehicle_detector
        self.plate_detector = plate_detector
        self.ocr = ocr
        self.camera_id = camera_id

        self.frame_idx = 0
        self.track_ocr_readings = defaultdict(list)
        self.track_best_plate = {}
        self.track_best_conf = defaultdict(float)

    def process_frame(self, frame) -> Dict[str, Any]:
        t0 = time.perf_counter()

        vehicles_out: List[Dict[str, Any]] = []

        try:
            dets = self.vehicle_detector.track_frame(frame) or []
        except Exception:
            dets = []

        for v in dets:
            bbox = v.get("bbox")
            vtype = v.get("vehicle_type", "car")
            track_id = v.get("track_id")
            conf = float(v.get("confidence", 0.0) or 0.0)

            vehicle_entry = {
                "vehicle_type": vtype,
                "track_id": track_id,
                "bbox": bbox,
                "confidence": conf,
                "plate_text": None,
                "plate_state": "UNKNOWN",
                "ocr_confidence": 0.0,
            }

            plate_found = False
            voted_text = None
            combined_conf = 0.0
            temporal_support = 0

            if self.plate_detector is not None and bbox is not None:
                try:
                    x1, y1, x2, y2 = [int(c) for c in bbox]
                    h, w = frame.shape[:2]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    if x2 > x1 and y2 > y1:
                        vehicle_crop = frame[y1:y2, x1:x2]
                        plate_dets = self.plate_detector.detect_on_array(vehicle_crop) or []
                        if plate_dets:
                            plate_found = True
                            best = plate_dets[0]
                            px1, py1, px2, py2 = best["bbox"]
                            fx1, fy1 = x1 + px1, y1 + py1
                            fx2, fy2 = x1 + px2, y1 + py2
                            pad = 4
                            fx1, fy1 = max(0, fx1 - pad), max(0, fy1 - pad)
                            fx2, fy2 = min(w, fx2 + pad), min(h, fy2 + pad)
                            plate_crop = frame[fy1:fy2, fx1:fx2]
                            if (plate_crop is not None and plate_crop.size > 0
                                    and self.ocr is not None):
                                try:
                                    text, c = self.ocr.read(plate_crop)
                                    if text and any(ch.isdigit() for ch in text):
                                        self.track_ocr_readings[track_id].append(
                                            (text, float(c or 0.0))
                                        )
                                except Exception:
                                    pass

                    if self.track_ocr_readings.get(track_id):
                        try:
                            from recognition.ocr_reader import vote_plate_text
                            voted_text, combined_conf = vote_plate_text(
                                self.track_ocr_readings[track_id]
                            )
                        except Exception:
                            voted_text = self.track_ocr_readings[track_id][-1][0]
                            combined_conf = self.track_ocr_readings[track_id][-1][1]

                        if voted_text:
                            self.track_best_plate[track_id] = voted_text
                            self.track_best_conf[track_id] = max(
                                self.track_best_conf.get(track_id, 0.0),
                                float(combined_conf or 0.0),
                            )

                    temporal_support = len(self.track_ocr_readings.get(track_id, []))

                    if self.ocr is None or self.plate_detector is None:
                        plate_status = "unavailable"
                    elif not plate_found:
                        plate_status = "no_plate_detected"
                    elif not voted_text:
                        plate_status = "detected_not_read"
                    elif float(combined_conf or 0.0) < LOW_CONFIDENCE_THRESHOLD:
                        plate_status = "low_confidence"
                    else:
                        plate_status = "recognized"

                    plate_state = _plate_state_for_track(
                        plate_status, temporal_support, float(combined_conf or 0.0)
                    )

                    vehicle_entry["plate_text"] = voted_text
                    vehicle_entry["plate_state"] = plate_state
                    vehicle_entry["ocr_confidence"] = float(combined_conf or 0.0)

                except Exception:
                    vehicle_entry["plate_state"] = "UNKNOWN"

            vehicles_out.append(vehicle_entry)

        total_ms = (time.perf_counter() - t0) * 1000.0

        result = {
            "frame_idx": self.frame_idx,
            "vehicles": vehicles_out,
            "timing_ms": {"total": total_ms},
            "elapsed_seconds": self.frame_idx * 0.5,
        }
        self.frame_idx += 1
        return result


# Module-level convenience alias used by some callers/tests.
LiveWebcam = LiveWebcamSession