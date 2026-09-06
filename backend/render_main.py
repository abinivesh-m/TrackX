"""
Simplified TrackX Backend for Render.com
No database - returns demo data for frontend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import random

app = FastAPI(
    title="TrackX API",
    description="City-Wide Vehicle Intelligence System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Demo data - Real Coimbatore cameras
DEMO_CAMERAS = [
    {"id": "CAM_01", "name": "Gandhipuram Junction", "status": "online", "latitude": 11.0205, "longitude": 76.9667},
    {"id": "CAM_02", "name": "Tidel Park Junction", "status": "online", "latitude": 11.0167, "longitude": 76.9707},
    {"id": "CAM_03", "name": "RS Puram Signal", "status": "online", "latitude": 11.0051, "longitude": 76.9508},
    {"id": "CAM_04", "name": "Lakshmi Mills Junction", "status": "online", "latitude": 11.0128, "longitude": 76.9889},
    {"id": "CAM_05", "name": "Town Hall Junction", "status": "online", "latitude": 10.9911, "longitude": 76.9600},
    {"id": "CAM_06", "name": "Gandhipuram Bus Stand", "status": "online", "latitude": 11.0200, "longitude": 76.9680},
    {"id": "CAM_07", "name": "Singanallur Junction", "status": "online", "latitude": 10.9990, "longitude": 77.0324},
]

# Real vehicle TN 09 CX 7134 tracked across 5 cameras
DEMO_VEHICLES = [
    {"plate_text": "TN09CX7134", "camera_id": "CAM_02", "observation_count": 5, "last_seen": "2025-03-06T10:22:47", "latitude": 11.0167, "longitude": 76.9707},
    {"plate_text": "TN09CX7134", "camera_id": "CAM_03", "observation_count": 5, "last_seen": "2025-03-06T12:31:09", "latitude": 11.0051, "longitude": 76.9508},
    {"plate_text": "TN09CX7134", "camera_id": "CAM_05", "observation_count": 5, "last_seen": "2025-03-06T18:05:44", "latitude": 10.9911, "longitude": 76.9600},
    {"plate_text": "TN09CX7134", "camera_id": "CAM_06", "observation_count": 5, "last_seen": "2025-03-06T20:17:33", "latitude": 11.0200, "longitude": 76.9680},
    {"plate_text": "TN09CX7134", "camera_id": "CAM_07", "observation_count": 5, "last_seen": "2025-03-06T22:38:56", "latitude": 10.9990, "longitude": 77.0324},
]

DEMO_ALERTS = [
    {"id": 1, "vehicle_plate": "TN09CX7134", "alert_type": "speed_violation", "severity": "high", "timestamp": datetime.now().isoformat(), "description": "Excessive speed detected", "status": "active", "created_at": datetime.now().isoformat()},
    {"id": 2, "vehicle_plate": "TN09CX7134", "alert_type": "stolen_vehicle", "severity": "critical", "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(), "description": "Vehicle flagged as stolen", "status": "active", "created_at": (datetime.now() - timedelta(hours=2)).isoformat()},
    {"id": 3, "vehicle_plate": "TN09CX7134", "alert_type": "suspicious_route", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(), "description": "Unusual travel pattern detected", "status": "active", "created_at": (datetime.now() - timedelta(hours=5)).isoformat()},
]

@app.get("/")
async def root():
    return {
        "message": "TrackX API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }

@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "trackx-api",
        "version": "1.0.0",
        "database": "demo-mode",
        "ai_engine": "operational",
        "ocr_engine": "LPRNet + PaddleOCR"
    }

@app.get("/api/v1/analytics/stats")
async def get_stats():
    return {
        "total_observations": 1954,
        "unique_vehicles": 1000,
        "avg_ocr_confidence": 90.82,
        "active_alerts": len(DEMO_ALERTS),
        "cameras_online": 12,
        "last_updated": datetime.now().isoformat()
    }

@app.get("/api/v1/vehicles")
async def get_vehicles():
    return {
        "vehicles": DEMO_VEHICLES,
        "total": len(DEMO_VEHICLES)
    }

@app.get("/api/v1/vehicles/{plate}")
async def get_vehicle(plate: str):
    vehicle = next((v for v in DEMO_VEHICLES if v["plate_text"] == plate), None)
    if vehicle:
        return vehicle
    return {"error": "Vehicle not found"}

@app.get("/api/v1/alerts")
async def get_alerts():
    return {
        "alerts": DEMO_ALERTS,
        "total": len(DEMO_ALERTS)
    }

@app.get("/api/v1/analytics/hourly")
async def get_hourly_analytics():
    hours = []
    for i in range(24):
        hours.append({
            "hour": i,
            "count": random.randint(20, 150),
            "timestamp": (datetime.now() - timedelta(hours=23-i)).isoformat()
        })
    return {"data": hours}

@app.get("/api/v1/cameras")
async def get_cameras():
    return {"cameras": DEMO_CAMERAS, "total": len(DEMO_CAMERAS)}

@app.get("/api/v1/vehicles/{plate}/trajectory")
async def get_vehicle_trajectory(plate: str):
    """Get vehicle trajectory showing path across cameras"""
    if plate.upper().replace(" ", "") == "TN09CX7134":
        trajectory = [
            {"camera_id": "CAM_02", "camera_name": "Tidel Park Junction", "timestamp": "2025-03-06T10:22:47", "latitude": 11.0167, "longitude": 76.9707},
            {"camera_id": "CAM_03", "camera_name": "RS Puram Signal", "timestamp": "2025-03-06T12:31:09", "latitude": 11.0051, "longitude": 76.9508},
            {"camera_id": "CAM_05", "camera_name": "Town Hall Junction", "timestamp": "2025-03-06T18:05:44", "latitude": 10.9911, "longitude": 76.9600},
            {"camera_id": "CAM_06", "camera_name": "Gandhipuram Bus Stand", "timestamp": "2025-03-06T20:17:33", "latitude": 11.0200, "longitude": 76.9680},
            {"camera_id": "CAM_07", "camera_name": "Singanallur Junction", "timestamp": "2025-03-06T22:38:56", "latitude": 10.9990, "longitude": 77.0324},
        ]
        return {"plate": plate, "trajectory": trajectory, "total_observations": len(trajectory)}
    return {"plate": plate, "trajectory": [], "total_observations": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
