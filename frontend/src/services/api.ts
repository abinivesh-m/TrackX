// frontend/src/services/api.ts

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios'
import { authService } from './auth'
import type { User, Camera, VehicleSearchResponse, Trajectory, AnalyticsSummary, Alert, Observation } from '@/types'

class ApiClient {
  private client: AxiosInstance
  private baseURL: string

  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || '/api/v1'
    
    this.client = axios.create({
      baseURL: this.baseURL,
      // Previously unset (axios default = no timeout at all), so a hung
      // backend call - a slow query, a stuck model - left the UI waiting
      // forever with no error state ever shown. 30s is generous for every
      // real endpoint here except video upload, which explicitly overrides
      // this per-call (see ingestVideo below).
      timeout: 30 * 1000,
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        const token = authService.getAccessToken()
        if (token) {
          config.headers.Authorization = `Bearer ${token}` 
        }
        return config
      },
      (error) => Promise.reject(error)
    )
    
    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config
        
        // Handle 401 with token refresh
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true
          
          try {
            const refreshToken = authService.getRefreshToken()
            if (refreshToken) {
              const response = await axios.post(`${this.baseURL}/auth/refresh`, {
                refresh_token: refreshToken,
              })
              
              authService.setTokens(response.data.access_token, response.data.refresh_token)
              originalRequest.headers.Authorization = `Bearer ${response.data.access_token}` 
              
              return this.client(originalRequest)
            }
          } catch (refreshError) {
            authService.logout()
            window.location.href = '/login'
          }
        }
        
        return Promise.reject(error)
      }
    )
  }

  // Generic methods
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config)
    return response.data
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config)
    return response.data
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<T>(url, data, config)
    return response.data
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config)
    return response.data
  }

  // API Methods
  getCameras() {
    return this.get<Camera[]>('/cameras')
  }

  getCameraHealth() {
    return this.get<Camera[]>('/cameras/health')
  }

  searchVehicle(params: { plate: string; camera_id?: string; start_time?: string; end_time?: string }) {
    return this.get<VehicleSearchResponse>('/vehicles/search', { params })
  }

  getVehicleTrajectory(plate: string) {
    return this.get<Trajectory>(`/vehicles/${plate}/trajectory`)
  }

  searchTrajectory(plate: string) {
    return this.get<any>('/trajectory/search', { params: { plate } })
  }

  getRecentTrajectories(limit: number = 10) {
    return this.get<any[]>('/trajectory/recent', { params: { limit } })
  }

  getGISCameras() {
    return this.get<any[]>('/gis/cameras')
  }

  getGISHeatmap() {
    return this.get<any>('/gis/heatmap')
  }

  getGISCongestion() {
    return this.get<any[]>('/gis/congestion')
  }

  getGISFlow() {
    return this.get<any[]>('/gis/od_flow')
  }

  getHealth() {
    return this.get<any>('/health')
  }

  getAnalyticsSummary() {
    return this.get<AnalyticsSummary>('/analytics/summary')
  }

  getAlerts(params?: { status?: string; severity?: string; limit?: number }) {
    return this.get<Alert[]>('/alerts', { params })
  }

  getAlertStats() {
    return this.get<{ total_alerts: number; open_alerts: number; high_severity_open: number }>('/alerts/stats')
  }

  resolveAlert(alertId: string, notes?: string) {
    return this.post(`/alerts/${alertId}/resolve`, null, { params: { notes } })
  }

  acknowledgeAlert(alertId: string) {
    return this.post(`/alerts/${alertId}/acknowledge`)
  }

  getWatchlist() {
    return this.get<any[]>('/alerts/watchlist')
  }

  addToWatchlist(plate: string, severity: string, reason: string) {
    return this.post('/vehicles/watchlist', null, { params: { plate, severity, reason } })
  }

  removeFromWatchlist(plate: string) {
    return this.delete('/vehicles/watchlist', { params: { plate } })
  }

  getObservations(params?: { camera_id?: string; plate?: string; limit?: number }) {
    return this.get<Observation[]>('/observations', { params })
  }

  getRecentObservations() {
    return this.get<Observation[]>('/observations/recent')
  }

  // Admin methods
  getUsers() {
    return this.get<User[]>('/admin/users')
  }

  createUser(data: Partial<User>) {
    return this.post('/admin/users', data)
  }

  updateUser(userId: number, data: Partial<User>) {
    return this.put(`/admin/users/${userId}`, data)
  }

  deleteUser(userId: number) {
    return this.delete(`/admin/users/${userId}`)
  }

  getAuditLogs(params?: { limit?: number; offset?: number }) {
    return this.get('/admin/audit-logs', { params })
  }

  getSystemHealth() {
    return this.get('/admin/system-health')
  }

  // Route Anomaly Detection
  getRouteAnomalies(params?: { plate?: string; severity?: string; status?: string; limit?: number }) {
    return this.get<any[]>('/route-anomaly/anomalies', { params })
  }

  getRouteAnomaly(anomalyId: string) {
    return this.get<any>(`/route-anomaly/anomalies/${anomalyId}`)
  }

  analyzeVehicleRoute(plate: string, startTime?: string, endTime?: string) {
    return this.post<any>(`/route-anomaly/analyze/${plate}`, null, { params: { start_time: startTime, end_time: endTime } })
  }

  analyzeCameraTransition(fromCamera: string, toCamera: string, travelTimeSeconds: number) {
    return this.get<any>(`/route-anomaly/analyze/${fromCamera}/${toCamera}`, { params: { travel_time_seconds: travelTimeSeconds } })
  }

  getCameraTransitions(cameraId: string) {
    return this.get<any>(`/route-anomaly/topology/transitions/${cameraId}`)
  }

  getAnomalyStatistics(startTime?: string, endTime?: string) {
    return this.get<any>('/route-anomaly/statistics', { params: { start_time: startTime, end_time: endTime } })
  }

  updateAnomalyStatus(anomalyId: string, status: string, investigatedBy?: string, investigationNotes?: string, resolutionNotes?: string) {
    return this.put<any>(`/route-anomaly/anomalies/${anomalyId}/status`, {
      status,
      investigated_by: investigatedBy,
      investigation_notes: investigationNotes,
      resolution_notes: resolutionNotes
    })
  }

  // Congestion Detection
  getCameraTrafficMetrics(cameraId: string, hours: number = 24) {
    return this.get<any>(`/congestion/metrics/${cameraId}`, { params: { hours } })
  }

  getActiveCongestionEvents(cameraId?: string, limit: number = 50) {
    return this.get<any[]>('/congestion/events/active', { params: { camera_id: cameraId, limit } })
  }

  getCongestionEventHistory(cameraId?: string, startTime?: string, endTime?: string, limit: number = 50) {
    return this.get<any[]>('/congestion/events/history', { params: { camera_id: cameraId, start_time: startTime, end_time: endTime, limit } })
  }

  processCameraCongestion(cameraId: string, windowDurationMinutes: number = 5) {
    return this.post<any>(`/congestion/process/${cameraId}`, null, { params: { window_duration_minutes: windowDurationMinutes } })
  }

  processAllCamerasCongestion(windowDurationMinutes: number = 5) {
    return this.post<any>('/congestion/process/all', null, { params: { window_duration_minutes: windowDurationMinutes } })
  }

  getCongestionAnalytics(cameraId: string) {
    return this.get<any>(`/congestion/analytics/${cameraId}`)
  }

  getActiveBottlenecks(limit: number = 20) {
    return this.get<any>('/congestion/bottlenecks', { params: { limit } })
  }

  getTrafficThresholds() {
    return this.get<any>('/congestion/thresholds')
  }

  updateTrafficThresholds(thresholds: any) {
    return this.put<any>('/congestion/thresholds', thresholds)
  }

  // Video Demo ingest
  ingestVideo(
    file: File,
    cameraId: string,
    onUploadProgress?: (percent: number) => void
  ) {
    const form = new FormData()
    form.append('file', file)
    form.append('camera_id', cameraId)
    return this.post<any>('/observations/ingest-video', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // Processing (detection + OCR) can genuinely take longer than the
      // default timeout for a demo-length clip - this is synchronous
      // real inference, not a quick CRUD call.
      timeout: 5 * 60 * 1000,
      onUploadProgress: (evt) => {
        if (onUploadProgress && evt.total) {
          onUploadProgress(Math.round((evt.loaded / evt.total) * 100))
        }
      },
    })
  }

  // Camera-folder AI processing: runs the real detection/OCR pipeline over
  // whatever images/videos already sit in a camera's local folder (see
  // demo/camera_simulator.py + demo/visual_pipeline.py), rather than a
  // user-uploaded file. Powers the "Process Camera Media" tab on the
  // AI Processing page.
  getCameraMedia(cameraId: string) {
    return this.get<any>(`/observations/camera-media/${cameraId}`)
  }

  processCamera(cameraId: string, frameSpeed: number, maxFrames?: number | null) {
    const form = new FormData()
    form.append('camera_id', cameraId)
    form.append('frame_speed', String(frameSpeed))
    if (maxFrames !== undefined && maxFrames !== null && maxFrames > 0) {
      form.append('max_frames', String(maxFrames))
    }
    return this.post<any>('/observations/process-camera', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // Same reasoning as ingestVideo - this is synchronous real inference
      // over potentially several images/videos, not a quick CRUD call.
      timeout: 5 * 60 * 1000,
    })
  }
}

export const api = new ApiClient()
