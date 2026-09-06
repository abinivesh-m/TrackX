import React, { useState, useEffect } from 'react'
import { apiClient } from '../App'
import { AlertCircle, CheckCircle, Clock } from 'lucide-react'

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAlerts()
  }, [])

  const fetchAlerts = async () => {
    try {
      const response = await apiClient.get('/api/v1/alerts')
      setAlerts(response.data.alerts || [])
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch alerts:', error)
      setLoading(false)
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'active':
        return <AlertCircle className="w-5 h-5 text-red-500" />
      case 'resolved':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      default:
        return <Clock className="w-5 h-5 text-yellow-500" />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'active':
        return 'bg-red-600/20 text-red-300 border-red-500'
      case 'resolved':
        return 'bg-green-600/20 text-green-300 border-green-500'
      default:
        return 'bg-yellow-600/20 text-yellow-300 border-yellow-500'
    }
  }

  // Calculate active and resolved counts
  const activeCount = alerts.filter(a => a.status === 'active').length
  const resolvedCount = alerts.filter(a => a.status === 'resolved').length

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-white mb-2">Alerts</h1>
        <p className="text-gray-400">System and vehicle tracking alerts</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm mb-2">Active Alerts</p>
              <p className="text-3xl font-bold text-red-400">{activeCount}</p>
            </div>
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm mb-2">Resolved</p>
              <p className="text-3xl font-bold text-green-400">{resolvedCount}</p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm mb-2">Total Alerts</p>
              <p className="text-3xl font-bold text-blue-400">{alerts.length}</p>
            </div>
            <Clock className="w-8 h-8 text-blue-500" />
          </div>
        </div>
      </div>

      {/* Alerts Table */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-900/50">
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Type</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Description</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Status</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Created</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="4" className="px-6 py-8 text-center text-gray-400">
                    Loading alerts...
                  </td>
                </tr>
              ) : alerts.length === 0 ? (
                <tr>
                  <td colSpan="4" className="px-6 py-8 text-center text-gray-400">
                    <div className="flex flex-col items-center space-y-2">
                      <CheckCircle className="w-8 h-8 text-green-500" />
                      <span>No active alerts</span>
                    </div>
                  </td>
                </tr>
              ) : (
                alerts.map((alert, idx) => (
                  <tr key={idx} className="border-b border-slate-700 hover:bg-slate-800/50 transition-colors">
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center space-x-2">
                        {getStatusIcon(alert.status)}
                        <span className="text-white font-semibold">{alert.alert_type}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-300">
                      {alert.description}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${getStatusColor(alert.status)}`}>
                        {alert.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-300 text-sm">
                      {new Date(alert.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Info */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-xl font-bold text-white mb-4">Alert System Status</h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Alert Engine</span>
            <span className="text-green-400 font-semibold">✅ Running</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Alert Processing</span>
            <span className="text-green-400 font-semibold">✅ Enabled</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Notifications</span>
            <span className="text-green-400 font-semibold">✅ Configured</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">System Health</span>
            <span className="text-green-400 font-semibold">✅ Healthy</span>
          </div>
        </div>
      </div>
    </div>
  )
}
