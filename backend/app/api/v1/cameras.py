"""
Camera API routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from network.camera_network import CAMERAS
from database.observation_store import ObservationStore
from intelligence.alerts import CAMERA_OFFLINE_HOURS

router = APIRouter()


def _camera_status(last_seen: str | None) -> str:
    """
    Real three-way status, not a fabricated ONLINE default:
      - NOT_CONFIGURED: this camera has never produced a single observation
        (present in the network topology, no data source has ever fed it -
        nothing to call "online" or "offline" about yet).
      - OFFLINE: it HAS produced observations before, but none in the last
        CAMERA_OFFLINE_HOURS - same threshold and reasoning as
        intelligence/alerts.py's CAMERA_OFFLINE alert, reused here rather
        than duplicated so this page and that alert always agree.
      - ONLINE: observation activity within that window.
    """
    if not last_seen:
        return "NOT_CONFIGURED"
    try:
        last_seen_dt = datetime.fromisoformat(last_seen)
    except (ValueError, TypeError):
        return "NOT_CONFIGURED"
    if datetime.now() - last_seen_dt > timedelta(hours=CAMERA_OFFLINE_HOURS):
        return "OFFLINE"
    return "ONLINE"

@router.get("")
@router.get("/")
def get_cameras(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all cameras"""
    # Return camera configuration from network config
    cameras = []
    for cam_id, config in CAMERAS.items():
        cameras.append({
            "id": cam_id,
            "camera_id": cam_id,
            "name": config.get("name", ""),
            "location": config.get("location", ""),
            "latitude": config.get("lat"),
            "longitude": config.get("long"),
            "direction": config.get("direction"),
            "road": config.get("road"),
            "camera_type": "Traffic",
            "is_active": True,
            "status": "ONLINE"
        })
    return cameras

@router.get("/health")
def get_camera_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get camera health status with observation counts"""
    """Report camera health from the actual observation stream."""
    store = ObservationStore()
    try:
        observations = store.all_observations()
    finally:
        store.close()
    by_camera = {camera_id: [] for camera_id in CAMERAS}
    for observation in observations:
        if observation.get("camera_id") in by_camera:
            by_camera[observation["camera_id"]].append(observation)
    cameras = []
    for cam_id, config in CAMERAS.items():
        camera_observations = by_camera[cam_id]
        timestamps = [obs.get("timestamp") for obs in camera_observations if obs.get("timestamp")]
        last_seen = max(timestamps) if timestamps else None
        cameras.append({
            "id": cam_id,
            "camera_id": cam_id,
            "name": config.get("name", ""),
            "location": config.get("location", ""),
            "latitude": config.get("lat"),
            "longitude": config.get("long"),
            "direction": config.get("direction"),
            "road": config.get("road"),
            "camera_type": "Traffic",
            "is_active": True,
            "status": _camera_status(last_seen),
            "observation_count": len(camera_observations),
            "last_seen": last_seen
        })
    return cameras

@router.get("/{camera_id}")
def get_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific camera details"""
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    config = CAMERAS[camera_id]
    return {
        "id": camera_id,
        "camera_id": camera_id,
        "name": config.get("name", ""),
        "location": config.get("location", ""),
        "latitude": config.get("lat"),
        "longitude": config.get("long"),
        "direction": config.get("direction"),
        "road": config.get("road"),
        "camera_type": "Traffic",
        "is_active": True,
        "status": "ONLINE"
    }
