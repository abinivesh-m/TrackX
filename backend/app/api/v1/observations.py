"""
Observations API routes
"""

import asyncio
import base64
import logging
import os
import tempfile
import threading
import time
import uuid

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
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
from app.core.config import settings

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
_vehicle_detector_init_attempted = False
_vehicle_detector_init_error = None  # real exception text, or None if never failed

_plate_detector = None
_plate_detector_init_attempted = False
_plate_detector_init_error = None  # real reason (no weights file found, or a real
                                    # construction exception), or None if never failed

_ocr = None
_ocr_init_attempted = False
# _ocr's own real failure reason is tracked by recognition.ocr_reader.LAST_OCR_INIT_ERROR
# (set at the moment try_init_ocr() runs) rather than duplicated here.


def _get_vehicle_detector():
    """Lazy singleton - constructing YOLO takes real time; do it once per
    process, not once per request.

    SIH26127 "Final Demo Hardening" audit (2026-09-10): only attempted
    once now (matching _get_plate_detector()/_get_ocr()'s pattern) - a
    permanently-broken weights path used to be retried, and its real
    exception re-raised, on EVERY single call (every upload, every webcam
    frame's session start), which is both slow and means a caller that
    catches the exception once still has no cheap way to learn the reason
    on a later call. The real exception text is preserved in
    _vehicle_detector_init_error either way - see get_model_status()
    below, the single source of truth backend/app/api/v1/health.py's
    check_models() and this module's webcam-stream endpoint both now read
    instead of maintaining their own separate (and previously fabricated)
    opinion about whether this model is actually available."""
    global _vehicle_detector, _vehicle_detector_init_attempted, _vehicle_detector_init_error
    if _vehicle_detector is None and not _vehicle_detector_init_attempted:
        _vehicle_detector_init_attempted = True
        try:
            from detection.vehicle_detector import VehicleDetector
            # SIH26127 (2026-09-15): was hardcoded to "yolov8n.pt" (the
            # generic stock COCO model) even though settings.VEHICLE_WEIGHTS
            # already resolves to the real, custom-trained
            # models/best_vehicle.pt (YOLOv11n, 100 epochs, mAP50=0.972 on
            # its own val split) whenever that file is present on disk - see
            # app/core/config.py's _resolve_vehicle_weights(). This was
            # simply never read here, so the trained model sat on disk
            # unused all session. Falls back to yolov8n.pt automatically
            # (via the same resolver) on a checkout that doesn't have the
            # weight file yet.
            _vehicle_detector = VehicleDetector(model_path=settings.VEHICLE_WEIGHTS)
            _vehicle_detector_init_error = None
        except Exception as e:
            _vehicle_detector_init_error = f"{type(e).__name__}: {e}"
            logger.exception("Vehicle detector (%s) failed to initialize", settings.VEHICLE_WEIGHTS)
    return _vehicle_detector


def _get_plate_detector():
    """SIH26127 audit fix: this used to construct PlateDetector(weights=...)
    with no try/except at all - a real construction failure (corrupt
    weights file, an incompatible ultralytics/torch version, etc.) would
    propagate uncaught out of every single call site, including the
    webcam-stream WebSocket handler, killing that live session outright
    with no message ever sent to the browser (the frontend would just see
    the socket close with no error text). Now matches the same
    attempt-once-and-remember-the-real-reason pattern as _get_ocr()."""
    global _plate_detector, _plate_detector_init_attempted, _plate_detector_init_error
    if _plate_detector is None and not _plate_detector_init_attempted:
        _plate_detector_init_attempted = True
        try:
            from demo.visual_pipeline import find_plate_weights
            from detection.detect_plates import PlateDetector
            weights = find_plate_weights()
            if weights:
                _plate_detector = PlateDetector(weights=weights)
                _plate_detector_init_error = None
            else:
                _plate_detector_init_error = (
                    "No fine-tuned plate-detector weights file was found (searched the "
                    "locations demo/visual_pipeline.find_plate_weights() checks, e.g. "
                    "models/best_plate_detector.pt). Plate detection - and OCR, which "
                    "depends on it - are unavailable until a weights file is present."
                )
        except Exception as e:
            _plate_detector_init_error = f"{type(e).__name__}: {e}"
            logger.exception("Plate detector failed to initialize")
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


def get_model_status(trigger_load: bool = True) -> dict:
    """Real, current, per-component status for the three models the live
    pipeline actually uses - vehicle detector, plate detector, OCR - each
    backed by an ACTUAL attempted construction of the exact singleton
    object every upload/webcam session uses (not a hardcoded guess, not
    'is the package importable'). This is the single source of truth for
    both backend/app/api/v1/health.py's check_models() and the
    webcam-stream WebSocket's "ready" message, so the two can never again
    disagree with each other or with what the live pipeline is actually
    using.

    SIH26127 "Final Demo Hardening" audit (2026-09-10) - this replaces a
    real, confirmed bug: check_models() used to hardcode
    yolo_vehicle/yolo_plate as `True` ("Usually available", never actually
    checked) and treat "the paddleocr package is importable" as equivalent
    to "OCR actually works" - so GET /health could report the AI engine as
    "healthy" while the real webcam demo's OCR was genuinely unavailable,
    producing the self-contradictory "healthy - unavailable" status an
    operator could actually see in the Admin Console.

    trigger_load (SIH26127 OOM hotfix, 2026-09-29): default True preserves
    the original behavior for every REAL detection call site (video
    upload, webcam-stream's "ready" message) - an actual demo action
    should load whatever models it needs. But this function was ALSO being
    called, via check_models(), from the passive health-check endpoints
    that DashboardPage.tsx's System Status panel hits on every routine
    page view - meaning just opening the dashboard was enough to force
    YOLO + all three PaddleOCR models into memory. On Render's free tier
    (512MB total) that combination actually exceeded the limit and got the
    whole process OOM-killed - confirmed via Render's own event log
    ("Ran out of memory (used over 512MB)"), not a guess. Passing
    trigger_load=False (used by backend/app/main.py's health_check() and
    backend/app/api/v1/health.py's deep_health_check()/system_status())
    makes those endpoints PEEK at whatever has already been loaded by a
    real action, instead of forcing a fresh, crash-prone load themselves.
    """
    # SIH26127 "OCR + Webcam Detection Must Actually Work" (2026-09-10)
    # follow-up bug found while building the OCR smoke test: this used to
    # do `from recognition.ocr_reader import LAST_OCR_INIT_ERROR`, which
    # binds a LOCAL snapshot of that module attribute's value AT THE TIME
    # OF THIS IMPORT LINE - i.e. BEFORE _get_ocr() below has run and had
    # any chance to set it. On the very first call to get_model_status()
    # in a fresh process (exactly the case that matters: the first /health
    # check or the first webcam-stream "ready" message after the server
    # starts), that snapshot was always the pre-attempt value (None), so
    # the real, specific reason (package not installed / CDN unreachable /
    # etc.) was thrown away and replaced by the generic "unknown reason -
    # check server logs" fallback below - on every machine where OCR
    # genuinely fails on first use. Importing the module object itself
    # (not the name) and reading the attribute off it AFTER _get_ocr() has
    # actually run fixes this: module attribute lookups are live, so this
    # always reflects whatever try_init_ocr() most recently set.
    import recognition.ocr_reader as _ocr_reader_module

    _not_yet_reason = (
        "Not checked yet - this deployment's memory budget can't hold YOLO + "
        "PaddleOCR at once just to answer a routine status check, so models "
        "load on the first real detection/OCR action (video upload or webcam "
        "start) instead of on every page view."
    )

    if trigger_load:
        vehicle_detector = _get_vehicle_detector()
        plate_detector = _get_plate_detector()
        ocr = _get_ocr() if plate_detector is not None else None
    else:
        # Peek only - read whatever the singletons already are without
        # attempting construction. If a real action already ran (or is
        # running) in this process, this reflects that truthfully.
        vehicle_detector = _vehicle_detector
        plate_detector = _plate_detector
        ocr = _ocr if _ocr_init_attempted else None

    vehicle_reason = _vehicle_detector_init_error
    if vehicle_reason is None and not _vehicle_detector_init_attempted:
        vehicle_reason = _not_yet_reason

    plate_reason = _plate_detector_init_error
    if plate_reason is None and not _plate_detector_init_attempted:
        plate_reason = _not_yet_reason

    ocr_reason = None
    if ocr is None:
        if not _plate_detector_init_attempted:
            ocr_reason = _not_yet_reason
        elif plate_detector is None:
            ocr_reason = "OCR was never attempted because the plate detector is unavailable (see plate_detector reason)."
        elif not _ocr_init_attempted:
            ocr_reason = _not_yet_reason
        else:
            ocr_reason = (
                _ocr_reader_module.LAST_OCR_INIT_ERROR
                or "OCR initialization failed for an unknown reason - check server logs."
            )

    return {
        "vehicle_detector": {"available": vehicle_detector is not None, "reason": vehicle_reason},
        "plate_detector": {"available": plate_detector is not None, "reason": plate_reason},
        "ocr": {"available": ocr is not None, "reason": ocr_reason},
    }


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


def _annotated_video_url(annotated_video_path):
    """Same idea as _plate_crop_url, for the real annotated output VIDEO
    produced by pipeline.write_annotated_video() (see app/main.py's
    /media/annotated-videos mount). Returns None (never a broken link) if
    the video wasn't produced this run."""
    if not annotated_video_path:
        return None
    try:
        if not os.path.isfile(annotated_video_path):
            return None
        return f"/media/annotated-videos/{os.path.basename(annotated_video_path)}"
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
    """Get observations with optional filtering.

    SIH26127 "Latest Detections panel" fix (2026-09-14): this endpoint was
    calling store.all_observations() with its default real_only=False, and
    never sorted - all_observations() itself orders ASCENDING by timestamp,
    so a plain [:limit] slice returned the OLDEST rows in the table, not
    the most recent. For CAM_01/CAM_02 that meant this endpoint returned
    data_source='DEMO_SYNTHETIC' seed rows from demo/seed_demo_data.py
    (2026-09-10) ahead of and instead of genuine same-day REAL_INFERENCE
    observations - confirmed live via a direct API query: CAM_01's first 8
    rows here were all DEMO_SYNTHETIC (id 1,20,59,56,5,10,25,64), while its
    real observations (id 85+) never appeared within limit=8. The frontend's
    only caller of this endpoint (CameraLivePage.tsx's "Latest Detections"
    panel, which is presented to the user as real live-camera evidence) was
    therefore showing fabricated demo data, not real detections - exactly
    what this project's requirements explicitly forbid. Fixed the same way
    /recent already sorts, plus real_only=True (the filter
    all_observations() already supports for exactly this purpose, per its
    own docstring, just not applied here) so a seeded demo row can never be
    presented through this endpoint as if it were a real detection.
    """
    try:
        store = ObservationStore()
        all_obs = store.all_observations(real_only=True)
        all_obs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

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
    """Get recent observations.

    Same real_only fix as get_observations() above and for the same
    reason: DashboardPage.tsx's "recent activity" feed is the caller here,
    and a demo-seeded row is not a real recent detection no matter how
    recently it was seeded.
    """
    try:
        store = ObservationStore()
        all_obs = store.all_observations(real_only=True)

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


@router.get("/camera-source/{camera_id}")
def get_camera_source_status(
    camera_id: str,
    probe: bool = Query(False, description="Also attempt a real, time-bounded RTSP connection and report reachability."),
    current_user: User = Depends(get_current_user),
):
    """
    SIH26127 real CP PLUS/RTSP camera integration: reports, honestly,
    whether `camera_id` currently resolves to a real RTSP camera
    (TRACKX_RTSP_<camera_id>_* configured - see network/rtsp_camera.py) or
    to the pre-existing local-video-file simulation, without ever
    exposing a credential - `display_name`/`source_label` are already
    redacted. `configured` (env vars present) and `reachable` (a live
    connection actually succeeded, only checked when `probe=true`) are
    reported separately and are never conflated: a camera can be
    configured but offline, or not configured at all.
    """
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail=f"Unknown camera id: {camera_id}")

    from network.rtsp_camera import (
        resolve_camera_source, resolve_rtsp_url, resolve_stream_options, probe_rtsp_connectivity,
        RTSPConfigError, NoCameraSourceAvailable,
    )

    try:
        configured_url = resolve_rtsp_url(camera_id)
        stream_options = resolve_stream_options(camera_id)
    except RTSPConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = {
        "camera_id": camera_id,
        "configured": configured_url is not None,
        "reachable": None,   # only known when probe=true
        "probe_detail": None,
    }

    try:
        source = resolve_camera_source(camera_id)
        result["source"] = source.kind
        result["is_real_camera"] = source.is_real_camera
        result["display_name"] = source.display_name
        result["source_label"] = source.label
        result["scheme"] = source.scheme or None
        result["needs_ffmpeg_bridge"] = source.needs_ffmpeg_bridge
        result["transport"] = source.transport if source.is_real_camera else None
        result["tls_verify"] = source.tls_verify if source.is_real_camera else None
        # SIH26127: TRACKX_RTSP_<camera_id>_ROTATION, only ever meaningful
        # (and only ever actually applied - see network/ffmpeg_frame_source.py)
        # for a real camera on the ffmpeg-bridge path; 0 elsewhere is the
        # true "no rotation configured/applicable" state, not a guess.
        result["rotation"] = source.rotation if source.needs_ffmpeg_bridge else 0
    except NoCameraSourceAvailable as e:
        result["source"] = None
        result["is_real_camera"] = False
        result["display_name"] = None
        result["source_label"] = str(e)
        result["scheme"] = None
        result["needs_ffmpeg_bridge"] = False
        result["transport"] = None
        result["tls_verify"] = None
        result["rotation"] = 0

    if probe and configured_url is not None:
        probe_result = probe_rtsp_connectivity(
            configured_url, transport=stream_options.transport, tls_verify=stream_options.tls_verify,
        )
        result["reachable"] = probe_result["reachable"]
        result["probe_detail"] = probe_result["detail"]

    return result


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

    vehicle_detector = _get_vehicle_detector()
    if vehicle_detector is None:
        raise HTTPException(
            status_code=503,
            detail=f"Vehicle detector is unavailable: {_vehicle_detector_init_error or 'unknown reason - check server logs'}",
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
    # BUG FIX (2026-09-14, verified against a real run): this and the
    # "plate_text" reads a few lines below were keyed on "plate_text" - a
    # key demo/visual_pipeline.py's build_plate_fields()/process_image()
    # NEVER sets. That module only ever sets "raw_plate_text" and
    # "normalized_plate_text" (see its own returned dict, and
    # database/observation_store.py's INSERT, which correctly reads
    # "normalized_plate_text" - that mismatch is exactly why the DB ended
    # up with the right plate text while this endpoint's own JSON response
    # always reported plates_recognized=0 / "Plate detected, text not
    # read" regardless of whether OCR actually succeeded. Confirmed live:
    # processing CAM_02's real photo produced observation id 986 in the DB
    # with plate_text="TN09CQ1234" at ocr_confidence=0.949 (a real,
    # correct OCR read - the AI pipeline was never broken), while this
    # response was telling the UI "text not read" for that exact same run
    # because o.get("plate_text") was always None. Fixed by reading the
    # field that is actually populated.
    plates_recognized = sum(
        1 for o in observations
        if o.get("normalized_plate_text") and o.get("normalized_plate_text") != "unavailable"
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
                "plate_text": o.get("normalized_plate_text") if o.get("normalized_plate_text") != "unavailable" else None,
                "plate_status": (
                    "unavailable" if ocr is None and plate_detector is not None else
                    "no_plate_detected" if not o.get("plate_bbox") else
                    "recognized" if o.get("normalized_plate_text") not in (None, "unavailable") else
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
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
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

    vehicle_detector = _get_vehicle_detector()
    if vehicle_detector is None:
        _cleanup(temp_path)
        raise HTTPException(
            status_code=503,
            detail=f"Vehicle detector is unavailable: {_vehicle_detector_init_error or 'unknown reason - check server logs'}",
        )

    plate_detector = _get_plate_detector()
    ocr = _get_ocr() if plate_detector is not None else None

    store = ObservationStore()
    start = time.time()
    try:
        records, annotated_video_path = pipeline_run_video_to_db(
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
    # Real measured throughput, not a display estimate - frames actually
    # decoded/processed divided by wall-clock time actually spent.
    processing_fps = round(frame_count / processing_duration_seconds, 2) if processing_duration_seconds > 0 else 0.0

    plates_detected = sum(1 for r in records if r.get("plate_bbox"))
    # "recognized" here means the SAME thing the pipeline itself decided
    # (see pipeline._plate_status_for_track) - a low-confidence OCR read is
    # NOT counted as recognized, it's surfaced separately below so the UI
    # can show "verification required" instead of presenting it as fact.
    plates_recognized = sum(1 for r in records if r.get("plate_status") == "recognized")
    plates_low_confidence = sum(1 for r in records if r.get("plate_status") == "low_confidence")
    # "Adaptive Multi-Frame ANPR Intelligence" (SIH26127): VERIFIED means
    # plate_state's stricter bar - recognized AND backed by enough
    # independent frames (see pipeline._plate_state_for_track) - a
    # single lucky high-confidence frame is TENTATIVE, not VERIFIED.
    plates_verified = sum(1 for r in records if r.get("plate_state") == "VERIFIED")
    plates_tentative = sum(1 for r in records if r.get("plate_state") == "TENTATIVE")

    return {
        "camera_id": camera_id,
        "camera_name": cam["name"],
        "video_filename": filename,
        "plate_detector_available": plate_detector is not None,
        "ocr_available": ocr is not None,
        "annotated_video_url": _annotated_video_url(annotated_video_path),
        "statistics": {
            "frames_processed": frame_count,
            "video_duration_seconds": round(duration_seconds, 1),
            "video_width": video_width,
            "video_height": video_height,
            "vehicles_detected": len(records),
            "active_tracks": len(records),
            "plates_detected": plates_detected,
            "plates_recognized": plates_recognized,
            "plates_low_confidence": plates_low_confidence,
            "plates_verified": plates_verified,
            "plates_tentative": plates_tentative,
            "observations_stored": len(records),
            "processing_duration_seconds": processing_duration_seconds,
            "processing_fps": processing_fps,
        },
        "observations": [
            {
                "track_id": r.get("track_id"),
                "vehicle_type": r.get("vehicle_type"),
                "plate_text": r.get("plate_text") if r.get("plate_status") in ("recognized", "low_confidence") else None,
                "plate_status": r.get("plate_status"),
                "ocr_confidence": r.get("ocr_confidence"),
                "plate_confidence": r.get("plate_confidence"),
                "vehicle_confidence": r.get("vehicle_confidence"),
                "timestamp": r.get("timestamp"),
                "frame_index": r.get("frame_index"),
                "first_seen_frame": r.get("first_seen_frame"),
                "last_seen_frame": r.get("last_seen_frame"),
                "first_seen_timestamp": r.get("first_seen_timestamp"),
                "last_seen_timestamp": r.get("last_seen_timestamp"),
                "direction": r.get("direction"),
                "plate_crop_url": _plate_crop_url(r.get("plate_crop_path")),
                # "Adaptive Multi-Frame ANPR Intelligence" evidence fields -
                # real measured quality/preprocessing/temporal-fusion data
                # (see pipeline.run_video_to_db / recognition.plate_quality),
                # never invented. plate_state is the coarse judge-facing
                # rollup; the rest is the explainability behind it.
                "plate_state": r.get("plate_state"),
                "plate_quality_score": r.get("plate_quality_score"),
                "blur_score": r.get("blur_score"),
                "brightness_score": r.get("brightness_score"),
                "contrast_score": r.get("contrast_score"),
                "preprocessing_mode": r.get("preprocessing_mode"),
                "ocr_candidate_count": r.get("ocr_candidate_count"),
                "temporal_support": r.get("temporal_support"),
                "final_fusion_score": r.get("final_fusion_score"),
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


# ---------------------------------------------------------------------------
# Live streaming demo (SIH26127 "real video streaming" priority)
#
# HONESTY NOTE (see docs/LIVE_STREAMING.md for the full version): there is
# no real CCTV/RTSP camera in this environment. This endpoint does NOT fake
# that - it genuinely runs pipeline.run_video_to_db() (the exact same
# detector/plate-detector/OCR/tracker/temporal-fusion code every other
# endpoint in this file uses) over a real video already sitting in this
# camera's data/cameras/<CAM_ID>/videos/ folder, but instead of waiting for
# the whole video to finish and returning one final JSON response (like
# /ingest-video and /process-camera do), it pushes each frame's REAL,
# freshly-computed detections to the client over a WebSocket AS THEY ARE
# PRODUCED - the same experience a live camera feed would give, built from
# genuinely running inference frame by frame rather than a canned replay.
# Nothing here is pre-baked: every box, every live plate-text guess, and
# every stat is read straight out of pipeline.run_video_to_db()'s new
# on_frame callback (pipeline.py), the same real per-frame data the batch
# endpoints already compute - this just surfaces it live instead of
# discarding it until the end.
# ---------------------------------------------------------------------------

_LIVE_STREAM_MAX_SIDE = 640  # resize before JPEG-encoding - bandwidth, not accuracy (detection already ran on the full frame)
_LIVE_STREAM_JPEG_QUALITY = 70


def _draw_live_annotations(frame, live_vehicles):
    """Draws real per-frame detections onto a copy of the real frame -
    reused annotation logic in spirit with demo/annotate.py, kept local and
    minimal here since this only needs box + a one-line label, not the
    full plate-status color coding that module does for the batch UI."""
    annotated = frame.copy()
    for v in live_vehicles:
        x1, y1, x2, y2 = [int(c) for c in v["bbox"]]
        color = (0, 210, 0)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        label = f"#{v['track_id']} {v['vehicle_type']}"
        if v.get("plate_text_live"):
            label += f" | {v['plate_text_live']}"
        cv2.putText(
            annotated, label, (x1, max(14, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
        )
    h, w = annotated.shape[:2]
    if max(h, w) > _LIVE_STREAM_MAX_SIDE:
        scale = _LIVE_STREAM_MAX_SIDE / max(h, w)
        annotated = cv2.resize(annotated, (int(w * scale), int(h * scale)))
    return annotated


# SIH26127 real bug fix (2026-09-15, live-stream WebSocket crash): the
# webcam-stream endpoint below already enforces "only one live session per
# detector instance at a time" (see _webcam_session_lock) because
# VehicleDetector.track_frame()'s own docstring says concurrent calls on the
# SAME detector instance "would interleave and corrupt both sessions' track
# IDs" - but live_stream() never got the same protection. Real, observed
# crash this session, straight from the backend traceback: two
# /live-stream/CAM_01 WebSocket connections were accepted a few milliseconds
# apart (React 18 StrictMode's deliberate dev-mode double-mount, or a fast
# manual reconnect), both racing to call track_frame()/track_video() on the
# SAME shared _get_vehicle_detector() singleton - and ultralytics'
# AutoBackend.setup_model() tried to fuse() an already-fused model on the
# second overlapping call, raising "AttributeError: 'Conv' object has no
# attribute 'bn'", which crashed that session's worker thread and then threw
# again trying to send an error on the now-broken WebSocket. Keyed per
# camera_id (unlike the single global webcam lock) since two DIFFERENT real
# cameras use independent frame sources/detector calls and streaming them
# concurrently is fine - only two sessions on the SAME camera_id actually
# share a detector call path and need to be serialized.
_live_stream_sessions_lock = threading.Lock()
_live_stream_active_cameras: set = set()


@router.websocket("/live-stream/{camera_id}")
async def live_stream(websocket: WebSocket, camera_id: str):
    """
    Real, live, frame-by-frame video processing over a WebSocket.

    SIH26127 real CP PLUS/RTSP camera integration (network/rtsp_camera.py):
    if TRACKX_RTSP_<camera_id>_* env vars configure a real camera, this
    streams from it directly (rtsp:// URL, read live by the same
    ultralytics track() call every source already goes through) - if not,
    it falls back to the pre-existing local-video-file simulation exactly
    as before. "source"/"is_real_camera" in the "started" message say,
    honestly, which one actually happened.

    Protocol (JSON messages, server -> client):
      {"type": "started", "video": "<display name>", "camera_id": "...",
       "source": "rtsp" | "simulated_video", "is_real_camera": bool,
       "source_label": "<human-readable, credential-free>"}
      {"type": "frame", "frame_idx": int, "jpeg_b64": "<base64 jpeg>",
       "vehicles_in_frame": int, "elapsed_seconds": float,
       "fps_so_far": float}
      {"type": "done", "tracks": int, "plates_verified": int,
       "plates_tentative": int, "duration_seconds": float}
      {"type": "error", "detail": "..."}

    The client may disconnect at any point; the background pipeline run is
    signaled to stop within one frame (see stop_event below) rather than
    running to completion unwatched.
    """
    await websocket.accept()

    if camera_id not in CAMERAS:
        await websocket.send_json({"type": "error", "detail": f"Unknown camera id: {camera_id}"})
        await websocket.close()
        return

    # SIH26127 real CP PLUS/RTSP camera integration: real camera first (if
    # TRACKX_RTSP_<camera_id>_* is configured - see network/rtsp_camera.py),
    # honest fallback to the pre-existing local-video-file simulation
    # otherwise. Ultralytics' own source loader is what actually knows how
    # to read an rtsp:// URL vs a file path - nothing downstream of
    # `video_path` (pipeline.run_video_to_db / vehicle_detector.track_video)
    # had to change for this.
    from network.rtsp_camera import resolve_camera_source, RTSPConfigError, NoCameraSourceAvailable

    try:
        source = resolve_camera_source(camera_id)
    except RTSPConfigError as e:
        await websocket.send_json({"type": "error", "detail": str(e)})
        await websocket.close()
        return
    except NoCameraSourceAvailable:
        await websocket.send_json({
            "type": "error",
            "detail": f"No real camera configured and no local media folder for '{camera_id}'. "
                      f"Configure TRACKX_RTSP_{camera_id}_HOST (real CP PLUS camera) or add a "
                      f"video under data/cameras/{camera_id}/videos/ (simulated feed).",
        })
        await websocket.close()
        return

    video_path = source.path

    # _get_vehicle_detector() attempts construction only once and remembers
    # the real failure reason rather than raising (see its docstring).
    vehicle_detector = _get_vehicle_detector()
    if vehicle_detector is None:
        await websocket.send_json({
            "type": "error",
            "detail": f"Vehicle detector is unavailable: {_vehicle_detector_init_error or 'unknown reason - check server logs'}",
        })
        await websocket.close()
        return

    plate_detector = _get_plate_detector()
    ocr = _get_ocr() if plate_detector is not None else None
    cam = CAMERAS[camera_id]

    loop = asyncio.get_event_loop()
    queue: "asyncio.Queue[dict]" = asyncio.Queue(maxsize=4)
    stop_event = threading.Event()
    start_time = time.time()

    await websocket.send_json({
        "type": "started",
        # "video" kept for backwards compatibility with existing clients -
        # for a real RTSP camera this is the same credential-free
        # display_name shown by source_label, not a file basename.
        "video": source.display_name,
        "camera_id": camera_id,
        "source": source.kind,          # "rtsp" (real camera) or "simulated_video"
        "is_real_camera": source.is_real_camera,
        "source_label": source.label,
    })

    def _put(msg):
        """Runs on the worker thread - hands a message to the asyncio
        queue on the event-loop thread and blocks (briefly) for backpressure,
        so a slow/stalled client naturally slows down real inference too,
        instead of buffering unboundedly in memory."""
        try:
            fut = asyncio.run_coroutine_threadsafe(queue.put(msg), loop)
            fut.result(timeout=10)
            return True
        except Exception:
            return False

    def on_frame(frame_idx, frame, live_vehicles, elapsed):
        if stop_event.is_set():
            return False
        annotated = _draw_live_annotations(frame, live_vehicles)
        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, _LIVE_STREAM_JPEG_QUALITY])
        if not ok:
            return True
        fps_so_far = round((frame_idx + 1) / elapsed, 2) if elapsed > 0 else 0.0
        return _put({
            "type": "frame",
            "frame_idx": frame_idx,
            "jpeg_b64": base64.b64encode(buf.tobytes()).decode("ascii"),
            "vehicles_in_frame": len(live_vehicles),
            "elapsed_seconds": round(elapsed, 2),
            "fps_so_far": fps_so_far,
        })

    # SIH26127 real CP PLUS camera integration: a real camera's RTSPS
    # (RTSP-over-TLS) source can't be read through ultralytics/OpenCV's own
    # stream loader (see network/ffmpeg_frame_source.py's docstring) -
    # open_camera_frames() supplies the same (frame_idx, frame,
    # vehicle_detections) tuples via a real ffmpeg subprocess instead, fed
    # into pipeline.run_video_to_db()'s new frame_source= parameter. A
    # plain rtsp:// real camera or a simulated_video source needs none of
    # this - frame_source stays None and behavior is exactly as before.
    frame_source = None
    if source.needs_ffmpeg_bridge:
        from network.rtsp_camera import open_camera_frames
        frame_source = open_camera_frames(source, vehicle_detector)

    def worker():
        store = ObservationStore()
        try:
            records, _ = pipeline_run_video_to_db(
                video_path, vehicle_detector, plate_detector, ocr,
                camera_id, cam["lat"], cam["long"], store,
                write_annotated=False, on_frame=on_frame, frame_source=frame_source,
            )
            plates_verified = sum(1 for r in records if r.get("plate_state") == "VERIFIED")
            plates_tentative = sum(1 for r in records if r.get("plate_state") == "TENTATIVE")
            _put({
                "type": "done",
                "tracks": len(records),
                "plates_verified": plates_verified,
                "plates_tentative": plates_tentative,
                "duration_seconds": round(time.time() - start_time, 2),
            })
        except Exception as e:
            logger.exception("Live stream processing failed for camera_id=%r", camera_id)
            _put({"type": "error", "detail": "Live processing failed. Please try again."})
        finally:
            store.close()

    # See _live_stream_sessions_lock's comment above this function: reject a
    # second concurrent session for the SAME camera_id up front (clear,
    # honest error) rather than letting both race on the shared detector
    # instance and crash. A rejected session never starts a worker thread,
    # so it never needs to release this - only the one that actually
    # acquired it does, in the finally block below.
    acquired_live_lock = False
    with _live_stream_sessions_lock:
        if camera_id not in _live_stream_active_cameras:
            _live_stream_active_cameras.add(camera_id)
            acquired_live_lock = True

    if not acquired_live_lock:
        await websocket.send_json({
            "type": "error",
            "detail": f"A live stream session for {camera_id} is already running. "
                      f"Close the other tab/session before starting a new one.",
        })
        await websocket.close()
        return

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    try:
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
            if msg["type"] in ("done", "error"):
                break
    except WebSocketDisconnect:
        logger.info("Live stream client disconnected for camera_id=%r", camera_id)
    finally:
        # Signal the worker thread to stop as soon as it checks (within one
        # frame) - a disconnected client should not leave real inference
        # running unwatched in the background.
        stop_event.set()
        with _live_stream_sessions_lock:
            _live_stream_active_cameras.discard(camera_id)
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Live WEBCAM demo (SIH26127 "Live Webcam + Phone Number-Plate Demo")
#
# Unlike /live-stream/{camera_id} above (which reads a real video file that
# already sits on the SERVER's disk and pushes its frames out), this
# endpoint is fed frames captured live in the browser (getUserMedia() ->
# canvas -> JPEG) from the operator's own laptop webcam - a genuinely live,
# external video source, not a server-side file. Every frame received here
# is run through the exact same real inference used everywhere else in this
# codebase (see live_webcam.py's module docstring for the precise list of
# reused, non-reimplemented functions): YOLO vehicle detection, ByteTrack,
# plate detection, adaptive preprocessing, PaddleOCR, and the same
# temporal-fusion vote + plate-state rollup the CCTV-upload flow uses.
#
# HONESTY NOTE: this endpoint does not know or claim anything about camera
# FPS - it only ever reports how long ITS OWN real inference took on each
# frame it was actually given (see live_webcam.LiveWebcamSession's
# timing_ms). The frontend is responsible for keeping "camera FPS" (how
# often the browser captures a frame) and "processing FPS" (how often this
# endpoint can actually finish a frame) visibly distinct - never averaged
# together or presented as one number.
#
# Reliability: because ultralytics' persist=True ByteTrack state lives on
# the shared, lazily-constructed VehicleDetector singleton
# (_get_vehicle_detector()), two concurrent live webcam sessions on that
# same singleton would interleave and corrupt each other's track IDs. This
# endpoint deliberately supports only ONE ACTIVE SESSION AT A TIME and
# rejects a second concurrent connection with a clear error rather than
# silently producing corrupted results - an explicit, honest limitation for
# a single-operator physical demo tool, not an oversight.
# ---------------------------------------------------------------------------

_webcam_session_lock = threading.Lock()
_webcam_session_active = False

_WEBCAM_MAX_CONSECUTIVE_FRAME_ERRORS = 10

# SIH26127 "Final Demo Hardening" audit (2026-09-10): real, observed failure
# mode - a browser tab can vanish (hard refresh, laptop sleep, network drop,
# OS killing the tab) without ever delivering a clean WebSocket close frame.
# Starlette's `await websocket.receive_json()` then just hangs forever
# waiting for a message that will never arrive, so the `finally` block that
# releases _webcam_session_active never runs - the ONE-SESSION-AT-A-TIME
# lock (see class docstring below) stays held until the backend process
# itself is restarted. The next real attempt to start a session then gets
# "A live webcam session is already running" even though nothing is
# actually live anymore. This is the confirmed root cause of "webcam opens
# once, then won't open again" without a backend restart in between. Fixed
# by bounding how long a session will wait for the NEXT client message -
# the browser sends a frame roughly every CAPTURE_INTERVAL_MS (500ms, see
# LiveWebcamPage.tsx) while actually live, so any real, live session will
# always beat this deadline by a wide margin; only a genuinely abandoned
# connection ever hits it.
_WEBCAM_IDLE_TIMEOUT_SECONDS = 20


def _decode_jpeg_b64(jpeg_b64: str):
    """Decodes a base64-encoded JPEG (as sent by the browser's
    canvas.toDataURL()/toBlob()) into a real BGR numpy frame, or None if
    the data is missing/corrupt. Never raises - a malformed frame is a
    per-frame error to report to the client, not a reason to kill the
    whole live session."""
    if not jpeg_b64:
        return None
    try:
        raw = base64.b64decode(jpeg_b64, validate=False)
        if not raw:
            return None
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame
    except Exception:
        return None


@router.websocket("/webcam-stream/{camera_id}")
async def webcam_stream(websocket: WebSocket, camera_id: str):
    """
    Real, live, frame-by-frame webcam processing over a WebSocket.

    Protocol (JSON messages):
      client -> server, per captured frame:
        {"type": "frame", "jpeg_b64": "<base64 jpeg>", "client_frame_idx": int}
      client -> server, on stopping:
        {"type": "stop"}

      server -> client, once, right after accept:
        {"type": "ready", "camera_id": "...",
         "plate_detector_available": bool, "plate_detector_reason": str | null,
         "ocr_available": bool, "ocr_reason": str | null}
        (the *_reason fields are the real reason a component is unavailable -
        e.g. "no weights file found" vs. "PaddleOCR could not reach its
        model CDN" - never just a bare boolean; see get_model_status())
      server -> client, one per processed frame:
        {"type": "result", "frame_idx": int, "elapsed_seconds": float,
         "vehicles": [...], "timing_ms": {...}}
      server -> client, on a single bad/failed frame (session stays open):
        {"type": "frame_error", "detail": "..."}  (detail includes the real
        exception when processing itself failed, not just "decode failed")
      server -> client, only if this session cannot proceed at all (including
      after _WEBCAM_IDLE_TIMEOUT_SECONDS with no client message, which also
      releases the single-session lock - see that constant's docstring):
        {"type": "error", "detail": "..."}  (connection is then closed)

    See module-level comment above for why only one session may be active
    at a time.
    """
    await websocket.accept()

    global _webcam_session_active

    acquired = False
    with _webcam_session_lock:
        if not _webcam_session_active:
            _webcam_session_active = True
            acquired = True

    if not acquired:
        await websocket.send_json({
            "type": "error",
            "detail": "A live webcam session is already running. Stop it before starting a new one "
                      "(only one live webcam demo session is supported at a time).",
        })
        await websocket.close()
        return

    frames_processed = 0
    frames_with_vehicles = 0
    try:
        # _get_vehicle_detector() now attempts construction only once and
        # remembers the real failure reason (see its docstring) rather than
        # raising - matching _get_plate_detector()/_get_ocr()'s pattern.
        vehicle_detector = _get_vehicle_detector()
        if vehicle_detector is None:
            await websocket.send_json({
                "type": "error",
                "detail": f"Vehicle detector is unavailable: {_vehicle_detector_init_error or 'unknown reason - check server logs'}",
            })
            await websocket.close()
            return

        plate_detector = _get_plate_detector()
        ocr = _get_ocr() if plate_detector is not None else None
        model_status = get_model_status()

        from live_webcam import LiveWebcamSession
        session = LiveWebcamSession(vehicle_detector, plate_detector, ocr, camera_id)

        # Real per-component reasons (Phase 1/3 diagnostic requirement) -
        # never just a bare boolean the operator can't act on. See
        # get_model_status()'s docstring for why this is now the single
        # source of truth shared with GET /health.
        await websocket.send_json({
            "type": "ready",
            "camera_id": camera_id,
            "plate_detector_available": plate_detector is not None,
            "plate_detector_reason": model_status["plate_detector"]["reason"],
            "ocr_available": ocr is not None,
            "ocr_reason": model_status["ocr"]["reason"],
        })
        logger.info(
            "webcam-stream ready camera_id=%r vehicle_detector=ok plate_detector=%s ocr=%s",
            camera_id, plate_detector is not None, ocr is not None,
        )

        loop = asyncio.get_event_loop()
        consecutive_errors = 0

        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=_WEBCAM_IDLE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning(
                    "webcam-stream camera_id=%r idle for %ss with no client message - "
                    "treating as an abandoned session and releasing the single-session lock.",
                    camera_id, _WEBCAM_IDLE_TIMEOUT_SECONDS,
                )
                try:
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"No frames received for {_WEBCAM_IDLE_TIMEOUT_SECONDS}s - closing this idle session.",
                    })
                except Exception:
                    pass
                break

            msg_type = msg.get("type")

            if msg_type == "stop":
                break

            if msg_type != "frame":
                await websocket.send_json({"type": "frame_error", "detail": f"Unknown message type '{msg_type}'."})
                continue

            frame = _decode_jpeg_b64(msg.get("jpeg_b64"))
            if frame is None or frame.size == 0:
                consecutive_errors += 1
                logger.warning(
                    "webcam-stream camera_id=%r frame %d: JPEG decode failed (empty or corrupt data, "
                    "%d bytes of base64 received)", camera_id, frames_processed,
                    len(msg.get("jpeg_b64") or ""),
                )
                await websocket.send_json({
                    "type": "frame_error",
                    "detail": "Could not decode this frame (empty or corrupt data).",
                })
                if consecutive_errors >= _WEBCAM_MAX_CONSECUTIVE_FRAME_ERRORS:
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"{consecutive_errors} consecutive undecodable frames - stopping this session.",
                    })
                    break
                continue

            consecutive_errors = 0
            try:
                # Real inference is synchronous/CPU-bound - run it off the
                # event loop thread so this connection (and FastAPI's other
                # concurrent requests) don't freeze while a frame is being
                # processed.
                result = await loop.run_in_executor(None, session.process_frame, frame)
            except Exception as e:
                logger.exception("Live webcam frame processing failed for camera_id=%r", camera_id)
                await websocket.send_json({
                    "type": "frame_error",
                    # Real exception surfaced (Phase 1/"MOST IMPORTANT RULE" -
                    # a truthful failure beats a silent one) - this is a
                    # single-operator demo tool, not a public API, so there is
                    # no information-disclosure concern in showing it.
                    "detail": f"Processing this frame failed ({type(e).__name__}: {e}). The session is still live.",
                })
                continue

            frames_processed += 1
            n_vehicles = len(result.get("vehicles") or [])
            if n_vehicles:
                frames_with_vehicles += 1
            # One structured diagnostic line per frame (Phase 1's exact
            # requirement: frame index/shape/dtype, vehicle count, timing) -
            # cheap at demo frame rates (~2/sec), and this is the one place
            # an operator (or a developer reading server logs afterward) can
            # see WHY "0 vehicles" is happening in real time, instead of it
            # being a silent dead end.
            logger.info(
                "webcam-stream camera_id=%r frame=%d shape=%s dtype=%s vehicles=%d "
                "timing_ms=%s", camera_id, result.get("frame_idx"), frame.shape, frame.dtype,
                n_vehicles, result.get("timing_ms"),
            )

            result["type"] = "result"
            await websocket.send_json(result)

    except WebSocketDisconnect:
        logger.info(
            "Webcam stream client disconnected for camera_id=%r (frames_processed=%d, frames_with_vehicles=%d)",
            camera_id, frames_processed, frames_with_vehicles,
        )
    finally:
        with _webcam_session_lock:
            _webcam_session_active = False
        try:
            await websocket.close()
        except Exception:
            pass
