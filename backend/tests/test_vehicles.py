# backend/tests/test_vehicles.py

import pytest
from datetime import datetime, timedelta
from app.models.observation import Observation
from app.models.camera import Camera
from app.services.vehicle_service import VehicleService


@pytest.mark.asyncio
async def test_search_vehicle_not_found(db_session):
    """Test searching for a vehicle that doesn't exist."""
    service = VehicleService(db_session)
    result = await service.search_vehicle("TN00AA0000")
    
    assert result["vehicle_found"] is False
    assert result["trajectory"] is None


@pytest.mark.asyncio
async def test_create_camera(db_session):
    """Test camera creation."""
    from app.services.camera_service import CameraService
    from app.schemas.camera import CameraCreate
    
    service = CameraService(db_session)
    camera = await service.create_camera(
        CameraCreate(
            camera_id="TEST_CAM",
            name="Test Camera",
            location="Test Location",
            latitude=11.0168,
            longitude=76.9558
        )
    )
    
    assert camera.camera_id == "TEST_CAM"
    assert camera.name == "Test Camera"


@pytest.mark.asyncio
async def test_get_camera_by_id(db_session):
    """Test retrieving camera by ID."""
    from app.services.camera_service import CameraService
    from app.schemas.camera import CameraCreate
    
    service = CameraService(db_session)
    await service.create_camera(
        CameraCreate(
            camera_id="CAM_01",
            name="Camera One",
            latitude=11.0168,
            longitude=76.9558
        )
    )
    
    camera = await service.get_camera_by_id("CAM_01")
    
    assert camera is not None
    assert camera.name == "Camera One"
