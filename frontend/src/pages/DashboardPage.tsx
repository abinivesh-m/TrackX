// frontend/src/pages/DashboardPage.tsx
//
// Operations Center overview. Every number here comes from a real API:
// KPI row from GET /analytics/summary + /congestion/bottlenecks + /alerts,
// the map and "Camera Network" panel from GET /cameras/health (real
// ONLINE/NO_DATA per camera, not the hardcoded-ONLINE /cameras list), and
// System Status from GET /health (now backed by real DB/model checks -
// see backend/app/main.py - instead of hardcoded "operational" literals).
//
// Restyled as a control-room overview panel: flat KPI tiles, no gradient
// icon glows, no staggered entrance animation, no rounded-pill badges.

import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts'
import { toast } from 'react-toastify'
import { api } from '@/services/api'
import CameraMap from '@/components/maps/CameraMap'
import StatCard from '@/components/common/StatCard'
import RecentActivity from '@/components/common/RecentActivity'
import { Activity, Camera, AlertTriangle, Gauge, Shield, Video, Car, TrendingUp, WifiOff } from 'lucide-react'
import type { AnalyticsSummary, Camera as CameraType, Alert, Observation, CongestionEvent } from '@/types'

const DashboardPage: React.FC = () => {
  const [cameras, setCameras] = useState<CameraType[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [bottlenecks, setBottlenecks] = useState<CongestionEvent[]>([])
  const [recentObservations, setRecentObservations] = useState<Observation[]>([])
  const [healthStatus, setHealthStatus] = useState<any>(null)
  // Real total open-alert count from GET /alerts/stats - NOT derived from
  // the 5-item `alerts` list below (that list is only ever the 5 most
  // recent alerts, fetched for the Recent Alerts panel; filtering it for
  // "OPEN" would silently undercount whenever there are more than 5 alerts
  // total or the 5 most recent happen to include resolved ones). The
  // header's notification bell reads this same /alerts/stats-backed count
  // indirectly via its own real fetch, so this KPI and the bell can never
  // show two different fabricated numbers for the same thing.
  const [alertStats, setAlertStats] = useState<{ total_alerts: number; open_alerts: number; high_severity_open: number } | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  // Distinguishes "backend unreachable" from "genuinely no data yet" - a
  // silent failure here previously rendered as an empty-looking, all-zero
  // dashboard with no indication anything was actually wrong.
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [camerasData, analyticsData, alertsData, alertStatsData, observationsData, healthData, bottlenecksData] = await Promise.all([
          api.getCameraHealth(),
          api.getAnalyticsSummary(),
          api.getAlerts({ limit: 5 }),
          api.getAlertStats(),
          api.getRecentObservations(),
          api.getHealth().catch(() => null),
          api.getActiveBottlenecks(50).catch(() => ({ bottlenecks: [] })),
        ])

        setCameras(camerasData)
        setAnalytics(analyticsData)
        setAlerts(alertsData)
        setAlertStats(alertStatsData)
        setRecentObservations(observationsData)
        setHealthStatus(healthData)
        setBottlenecks(bottlenecksData.bottlenecks || bottlenecksData || [])
        setLoadError(null)
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
        setLoadError('Could not reach the TrackX API. The dashboard below may be incomplete or stale.')
        toast.error('Failed to load dashboard data')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [])

  if (isLoading) {
    return (
      <div className="flex flex-col justify-center items-center h-full text-white space-y-3">
        <div className="spinner" />
        <p className="text-sm text-muted font-data">LOADING OPERATIONS CENTER...</p>
      </div>
    )
  }

  const openAlerts = alertStats?.open_alerts ?? alerts.filter(a => a.status === 'OPEN').length
  const onlineCameras = cameras.filter(c => c.status === 'ONLINE').length
  const trendData = analytics?.hourly_density?.hourly_totals
    ?.slice()
    .sort((a, b) => a.hour.localeCompare(b.hour))
    .map((h) => ({ hour: h.hour.slice(-5), vehicles: h.count })) || []

  return (
    <div className="space-y-5">
      {loadError && (
        <div className="bg-critical-500/10 border border-critical-500/30 rounded-sm p-3 flex items-center gap-2 text-critical-400 text-sm">
          <WifiOff size={16} />
          <span>{loadError}</span>
        </div>
      )}

      <div className="bg-surface border border-border rounded-sm p-3 flex items-center justify-between text-sm text-muted">
        <div className="flex items-center gap-2">
          <span className="live-dot is-live" />
          <span>Operating on recorded multi-camera feeds with genuine Indian plates for evaluation.</span>
        </div>
        <span className="text-xs bg-surface-light px-2 py-0.5 rounded-sm font-data border border-border">SIH 26127</span>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white flex items-center gap-2.5">
          <Shield className="text-signal-400" size={22} />
          Operations Center
        </h1>
        <span className="label-caps">Pipeline: Camera &rarr; Detection &rarr; OCR &rarr; Matching &rarr; Map &rarr; Intelligence</span>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatCard icon={Video} label="Active Cameras" value={`${onlineCameras}/${cameras.length}`} iconColor="bg-clear-500/15 text-clear-400" />
        <StatCard icon={Car} label="Vehicles Detected" value={analytics?.total_observations?.toLocaleString() || '0'} iconColor="bg-signal-500/15 text-signal-400" />
        <StatCard icon={Activity} label="Unique Vehicles" value={analytics?.total_vehicles?.toLocaleString() || '0'} iconColor="bg-telemetry-500/15 text-telemetry-400" />
        <StatCard icon={Gauge} label="Avg Speed" value={analytics?.average_speed != null ? `${analytics.average_speed.toFixed(1)} km/h` : '—'} iconColor="bg-telemetry-500/15 text-telemetry-400" />
        <StatCard icon={TrendingUp} label="Congestion Bottlenecks" value={bottlenecks.length.toString()} iconColor="bg-caution-500/15 text-caution-400" />
        <StatCard icon={AlertTriangle} label="Active Alerts" value={openAlerts.toString()} iconColor="bg-critical-500/15 text-critical-400" />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 space-y-5">
          <div className="card p-0 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="label-caps flex items-center gap-2">
                <Camera size={13} />
                City Camera Network
              </h2>
              <span className={`text-[11px] flex items-center gap-1.5 px-2.5 py-1 rounded-sm font-semibold font-data border ${
                onlineCameras === cameras.length
                  ? 'text-clear-400 bg-clear-500/10 border-clear-500/30'
                  : 'text-caution-400 bg-caution-500/10 border-caution-500/30'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${onlineCameras === cameras.length ? 'bg-clear-500' : 'bg-caution-500'}`} />
                {onlineCameras} / {cameras.length} REPORTING
              </span>
            </div>
            <div className="h-[440px]">
              <CameraMap cameras={cameras} />
            </div>
          </div>

          {/* Traffic Volume Trend */}
          <div className="card p-4">
            <h3 className="label-caps mb-0.5 flex items-center gap-2">
              <TrendingUp size={13} />
              Traffic Volume Trend
            </h3>
            <p className="text-xs text-muted mb-3">Vehicle observations per hour, city-wide.</p>
            {trendData.length === 0 ? (
              <div className="text-center py-10 text-muted text-sm">No hourly observation data yet.</div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={trendData}>
                  <defs>
                    <linearGradient id="dashTrendFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ec9d1e" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#ec9d1e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="2 4" stroke="#232733" />
                  <XAxis dataKey="hour" stroke="#6b7385" fontSize={11} />
                  <YAxis stroke="#6b7385" fontSize={11} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#171a21', border: '1px solid #232733', borderRadius: 3, fontSize: 12 }} />
                  <Area type="monotone" dataKey="vehicles" stroke="#ec9d1e" fill="url(#dashTrendFill)" strokeWidth={1.5} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Side Panel */}
        <div className="space-y-5">
          {/* System Status - every value below comes from GET /health, which
              actually checks the database and model availability
              (backend/app/api/v1/health.py's check_database()/check_models())
              rather than returning hardcoded "operational" strings. */}
          <div className="card p-4">
            <h3 className="label-caps mb-3 flex items-center gap-2">
              <Shield size={13} />
              System Status
            </h3>
            <div className="space-y-0.5">
              {[
                {
                  label: 'Database',
                  value: healthStatus?.database || 'unknown',
                  ok: healthStatus?.database === 'healthy',
                },
                {
                  label: 'Detection / OCR Models',
                  value: healthStatus?.ocr_engine || 'unknown',
                  ok: healthStatus?.ai_engine === 'healthy',
                },
                {
                  label: 'Observations Stored',
                  value: healthStatus?.database_details?.observation_count?.toLocaleString() ?? '—',
                  ok: true,
                },
              ].map((status) => (
                <div key={status.label} className="flex items-center justify-between py-2 border-b border-border last:border-b-0">
                  <span className="text-muted text-xs">{status.label}</span>
                  <span className={`text-xs flex items-center gap-1.5 font-semibold font-data ${status.ok ? 'text-clear-400' : 'text-caution-400'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${status.ok ? 'bg-clear-500' : 'bg-caution-500'}`} />
                    {status.value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Camera Network status breakdown */}
          <div className="card p-4">
            <h3 className="label-caps mb-3 flex items-center gap-2">
              <Video size={13} />
              Camera Network
            </h3>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">Online (recent observations)</span>
                <span className="text-clear-400 font-semibold font-data">{onlineCameras}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">No data yet</span>
                <span className="text-caution-400 font-semibold font-data">{cameras.length - onlineCameras}</span>
              </div>
              <Link to="/cameras" className="text-xs text-signal-400 hover:text-signal-300 inline-block mt-1.5">
                View Camera Network &rarr;
              </Link>
            </div>
          </div>

          {/* Recent Activity */}
          <RecentActivity observations={recentObservations} />

          {/* Alerts Preview */}
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="label-caps flex items-center gap-2">
                <AlertTriangle size={13} />
                Recent Alerts
              </h3>
              <Link to="/alerts" className="text-xs text-signal-400 hover:text-signal-300">View All</Link>
            </div>
            <div className="space-y-2">
              {alerts.length === 0 ? (
                <div className="text-xs text-muted text-center py-4">No active security alerts</div>
              ) : (
                alerts.slice(0, 3).map((alert) => (
                  <div
                    key={alert.alert_id}
                    className="p-2.5 rounded-sm bg-surface-light border border-border"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium text-white">{alert.alert_type.replace(/_/g, ' ')}</span>
                      <span className={`badge ${
                        alert.severity === 'HIGH'
                          ? 'badge-danger'
                          : alert.severity === 'MEDIUM'
                          ? 'badge-warning'
                          : 'badge-info'
                      }`}>
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-xs text-white font-data">{alert.plate_text || alert.camera_id}</p>
                    <p className="text-[11px] text-muted mt-0.5">{alert.description}</p>
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
