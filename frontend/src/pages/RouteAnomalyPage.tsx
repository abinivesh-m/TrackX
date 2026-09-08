// frontend/src/pages/RouteAnomalyPage.tsx

import React, { useState, useEffect } from 'react'
import { api } from '@/services/api'
import { useAuth } from '@/contexts/AuthContext'
import { AlertTriangle, Shield, Search, Clock, MapPin, Navigation, XCircle } from 'lucide-react'
import type { RouteAnomaly } from '@/types'
import { toast } from 'react-toastify'

const RouteAnomalyPage: React.FC = () => {
  const { user } = useAuth()
  const [anomalies, setAnomalies] = useState<RouteAnomaly[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedAnomaly, setSelectedAnomaly] = useState<RouteAnomaly | null>(null)
  const [searchPlate, setSearchPlate] = useState('')
  const [filterSeverity, setFilterSeverity] = useState<string>('')
  const [filterStatus, setFilterStatus] = useState<string>('')

  useEffect(() => {
    loadAnomalies()
  }, [filterSeverity, filterStatus])

  const loadAnomalies = async () => {
    setIsLoading(true)
    try {
      const data = await api.getRouteAnomalies({
        plate: searchPlate || undefined,
        severity: filterSeverity || undefined,
        status: filterStatus || undefined,
        limit: 50
      })
      setAnomalies(data)
    } catch (error) {
      console.error('Failed to load anomalies:', error)
      toast.error('Failed to load route anomalies')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault()
    loadAnomalies()
  }

  const handleAnalyzeVehicle = async (plate: string) => {
    try {
      const result = await api.analyzeVehicleRoute(plate)
      toast.success(`Analysis complete: ${result.anomalies_detected} anomalies detected`)
      loadAnomalies()
    } catch (error) {
      console.error('Analysis failed:', error)
      toast.error('Route analysis failed')
    }
  }

  const handleUpdateStatus = async (anomaly: RouteAnomaly, newStatus: string) => {
    try {
      await api.updateAnomalyStatus(
        anomaly.anomaly_id,
        newStatus,
        // Was hardcoded to the literal string 'current_user' regardless of
        // who was actually logged in - every investigation note falsely
        // attributed the action to a fake username. Uses the real signed-in
        // user now (falls back only if auth context is somehow unavailable).
        user?.username || 'unknown_user',
        'Investigated via dashboard'
      )
      toast.success(`Anomaly status updated to ${newStatus}`)
      loadAnomalies()
    } catch (error) {
      console.error('Status update failed:', error)
      toast.error('Failed to update anomaly status')
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'HIGH': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      case 'MEDIUM': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'LOW': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'OPEN': return 'bg-red-500/20 text-red-400'
      case 'UNDER_INVESTIGATION': return 'bg-yellow-500/20 text-yellow-400'
      case 'RESOLVED': return 'bg-green-500/20 text-green-400'
      case 'FALSE_POSITIVE': return 'bg-gray-500/20 text-gray-400'
      default: return 'bg-gray-500/20 text-gray-400'
    }
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A'
    const date = new Date(dateString)
    return date.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="space-y-6">
      {/* Demo Mode Notice Banner */}
      <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30 rounded-lg p-3 flex items-center justify-between text-purple-300 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
          <span><b>VEHICLE INTELLIGENCE GRAPH:</b> On-demand suspicious route detection with multi-factor anomaly scoring.</span>
        </div>
        <span className="text-xs bg-purple-500/20 px-2 py-0.5 rounded font-mono border border-purple-500/30">ROUTE ANOMALY</span>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Shield className="text-purple-400" />
          Route Anomaly Detection
        </h1>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">{anomalies.length} anomalies detected</span>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="card p-6">
        <div className="flex flex-col md:flex-row gap-4">
          <form onSubmit={handleSearch} className="flex-1 flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={18} />
              <input
                type="text"
                placeholder="Search by vehicle plate..."
                value={searchPlate}
                onChange={(e) => setSearchPlate(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-white"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors"
            >
              Search
            </button>
          </form>

          <div className="flex gap-2">
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="px-4 py-2 rounded-lg bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-white"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>

            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-4 py-2 rounded-lg bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-white"
            >
              <option value="">All Status</option>
              <option value="OPEN">Open</option>
              <option value="UNDER_INVESTIGATION">Under Investigation</option>
              <option value="RESOLVED">Resolved</option>
              <option value="FALSE_POSITIVE">False Positive</option>
            </select>
          </div>
        </div>
      </div>

      {/* Vehicle Analysis */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <Navigation className="text-blue-400" />
          Analyze Vehicle Route
        </h3>
        <div className="flex gap-4">
          <input
            type="text"
            placeholder="Enter plate to analyze (e.g., TN38AB1234)"
            className="flex-1 px-4 py-2 rounded-lg bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-white"
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleAnalyzeVehicle((e.target as HTMLInputElement).value)
              }
            }}
          />
          <button
            onClick={() => {
              const input = document.querySelector('input[placeholder*="Enter plate to analyze"]') as HTMLInputElement
              if (input?.value) handleAnalyzeVehicle(input.value)
            }}
            className="px-6 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-600 text-white font-bold hover:opacity-90 transition-opacity"
          >
            Analyze Route
          </button>
        </div>
      </div>

      {/* Anomalies List */}
      {isLoading ? (
        <div className="text-center py-8 text-muted">Loading anomalies...</div>
      ) : anomalies.length === 0 ? (
        <div className="card p-8 text-center">
          <AlertTriangle size={48} className="mx-auto mb-4 text-muted" />
          <p className="text-muted">No route anomalies detected</p>
          <p className="text-sm text-muted mt-2">Analyze vehicle routes to detect suspicious movements</p>
        </div>
      ) : (
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-4">Detected Anomalies</h3>
          <div className="space-y-4">
            {anomalies.map((anomaly) => (
              <div
                key={anomaly.anomaly_id}
                className="p-4 rounded-lg bg-surface-light border border-border hover:border-purple-500/30 transition-all cursor-pointer"
                onClick={() => setSelectedAnomaly(anomaly)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono font-bold text-white">{anomaly.plate}</span>
                      <span className={`text-xs px-2 py-1 rounded-full border ${getSeverityColor(anomaly.severity)}`}>
                        {anomaly.severity}
                      </span>
                      <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(anomaly.status)}`}>
                        {anomaly.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-sm text-muted mb-2">
                      <div className="flex items-center gap-1">
                        <MapPin size={14} />
                        {anomaly.from_camera} → {anomaly.to_camera}
                      </div>
                      <div className="flex items-center gap-1">
                        <Clock size={14} />
                        {formatDate(anomaly.timestamp)}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-muted">Anomaly Score:</span>
                      <span className="font-bold text-white">{anomaly.anomaly_score.toFixed(1)}/100</span>
                      <span className="text-muted">Type:</span>
                      <span className="text-purple-400">{anomaly.anomaly_type}</span>
                    </div>

                    {anomaly.details && (
                      <div className="mt-2 text-xs text-muted space-y-1">
                        {/*
                          route_anomaly.py's add_anomaly() call never sends
                          observed_travel_time or expected_max_time, and
                          sends observed_speed_kmph as null for exactly the
                          "impossible" case (required_speed_kmph == inf) -
                          the most common/dramatic anomaly type. Calling
                          .toFixed() on those unconditionally crashed this
                          whole page to a black screen (no error boundary)
                          the moment such an anomaly rendered. Optional
                          chaining + a fallback keeps it rendering instead.
                        */}
                        {anomaly.details.unexpected_transition && (
                          <div className="flex items-center gap-1 text-red-400">
                            <XCircle size={12} />
                            Unexpected camera transition
                          </div>
                        )}
                        {anomaly.details.impossible_travel_time && (
                          <div className="flex items-center gap-1 text-red-400">
                            <XCircle size={12} />
                            Impossible travel time ({anomaly.details.observed_travel_time?.toFixed(1) ?? '?'}s vs expected {anomaly.details.expected_min_time ?? '?'}-{anomaly.details.expected_max_time ?? '?'}s)
                          </div>
                        )}
                        {anomaly.details.unreasonable_speed && (
                          <div className="flex items-center gap-1 text-orange-400">
                            <AlertTriangle size={12} />
                            Unreasonable speed ({anomaly.details.observed_speed_kmph?.toFixed(1) ?? 'very high'} km/h)
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    {anomaly.status === 'OPEN' && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleUpdateStatus(anomaly, 'UNDER_INVESTIGATION')
                          }}
                          className="px-3 py-1 rounded bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 text-xs"
                        >
                          Investigate
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleUpdateStatus(anomaly, 'FALSE_POSITIVE')
                          }}
                          className="px-3 py-1 rounded bg-gray-500/20 text-gray-400 hover:bg-gray-500/30 text-xs"
                        >
                          False Positive
                        </button>
                      </>
                    )}
                    {anomaly.status === 'UNDER_INVESTIGATION' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleUpdateStatus(anomaly, 'RESOLVED')
                        }}
                        className="px-3 py-1 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30 text-xs"
                      >
                        Resolve
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Anomaly Detail Modal */}
      {selectedAnomaly && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-surface border border-border rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-border">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white">Anomaly Details</h2>
                <button
                  onClick={() => setSelectedAnomaly(null)}
                  className="text-muted hover:text-white"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs text-muted">Vehicle Plate</span>
                  <p className="font-mono font-bold text-white">{selectedAnomaly.plate}</p>
                </div>
                <div>
                  <span className="text-xs text-muted">Anomaly ID</span>
                  <p className="text-white">{selectedAnomaly.anomaly_id}</p>
                </div>
                <div>
                  <span className="text-xs text-muted">Route</span>
                  <p className="text-white">{selectedAnomaly.from_camera} → {selectedAnomaly.to_camera}</p>
                </div>
                <div>
                  <span className="text-xs text-muted">Timestamp</span>
                  <p className="text-white">{formatDate(selectedAnomaly.timestamp)}</p>
                </div>
                <div>
                  <span className="text-xs text-muted">Severity</span>
                  <p className={`font-bold ${getSeverityColor(selectedAnomaly.severity).split(' ')[2]}`}>
                    {selectedAnomaly.severity}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-muted">Status</span>
                  <p className={`font-bold ${getStatusColor(selectedAnomaly.status).split(' ')[2]}`}>
                    {selectedAnomaly.status}
                  </p>
                </div>
              </div>

              {selectedAnomaly.details && (
                <div className="bg-surface-light p-4 rounded-lg">
                  <h3 className="font-bold text-white mb-3">Technical Details</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted">Distance</span>
                      <span className="text-white">{selectedAnomaly.details.distance_km?.toFixed(2) ?? '?'} km</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Observed Travel Time</span>
                      <span className="text-white">{selectedAnomaly.details.observed_travel_time?.toFixed(1) ?? '?'}s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Expected Time Range</span>
                      <span className="text-white">{selectedAnomaly.details.expected_min_time?.toFixed(0) ?? '?'}s - {selectedAnomaly.details.expected_max_time?.toFixed(0) ?? '?'}s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Observed Speed</span>
                      <span className={selectedAnomaly.details.unreasonable_speed ? 'text-red-400 font-bold' : 'text-white'}>
                        {selectedAnomaly.details.observed_speed_kmph?.toFixed(1) ?? 'very high'} km/h
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Anomaly Score</span>
                      <span className="text-purple-400 font-bold">{selectedAnomaly.anomaly_score.toFixed(1)}/100</span>
                    </div>
                  </div>
                </div>
              )}

              {selectedAnomaly.investigated_by && (
                <div>
                  <span className="text-xs text-muted">Investigated By</span>
                  <p className="text-white">{selectedAnomaly.investigated_by}</p>
                </div>
              )}

              {selectedAnomaly.investigation_notes && (
                <div>
                  <span className="text-xs text-muted">Investigation Notes</span>
                  <p className="text-white">{selectedAnomaly.investigation_notes}</p>
                </div>
              )}

              {selectedAnomaly.resolution_notes && (
                <div>
                  <span className="text-xs text-muted">Resolution Notes</span>
                  <p className="text-white">{selectedAnomaly.resolution_notes}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RouteAnomalyPage