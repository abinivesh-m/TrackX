"""Persistent alert API for blacklist, route-anomaly, congestion and
camera-health operations."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from database.alert_store import AlertStore
from database.blacklist_store import BlacklistStore
from database.congestion_store import CongestionStore
from database.observation_store import ObservationStore
from intelligence.alerts import scan_trajectories_for_alerts, detect_camera_offline_alerts
from intelligence.trajectory import build_trajectories

router = APIRouter()

# Alert types with no real vehicle to search/link - the frontend uses this
# to skip the "View Vehicle Intelligence" / "View Trajectory" actions and
# show the camera identity instead of treating `plate_text` as a plate.
_CAMERA_SCOPED_ALERT_TYPES = {"CAMERA_OFFLINE", "CONGESTION_BOTTLENECK"}


def _alert_response(alert: dict) -> dict:
    is_camera_scoped = alert["alert_type"] in _CAMERA_SCOPED_ALERT_TYPES
    return {
        "id": alert["alert_id"],
        "alert_id": f"ALERT_{alert['alert_id']:06d}",
        "alert_type": alert["alert_type"],
        "severity": alert["severity"],
        "plate_text": None if is_camera_scoped else alert["plate"],
        "normalized_plate": None if is_camera_scoped else alert["plate"],
        "camera_id": alert.get("camera_id"),
        "timestamp": alert["timestamp"],
        "description": alert.get("description") or "",
        "confidence": alert.get("confidence"),
        "similarity": (alert.get("evidence") or {}).get("similarity"),
        "status": alert["status"],
        "evidence": alert.get("evidence"),
        "is_vehicle_alert": not is_camera_scoped,
        "created_at": alert["created_at"],
        "updated_at": alert.get("updated_at") or alert["created_at"],
    }


def _refresh_congestion_alerts() -> None:
    """
    Promotes currently-ACTIVE bottleneck congestion events (already
    detected and persisted by backend/app/api/v1/congestion.py's
    "Process All Cameras" -> analytics.congestion_hotspots(), see
    database/congestion_store.py) into the unified alert feed. This does
    NOT recompute congestion - it reads the same persisted events the
    Traffic Analytics page shows and surfaces the currently-severe ones as
    alerts too, so operators see them in one place without duplicating the
    detection model.
    """
    congestion_store = CongestionStore()
    try:
        bottlenecks = congestion_store.list_bottlenecks(limit=50)
    finally:
        congestion_store.close()

    if not bottlenecks:
        return

    alert_store = AlertStore()
    try:
        for event in bottlenecks:
            evidence = {
                "camera_id": event["camera_id"],
                "congestion_level": event["congestion_level"],
                "congestion_score": event["congestion_score"],
                "bottleneck_score": event["bottleneck_score"],
                "avg_speed_kmh": event["avg_speed_kmh"],
                "vehicle_density": event["vehicle_density"],
                "duration_minutes": event["duration_minutes"],
                "event_id": event["event_id"],
            }
            alert_store.add_alert(
                plate=event["camera_id"],
                alert_type="CONGESTION_BOTTLENECK",
                # day-granularity key: one open alert per camera per day
                # while the bottleneck persists, not one per page load.
                timestamp=event["event_start"][:10],
                severity="HIGH" if event["congestion_level"] in ("HIGH", "SEVERE") else "MEDIUM",
                camera_id=event["camera_id"],
                description=(
                    f"{event['camera_id']}: bottleneck for {event['duration_minutes']} min "
                    f"(avg speed {event['avg_speed_kmh']:.1f} km/h, score {event['bottleneck_score']:.1f}/100)"
                ),
                confidence=min(event["bottleneck_score"] / 100.0, 1.0),
                evidence=evidence,
            )
    finally:
        alert_store.close()


def _parse_alert_id(alert_id: str) -> int:
    value = alert_id.removeprefix("ALERT_")
    if not value.isdigit():
        raise HTTPException(status_code=422, detail="Invalid alert id")
    return int(value)


def _refresh_detected_alerts() -> None:
    """Detect newly eligible alerts while AlertStore prevents duplicates.
    Covers all four alert families: blacklist/route-anomaly/repeated-camera
    (vehicle trajectory scan), camera-offline (observation staleness), and
    congestion bottlenecks (promoted from the persisted congestion events)."""
    observation_store = ObservationStore()
    try:
        all_observations = observation_store.all_observations()
    finally:
        observation_store.close()

    scan_trajectories_for_alerts(build_trajectories(all_observations))
    detect_camera_offline_alerts(all_observations)
    _refresh_congestion_alerts()


@router.get("")
@router.get("/")
def get_alerts(
    status: str | None = Query(None, pattern="^(OPEN|ACKNOWLEDGED|RESOLVED)$"),
    severity: str | None = Query(None, pattern="^(LOW|MEDIUM|HIGH)$"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return persisted alerts, with durable status filters."""
    _refresh_detected_alerts()
    store = AlertStore()
    try:
        return [_alert_response(row) for row in store.list_alerts(status, severity, limit)]
    finally:
        store.close()


@router.get("/stats")
def get_alert_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return durable alert counts for the operations dashboard."""
    _refresh_detected_alerts()
    store = AlertStore()
    try:
        alerts = store.list_alerts(limit=1000)
    finally:
        store.close()
    return {
        "total_alerts": len(alerts),
        "open_alerts": sum(alert["status"] == "OPEN" for alert in alerts),
        "high_severity_open": sum(
            alert["status"] == "OPEN" and alert["severity"] == "HIGH" for alert in alerts
        ),
    }


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    notes: str | None = Query(None, max_length=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve an alert and retain the decision across page refreshes."""
    store = AlertStore()
    try:
        if not store.resolve_alert(_parse_alert_id(alert_id), notes):
            raise HTTPException(status_code=404, detail="Alert not found")
    finally:
        store.close()
    return {"message": f"Alert {alert_id} resolved", "notes": notes}


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge an alert and retain the status in the alert store."""
    store = AlertStore()
    try:
        if not store.acknowledge_alert(_parse_alert_id(alert_id)):
            raise HTTPException(status_code=404, detail="Alert not found")
    finally:
        store.close()
    return {"message": f"Alert {alert_id} acknowledged"}


@router.get("/watchlist")
def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Every active watchlist/blacklist entry (database/blacklist_store.py),
    tagged by real source: 'DEMO_SEED' for demo/seed_demo_data.py's
    scripted scenario plates, 'OPERATOR' for anything added through
    POST /api/v1/vehicles/watchlist. The frontend uses this to show demo
    scenario plates as clearly-labeled demo data, never as real
    government/operational watchlist records.
    """
    store = BlacklistStore()
    try:
        entries = store.all_active()
    finally:
        store.close()
    return [
        {
            "id": e["id"],
            "plate": e["plate"],
            "normalized_plate": e["normalized_plate"],
            "description": e.get("description"),
            "severity": e.get("severity"),
            "source": e.get("source", "OPERATOR"),
            "created_at": e.get("created_at"),
        }
        for e in entries
    ]
