import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../App'
import { ArrowLeft, AlertTriangle, MapPin, Clock, Camera, TrendingUp, Shield } from 'lucide-react'
import MapView from '../components/MapView'

export default function VehicleDetails() {
  const { plate } = useParams()
  const navigate = useNavigate()
  const [details, setDetails] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (plate) {
      fetchVehicleDetails()
    }
  }, [plate])

  const fetchVehicleDetails = async () => {
    try {
      const response = await apiClient.get(`/api/v1/vehicles/${plate}/details`)
      setDetails(response.data)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch vehicle details:', error)
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-white text-lg">Loading vehicle details...</p>
        </div>
      </div>
    )
  }

  if (!details || details.error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <p className="text-white text-lg mb-4">Vehicle not found</p>
          <button
            onClick={() => navigate('/tracking')}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Back to Tracking
          </button>
        </div>
      </div>
    )
  }

  const getRiskColor = (level) => {
    switch (level) {
      case 'CRITICAL': return 'text-red-400 bg-red-600/20 border-red-500'
      case 'HIGH': return 'text-orange-400 bg-orange-600/20 border-orange-500'
      case 'MEDIUM': return 'text-yellow-400 bg-yellow-600/20 border-yellow-500'
      default: return 'text-green-400 bg-green-600/20 border-green-500'
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/tracking')}
            className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-6 h-6 text-white" />
          </button>
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">Vehicle Intelligence Report</h1>
            <p className="text-gray-400">Complete tracking and risk analysis</p>
          </div>
        </div>
        <div className={`px-6 py-3 rounded-lg border ${getRiskColor(details.risk_level)}`}>
          <div className="flex items-center space-x-2">
            <Shield className="w-5 h-5" />
            <span className="font-bold">{details.risk_level}</span>
          </div>
        </div>
      </div>

      {/* Plate Number Hero */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-8 text-center">
        <p className="text-white/80 text-sm mb-2">LICENSE PLATE</p>
        <p className="text-6xl font-bold text-white tracking-wider font-mono">{details.plate}</p>
        <p className="text-white/80 text-sm mt-2">{details.state} • Registered {details.registration_year}</p>
      </div>

      {/* Key Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 text-sm">First Seen</h3>
            <Clock className="w-5 h-5 text-blue-500" />
          </div>
          <p className="text-2xl font-bold text-white">{new Date(details.first_seen).toLocaleString()}</p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 text-sm">Last Seen</h3>
            <Clock className="w-5 h-5 text-green-500" />
          </div>
          <p className="text-2xl font-bold text-white">{new Date(details.last_seen).toLocaleString()}</p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 text-sm">Cameras Visited</h3>
            <Camera className="w-5 h-5 text-purple-500" />
          </div>
          <p className="text-2xl font-bold text-white">{details.camera_count}</p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 text-sm">Risk Score</h3>
            <TrendingUp className="w-5 h-5 text-red-500" />
          </div>
          <p className="text-2xl font-bold text-white">{details.risk_score}/100</p>
        </div>
      </div>

      {/* Trajectory Map */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center space-x-2">
          <MapPin className="w-6 h-6 text-blue-500" />
          <span>Complete Trajectory</span>
        </h2>
        <MapView searchPlate={details.plate} />
      </div>

      {/* Alerts */}
      {details.alerts && details.alerts.length > 0 && (
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
          <h2 className="text-2xl font-bold text-white mb-6 flex items-center space-x-2">
            <AlertTriangle className="w-6 h-6 text-red-500" />
            <span>Active Alerts ({details.alert_count})</span>
          </h2>
          <div className="space-y-4">
            {details.alerts.map((alert, idx) => (
              <div
                key={idx}
                className="bg-slate-900/50 border border-slate-700 rounded-lg p-6 hover:bg-slate-900 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className={`px-3 py-1 rounded-full text-sm font-semibold border ${getRiskColor(alert.severity.toUpperCase())}`}>
                        {alert.severity.toUpperCase()}
                      </span>
                      <span className="text-white font-semibold">{alert.alert_type.replace('_', ' ').toUpperCase()}</span>
                    </div>
                    <p className="text-gray-300 mb-2">{alert.description}</p>
                    <div className="flex items-center space-x-4 text-sm text-gray-400">
                      <span>📍 {alert.location}</span>
                      <span>🕐 {new Date(alert.timestamp).toLocaleString()}</span>
                    </div>
                  </div>
                  <span className={`ml-4 px-3 py-1 rounded-full text-sm ${alert.status === 'active' ? 'bg-red-600/20 text-red-400' : 'bg-green-600/20 text-green-400'}`}>
                    {alert.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Observation Timeline */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center space-x-2">
          <Camera className="w-6 h-6 text-green-500" />
          <span>Camera Observations ({details.total_observations})</span>
        </h2>
        <div className="space-y-3">
          {details.observations.map((obs, idx) => (
            <div key={idx} className="flex items-center justify-between bg-slate-900/50 border border-slate-700 rounded-lg p-4">
              <div className="flex items-center space-x-4">
                <Camera className="w-5 h-5 text-blue-400" />
                <div>
                  <p className="text-white font-semibold">{obs.camera_id}</p>
                  <p className="text-sm text-gray-400">{new Date(obs.last_seen).toLocaleString()}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-gray-400 text-sm">📍 {obs.latitude.toFixed(4)}°, {obs.longitude.toFixed(4)}°</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Status Summary */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
        <h2 className="text-2xl font-bold text-white mb-6">Vehicle Status Summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-gray-400 mb-3">Vehicle Information</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-400">Type:</span>
                <span className="text-white font-semibold">{details.vehicle_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">State:</span>
                <span className="text-white font-semibold">{details.state}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Registration:</span>
                <span className="text-white font-semibold">{details.registration_year}</span>
              </div>
            </div>
          </div>
          <div>
            <h3 className="text-gray-400 mb-3">Security Status</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-400">Blacklist Status:</span>
                <span className={`font-semibold ${details.blacklist_status === 'BLACKLISTED' ? 'text-red-400' : 'text-green-400'}`}>
                  {details.blacklist_status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Risk Level:</span>
                <span className={`font-semibold ${details.risk_level === 'CRITICAL' ? 'text-red-400' : details.risk_level === 'HIGH' ? 'text-orange-400' : 'text-green-400'}`}>
                  {details.risk_level}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Active Alerts:</span>
                <span className="text-white font-semibold">{details.alert_count}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
