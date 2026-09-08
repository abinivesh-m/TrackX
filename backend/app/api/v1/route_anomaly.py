"""
Route anomaly detection API.

Was previously called by frontend/src/pages/RouteAnomalyPage.tsx
(frontend/src/services/api.ts: getRouteAnomalies / analyzeVehicleRoute /
analyzeCameraTransition / getCameraTransitions / getAnomalyStatistics /
updateAnomalyStatus) with NO backend router registered for it - every call
was a 404. This file is that missing router.

Detection logic is not reimplemented here - it's a thin layer over the
already-tested intelligence/spatio_temporal.py (impossible-travel-time /
unexpected-transition detection against network/camera_network.py's real
road topology) and intelligence/anomaly_scoring.py (per-vehicle anomaly
scoring), persisted through database/route_anomaly_store.py so the
frontend's OPEN -> UNDER_INVESTIGATION -> RESOLVED/FALSE_POSITIVE workflow
has somewhere real to read/write.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from database.observation_store import ObservationStore
from database.route_anomaly_store import RouteAnomalyStore
from intelligence.spatio_temporal import (
    calculate_spatial_temporal_plausibility,
    detect_impossible_transitions,
)
from network.camera_network import CAMERAS, ROAD_GRAPH, _get_edge

router = APIRouter()


def _persist_impossible_transitions(observations: list) -> int:
    """Run detection over a set of observations and persist any findings.

    Returns the number of NEW anomalies created (existing ones are
    idempotently skipped, matching the pattern intelligence/alerts.py's
    scan_trajectories_for_alerts already uses for the blacklist alert
    table).
    """
    findings = detect_impossible_transitions(observations)
    store = RouteAnomalyStore()
    created = 0
    try:
        for finding in findings:
            result = finding["result"]
            plate = finding.get("plate_a") or finding.get("plate_b") or "UNKNOWN"
            # anomaly_score: 0-100, higher = more anomalous. Distance/confidence
            # already computed by spatio_temporal; derive a simple, explainable
            # score from how far required speed exceeds the plausible max
            # rather than inventing a new model.
            if result.required_speed_kmph and result.required_speed_kmph != float("inf"):
                edge = _get_edge(result.camera_a, result.camera_b)
                speed_limit = edge["speed_limit_kmph"] if edge else 60
                overshoot = max(0.0, (result.required_speed_kmph - speed_limit) / max(speed_limit, 1))
                score = min(100.0, 40.0 + overshoot * 60.0)
            else:
                score = 95.0  # infinite/undefined required speed = clearly impossible

            anomaly_id, was_created = store.add_anomaly(
                plate=plate,
                from_camera=result.camera_a,
                to_camera=result.camera_b,
                timestamp=result.timestamp_b.isoformat(),
                anomaly_type="IMPOSSIBLE_TRAVEL" if not result.spatial_connected or result.required_speed_kmph == float("inf")
                             else "UNREASONABLE_SPEED",
                anomaly_score=score,
                reason=result.reason,
                unexpected_transition=not result.spatial_connected,
                impossible_travel_time=not result.is_plausible,
                unreasonable_speed=result.required_speed_kmph not in (0, float("inf")) and
                                    bool(_get_edge(result.camera_a, result.camera_b)) and
                                    result.required_speed_kmph > _get_edge(result.camera_a, result.camera_b)["speed_limit_kmph"],
                observed_speed_kmph=None if result.required_speed_kmph == float("inf") else round(result.required_speed_kmph, 1),
                expected_min_time=result.expected_time_min_seconds,
                distance_km=round(result.distance_km, 2),
            )
            if was_created:
                created += 1
    finally:
        store.close()
    return created


@router.get("/anomalies")
def get_route_anomalies(
    plate: str | None = None,
    severity: str | None = Query(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    status: str | None = Query(None, pattern="^(OPEN|UNDER_INVESTIGATION|RESOLVED|FALSE_POSITIVE)$"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List persisted route anomalies, with durable status/severity filters."""
    store = RouteAnomalyStore()
    try:
        return store.list_anomalies(plate=plate, severity=severity, status=status, limit=limit)
    finally:
        store.close()


@router.get("/anomalies/{anomaly_id}")
def get_route_anomaly(
    anomaly_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = RouteAnomalyStore()
    try:
        anomaly = store.get_anomaly(anomaly_id)
    finally:
        store.close()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Route anomaly not found")
    return anomaly


@router.post("/analyze/{plate}")
def analyze_vehicle_route(
    plate: str,
    start_time: str | None = None,
    end_time: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-run impossible-transition detection restricted to one vehicle's
    observations and persist any findings. Returns what was found, not just
    an "ok" - this is what the "Analyze Route" button on
    RouteAnomalyPage.tsx is for.
    """
    observation_store = ObservationStore()
    try:
        observations = [
            o for o in observation_store.all_observations()
            if (o.get("normalized_plate") or o.get("plate_text")) == plate
        ]
    finally:
        observation_store.close()

    if start_time:
        observations = [o for o in observations if o.get("timestamp", "") >= start_time]
    if end_time:
        observations = [o for o in observations if o.get("timestamp", "") <= end_time]

    observations.sort(key=lambda o: o.get("timestamp", ""))
    new_count = _persist_impossible_transitions(observations)

    store = RouteAnomalyStore()
    try:
        anomalies = store.list_anomalies(plate=plate, limit=100)
    finally:
        store.close()

    return {
        "plate": plate,
        "observations_analyzed": len(observations),
        "new_anomalies_found": new_count,
        "anomalies": anomalies,
    }


@router.get("/analyze/{from_camera}/{to_camera}")
def analyze_camera_transition(
    from_camera: str,
    to_camera: str,
    travel_time_seconds: float = Query(..., ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    On-demand what-if check: "is a `travel_time_seconds` gap between these
    two cameras physically plausible?" - directly exposes
    intelligence.spatio_temporal.calculate_spatial_temporal_plausibility()
    without needing two real observations.
    """
    if from_camera not in CAMERAS or to_camera not in CAMERAS:
        raise HTTPException(status_code=404, detail="Unknown camera id")

    t_a = datetime.now()
    t_b = t_a + timedelta(seconds=travel_time_seconds)
    result = calculate_spatial_temporal_plausibility(from_camera, to_camera, t_a, t_b)
    return result.to_dict()


@router.get("/topology/transitions/{camera_id}")
def get_camera_transitions(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Real road-topology neighbors for one camera, from
    network/camera_network.py's ROAD_GRAPH - what "expected" transitions
    look like for this node, which is exactly what "unexpected transition"
    anomalies are measured against.
    """
    if camera_id not in CAMERAS:
        raise HTTPException(status_code=404, detail="Unknown camera id")

    neighbors = []
    for (a, b), edge in ROAD_GRAPH.items():
        if a == camera_id:
            neighbors.append({"camera_id": b, **edge})
        elif b == camera_id:
            neighbors.append({"camera_id": a, **edge})

    return {
        "camera_id": camera_id,
        "camera": CAMERAS[camera_id],
        "connected_cameras": neighbors,
    }


@router.get("/statistics")
def get_anomaly_statistics(
    start_time: str | None = None,
    end_time: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = RouteAnomalyStore()
    try:
        return store.statistics(start_time=start_time, end_time=end_time)
    finally:
        store.close()


@router.put("/anomalies/{anomaly_id}/status")
def update_anomaly_status(
    anomaly_id: int,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    status = payload.get("status")
    if not status:
        raise HTTPException(status_code=422, detail="status is required")
    store = RouteAnomalyStore()
    try:
        updated = store.update_status(
            anomaly_id,
            status=status,
            investigated_by=payload.get("investigated_by"),
            investigation_notes=payload.get("investigation_notes"),
            resolution_notes=payload.get("resolution_notes"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        store.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Route anomaly not found")
    return {"message": f"Anomaly {anomaly_id} updated", "status": status}
