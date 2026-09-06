// frontend/src/pages/AlertsPage.tsx

import React, { useState, useEffect } from 'react'
import { api } from '@/services/api'
import { AlertTriangle, Bell } from 'lucide-react'
import type { Alert } from '@/types'
import { toast } from 'react-toastify'

const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState('ALL')

  const fetchAlerts = async () => {
    try {
      const data = await api.getAlerts({ limit: 100 })
      setAlerts(data)
    } catch (error) {
      console.error('Failed to fetch alerts:', error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchAlerts()
  }, [])

  const handleResolve = async (alertId: string) => {
    try {
      await api.resolveAlert(alertId)
      toast.success('Alert resolved')
      fetchAlerts()
    } catch (error) {
      toast.error('Failed to resolve alert')
    }
  }

  const handleAcknowledge = async (alertId: string) => {
    try {
      await api.acknowledgeAlert(alertId)
      toast.success('Alert acknowledged')
      fetchAlerts()
    } catch (error) {
      toast.error('Failed to acknowledge alert')
    }
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'HIGH':
        return 'bg-red-500/20 text-red-400'
      case 'MEDIUM':
        return 'bg-yellow-500/20 text-yellow-400'
      default:
        return 'bg-green-500/20 text-green-400'
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'OPEN':
        return 'bg-red-500/20 text-red-400'
      case 'ACKNOWLEDGED':
        return 'bg-yellow-500/20 text-yellow-400'
      case 'RESOLVED':
        return 'bg-green-500/20 text-green-400'
      default:
        return 'bg-gray-500/20 text-gray-400'
    }
  }

  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'ALL') return true
    return alert.status === filter
  })

  if (isLoading) {
    return <div className="flex justify-center items-center h-full">Loading...</div>
  }

  return (
    <div className="space-y-6">
      {/* Demo Mode Notice Banner */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center justify-between text-amber-300 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span><b>DEMO MODE (SIH-26127):</b> Automated alerts generated for blacklisted plates, impossible speeds, and route anomalies.</span>
        </div>
        <span className="text-xs bg-amber-500/20 px-2 py-0.5 rounded font-mono">AUTOMATED INCIDENTS</span>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Alert Operations Center</h1>
        
        {/* Filters */}
        <div className="flex gap-2">
          {['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'].map(status => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filter === status
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                  : 'bg-surface-light text-muted border border-border hover:text-white'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-6 text-center">
          <p className="text-3xl font-bold text-red-400">{alerts.filter(a => a.status === 'OPEN').length}</p>
          <p className="text-sm text-muted mt-1">Open Alerts</p>
        </div>
        <div className="card p-6 text-center">
          <p className="text-3xl font-bold text-yellow-400">{alerts.filter(a => a.status === 'ACKNOWLEDGED').length}</p>
          <p className="text-sm text-muted mt-1">Acknowledged</p>
        </div>
        <div className="card p-6 text-center">
          <p className="text-3xl font-bold text-green-400">{alerts.filter(a => a.status === 'RESOLVED').length}</p>
          <p className="text-sm text-muted mt-1">Resolved</p>
        </div>
      </div>

      {/* Alerts List */}
      <div className="space-y-4">
        {filteredAlerts.length === 0 ? (
          <div className="card p-12 text-center">
            <Bell size={48} className="mx-auto text-muted mb-4" />
            <p className="text-muted">No alerts found</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => (
            <div 
              key={alert.alert_id}
              className="card p-6 flex items-start gap-4 hover:border-blue-500/50 transition-colors cursor-pointer"
            >
              {/* Alert Icon */}
              <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                alert.severity === 'HIGH' 
                  ? 'bg-red-500/20' 
                  : alert.severity === 'MEDIUM'
                  ? 'bg-yellow-500/20'
                  : 'bg-green-500/20'
              }`}>
                <AlertTriangle size={24} className={
                  alert.severity === 'HIGH' ? 'text-red-400' : alert.severity === 'MEDIUM' ? 'text-yellow-400' : 'text-green-400'
                } />
              </div>

              {/* Alert Details */}
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-bold text-white">{alert.alert_type}</h3>
                  <div className="flex gap-2">
                    <span className={`text-xs px-2 py-1 rounded-full ${getSeverityBadge(alert.severity)}`}>
                      {alert.severity}
                    </span>
                    <span className={`text-xs px-2 py-1 rounded-full ${getStatusBadge(alert.status)}`}>
                      {alert.status}
                    </span>
                  </div>
                </div>
                
                <p className="font-mono text-white text-lg">{alert.plate_text}</p>
                <p className="text-sm text-muted mt-1">{alert.description}</p>
                <p className="text-xs text-muted mt-2">
                  {alert.camera_id && `${alert.camera_id} · `}
                  {alert.timestamp}
                </p>
              </div>

              {/* Actions */}
              <div className="flex flex-col gap-2">
                {alert.status === 'OPEN' && (
                  <>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleAcknowledge(alert.alert_id) }}
                      className="px-3 py-1 text-xs rounded-lg bg-surface-light border border-border text-yellow-400 hover:bg-yellow-500/10"
                    >
                      Acknowledge
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleResolve(alert.alert_id) }}
                      className="px-3 py-1 text-xs rounded-lg bg-surface-light border border-border text-green-400 hover:bg-green-500/10"
                    >
                      Resolve
                    </button>
                  </>
                )}
                {alert.status === 'ACKNOWLEDGED' && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleResolve(alert.alert_id) }}
                    className="px-3 py-1 text-xs rounded-lg bg-surface-light border border-border text-green-400 hover:bg-green-500/10"
                  >
                    Resolve
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default AlertsPage
