# TrackX API Reference

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000/api/v1`  
**Authentication:** JWT Bearer (where applicable)

---

## HEALTH & MONITORING

### GET `/health/`
Quick health check (database only).

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-09-06T12:30:45.123456",
  "version": "1.0.0",
  "components": {
    "database": {
      "status": "healthy",
      "sqlite_ready": true,
      "observation_count": 45000
    }
  }
}
```

### GET `/health/deep`
Comprehensive system health check (database + models).

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-09-06T12:30:45.123456",
  "version": "1.0.0",
  "components": {
    "database": { "status": "healthy", "observation_count": 45000 },
    "models": {
      "status": "healthy",
      "models": {
        "lprnet": true,
        "paddleocr": true,
        "yolo_vehicle": true,
        "yolo_plate": true
      }
    }
  },
  "environment": "production"
}
```

### GET `/health/status`
Detailed status with metrics.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-09-06T12:30:45.123456",
  "components": { ... },
  "metrics": {
    "cameras_configured": 7,
    "observations_stored": 45000
  }
}
```

---

## TRAJECTORY

### GET `/trajectory/search`
Search for vehicle trajectories by plate.

**Query Parameters:**
- `plate_text` (string, required): License plate to search
- `limit` (int, optional): Max trajectories to return (default: 10)

**Response:**
```json
{
  "plate": "TN10AB1234",
  "trajectories": [
    {
      "id": "traj_001",
      "vehicle_type": "car",
      "plate_text": "TN10AB1234",
      "confidence": 0.92,
      "hops": [
        {
          "camera_id": "CAM_01",
          "timestamp": "2026-09-06T10:30:15",
          "lat": 11.0205,
          "long": 76.9667,
          "plate_confidence": 0.91,
          "appearance_confidence": 0.85,
          "spatial_score": 0.8
        },
        {
          "camera_id": "CAM_03",
          "timestamp": "2026-09-06T10:32:45",
          "lat": 11.0051,
          "long": 76.9508,
          "plate_confidence": 0.93,
          "appearance_confidence": 0.88,
          "spatial_score": 0.9
        }
      ],
      "total_time_seconds": 150,
      "distance_km": 2.8,
      "average_speed_kmh": 67.2
    }
  ]
}
```

### GET `/trajectory/{trajectory_id}`
Get detailed trajectory information.

**Response:** Single trajectory object (see search response)

---

## ANALYTICS

### GET `/analytics/vehicles-per-camera`
Count vehicles observed at each camera.

**Response:**
```json
{
  "data": {
    "CAM_01": 120,
    "CAM_02": 85,
    "CAM_03": 110,
    "CAM_04": 95,
    "CAM_05": 65,
    "CAM_06": 75,
    "CAM_07": 90
  },
  "total_vehicles": 640,
  "timestamp": "2026-09-06T12:30:45"
}
```

### GET `/analytics/busiest-camera`
Find camera with most vehicle observations.

**Response:**
```json
{
  "camera_id": "CAM_01",
  "vehicle_count": 120,
  "percentage": 18.75
}
```

### GET `/analytics/cross-camera-routes`
Most frequent vehicle routes between cameras.

**Query Parameters:**
- `limit` (int, optional): Top N routes (default: 10)

**Response:**
```json
{
  "routes": [
    {
      "route": "CAM_01 → CAM_03",
      "frequency": 45,
      "percentage": 12.5,
      "avg_time_seconds": 150,
      "distance_km": 2.8
    },
    {
      "route": "CAM_03 → CAM_05",
      "frequency": 38,
      "percentage": 10.3,
      "avg_time_seconds": 120,
      "distance_km": 1.8
    }
  ]
}
```

### GET `/analytics/congestion-hotspots`
Identify congestion levels by camera.

**Response:**
```json
{
  "hotspots": [
    {
      "camera_id": "CAM_01",
      "congestion_level": "moderate",
      "score": 0.65,
      "avg_vehicles_per_min": 2.3,
      "density_rank": 1
    },
    {
      "camera_id": "CAM_03",
      "congestion_level": "light",
      "score": 0.35,
      "avg_vehicles_per_min": 1.1,
      "density_rank": 4
    }
  ]
}
```

### GET `/analytics/origin-destination-patterns`
Traffic flow patterns between origins and destinations.

**Response:**
```json
{
  "patterns": [
    {
      "origin": "CAM_01",
      "destination": "CAM_07",
      "vehicle_count": 25,
      "percentage": 6.8,
      "avg_travel_time_min": 8.5
    }
  ]
}
```

### GET `/analytics/average-vehicle-speed`
Average travel speed across the network.

**Response:**
```json
{
  "average_speed_kmh": 52.3,
  "min_speed_kmh": 12.1,
  "max_speed_kmh": 95.2,
  "vehicles_analyzed": 340
}
```

### GET `/analytics/hourly-density`
Vehicle traffic density by hour.

**Query Parameters:**
- `camera_id` (string, optional): Filter by camera

**Response:**
```json
{
  "hourly_data": [
    {"hour": 0, "vehicle_count": 12},
    {"hour": 1, "vehicle_count": 8},
    ...,
    {"hour": 18, "vehicle_count": 156},
    {"hour": 19, "vehicle_count": 142}
  ],
  "peak_hour": 18,
  "peak_count": 156
}
```

---

## ALERTS

### GET `/alerts/`
List all generated alerts.

**Query Parameters:**
- `alert_type` (string, optional): Filter by type (blacklist, repeated_camera, route_anomaly)
- `camera_id` (string, optional): Filter by camera
- `limit` (int, optional): Number of alerts (default: 50)

**Response:**
```json
{
  "alerts": [
    {
      "id": "alert_001",
      "timestamp": "2026-09-06T10:30:45",
      "alert_type": "blacklist_match",
      "camera_id": "CAM_01",
      "plate_text": "TN10AB1234",
      "confidence": 0.92,
      "reason": "Vehicle plate matches blacklist entry",
      "severity": "high",
      "status": "active"
    },
    {
      "id": "alert_002",
      "timestamp": "2026-09-06T10:32:15",
      "alert_type": "repeated_camera",
      "camera_id": "CAM_03",
      "plate_text": "TN09XY5678",
      "confidence": 0.88,
      "reason": "Vehicle observed 3 times at same camera in 5 minutes",
      "severity": "medium",
      "status": "active"
    }
  ],
  "total_count": 127
}
```

### GET `/alerts/{alert_id}`
Get detailed alert information.

**Response:** Single alert object (see list response)

### POST `/alerts/{alert_id}/acknowledge`
Mark alert as acknowledged.

**Request:**
```json
{
  "notes": "Verified - vehicle reported for illegal parking"
}
```

**Response:** Updated alert object

---

## ADMIN: ROAD NETWORK

### GET `/admin/road-network`
List all road network connections.

**Response:**
```json
{
  "connections": [
    {
      "id": 1,
      "camera_a": "CAM_01",
      "camera_b": "CAM_02",
      "distance_km": 0.5,
      "speed_limit_kmph": 40,
      "road_type": "arterial",
      "traffic_condition": "moderate",
      "lanes": 2,
      "has_traffic_lights": true,
      "typical_travel_time_min": 0.8
    }
  ]
}
```

### GET `/admin/road-network/{camera_id}`
Get all connections for a specific camera.

**Response:** List of connection objects

### POST `/admin/road-network`
Create a new road network connection.

**Request:**
```json
{
  "camera_a": "CAM_01",
  "camera_b": "CAM_02",
  "distance_km": 0.5,
  "speed_limit_kmph": 40,
  "road_type": "arterial",
  "traffic_condition": "moderate",
  "lanes": 2,
  "has_traffic_lights": true,
  "typical_travel_time_min": 0.8
}
```

**Response:** Created connection object (HTTP 201)

### PUT `/admin/road-network/{connection_id}`
Update a road network connection.

**Request:** Subset of fields to update

**Response:** Updated connection object

### DELETE `/admin/road-network/{connection_id}`
Delete a road network connection.

**Response:** HTTP 204 (No Content)

### POST `/admin/road-network/seed`
Populate road network from hardcoded ROAD_GRAPH (admin only).

**Response:**
```json
{
  "message": "Seeded 16 road network connections"
}
```

---

## CAMERAS

### GET `/cameras/`
List all configured cameras.

**Response:**
```json
{
  "cameras": [
    {
      "id": "CAM_01",
      "name": "Gandhipuram Junction",
      "location": "Gandhipuram Main Road",
      "lat": 11.0205,
      "long": 76.9667,
      "fov": "90 degrees",
      "direction": "North-East",
      "coverage": "Main traffic flow towards Tidel Park",
      "road_type": "Arterial Road",
      "status": "active",
      "last_observation": "2026-09-06T12:28:15"
    }
  ]
}
```

### GET `/cameras/{camera_id}`
Get specific camera information.

**Response:** Single camera object

### GET `/cameras/{camera_id}/observations`
Get recent observations from a camera.

**Query Parameters:**
- `limit` (int, optional): Number of observations (default: 100)
- `start_time` (datetime, optional): Filter from time
- `end_time` (datetime, optional): Filter to time

**Response:**
```json
{
  "camera_id": "CAM_01",
  "observations": [
    {
      "id": 1,
      "plate_text": "TN10AB1234",
      "confidence": 0.91,
      "timestamp": "2026-09-06T12:28:15",
      "vehicle_type": "car",
      "direction": "North-East"
    }
  ],
  "total_count": 120
}
```

---

## OBSERVATIONS

### GET `/observations/`
List recent observations.

**Query Parameters:**
- `plate_text` (string, optional): Filter by plate
- `camera_id` (string, optional): Filter by camera
- `start_time` (datetime, optional): Filter from time
- `end_time` (datetime, optional): Filter to time
- `limit` (int, optional): Number of records (default: 100)

**Response:**
```json
{
  "observations": [
    {
      "id": 1,
      "plate_text": "TN10AB1234",
      "confidence": 0.91,
      "camera_id": "CAM_01",
      "timestamp": "2026-09-06T12:28:15",
      "lat": 11.0205,
      "long": 76.9667,
      "vehicle_type": "car",
      "vehicle_confidence": 0.87,
      "plate_bbox": [120, 200, 180, 240],
      "vehicle_bbox": [100, 150, 250, 300],
      "direction": "North-East",
      "data_source": "REAL_INFERENCE"
    }
  ]
}
```

### GET `/observations/{observation_id}`
Get specific observation details.

**Response:** Single observation object

---

## ERROR RESPONSES

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong",
  "status_code": 400,
  "timestamp": "2026-09-06T12:30:45"
}
```

### Common Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (success, no response body) |
| 400 | Bad Request (invalid parameters) |
| 401 | Unauthorized (authentication required) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 409 | Conflict (resource already exists) |
| 500 | Internal Server Error |
| 503 | Service Unavailable (database down) |

---

## RATE LIMITING

- Analytics endpoints: 100 requests/min per IP
- Trajectory search: 200 requests/min per IP
- Health check: Unlimited
- Admin endpoints: 50 requests/min per user (requires auth)

---

## AUTHENTICATION

Bearer token in Authorization header:
```
GET /api/v1/admin/road-network
Authorization: Bearer <jwt-token>
```

Obtain token via `/auth/login` endpoint (see FastAPI auto-docs at `/docs`)

