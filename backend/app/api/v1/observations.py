"""
Observations API routes
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.observation import ObservationResponse
from database.observation_store import ObservationStore

router = APIRouter()

@router.get("/")
def get_observations(
    camera_id: str = Query(None, description="Filter by camera"),
    plate: str = Query(None, description="Filter by license plate"),
    limit: int = Query(100, description="Maximum number of observations"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get observations with optional filtering"""
    try:
        store = ObservationStore()
        all_obs = store.all_observations()
        
        # Apply filters
        if camera_id:
            all_obs = [obs for obs in all_obs if obs.get("camera_id") == camera_id]
        
        if plate:
            all_obs = [obs for obs in all_obs if obs.get("normalized_plate") == plate or obs.get("plate_text") == plate]
        
        # Apply limit
        all_obs = all_obs[:limit]
        
        # Convert to ObservationResponse format
        observation_responses = []
        for obs in all_obs:
            observation_responses.append({
                "id": obs.get("id", 0),
                "plate_text": obs.get("plate_text"),
                "normalized_plate": obs.get("normalized_plate"),
                "raw_plate_text": obs.get("raw_plate_text"),
                "camera_id": obs.get("camera_id"),
                "timestamp": obs.get("timestamp"),
                "vehicle_type": obs.get("vehicle_type"),
                "confidence": obs.get("confidence"),
                "vehicle_bbox": obs.get("vehicle_bbox"),
                "plate_bbox": obs.get("plate_bbox"),
                "source_file": obs.get("source_file"),
                "frame_index": obs.get("frame_index"),
                "ocr_confidence": obs.get("ocr_confidence"),
                "data_source": obs.get("data_source"),
                "annotated_output": obs.get("annotated_output"),
                "plate_crop_path": obs.get("plate_crop_path"),
                "created_at": obs.get("timestamp", datetime.utcnow().isoformat())
            })
        
        return observation_responses
        
    except Exception as e:
        raise Exception(f"Observations error: {str(e)}")
    finally:
        if 'store' in locals():
            store.close()

@router.get("/recent")
def get_recent_observations(
    limit: int = Query(20, description="Number of recent observations"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent observations"""
    try:
        store = ObservationStore()
        all_obs = store.all_observations()
        
        # Sort by timestamp descending
        all_obs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Get recent observations
        recent_obs = all_obs[:limit]
        
        # Convert to ObservationResponse format
        observation_responses = []
        for obs in recent_obs:
            observation_responses.append({
                "id": obs.get("id", 0),
                "plate_text": obs.get("plate_text"),
                "normalized_plate": obs.get("normalized_plate"),
                "camera_id": obs.get("camera_id"),
                "timestamp": obs.get("timestamp"),
                "confidence": obs.get("confidence"),
                "vehicle_type": obs.get("vehicle_type"),
                "annotated_output": obs.get("annotated_output"),
                "created_at": obs.get("timestamp", datetime.utcnow().isoformat())
            })
        
        return observation_responses
        
    except Exception as e:
        raise Exception(f"Recent observations error: {str(e)}")
    finally:
        if 'store' in locals():
            store.close()
