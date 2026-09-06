# TrackX User Guide

**Version:** 1.0.0  
**For:** End Users, Traffic Managers, System Administrators

---

## TABLE OF CONTENTS

1. [Getting Started](#getting-started)
2. [Dashboard Features](#dashboard-features)
3. [Vehicle Search](#vehicle-search)
4. [Traffic Analytics](#traffic-analytics)
5. [Alert Management](#alert-management)
6. [System Administration](#system-administration)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## GETTING STARTED

### First Login

1. Open TrackX Dashboard: `http://your-server:8501`
2. Wait for dashboard to load (~3 seconds)
3. Verify system status: Green = Ready, Red = Error

### Dashboard Tabs

| Tab | Purpose | Who Uses It |
|-----|---------|------------|
| **Search** | Find vehicles by plate | Traffic police, investigators |
| **City Intelligence** | View traffic patterns | Traffic managers, planners |
| **Alerts** | Manage security alerts | Security team |
| **Monitor** | Real-time vehicle detection | Operators |
| **System** | Check health and configuration | Admins |

---

## DASHBOARD FEATURES

### Search Tab
Find and track individual vehicles.

**To Search:**
1. Enter vehicle license plate (e.g., "TN10AB1234")
2. Click "Search"
3. View trajectory showing:
   - **Route:** Which cameras detected the vehicle
   - **Timeline:** When detected at each camera
   - **Map:** Geographic path on city map
   - **Confidence:** How certain the match is

**Trajectory Details:**
- **Plate Confidence:** OCR reading accuracy (0-100%)
- **Vehicle Match:** Vehicle appearance consistency across cameras
- **Temporal Score:** Travel time feasibility
- **Spatial Score:** Road network connection (0-100%)
- **Overall Match:** Combined confidence score

### City Intelligence Tab
Understand traffic patterns city-wide.

**Available Views:**
- **Heatmap:** Vehicle density by camera (darker = busier)
- **Top Routes:** Most frequently traveled vehicle paths
- **Busiest Camera:** Which camera sees most vehicles
- **Traffic Speed:** Average vehicle speed on roads
- **Congestion Level:** Real-time traffic congestion estimate

### Alerts Tab
Manage vehicle security alerts.

**Alert Types:**
1. **Blacklist Match** — Vehicle on watchlist detected
2. **Repeated Camera** — Vehicle loitering at same location
3. **Route Anomaly** — Impossible travel speed detected

**Managing Alerts:**
- Click alert to view details
- "Acknowledge" to mark as reviewed
- Add notes for investigations
- Export alerts for reports

### Monitor Tab
Real-time vehicle detection pipeline.

**Shows:**
- Live detection frames (if connected to camera feed)
- Vehicle confidence scores
- Plate detection and OCR output
- Detection FPS (frames per second)

### System Tab
System status and configuration.

**Check:**
- Database status (green = healthy)
- ML models availability (YOLO, OCR, etc.)
- Total observations stored
- System uptime
- Component health

---

## VEHICLE SEARCH

### Plate Format

**Supported Formats:**
- TN10AB1234 (Standard Indian format)
- TN10-AB-1234 (With dashes)
- tn10ab1234 (Lowercase auto-converted)

**What the System Does:**
1. Searches for exact matches first
2. Searches for fuzzy matches (minor OCR errors)
3. Returns best matches with confidence scores
4. Displays full trajectory if found

### Search Tips

- **Recent searches load faster** — Database caches common queries
- **Use exact plate when possible** — More accurate results
- **If no results:** Vehicle may not have passed any cameras yet
- **Confidence below 70%?** — Multiple vehicles similar appearance; verify manually

---

## TRAFFIC ANALYTICS

### Origin-Destination (OD) Matrix
Shows which routes are busiest.

**Usage:**
- Plan traffic management
- Identify congestion points
- Analyze rush hour patterns
- Forecast traffic problems

### Density Heatmap
Visual representation of traffic by camera location.

**Red zones:** High traffic, possible congestion
**Yellow zones:** Moderate traffic
**Green zones:** Light traffic

### Average Speed
Typical vehicle speed on each road segment.

**Formula:** Distance / Travel Time
**Used for:**
- Detect speeding violations
- Identify traffic problems (low speeds = congestion)
- Route planning

### Congestion Calculation
Multi-factor model considering:
- Vehicle density at camera
- Travel speed on routes
- Time of day patterns
- Recent traffic trends

---

## ALERT MANAGEMENT

### Creating Alerts

**Blacklist Alerts:**
1. Go to **Alerts** tab → **Manage Blacklist**
2. Enter vehicle plate
3. Add reason (stolen, wanted, etc.)
4. System notifies immediately if vehicle detected

**Repeated Camera Alerts:**
- Automatic if vehicle seen 3+ times at same camera in 5 minutes
- Indicates possible loitering/suspicious activity

**Route Anomaly Alerts:**
- Automatic if vehicle travels at impossible speed
- Indicates detection error or system glitch

### Responding to Alerts

1. **Click** alert in list
2. **Review** details (plate, location, confidence)
3. **Investigate** using search to view full trajectory
4. **Acknowledge** when resolved
5. **Add notes** for audit trail

### Exporting Alerts

```
Click "Export" → Select date range → Choose format (CSV/PDF)
```

Used for reports, investigations, audits.

---

## SYSTEM ADMINISTRATION

### User Roles

| Role | Permissions |
|------|-------------|
| **Viewer** | Search, view analytics (read-only) |
| **Operator** | Viewer + manage alerts |
| **Admin** | Full access + configuration |

### Configuration

**Available Settings:**
- Alert thresholds (plate confidence, speed limits)
- Blacklist policies (automatic expiry, etc.)
- Map settings (zoom, markers, heatmap)
- Data retention (delete observations older than X days)

**To Change Settings:**
1. Go to **System** tab → **Configuration**
2. Update values
3. Click "Save"
4. Changes apply immediately

### Backup & Restore

**Backup:**
```bash
# Automatic daily backups to: /backups/trackx_YYYY-MM-DD.db
# Manual backup:
curl -X POST http://localhost:8000/api/v1/admin/backup
```

**Restore:**
```bash
# Contact admin to restore from backup
```

### Database Maintenance

**Auto-cleanup (daily):**
- Delete observations older than 90 days
- Consolidate database (VACUUM)
- Recreate indexes if needed

**Manual cleanup:**
```bash
# Clear observations for specific camera (before reset)
curl -X POST http://localhost:8000/api/v1/admin/clear-camera?camera_id=CAM_01
```

---

## TROUBLESHOOTING

### Dashboard Won't Load

**Problem:** "Connection refused" or blank page
**Solution:**
1. Check system status: Is backend running?
2. Verify internet connection
3. Clear browser cache (Ctrl+Shift+Del)
4. Wait 10 seconds and refresh

### Search Returns No Results

**Problem:** "No trajectories found"
**Possible Causes:**
1. Plate not in database (vehicle hasn't passed any cameras)
2. Plate format wrong (check format above)
3. OCR was uncertain (confidence <70%, not stored)

**Solution:**
1. Check spelling carefully
2. Try fuzzy search (system tries automatically)
3. View recent observations in **City Intelligence** tab
4. If still not found, vehicle likely hasn't been detected yet

### Slow Search Response

**Problem:** Searches taking >5 seconds
**Causes:** Large database, high system load

**Solution:**
1. System caches frequent searches (15s after search)
2. Avoid searching during peak hours
3. If persistent, contact admin to optimize database

### Alerts Not Generating

**Problem:** Should get alert but didn't
**Possible Causes:**
1. Confidence too low (threshold set >75%)
2. Alert type disabled in settings
3. Vehicle not actually detected

**Solution:**
1. Verify blacklist entry exists (**Alerts** → **Manage Blacklist**)
2. Check alert settings (**System** → **Configuration**)
3. Manual search to verify vehicle was detected

### Accuracy Issues

**Problem:** Wrong vehicle detected as match
**Causes:**
- Similar plates in system
- Poor OCR confidence
- Vehicle appearance changed (lighting, dirt, etc.)

**Solution:**
1. Always verify before acting on alert
2. Use full trajectory context (multiple cameras confirm identity)
3. Check confidence scores (>85% = high confidence)

---

## FAQ

### Q: How accurate is plate recognition?
**A:** 85-95% on clear plates, 60-75% in poor conditions (rain, glare, etc.). Always verify with full trajectory context before acting.

### Q: Can I search for vehicles by color/type?
**A:** Not in current version. Future update will add visual search.

### Q: How long are observations kept?
**A:** Default 90 days. Configurable by admin. Old data automatically deleted.

### Q: What if vehicle uses fake/covered plate?
**A:** System won't detect it. Vehicle tracking requires visible, readable plates.

### Q: Can I share searches/trajectories?
**A:** Click "Export" to download trajectory as PDF or CSV.

### Q: What time zone is used?
**A:** UTC (GMT+0). System automatically converts to local time in settings.

### Q: Is my search history saved?
**A:** No. Each search is independent. No browsing history kept.

### Q: Can I delete an alert?
**A:** Yes, but it remains in history for audit. "Delete" removes from active alerts.

### Q: How do I report system errors?
**A:** Contact admin with:
- Error message (screenshot if possible)
- When it happened
- What you were doing
- System status (System tab)

### Q: What's the maximum search radius?
**A:** Entire city network. Searches across all connected cameras.

### Q: Can I set up automatic alerts?
**A:** Yes, via blacklist (added vehicles auto-trigger alerts). Threshold-based alerts coming in future version.

### Q: How is "impossible speed" detected?
**A:** If distance/time > road speed limit * safety margin (1.3x).
Example: 8.5km in 200s = 153 km/h on 50km/h road = anomaly

---

## SUPPORT & FEEDBACK

**Report Issues:**
- Email: support@trackx.local
- Chat: In-app support (bottom right)
- Documentation: See DEPLOYMENT.md, API.md

**Feature Requests:**
- Submit via in-app feedback form
- Vote on community board
- Enterprise customers get priority

**Training:**
- Video tutorials: https://docs.trackx.local/videos
- Webinars: Monthly training sessions (Zoom link in app)
- Documentation: Complete technical docs available

---

**Last Updated:** 2026-09-06  
**Version:** 1.0.0  
**Support Status:** Full support during business hours

