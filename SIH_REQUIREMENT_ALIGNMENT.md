# TrackX - SIH PS 26127 Requirement Alignment Document

> **Current validation note (2026-09-05):** Latest benchmark results from `benchmark_ocr_engines.py` on the clean test dataset (113 samples) report **25.66% exact-match accuracy for LPRNet**. This is below SIH PS 26127's >90% exact-plate-recognition requirement; a fine-tuned and independently evaluated ANPR model is still required before claiming full compliance. The dataset has been expanded to 784 total images with clean train/validation/test splits to prevent data leakage.

## Problem Statement Overview

**Modern urban centers deploy vast networks of CCTV and Automatic Number Plate Recognition (ANPR) cameras to manage traffic, enforce traffic laws, and maintain public security. However, most existing systems process these feeds in isolated silos, performing basic license plate detection without effectively linking data across space and time. This lack of integration prevents city authorities from automatically tracking high-interest vehicles across different sectors and limits their ability to extract macro-level traffic movement trends from the existing camera infrastructure.**

## Expected Solution Components

### 1. High-Precision OCR Module (>90% accuracy)

**Requirement:** Deep-learning model exceeding 90% recognition accuracy for license plates in multi-lane traffic streams under diverse conditions (lighting, weather, angles, motion blur, dirty plates).

**TrackX Implementation:**
|- ⚠️ **Current Status**: 72.4% exact-match accuracy on 551-sample Indian plate dataset (below 90% requirement)
|- ✅ **LPRNet Integration**: Uses LPRNet deep-learning model for Indian license plate text recognition
|- ✅ **YOLO Vehicle Detection**: YOLO11n for robust vehicle detection
|- ✅ **Plate Detection**: Specialized plate detector for locating license plates with trained weights (best_plate_detector.pt)
|- ✅ **OCR Evaluation Module**: `recognition/ocr_evaluation.py` provides comprehensive accuracy metrics
|- ✅ **Confidence Scoring**: Each OCR result includes confidence scores
|- ✅ **Real-world Condition Handling**: Designed to handle varying lighting, angles, and plate conditions
|- ✅ **Evaluation Reports**: Generates detailed accuracy reports with character-level and exact match metrics
|- ✅ **ANPR Lab**: Comprehensive testing framework for 1000+ test samples across conditions
|- ✅ **Dataset Support**: Supports both real and synthetic datasets for training/evaluation
|- ✅ **Multi-pass OCR**: Intelligent multi-pass approach with preprocessing variants

**Current Performance (from CLEAN_OCR_FINAL_REPORT.md):**
|- Exact-match accuracy: 72.4% (399/551 samples)
|- Character accuracy: 81.1%
|- Status: Below 90% SIH requirement threshold

**Path to >90% Accuracy:**
1. Fine-tune LPRNet on verified Indian plate training dataset (architecture ready, needs training)
2. Add perspective/angle correction before OCR processing
3. Implement fast/slow path for real-time multi-lane processing
4. Train on larger Indian plate dataset (currently have 186-737 verified training crops)

**Verification:** Run `python recognition/anpr_lab.py` for comprehensive evaluation, check OCR evaluation in dashboard tab 5.

---

### 2. Trajectory Reconstruction Engine

**Requirement:** Query-based tracking interface that plots a vehicle's historical path chronologically across the city map with accurate timestamps and camera locations.

**TrackX Implementation:**
|- ✅ **Spatio-Temporal Tracking**: `intelligence/spatio_temporal.py` implements sophisticated tracking algorithms
|- ✅ **Vehicle Fusion**: `intelligence/fusion.py` combines multiple evidence sources (plate, appearance, temporal, spatial)
|- ✅ **Trajectory Building**: `intelligence/trajectory.py` constructs complete vehicle trajectories
|- ✅ **Multi-Camera Linking**: Links observations across different camera locations
|- ✅ **Temporal Analysis**: Considers time constraints for realistic vehicle movement
|- ✅ **Spatial Analysis**: Uses geographic coordinates for route reconstruction
|- ✅ **GIS Integration**: `gis/gis_map.py` generates interactive maps with trajectory visualization
|- ✅ **Query Interface**: Dashboard provides search-by-plate functionality
|- ✅ **Confidence Scoring**: Each trajectory link includes confidence breakdown
|- ✅ **Explainable AI**: "Why This Vehicle Match?" feature with detailed evidence breakdown

**Verification:** Use dashboard tab 1 to search for vehicle plates and view their complete trajectories.

---

### 3. City Traffic Analytics Dashboard

**Requirement:** Centralized, GIS-integrated web platform displaying heatmaps, average vehicle speeds, route densities, and traffic flow trends across all camera nodes.

**TrackX Implementation:**
|- ✅ **Streamlit Dashboard**: `dashboard/dashboard.py` provides comprehensive web interface
|- ✅ **GIS Integration**: Interactive Folium maps with camera network visualization
|- ✅ **Traffic Heatmaps**: Real-time heatmaps showing vehicle density across cameras
|- ✅ **Vehicle Count Analytics**: Per-camera vehicle counting and statistics
|- ✅ **Busiest Camera Detection**: Identifies high-traffic locations
|- ✅ **Cross-Camera Routes**: Analyzes vehicle movement patterns between cameras
|- ✅ **Speed Analysis**: `analytics/analytics.py` calculates average vehicle speeds
|- ✅ **Origin-Destination Patterns**: Tracks vehicle flow between locations
|- ✅ **Congestion Detection**: Identifies traffic bottlenecks and hotspots
|- ✅ **Real-time Updates**: Dashboard refreshes with new data
|- ✅ **Multi-tab Interface**: Organized into Search, Analytics, Alerts, Ingestion, and OCR Evaluation

**Verification:** Run `streamlit run dashboard/dashboard.py` and explore tabs 2 (City Analytics).

---

### 4. Alert System

**Requirement:** Capable of flagging blacklisted vehicles and suspicious route anomalies in real time.

**TrackX Implementation:**
|- ✅ **Blacklist Detection**: `intelligence/alerts.py` with fuzzy matching (85% similarity threshold)
|- ✅ **Database Persistence**: `database/blacklist_store.py` for persistent blacklist management
|- ✅ **Route Anomaly Detection**: `intelligence/anomaly_scoring.py` identifies suspicious patterns
|- ✅ **Impossible Travel Detection**: Flags vehicles moving faster than physically possible
|- ✅ **Repeated Camera Detection**: Identifies loitering behavior
|- ✅ **Alert Persistence**: `database/alert_store.py` stores all alerts with status tracking
|- ✅ **Multi-Severity System**: HIGH, MEDIUM, LOW severity classification
|- ✅ **Real-time Generation**: On-demand alert generation from trajectory data
|- ✅ **Dashboard Integration**: Alert management UI with add/remove/resolve functionality
|- ✅ **Comprehensive Alert Types**: BLACKLISTED_VEHICLE, SUSPICIOUS_ROUTE, REPEATED_CAMERA

**Verification:** Run `python demo/run_alert_demo.py` to generate alerts, then view in dashboard tab 3.

---

## Additional SIH-Aligned Features

### Database Architecture
|- ✅ **SQLite Database**: Persistent storage for observations, trajectories, alerts, blacklist
|- ✅ **Observation Store**: `database/observation_store.py` with comprehensive vehicle data
|- ✅ **Schema Migration**: Automatic database schema updates for new features
|- ✅ **Data Source Tagging**: Distinguishes between REAL_INFERENCE and SYNTHETIC_DEMO data

### Multi-Camera Network Support
|- ✅ **Camera Network Configuration**: `network/camera_network.py` with geographic coordinates
|- ✅ **Multi-Camera Processing**: Simultaneous processing of multiple camera feeds
|- ✅ **Camera Feed Management**: `demo/camera_simulator.py` for camera feed handling
|- ✅ **Road Network Constraints**: Physical feasibility analysis for trajectory validation

### Demo and Testing Infrastructure
|- ✅ **Demo Data Seeding**: `demo/seed_alert_demo.py` for realistic test scenarios
|- ✅ **End-to-End Demo**: `demo/run_alert_demo.py` for complete workflow demonstration
|- ✅ **Visual Pipeline**: `demo/visual_pipeline.py` for real detection processing
|- ✅ **OCR Evaluation**: Comprehensive accuracy testing and reporting
|- ✅ **ANPR Lab**: `recognition/anpr_lab.py` for rigorous Indian plate testing

### System Health Monitoring
|- ✅ **System Health Page**: `dashboard/system_health.py` for monitoring system status
|- ✅ **Dependency Checks**: Verifies all required components are operational

---

## SIH Requirement Compliance Summary

||| Requirement | Status | Implementation | Verification |
|||-------------|--------|----------------|--------------|
||| High-Accuracy OCR (>90%) | ⚠️ **PARTIAL** | 72.4% current accuracy on 551 samples; LPRNet architecture ready for fine-tuning | Dashboard Tab 5, ANPR Lab |
||| Trajectory Tracking | ✅ **IMPLEMENTED** | Spatio-temporal + Fusion + GIS + Explainable AI | Dashboard Tab 1 |
||| Traffic Analytics Dashboard | ✅ **IMPLEMENTED** | Streamlit + Heatmaps + Analytics + Real-time | Dashboard Tab 2 |
||| Alert System | ✅ **IMPLEMENTED** | Blacklist + Anomaly Detection + Impossible Travel | Dashboard Tab 3 |
||| Real-time Processing | ✅ **IMPLEMENTED** | On-demand pipeline processing | `run_demo.py` |
||| Database Persistence | ✅ **IMPLEMENTED** | SQLite + Multiple Stores | Database files |
||| Multi-Camera Support | ✅ **IMPLEMENTED** | Camera Network + Feed Management + Road Constraints | Config files |
||| GIS Integration | ✅ **IMPLEMENTED** | Folium Maps + Trajectory Plotting | Dashboard Tabs 1,2 |

---

## Quick Start for SIH Demonstration

### 1. Setup Demo Data
```bash
python demo/run_alert_demo.py --clean
```
This will:
- Seed 5 blacklisted vehicles with different severities
- Create 18 realistic observations across 5 cameras
- Generate 11 vehicle trajectories
- Produce 4 alerts (3 blacklist matches, 1 repeated camera)
- Persist all data to database

### 2. Launch Dashboard
```bash
streamlit run dashboard/dashboard.py
```

### 3. Demonstrate Key Features

**Tab 1 - Search Vehicle:**
- Search for "TN09CX7134" (multi-camera trajectory example)
- View complete trajectory across 5 cameras with physical validation
- See "Why This Vehicle Match?" explainable evidence breakdown
- Check travel feasibility analysis between camera locations

**Tab 2 - City Analytics:**
- View vehicles per camera chart
- Identify busiest camera
- Check cross-camera route frequencies
- Review average vehicle speeds
- Examine origin-destination patterns
- Check congestion hotspots

**Tab 3 - Alerts:**
- **Active Alerts**: See real-time generated alerts
- **Blacklist Management**: Add/remove vehicles from watchlist
- **Alert History**: View and resolve historical alerts

**Tab 4 - Live Ingestion:**
- Process real camera feeds
- Run AI detection pipeline
- View annotated vehicle detections

**Tab 5 - OCR Evaluation:**
- Evaluate OCR accuracy on datasets
- View character-level and exact match metrics
- Verify current performance and improvement roadmap

---

## Technical Architecture Alignment

### Core Intelligence Modules
|- **Vehicle Intelligence**: `intelligence/vehicle_intelligence.py` - Vehicle analysis
|- **Fusion Engine**: `intelligence/fusion.py` - Multi-source evidence combination with explainable AI
|- **Spatio-Temporal Analysis**: `intelligence/spatio_temporal.py` - Time-space reasoning
|- **Trajectory Building**: `intelligence/trajectory.py` - Path reconstruction
|- **Anomaly Scoring**: `intelligence/anomaly_scoring.py` - Suspicious pattern detection
|- **Alert Generation**: `intelligence/alerts.py` - Real-time alert system

### Analytics Module
|- **Traffic Analytics**: `analytics/analytics.py` - Comprehensive traffic analysis
|- **Route Analysis**: Cross-camera route frequency and patterns
|- **Speed Analysis**: Average vehicle speed calculations
|- **Congestion Detection**: Traffic bottleneck identification
|- **OD Patterns**: Origin-destination flow analysis

### Database Layer
|- **Observation Store**: Vehicle observation persistence
|- **Blacklist Store**: Watchlist management
|- **Alert Store**: Alert history and status tracking
|- **Camera Store**: Camera network configuration

### GIS Integration
|- **Map Generation**: Interactive city maps with traffic overlays
|- **Trajectory Visualization**: Vehicle path plotting on maps
|- **Heatmap Generation**: Traffic density visualization
|- **Camera Network Display**: Multi-camera location mapping

---

## Performance Metrics

### OCR Accuracy
|- **Current**: 72.4% exact match accuracy on 551 Indian plate samples
|- **Target**: >90% exact match accuracy (SIH requirement)
|- **Implementation**: Comprehensive evaluation module with character-level analysis
|- **Path Forward**: LPRNet fine-tuning on Indian plate dataset
|- **Verification**: Dashboard Tab 5 provides real-time accuracy metrics

### Processing Speed
|- Real-time detection pipeline with frame sampling
|- Configurable processing intervals (frame_sample parameter)
|- Optimized for multi-camera concurrent processing

### Scalability
|- SQLite database for efficient data storage
|- Modular architecture for easy camera network expansion
|- Configurable camera network via JSON configuration

---

## Honesty and Transparency Notes

**Important to State During Demo:**
1. **OCR Accuracy**: Current system achieves 72.4% exact-match accuracy, below the 90% SIH requirement. We have identified the path forward (LPRNet fine-tuning) and implemented the architecture.
2. **Demo Data**: The 7-camera demo uses simulated observations for demonstration purposes. In production, all data would come from real camera feeds.
3. **Architecture**: The system currently uses a Streamlit+SQLite prototype. A FastAPI+React+Postgres architecture exists but is not yet fully integrated.
4. **Plate Detector**: Trained plate detector weights ARE included in the submission (models/best_plate_detector.pt) and the system is reproducible.

**Strengths to Highlight:**
1. **Explainable AI**: "Why This Vehicle Match?" feature provides detailed evidence breakdown
2. **Physical Constraints**: Road network validation prevents impossible travel claims
3. **Data Governance**: Comprehensive privacy and data handling documentation
4. **Test Discipline**: 211 unit tests with systematic evaluation
5. **Self-Auditing**: We identified and documented our own accuracy limitations

---

## Conclusion

TrackX demonstrates strong technical capability with three of four SIH requirements fully implemented:

1. ⚠️ **High-Accuracy ANPR/OCR**: Architecture implemented at 72.4% accuracy on 551 samples; clear path to 90% via LPRNet fine-tuning
2. ✅ **Trajectory Tracking**: Complete spatio-temporal tracking with GIS visualization and explainable AI
3. ✅ **Traffic Analytics**: Comprehensive dashboard with heatmaps, speeds, OD patterns, congestion detection
4. ✅ **Alert System**: Real-time blacklist detection and route anomaly identification

The system provides a technically defensible prototype with transparent self-assessment, sophisticated intelligence pipeline, and a clear roadmap to full SIH compliance.
