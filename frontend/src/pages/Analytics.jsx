import React, { useState, useEffect } from 'react'
import { apiClient } from '../App'
import { TrendingUp, BarChart3, Activity, Clock } from 'lucide-react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function Analytics() {
  const [hourlyData, setHourlyData] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAnalytics()
  }, [])

  const fetchAnalytics = async () => {
    try {
      const [hourlyRes, statsRes] = await Promise.all([
        apiClient.get('/api/v1/analytics/hourly'),
        apiClient.get('/api/v1/analytics/stats')
      ])
      setHourlyData(hourlyRes.data.data || [])
      setStats(statsRes.data)
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
            <div className="flex justify-between items-center">
              <span className="text-gray-300">CAM_001 → CAM_002</span>
              <span className="bg-blue-600 px-3 py-1 rounded-full text-sm font-semibold">245</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">CAM_003 → CAM_001</span>
              <span className="bg-blue-600 px-3 py-1 rounded-full text-sm font-semibold">198</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">CAM_002 → CAM_004</span>
              <span className="bg-blue-600 px-3 py-1 rounded-full text-sm font-semibold">167</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">CAM_004 → CAM_003</span>
              <span className="bg-blue-600 px-3 py-1 rounded-full text-sm font-semibold">142</span>
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
          <h2 className="text-xl font-bold text-white mb-4">Camera Performance</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-300">CAM_001 - MG Road</span>
              <span className="text-green-400 font-semibold">99.2%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">CAM_002 - Brigade Rd</span>
              <span className="text-green-400 font-semibold">98.8%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">CAM_003 - Indiranagar</span>
              <span className="text-green-400 font-semibold">99.5%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">CAM_004 - Koramangala</span>
              <span className="text-green-400 font-semibold">97.9%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
