"""Health check and system status endpoints."""

from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, status

from app.api.deps import get_db
from app.core.config import settings
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
        from recognition.ocr_reader import PlateOCR, PADDLEOCR_AVAILABLE
        from detection.vehicle_detector import VehicleDetector
        from detection.detect_plates import PlateDetector

        models = {
            # LPRNet was removed from the live OCR path (see
            # recognition/ocr_reader.py) - it never had a trained checkpoint
            # in this repo and could only ever fall through to PaddleOCR
            # anyway, so it's reported as not in use rather than checked.
            "lprnet": False,
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
        "environment": settings.ENVIRONMENT
    }


@router.get("/status", status_code=status.HTTP_200_OK)
def system_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Detailed system status with metrics."""
    db_status = check_database()
    model_status = check_models()
    
    try:
        # Camera.observations is a relationship("Observation", ...) resolved
        # by name at mapper-configure time. Camera is otherwise never
        # imported anywhere in the live app (the app/services/* modules
        # that also import it are dead code, never imported by any
        # router), so importing Camera here without Observation used to
        # leave that relationship permanently unresolvable: SQLAlchemy's
        # configure_mappers() runs once per process and caches the failure
        # on the mapper, which then poisons every subsequent ORM query in
        # the whole process (not just this endpoint - a bare except here
        # only hid the immediate symptom) with
        # "InvalidRequestError: One or more mappers failed to initialize".
        # Importing Observation alongside Camera lets the relationship
        # resolve correctly the first time, so calling this endpoint can
        # no longer break every other endpoint that touches the database
        # afterward.
        from app.models.camera import Camera
        from app.models.observation import Observation  # noqa: F401 - required for Camera's relationship("Observation") to resolve
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
