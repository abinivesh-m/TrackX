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
  road?: string
  camera_type: string
  is_active: boolean
  last_seen?: string
  observation_count?: number
  status?: 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'NO_DATA'
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
  vehicle_type?: string
  vehicle_bbox?: number[]
  plate_bbox?: number[]
  annotated_output?: string
  plate_crop_path?: string
  source_file?: string
}

export interface TrajectoryPoint {
  observation_id: number
  camera_id: string
  camera_name: string
  location: string
  latitude: number
  longitude: number
  timestamp: string
  plate_text: string
  confidence: number
  vehicle_type: string
  annotated_output?: string
  plate_crop_path?: string
}

export interface Trajectory {
  plate_text: string
  vehicle_found: boolean
  observation_count: number
  camera_count: number
  first_seen?: string
  last_seen?: string
  total_journey_time?: string
  average_speed?: number
  route_path: string
  trajectory_points: TrajectoryPoint[]
  watchlist_status: string
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
  alert_type: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH'
  plate_text: string
  normalized_plate: string
  camera_id?: string
  timestamp: string
  description?: string
  confidence?: number
  similarity?: number
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'
  evidence?: Record<string, any>
}

export interface AnalyticsSummary {
  total_vehicles: number
  active_cameras: number
  avg_vehicles_per_camera: number
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
