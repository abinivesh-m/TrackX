"""Health check and system status endpoints."""

from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, status

from backend.app.api.deps import get_db
from backend.app.core.config import settings
from database.observation_store import database_file_exists, ObservationStore

router = APIRouter(prefix="/health", tags=["health"])


def check_database() -> Dict[str, Any]:
    """Check database connectivity and status."""
    try:
        # Try both SQLite backends
        sqlite_ready = database_file_exists()
        obs_count = 0
        if sqlite_ready:
            try:
                store = ObservationStore()
                obs_count = len(store.all_observations())
                store.close()
            except Exception as e:
                return {"status": "degraded", "error": str(e)}
        
        return {
            "status": "healthy" if sqlite_ready else "unavailable",
            "sqlite_ready": sqlite_ready,
            "observation_count": obs_count
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_models() -> Dict[str, Any]:
    """Check availability of ML models."""
    try:
        from recognition.ocr_reader import PlateOCR, LPRNET_AVAILABLE, PADDLEOCR_AVAILABLE
        from detection.vehicle_detector import VehicleDetector
        from detection.detect_plates import PlateDetector
        
        models = {
            "lprnet": LPRNET_AVAILABLE,
            "paddleocr": PADDLEOCR_AVAILABLE,
            "yolo_vehicle": True,  # Usually available
            "yolo_plate": True,     # Usually available
        }
        
        return {
            "status": "healthy" if any(models.values()) else "unavailable",
            "models": models
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.get("/", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, Any]:
    """Quick health check - database only."""
    db_status = check_database()
    is_healthy = db_status["status"] in ["healthy", "degraded"]
    
    return {
        "status": "healthy" if is_healthy else "unavailable",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "components": {
            "database": db_status
        }
    }


@router.get("/deep", status_code=status.HTTP_200_OK)
def deep_health_check() -> Dict[str, Any]:
    """Comprehensive system health check."""
    db_status = check_database()
    model_status = check_models()
    
    overall_status = "healthy"
    if db_status["status"] == "unhealthy" or model_status["status"] == "unhealthy":
        overall_status = "unhealthy"
    elif db_status["status"] == "degraded" or model_status["status"] == "degraded":
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "components": {
            "database": db_status,
            "models": model_status,
        },
        "environment": "production" if settings.DEBUG is False else "development"
    }


@router.get("/status", status_code=status.HTTP_200_OK)
def system_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Detailed system status with metrics."""
    db_status = check_database()
    model_status = check_models()
    
    try:
        from backend.app.models.camera import Camera
        camera_count = db.query(Camera).count()
    except:
        camera_count = 0
    
    try:
        from database.observation_store import ObservationStore
        store = ObservationStore()
        obs_list = store.all_observations()
        obs_count = len(obs_list)
        store.close()
    except:
        obs_count = 0
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": db_status,
            "models": model_status,
        },
        "metrics": {
            "cameras_configured": camera_count,
            "observations_stored": obs_count,
        }
    }
