"""
Vehicle API routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from database.observation_store import ObservationStore
from database.blacklist_store import BlacklistStore
from intelligence.trajectory import build_trajectories
from recognition.plate_matcher import normalize_plate

router = APIRouter()


def _summarize(matching_obs, trajectory):
    """Attach the human-readable summary fields the UI shows (first/last seen,
    camera sequence, route path, journey time) to a trajectory dict."""
    if not matching_obs:
        return {}
    ordered = sorted(matching_obs, key=lambda o: o["timestamp"])
    first = ordered[0]
    last = ordered[-1]
    cameras = []
    for o in ordered:
        cam = o.get("camera_id")
        if not cameras or cameras[-1] != cam:
            cameras.append(cam)
    route = " → ".join(cameras)
    try:
        from datetime import datetime as _dt
        total_s = (_dt.fromisoformat(last["timestamp"]) - _dt.fromisoformat(first["timestamp"])).total_seconds()
        mins = int(total_s // 60)
        secs = int(total_s % 60)
        total_journey = f"{mins}m {secs}s" if total_s >= 0 else "-"
    except Exception:
        total_journey = "-"
    summary = {
        "first_seen": first.get("timestamp"),
        "last_seen": last.get("timestamp"),
        "first_camera": first.get("camera_id"),
        "last_camera": last.get("camera_id"),
        "camera_count": len(set(cameras)),
        "camera_sequence": cameras,
        "route_path": route,
        "total_journey_time": total_journey,
        "observation_count": len(matching_obs),
    }
    if trajectory is not None and isinstance(trajectory, dict):
        trajectory.update(summary)
        return trajectory
    return summary

@router.get("/search")
def search_vehicle(
    plate: str = Query(..., description="License plate to search"),
    camera_id: Optional[str] = Query(None, description="Filter by camera"),
    start_time: Optional[str] = Query(None, description="Start time filter"),
    end_time: Optional[str] = Query(None, description="End time filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search for vehicle by license plate"""
    try:
        # Use existing observation store
        store = ObservationStore()
        
        # Get observations for the plate
        all_obs = store.all_observations()
        
        # Filter by plate
        normalized_plate = normalize_plate(plate)
        matching_obs = [
            obs for obs in all_obs 
            if normalize_plate(obs.get("normalized_plate") or obs.get("plate_text") or "") == normalized_plate
        ]
        
        # Apply additional filters
        if camera_id:
            matching_obs = [obs for obs in matching_obs if obs.get("camera_id") == camera_id]
        
        if start_time:
            start_dt = datetime.fromisoformat(start_time)
            matching_obs = [obs for obs in matching_obs if datetime.fromisoformat(obs["timestamp"]) >= start_dt]
        
        if end_time:
            end_dt = datetime.fromisoformat(end_time)
            matching_obs = [obs for obs in matching_obs if datetime.fromisoformat(obs["timestamp"]) <= end_dt]
        
        # Build trajectory
        trajectories = build_trajectories(matching_obs)
        
        vehicle_trajectory = trajectories[0] if trajectories else None
        vehicle_trajectory = _summarize(matching_obs, vehicle_trajectory)
        
        return {
            "vehicle_found": len(matching_obs) > 0,
            "observations": matching_obs,
            "trajectory": vehicle_trajectory
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'store' in locals():
            store.close()

@router.get("/{plate}/trajectory")
def get_vehicle_trajectory(
    plate: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete trajectory for a vehicle"""
    try:
        store = ObservationStore()
        
        # Get observations for the plate
        all_obs = store.all_observations()
        normalized_plate = normalize_plate(plate)
        matching_obs = [
            obs for obs in all_obs 
            if normalize_plate(obs.get("normalized_plate") or obs.get("plate_text") or "") == normalized_plate
        ]
        
        # Build trajectory
        trajectories = build_trajectories(matching_obs)
        
        # Find trajectory for this plate
        if trajectories:
            return _summarize(matching_obs, trajectories[0])
        
        raise HTTPException(status_code=404, detail="Trajectory not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'store' in locals():
            store.close()

@router.post("/watchlist")
def add_to_watchlist(
    plate: str = Query(...),
    severity: str = Query(...),
    reason: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a normalized plate to the persistent operational watchlist."""
    severity = severity.upper()
    if severity not in {"LOW", "MEDIUM", "HIGH"}:
        raise HTTPException(status_code=422, detail="severity must be LOW, MEDIUM, or HIGH")
    if not normalize_plate(plate):
        raise HTTPException(status_code=422, detail="A valid license plate is required")
    store = BlacklistStore()
    try:
        entry_id = store.add_plate(plate, description=reason, severity=severity)
    finally:
        store.close()
    return {"message": "Added to watchlist", "id": entry_id, "plate": normalize_plate(plate)}

@router.delete("/watchlist")
def remove_from_watchlist(
    plate: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate a watchlist entry without deleting its audit history."""
    store = BlacklistStore()
    try:
        existing = store.get_active_entry(plate)
        if not existing:
            raise HTTPException(status_code=404, detail="Plate is not on the watchlist")
        store.deactivate_plate(plate)
    finally:
        store.close()
    return {"message": "Removed from watchlist", "plate": normalize_plate(plate)}
