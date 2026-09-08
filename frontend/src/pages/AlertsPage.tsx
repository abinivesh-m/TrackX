// frontend/src/pages/AlertsPage.tsx
//
// Alert Operations Center - blacklist/watchlist matches, route anomalies,
// congestion bottlenecks, and camera-offline alerts, each with the real
// evidence the backend actually computed (see backend/app/api/v1/alerts.py
// and intelligence/alerts.py) - not just a type label and a description
// string. Vehicle-scoped alerts link straight into Vehicle Intelligence and
// the trajectory view; camera-scoped alerts (congestion, offline) show the
// camera instead of a fabricated plate.

import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import {
  AlertTriangle, Bell, ShieldAlert, Route, Repeat, Activity, VideoOff,
  ArrowUpRight, Search, ListChecks,
} from 'lucide-react'
import type { Alert, WatchlistEntry } from '@/types'
import { toast } from 'react-toastify'

const ALERT_TYPE_META: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  BLACKLISTED_VEHICLE: { label: 'Watchlist Match', icon: ShieldAlert, color: 'red' },
  SUSPICIOUS_ROUTE: { label: 'Route Anomaly', icon: Route, color: 'orange' },
  REPEATED_CAMERA: { label: 'Repeated Sighting', icon: Repeat, color: 'yellow' },
  CONGESTION_BOTTLENECK: { label: 'Congestion Bottleneck', icon: Activity, color: 'orange' },
  CAMERA_OFFLINE: { label: 'Camera Offline', icon: VideoOff, color: 'gray' },
}

function meta(alertType: string) {
  return ALERT_TYPE_META[alertType] || { label: alertType.replace(/_/g, ' '), icon: AlertTriangle, color: 'gray' }
}

const COLOR_CLASSES: Record<string, { bg: string; text: string; border: string }> = {
  red: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
  orange: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/30' },
  yellow: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  gray: { bg: 'bg-gray-500/20', text: 'text-gray-400', border: 'border-gray-500/30' },
}

function severityBadge(severity: string) {
  switch (severity) {
    case 'HIGH': return 'bg-red-500/20 text-red-400'
    case 'MEDIUM': return 'bg-yellow-500/20 text-yellow-400'
    default: return 'bg-green-500/20 text-green-400'
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'OPEN': return 'bg-red-500/20 text-red-400'
    case 'ACKNOWLEDGED': return 'bg-yellow-500/20 text-yellow-400'
    case 'RESOLVED': return 'bg-green-500/20 text-green-400'
    default: return 'bg-gray-500/20 text-gray-400'
  }
}

function EvidenceRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex items-center justify-between text-xs py-1 border-b border-border/50 last:border-0">
      <span className="text-muted">{label}</span>
      <span className="text-white font-medium">{value}</span>
    </div>
  )
}

function AlertEvidence({ alert }: { alert: Alert }) {
  const e = alert.evidence || {}
  switch (alert.alert_type) {
    case 'BLACKLISTED_VEHICLE':
      return (
        <div className="mt-3 bg-surface p-3 rounded-lg">
          <EvidenceRow label="Matched against" value={e.matched_against} />
          <EvidenceRow label="Match similarity" value={e.similarity != null ? `${(e.similarity * 100).toFixed(0)}%` : undefined} />
          <EvidenceRow label="Cameras hit" value={Array.isArray(e.camera_hits) ? e.camera_hits.join(' → ') : undefined} />
          <EvidenceRow label="Watchlist reason" value={e.watchlist_reason} />
          {e.watchlist_source && (
            <div className="mt-2">
              <span className={`text-[10px] px-2 py-0.5 rounded-full border ${e.watchlist_source === 'DEMO_SEED' ? 'bg-purple-500/20 text-purple-300 border-purple-500/30' : 'bg-blue-500/20 text-blue-300 border-blue-500/30'}`}>
                {e.watchlist_source === 'DEMO_SEED' ? 'DEMO WATCHLIST — not a real record' : 'OPERATIONAL WATCHLIST'}
              </span>
            </div>
          )}
        </div>
      )
    case 'SUSPICIOUS_ROUTE': {
      const breakdown = e.signal_breakdown || {}
      const activeSignals = Object.entries(breakdown).filter(([, v]) => typeof v === 'number' && v > 0)
      return (
        <div className="mt-3 bg-surface p-3 rounded-lg">
          <EvidenceRow label="Anomaly score" value={e.anomaly_score != null ? `${e.anomaly_score.toFixed(0)}/100` : undefined} />
          <EvidenceRow label="Camera sequence" value={Array.isArray(e.camera_sequence) ? e.camera_sequence.join(' → ') : undefined} />
          {activeSignals.length > 0 && (
            <div className="mt-2">
              <span className="text-xs text-muted">Contributing signals: </span>
              {activeSignals.map(([k, v]) => (
                <span key={k} className="inline-block text-[10px] mr-1 mt-1 px-2 py-0.5 rounded bg-orange-500/10 text-orange-300">
                  {k.replace(/_/g, ' ')} ({String(v)})
                </span>
              ))}
            </div>
          )}
        </div>
      )
    }
    case 'REPEATED_CAMERA':
      return (
        <div className="mt-3 bg-surface p-3 rounded-lg">
          <EvidenceRow label="Camera" value={e.camera_id} />
          <EvidenceRow label="Sightings" value={e.sighting_count} />
        </div>
      )
    case 'CONGESTION_BOTTLENECK':
      return (
        <div className="mt-3 bg-surface p-3 rounded-lg">
          <EvidenceRow label="Congestion level" value={e.congestion_level} />
          <EvidenceRow label="Bottleneck score" value={e.bottleneck_score != null ? `${e.bottleneck_score.toFixed(1)}/100` : undefined} />
          <EvidenceRow label="Avg speed" value={e.avg_speed_kmh != null ? `${e.avg_speed_kmh.toFixed(1)} km/h` : undefined} />
          <EvidenceRow label="Duration" value={e.duration_minutes != null ? `${e.duration_minutes} min` : undefined} />
          <div className="mt-2">
            <Link to="/congestion" className="text-xs text-orange-400 hover:underline inline-flex items-center gap-1">
              View on Congestion map <ArrowUpRight size={12} />
            </Link>
          </div>
        </div>
      )
    case 'CAMERA_OFFLINE':
      return (
        <div className="mt-3 bg-surface p-3 rounded-lg">
          <EvidenceRow label="Last seen" value={e.last_seen || 'Never'} />
          <EvidenceRow label="Offline threshold" value={e.threshold_hours != null ? `${e.threshold_hours}h` : undefined} />
        </div>
      )
    default:
      return null
  }
}

const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState('ALL')
  const [showWatchlist, setShowWatchlist] = useState(false)
  // alerts and watchlist are independent data sources - a failure in one
  // (e.g. the watchlist endpoint being unreachable) previously wiped out
  // BOTH, because a single Promise.all([...]) rejects entirely the moment
  // either call fails, discarding a perfectly good alerts response along
  // with it. Real, reproduced bug: real alerts existed and the bell/
  // Overview KPI showed them correctly, while this page showed "0 Open
  // Alerts / No alerts found" because the separate watchlist call had
  // failed. Fetched independently now so each surfaces its own real error
  // without hiding the other's real data.
  const [alertsError, setAlertsError] = useState(false)
  const [watchlistError, setWatchlistError] = useState(false)

  const fetchAll = async () => {
    setIsLoading(true)
    const results = await Promise.allSettled([
      api.getAlerts({ limit: 100 }),
      api.getWatchlist(),
    ])

    if (results[0].status === 'fulfilled') {
      setAlerts(results[0].value)
      setAlertsError(false)
    } else {
      console.error('Failed to fetch alerts:', results[0].reason)
      setAlertsError(true)
      toast.error('Failed to load alerts')
    }

    if (results[1].status === 'fulfilled') {
      setWatchlist(results[1].value)
      setWatchlistError(false)
    } else {
      console.error('Failed to fetch watchlist:', results[1].reason)
      setWatchlistError(true)
    }

    setIsLoading(false)
  }

  useEffect(() => {
    fetchAll()
  }, [])

  const handleResolve = async (alertId: string) => {
    try {
      await api.resolveAlert(alertId)
      toast.success('Alert resolved')
      fetchAll()
    } catch (error) {
      toast.error('Failed to resolve alert')
    }
  }

  const handleAcknowledge = async (alertId: string) => {
    try {
      await api.acknowledgeAlert(alertId)
      toast.success('Alert acknowledged')
      fetchAll()
    } catch (error) {
      toast.error('Failed to acknowledge alert')
    }
  }

  const filteredAlerts = alerts.filter((alert) => {
    if (filter === 'ALL') return true
    return alert.status === filter
  })

  const demoWatchlist = watchlist.filter((w) => w.source === 'DEMO_SEED')
  const operationalWatchlist = watchlist.filter((w) => w.source === 'OPERATOR')

  if (isLoading) {
    return <div className="flex justify-center items-center h-full text-muted">Loading alerts…</div>
  }

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded-lg p-3 flex items-center justify-between text-sm text-muted">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          <span>Alerts generated from watchlist matches, route anomalies, congestion bottlenecks, and camera activity.</span>
        </div>
        <span className="text-xs bg-surface-light px-2 py-0.5 rounded font-mono border border-border">AUTOMATED INCIDENTS</span>
      </div>

      {alertsError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">
          TrackX services are temporarily unavailable. Alerts could not be loaded — try refreshing the page.
        </div>
      )}
      {watchlistError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">
          The watchlist could not be loaded right now. Alerts above are unaffected — try refreshing to see the watchlist.
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-white">Alert Operations Center</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowWatchlist((v) => !v)}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-surface-light border border-border text-white hover:border-blue-500/50 flex items-center gap-2"
          >
            <ListChecks size={16} />
            Watchlist ({watchlist.length})
          </button>
          <div className="flex gap-2">
            {['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'].map((status) => (
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
      </div>

      {showWatchlist && (
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
            <ListChecks className="text-blue-400" />
            Watchlist
          </h3>
          <p className="text-xs text-muted mb-4">
            Plates that trigger a Watchlist Match alert when observed. Demo scenario plates are clearly separated from
            plates an operator adds through the app — demo entries are not real government watchlist data.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="text-xs font-bold text-purple-300 mb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-purple-400" />
                DEMO WATCHLIST ({demoWatchlist.length}) — scripted demo scenario data, not real records
              </div>
              {demoWatchlist.length === 0 ? (
                <p className="text-xs text-muted">None</p>
              ) : (
                <div className="space-y-2">
                  {demoWatchlist.map((w) => (
                    <div key={w.id} className="p-3 rounded-lg bg-purple-500/5 border border-purple-500/20 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-white">{w.plate}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${severityBadge(w.severity)}`}>{w.severity}</span>
                      </div>
                      <p className="text-xs text-muted mt-1">{w.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <div className="text-xs font-bold text-blue-300 mb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-400" />
                OPERATIONAL WATCHLIST ({operationalWatchlist.length}) — added by an operator via Vehicle Intelligence
              </div>
              {operationalWatchlist.length === 0 ? (
                <p className="text-xs text-muted">No operator-added entries yet.</p>
              ) : (
                <div className="space-y-2">
                  {operationalWatchlist.map((w) => (
                    <div key={w.id} className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/20 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-white">{w.plate}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${severityBadge(w.severity)}`}>{w.severity}</span>
                      </div>
                      <p className="text-xs text-muted mt-1">{w.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <div className="card p-6 text-center">
          <p className="text-3xl font-bold text-red-400">{alerts.filter((a) => a.status === 'OPEN').length}</p>
          <p className="text-sm text-muted mt-1">Open Alerts</p>
        </div>
        <div className="card p-6 text-center">
          <p className="text-3xl font-bold text-yellow-400">{alerts.filter((a) => a.status === 'ACKNOWLEDGED').length}</p>
          <p className="text-sm text-muted mt-1">Acknowledged</p>
        </div>
        <div className="card p-6 text-center">
          <p className="text-3xl font-bold text-green-400">{alerts.filter((a) => a.status === 'RESOLVED').length}</p>
          <p className="text-sm text-muted mt-1">Resolved</p>
        </div>
      </div>

      <div className="space-y-4">
        {filteredAlerts.length === 0 ? (
          <div className="card p-12 text-center">
            <Bell size={48} className="mx-auto text-muted mb-4" />
            <p className="text-muted">No alerts found</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const m = meta(alert.alert_type)
            const Icon = m.icon
            const colors = COLOR_CLASSES[m.color]
            return (
              <div key={alert.alert_id} className="card p-6 hover:border-blue-500/50 transition-colors">
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 ${colors.bg}`}>
                    <Icon size={22} className={colors.text} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                      <h3 className="font-bold text-white">{m.label}</h3>
                      <div className="flex gap-2">
                        <span className={`text-xs px-2 py-1 rounded-full ${severityBadge(alert.severity)}`}>{alert.severity}</span>
                        <span className={`text-xs px-2 py-1 rounded-full ${statusBadge(alert.status)}`}>{alert.status}</span>
                      </div>
                    </div>

                    {alert.is_vehicle_alert && alert.plate_text ? (
                      <p className="font-mono text-white text-lg">{alert.plate_text}</p>
                    ) : (
                      <p className="font-mono text-white text-lg">{alert.camera_id}</p>
                    )}
                    <p className="text-sm text-muted mt-1">{alert.description}</p>
                    <p className="text-xs text-muted mt-2">
                      {alert.camera_id && `${alert.camera_id} · `}
                      {alert.timestamp}
                    </p>

                    <AlertEvidence alert={alert} />

                    {alert.is_vehicle_alert && alert.plate_text && (
                      <div className="flex items-center gap-4 mt-3">
                        <Link
                          to={`/vehicles?plate=${encodeURIComponent(alert.plate_text)}`}
                          className="text-xs text-blue-400 hover:underline flex items-center gap-1"
                        >
                          <Search size={12} /> View Vehicle Intelligence
                        </Link>
                        <Link
                          to={`/trajectory?plate=${encodeURIComponent(alert.plate_text)}`}
                          className="text-xs text-blue-400 hover:underline flex items-center gap-1"
                        >
                          <Route size={12} /> View Trajectory
                        </Link>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col gap-2 flex-shrink-0">
                    {alert.status === 'OPEN' && (
                      <>
                        <button
                          onClick={() => handleAcknowledge(alert.alert_id)}
                          className="px-3 py-1 text-xs rounded-lg bg-surface-light border border-border text-yellow-400 hover:bg-yellow-500/10"
                        >
                          Acknowledge
                        </button>
                        <button
                          onClick={() => handleResolve(alert.alert_id)}
                          className="px-3 py-1 text-xs rounded-lg bg-surface-light border border-border text-green-400 hover:bg-green-500/10"
                        >
                          Resolve
                        </button>
                      </>
                    )}
                    {alert.status === 'ACKNOWLEDGED' && (
                      <button
                        onClick={() => handleResolve(alert.alert_id)}
                        className="px-3 py-1 text-xs rounded-lg bg-surface-light border border-border text-green-400 hover:bg-green-500/10"
                      >
                        Resolve
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export default AlertsPage
