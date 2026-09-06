"""Persistent alert API for blacklist and route-anomaly operations."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from database.alert_store import AlertStore
from database.observation_store import ObservationStore
from intelligence.alerts import scan_trajectories_for_alerts
from intelligence.trajectory import build_trajectories

router = APIRouter()


def _alert_response(alert: dict) -> dict:
    return {
        "id": alert["alert_id"],
        "alert_id": f"ALERT_{alert['alert_id']:06d}",
        "alert_type": alert["alert_type"],
        "severity": alert["severity"],
        "plate_text": alert["plate"],
        "normalized_plate": alert["plate"],
        "camera_id": alert.get("camera_id"),
        "timestamp": alert["timestamp"],
        "description": alert.get("description") or "",
        "confidence": alert.get("confidence"),
        "status": alert["status"],
        "created_at": alert["created_at"],
        "updated_at": alert.get("updated_at") or alert["created_at"],
    }


def _parse_alert_id(alert_id: str) -> int:
    value = alert_id.removeprefix("ALERT_")
    if not value.isdigit():
        raise HTTPException(status_code=422, detail="Invalid alert id")
    return int(value)


def _refresh_detected_alerts() -> None:
    """Detect newly eligible alerts while AlertStore prevents duplicates."""
    observation_store = ObservationStore()
    try:
        scan_trajectories_for_alerts(build_trajectories(observation_store.all_observations()))
    finally:
        observation_store.close()


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
