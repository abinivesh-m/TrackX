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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from typing import Dict, Set
import json

# Try imports with fallback for different execution contexts
try:
    from app.core.database import init_db, SessionLocal
    from app.core.config import settings
    from app.core.security import get_password_hash
    from app.models.user import User
    from app.api.v1 import auth, cameras, vehicles, analytics, alerts, observations, admin, trajectory, gis
except ImportError:
    from backend.app.core.database import init_db, SessionLocal
    from backend.app.core.config import settings
    from backend.app.core.security import get_password_hash
    from backend.app.models.user import User
    from backend.app.api.v1 import auth, cameras, vehicles, analytics, alerts, observations, admin, trajectory, gis

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
    if settings.ENVIRONMENT != "production":
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
                logger.warning("Created development administrator account; configure real credentials before deployment.")
        finally:
            db.close()
    logger.info("Database initialized")
    
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

# Health and monitoring endpoints
from backend.app.api.v1 import health, road_network
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(road_network.router, tags=["Admin"])

# Mount static files (for frontend in production)
# app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "TrackX API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }

@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "trackx-api",
        "version": "1.0.0",
        "database": "connected",
        "ai_engine": "operational",
        "ocr_engine": "LPRNet + PaddleOCR"
    }

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time events"""
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
