"""
TrackX Main Application Entry Point
FastAPI application for vehicle intelligence system
"""

import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add backend to path for imports
backend_path = os.path.join(os.path.dirname(__file__), '..')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
from typing import Dict, Set
import json

# Try imports with fallback for different execution contexts
# Phase 14 finding: this used to fall back to "backend.app.X"-style imports
# on ImportError. sys.path already has both project_root and backend_path
# inserted above, so "app.X" always resolves - the fallback branch was dead
# in practice, but if it ever DID trigger, it would silently re-import every
# model under a second, parallel "backend.app.X" module identity with its
# own separate SQLAlchemy declarative Base. SQLAlchemy's configure_mappers()
# sweeps every mapper ever registered in the process on the first real ORM
# write anywhere, so that orphaned second copy (whose relationships can
# never resolve against the real Base) would crash the very first user
# registration/login after it loaded - a serious, hard-to-diagnose
# production bug. Removed the fallback entirely so this can never happen
# again; only one import path exists now.
from app.core.database import init_db, SessionLocal
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.api.v1 import auth, cameras, vehicles, analytics, alerts, observations, admin, trajectory, gis
from app.api.v1 import congestion, route_anomaly

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create connection manager if needed
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: Dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to websocket: {e}")

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting TrackX application...")
    init_db()
    # Always ensure the configured admin account exists (the `admin is
    # None` check below prevents duplicates on every restart). This used
    # to be skipped whenever ENVIRONMENT=="production" - but Render sets
    # ENVIRONMENT=production for every deploy, so with that check NO admin
    # account was ever created on the live deployed app, no matter what
    # FIRST_SUPERUSER_PASSWORD was set to. The password always comes from
    # FIRST_SUPERUSER_PASSWORD (a real secret set in Render's dashboard,
    # never the "admin123" default), so it's safe to run this in
    # production too.
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.FIRST_SUPERUSER).first()
        if admin is None:
            db.add(User(
                username=settings.FIRST_SUPERUSER,
                email=settings.FIRST_SUPERUSER,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                full_name="TrackX Administrator",
                role="admin",
                is_admin=True,
                is_active=True,
            ))
            db.commit()
            logger.info("Created admin account from FIRST_SUPERUSER/FIRST_SUPERUSER_PASSWORD.")
    finally:
        db.close()
    logger.info("Database initialized")

    # Phase 14 deployment: Render's (and most free-tier hosts') disk is
    # ephemeral - every restart/redeploy loses the SQLite observations DB
    # this app seeds its demo data into, with no shell access afterward to
    # fix it. Setting AUTO_SEED_DEMO_DATA=true re-runs the same seeding
    # demo/seed_demo_data.py's CLI (--reset) already does, so a fresh
    # deploy comes up with working demo data instead of an empty database.
    # Off by default - never runs in a normal local dev checkout unless
    # this env var is explicitly set.
    if os.getenv("AUTO_SEED_DEMO_DATA", "").lower() in ("1", "true", "yes"):
        try:
            from demo.seed_demo_data import run_seed
            summary = run_seed(reset=True)
            logger.info(f"AUTO_SEED_DEMO_DATA: seeded demo data on startup: {summary}")
        except Exception:
            logger.exception("AUTO_SEED_DEMO_DATA: seeding failed - app will still start, but demo data may be missing/incomplete")

    yield
    
    # Shutdown
    logger.info("Shutting down TrackX application...")

# Create FastAPI app
app = FastAPI(
    title="TrackX API",
    description="City-Wide Vehicle Intelligence System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS] or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(cameras.router, prefix="/api/v1/cameras", tags=["Cameras"])
app.include_router(vehicles.router, prefix="/api/v1/vehicles", tags=["Vehicles"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(observations.router, prefix="/api/v1/observations", tags=["Observations"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(trajectory.router, prefix="/api/v1/trajectory", tags=["Trajectory"])
app.include_router(gis.router, prefix="/api/v1/gis", tags=["GIS"])
# CongestionPage.tsx and RouteAnomalyPage.tsx (frontend/src/pages/) already
# called these paths - these routers were simply missing, so every call
# 404'd. See backend/app/api/v1/congestion.py and route_anomaly.py.
app.include_router(congestion.router, prefix="/api/v1/congestion", tags=["Congestion"])
app.include_router(route_anomaly.router, prefix="/api/v1/route-anomaly", tags=["Route Anomaly"])

# Health and monitoring endpoints
from app.api.v1 import health, road_network
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(road_network.router, tags=["Admin"])

# Serves plate crop images saved by pipeline.run_video_to_db() /
# demo/visual_pipeline.py (outputs/results/plate_crops/*.jpg) so the
# frontend can actually display obs.plate_crop_url instead of a broken
# local filesystem path. Directory is created on demand if it doesn't
# exist yet (a fresh checkout with no processed video yet).
_plate_crops_dir = os.path.join(project_root, "outputs", "results", "plate_crops")
os.makedirs(_plate_crops_dir, exist_ok=True)
app.mount("/media/plate-crops", StaticFiles(directory=_plate_crops_dir), name="plate-crops")

# Serves full annotated frames (bounding boxes + plate labels drawn in) saved
# by demo/visual_pipeline.py's process_image()/process_video() so the
# camera-folder AI processing UI can show the real annotated result image,
# not just the cropped plate.
_annotated_dir = os.path.join(project_root, "outputs", "results", "annotated")
os.makedirs(_annotated_dir, exist_ok=True)
app.mount("/media/annotated", StaticFiles(directory=_annotated_dir), name="annotated-frames")

# Serves the ACTUAL annotated output video produced by
# pipeline.write_annotated_video() (called from run_video_to_db(), which
# backs POST /ingest-video) - the real video, re-encoded and stitched
# frame by frame with real detection overlays, not a single frame image.
_annotated_videos_dir = os.path.join(project_root, "outputs", "results", "annotated_videos")
os.makedirs(_annotated_videos_dir, exist_ok=True)
app.mount("/media/annotated-videos", StaticFiles(directory=_annotated_videos_dir), name="annotated-videos")

# ---------------------------------------------------------------------------
# Phase 14 deployment: serve the built React frontend from this same
# service, so a single Render/Railway web service can host both the API and
# the UI (no second deployed service, no cross-origin CORS coordination to
# get right under time pressure). Only activates when frontend/dist exists
# (a normal `npm run build` output) - a backend-only checkout with no
# frontend build present keeps behaving exactly as before (root path
# returns the plain JSON status message, unmatched paths 404 normally).
# Nothing here changes any API route already registered above.
# ---------------------------------------------------------------------------
_frontend_dist_dir = os.path.join(project_root, "frontend", "dist")
_frontend_index_html = os.path.join(_frontend_dist_dir, "index.html")
_frontend_assets_dir = os.path.join(_frontend_dist_dir, "assets")
_SERVE_FRONTEND = os.path.isfile(_frontend_index_html)

if _SERVE_FRONTEND and os.path.isdir(_frontend_assets_dir):
    # Vite's build output puts hashed JS/CSS under dist/assets/ - serve that
    # directly rather than through the catch-all below.
    app.mount("/assets", StaticFiles(directory=_frontend_assets_dir), name="frontend-assets")


@app.get("/")
async def root():
    """Root endpoint - serves the built frontend when present, otherwise a
    plain API status message (backend-only / local API dev without a
    frontend build)."""
    if _SERVE_FRONTEND:
        return FileResponse(_frontend_index_html)
    return {
        "message": "TrackX API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }

@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    """
    Health check endpoint. Every field here is a REAL check
    (backend/app/api/v1/health.py's check_database()/check_models(), the
    same functions GET /api/v1/health/deep and /status use) - this used to
    return hardcoded literals ("database": "connected", "ai_engine":
    "operational", "ocr_engine": "LPRNet + PaddleOCR") regardless of
    whether any of that was actually true. DashboardPage.tsx's System
    Status panel reads this endpoint directly.

    SIH26127 hotfix (2026-09-29): this was `async def`, but check_models()
    does REAL, synchronous, CPU-heavy work on the first call per process -
    actually constructing the YOLO vehicle/plate detectors and PaddleOCR
    singletons (see app/api/v1/observations.py's get_model_status()), which
    can take a long time (or block on a first-run model download) on a
    resource-constrained host. Calling that directly inside `async def`
    blocked FastAPI's single-threaded event loop for the entire duration -
    freezing EVERY other in-flight request on the whole app (dashboard,
    alerts, analytics, everything), not just this endpoint. Plain `def`
    (like every other endpoint in backend/app/api/v1/health.py already
    is) makes FastAPI run this in its worker thread pool instead, so a
    slow model load only ties up one thread and the rest of the app stays
    responsive.

    SIH26127 OOM hotfix (2026-09-29): also now calls check_models with
    trigger_load=False - this endpoint fires on every routine dashboard
    page view (see docstring above), and forcing a fresh construction of
    YOLO + all three PaddleOCR models on every one of those views was
    exactly what exceeded Render's free-tier 512MB limit and got this
    instance OOM-killed (confirmed via Render's own event log). Real
    detection actions (video upload, webcam start - see
    app/api/v1/observations.py) still load models eagerly; a passive
    status check no longer does.
    """
    db_status = health.check_database()
    model_status = health.check_models(trigger_load=False)
    models = model_status.get("models", {})
    reasons = model_status.get("reasons", {})
    ocr_engines = [name for name, available in
                   (("LPRNet", models.get("lprnet")), ("PaddleOCR", models.get("paddleocr")))
                   if available]
    # SIH26127 audit fix (2026-09-10): ai_engine and ocr_engine used to be
    # computed from two DIFFERENT signals that could disagree - ai_engine
    # from a status string that was ALWAYS "healthy" (see
    # health.check_models()'s old hardcoded yolo_vehicle/yolo_plate=True),
    # ocr_engine from a real but separately-computed list. AdminPage.tsx
    # concatenates them as "{ai_engine} - {ocr_engine}", which is exactly
    # how an operator could see the self-contradictory "healthy -
    # unavailable" status. Both now come from the same
    # get_model_status()-backed model_status, so they can no longer
    # disagree - and the real reason for any unavailable component is
    # surfaced in model_reasons instead of being silently dropped.
    return {
        "status": "healthy" if db_status["status"] in ("healthy", "degraded") else "unavailable",
        "service": "trackx-api",
        "version": "1.0.0",
        "database": db_status["status"],
        "database_details": db_status,
        "ai_engine": model_status["status"],
        "ocr_engine": " + ".join(ocr_engines) if ocr_engines else "unavailable",
        "models": models,
        "model_reasons": reasons,
    }

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint - echoes back whatever a client sends it. Phase 12
    honesty-audit note: this is NOT wired to any real backend event - no
    new observation, alert, or congestion change ever triggers a broadcast
    here, and the frontend never connects to this endpoint at all. There is
    no live-push "real-time" capability in this app; every page fetches
    once per load/action. This is unused scaffolding, not working
    functionality - do not describe this app as having real-time push
    updates on the strength of this endpoint existing.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or process events
            await manager.broadcast({
                "type": "message",
                "data": data
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")


# ---------------------------------------------------------------------------
# SPA fallback - MUST be the last route registered. FastAPI matches routes
# in registration order, so every real API router/mount above (auth,
# vehicles, health, /media/plate-crops, /assets, etc.) always wins first;
# this only catches paths nothing else matched. A client-side route like
# /dashboard or /vehicles has no matching server route of its own - without
# this, loading that URL directly (not by clicking a link inside the
# already-loaded app) would 404 instead of loading the SPA, which then
# handles the route itself via React Router. Paths under /api/ are excluded
# so a real API 404 stays a real 404 instead of silently returning HTML.
# ---------------------------------------------------------------------------
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if not _SERVE_FRONTEND or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(_frontend_index_html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
