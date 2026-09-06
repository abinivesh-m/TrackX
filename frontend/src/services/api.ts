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
}

export const api = new ApiClient()
