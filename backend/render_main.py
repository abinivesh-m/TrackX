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

# Generate 50+ realistic vehicles with timestamps spread across 24 hours
def generate_demo_vehicles():
    """Generate realistic vehicle data for demonstration"""
    vehicles = []
    camera_ids = ["CAM_01", "CAM_02", "CAM_03", "CAM_04", "CAM_05", "CAM_06", "CAM_07"]
    camera_coords = {
        "CAM_01": (11.0205, 76.9667),
        "CAM_02": (11.0167, 76.9707),
        "CAM_03": (11.0051, 76.9508),
        "CAM_04": (11.0128, 76.9889),
        "CAM_05": (10.9911, 76.9600),
        "CAM_06": (11.0200, 76.9680),
        "CAM_07": (10.9990, 77.0324),
    }
    
    # TN09CX7134 - Main tracked vehicle across 5 cameras
    vehicles.extend([
        {"plate_text": "TN09CX7134", "camera_id": "CAM_02", "observation_count": 5, "last_seen": "2025-03-06T10:22:47", "latitude": 11.0167, "longitude": 76.9707},
        {"plate_text": "TN09CX7134", "camera_id": "CAM_03", "observation_count": 5, "last_seen": "2025-03-06T12:31:09", "latitude": 11.0051, "longitude": 76.9508},
        {"plate_text": "TN09CX7134", "camera_id": "CAM_05", "observation_count": 5, "last_seen": "2025-03-06T18:05:44", "latitude": 10.9911, "longitude": 76.9600},
        {"plate_text": "TN09CX7134", "camera_id": "CAM_06", "observation_count": 5, "last_seen": "2025-03-06T20:17:33", "latitude": 11.0200, "longitude": 76.9680},
        {"plate_text": "TN09CX7134", "camera_id": "CAM_07", "observation_count": 5, "last_seen": "2025-03-06T22:38:56", "latitude": 10.9990, "longitude": 77.0324},
    ])
    
    # Generate 50+ additional unique vehicles
    prefixes = ["AB", "CD", "EF", "GH", "IJ", "KL", "MN", "OP", "QR", "ST", "UV", "WX", "YZ", "AA", "BB", "CC", "DD", "EE", "FF", "GG", "HH", "II", "JJ", "KK", "LL", "MM", "NN", "OO", "PP", "QQ", "RR", "SS", "TT", "UU", "VV", "WW", "XX", "YY", "ZZ", "AX", "BY", "CZ", "DX", "EY", "FZ", "GX", "HY", "IZ"]
    
    for i, prefix in enumerate(prefixes):
        plate_num = str(1000 + i * 111)[:4]
        plate = f"TN09{prefix}{plate_num}"
        camera = camera_ids[i % len(camera_ids)]
        lat, lng = camera_coords[camera]
        hour = i % 24
        minute = (i * 17) % 60
        timestamp = f"2025-03-06T{hour:02d}:{minute:02d}:{(i*13)%60:02d}"
        obs_count = (i % 7) + 1
        
        vehicles.append({
            "plate_text": plate,
            "camera_id": camera,
            "observation_count": obs_count,
            "last_seen": timestamp,
            "latitude": lat,
            "longitude": lng
        })
    
    return vehicles

DEMO_VEHICLES = generate_demo_vehicles()

# Generate 20+ realistic alerts for demo
DEMO_ALERTS = [
    {"id": 1, "vehicle_plate": "TN09CX7134", "alert_type": "speed_violation", "severity": "high", "timestamp": datetime.now().isoformat(), "description": "Excessive speed detected at 85 km/h in 40 zone", "status": "active", "created_at": datetime.now().isoformat(), "camera_id": "CAM_02", "location": "Tidel Park Junction"},
    {"id": 2, "vehicle_plate": "TN09CX7134", "alert_type": "stolen_vehicle", "severity": "critical", "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(), "description": "Vehicle flagged as stolen in police database", "status": "active", "created_at": (datetime.now() - timedelta(hours=2)).isoformat(), "camera_id": "CAM_05", "location": "Town Hall Junction"},
    {"id": 3, "vehicle_plate": "TN09CX7134", "alert_type": "suspicious_route", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(), "description": "Unusual travel pattern detected across 5 cameras", "status": "active", "created_at": (datetime.now() - timedelta(hours=5)).isoformat(), "camera_id": "CAM_07", "location": "Singanallur Junction"},
    {"id": 4, "vehicle_plate": "TN09AB1234", "alert_type": "wrong_way", "severity": "critical", "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(), "description": "Vehicle traveling in wrong direction", "status": "active", "created_at": (datetime.now() - timedelta(hours=1)).isoformat(), "camera_id": "CAM_01", "location": "Gandhipuram Junction"},
    {"id": 5, "vehicle_plate": "TN09CD5678", "alert_type": "signal_violation", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(), "description": "Red light violation detected", "status": "active", "created_at": (datetime.now() - timedelta(hours=3)).isoformat(), "camera_id": "CAM_03", "location": "RS Puram Signal"},
    {"id": 6, "vehicle_plate": "TN09EF9012", "alert_type": "blacklist_match", "severity": "critical", "timestamp": (datetime.now() - timedelta(hours=4)).isoformat(), "description": "Vehicle matches blacklist entry", "status": "active", "created_at": (datetime.now() - timedelta(hours=4)).isoformat(), "camera_id": "CAM_04", "location": "Lakshmi Mills Junction"},
    {"id": 7, "vehicle_plate": "TN09GH3456", "alert_type": "parking_violation", "severity": "low", "timestamp": (datetime.now() - timedelta(hours=6)).isoformat(), "description": "Illegal parking detected", "status": "resolved", "created_at": (datetime.now() - timedelta(hours=6)).isoformat(), "camera_id": "CAM_05", "location": "Town Hall Junction"},
    {"id": 8, "vehicle_plate": "TN09IJ7890", "alert_type": "speed_violation", "severity": "high", "timestamp": (datetime.now() - timedelta(hours=7)).isoformat(), "description": "Speed limit exceeded by 30 km/h", "status": "active", "created_at": (datetime.now() - timedelta(hours=7)).isoformat(), "camera_id": "CAM_06", "location": "Gandhipuram Bus Stand"},
    {"id": 9, "vehicle_plate": "TN09KL2345", "alert_type": "suspicious_route", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=8)).isoformat(), "description": "Vehicle visited same location 5 times in 2 hours", "status": "active", "created_at": (datetime.now() - timedelta(hours=8)).isoformat(), "camera_id": "CAM_07", "location": "Singanallur Junction"},
    {"id": 10, "vehicle_plate": "TN09MN6789", "alert_type": "no_helmet", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=9)).isoformat(), "description": "Two-wheeler without helmet detected", "status": "active", "created_at": (datetime.now() - timedelta(hours=9)).isoformat(), "camera_id": "CAM_01", "location": "Gandhipuram Junction"},
    {"id": 11, "vehicle_plate": "TN09OP0123", "alert_type": "overloading", "severity": "high", "timestamp": (datetime.now() - timedelta(hours=10)).isoformat(), "description": "Vehicle overloading detected", "status": "active", "created_at": (datetime.now() - timedelta(hours=10)).isoformat(), "camera_id": "CAM_02", "location": "Tidel Park Junction"},
    {"id": 12, "vehicle_plate": "TN09QR4567", "alert_type": "lane_violation", "severity": "low", "timestamp": (datetime.now() - timedelta(hours=11)).isoformat(), "description": "Improper lane usage", "status": "resolved", "created_at": (datetime.now() - timedelta(hours=11)).isoformat(), "camera_id": "CAM_03", "location": "RS Puram Signal"},
    {"id": 13, "vehicle_plate": "TN09ST8901", "alert_type": "traffic_violation", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=12)).isoformat(), "description": "Multiple traffic violations detected", "status": "active", "created_at": (datetime.now() - timedelta(hours=12)).isoformat(), "camera_id": "CAM_04", "location": "Lakshmi Mills Junction"},
    {"id": 14, "vehicle_plate": "TN09UV2345", "alert_type": "stolen_vehicle", "severity": "critical", "timestamp": (datetime.now() - timedelta(hours=13)).isoformat(), "description": "Reported stolen 2 days ago", "status": "active", "created_at": (datetime.now() - timedelta(hours=13)).isoformat(), "camera_id": "CAM_05", "location": "Town Hall Junction"},
    {"id": 15, "vehicle_plate": "TN09WX6789", "alert_type": "speed_violation", "severity": "high", "timestamp": (datetime.now() - timedelta(hours=14)).isoformat(), "description": "Racing suspected - speed 120 km/h", "status": "active", "created_at": (datetime.now() - timedelta(hours=14)).isoformat(), "camera_id": "CAM_06", "location": "Gandhipuram Bus Stand"},
    {"id": 16, "vehicle_plate": "TN09YZ0123", "alert_type": "suspicious_route", "severity": "high", "timestamp": (datetime.now() - timedelta(hours=15)).isoformat(), "description": "Circular route pattern detected", "status": "active", "created_at": (datetime.now() - timedelta(hours=15)).isoformat(), "camera_id": "CAM_07", "location": "Singanallur Junction"},
    {"id": 17, "vehicle_plate": "TN09AA4567", "alert_type": "document_violation", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=16)).isoformat(), "description": "Expired registration detected", "status": "active", "created_at": (datetime.now() - timedelta(hours=16)).isoformat(), "camera_id": "CAM_01", "location": "Gandhipuram Junction"},
    {"id": 18, "vehicle_plate": "TN09BB8901", "alert_type": "signal_violation", "severity": "medium", "timestamp": (datetime.now() - timedelta(hours=17)).isoformat(), "description": "Signal jump at yellow light", "status": "resolved", "created_at": (datetime.now() - timedelta(hours=17)).isoformat(), "camera_id": "CAM_02", "location": "Tidel Park Junction"},
    {"id": 19, "vehicle_plate": "TN09CC2345", "alert_type": "wrong_way", "severity": "critical", "timestamp": (datetime.now() - timedelta(hours=18)).isoformat(), "description": "One-way violation detected", "status": "active", "created_at": (datetime.now() - timedelta(hours=18)).isoformat(), "camera_id": "CAM_03", "location": "RS Puram Signal"},
    {"id": 20, "vehicle_plate": "TN09DD6789", "alert_type": "blacklist_match", "severity": "critical", "timestamp": (datetime.now() - timedelta(hours=19)).isoformat(), "description": "Vehicle involved in previous hit-and-run", "status": "active", "created_at": (datetime.now() - timedelta(hours=19)).isoformat(), "camera_id": "CAM_04", "location": "Lakshmi Mills Junction"},
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
    # Group by plate_text to show unique vehicles with their latest observation
    unique_vehicles = {}
    for v in DEMO_VEHICLES:
        plate = v["plate_text"]
        if plate not in unique_vehicles:
            unique_vehicles[plate] = v.copy()
        else:
            # Keep the latest observation
            if v["last_seen"] > unique_vehicles[plate]["last_seen"]:
                unique_vehicles[plate] = v.copy()
    
    vehicles_list = list(unique_vehicles.values())
    return {
        "vehicles": vehicles_list,
        "total": len(vehicles_list)
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

@app.get("/api/v1/vehicles/{plate}/details")
async def get_vehicle_details(plate: str):
    """Get complete vehicle details including all observations, alerts, and risk status"""
    plate_upper = plate.upper().replace(" ", "")
    
    # Find all observations for this plate
    vehicle_obs = [v for v in DEMO_VEHICLES if v["plate_text"] == plate_upper]
    
    if not vehicle_obs:
        return {"error": "Vehicle not found", "plate": plate}
    
    # Sort by timestamp to get first and last seen
    sorted_obs = sorted(vehicle_obs, key=lambda x: x["last_seen"])
    first_seen = sorted_obs[0]["last_seen"]
    last_seen = sorted_obs[-1]["last_seen"]
    
    # Get all cameras visited
    cameras_visited = list(set([v["camera_id"] for v in vehicle_obs]))
    
    # Get all alerts for this vehicle
    vehicle_alerts = [a for a in DEMO_ALERTS if a["vehicle_plate"] == plate_upper]
    
    # Calculate risk score based on alerts
    risk_score = 0
    if any(a["severity"] == "critical" for a in vehicle_alerts):
        risk_score = 90
        risk_level = "CRITICAL"
    elif any(a["severity"] == "high" for a in vehicle_alerts):
        risk_score = 70
        risk_level = "HIGH"
    elif any(a["severity"] == "medium" for a in vehicle_alerts):
        risk_score = 40
        risk_level = "MEDIUM"
    else:
        risk_score = 10
        risk_level = "LOW"
    
    # Get trajectory if available
    trajectory_response = await get_vehicle_trajectory(plate)
    
    return {
        "plate": plate_upper,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "total_observations": len(vehicle_obs),
        "cameras_visited": cameras_visited,
        "camera_count": len(cameras_visited),
        "alerts": vehicle_alerts,
        "alert_count": len(vehicle_alerts),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "blacklist_status": "BLACKLISTED" if risk_level == "CRITICAL" else "CLEAR",
        "trajectory": trajectory_response.get("trajectory", []),
        "observations": vehicle_obs,
        "vehicle_type": "Car",
        "state": "Tamil Nadu",
        "registration_year": "2020",
    }

@app.post("/api/v1/upload/image")
async def upload_image():
    """
    Endpoint for live image ingestion (OCR processing)
    In production, this would process the image with PaddleOCR/LPRNet
    For demo, returns mock OCR results
    """
    return {
        "success": True,
        "message": "Image processed successfully",
        "ocr_results": {
            "plate_text": "TN09CX7134",
            "confidence": 0.92,
            "processing_time_ms": 145,
            "detection_box": [[100, 50], [300, 50], [300, 120], [100, 120]],
            "camera_id": "UPLOAD",
            "timestamp": datetime.now().isoformat()
        },
        "note": "Live OCR processing available in full deployment"
    }

@app.get("/api/v1/analytics/camera-performance")
async def get_camera_performance():
    """Get individual camera performance metrics"""
    return {
        "cameras": [
            {"id": "CAM_01", "name": "Gandhipuram Junction", "accuracy": 99.2, "uptime": 99.8, "vehicles_today": 1245},
            {"id": "CAM_02", "name": "Tidel Park Junction", "accuracy": 98.8, "uptime": 99.5, "vehicles_today": 1189},
            {"id": "CAM_03", "name": "RS Puram Signal", "accuracy": 99.5, "uptime": 99.9, "vehicles_today": 1432},
            {"id": "CAM_04", "name": "Lakshmi Mills Junction", "accuracy": 97.9, "uptime": 98.7, "vehicles_today": 987},
            {"id": "CAM_05", "name": "Town Hall Junction", "accuracy": 98.4, "uptime": 99.2, "vehicles_today": 1567},
            {"id": "CAM_06", "name": "Gandhipuram Bus Stand", "accuracy": 99.1, "uptime": 99.6, "vehicles_today": 1834},
            {"id": "CAM_07", "name": "Singanallur Junction", "accuracy": 98.6, "uptime": 99.3, "vehicles_today": 1098},
        ]
    }

@app.get("/api/v1/analytics/vehicles-per-camera")
async def get_vehicles_per_camera():
    """Get vehicle count by camera for bar chart"""
    camera_counts = {}
    for vehicle in DEMO_VEHICLES:
        cam = vehicle["camera_id"]
        camera_counts[cam] = camera_counts.get(cam, 0) + 1
    
    return {
        "data": [
            {"camera_id": cam_id, "camera_name": next((c["name"] for c in DEMO_CAMERAS if c["id"] == cam_id), cam_id), "count": count}
            for cam_id, count in sorted(camera_counts.items())
        ]
    }

@app.get("/api/v1/analytics/congestion")
async def get_congestion_hotspots():
    """Get congestion hotspots (cameras above threshold)"""
    threshold = 10  # vehicles per camera
    camera_counts = {}
    for vehicle in DEMO_VEHICLES:
        cam = vehicle["camera_id"]
        camera_counts[cam] = camera_counts.get(cam, 0) + 1
    
    congested = [(cam, count) for cam, count in camera_counts.items() if count >= threshold]
    congested_sorted = sorted(congested, key=lambda x: x[1], reverse=True)
    
    return {
        "threshold": threshold,
        "congested_cameras": [
            {
                "camera_id": cam,
                "camera_name": next((c["name"] for c in DEMO_CAMERAS if c["id"] == cam), cam),
                "vehicle_count": count,
                "severity": "HIGH" if count >= threshold * 1.5 else "MEDIUM"
            }
            for cam, count in congested_sorted
        ],
        "status": "detected" if congested_sorted else "clear"
    }

@app.get("/api/v1/analytics/speed-by-pair")
async def get_speed_by_camera_pair():
    """Get average speed between camera pairs"""
    # Mock data for demo - in production, calculate from trajectories
    return {
        "speeds": [
            {"from_camera": "CAM_01", "to_camera": "CAM_02", "from_name": "Gandhipuram Junction", "to_name": "Tidel Park Junction", "avg_speed_kmh": 35.2, "sample_count": 45},
            {"from_camera": "CAM_02", "to_camera": "CAM_03", "from_name": "Tidel Park Junction", "to_name": "RS Puram Signal", "avg_speed_kmh": 42.8, "sample_count": 38},
            {"from_camera": "CAM_03", "to_camera": "CAM_05", "from_name": "RS Puram Signal", "to_name": "Town Hall Junction", "avg_speed_kmh": 38.5, "sample_count": 29},
            {"from_camera": "CAM_05", "to_camera": "CAM_06", "from_name": "Town Hall Junction", "to_name": "Gandhipuram Bus Stand", "avg_speed_kmh": 31.7, "sample_count": 41},
            {"from_camera": "CAM_06", "to_camera": "CAM_07", "from_name": "Gandhipuram Bus Stand", "to_name": "Singanallur Junction", "avg_speed_kmh": 45.3, "sample_count": 33},
        ],
        "overall_avg_speed": 38.7
    }

@app.get("/api/v1/analytics/od-patterns")
async def get_origin_destination_patterns():
    """Get top origin-destination patterns"""
    return {
        "top_od_pairs": [
            {"origin": "CAM_01", "destination": "CAM_07", "origin_name": "Gandhipuram Junction", "dest_name": "Singanallur Junction", "count": 67, "avg_time_minutes": 45},
            {"origin": "CAM_02", "destination": "CAM_05", "origin_name": "Tidel Park Junction", "dest_name": "Town Hall Junction", "count": 54, "avg_time_minutes": 32},
            {"origin": "CAM_03", "destination": "CAM_06", "origin_name": "RS Puram Signal", "dest_name": "Gandhipuram Bus Stand", "count": 48, "avg_time_minutes": 28},
            {"origin": "CAM_04", "destination": "CAM_02", "origin_name": "Lakshmi Mills Junction", "dest_name": "Tidel Park Junction", "count": 41, "avg_time_minutes": 22},
            {"origin": "CAM_05", "destination": "CAM_01", "origin_name": "Town Hall Junction", "dest_name": "Gandhipuram Junction", "count": 39, "avg_time_minutes": 25},
        ]
    }

@app.get("/api/v1/analytics/repeated-sightings")
async def get_repeated_camera_sightings():
    """Get vehicles with repeated sightings at same camera"""
    # Mock data - in production, analyze trajectories for repeated visits
    return {
        "repeated_sightings": [
            {"camera_id": "CAM_01", "camera_name": "Gandhipuram Junction", "vehicle_count": 3, "plates": ["TN09AB1234", "TN09MN6789", "TN09CX7134"]},
            {"camera_id": "CAM_06", "camera_name": "Gandhipuram Bus Stand", "vehicle_count": 2, "plates": ["TN09IJ7890", "TN09CX7134"]},
            {"camera_id": "CAM_03", "camera_name": "RS Puram Signal", "vehicle_count": 2, "plates": ["TN09CD5678", "TN09QR4567"]},
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
