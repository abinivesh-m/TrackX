# backend/tests/test_alerts.py

import pytest
from datetime import datetime
from app.services.alert_service import AlertService
from app.models.alert import Alert


@pytest.mark.asyncio
async def test_create_alert(db_session):
    """Test creating an alert."""
    service = AlertService(db_session)
    
    alert = await service.create_alert(
        alert_type="BLACKLIST_MATCH",
        severity="HIGH",
        plate_text="TN38AB1234",
        camera_id="CAM_01",
        description="Vehicle matched blacklist"
    )
    
    assert alert.alert_id is not None
    assert alert.status == "OPEN"
    assert alert.severity == "HIGH"


@pytest.mark.asyncio
async def test_get_alerts(db_session):
    """Test retrieving alerts."""
    service = AlertService(db_session)
    
    await service.create_alert(
        alert_type="BLACKLIST_MATCH",
        severity="HIGH",
        plate_text="TN38AB1234",
        camera_id="CAM_01"
    )
    
    alerts = await service.get_alerts()
    
    assert len(alerts) == 1
    assert alerts[0].plate_text == "TN38AB1234"


@pytest.mark.asyncio
async def test_resolve_alert(db_session):
    """Test resolving an alert."""
    service = AlertService(db_session)
    
    alert = await service.create_alert(
        alert_type="BLACKLIST_MATCH",
        severity="HIGH",
        plate_text="TN38AB1234",
        camera_id="CAM_01"
    )
    
    success = await service.resolve_alert(alert.alert_id, resolved_by="test_user", notes="Test resolution")
    
    assert success is True
    
    resolved = await service.get_alert_by_id(alert.alert_id)
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_by == "test_user"
