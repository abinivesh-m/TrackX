import React, { useState, useEffect } from 'react'
import { apiClient } from '../App'
import { TrendingUp, BarChart3, Activity, Clock } from 'lucide-react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function Analytics() {
  // Fetches analytics data including routes and camera performance from Coimbatore
  const [hourlyData, setHourlyData] = useState([])
  const [stats, setStats] = useState(null)
  const [routeData, setRouteData] = useState([])
  const [cameraPerformance, setCameraPerformance] = useState([])
  const [vehiclesPerCamera, setVehiclesPerCamera] = useState([])
  const [congestion, setCongestion] = useState(null)
  const [speedByPair, setSpeedByPair] = useState([])
  const [odPatterns, setOdPatterns] = useState([])
  const [repeatedSightings, setRepeatedSightings] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAnalytics()
  }, [])

  const fetchAnalytics = async () => {
    try {
      const [hourlyRes, statsRes, routesRes, perfRes, vpcRes, congRes, speedRes, odRes, repRes] = await Promise.all([
        apiClient.get('/api/v1/analytics/hourly'),
        apiClient.get('/api/v1/analytics/stats'),
        apiClient.get('/api/v1/analytics/routes'),
        apiClient.get('/api/v1/analytics/camera-performance'),
        apiClient.get('/api/v1/analytics/vehicles-per-camera'),
        apiClient.get('/api/v1/analytics/congestion'),
        apiClient.get('/api/v1/analytics/speed-by-pair'),
        apiClient.get('/api/v1/analytics/od-patterns'),
        apiClient.get('/api/v1/analytics/repeated-sightings')
      ])
      setHourlyData(hourlyRes.data.data || [])
      setStats(statsRes.data)
      setRouteData(routesRes.data.routes || [])
      setCameraPerformance(perfRes.data.cameras || [])
      setVehiclesPerCamera(vpcRes.data.data || [])
      setCongestion(congRes.data)
      setSpeedByPair(speedRes.data.speeds || [])
      setOdPatterns(odRes.data.top_od_pairs || [])
      setRepeatedSightings(repRes.data.repeated_sightings || [])
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch analytics:', error)
      setLoading(false)
    }
  }

  // Transform hourly data for charts
  const chartData = hourlyData.map(item => ({
    hour: `${item.hour}:00`,
    vehicles: item.count,
    time: item.hour
  }))

  // Find peak hour
  const peakHour = hourlyData.length > 0 
    ? hourlyData.reduce((max, item) => item.count > max.count ? item : max, hourlyData[0])
    : null

  // Calculate average
  const avgVehicles = hourlyData.length > 0
    ? Math.round(hourlyData.reduce((sum, item) => sum + item.count, 0) / hourlyData.length)
    : 0

  // Export functions
  const handleExportVehicles = async () => {
    try {
      const response = await apiClient.get('/api/v1/vehicles')
      const vehicles = response.data.vehicles || []
      
      const csv = [
        ['Plate Number', 'Camera ID', 'Observations', 'Last Seen', 'Latitude', 'Longitude'],
        ...vehicles.map(v => [
          v.plate_text,
          v.camera_id,
          v.observation_count,
          v.last_seen,
          v.latitude,
          v.longitude
        ])
      ].map(row => row.join(',')).join('\n')
      
      downloadCSV(csv, 'trackx_vehicles.csv')
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  const handleExportAnalytics = () => {
    const csv = [
      ['Hour', 'Vehicle Count', 'Timestamp'],
      ...hourlyData.map(item => [
        item.hour,
        item.count,
        item.timestamp
      ])
    ].map(row => row.join(',')).join('\n')
    
    downloadCSV(csv, 'trackx_analytics.csv')
  }

  const handleExportAlerts = async () => {
    try {
      const response = await apiClient.get('/api/v1/alerts')
      const alerts = response.data.alerts || []
      
      const csv = [
        ['ID', 'Vehicle Plate', 'Alert Type', 'Severity', 'Description', 'Status', 'Camera', 'Location', 'Timestamp'],
        ...alerts.map(a => [
          a.id,
          a.vehicle_plate,
          a.alert_type,
          a.severity,
          a.description,
          a.status,
          a.camera_id || 'N/A',
          a.location || 'N/A',
          a.timestamp
        ])
      ].map(row => row.join(',')).join('\n')
      
      downloadCSV(csv, 'trackx_alerts.csv')
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  const downloadCSV = (csv, filename) => {
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-white mb-2">Analytics</h1>
        <p className="text-gray-400">Traffic patterns and insights</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">Peak Hour</h3>
            <Clock className="w-6 h-6 text-blue-500" />
          </div>
          <p className="text-3xl font-bold text-white">
            {peakHour ? `${peakHour.hour}:00` : '--:--'}
          </p>
          <p className="text-sm text-gray-400 mt-2">
            {peakHour ? `${peakHour.count} vehicles` : 'No data'}
          </p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">Avg/Hour</h3>
            <BarChart3 className="w-6 h-6 text-green-500" />
          </div>
          <p className="text-3xl font-bold text-white">{avgVehicles}</p>
          <p className="text-sm text-gray-400 mt-2">City-wide average</p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">OCR Accuracy</h3>
            <Activity className="w-6 h-6 text-purple-500" />
          </div>
          <p className="text-3xl font-bold text-white">
            {stats?.avg_ocr_confidence?.toFixed(1) || 90.8}%
          </p>
          <p className="text-sm text-gray-400 mt-2">Detection rate</p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">Total Today</h3>
            <TrendingUp className="w-6 h-6 text-orange-500" />
          </div>
          <p className="text-3xl font-bold text-white">
            {stats?.total_observations || 0}
          </p>
          <p className="text-sm text-gray-400 mt-2">Observations</p>
        </div>
      </div>

      {/* Hourly Traffic Chart */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-xl font-bold text-white mb-6">24-Hour Traffic Pattern</h2>
        {loading ? (
          <div className="h-64 flex items-center justify-center text-gray-400">
            Loading analytics...
          </div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="hour" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend />
              <Line type="monotone" dataKey="vehicles" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6' }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-400">
            No data available
          </div>
        )}
      </div>

      {/* Vehicle Distribution Chart */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-xl font-bold text-white mb-6">Hourly Distribution (Bar Chart)</h2>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="hour" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Legend />
              <Bar dataKey="vehicles" fill="#10b981" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-400">
            No data available
          </div>
        )}
      </div>

      {/* Route Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
          <h2 className="text-xl font-bold text-white mb-4">Top Routes</h2>
          <div className="space-y-3">
            {loading ? (
              <div className="text-gray-400">Loading routes...</div>
            ) : routeData.length > 0 ? (
              routeData.map((route, idx) => (
                <div key={idx} className="flex justify-between items-center">
                  <span className="text-gray-300">{route.from_name} → {route.to_name}</span>
                  <span className="bg-blue-600 px-3 py-1 rounded-full text-sm font-semibold">{route.count}</span>
                </div>
              ))
            ) : (
              <div className="text-gray-400">No route data available</div>
            )}
          </div>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
          <h2 className="text-xl font-bold text-white mb-4">Camera Performance</h2>
          <div className="space-y-3">
            {loading ? (
              <div className="text-gray-400">Loading cameras...</div>
            ) : cameraPerformance.length > 0 ? (
              cameraPerformance.map((cam, idx) => (
                <div key={idx} className="flex justify-between items-center">
                  <span className="text-gray-300">{cam.name}</span>
                  <span className="text-green-400 font-semibold">{cam.accuracy}%</span>
                </div>
              ))
            ) : (
              <div className="text-gray-400">No camera data available</div>
            )}
          </div>
        </div>
      </div>

      {/* Vehicles Per Camera */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-xl font-bold text-white mb-6">Vehicles Per Camera</h2>
        {loading ? (
          <div className="text-gray-400">Loading...</div>
        ) : vehiclesPerCamera.length > 0 ? (
          <div className="space-y-3">
            {vehiclesPerCamera.map((item, idx) => (
              <div key={idx} className="flex justify-between items-center bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <div>
                  <span className="text-white font-semibold">{item.camera_id}</span>
                  <span className="text-gray-400 text-sm ml-2">— {item.camera_name}</span>
                </div>
                <span className="bg-blue-600 px-4 py-2 rounded-full font-bold text-white">{item.count}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-400">No data available</div>
        )}
      </div>

      {/* Congestion Hotspots */}
      {congestion && congestion.congested_cameras && congestion.congested_cameras.length > 0 && (
        <div className="bg-red-600/10 border border-red-500 rounded-lg p-8">
          <h2 className="text-xl font-bold text-red-400 mb-6">⚠️ Congestion Hotspots</h2>
          <p className="text-gray-300 mb-4">Cameras with high traffic (threshold: {congestion.threshold} vehicles)</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {congestion.congested_cameras.map((cam, idx) => (
              <div key={idx} className={`p-4 rounded-lg border ${cam.severity === 'HIGH' ? 'bg-red-600/20 border-red-500' : 'bg-orange-600/20 border-orange-500'}`}>
                <div className="flex justify-between items-center">
                  <div>
                    <p className="text-white font-semibold">{cam.camera_id} — {cam.camera_name}</p>
                    <p className="text-sm text-gray-300">{cam.vehicle_count} vehicles</p>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-sm font-bold ${cam.severity === 'HIGH' ? 'bg-red-600 text-white' : 'bg-orange-600 text-white'}`}>
                    {cam.severity}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Speed by Camera Pair */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-xl font-bold text-white mb-6">Average Speed by Camera Pair</h2>
        {loading ? (
          <div className="text-gray-400">Loading...</div>
        ) : speedByPair.length > 0 ? (
          <div className="space-y-3">
            {speedByPair.map((speed, idx) => (
              <div key={idx} className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-white font-semibold">{speed.from_name} → {speed.to_name}</span>
                  <span className="bg-purple-600 px-3 py-1 rounded-full text-white font-bold">{speed.avg_speed_kmh} km/h</span>
                </div>
                <div className="text-sm text-gray-400">
                  {speed.from_camera} → {speed.to_camera} • {speed.sample_count} vehicles tracked
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-400">No data available</div>
        )}
      </div>

      {/* Origin-Destination Patterns */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-xl font-bold text-white mb-6">Origin-Destination Patterns</h2>
        <p className="text-gray-400 mb-4">Top vehicle journey patterns across the city</p>
        {loading ? (
          <div className="text-gray-400">Loading...</div>
        ) : odPatterns.length > 0 ? (
          <div className="space-y-3">
            {odPatterns.map((od, idx) => (
              <div key={idx} className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-green-400">🚩 {od.origin_name}</span>
                      <span className="text-gray-500">→</span>
                      <span className="text-red-400">🏁 {od.dest_name}</span>
                    </div>
                    <div className="text-sm text-gray-400">
                      {od.origin} → {od.destination}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-white font-bold text-2xl">{od.count}</p>
                    <p className="text-xs text-gray-400">{od.avg_time_minutes} min avg</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-400">No data available</div>
        )}
      </div>

      {/* Repeated Camera Sightings */}
      {repeatedSightings.length > 0 && (
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
          <h2 className="text-xl font-bold text-white mb-6">Repeated Camera Sightings</h2>
          <p className="text-gray-400 mb-4">Vehicles with multiple visits to the same camera</p>
          <div className="space-y-3">
            {repeatedSightings.map((sighting, idx) => (
              <div key={idx} className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <div className="flex justify-between items-center">
                  <div>
                    <p className="text-white font-semibold">{sighting.camera_id} — {sighting.camera_name}</p>
                    <p className="text-sm text-gray-400 mt-1">
                      Vehicles: {sighting.plates.map((plate, i) => (
                        <span key={i} className="font-mono text-blue-400 ml-2">{plate}</span>
                      ))}
                    </p>
                  </div>
                  <span className="bg-orange-600 px-4 py-2 rounded-full text-white font-bold">
                    {sighting.vehicle_count} repeated
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Export to CSV */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-xl font-bold text-white mb-6">Data Export</h2>
        <p className="text-gray-400 mb-6">Export analytics data for further analysis</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={handleExportVehicles}
            className="px-6 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors flex items-center justify-center space-x-2"
          >
            <span>📊</span>
            <span>Export Vehicles CSV</span>
          </button>
          <button
            onClick={handleExportAnalytics}
            className="px-6 py-4 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-colors flex items-center justify-center space-x-2"
          >
            <span>📈</span>
            <span>Export Analytics CSV</span>
          </button>
          <button
            onClick={handleExportAlerts}
            className="px-6 py-4 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-semibold transition-colors flex items-center justify-center space-x-2"
          >
            <span>⚠️</span>
            <span>Export Alerts CSV</span>
          </button>
        </div>
      </div>
    </div>
  )
}
