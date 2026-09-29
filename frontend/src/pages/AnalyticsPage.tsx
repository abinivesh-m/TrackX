// frontend/src/pages/AnalyticsPage.tsx

import React, { useState, useEffect } from 'react'
import { toast } from 'react-toastify'
import { api } from '@/services/api'
import TrafficHeatmap from '@/components/maps/TrafficHeatmap'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { TrendingUp, Activity, MapPin, AlertTriangle, WifiOff } from 'lucide-react'
import type { AnalyticsSummary } from '@/types'

const AnalyticsPage: React.FC = () => {
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  // Tells "backend unreachable" apart from "genuinely nothing to show yet" -
  // both used to render as the same "No analytics data available" message.
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const data = await api.getAnalyticsSummary()
        setAnalytics(data)
        setLoadError(null)
      } catch (error) {
        console.error('Failed to fetch analytics:', error)
        setLoadError('Could not reach the TrackX API.')
        toast.error('Failed to load analytics data')
      } finally {
        setIsLoading(false)
      }
    }

    fetchAnalytics()
  }, [])

  if (isLoading) {
    return <div className="flex justify-center items-center h-full">Loading...</div>
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center gap-2 text-critical-400">
        <WifiOff size={32} />
        <p className="text-lg font-medium">{loadError}</p>
        <p className="text-sm text-muted">Analytics could not be loaded. Try refreshing the page.</p>
      </div>
    )
  }

  if (!analytics) {
    return <div className="text-center text-muted mt-10">No analytics data available</div>
  }

  const vehicleCountData = analytics.vehicle_counts_per_camera.map(item => ({
    name: item.camera_id,
    vehicles: item.vehicle_count,
  }))

  const hourlyData = analytics.hourly_density.hourly_totals.map(item => ({
    hour: item.hour.split(' ')[1],
    vehicles: item.count,
  }))

  const routeData = analytics.top_routes.map(route => ({
    name: route.route,
    vehicles: route.vehicle_count,
  }))

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded p-3 flex items-center justify-between text-sm text-muted">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-clear-400" />
          <span>Urban analytics aggregating multi-camera density, route flow trends, and bottleneck hotspots, computed fresh from stored observations each time this page loads.</span>
        </div>
        <span className="text-xs bg-surface-light px-2 py-0.5 rounded font-mono border border-border">MACRO ANALYTICS</span>
      </div>

      <h1 className="text-2xl font-bold text-white">Traffic Analytics</h1>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-2">
            <Activity size={20} className="text-signal-400" />
            <span className="text-sm text-muted">Total Vehicles</span>
          </div>
          <p className="text-3xl font-bold text-white">{analytics.total_vehicles.toLocaleString()}</p>
        </div>
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-2">
            <MapPin size={20} className="text-clear-400" />
            <span className="text-sm text-muted">Active Cameras</span>
          </div>
          <p className="text-3xl font-bold text-white">{analytics.active_cameras}</p>
        </div>
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp size={20} className="text-telemetry-400" />
            <span className="text-sm text-muted">Avg/Camera</span>
          </div>
          <p className="text-3xl font-bold text-white">{analytics.avg_vehicles_per_camera}</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-white">Traffic Density Heatmap</h3>
            <span className="text-xs text-muted">Circle size and colour reflect camera traffic intensity</span>
          </div>
          <TrafficHeatmap points={analytics.heatmap_points} />
        </div>

        {/* Vehicle Count per Camera */}
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-4">Vehicles per Camera</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={vehicleCountData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#232733" />
                <XAxis dataKey="name" stroke="#6b7385" />
                <YAxis stroke="#6b7385" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#171a21', border: '1px solid #232733', borderRadius: '3px' }}
                  labelStyle={{ color: '#dde1e6' }}
                />
                <Bar dataKey="vehicles" fill="#ec9d1e" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hourly Density */}
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-4">Hourly Traffic Density</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={hourlyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#232733" />
                <XAxis dataKey="hour" stroke="#6b7385" />
                <YAxis stroke="#6b7385" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#171a21', border: '1px solid #232733', borderRadius: '3px' }}
                  labelStyle={{ color: '#dde1e6' }}
                />
                <Area type="monotone" dataKey="vehicles" stroke="#3f9e5c" fill="#3f9e5c" fillOpacity={0.3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Routes */}
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-4">Top Origin-Destination Routes</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={routeData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#232733" />
                <XAxis type="number" stroke="#6b7385" />
                <YAxis type="category" dataKey="name" stroke="#6b7385" width={150} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#171a21', border: '1px solid #232733', borderRadius: '3px' }}
                  labelStyle={{ color: '#dde1e6' }}
                />
                <Bar dataKey="vehicles" fill="#42c9d1" radius={[0, 2, 2, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Congestion Hotspots */}
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-4">Congestion Hotspots</h3>
          {analytics.congestion_hotspots.length > 0 ? (
            <div className="space-y-3">
              {analytics.congestion_hotspots.map((camera) => (
                <div key={camera.camera_id} className="flex items-center justify-between p-3 rounded bg-surface-light border border-border">
                  <div className="flex items-center gap-3">
                    <AlertTriangle size={16} className="text-critical-400" />
                    <span className="text-white font-medium">{camera.camera_id}</span>
                    <span className="text-xs text-muted">{camera.name}</span>
                  </div>
                  <span className="text-critical-400 text-sm font-bold">{camera.observation_count} vehicles</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted text-sm">No congestion hotspots detected</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default AnalyticsPage
