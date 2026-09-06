import React, { useState, useEffect, Fragment } from 'react'
import { apiClient } from '../App'
import { AlertCircle, CheckCircle, Clock } from 'lucide-react'

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedAlert, setExpandedAlert] = useState(null)
  const [activeTab, setActiveTab] = useState('alerts')
  const [blacklist, setBlacklist] = useState([])
  const [newPlate, setNewPlate] = useState('')
  const [newReason, setNewReason] = useState('')

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

  const handleAddToBlacklist = () => {
    if (!newPlate || !newReason) return
    
    const newEntry = {
      plate: newPlate,
      reason: newReason,
      added: new Date().toLocaleString()
    }
    
    setBlacklist([...blacklist, newEntry])
    setNewPlate('')
    setNewReason('')
  }

  const handleRemoveFromBlacklist = (plate) => {
    setBlacklist(blacklist.filter(item => item.plate !== plate))
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
  
  // Sort alerts by severity (CRITICAL > HIGH > MEDIUM > LOW)
  const severityOrder = { 'critical': 0, 'high': 1, 'medium': 2, 'low': 3 }
  const sortedAlerts = [...alerts].sort((a, b) => 
    severityOrder[a.severity.toLowerCase()] - severityOrder[b.severity.toLowerCase()]
  )
  
  const heroAlert = sortedAlerts.length > 0 ? sortedAlerts[0] : null
  const remainingAlerts = sortedAlerts.slice(1)

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-white mb-2">Alerts</h1>
        <p className="text-gray-400">System and vehicle tracking alerts</p>
      </div>

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-700">
        <button
          onClick={() => setActiveTab('alerts')}
          className={`px-6 py-3 font-semibold transition-colors ${activeTab === 'alerts' ? 'text-white border-b-2 border-blue-500' : 'text-gray-400 hover:text-white'}`}
        >
          Active Alerts
        </button>
        <button
          onClick={() => setActiveTab('blacklist')}
          className={`px-6 py-3 font-semibold transition-colors ${activeTab === 'blacklist' ? 'text-white border-b-2 border-blue-500' : 'text-gray-400 hover:text-white'}`}
        >
          Blacklist Management
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-6 py-3 font-semibold transition-colors ${activeTab === 'history' ? 'text-white border-b-2 border-blue-500' : 'text-gray-400 hover:text-white'}`}
        >
          Alert History
        </button>
      </div>

      {activeTab === 'alerts' && (
        <>

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
        {/* Hero Alert Card */}
        {heroAlert && (
          <div className={`p-8 border-b-4 ${heroAlert.severity === 'critical' ? 'bg-red-900/20 border-red-500' : heroAlert.severity === 'high' ? 'bg-orange-900/20 border-orange-500' : 'bg-yellow-900/20 border-yellow-500'}`}>
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-3">
                  <AlertCircle className="w-8 h-8 text-red-500" />
                  <span className={`px-4 py-2 rounded-full text-lg font-bold border-2 ${heroAlert.severity === 'critical' ? 'bg-red-600 text-white border-red-400' : heroAlert.severity === 'high' ? 'bg-orange-600 text-white border-orange-400' : 'bg-yellow-600 text-white border-yellow-400'}`}>
                    {heroAlert.severity.toUpperCase()}
                  </span>
                  <span className="text-2xl font-bold text-white">{heroAlert.alert_type.replace(/_/g, ' ').toUpperCase()}</span>
                </div>
                <p className="text-xl text-gray-200 mb-3">{heroAlert.description}</p>
                <div className="flex items-center space-x-6 text-gray-300">
                  <span className="flex items-center space-x-2">
                    <span className="font-semibold">Vehicle:</span>
                    <span className="font-mono bg-slate-800 px-3 py-1 rounded">{heroAlert.vehicle_plate}</span>
                  </span>
                  <span>📍 {heroAlert.location || 'Unknown'}</span>
                  <span>🕐 {new Date(heroAlert.timestamp).toLocaleString()}</span>
                </div>
              </div>
              <span className={`ml-4 px-4 py-2 rounded-full text-sm font-bold ${heroAlert.status === 'active' ? 'bg-red-600 text-white' : 'bg-green-600 text-white'}`}>
                {heroAlert.status.toUpperCase()}
              </span>
            </div>
            {heroAlert.camera_id && (
              <div className="mt-4 p-4 bg-slate-900/50 rounded-lg">
                <p className="text-sm text-gray-400">Camera: <span className="text-white font-semibold">{heroAlert.camera_id}</span></p>
              </div>
            )}
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-900/50">
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Type</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Description</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Status</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Created</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Details</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="5" className="px-6 py-8 text-center text-gray-400">
                    Loading alerts...
                  </td>
                </tr>
              ) : remainingAlerts.length === 0 && !heroAlert ? (
                <tr>
                  <td colSpan="5" className="px-6 py-8 text-center text-gray-400">
                    <div className="flex flex-col items-center space-y-2">
                      <CheckCircle className="w-8 h-8 text-green-500" />
                      <span>No active alerts</span>
                    </div>
                  </td>
                </tr>
              ) : (
                remainingAlerts.map((alert, idx) => (
                  <React.Fragment key={idx}>
                    <tr className="border-b border-slate-700 hover:bg-slate-800/50 transition-colors">
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
                      <td className="px-6 py-4">
                        <button
                          onClick={() => setExpandedAlert(expandedAlert === alert.id ? null : alert.id)}
                          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm transition-colors"
                        >
                          {expandedAlert === alert.id ? 'Hide' : 'Show'}
                        </button>
                      </td>
                    </tr>
                    {expandedAlert === alert.id && (
                      <tr className="border-b border-slate-700 bg-slate-900/50">
                        <td colSpan="5" className="px-6 py-6">
                          <div className="space-y-4">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                              <div>
                                <p className="text-xs text-gray-400 mb-1">Vehicle Plate</p>
                                <p className="font-mono text-white font-semibold">{alert.vehicle_plate}</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400 mb-1">Severity</p>
                                <p className={`font-bold ${alert.severity === 'critical' ? 'text-red-400' : alert.severity === 'high' ? 'text-orange-400' : 'text-yellow-400'}`}>
                                  {alert.severity.toUpperCase()}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400 mb-1">Camera</p>
                                <p className="text-white">{alert.camera_id || 'N/A'}</p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-400 mb-1">Location</p>
                                <p className="text-white">{alert.location || 'Unknown'}</p>
                              </div>
                            </div>
                            <div>
                              <p className="text-xs text-gray-400 mb-1">Timestamp</p>
                              <p className="text-white">{new Date(alert.timestamp).toLocaleString()}</p>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      </>
      )}

      {activeTab === 'blacklist' && (
        <div className="space-y-6">
          {/* Add to Blacklist */}
          <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
            <h2 className="text-xl font-bold text-white mb-6">Add Vehicle to Blacklist</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <input
                type="text"
                placeholder="License Plate (e.g., TN09XX1234)"
                value={newPlate}
                onChange={(e) => setNewPlate(e.target.value.toUpperCase())}
                className="px-4 py-3 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-500"
              />
              <input
                type="text"
                placeholder="Reason (e.g., Stolen vehicle)"
                value={newReason}
                onChange={(e) => setNewReason(e.target.value)}
                className="px-4 py-3 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-500"
              />
              <button
                onClick={handleAddToBlacklist}
                className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition-colors"
              >
                Add to Blacklist
              </button>
            </div>
          </div>

          {/* Blacklist Table */}
          <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg overflow-hidden">
            <div className="p-6 border-b border-slate-700">
              <h2 className="text-xl font-bold text-white">Blacklisted Vehicles</h2>
              <p className="text-gray-400 text-sm mt-1">{blacklist.length} vehicle(s) on watchlist</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700 bg-slate-900/50">
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Plate</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Reason</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Added</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {blacklist.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="px-6 py-8 text-center text-gray-400">
                        No vehicles on blacklist
                      </td>
                    </tr>
                  ) : (
                    blacklist.map((item, idx) => (
                      <tr key={idx} className="border-b border-slate-700 hover:bg-slate-800/50 transition-colors">
                        <td className="px-6 py-4">
                          <span className="font-mono font-bold text-red-400">{item.plate}</span>
                        </td>
                        <td className="px-6 py-4 text-gray-300">{item.reason}</td>
                        <td className="px-6 py-4 text-gray-300 text-sm">{item.added}</td>
                        <td className="px-6 py-4">
                          <button
                            onClick={() => handleRemoveFromBlacklist(item.plate)}
                            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded text-sm transition-colors"
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
          <h2 className="text-xl font-bold text-white mb-6">Alert History</h2>
          <div className="space-y-4">
            {alerts.filter(a => a.status === 'resolved').length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <CheckCircle className="w-16 h-16 mx-auto mb-4 text-green-500" />
                <p>No resolved alerts in history</p>
              </div>
            ) : (
              alerts.filter(a => a.status === 'resolved').map((alert, idx) => (
                <div key={idx} className="bg-slate-900/50 border border-slate-700 rounded-lg p-6">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <span className="inline-flex items-center space-x-2 text-white font-semibold mb-2">
                        <CheckCircle className="w-5 h-5 text-green-500" />
                        <span>{alert.alert_type.replace(/_/g, ' ').toUpperCase()}</span>
                      </span>
                      <p className="text-gray-300 mt-2">{alert.description}</p>
                    </div>
                    <span className="bg-green-600/20 text-green-400 px-3 py-1 rounded-full text-sm border border-green-500">
                      RESOLVED
                    </span>
                  </div>
                  <div className="flex items-center space-x-6 text-sm text-gray-400">
                    <span>Vehicle: <span className="font-mono text-white">{alert.vehicle_plate}</span></span>
                    <span>📍 {alert.location || 'Unknown'}</span>
                    <span>🕐 {new Date(alert.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

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
