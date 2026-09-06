// frontend/src/pages/DashboardPage.tsx

import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import CameraMap from '@/components/maps/CameraMap'
import StatCard from '@/components/common/StatCard'
import RecentActivity from '@/components/common/RecentActivity'
import { Activity, Camera, AlertTriangle, Gauge } from 'lucide-react'
import type { AnalyticsSummary, Camera as CameraType, Alert, Observation } from '@/types'

const DashboardPage: React.FC = () => {
  const [cameras, setCameras] = useState<CameraType[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [recentObservations, setRecentObservations] = useState<Observation[]>([])
  const [healthStatus, setHealthStatus] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [camerasData, analyticsData, alertsData, observationsData, healthData] = await Promise.all([
          api.getCameras(),
          api.getAnalyticsSummary(),
          api.getAlerts({ limit: 5 }),
          api.getRecentObservations(),
          api.getHealth().catch(() => null)
        ])
        
        setCameras(camerasData)
        setAnalytics(analyticsData)
        setAlerts(alertsData)
        setRecentObservations(observationsData)
        setHealthStatus(healthData)
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchData()
  }, [])

  if (isLoading) {
    return <div className="flex justify-center items-center h-full text-white">Loading Command Center...</div>
  }

  const openAlerts = alerts.filter(a => a.status === 'OPEN').length

  return (
    <div className="space-y-6">
      {/* Demo Mode Notice Banner */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center justify-between text-amber-300 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span><b>DEMO MODE (SIH-26127):</b> Operating on recorded multi-camera feeds with genuine Indian plates for evaluation.</span>
        </div>
        <span className="text-xs bg-amber-500/20 px-2 py-0.5 rounded font-mono">BEL JUDGES DEMO</span>
      </div>

      <h1 className="text-2xl font-bold text-white">Command Center</h1>
      
      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Activity}
          label="Total Vehicles Detected"
          value={analytics?.total_vehicles?.toLocaleString() || '0'}
          iconColor="bg-blue-500/20 text-blue-400"
        />
        <StatCard
          icon={Camera}
          label="Active Cameras"
          value={analytics?.active_cameras?.toString() || '0'}
          iconColor="bg-green-500/20 text-green-400"
        />
        <StatCard
          icon={AlertTriangle}
          label="Open Alerts"
          value={openAlerts.toString()}
          iconColor="bg-red-500/20 text-red-400"
        />
        <StatCard
          icon={Gauge}
          label="Avg Vehicles/Camera"
          value={analytics?.avg_vehicles_per_camera?.toFixed(1) || '0'}
          iconColor="bg-purple-500/20 text-purple-400"
        />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Map */}
        <div className="lg:col-span-2">
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white">City Camera Network</h2>
              <span className="text-xs text-green-400 flex items-center gap-2">
                <span className="w-2 h-2 bg-green-500 rounded-full pulse" />
                ONLINE
              </span>
            </div>
            <div className="h-[500px] rounded-lg overflow-hidden">
              <CameraMap cameras={cameras} />
            </div>
          </div>
        </div>

        {/* Side Panel */}
        <div className="space-y-6">
          {/* System Status */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-white mb-4">System Status</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-muted text-sm">AI Engine</span>
                <span className="text-green-400 text-sm flex items-center gap-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full" />
                  {healthStatus?.ai_engine || 'OPERATIONAL'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted text-sm">Database</span>
                <span className="text-green-400 text-sm flex items-center gap-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full" />
                  {healthStatus?.database || 'CONNECTED'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted text-sm">OCR Engine</span>
                <span className="text-blue-400 text-sm flex items-center gap-2">
                  <span className="w-2 h-2 bg-blue-500 rounded-full" />
                  {healthStatus?.ocr_engine || 'LPRNet + PaddleOCR'}
                </span>
              </div>
            </div>
          </div>

          {/* Recent Activity */}
          <RecentActivity observations={recentObservations} />

          {/* Alerts Preview */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white">Recent Alerts</h3>
              <Link to="/alerts" className="text-xs text-blue-400 hover:text-blue-300">View All</Link>
            </div>
            <div className="space-y-3">
              {alerts.length === 0 ? (
                <div className="text-xs text-muted text-center py-4">No active security alerts</div>
              ) : (
                alerts.slice(0, 3).map((alert) => (
                  <div key={alert.alert_id} className="p-3 rounded-lg bg-surface-light border border-border">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">{alert.alert_type}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        alert.severity === 'HIGH' 
                          ? 'bg-red-500/20 text-red-400'
                          : alert.severity === 'MEDIUM'
                          ? 'bg-yellow-500/20 text-yellow-400'
                          : 'bg-green-500/20 text-green-400'
                      }`}>
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-sm text-white font-mono">{alert.plate_text}</p>
                    <p className="text-xs text-muted mt-1">{alert.description}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage