# TrackX Quick Start

## 🚀 Start in 60 Seconds

```bash
git clone <repo>
cd TrackX
pip install -r requirements-prod.txt
docker-compose up -d
```

Done! Access:
- **Dashboard:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/api/v1/health/

## 🧪 Run Tests (60 seconds)

```bash
pytest tests/ -q
# Expected: 204 passed in ~30s
```

## 📊 Try a Query (30 seconds)

```bash
# List all cameras
curl http://localhost:8000/api/v1/cameras/

# Search for vehicle trajectory
curl 'http://localhost:8000/api/v1/trajectory/search?plate_text=TN10AB1234'

# Get traffic analytics
curl http://localhost:8000/api/v1/analytics/vehicles-per-camera
```

## 🎬 Demo Video Pipeline (2 minutes)

```bash
# Load sample video through pipeline
python demo/visual_pipeline.py --sample-video

# This will:
# 1. Detect vehicles with YOLO
# 2. Detect plates within vehicles
# 3. Read plates with OCR
# 4. Store 40-60 observations in database

# Then search in dashboard
open http://localhost:8501
# Navigate to "Search" tab
# Search for any plate (e.g., "TN10AB1234")
```

## 📱 System Status

```bash
# Quick check
curl http://localhost:8000/api/v1/health/
# Response: {"status": "healthy", ...}

# Detailed check
curl http://localhost:8000/api/v1/health/deep
# Response includes database, models, components
```

## 🛠️ Common Tasks

### View All Observations
```bash
curl http://localhost:8000/api/v1/observations/ | jq .
```

### Get Traffic Analytics
```bash
curl http://localhost:8000/api/v1/analytics/cross-camera-routes | jq .
```

### List All Alerts
```bash
curl http://localhost:8000/api/v1/alerts/ | jq .
```

### Add Camera to Road Network
```bash
curl -X POST http://localhost:8000/api/v1/admin/road-network \
  -H "Content-Type: application/json" \
  -d '{
    "camera_a": "CAM_01",
    "camera_b": "CAM_02",
    "distance_km": 0.5,
    "speed_limit_kmph": 40,
    "road_type": "arterial"
  }'
```

## 📖 Documentation

- **Setup & Deploy:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **API Reference:** [API.md](API.md)
- **Architecture:** [ARCHITECTURE_STRATEGY.md](ARCHITECTURE_STRATEGY.md)
- **Full Audit:** [AUDIT_REPORT.md](AUDIT_REPORT.md)
- **Demo Guide:** [READY_FOR_SIH.md](READY_FOR_SIH.md)

## 🐛 Troubleshooting

### Dashboard won't load
```bash
streamlit run dashboard/dashboard.py --logger.level=debug
```

### API returns 404
```bash
curl http://localhost:8000/docs  # Check if API is running
```

### Tests fail
```bash
pytest tests/ -q --tb=short
```

### Database error
```bash
# Recreate indexes if missing
python -c "from database.observation_store import ObservationStore; ObservationStore()._ensure_indexes()"
```

## ✅ Verification Checklist

- [ ] `pytest tests/ -q` → 204 passed
- [ ] `curl http://localhost:8000/api/v1/health/` → status: healthy
- [ ] Dashboard loads at http://localhost:8501
- [ ] API docs visible at http://localhost:8000/docs
- [ ] Can search trajectories in dashboard
- [ ] Can query API endpoints

If all checks pass: **System is ready!**

## 🎯 Performance Baseline

- Trajectory search: <2 seconds
- Dashboard load: <3 seconds
- Health check: <60ms
- API response: <500ms
- Max observations: 100k+ (tested at 45k)

## 📞 Support

Check the documentation files above for:
- Deployment options (Docker, Kubernetes, bare metal)
- Troubleshooting guide (10+ scenarios)
- Security checklist
- Performance tuning
- Scaling roadmap

---

**Everything is working correctly when all 204 tests pass and health endpoints return green.**

Ready to demo? See [READY_FOR_SIH.md](READY_FOR_SIH.md) for the full evaluation scenario.
