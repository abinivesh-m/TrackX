// frontend/src/types/index.ts

export interface User {
  id: number
  username: string
  email: string
  full_name?: string
  role: 'operator' | 'analyst' | 'admin' | 'viewer'
  is_active: boolean
  is_admin: boolean
  organization?: string
  department?: string
  last_login?: string
  created_at: string
}

export interface Camera {
  id: number
  camera_id: string
  name: string
  location: string
  latitude: number
  longitude: number
  direction?: string
  road?: string | null
  camera_type: string
  is_active: boolean
  last_seen?: string | null
  observation_count?: number
  // ONLINE: observation activity within the last 24h. OFFLINE: has produced
  // observations before, none recently. NOT_CONFIGURED: this camera has
  // never produced a single observation - see backend/app/api/v1/cameras.py
  // _camera_status(), same threshold intelligence/alerts.py's
  // CAMERA_OFFLINE alert uses so this page and that alert always agree.
  status?: 'ONLINE' | 'OFFLINE' | 'NOT_CONFIGURED' | 'DEGRADED' | 'NO_DATA'
}

export interface Observation {
  id: number
  plate_text?: string
  normalized_plate?: string
  raw_plate_text?: string
  camera_id: string
  timestamp: string
  confidence?: number
  ocr_confidence?: number
  plate_confidence?: number
  vehicle_type?: string
  vehicle_bbox?: number[]
  plate_bbox?: number[]
  annotated_output?: string
  plate_crop_path?: string
  plate_crop_url?: string
  source_file?: string
  direction?: string
}

// A real transition between two consecutive camera visits, from
// intelligence/spatio_temporal.py's calculate_spatial_temporal_plausibility()
// (backend/app/api/v1/vehicles.py._build_hops_and_segments) - road-graph
// distance/speed-limit aware when the cameras are connected, not a
// straight-line guess. is_plausible === false is a real anomaly, not a
// styling flag.
export interface TrajectorySegment {
  from_camera: string
  from_camera_name: string
  to_camera: string
  to_camera_name: string
  is_plausible: boolean | null
  distance_km: number | null
  elapsed_seconds?: number
  required_speed_kmph: number | null
  expected_time_min_seconds?: number
  expected_time_max_seconds?: number
  expected_time_range?: string
  elapsed_time_formatted?: string
  spatial_connected?: boolean
  reason: string
  confidence?: number
}

// One node on the GIS trajectory map - one per camera actually visited
// (consecutive same-camera observations collapsed into a single hop).
export interface TrajectoryHop {
  camera_id: string
  camera_name: string
  lat: number | null
  lng: number | null
  timestamp: string
  direction?: string | null
  confidence?: number | null
  plate_confidence?: number | null
  vehicle_confidence?: number | null
  vehicle_type?: string | null
  plate_crop_url?: string | null
  segment_from_prev: TrajectorySegment | null
}

export interface Trajectory {
  plate_text: string
  vehicle_found: boolean
  vehicle_type?: string | null
  observation_count: number
  camera_count: number
  first_seen?: string
  last_seen?: string
  first_camera?: string
  last_camera?: string
  total_journey_time?: string
  total_distance_km?: number
  total_duration_min?: number
  average_speed_kmh?: number
  route_path: string
  camera_sequence?: string[]
  hops: TrajectoryHop[]
  segments: TrajectorySegment[]
  // Average of the real multi-camera identity-fusion match scores
  // (intelligence/fusion.py) that link consecutive hops into one
  // trajectory - null when there's only one observation to show (nothing
  // to have linked yet), never a fabricated placeholder.
  trajectory_confidence?: number | null
  anomalous_segment_count?: number
  is_blacklisted?: boolean
  blacklist_severity?: string | null
  blacklist_reason?: string | null
  risk_level: string
}

export interface VehicleSearchResponse {
  vehicle_found: boolean
  vehicle?: User
  observations: Observation[]
  trajectory?: Trajectory
}

export interface Alert {
  id: number
  alert_id: string
  // BLACKLISTED_VEHICLE / SUSPICIOUS_ROUTE / REPEATED_CAMERA (vehicle-scoped)
  // or CAMERA_OFFLINE / CONGESTION_BOTTLENECK (camera-scoped, no plate) -
  // see is_vehicle_alert.
  alert_type: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH'
  plate_text: string | null
  normalized_plate: string | null
  camera_id?: string
  timestamp: string
  description?: string
  confidence?: number
  similarity?: number
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'
  // Per-alert-type proof: BLACKLISTED_VEHICLE -> matched_against/
  // similarity/camera_hits/watchlist_source; SUSPICIOUS_ROUTE ->
  // anomaly_type/anomaly_score/signal_breakdown/camera_sequence;
  // REPEATED_CAMERA -> sighting_count/sighting_timestamps; CAMERA_OFFLINE ->
  // last_seen/threshold_hours/reason; CONGESTION_BOTTLENECK ->
  // congestion_score/bottleneck_score/avg_speed_kmh/duration_minutes.
  evidence?: Record<string, any>
  // false for CAMERA_OFFLINE / CONGESTION_BOTTLENECK - no vehicle to link
  // to Vehicle Intelligence or a trajectory search.
  is_vehicle_alert?: boolean
}

// One entry from GET /api/v1/alerts/watchlist - real persisted watchlist
// data (database/blacklist_store.py), never invented. `source` tells demo
// scenario plates (seeded by demo/seed_demo_data.py) apart from anything an
// operator actually added via POST /api/v1/vehicles/watchlist.
export interface WatchlistEntry {
  id: number
  plate: string
  normalized_plate: string
  description?: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH'
  source: 'DEMO_SEED' | 'OPERATOR'
  created_at: string
}

export interface AnalyticsSummary {
  total_vehicles: number
  total_observations: number
  active_cameras: number
  avg_vehicles_per_camera: number
  average_speed: number | null
  hourly_density: {
    hourly_data: Array<{ hour: string; camera_id: string; count: number }>
    hourly_totals: Array<{ hour: string; count: number }>
  }
  top_routes: Array<{
    route: string
    origin: string
    destination: string
    vehicle_count: number
    unique_vehicles: number
    average_travel_time_minutes?: number
  }>
  congestion_hotspots: Camera[]
  vehicle_counts_per_camera: Array<{
    camera_id: string
    camera_name: string
    location: string
    vehicle_count: number
  }>
  heatmap_points: HeatmapPoint[]
}

export interface HeatmapPoint {
  camera_id: string
  latitude: number
  longitude: number
  intensity: number
  average_speed?: number | null
}

// Route Anomaly Detection Types
export interface RouteAnomaly {
  anomaly_id: string
  plate: string
  from_camera: string
  to_camera: string
  timestamp: string
  anomaly_type: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  status: 'OPEN' | 'UNDER_INVESTIGATION' | 'RESOLVED' | 'FALSE_POSITIVE'
  anomaly_score: number
  details: {
    unexpected_transition: boolean
    impossible_travel_time: boolean
    unreasonable_speed: boolean
    observed_speed_kmph: number
    expected_min_time: number
    expected_max_time: number
    observed_travel_time: number
    distance_km: number
  }
  investigated_by?: string
  investigation_notes?: string
  resolution_notes?: string
  created_at: string
  updated_at: string
}

export interface CameraTransition {
  to_camera: string
  expected_min_time: number
  expected_max_time: number
  average_time: number
  transition_count: number
  road_distance_km: number
}

export interface RouteAnalysis {
  plate: string
  from_camera: string
  to_camera: string
  is_valid_route: boolean
  expected_travel_time_min: number
  expected_travel_time_max: number
  observed_travel_time: number
  distance_km: number
  route_validity: string
  anomaly_detected: boolean
  anomaly_details: {
    unexpected_transition: boolean
    impossible_travel_time: boolean
    unreasonable_speed: boolean
    observed_speed_kmph: number
    expected_transitions: string[]
  }
}

// Congestion Detection Types
export interface TrafficMetrics {
  id: number
  camera_id: string
  road_segment_id: string
  window_start: string
  window_end: string
  window_duration_minutes: number
  vehicle_count: number
  unique_vehicles: number
  flow_rate_vehicles_per_hour: number
  avg_speed_kmh: number
  vehicle_density: number
  congestion_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'SEVERE'
  congestion_score: number
  is_congested: boolean
  is_bottleneck: boolean
  bottleneck_score: number
  avg_travel_time_seconds: number
  queue_length_vehicles: number
  is_anomaly: boolean
  anomaly_score: number
  created_at: string
}

export interface CongestionEvent {
  id: number
  event_id: string
  camera_id: string
  road_segment_id: string
  event_start: string
  event_end?: string
  status: 'ACTIVE' | 'RESOLVED' | 'INVESTIGATING'
  congestion_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'SEVERE'
  congestion_score: number
  avg_speed_kmh: number
  vehicle_density: number
  flow_rate_vehicles_per_hour: number
  is_bottleneck: boolean
  bottleneck_score: number
  duration_minutes: number
  affected_cameras: string[]
  resolution_notes?: string
  created_at: string
  updated_at: string
}

// One camera's live reading from GET /api/v1/gis/congestion - real,
// backend/app/api/v1/gis.py:get_gis_congestion(), built on the same
// analytics.congestion_hotspots() model as everything else on this page.
export interface GisCongestionPoint {
  camera_id: string
  camera_name: string
  lat: number
  lng: number
  level: string
  score: number
  vehicle_count: number
  unique_vehicles: number
  description: string
}

// One real origin-destination flow from GET /api/v1/gis/od_flow -
// backend/app/api/v1/gis.py:get_gis_od_flow(), derived from actual
// reconstructed multi-camera trajectories (intelligence/trajectory.py),
// not invented routes.
export interface GisOdFlow {
  origin_camera: string
  origin_name: string
  origin_lat: number
  origin_lng: number
  dest_camera: string
  dest_name: string
  dest_lat: number
  dest_lng: number
  count: number
}

export interface TrafficThresholds {
  speed_threshold_kmh: number
  density_threshold_vehicles_per_km: number
  flow_threshold_vehicles_per_hour: number
  congestion_duration_minutes: number
  bottleneck_speed_reduction_percent: number
  anomaly_deviation_percent: number
}

export interface CongestionAnalytics {
  camera_id: string
  camera_name: string
  location: string
  current_congestion_level: string
  avg_speed_kmph: number
  vehicle_density: number
  flow_rate_vehicles_per_hour: number
  is_congested: boolean
  is_bottleneck: boolean
  bottleneck_score: number
  active_events: CongestionEvent[]
}
