"""
Congestion / bottleneck detection API.

Was previously called by frontend/src/pages/CongestionPage.tsx
(frontend/src/services/api.ts: getCameraTrafficMetrics /
getActiveCongestionEvents / getCongestionEventHistory /
processCameraCongestion / processAllCamerasCongestion /
getCongestionAnalytics / getActiveBottlenecks / getTrafficThresholds /
updateTrafficThresholds) with NO backend router registered for it - every
call was a 404. This file is that missing router.

The congestion score itself is not reimplemented here - it's
analytics/analytics.py's congestion_hotspots(), a real multi-factor model
(density + speed + density/speed efficiency ratio, see that module for the
weights) already used by backend/app/api/v1/analytics.py's /summary
endpoint. This file adds a persisted ACTIVE/RESOLVED event lifecycle and
configurable thresholds on top of it via database/congestion_store.py, so
"process cameras for congestion" produces something durable to browse
rather than a number that vanishes on refresh.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analytics.analytics import average_vehicle_speed, congestion_hotspots
from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from database.congestion_store import CongestionStore
from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories
from network.camera_network import CAMERAS

router = APIRouter()


def _native(value):
    """
    analytics.congestion_hotspots() uses numpy (np.mean/np.percentile) when
    numpy is available, so congestion_score/threshold comparisons can come
    back as numpy.float64/numpy.bool_ instead of plain Python types. Those
    are not JSON-serializable by FastAPI's default encoder (caught by
    actually calling this endpoint - see docs/CLAUDE_PHASE0_AUDIT.md) and
    sqlite3 param binding is also unreliable with them. Convert at the API
    boundary rather than pushing this concern into analytics/analytics.py.
    """
    if hasattr(value, "item"):
        return value.item()
    return value


def _load_observations(camera_id: str | None = None, hours: float | None = None):
    store = ObservationStore()
    try:
        observations = store.all_observations()
    finally:
        store.close()
    if camera_id:
        observations = [o for o in observations if o.get("camera_id") == camera_id]
    if hours is not None:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        observations = [o for o in observations if o.get("timestamp", "") >= cutoff]
    return observations


def _run_congestion_model(camera_id: str | None = None, hours: float | None = 24):
    """Real computation shared by every endpoint below: load observations,
    build trajectories for speed, run the multi-factor congestion model."""
    observations = _load_observations(camera_id=camera_id, hours=hours)
    all_observations_for_trajectories = _load_observations(hours=hours)  # trajectories need cross-camera data
    trajectories = build_trajectories(all_observations_for_trajectories)
    return congestion_hotspots(observations if camera_id is None else all_observations_for_trajectories,
                                trajectories), observations


@router.get("/metrics/{camera_id}")
def get_camera_traffic_metrics(
    camera_id: str,
    hours: float = Query(24, gt=0, le=24 * 30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current-window traffic metrics for one camera - computed fresh from
    stored observations each call (not a persisted rolling window; see
    docs/CLAUDE_PHASE0_AUDIT.md for why a full time-bucketed metrics table
    was scoped out for this pass)."""
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail="Unknown camera id")

    result, observations = _run_congestion_model(camera_id=camera_id, hours=hours)
    factors = result["congestion_factors"].get(camera_id)
    thresholds = CongestionStore().get_thresholds()

    if not factors:
        return {
            "camera_id": camera_id,
            "road_segment_id": camera_id,
            "window_duration_minutes": hours * 60,
            "vehicle_count": len(observations),
            "unique_vehicles": len({o.get("normalized_plate") or o.get("plate_text") for o in observations if o.get("normalized_plate") or o.get("plate_text")}),
            "flow_rate_vehicles_per_hour": round(len(observations) / hours, 2) if hours else 0,
            "avg_speed_kmh": None,
            "vehicle_density": 0,
            "congestion_level": "LOW",
            "congestion_score": 0,
            "is_congested": False,
            "is_bottleneck": False,
            "window_start": (datetime.now() - timedelta(hours=hours)).isoformat(),
            "window_end": datetime.now().isoformat(),
        }

    congestion_score = _native(result["congestion_scores"].get(camera_id, 0))
    is_congested = _native(congestion_score >= _native(result["threshold"]))
    is_bottleneck = _native(
        factors["raw_speed"] > 0 and thresholds["speed_threshold_kmh"] > 0 and
        factors["raw_speed"] <= thresholds["speed_threshold_kmh"] and is_congested
    )
    unique_vehicles = len({
        o.get("normalized_plate") or o.get("plate_text") for o in observations
        if o.get("normalized_plate") or o.get("plate_text")
    })

    return {
        "camera_id": camera_id,
        "road_segment_id": camera_id,
        "window_duration_minutes": hours * 60,
        "vehicle_count": len(observations),
        "unique_vehicles": unique_vehicles,
        "flow_rate_vehicles_per_hour": round(len(observations) / hours, 2) if hours else 0,
        "avg_speed_kmh": _native(factors["raw_speed"]),
        "vehicle_density": _native(factors["raw_density"]),
        "congestion_level": factors["congestion_level"],
        "congestion_score": round(congestion_score * 100, 1),
        "is_congested": bool(is_congested),
        "is_bottleneck": bool(is_bottleneck),
        "window_start": (datetime.now() - timedelta(hours=hours)).isoformat(),
        "window_end": datetime.now().isoformat(),
    }


@router.get("/events/active")
def get_active_congestion_events(
    camera_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = CongestionStore()
    try:
        return store.list_active_events(camera_id=camera_id, limit=limit)
    finally:
        store.close()


@router.get("/events/history")
def get_congestion_event_history(
    camera_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = CongestionStore()
    try:
        return store.list_history(camera_id=camera_id, start_time=start_time, end_time=end_time, limit=limit)
    finally:
        store.close()


def _process_one_camera(camera_id: str, thresholds: dict) -> dict | None:
    result, observations = _run_congestion_model(camera_id=camera_id, hours=24)
    factors = result["congestion_factors"].get(camera_id)
    if not factors or not observations:
        return None

    congestion_score = _native(result["congestion_scores"].get(camera_id, 0))
    is_congested = bool(_native(congestion_score >= _native(result["threshold"])))
    is_bottleneck = bool(_native(
        factors["raw_speed"] > 0 and thresholds["speed_threshold_kmh"] > 0 and
        factors["raw_speed"] <= thresholds["speed_threshold_kmh"] and is_congested
    ))
    if not is_congested:
        return {"camera_id": camera_id, "congested": False}

    store = CongestionStore()
    try:
        event = store.upsert_active_event(
            camera_id=camera_id,
            congestion_level=factors["congestion_level"],
            congestion_score=round(congestion_score * 100, 1),
            avg_speed_kmh=_native(factors["raw_speed"]),
            vehicle_density=_native(factors["raw_density"]),
            flow_rate_vehicles_per_hour=round(len(observations) / 24, 2),
            is_bottleneck=is_bottleneck,
            bottleneck_score=round(congestion_score * 100, 1) if is_bottleneck else 0,
        )
    finally:
        store.close()
    return {"camera_id": camera_id, "congested": True, "event": event}


@router.post("/process/all")
def process_all_cameras_congestion(
    window_duration_minutes: int = Query(5, ge=1, le=1440),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # NOTE: this literal route MUST be declared before /process/{camera_id}
    # below - FastAPI/Starlette matches path routes in declaration order,
    # so a path-param route declared first would greedily swallow
    # "/process/all" as camera_id="all" and 404 (that was a real bug caught
    # by actually testing this endpoint - see docs/CLAUDE_PHASE0_AUDIT.md
    # follow-up notes).
    thresholds = CongestionStore().get_thresholds()
    congested_ids = set()
    processed = []
    for camera_id in CAMERAS:
        outcome = _process_one_camera(camera_id, thresholds)
        if outcome:
            processed.append(outcome)
            if outcome["congested"]:
                congested_ids.add(camera_id)

    store = CongestionStore()
    try:
        store.resolve_events_not_in(congested_ids)
    finally:
        store.close()

    return {
        "processed_cameras": len(processed),
        "congested_cameras": len(congested_ids),
        "results": processed,
    }


@router.post("/process/{camera_id}")
def process_camera_congestion(
    camera_id: str,
    window_duration_minutes: int = Query(5, ge=1, le=1440),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail="Unknown camera id")
    thresholds = CongestionStore().get_thresholds()
    outcome = _process_one_camera(camera_id, thresholds)
    return outcome or {"camera_id": camera_id, "congested": False, "reason": "no observations in window"}


@router.get("/analytics/{camera_id}")
def get_congestion_analytics(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail="Unknown camera id")

    result, observations = _run_congestion_model(camera_id=camera_id, hours=24)
    factors = result["congestion_factors"].get(camera_id, {})
    cam = CAMERAS[camera_id]

    store = CongestionStore()
    try:
        active_events = store.list_active_events(camera_id=camera_id, limit=10)
    finally:
        store.close()

    return {
        "camera_id": camera_id,
        "camera_name": cam["name"],
        "location": cam["location"],
        "current_congestion_level": factors.get("congestion_level", "LOW"),
        "avg_speed_kmph": _native(factors.get("raw_speed", 0)),
        "vehicle_density": _native(factors.get("raw_density", 0)),
        "active_events": active_events,
    }


@router.get("/bottlenecks")
def get_active_bottlenecks(
    limit: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = CongestionStore()
    try:
        return store.list_bottlenecks(limit=limit)
    finally:
        store.close()


@router.get("/thresholds")
def get_traffic_thresholds(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = CongestionStore()
    try:
        return store.get_thresholds()
    finally:
        store.close()


@router.put("/thresholds")
def update_traffic_thresholds(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = CongestionStore()
    try:
        return store.update_thresholds(**payload)
    finally:
        store.close()
