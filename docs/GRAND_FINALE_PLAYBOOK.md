# TrackX — Grand Finale Playbook (SIH26127, BEL)

> For Team NexussAI (ID 178670) · Sri Krishna College of Engineering and Technology.
> Goal: win the SIH 2026 grand finale for problem statement **SIH26127** (Bharat Electronics Limited).

---

## 1. The problem statement, in one paragraph

BEL wants a **centralized AI software platform** that processes multi-camera CCTV/ANPR feeds city-wide to do three things:
1. **High-accuracy ANPR/OCR** (>90% exact-match, robust to lighting, weather, angles, blur, dirty/damaged plates).
2. **Single-plate trajectory tracking** — reconstruct a vehicle's full journey (timestamps, direction, route) on a GIS map across geographically distributed cameras.
3. **Macro traffic flow & movement analytics** — density, origin–destination, congestion bottlenecks, real-time heatmaps.

Plus an **alert system** for blacklisted vehicles and suspicious route anomalies, in real time. Enterprise-grade, scalable, software only (no new hardware).

## 2. PS → TrackX requirement map (know this cold)

| PS requirement | TrackX implementation | Honest status |
|---|---|---|
| High-precision OCR module (>90%) | PaddleOCR + 3-stage temporal fusion + adaptive preprocessing + D↔O fix + crop-pad fix + watermark filter | **~43% exact-match measured** (below target). Frame honestly. |
| Trajectory reconstruction engine (query-based, GIS, timestamps, camera locations) | `intelligence/trajectory.py` + `intelligence/fusion.py` (4-signal) on Coimbatore road graph | ✅ Real |
| City traffic analytics dashboard (heatmaps, avg speed, route densities, trends) | React + FastAPI + Folium/Leaflet, `analytics/analytics.py` | ✅ Real |
| Alert system (blacklist + route anomalies, real time) | `intelligence/alerts.py`, `route_anomaly_store`, persisted alerts, RBAC | ✅ Real |
| Scalable, enterprise-grade | FastAPI + Postgres/SQLite + Redis (claimed) + RBAC + audit log | ⚠️ Single worker, SQLite in dev; horizontal scale is a roadmap item |
| Real-time multi-camera processing | RTSPS live-stream WebSocket + Camera Media batch path | ✅ Real (no auto-reconnect) |

## 3. The 5 judge questions you WILL be asked (prepare answers)

### Q1. "Your OCR is supposed to be >90%. What's your real number?"
**Answer:** "We measured it honestly. On 35 hand-graded real plate crops from our own pipeline, exact-match is ~43%, character accuracy higher. We did not inflate this. We documented four root causes — truncated crops (fixed by loosening the plate-crop margin), D↔O confusion (fixed in our confusable-pair table), one hard plate/font case, and a rare cross-track contamination bug — and shipped fixes for two of them. The path to >90% is retraining on ANPR-resolution Indian plates plus per-vehicle multi-frame voting, which needs a labeled dataset and GPU time we're scoping as the next step. We chose to report the real number and the real root causes rather than a suspiciously perfect one, because for a defense-linked evaluator like BEL, trust in the measurement matters more than the headline."

### Q2. "Do you actually have a multi-camera network? Or is it simulated?"
**Answer:** "CAM_01 is a real physical RTSPS camera on our campus network. CAM_02–07 are processed from real footage (one real traffic photo + generated clips) through the exact same inference path — YOLO, plate detector, PaddleOCR, ByteTrack — so the pipeline is real; only the camera topology is a simulated 7-camera deployment we constructed to demonstrate cross-camera fusion. We're honest about that distinction, and our `data_source` tagging (`REAL_INFERENCE` vs `DEMO_SYNTHETIC`) makes it visible in the UI."

### Q3. "How is this different from the other 466 teams who submitted the same PS?"
**Answer:** (lead with depth, not baseline)
1. Three-stage OCR temporal fusion (most teams take a single highest-confidence read).
2. ANDed 3-tier plate-state confidence that withholds low-confidence reads instead of asserting them.
3. 4-signal weighted identity fusion (plate + appearance + time + space) with impossible-speed rejection — not plate-text-only matching.
4. Real road-graph travel-time plausibility, not straight-line haversine.
5. Honest real/demo data discipline with UI badges — rare in hackathon prototypes.
6. Working auth, RBAC, audit logging, rate limiting.

### Q4. "What about privacy, retention, and misuse of city-wide tracking?"
**Answer:** "We've scoped this as a productionization item, not hidden it. Our roadmap includes: role-based access control (operator/supervisor/auditor — who can blacklist, resolve alerts, export), a stated data-retention policy (raw footage N days, plate observations M days), and an access/audit trail for every query on a vehicle's trajectory. For the prototype, RBAC and audit logging already exist; the retention policy is a one-page document we can finalize with BEL's policy team. We treat city-wide vehicle tracking as a surveillance capability that needs accountability, not just accuracy."

### Q5. "Does it scale to 50+ cameras across a city?"
**Answer:** "Today: single SQLite file, single detection worker, one job at a time — honest. Our productionization roadmap: Postgres/PostGIS (already in the schema), a job queue for concurrent camera processing, horizontal worker scaling, ONVIF-style camera onboarding (today cameras are a hardcoded dict), and encrypted secrets at rest (today the RTSP password is in `.env`). We present these as known next steps, not hidden gaps — we'd rather name the gap than pretend it doesn't exist."

### Q6 (BEL-specific). "How does this fit with our existing command-and-control systems?"
**Answer:** "All observations, trajectories, alerts and analytics are exposed via a documented REST API (`/api/v1/*`) with OpenAPI docs at `/docs`. Alerts and observations are exportable via API to an existing VMS/C2 system — we'd align the schema with whatever BEL's command center expects (we can adapt field names/formats in a day)."

### Q7. "Why a dedicated engine vs. SIH26124 (same org, ANPR portion)?"
**Answer:** "SIH26124 covers the ANPR + tracking slice. SIH26127 is the city-wide engine: it adds macro traffic flow analytics, OD patterns, congestion heatmaps, route-anomaly detection, and the alert system on top of the same ANPR base. Our platform is built so the ANPR module is swappable, but the differentiator is the spatial-temporal fusion + traffic intelligence layer, which is what a city actually needs for command-center decisions."

## 4. 36-hour grand finale build plan (hour by hour)

**Before you travel (prep, no code):**
- [ ] Lock the demo dataset: 2 real multi-camera videos (even 2 cameras) + the existing 7-camera simulated set.
- [ ] Pre-train any OCR/model improvements on a GPU; bring weights on a USB drive (Render free tier won't have them).
- [ ] Print the 6-page PPT (judges sometimes want paper). Have the demo video (YouTube link) cached offline.
- [ ] Each member owns one module: ML (detection/OCR), backend (FastAPI/DB), frontend (React/maps), intelligence (fusion/trajectory), demo (script + data), pitch (PPT + Q&A).

**Hour 0–2 (setup):** clone repo, `pip install -r requirements.txt` + backend, `npm install`, verify app boots on the nodal-center laptop. Run `python -m unittest discover` — must be green.

**Hour 2–8 (core demo path):** ingest 2 real videos through `run_video_to_db`, build trajectories, generate GIS map, verify Vehicles/Trajectory/Alerts pages show real data. Fix any environment issue immediately — don't defer.

**Hour 8–16 (polish + honesty):** wire `route_hypothesis.py` into one GET endpoint (so it's a live feature, not an ambiguous one). Add the privacy/retention note. Ensure no synthetic data leaks into "real" views.

**Hour 16–24 (OCR + robustness):** apply crop-pad + watermark filter (already in code). Run the OCR audit harness on the demo videos; refresh the accuracy number if it improved.

**Hour 24–30 (demo rehearsal):** run the full demo 3× end-to-end with a timer. Each member rehearses their 2-minute module explanation. Prepare fallback (offline video) if live inference is slow.

**Hour 30–36 (final):** freeze code. Only documentation/PPT edits. Sleep.

## 5. Demo script (90 seconds, what judges see)

1. **0–15s** — Dashboard: "7 cameras, X real observations, Y verified plates." Show Active Cameras, KPIs.
2. **15–35s** — Vehicles page: search a plate, show VERIFIED green badge, 93.7%-style confidence, reading count, evidence (crop).
3. **35–55s** — Trajectory page: same plate plotted across 3 cameras on the map with timestamps.
4. **55–70s** — Alerts page: blacklist hit + route anomaly, with the DEMO/OPERATIONAL badge.
5. **70–85s** — Analytics/Congestion: heatmap, OD patterns, bottleneck.
6. **85–90s** — "Everything you saw is real inference on real footage; synthetic data is tagged and never shown as real."

## 6. Pre-flight checklist (run before every demo)

- [ ] `python -m unittest discover -s tests -p "test_*.py"` → 155 passed, 0 failed.
- [ ] `cd backend && python -m pytest tests/ -q` → only environment-related skips (torchvision) on local; CI green.
- [ ] `uvicorn app.main:app` boots, `/docs` loads, `admin@trackx.com / admin123` logs in.
- [ ] `npm run dev` boots, all 11 pages render.
- [ ] At least one real video ingested; Vehicles/Trajectory/Alerts show non-empty real data.
- [ ] No `.env`, `.db`, `.pt` files in `git status` (all gitignored).
- [ ] README renders on GitHub; demo video + deployed app links work.

## 7. What NOT to do

- Don't claim >90% OCR. It's measured at ~43%. Say the real number + root causes.
- `route_hypothesis.py` is now wired to `GET /api/v1/trajectory/route-hypothesis?plate=...` (done).
- Don't claim `CAMERA_RELIABILITY` is learned — it's hand-tuned.
- Don't claim auto-reconnect exists — it doesn't.
- Don't claim Redis/Postgres are in use in dev — they're production targets.
- Don't recycle any prior project/hackathon submission (SIH hard rule).

## 8. Useful links

- SIH portal: https://www.sih.gov.in
- Problem statement SIH26127: https://www.sih.gov.in (search 26127)
- TrackX repo: https://github.com/abinivesh-m/TrackX
- Deployed app: https://trackx-scoj.onrender.com
- Demo video: https://youtu.be/nd0tCe5RH-8
- Drive (datasets/models): https://drive.google.com/drive/folders/1Z6f89znJKj9f1LXG2pi7tEtfIhIcJ57A

---

*Prepared for Team NexussAI. Update this doc as the grand finale approaches.*