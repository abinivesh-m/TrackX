"""
Observations API routes
"""

import logging
import os
import tempfile
import time
import uuid

import cv2
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.observation import ObservationResponse
from database.observation_store import ObservationStore
from config import RESULTS_DIR
from network.camera_network import CAMERAS

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Video ingest (Demo Mode video-upload flow)
#
# This is the one piece of "CCTV video -> observations" product flow that
# had no backend endpoint at all before this. Everything it does is reused,
# not reimplemented: detection/OCR/tracking is pipeline.run_video_to_db()
# (the same function `python pipeline.py --to-db` already calls from the
# CLI), and persistence is the same ObservationStore every other endpoint in
# this file reads from. This module only adds: upload handling/validation,
# lazy singleton model loading (constructing YOLO/PaddleOCR per request
# would add several seconds to every call), and turning the returned
# records into summary statistics + a servable crop image URL.
# ---------------------------------------------------------------------------

_ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
_MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB - generous for a demo clip, bounded on purpose
_MAX_VIDEO_DURATION_SECONDS = 180  # 3 minutes - "demo-scale", processed synchronously
_UPLOAD_DIR = RESULTS_DIR / "video_uploads"

_vehicle_detector = None
_plate_detector = None
_ocr = None
_ocr_init_attempted = False


def _get_vehicle_detector():
    """Lazy singleton - constructing YOLO takes real time; do it once per
    process, not once per request."""
    global _vehicle_detector
    if _vehicle_detector is None:
        from detection.vehicle_detector import VehicleDetector
        _vehicle_detector = VehicleDetector(model_path="yolov8n.pt")
    return _vehicle_detector


def _get_plate_detector():
    global _plate_detector
    if _plate_detector is None:
        from demo.visual_pipeline import find_plate_weights
        from detection.detect_plates import PlateDetector
        weights = find_plate_weights()
        if weights:
            _plate_detector = PlateDetector(weights=weights)
    return _plate_detector


def _get_ocr():
    """Only attempted once - if OCR can't initialize, don't retry it (and
    pay its failure cost) on every single upload."""
    global _ocr, _ocr_init_attempted
    if not _ocr_init_attempted:
        _ocr_init_attempted = True
        from recognition.ocr_reader import try_init_ocr
        _ocr = try_init_ocr()
    return _ocr


def _plate_crop_url(plate_crop_path):
    """Converts an absolute/relative filesystem path (as stored by
    pipeline.run_video_to_db) into a URL the frontend can actually load,
    via the /media/plate-crops static mount (see app/main.py). Returns None
    rather than a broken path if the file isn't where expected."""
    if not plate_crop_path:
        return None
    try:
        if not os.path.isfile(plate_crop_path):
            return None
        return f"/media/plate-crops/{os.path.basename(plate_crop_path)}"
    except (TypeError, OSError):
        return None

@router.get("/")
def get_observations(
    camera_id: str = Query(None, description="Filter by camera"),
    plate: str = Query(None, description="Filter by license plate"),
    limit: int = Query(100, description="Maximum number of observations"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get observations with optional filtering"""
    try:
        store = ObservationStore()
        all_obs = store.all_observations()
        
        # Apply filters
        if camera_id:
            all_obs = [obs for obs in all_obs if obs.get("camera_id") == camera_id]
        
        if plate:
            all_obs = [obs for obs in all_obs if obs.get("normalized_plate") == plate or obs.get("plate_text") == plate]
        
        # Apply limit
        all_obs = all_obs[:limit]
        
        # Convert to ObservationResponse format
        observation_responses = []
        for obs in all_obs:
            observation_responses.append({
                "id": obs.get("id", 0),
                "plate_text": obs.get("plate_text"),
                "normalized_plate": obs.get("normalized_plate"),
                "raw_plate_text": obs.get("raw_plate_text"),
                "camera_id": obs.get("camera_id"),
                "timestamp": obs.get("timestamp"),
                "vehicle_type": obs.get("vehicle_type"),
                "confidence": obs.get("confidence"),
                "vehicle_bbox": obs.get("vehicle_bbox"),
                "plate_bbox": obs.get("plate_bbox"),
                "source_file": obs.get("source_file"),
                "frame_index": obs.get("frame_index"),
                "ocr_confidence": obs.get("ocr_confidence"),
                "plate_confidence": obs.get("plate_confidence"),
                "data_source": obs.get("data_source"),
                "annotated_output": obs.get("annotated_output"),
                "plate_crop_path": obs.get("plate_crop_path"),
                "plate_crop_url": _plate_crop_url(obs.get("plate_crop_path")),
                "created_at": obs.get("timestamp", datetime.utcnow().isoformat())
            })
        
        return observation_responses
        
    except Exception as e:
        # Was `raise Exception(...)` - an unhandled exception type FastAPI
        # has no HTTPException mapping for, so it fell through to a bare
        # generic 500 with no JSON error envelope for the client. Log the
        # real cause server-side; return a safe, well-formed error to callers.
        logger.exception("get_observations failed")
        raise HTTPException(status_code=500, detail="Could not retrieve observations. Please try again.")
    finally:
        if 'store' in locals():
            store.close()

@router.get("/recent")
def get_recent_observations(
    limit: int = Query(20, description="Number of recent observations"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent observations"""
    try:
        store = ObservationStore()
        all_obs = store.all_observations()
        
        # Sort by timestamp descending
        all_obs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Get recent observations
        recent_obs = all_obs[:limit]
        
        # Convert to ObservationResponse format
        observation_responses = []
        for obs in recent_obs:
            observation_responses.append({
                "id": obs.get("id", 0),
                "plate_text": obs.get("plate_text"),
                "normalized_plate": obs.get("normalized_plate"),
                "camera_id": obs.get("camera_id"),
                "timestamp": obs.get("timestamp"),
                "confidence": obs.get("confidence"),
                "vehicle_type": obs.get("vehicle_type"),
                "annotated_output": obs.get("annotated_output"),
                "created_at": obs.get("timestamp", datetime.utcnow().isoformat())
            })
        
        return observation_responses
        
    except Exception as e:
        logger.exception("get_recent_observations failed")
        raise HTTPException(status_code=500, detail="Could not retrieve recent observations. Please try again.")
    finally:
        if 'store' in locals():
            store.close()


def _annotated_url(annotated_path):
    """Same idea as _plate_crop_url but for the full annotated frame saved
    under outputs/results/annotated/ (mounted at /media/annotated - see
    app/main.py)."""
    if not annotated_path:
        return None
    try:
        if not os.path.isfile(annotated_path):
            return None
        return f"/media/annotated/{os.path.basename(annotated_path)}"
    except (TypeError, OSError):
        return None


@router.get("/camera-media/{camera_id}")
def get_camera_media(camera_id: str, current_user: User = Depends(get_current_user)):
    """
    Real discovery of what's on disk for this camera - the same
    data/cameras/<CAM_ID>/images|videos/ folders demo/visual_pipeline.py's
    `python -m demo.visual_pipeline --camera CAM_01` CLI reads from. Powers
    the "N image(s), M video(s) available for <camera>" label on the AI
    Processing page so it always reflects real files, never a guess.
    """
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail=f"Unknown camera id: {camera_id}")

    from demo.camera_simulator import get_camera_feed, CameraFeedNotFound

    try:
        feed = get_camera_feed(camera_id)
    except CameraFeedNotFound:
        return {"camera_id": camera_id, "available_images": 0, "available_videos": 0, "folder_exists": False}

    return {
        "camera_id": camera_id,
        "available_images": len(feed.images),
        "available_videos": len(feed.videos),
        "folder_exists": True,
    }


@router.post("/process-camera")
def process_camera(
    camera_id: str = Form(...),
    frame_speed: int = Form(5, description="Process every Nth video frame (ignored for still images)."),
    max_frames: int | None = Form(None, description="Optional hard cap on video frames processed."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Runs the REAL AI pipeline (demo/visual_pipeline.py's process_image() /
    process_video() - the exact same functions `python -m demo.visual_pipeline
    --camera CAM_01` uses from the CLI) over whatever images/videos already
    sit in this camera's local folder (data/cameras/<CAM_ID>/images|videos/),
    and writes every resulting observation into the same observations.db
    every other endpoint reads from. Nothing here is simulated or
    hardcoded - a camera with no media on disk simply produces zero
    observations, honestly.
    """
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail=f"Unknown camera id: {camera_id}")
    if frame_speed < 1:
        raise HTTPException(status_code=400, detail="frame_speed must be >= 1.")

    from demo.camera_simulator import get_camera_feed, CameraFeedNotFound
    from demo.visual_pipeline import process_image, process_video, write_observations_to_db

    try:
        feed = get_camera_feed(camera_id)
    except CameraFeedNotFound:
        raise HTTPException(
            status_code=404,
            detail=f"No local media folder found for '{camera_id}'. "
                   f"Add files under data/cameras/{camera_id}/images/ or videos/ first.",
        )

    if not feed.has_media:
        return {
            "camera_id": camera_id,
            "camera_name": CAMERAS[camera_id]["name"],
            "statistics": {
                "images_processed": 0,
                "videos_processed": 0,
                "vehicles_detected": 0,
                "plates_detected": 0,
                "plates_recognized": 0,
                "observations_stored": 0,
                "processing_duration_seconds": 0,
            },
            "observations": [],
        }

    try:
        vehicle_detector = _get_vehicle_detector()
    except Exception:
        logger.exception("Vehicle detector initialization failed")
        raise HTTPException(
            status_code=503,
            detail="Vehicle detector is unavailable right now. Please try again shortly.",
        )

    plate_detector = _get_plate_detector()
    ocr = _get_ocr() if plate_detector is not None else None

    start = time.time()
    observations = []
    try:
        for img_path in feed.images:
            observations.extend(process_image(img_path, camera_id, vehicle_detector, plate_detector, ocr))
        for vid_path in feed.videos:
            observations.extend(
                process_video(
                    vid_path, camera_id, vehicle_detector, plate_detector, ocr,
                    frame_sample=frame_speed, max_frames=max_frames,
                )
            )
    except Exception:
        logger.exception("Camera-folder processing failed for camera_id=%r", camera_id)
        raise HTTPException(status_code=500, detail="AI processing failed. Please try again.")

    try:
        n_written = write_observations_to_db(observations)
    except Exception:
        logger.exception("Failed to write camera-folder observations to the database for camera_id=%r", camera_id)
        raise HTTPException(status_code=500, detail="Vehicles were detected but could not be saved. Please try again.")

    processing_duration_seconds = round(time.time() - start, 2)
    plates_detected = sum(1 for o in observations if o.get("plate_bbox"))
    plates_recognized = sum(
        1 for o in observations
        if o.get("plate_text") and o.get("plate_text") != "unavailable"
    )

    return {
        "camera_id": camera_id,
        "camera_name": CAMERAS[camera_id]["name"],
        "plate_detector_available": plate_detector is not None,
        "ocr_available": ocr is not None,
        "statistics": {
            "images_processed": len(feed.images),
            "videos_processed": len(feed.videos),
            "vehicles_detected": len(observations),
            "plates_detected": plates_detected,
            "plates_recognized": plates_recognized,
            "observations_stored": n_written,
            "processing_duration_seconds": processing_duration_seconds,
        },
        "observations": [
            {
                "track_id": o.get("track_id"),
                "vehicle_type": o.get("vehicle_class"),
                "plate_text": o.get("plate_text") if o.get("plate_text") != "unavailable" else None,
                "plate_status": (
                    "unavailable" if ocr is None and plate_detector is not None else
                    "no_plate_detected" if not o.get("plate_bbox") else
                    "recognized" if o.get("plate_text") not in (None, "unavailable") else
                    "detected_not_read"
                ),
                "ocr_confidence": o.get("ocr_confidence"),
                "plate_confidence": o.get("plate_confidence"),
                "vehicle_confidence": o.get("vehicle_confidence"),
                "timestamp": o.get("timestamp"),
                "source_file": os.path.basename(o.get("source_file") or ""),
                "source_type": o.get("source_type"),
                "frame_index": o.get("frame_index"),
                "plate_crop_url": _plate_crop_url(o.get("plate_crop_path")),
                "annotated_url": _annotated_url(o.get("annotated_output")),
            }
            for o in observations
        ],
    }


@router.post("/ingest-video")
def ingest_video(
    file: UploadFile = File(...),
    camera_id: str = Form(...),
    max_frames: int | None = Form(
        None, description="Optional hard cap on frames processed, for a faster demo run."
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    CCTV video upload -> real detection/OCR -> persisted observations.

    Reuses pipeline.run_video_to_db() end to end (the same vehicle
    detector + plate detector + OCR + tracking used everywhere else in
    this repo) - nothing here reimplements detection, OCR, or analytics.
    Processed synchronously: demo clips are short enough that this is
    simpler and more honest than a fake progress bar over a background
    job, and every other endpoint in this codebase is synchronous too.
    Duration is bounded (see _MAX_VIDEO_DURATION_SECONDS) specifically so
    that stays true for whatever gets uploaded here.
    """
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail=f"Unknown camera id: {camera_id}")

    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format '{ext or 'unknown'}'. "
                   f"Allowed: {', '.join(sorted(_ALLOWED_VIDEO_EXTENSIONS))}",
        )

    # Save under a SERVER-GENERATED name, never the client-provided filename
    # (path traversal / arbitrary-write hardening) - only the validated
    # extension is carried over.
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{ext}"
    temp_path = str(_UPLOAD_DIR / safe_name)

    bytes_written = 0
    try:
        with open(temp_path, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Video exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB demo upload limit.",
                    )
                out.write(chunk)
    except HTTPException:
        _cleanup(temp_path)
        raise
    except Exception as e:
        logger.exception("Failed to read uploaded video for camera_id=%r", camera_id)
        _cleanup(temp_path)
        raise HTTPException(status_code=400, detail="Could not read uploaded file. Please try a different file.")

    if bytes_written == 0:
        _cleanup(temp_path)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Real validation, not just trusting the extension: confirm this is a
    # video OpenCV can actually decode, and read its real duration up front
    # so a video far too long for a synchronous demo request is rejected
    # with a clear reason instead of hanging the request for minutes.
    cap = cv2.VideoCapture(temp_path)
    if not cap.isOpened():
        cap.release()
        _cleanup(temp_path)
        raise HTTPException(status_code=400, detail="Could not decode this file as a video.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    duration_seconds = (frame_count / fps) if fps > 0 else 0

    if duration_seconds > _MAX_VIDEO_DURATION_SECONDS:
        _cleanup(temp_path)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Video is ~{round(duration_seconds)}s long, over the "
                f"{_MAX_VIDEO_DURATION_SECONDS}s demo-mode limit for synchronous "
                f"processing. Trim the clip and try again."
            ),
        )

    cam = CAMERAS[camera_id]

    try:
        vehicle_detector = _get_vehicle_detector()
    except Exception as e:
        logger.exception("Vehicle detector initialization failed")
        _cleanup(temp_path)
        raise HTTPException(
            status_code=503,
            detail="Vehicle detector is unavailable right now. Please try again shortly.",
        )

    plate_detector = _get_plate_detector()
    ocr = _get_ocr() if plate_detector is not None else None

    store = ObservationStore()
    start = time.time()
    try:
        records = pipeline_run_video_to_db(
            temp_path, vehicle_detector, plate_detector, ocr,
            camera_id, cam["lat"], cam["long"], store,
            fps_assumed=fps if fps > 0 else 25,
        )
    except Exception as e:
        logger.exception("Video processing failed for camera_id=%r", camera_id)
        raise HTTPException(status_code=500, detail="Video processing failed. Please try again.")
    finally:
        store.close()
        _cleanup(temp_path)

    processing_duration_seconds = round(time.time() - start, 2)

    plates_detected = sum(1 for r in records if r.get("plate_bbox"))
    plates_recognized = sum(
        1 for r in records
        if r.get("plate_text") and r.get("plate_text") != "unavailable"
    )

    return {
        "camera_id": camera_id,
        "camera_name": cam["name"],
        "video_filename": filename,
        "plate_detector_available": plate_detector is not None,
        "ocr_available": ocr is not None,
        "statistics": {
            "frames_processed": frame_count,
            "video_duration_seconds": round(duration_seconds, 1),
            "vehicles_detected": len(records),
            "plates_detected": plates_detected,
            "plates_recognized": plates_recognized,
            "observations_stored": len(records),
            "processing_duration_seconds": processing_duration_seconds,
        },
        "observations": [
            {
                "track_id": r.get("track_id"),
                "vehicle_type": r.get("vehicle_type"),
                "plate_text": r.get("plate_text") if r.get("plate_text") != "unavailable" else None,
                "plate_status": (
                    "unavailable" if ocr is None and plate_detector is not None else
                    "no_plate_detected" if not r.get("plate_bbox") else
                    "recognized" if r.get("plate_text") not in (None, "unavailable") else
                    "detected_not_read"
                ),
                "ocr_confidence": r.get("ocr_confidence"),
                "plate_confidence": r.get("plate_confidence"),
                "vehicle_confidence": r.get("vehicle_confidence"),
                "timestamp": r.get("timestamp"),
                "frame_index": r.get("frame_index"),
                "direction": r.get("direction"),
                "plate_crop_url": _plate_crop_url(r.get("plate_crop_path")),
            }
            for r in records
        ],
    }


def _cleanup(path):
    """Uploaded video files are temporary demo input, not something to keep
    around after processing - delete regardless of success/failure."""
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def pipeline_run_video_to_db(*args, **kwargs):
    """Thin import indirection so this module doesn't import pipeline.py
    (and, transitively, ultralytics/torch) at backend startup - only when
    the ingest-video endpoint is actually first called."""
    from pipeline import run_video_to_db
    return run_video_to_db(*args, **kwargs)
