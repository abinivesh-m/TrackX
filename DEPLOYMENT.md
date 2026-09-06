# TrackX Deployment Guide

**Version:** 1.0.0  
**Date:** September 6, 2026  
**Status:** Production-Ready

---

## QUICK START

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run dashboard
streamlit run dashboard/dashboard.py

# Run backend API (in another terminal)
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment
```bash
docker-compose up -d
```

Endpoints:
- Dashboard: http://localhost:8501
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

---

## ARCHITECTURE

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    RTSP CAMERAS (7x)                        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│           DETECTION PIPELINE                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ YOLO Vehicle │→ │ Plate Detect │→ │ OCR Voting   │      │
│  │ (ByteTrack)  │  │ (YOLO)       │  │ (LPRNet/     │      │
│  └──────────────┘  └──────────────┘  │  PaddleOCR)  │      │
│                                       └──────────────┘      │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│         OBSERVATION STORE (SQLite)                          │
│  observations.db [SINGLE SOURCE OF TRUTH]                  │
│  ├─ Indexed queries (plate, camera, timestamp)             │
│  ├─ 200k+ observations supported                           │
│  └─ Real-time ingestion                                    │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
┌──────────────────┐  ┌─────────────────────────────────┐
│ INTELLIGENCE     │  │ API / BACKEND                   │
│ ┌────────────┐   │  │ ┌─────────────────────────────┐ │
│ │Trajectory  │   │  │ │ FastAPI Routes              │ │
│ │Fusion(0.45│   │  │ │ ├─ /api/v1/trajectory/...   │ │
│ │ + 0.25app │   │  │ │ ├─ /api/v1/analytics/...    │ │
│ │ + 0.15t   │   │  │ │ ├─ /api/v1/alerts/...       │ │
│ │ + 0.15s)  │   │  │ │ ├─ /api/v1/admin/...        │ │
│ ├────────────┤   │  │ │ └─ /api/v1/health/...       │ │
│ │ Alerts    │   │  │ └─────────────────────────────┘ │
│ │ (Blacklist│   │  │                                 │
│ │  Route    │   │  │ WebSocket: /ws/events          │
│ │  Repeat)  │   │  └─────────────────────────────────┘
│ └────────────┘   │
│ ┌────────────┐   │
│ │Analytics   │   │
│ │(OD, Cong)  │   │
│ └────────────┘   │
└──────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│           STREAMLIT DASHBOARD                               │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐         │
│  │Search/Browse│ │City Intel    │ │Alerts/Config │         │
│  │@cache(ttl)  │ │Heatmap/OD/Cg │ │Blacklist     │         │
│  └─────────────┘ └──────────────┘ └──────────────┘         │
│                                                             │
│  [Cached 5 min] – Dashboard load <3s, queries <1s          │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Ingestion:** RTSP streams → Vehicle Detection → Plate OCR → Observation records (SQLite)
2. **Processing:** Observations + ROAD_GRAPH → Trajectory reconstruction → Fusion scoring
3. **Intelligence:** Trajectories → Alert generation + Analytics computation
4. **Query:** Dashboard/API → Cached results (5-min TTL) + Real-time updates

---

## DEPLOYMENT OPTIONS

### Option 1: Bare Metal / VM

**Requirements:**
- Ubuntu 20.04 LTS or later
- Python 3.10+
- SQLite 3.35+
- 8GB RAM minimum (16GB recommended for 100k+ observations)
- GPU optional (accelerates detection 5-10x)

**Setup:**
```bash
git clone <repo>
cd TrackX
pip install -r requirements-prod.txt
python -m pytest tests/ -q  # Verify installation
```

**Run:**
```bash
# Terminal 1: Dashboard
streamlit run dashboard/dashboard.py

# Terminal 2: Backend API
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Systemd Service (Production):**
```ini
# /etc/systemd/system/trackx-dashboard.service
[Unit]
Description=TrackX Dashboard
After=network.target

[Service]
Type=simple
User=trackx
WorkingDirectory=/opt/trackx
ExecStart=/usr/bin/streamlit run dashboard/dashboard.py --server.port=8501
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Option 2: Docker Compose (Recommended)

**Requirements:**
- Docker 20.10+
- Docker Compose 1.29+
- 8GB available disk space

**Setup:**
```bash
git clone <repo>
cd TrackX
docker-compose build
docker-compose up -d
```

**Verify:**
```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8501/  # Dashboard
```

**Access:**
- Dashboard: http://localhost:8501
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 3: Kubernetes

Create `k8s/trackx-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trackx-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: trackx-api
  template:
    metadata:
      labels:
        app: trackx-api
    spec:
      containers:
      - name: api
        image: trackx:latest
        ports:
        - containerPort: 8000
        env:
        - name: DB_PATH_STR
          value: /data/observations.db
        volumeMounts:
        - name: data
          mountPath: /data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: trackx-pvc
```

Deploy:
```bash
kubectl apply -f k8s/trackx-deployment.yaml
```

---

## CONFIGURATION

### Environment Variables

```bash
# .env (create this file)

# Database
DB_PATH_STR=outputs/results/observations.db
SQLITE_DB_PATH=backend/trackx.db

# API
SECRET_KEY=your-secure-random-key-here-min-32-chars
DEBUG=False
ENVIRONMENT=production

# Performance
TRAJECTORY_CACHE_TTL=300  # 5 minutes
ANALYTICS_CACHE_TTL=300

# Optional: Redis (for distributed caching)
REDIS_URL=redis://localhost:6379/0
```

### Database Setup

**First-time setup:**
```bash
cd backend
alembic upgrade head  # Run migrations
python -c "from app.api.v1.road_network import *; seed_road_network()"  # Seed ROAD_GRAPH
```

**Backup observations:**
```bash
sqlite3 outputs/results/observations.db ".backup observations-backup.db"
```

---

## MONITORING & HEALTH

### Health Check Endpoints

```bash
# Quick check
curl http://localhost:8000/api/v1/health/
# Response: {"status": "healthy", ...}

# Deep health check
curl http://localhost:8000/api/v1/health/deep
# Response includes database, models, components

# System status with metrics
curl http://localhost:8000/api/v1/health/status
# Response: {"status": "healthy", "metrics": {"observations_stored": 45000, ...}}
```

### Logs

**Dashboard:**
```bash
tail -f ~/.streamlit/logs/
```

**Backend API:**
```bash
journalctl -u trackx-api -f  # Systemd
docker logs trackx-backend -f  # Docker
```

### Metrics to Monitor

- **Observation ingestion rate:** queries/sec into observations.db
- **Trajectory latency:** time to reconstruct routes (target: <2s)
- **Dashboard load time:** target: <3s
- **API response time:** target: <500ms
- **Database size:** SQLite file size (GBs)
- **Alert generation latency:** <1s

---

## SCALING

### Single-Machine Scaling

1. **Add indexes** (already done in Phase 1)
   - `idx_plate_text`, `idx_camera_id`, `idx_timestamp` 
   - Trajectory queries: 780s → <2s

2. **Enable caching** (already done in Phase 1)
   - Streamlit: @st.cache_data(ttl=300)
   - Redis (optional): for distributed caching

3. **Incremental trajectory updates** (Phase 3)
   - Don't rebuild all trajectories; only update affected ones
   - Expected: 1M observations in <100ms

### Multi-Machine Scaling

1. **Observations database:** Migrate from SQLite to PostgreSQL + PostGIS
   - Alembic already supports this
   - Set `DATABASE_URL` in .env

2. **Caching layer:** Deploy Redis
   - Distributed cache for analytics, trajectories
   - Reduces database load 10x

3. **API replicas:** Run multiple FastAPI instances behind load balancer
   - All instances read from same observations.db (PostgreSQL)
   - Stateless API layer

4. **Streaming ingest:** Add Kafka/Redis Stream for live observation ingestion
   - Current: synchronous writes to SQLite
   - Future: async writes → persistence layer

---

## TROUBLESHOOTING

### Dashboard Won't Start
```
Error: ModuleNotFoundError: No module named 'recognition'
```
**Fix:** Ensure you're running from project root, not dashboard/:
```bash
cd /path/to/TrackX
streamlit run dashboard/dashboard.py  # Correct
```

### API Returns 404
```
GET /api/v1/trajectory/search → 404
```
**Fix:** Check if FastAPI is running:
```bash
ps aux | grep uvicorn
curl http://localhost:8000/docs  # Should show swagger UI
```

### Trajectory Search Timeout
```
Trajectory search taking >10s
```
**Fix:** Verify database indexes:
```bash
sqlite3 observations.db
sqlite> PRAGMA index_list(observations);
```
Re-create if missing:
```bash
python -c "from database.observation_store import ObservationStore; ObservationStore()._ensure_indexes()"
```

### High Memory Usage
```
Dashboard process using 2GB+ RAM
```
**Fix:** Reduce cache TTL or limit observations loaded:
```python
# dashboard/dashboard.py
@st.cache_data(ttl=60)  # Reduce from 300s
def load_observations_cached():
    store = ObservationStore()
    obs = store.recent_observations(limit=50000)  # Cap at 50k
    store.close()
    return obs
```

---

## SECURITY

### Production Checklist

- [ ] Change `SECRET_KEY` in .env (use `openssl rand -hex 32`)
- [ ] Set `DEBUG=False`
- [ ] Use HTTPS (nginx reverse proxy with SSL cert)
- [ ] Enable CORS only for trusted origins
- [ ] Rotate database backups weekly
- [ ] Enable PostgreSQL authentication (if not SQLite)
- [ ] Run API behind firewall (not publicly exposed)
- [ ] Use environment-specific .env files (never commit secrets)

### API Security

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Whitelist
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization"],
)
```

---

## PERFORMANCE TUNING

### Database Optimization

```sql
-- Analyze query performance
EXPLAIN QUERY PLAN SELECT * FROM observations WHERE plate_text = 'TN10AB1234';

-- Vacuum database (cleanup)
VACUUM;

-- Check index usage
PRAGMA index_info(idx_plate_text);
```

### API Optimization

```python
# Use async handlers
@app.get("/api/v1/trajectory/search")
async def search_trajectory(plate_text: str):
    # Async database queries
    obs = await db.query(Observation).filter(...)
    trajectories = await build_trajectories_async(obs)
    return trajectories
```

---

## ROLLBACK PROCEDURE

If a deployment fails:

```bash
# Restore database from backup
sqlite3 observations.db-backup ".restore observations.db"

# Rollback API version
docker image ls | grep trackx
docker-compose down
git checkout previous-working-commit
docker-compose up -d

# Verify health
curl http://localhost:8000/api/v1/health/deep
```

---

## SUPPORT & MONITORING

### Regular Maintenance

- **Weekly:** Check database size, prune old observations if needed
- **Monthly:** Review performance metrics, update ML models if available
- **Quarterly:** Full backup, security audit, dependency updates

### Logs & Alerts

Set up alerting for:
- Health endpoint returns `status != healthy`
- API response time > 1000ms (median)
- Observation ingestion rate drops below 10/min
- Database size exceeds 90% capacity

---

## NEXT STEPS (FUTURE WORK)

1. **Multi-city deployment:** Migrate to PostgreSQL, deploy multiple regional instances
2. **Real-time streaming:** Kafka-based observation ingestion
3. **ML pipeline updates:** Retrain vehicle/plate detectors on production data
4. **Distributed trajectory reconstruction:** Horizontal scaling with Spark
5. **Web-based admin UI:** Replace CLI admin commands with dashboard UI

