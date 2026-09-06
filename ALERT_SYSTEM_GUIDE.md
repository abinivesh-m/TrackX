# TrackX Alert System - Complete Guide

## Overview

The TrackX Alert System is a comprehensive real-time vehicle monitoring solution that detects and alerts on suspicious vehicle activities across a city-wide ANPR network. It implements the SIH PS 26127 requirements for blacklisted vehicle detection and route anomaly identification.

## Key Features

### 1. Blacklist Detection
- **Fuzzy Matching**: Uses similarity-based matching (85% threshold) to handle OCR variations
- **Multi-Severity Support**: HIGH, MEDIUM, LOW severity classification
- **Database Persistence**: All blacklist entries stored in SQLite database
- **Real-time Updates**: Immediate detection when blacklisted vehicles are observed

### 2. Route Anomaly Detection
- **Impossible Travel Detection**: Flags vehicles moving faster than physically possible
- **Suspicious Pattern Recognition**: Identifies unusual route behaviors
- **Confidence Scoring**: Each anomaly includes an anomaly score (0-100)
- **Detailed Reasoning**: Provides explanations for why a route is flagged

### 3. Repeated Camera Detection
- **Loitering Detection**: Identifies vehicles appearing multiple times at the same camera
- **Configurable Thresholds**: Adjustable sensitivity for repeated sightings
- **Time-based Analysis**: Considers temporal patterns in repeated appearances

### 4. Alert Management
- **Dashboard Integration**: Full UI for managing alerts and blacklist
- **Status Tracking**: OPEN/RESOLVED status for each alert
- **Historical Records**: Complete alert history with filtering capabilities
- **Real-time Generation**: On-demand alert generation from trajectory data

## Quick Start

### 1. Run the Complete Alert Demo

The fastest way to see the alert system in action:

```bash
python demo/run_alert_demo.py --clean
```

This will:
- Seed 5 blacklisted vehicles with different scenarios
- Create 18 realistic observations across 5 cameras
- Build 11 vehicle trajectories
- Generate 4 alerts (3 blacklist matches, 1 repeated camera)
- Persist all data to the database
- Display comprehensive alert summary

### 2. Launch the Dashboard

```bash
streamlit run dashboard/dashboard.py
```

Navigate to the **Alerts** tab to:
- View real-time generated alerts
- Manage the blacklist (add/remove vehicles)
- View and resolve historical alerts
- Filter alerts by status and type

## Alert Types

### BLACKLISTED_VEHICLE (HIGH Severity)
Triggered when a vehicle's license plate matches an entry in the blacklist database.

**Example:**
```
[ALERT] BLACKLIST MATCH — TN10AB1234 
(matched TN10AB1234, similarity 1.00) 
— seen at ['CAM_01', 'CAM_02', 'CAM_03'] 
— Severity: HIGH
```

**Use Case:** Immediate notification of stolen vehicles, wanted suspects, or vehicles of interest.

### SUSPICIOUS_ROUTE (HIGH/MEDIUM Severity)
Triggered when a vehicle's movement pattern indicates suspicious behavior.

**Example:**
```
[ALERT] ROUTE ANOMALY — IMPOSSIBLE_TRAVEL (Score: 85.0) 
— Global Vehicle #7
Reason: Vehicle traveled 5.2 km in 2 minutes (156 km/h - impossible)
```

**Use Case:** Detecting vehicles that could not have traveled between cameras in the observed time.

### REPEATED_CAMERA (MEDIUM Severity)
Triggered when a vehicle is detected multiple times at the same camera location.

**Example:**
```
[WARNING] Repeated sighting at CAM_03 (3 times) 
— Global Vehicle #9 
— Severity: MEDIUM
```

**Use Case:** Identifying potential loitering, surveillance, or suspicious stationary behavior.

## Database Schema

### Blacklist Table
```sql
CREATE TABLE blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate TEXT NOT NULL,
    normalized_plate TEXT NOT NULL,
    description TEXT,
    severity TEXT NOT NULL DEFAULT 'MEDIUM',
    created_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
)
```

### Alerts Table
```sql
CREATE TABLE alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MEDIUM',
    camera_id TEXT,
    timestamp TEXT NOT NULL,
    description TEXT,
    confidence REAL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL
)
```

## API Usage

### Adding a Vehicle to Blacklist

```python
from database.blacklist_store import BlacklistStore

store = BlacklistStore()
plate_id = store.add_plate(
    plate="TN10AB1234",
    description="Reported stolen vehicle",
    severity="HIGH"
)
store.close()
```

### Generating Alerts from Trajectories

```python
from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories
from intelligence.alerts import scan_trajectories_for_alerts

# Get observations and build trajectories
store = ObservationStore()
observations = store.all_observations()
trajectories = build_trajectories(observations)
store.close()

# Generate alerts (automatically persisted to database)
alerts = scan_trajectories_for_alerts(trajectories, persist_to_db=True)

print(f"Generated {len(alerts)} alerts")
for alert in alerts:
    print(f"{alert['type']}: {alert.get('plate', 'N/A')}")
```

### Querying Alert History

```python
from database.alert_store import AlertStore

store = AlertStore()

# Get all alerts
all_alerts = store.list_alerts()

# Get only open alerts
open_alerts = store.list_alerts(status="OPEN")

# Resolve an alert
store.resolve_alert(alert_id=123)

store.close()
```

## Demo Scenarios

The demo data includes these realistic scenarios:

### Scenario 1: Stolen Vehicle Movement
- **Plate**: TN10AB1234 (HIGH severity blacklist)
- **Behavior**: Vehicle moves across 3 cameras (CAM_01 → CAM_02 → CAM_03)
- **Alert**: BLACKLIST_MATCH with full camera hit list

### Scenario 2: Hit-and-Run Suspect
- **Plate**: KA05CD5678 (HIGH severity blacklist)
- **Behavior**: Detected at 2 different camera locations
- **Alert**: BLACKLIST_MATCH with camera locations

### Scenario 3: Loitering Vehicle
- **Plate**: TN44AA1111 (not blacklisted)
- **Behavior**: Detected 3 times at the same camera (CAM_03)
- **Alert**: REPEATED_CAMERA_SIGHTING indicating possible loitering

### Scenario 4: Impossible Travel
- **Plate**: TN33ZZ9999 (not blacklisted)
- **Behavior**: Travels between distant cameras in impossibly short time
- **Alert**: ROUTE_ANOMALY with impossible travel detection

## Dashboard Features

### Active Alerts Tab
- Real-time alert display with severity indicators
- Alert type categorization and counts
- Detailed alert information with camera hits
- One-click alert resolution

### Blacklist Management Tab
- Add new vehicles to blacklist
- View current blacklist with descriptions
- Remove vehicles from blacklist
- Severity classification (HIGH/MEDIUM/LOW)

### Alert History Tab
- View all historical alerts
- Filter by status (OPEN/RESOLVED)
- Resolve alerts with one click
- Detailed alert information with timestamps

## Configuration

### Blacklist Match Threshold
```python
# In intelligence/alerts.py
BLACKLIST_MATCH_THRESHOLD = 0.85  # 85% similarity required
```

### Anomaly Detection Thresholds
```python
# In intelligence/anomaly_scoring.py
# Configured for impossible travel detection
# based on distance/time calculations
```

### Repeated Camera Threshold
```python
# In intelligence/alerts.py
# Requires 3+ sightings at same camera
if len(cams) >= 3 and len(set(cams)) == 1:
    # Trigger repeated camera alert
```

## Integration with Pipeline

The alert system integrates seamlessly with the main TrackX pipeline:

1. **Visual Pipeline** (`demo/visual_pipeline.py`): Processes camera feeds and generates observations
2. **Observation Store** (`database/observation_store.py`): Persists observations to database
3. **Trajectory Building** (`intelligence/trajectory.py`): Constructs vehicle trajectories
4. **Alert Generation** (`intelligence/alerts.py`): Detects and generates alerts
5. **Alert Persistence** (`database/alert_store.py`): Stores alerts in database
6. **Dashboard Display** (`dashboard/dashboard.py`): Visualizes alerts and management

## Performance Considerations

### Database Optimization
- SQLite database for efficient storage and querying
- Indexed fields for fast lookups (plate, camera_id, timestamp)
- Batch operations for bulk data processing

### Real-time Processing
- On-demand alert generation (no continuous background processing)
- Efficient trajectory building with caching
- Optimized fuzzy matching algorithms

### Scalability
- Modular architecture supports adding new alert types
- Database schema designed for easy migration
- Configurable thresholds for different deployment scenarios

## Troubleshooting

### No Alerts Generated
- Ensure observations exist in the database
- Check that trajectories are being built correctly
- Verify blacklist has active entries
- Check alert generation logs for errors

### Database Connection Issues
- Verify database path in `config.py`
- Check file permissions on database directory
- Ensure SQLite is properly installed

### Dashboard Not Showing Alerts
- Refresh the dashboard after running the demo
- Check that alerts are persisted to database
- Verify alert store is working correctly
- Check browser console for JavaScript errors

## SIH Requirement Compliance

The alert system fully implements the SIH PS 26127 requirement:

> "The platform must incorporate an Alert System capable of flagging blacklisted vehicles and suspicious route anomalies in real time."

**Implementation:**
- ✅ Blacklisted vehicle detection with fuzzy matching
- ✅ Suspicious route anomaly detection
- ✅ Real-time alert generation
- ✅ Database persistence for alert history
- ✅ Dashboard integration for alert management
- ✅ Multi-severity classification system
- ✅ Comprehensive alert types (blacklist, route anomalies, repeated cameras)

## Future Enhancements

Potential improvements for production deployment:

1. **Email/SMS Notifications**: Real-time alert notifications to authorities
2. **Machine Learning**: Advanced pattern recognition for anomaly detection
3. **Geofencing**: Alert on vehicles entering/exiting specific zones
4. **Historical Analysis**: Trend analysis of alert patterns over time
5. **Multi- Agency Support**: Role-based access for different agencies
6. **API Endpoints**: REST API for integration with other systems
7. **Real-time Streaming**: WebSocket support for live alert updates

## Support

For issues or questions:
1. Check the main project README.md
2. Review SIH_REQUIREMENT_ALIGNMENT.md for requirement mapping
3. Run the demo script to verify installation
4. Check dashboard system health page

## License

This is part of the TrackX SIH PS 26127 project for Bharat Electronics Limited.
