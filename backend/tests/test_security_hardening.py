# backend/tests/test_security_hardening.py
#
# Phase 10 security/failure-hardening audit tests. Covers gaps this phase
# actually found (not a re-test of things Phase 2's upload hardening or the
# pre-existing JWT plumbing already cover):
#
#   1. Protected routes across multiple different routers genuinely reject
#      unauthenticated requests (401), not just in deps.py's code - a live
#      request without a token.
#   2. A garbage / malformed / nonexistent-user token is rejected with a
#      generic message, never leaking why.
#   3. A malformed date query parameter on /vehicles/search is a 400 with a
#      clear message, not a 500 that echoes Python's raw exception text.
#   4. An unexpected internal failure in /vehicles/search or
#      /vehicles/{plate}/trajectory returns a safe, generic error message -
#      the underlying exception text is logged, never handed to the client.
#   5. GET /api/v1/health/deep does not crash (regression test for a real
#      bug this phase found: `settings.DEBUG` doesn't exist on Settings -
#      every call to this endpoint raised AttributeError before the fix).
#
# Uses a real user row in the project's own users table (not a throwaway
# temp DB) since AlertStore/BlacklistStore/CongestionStore-style DB_PATH
# monkeypatching doesn't apply here - the SQLAlchemy User model reads
# whatever DATABASE_URL the app is already configured with.

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
def auth_headers():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "security_audit_test_user").first()
        if not user:
            user = User(
                username="security_audit_test_user",
                email="security_audit@test.local",
                hashed_password=get_password_hash("testpass123"),
                full_name="Security Audit Test",
                role="operator",
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(data={"sub": str(user.id)})
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/vehicles/search", {"plate": "AB12CD3456"}),
    ("GET", "/api/v1/alerts", {}),
    ("GET", "/api/v1/alerts/watchlist", {}),
    ("GET", "/api/v1/congestion/bottlenecks", {}),
    ("GET", "/api/v1/cameras", {}),
    ("GET", "/api/v1/cameras/health", {}),
    ("GET", "/api/v1/gis/congestion", {}),
    ("GET", "/api/v1/gis/od_flow", {}),
    ("GET", "/api/v1/analytics/summary", {}),
]


@pytest.mark.parametrize("method,url,params", PROTECTED_ENDPOINTS)
def test_protected_endpoints_reject_missing_token(client, method, url, params):
    resp = client.request(method, url, params=params)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_protected_endpoint_rejects_garbage_token(client):
    resp = client.get(
        "/api/v1/vehicles/search",
        params={"plate": "AB12CD3456"},
        headers={"Authorization": "Bearer garbage.token.value"},
    )
    assert resp.status_code == 401
    # Never leak *why* the token was rejected (expired vs malformed vs
    # signature mismatch) - one generic message for every failure mode.
    assert resp.json()["detail"] == "Could not validate credentials"


def test_protected_endpoint_rejects_token_for_nonexistent_user(client):
    bad_token = create_access_token(data={"sub": "99999999"})
    resp = client.get(
        "/api/v1/vehicles/search",
        params={"plate": "AB12CD3456"},
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Could not validate credentials"


def test_vehicle_search_with_valid_token_succeeds(client, auth_headers):
    resp = client.get(
        "/api/v1/vehicles/search", params={"plate": "AB12CD3456"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "vehicle_found" in body
    assert "observations" in body


def test_vehicle_search_malformed_start_time_is_400_not_500(client, auth_headers):
    resp = client.get(
        "/api/v1/vehicles/search",
        params={"plate": "AB12CD3456", "start_time": "not-a-date"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    # A clear, safe message - not Python's raw "Invalid isoformat string: ..."
    # echoed straight back to the client.
    assert "start_time" in detail
    assert "Invalid isoformat string" not in detail


def test_vehicle_search_malformed_end_time_is_400_not_500(client, auth_headers):
    resp = client.get(
        "/api/v1/vehicles/search",
        params={"plate": "AB12CD3456", "end_time": "also-not-a-date"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "end_time" in resp.json()["detail"]


def test_vehicle_search_internal_error_does_not_leak_exception_text(client, auth_headers, monkeypatch):
    """
    Forces an unexpected internal failure inside search_vehicle() (not a
    validation error) and confirms the client gets a safe, generic message
    - never the raw exception text, which could contain internal details.
    """
    import app.api.v1.vehicles as vehicles_module

    def _boom(*args, **kwargs):
        raise RuntimeError("/some/internal/server/path/leaked/by/accident.db")

    monkeypatch.setattr(vehicles_module, "build_trajectories", _boom)

    resp = client.get(
        "/api/v1/vehicles/search", params={"plate": "AB12CD3456"}, headers=auth_headers
    )
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "leaked/by/accident.db" not in detail
    assert detail == "Vehicle search failed. Please try again."


def test_vehicle_trajectory_internal_error_does_not_leak_exception_text(client, auth_headers, monkeypatch):
    import app.api.v1.vehicles as vehicles_module

    def _boom(*args, **kwargs):
        raise RuntimeError("sqlite3.OperationalError: unable to open /secret/path/trackx.db")

    monkeypatch.setattr(vehicles_module, "build_trajectories", _boom)

    resp = client.get(
        "/api/v1/vehicles/AB12CD3456/trajectory", headers=auth_headers
    )
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "/secret/path" not in detail
    assert detail == "Trajectory lookup failed. Please try again."


def test_health_deep_does_not_crash(client):
    """
    Regression test: GET /api/v1/health/deep unconditionally raised
    AttributeError (`Settings` has no attribute `DEBUG`) before this phase's
    fix - every single call to this public, unauthenticated endpoint failed.
    """
    resp = client.get("/api/v1/health/deep")
    assert resp.status_code == 200
    body = resp.json()
    assert body["environment"] in ("development", "testing", "production")


def test_health_status_does_not_crash(client):
    resp = client.get("/api/v1/health/status")
    assert resp.status_code == 200


def test_ingest_video_rejects_unknown_camera_without_auth_leak(client, auth_headers):
    """Existing Phase 2 hardening, re-verified here rather than re-audited
    from scratch: an unknown camera_id is rejected before any file is even
    read, and a plain non-video file is rejected as an unsupported format."""
    resp = client.post(
        "/api/v1/observations/ingest-video",
        data={"camera_id": "NOT_A_REAL_CAMERA"},
        files={"file": ("clip.mp4", b"not-a-real-video-file", "video/mp4")},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert "Unknown camera id" in resp.json()["detail"]


def test_ingest_video_rejects_disallowed_extension(client, auth_headers):
    resp = client.post(
        "/api/v1/observations/ingest-video",
        data={"camera_id": "CAM_01"},
        files={"file": ("clip.exe", b"not-a-video", "application/octet-stream")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Unsupported video format" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Phase 14 pre-deployment finding: public self-registration privilege
# escalation. Public POST /auth/register accepted role="admin" straight from
# the request body, and get_current_admin_user() grants access when EITHER
# is_admin OR role=="admin" - so anyone could self-register their way to a
# full admin account. Never mattered while this only ran privately; going
# public in Phase 14 makes it a real, exploitable vulnerability. Fixed in
# app/api/v1/auth.py's register(): client-supplied role is now restricted to
# non-privileged values regardless of what's in the request body.
# ---------------------------------------------------------------------------

def test_public_registration_cannot_grant_admin_role(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "privesc_regression_test_user",
            "email": "privesc_regression@example.com",
            "password": "testpass123",
            "role": "admin",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] != "admin", f"public registration granted role={body['role']!r}"
    assert body["is_admin"] is False, "public registration granted is_admin=True"


def test_public_registration_account_is_rejected_from_admin_routes(client):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "privesc_regression_test_user", "password": "testpass123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403, (
        f"a self-registered account (which requested role=admin) got {resp.status_code} "
        f"on an admin-only route, expected 403"
    )

    # cleanup
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == "privesc_regression_test_user").delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Phase 14 pre-deployment finding: a duplicate-model-registration bug caused
# by inconsistent import paths. Several backend modules imported internal
# app code via the fully-qualified "backend.app.X" path instead of the
# "app.X" path every other module uses. Both paths resolve to the same
# files but register as SEPARATE module identities in sys.modules, so each
# one gets its own SQLAlchemy declarative Base/registry - meaning
# GET /api/v1/health/status (which lazily imports Camera to count rows)
# could register a Camera model whose relationship("Observation") could
# never resolve, since Observation was registered (if at all) under a
# different registry. SQLAlchemy's configure_mappers() sweeps every
# mapper ever registered in the process on the first real ORM
# flush/commit ANYWHERE, and caches a failed mapper's error permanently -
# so calling that one health endpoint could silently poison every other
# endpoint's database access for the rest of the process's life, with an
# error message that gives no hint the health endpoint was the cause.
# Fixed by standardizing every import in the backend on "app.X" (no
# "backend.app.X" import remains anywhere in the codebase - see
# app/main.py's import block for the full explanation) and by having
# health.py's system_status() import Observation alongside Camera so the
# relationship always resolves. This test proves the fix: hit the health
# endpoint that used to poison the process, THEN perform a real ORM write
# on an unrelated model (User, via register) and confirm it still works.
# ---------------------------------------------------------------------------

def test_health_status_endpoint_does_not_poison_later_orm_writes(client):
    resp = client.get("/api/v1/health/status")
    assert resp.status_code == 200

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "mapper_regression_test_user",
            "email": "mapper_regression@example.com",
            "password": "testpass123",
        },
    )
    assert resp.status_code == 200, (
        "a real ORM write failed after GET /api/v1/health/status was called - "
        f"likely the duplicate-model-registration bug has regressed: {resp.text}"
    )

    # cleanup
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == "mapper_regression_test_user").delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
