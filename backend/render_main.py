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

# Demo data
DEMO_VEHICLES = [
    {"plate_text": "TN01AB1234", "camera_id": "CAM_001", "observation_count": 5, "last_seen": datetime.now().isoformat()},
    {"plate_text": "KA02CD5678", "camera_id": "CAM_002", "observation_count": 3, "last_seen": (datetime.now() - timedelta(hours=1)).isoformat()},
    {"plate_text": "MH03EF9012", "camera_id": "CAM_003", "observation_count": 7, "last_seen": (datetime.now() - timedelta(hours=2)).isoformat()},
    {"plate_text": "DL04GH3456", "camera_id": "CAM_001", "observation_count": 2, "last_seen": (datetime.now() - timedelta(hours=3)).isoformat()},
    {"plate_text": "GJ05IJ7890", "camera_id": "CAM_004", "observation_count": 4, "last_seen": (datetime.now() - timedelta(hours=4)).isoformat()},
]

DEMO_ALERTS = [
    {"id": 1, "vehicle_plate": "TN01AB1234", "alert_type": "speed_violation", "severity": "high", "timestamp": datetime.now().isoformat()},
    {"id": 2, "vehicle_plate": "KA02CD5678", "alert_type": "stolen_vehicle", "severity": "critical", "timestamp": (datetime.now() - timedelta(hours=2)).isoformat()},
    {"id": 3, "vehicle_plate": "MH03EF9012", "alert_type": "suspicious_route", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=5)).isoformat()},
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
    cameras = [
        {"id": "CAM_001", "name": "MG Road Junction", "status": "online", "latitude": 12.9716, "longitude": 77.5946},
        {"id": "CAM_002", "name": "Brigade Road", "status": "online", "latitude": 12.9720, "longitude": 77.6079},
        {"id": "CAM_003", "name": "Indiranagar", "status": "online", "latitude": 12.9784, "longitude": 77.6408},
        {"id": "CAM_004", "name": "Koramangala", "status": "online", "latitude": 12.9352, "longitude": 77.6245},
    ]
    return {"cameras": cameras, "total": len(cameras)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
