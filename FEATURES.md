# TrackX — Feature → File Map

Which file(s) implement each feature, front to back. Frontend pages live in
`frontend/src/pages/`, API routers in `backend/app/api/v1/`, and the real
algorithms live outside `backend/` entirely (`analytics/`, `intelligence/`,
`detection/`, `recognition/`, `demo/`, `database/`) - the backend is a thin
FastAPI wrapper around those, not where the actual logic lives.

## Operations Center (Dashboard)
- **Page**: `frontend/src/pages/DashboardPage.tsx`
- **API**: `backend/app/api/v1/analytics.py` (`/analytics/summary`),
  `backend/app/api/v1/alerts.py` (`/alerts/stats`)
- **Notification bell**: `frontend/src/components/layout/Header.tsx`

## Vehicle Intelligence (plate search + trajectory summary)
- **Page**: `frontend/src/pages/VehiclesPage.tsx`
- **API**: `backend/app/api/v1/vehicles.py` — `search_vehicle()` is the
  main endpoint; `_summarize()` in the same file computes risk level,
  total distance, average speed, and trajectory confidence (see "Vehicle
  speed / trajectory math" below).
- **Watchlist add/remove**: same file, `add_to_watchlist()` /
  `remove_from_watchlist()`, backed by `database/blacklist_store.py`.

## GIS Trajectory / Route Map
- **Page**: `frontend/src/pages/GISPage.tsx`, `frontend/src/pages/TrajectoryPage.tsx`
- **Map component**: `frontend/src/components/maps/TrajectoryMap.tsx`,
  `frontend/src/components/maps/CameraMap.tsx`,
  `frontend/src/components/maps/CongestionMap.tsx`,
  `frontend/src/components/maps/TrafficHeatmap.tsx`
- **Tile provider (no API key)**: `frontend/src/config/mapTiles.ts` -
  OpenStreetMap standard tiles, overridable via `VITE_MAP_TILE_URL`. See
  "Map tile provider decision" below for why CARTO was replaced.
- **API**: `backend/app/api/v1/gis.py` (`/gis/heatmap`, `/gis/congestion`,
  `/gis/od_flow`), `backend/app/api/v1/trajectory.py`
- **Road-graph-aware distance**: `gis/` (road network graph), consumed by
  `backend/app/api/v1/vehicles.py`'s `_build_hops_and_segments()`.

## Traffic Analytics & Congestion
- **Page**: `frontend/src/pages/AnalyticsPage.tsx` (density/routes charts),
  `frontend/src/pages/CongestionPage.tsx` (bottlenecks, active/resolved
  events, thresholds)
- **API**: `backend/app/api/v1/analytics.py`, `backend/app/api/v1/congestion.py`
- **Real math**: `analytics/analytics.py` (`congestion_hotspots()` and
  friends) - the API layer does not reimplement any of this.

## Alert Center
- **Page**: `frontend/src/pages/AlertsPage.tsx`
- **API**: `backend/app/api/v1/alerts.py` — `/alerts`, `/alerts/stats`,
  `/alerts/{id}/resolve`, `/alerts/{id}/acknowledge`, `/alerts/watchlist`
  (route order in this file matters - static paths like `/stats` and
  `/watchlist` are declared before the `/{alert_id}/...` dynamic routes so
  they can't be shadowed).
- **Store**: `database/alert_store.py`, `database/blacklist_store.py`
- **Generation logic**: `demo/run_alert_demo.py` / `demo/seed_alert_demo.py`
  for demo seeding; real-time alerts come from watchlist matches, route
  anomalies, and congestion bottlenecks as they're detected.

## Route Anomaly Detection
- **Page**: `frontend/src/pages/RouteAnomalyPage.tsx`
- **API**: `backend/app/api/v1/route_anomaly.py`
- **Real math**: `database/route_anomaly_store.py`,
  `calculate_spatial_temporal_plausibility()` (used by both the anomaly
  detector and the vehicle risk-level calculation above) — lives in the
  trajectory/intelligence layer, not duplicated per caller.

## Camera Network
- **Page**: `frontend/src/pages/CamerasPage.tsx`
- **API**: `backend/app/api/v1/cameras.py`
- **Camera registry**: `network/camera_network.py` (the 7 seeded cameras'
  IDs, names, real lat/long)

## AI Processing (camera-folder + video-upload pipeline)
- **Page**: `frontend/src/pages/VideoDemoPage.tsx` (route `/ai-processing`
  in the sidebar) — two tabs:
  - **Camera Media tab**: runs the pipeline on images/videos already in
    `data/cameras/<CAM_ID>/images|videos/`. API: new endpoints
    `POST /observations/process-camera` and
    `GET /observations/camera-media/{camera_id}` in
    `backend/app/api/v1/observations.py`, which call straight into
    `demo/visual_pipeline.py`'s `process_image()` / `process_video()` (the
    exact functions `python -m demo.visual_pipeline --camera CAM_01` uses
    from the CLI) — no separate/duplicated detection code.
  - **Upload Video tab**: uploads a video file directly. API:
    `POST /observations/ingest-video`, same file, reusing
    `pipeline.py`'s `run_video_to_db()`.
- **Camera-folder discovery**: `demo/camera_simulator.py` -
  `list_camera_media()` / `get_camera_feed()` (anchored to an absolute
  path via `config.PROJECT_ROOT` so it works regardless of the server's
  working directory - see the comment in that file for why this matters
  for the Render deploy command specifically).
- **Detection / OCR / plate pipeline**: `detection/vehicle_detector.py`
  (YOLO), `detection/detect_plates.py` (plate box detector),
  `recognition/ocr_reader.py` (PaddleOCR, with LPRNet as a disabled
  fallback until a trained checkpoint exists - see `models/README.md`),
  `recognition/plate_normalizer.py`, `recognition/appearance.py`
  (re-identification embedding).
- **Annotated frames / plate crops served to the frontend**: mounted as
  static files in `backend/app/main.py` at `/media/annotated` and
  `/media/plate-crops`.

## Vehicle speed / trajectory math (verified this session)
Lives in `backend/app/api/v1/vehicles.py`'s `_summarize()` +
`_build_hops_and_segments()`:
- **Distance**: sum of real, road-graph-aware per-segment distances (not
  a single straight-line haversine over the whole trip).
- **Duration**: `last_observation_timestamp - first_observation_timestamp`.
- **Average speed**: `distance_km / (duration_min / 60)`, but only when
  `duration_min > 0.5` **and** `distance_km > 0` — otherwise reported as
  `0.0` rather than a wildly inflated number from dividing by a near-zero
  duration. (Minor documented nuance: this returns `0.0` for a real but
  very short hop, not `null` — semantically "not enough time elapsed to
  compute a reliable average", not "vehicle was stationary". Not changed
  this session since it's working, honest, and not a correctness bug.)
- **Risk level**: `HIGH` only for an active blacklist match (a real
  operator-configured fact), `MEDIUM` for a real implausible segment
  (see `calculate_spatial_temporal_plausibility()`), `LOW` otherwise —
  never a fabricated score.
- **Trajectory confidence**: average of the real per-hop match scores from
  `intelligence/`'s identity fusion (plate similarity + appearance +
  temporal + spatial); `null` for a single-observation trajectory, not a
  fabricated 100%.
- Spot-checked this session across all 57 distinct plates in the seeded
  dataset via a direct backend probe — every value was internally
  consistent (no negative distances, no absurd speeds, `0.0`-speed cases
  all traced to the sub-30-second-window rule above, not a bug).

## Map tile provider decision (CARTO vs. OpenStreetMap)
CARTO's anonymous basemap endpoint
(`{s}.basemaps.cartocdn.com/dark_all/...`), previously hardcoded across
all 4 Leaflet map components, was live-reproduced this session serving
placeholder tiles reading **"API KEY REQUIRED"** — it no longer works
without a CARTO account/key. Per the requirement that the shipped map
never require an API key, all 4 map components
(`CameraMap.tsx`, `CongestionMap.tsx`, `TrafficHeatmap.tsx`,
`TrajectoryMap.tsx`) now use OpenStreetMap's standard keyless tile
endpoint via the shared `frontend/src/config/mapTiles.ts` module
(overridable through `VITE_MAP_TILE_URL` if you later get a CARTO key and
want its look back — nothing else needs to change). This is the
"best interactive map that needs no key" option for the GIS Trajectory
page specifically, since it's the same Leaflet-based `TrajectoryMap.tsx`
component, just pointed at a working, free tile source.

## "Manage data / CSV" feature
No CSV import/export/management feature exists anywhere in this codebase
(frontend or backend) — an exhaustive repo-wide search found nothing to
fix or clean up here. If this was meant to describe something else
(e.g. the seeded demo dataset, or the camera-folder AI Processing feature
above), let me know what it should do and it can be built rather than
guessed at.

## Deployment
- **Recommended, tested path**: `render.yaml` (repo root) + `DEPLOYMENT.md`
  — single Python web service, PaddleOCR + SQLite, matches what this
  session actually built and tested (`npm run build` succeeds,
  251/251 backend tests pass).
- **Other config that already existed in the repo** (`railway.json`,
  `docker-compose*.yml`, `backend/Dockerfile`, `backend/start.sh`) is from
  a different, Postgres+EasyOCR-oriented attempt that doesn't match this
  codebase's real dependencies (it actually uses PaddleOCR, not EasyOCR)
  and was not verified this session — see the "Correction" section in
  `DEPLOYMENT.md` for the full explanation, including one file
  (`backend/render_main.py`) that has been disabled because it silently
  served 100% fabricated data.

## Local run / test instructions
See `RUNNING.md`.
