# ✅ PRODUCTION DEPLOYMENT CHECKLIST — SIH-26127 TrackX

**Created:** September 6, 2026  
**Status:** READY TO DEPLOY  
**Target:** Production Environment  

Use this checklist to ensure smooth deployment.

---

## PRE-DEPLOYMENT (Do Before Deploy)

### Code & Tests
- [ ] Pull latest code from main branch
- [ ] Run all tests: `pytest tests/ -q` (expect 204 passing)
- [ ] Check for merge conflicts: `git status`
- [ ] Review recent commits: `git log --oneline -10`
- [ ] Verify no uncommitted changes: `git diff --stat`

### Environment Preparation
- [ ] Verify Docker installed: `docker --version` (need 20.10+)
- [ ] Verify Docker Compose: `docker-compose --version` (need 2.0+)
- [ ] Check disk space: Need 50GB+ free
- [ ] Check memory: Need 8GB+ RAM available
- [ ] Check network: Internet connectivity for image pulls

### Configuration
- [ ] Create production `.env` from `.env.example`
- [ ] Set `SECRET_KEY` (use: `python -c "import secrets; print(secrets.token_urlsafe(64))"`)
- [ ] Set `DB_PASSWORD` (use: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- [ ] Set `FIRST_SUPERUSER_PASSWORD` (strong, 16+ chars)
- [ ] Set `BACKEND_CORS_ORIGINS` to production domain(s)
- [ ] Verify `.env` not committed: `git check-ignore backend/.env`

### Security Review
- [ ] Verify DEBUG=False in production config
- [ ] Verify rate limiting enabled (default: 100 req/min)
- [ ] Verify CORS origins not overly permissive
- [ ] Verify no secrets in logs
- [ ] Verify no hardcoded credentials in code

### Documentation Review
- [ ] Read PRODUCTION_DEPLOYMENT.md
- [ ] Read E2E_VERIFICATION.md
- [ ] Review ARCHITECTURE_STRATEGY.md
- [ ] Have API.md open for reference

---

## DEPLOYMENT (Execute These Steps)

### Phase 1: Build
- [ ] Build Docker images: `docker-compose -f docker-compose.prod.yml build --no-cache`
- [ ] Verify build success (no errors)
- [ ] Verify image tags created: `docker images | grep trackx`

### Phase 2: Start Services
- [ ] Start all services: `docker-compose -f docker-compose.prod.yml up -d`
- [ ] Wait 30 seconds for services to stabilize
- [ ] Check all containers running: `docker-compose -f docker-compose.prod.yml ps`
- [ ] Expect status: "Up" for all services

### Phase 3: Database Setup
- [ ] Run migrations: `docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head`
- [ ] Verify no migration errors
- [ ] Check database connection: `docker-compose -f docker-compose.prod.yml exec postgres psql -U trackx -d trackx -c "SELECT version();"`

### Phase 4: Service Verification
- [ ] Verify PostgreSQL: `docker-compose -f docker-compose.prod.yml exec postgres pg_isready -U trackx`
- [ ] Verify Redis: `docker-compose -f docker-compose.prod.yml exec redis redis-cli ping` (expect PONG)
- [ ] Verify Backend: `curl http://localhost:8000/api/v1/health/` (expect {"status": "ok"})
- [ ] Verify Deep Health: `curl http://localhost:8000/api/v1/health/deep`

### Phase 5: Access Verification
- [ ] Check Dashboard: Open http://localhost:8501 in browser
- [ ] Check API Docs: Open http://localhost:8000/docs in browser
- [ ] Check Grafana: Open http://localhost:3000 (admin/admin)
- [ ] Check Prometheus: Open http://localhost:9090 in browser

---

## POST-DEPLOYMENT (After Services Running)

### Immediate Checks (First 5 Minutes)
- [ ] Check error logs: `docker-compose -f docker-compose.prod.yml logs backend | grep ERROR`
- [ ] Monitor CPU usage: `docker stats`
- [ ] Monitor memory: `docker stats`
- [ ] Verify no service restarts: `docker-compose -f docker-compose.prod.yml logs --tail=50`

### Health Monitoring (First Hour)
- [ ] Monitor logs continuously: `docker-compose -f docker-compose.prod.yml logs -f`
- [ ] Check database size: `docker-compose -f docker-compose.prod.yml exec postgres du -h /var/lib/postgresql/data`
- [ ] Check Redis memory: `docker-compose -f docker-compose.prod.yml exec redis redis-cli INFO memory`
- [ ] Verify Prometheus scraping metrics: `curl http://localhost:9090/api/v1/targets`

### Data Verification (First 24 Hours)
- [ ] Load sample data (if available)
- [ ] Verify observations created: `docker-compose -f docker-compose.prod.yml exec postgres psql -U trackx -d trackx -c "SELECT COUNT(*) FROM observations;"`
- [ ] Check OCR accuracy on real data
- [ ] Verify trajectory calculations
- [ ] Test alert generation

### Performance Baseline (First 24 Hours)
- [ ] Record API response times
- [ ] Record database query times
- [ ] Record CPU/memory usage patterns
- [ ] Document any anomalies

---

## MONITORING & MAINTENANCE

### Daily Tasks (After 24h Stability)
- [ ] Check error logs for patterns
- [ ] Verify backups completed
- [ ] Monitor disk usage growth
- [ ] Review OCR accuracy metrics
- [ ] Check system resource usage

### Weekly Tasks
- [ ] Review all logs for errors
- [ ] Check PostgreSQL maintenance: `ANALYZE`, `VACUUM`
- [ ] Review Grafana dashboards
- [ ] Test disaster recovery procedures
- [ ] Update documentation if needed

### Monthly Tasks
- [ ] Run `docker-compose pull` to check for updates
- [ ] Review security logs
- [ ] Analyze performance trends
- [ ] Plan capacity expansion if needed
- [ ] Rotate credentials if standard practice

---

## TROUBLESHOOTING DURING DEPLOYMENT

### Services Won't Start
```bash
# Check what's wrong
docker-compose -f docker-compose.prod.yml logs

# Common issues:
# 1. Port already in use (8000, 8501, 5432, 6379, 3000, 9090)
#    Solution: Kill existing process or change ports in .env
lsof -i :8000
kill -9 <PID>

# 2. Insufficient memory
#    Solution: Free up RAM or increase Docker memory limit

# 3. Corrupted Docker image
#    Solution: Clean and rebuild
docker-compose -f docker-compose.prod.yml down -v
docker-compose -f docker-compose.prod.yml build --no-cache
```

### Database Connection Failed
```bash
# Check PostgreSQL logs
docker-compose -f docker-compose.prod.yml logs postgres

# Verify credentials
cat backend/.env | grep POSTGRES

# Test connection manually
docker-compose -f docker-compose.prod.yml exec postgres psql -U trackx -d trackx -c "SELECT 1;"

# If still fails: restart PostgreSQL
docker-compose -f docker-compose.prod.yml restart postgres
sleep 10
docker-compose -f docker-compose.prod.yml restart backend
```

### Redis Connection Failed
```bash
# Check Redis logs
docker-compose -f docker-compose.prod.yml logs redis

# Test connection
docker-compose -f docker-compose.prod.yml exec redis redis-cli PING

# If failed: restart Redis
docker-compose -f docker-compose.prod.yml restart redis
```

### API Returns 500 Errors
```bash
# Check backend logs for stacktrace
docker-compose -f docker-compose.prod.yml logs -f backend

# Check if database is accessible
docker-compose -f docker-compose.prod.yml exec backend python -c "from app.core.database import SessionLocal; SessionLocal()"

# If database fails: check PostgreSQL
docker-compose -f docker-compose.prod.yml exec postgres pg_isready
```

### Dashboard Won't Load
```bash
# Check dashboard logs
docker-compose -f docker-compose.prod.yml logs -f dashboard

# Check backend API availability from dashboard container
docker-compose -f docker-compose.prod.yml exec dashboard curl http://backend:8000/api/v1/health/

# If fails: ensure backend is running and healthy
docker-compose -f docker-compose.prod.yml restart backend
sleep 30
docker-compose -f docker-compose.prod.yml restart dashboard
```

---

## ROLLBACK PROCEDURE

If deployment fails and you need to rollback:

```bash
# 1. Stop all services
docker-compose -f docker-compose.prod.yml down

# 2. Restore from backup (if applicable)
docker-compose -f docker-compose.prod.yml up -d postgres
sleep 10
docker-compose -f docker-compose.prod.yml exec postgres pg_restore \
    -U trackx -d trackx < /path/to/backup.sql.gz

# 3. Checkout previous code version
git checkout HEAD~1

# 4. Rebuild with previous version
docker-compose -f docker-compose.prod.yml build --no-cache

# 5. Restart services
docker-compose -f docker-compose.prod.yml up -d

# 6. Verify health
curl http://localhost:8000/api/v1/health/deep
```

---

## SUCCESS CRITERIA

Deployment is successful when ALL of these are true:

- [ ] All services running: `docker-compose -f docker-compose.prod.yml ps` shows all "Up"
- [ ] Health check passes: `curl http://localhost:8000/api/v1/health/deep` returns status "healthy"
- [ ] Dashboard accessible: http://localhost:8501 loads without errors
- [ ] API docs accessible: http://localhost:8000/docs loads properly
- [ ] Database accessible: Can query PostgreSQL
- [ ] Redis accessible: `redis-cli ping` returns PONG
- [ ] No error logs: `docker logs | grep ERROR` returns nothing
- [ ] No service restarts: Services have been "Up" for >5 minutes without restart

---

## PRODUCTION HANDOFF

Once deployment is complete and stable (24 hours):

- [ ] Document any configuration changes made
- [ ] Update runbook with production details
- [ ] Train operations team on deployment/monitoring
- [ ] Set up alerting and on-call rotation
- [ ] Document escalation procedures
- [ ] Create backup schedule
- [ ] Schedule regular maintenance windows
- [ ] Review and update disaster recovery plan

---

## DEPLOYMENT LOG TEMPLATE

```
DEPLOYMENT DATE: ________________
DEPLOYED BY: ____________________
ENVIRONMENT: Production / Staging / Development

PRE-DEPLOYMENT CHECKS:
- Tests passing: ____________ (expect 204/204)
- Disk space: ____________ (need 50GB+)
- Memory available: ____________ (need 8GB+)
- Docker version: ____________ (need 20.10+)

DEPLOYMENT STEPS:
- Build time: ____________
- Start time: ____________
- Migration time: ____________
- Verification time: ____________
- Total time: ____________

SERVICES RUNNING:
- PostgreSQL: ✓/✗ ____________________
- Redis: ✓/✗ ____________________
- Backend: ✓/✗ ____________________
- Dashboard: ✓/✗ ____________________
- Prometheus: ✓/✗ ____________________
- Grafana: ✓/✗ ____________________

HEALTH CHECK RESULTS:
- API health: ✓/✗ ____________________
- Database connection: ✓/✗ ____________________
- Redis connection: ✓/✗ ____________________
- Dashboard load: ✓/✗ ____________________

ISSUES ENCOUNTERED:
____________________
____________________

RESOLUTION:
____________________
____________________

APPROVED FOR PRODUCTION: Yes / No

Signed: ____________________ Date: ________
```

---

## CONTACT & SUPPORT

- **On-Call:** [Contact info]
- **Slack Channel:** #trackx-ops
- **Documentation:** See PRODUCTION_DEPLOYMENT.md
- **Runbook:** See ARCHITECTURE_STRATEGY.md
- **Emergency Contacts:** [List]

---

## FINAL STATUS

**✅ DEPLOYMENT CHECKLIST COMPLETE**

This checklist is your guarantee that:
1. All pre-deployment checks passed
2. Services deployed correctly
3. Health verification successful
4. System ready for production use

**Sign-off:** ________________ Date: ________

