# 🧪 LOCAL DEPLOYMENT TEST - Before Going Live

Test everything locally before deploying to Railway.

---

## STEP 1: Clean Docker Environment

```bash
# Stop all containers
docker-compose down -v

# Remove old images
docker rmi trackx-trackx trackx-trackx-frontend trackx-trackx-worker 2>/dev/null || true

# Verify clean
docker ps
```

---

## STEP 2: Start Production Services Locally

```bash
# Set environment
export DB_PASSWORD=testpass123
export SECRET_KEY=testsecret123456789

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Wait 30 seconds
sleep 30

# Check status
docker-compose -f docker-compose.prod.yml ps
```

**Expected output:**
```
NAME              STATUS           PORTS
trackx-postgres   Up (healthy)     5432
trackx-redis      Up (healthy)     6379
trackx-backend    Up (healthy)     8000
trackx-frontend   Up (starting)    3000
```

---

## STEP 3: Initialize Database

```bash
# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Verify
docker-compose -f docker-compose.prod.yml exec postgres psql -U trackx -d trackx -c "SELECT COUNT(*) FROM observations;"
```

---

## STEP 4: Test Backend API

```bash
# Health check
curl http://localhost:8000/api/v1/health/

# Expected: {"status": "ok"}

# Deep health check
curl http://localhost:8000/api/v1/health/deep

# Should show: database connected, redis connected
```

---

## STEP 5: Test Frontend

Open in browser:
```
http://localhost:3000
```

**Should see:**
- ✅ TrackX logo and navigation
- ✅ Dashboard with stats
- ✅ Vehicle tracking page
- ✅ Analytics page
- ✅ Alerts page

---

## STEP 6: Test API Endpoints

```bash
# Get all observations
curl http://localhost:8000/api/v1/observations/

# Get vehicles
curl http://localhost:8000/api/v1/vehicles/

# Get analytics
curl http://localhost:8000/api/v1/analytics/summary

# Get alerts
curl http://localhost:8000/api/v1/alerts/
```

---

## STEP 7: Check Logs

```bash
# Backend logs
docker logs trackx-backend

# Frontend logs
docker logs trackx-frontend

# Database logs
docker logs trackx-postgres

# Redis logs
docker logs trackx-redis
```

---

## STEP 8: Monitor Performance

```bash
# CPU and Memory
docker stats

# Check if anything is crashing
docker-compose -f docker-compose.prod.yml ps
```

---

## TROUBLESHOOTING

### Backend won't start
```bash
# Check logs
docker logs trackx-backend

# Restart
docker-compose -f docker-compose.prod.yml restart backend

# Wait 15 seconds and check again
```

### Frontend won't start
```bash
# Check logs
docker logs trackx-frontend

# Ensure Node modules built
docker-compose -f docker-compose.prod.yml exec frontend npm install

# Restart
docker-compose -f docker-compose.prod.yml restart frontend
```

### Database connection error
```bash
# Check PostgreSQL
docker exec trackx-postgres pg_isready -U trackx

# Check DATABASE_URL
docker-compose -f docker-compose.prod.yml exec backend env | grep DATABASE_URL
```

### Can't access frontend from browser
```bash
# Check container is running
docker ps | grep frontend

# Check port mapping
docker port trackx-frontend

# Try accessing
curl http://localhost:3000
```

---

## VERIFICATION CHECKLIST

- [ ] All containers running and healthy
- [ ] Database initialized
- [ ] Backend API responding
- [ ] Frontend loads in browser
- [ ] Navigation works
- [ ] Dashboard shows stats
- [ ] API endpoints return data
- [ ] No errors in logs
- [ ] Performance is good

---

## IF ALL TESTS PASS

You're ready to deploy to Railway! 🎉

Next: Follow RAILWAY_DEPLOYMENT.md

---

## CLEANUP (After Testing)

```bash
# Stop all services
docker-compose -f docker-compose.prod.yml down

# Remove volumes
docker-compose -f docker-compose.prod.yml down -v

# Verify
docker ps
```

