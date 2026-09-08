"""
Vehicle API routes
"""

import logging

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
from intelligence.spatio_temporal import calculate_spatial_temporal_plausibility
from network.camera_network import CAMERAS
from recognition.plate_matcher import normalize_plate
from app.api.v1.observations import _plate_crop_url

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_hops_and_segments(ordered_obs):
    """
    One hop per camera actually VISITED (collapsing consecutive
    observations at the same camera - multiple frames/track sessions at
    one camera are one visit, not one hop each), with real coordinates
    from network.camera_network.CAMERAS (falling back to the observation's
    own stored lat/long if a camera isn't in that table). This is what the
    Vehicle Intelligence hero map plots - one clean node per camera visit,
    not one per raw observation row.

    Segments (camera[i] -> camera[i+1]) reuse the SAME real plausibility
    engine route_anomaly.py already uses
    (intelligence.spatio_temporal.calculate_spatial_temporal_plausibility) -
    real road-graph distance when the cameras are connected, real speed
    limits, real elapsed time - instead of a separate/duplicated distance
    or anomaly calculation. is_plausible=False on a segment is exactly the
    "anomaly segment" the map should highlight.
    """
    hops = []
    for o in ordered_obs:
        cid = o.get("camera_id")
        if hops and hops[-1]["camera_id"] == cid:
            continue
        cam = CAMERAS.get(cid, {})
        lat = o.get("lat") if o.get("lat") is not None else cam.get("lat")
        lng = o.get("long") if o.get("long") is not None else cam.get("long")
        hops.append({
            "camera_id": cid,
            "camera_name": cam.get("name", cid),
            "lat": lat,
            "lng": lng,
            "timestamp": o.get("timestamp"),
            "direction": o.get("direction"),
            "confidence": o.get("confidence"),
            "plate_confidence": o.get("plate_confidence"),
            "vehicle_confidence": o.get("vehicle_confidence"),
            "vehicle_type": o.get("vehicle_type"),
            "plate_crop_url": _plate_crop_url(o.get("plate_crop_path")),
            "segment_from_prev": None,  # filled in below for hops[1:]
        })

    segments = []
    for i in range(1, len(hops)):
        a, b = hops[i - 1], hops[i]
        try:
            t_a = datetime.fromisoformat(a["timestamp"])
            t_b = datetime.fromisoformat(b["timestamp"])
            result = calculate_spatial_temporal_plausibility(a["camera_id"], b["camera_id"], t_a, t_b)
            seg = result.to_dict()
        except Exception as e:
            seg = {
                "is_plausible": None,
                "distance_km": None,
                "required_speed_kmph": None,
                "reason": f"Could not evaluate this segment: {e}",
            }
        seg["from_camera"] = a["camera_id"]
        seg["from_camera_name"] = a["camera_name"]
        seg["to_camera"] = b["camera_id"]
        seg["to_camera_name"] = b["camera_name"]
        hops[i]["segment_from_prev"] = seg
        segments.append(seg)

    return hops, segments


def _summarize(matching_obs, trajectory):
    """Attach the human-readable summary fields the UI shows: first/last
    seen, camera sequence, journey totals, the GIS hop/segment list, a
    trajectory-confidence score, and blacklist status."""
    if not matching_obs:
        return {}
    ordered = sorted(matching_obs, key=lambda o: o["timestamp"])
    first = ordered[0]
    last = ordered[-1]

    hops, segments = _build_hops_and_segments(ordered)
    cameras = [h["camera_id"] for h in hops]
    route = " → ".join(cameras)

    try:
        total_s = (datetime.fromisoformat(last["timestamp"]) - datetime.fromisoformat(first["timestamp"])).total_seconds()
        mins = int(total_s // 60)
        secs = int(total_s % 60)
        total_journey = f"{mins}m {secs}s" if total_s >= 0 else "-"
        total_duration_min = round(total_s / 60.0, 1) if total_s >= 0 else 0.0
    except Exception:
        total_journey = "-"
        total_duration_min = 0.0

    # Real segment distances (road-graph aware, not straight-line unless
    # unconnected) - not a separate/duplicated haversine sum.
    real_distances = [s["distance_km"] for s in segments if s.get("distance_km") is not None]
    total_distance_km = round(sum(real_distances), 2) if real_distances else 0.0
    average_speed_kmh = (
        round(total_distance_km / (total_duration_min / 60.0), 1)
        if total_duration_min > 0.5 and total_distance_km > 0 else 0.0
    )

    # Trajectory confidence: the actual multi-camera identity-fusion match
    # scores from intelligence/trajectory.py's build_trajectories() (plate
    # similarity + appearance + temporal + spatial, see intelligence/
    # fusion.py) - not a fabricated number. A single-observation trajectory
    # has nothing to link, so confidence is reported as null (not 100%,
    # which would overstate certainty about a route that doesn't exist yet).
    match_scores = trajectory.get("match_scores") if isinstance(trajectory, dict) else None
    trajectory_confidence = round((sum(match_scores) / len(match_scores)) * 100, 1) if match_scores else None

    anomalous_segments = [s for s in segments if s.get("is_plausible") is False]

    blacklist_store = BlacklistStore()
    try:
        plate_for_blacklist = first.get("normalized_plate") or first.get("plate_text")
        blacklist_entry = blacklist_store.get_active_entry(plate_for_blacklist) if plate_for_blacklist else None
    finally:
        blacklist_store.close()

    vehicle_types = [o.get("vehicle_type") for o in ordered if o.get("vehicle_type")]
    vehicle_type = max(set(vehicle_types), key=vehicle_types.count) if vehicle_types else None

    # Real, explainable risk level - not a fabricated score. HIGH only for
    # an active blacklist match (an operator-configured fact); MEDIUM for
    # an implausible segment this session actually found; LOW otherwise.
    # The frontend previously rendered a risk badge with no backing field
    # at all (always fell through to its default), which this replaces.
    if blacklist_entry is not None:
        risk_level = "HIGH"
    elif anomalous_segments:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    summary = {
        "risk_level": risk_level,
        "vehicle_type": vehicle_type,
        "first_seen": first.get("timestamp"),
        "last_seen": last.get("timestamp"),
        "first_camera": first.get("camera_id"),
        "last_camera": last.get("camera_id"),
        "camera_count": len(set(cameras)),
        "camera_sequence": cameras,
        "route_path": route,
        "total_journey_time": total_journey,
        "observation_count": len(matching_obs),
        "hops": hops,
        "segments": segments,
        "total_distance_km": total_distance_km,
        "total_duration_min": total_duration_min,
        "average_speed_kmh": average_speed_kmh,
        "trajectory_confidence": trajectory_confidence,
        "anomalous_segment_count": len(anomalous_segments),
        "is_blacklisted": blacklist_entry is not None,
        "blacklist_severity": blacklist_entry.get("severity") if blacklist_entry else None,
        "blacklist_reason": blacklist_entry.get("description") if blacklist_entry else None,
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
    # Validate user-supplied date filters BEFORE the general try/except, so a
    # bad query parameter is reported as a 400 (client error) with a clear,
    # safe message - not a 500 that echoes Python's raw ValueError text back
    # to the caller.
    start_dt = None
    end_dt = None
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid start_time - expected ISO 8601 format, e.g. 2026-09-07T12:00:00",
            )
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid end_time - expected ISO 8601 format, e.g. 2026-09-07T12:00:00",
            )

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

        if start_dt is not None:
            matching_obs = [obs for obs in matching_obs if datetime.fromisoformat(obs["timestamp"]) >= start_dt]

        if end_dt is not None:
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

    except HTTPException:
        raise
    except Exception as e:
        # Log the real exception server-side for diagnosis, but never hand
        # raw internal exception text (which can include file paths, DB
        # driver internals, etc.) back to an API client.
        logger.exception("search_vehicle failed for plate=%r", plate)
        raise HTTPException(status_code=500, detail="Vehicle search failed. Please try again.")
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
        logger.exception("get_vehicle_trajectory failed for plate=%r", plate)
        raise HTTPException(status_code=500, detail="Trajectory lookup failed. Please try again.")
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
