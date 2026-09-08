# backend/tests/test_honesty_audit.py
#
# Phase 12 honesty-audit regression tests. Locks in the two backend fixes
# from this phase so they can't silently regress back to fabricated data:
#   - GET /admin/audit-logs used to return two hardcoded fake log entries
#     on every call ("sample data"); now queries the real (currently empty)
#     audit_logs table.
#   - GET /admin/system-health used to return hardcoded 45/62/78 resource
#     percentages and a fake "redis: connected" service (no Redis exists
#     anywhere in this stack); now reports real psutil metrics and real
#     database/model health.

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "honesty_audit_test_admin").first()
        if not user:
            user = User(
                username="honesty_audit_test_admin",
                email="honesty_audit@test.local",
                hashed_password=get_password_hash("testpass123"),
                full_name="Honesty Audit Test Admin",
                role="admin",
                is_active=True,
                is_admin=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(data={"sub": str(user.id)})
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


def test_audit_logs_are_not_fabricated(client, admin_headers):
    """
    Was returning two hardcoded entries (USER_LOGIN / VEHICLE_SEARCH with a
    literal fixed timestamp) regardless of any real activity. Now queries
    the real audit_logs table, which nothing currently writes to - an
    honestly empty list, not fake rows.
    """
    resp = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    # The specific fabricated values that used to be hardcoded here must
    # never appear again.
    serialized = str(body)
    assert "2026-09-04T10:00:00" not in serialized


def test_system_health_reports_real_resources_not_fixed_numbers(client, admin_headers):
    """
    Was returning the literal values cpu_percent=45, memory_percent=62,
    disk_percent=78, and a fabricated "redis: connected" service, on a
    hardcoded stale timestamp, every single call. Now reports real psutil
    readings and real database/model status.
    """
    resp = client.get("/api/v1/admin/system-health", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "redis" not in body.get("services", {})
    resources = body.get("resources", {})
    if "error" not in resources:
        # Real psutil readings are numeric and in a valid percentage range -
        # not the exact fabricated constants that used to be hardcoded.
        assert 0 <= resources["cpu_percent"] <= 100
        assert 0 <= resources["memory_percent"] <= 100
        assert 0 <= resources["disk_percent"] <= 100
    assert body["timestamp"] != "2026-09-04T10:00:00"
    assert body["services"]["database"] in ("healthy", "degraded", "unhealthy", "unavailable")
