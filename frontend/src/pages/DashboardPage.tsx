// frontend/src/pages/DashboardPage.tsx
//
// Operations Center overview. Every number here comes from a real API:
// KPI row from GET /analytics/summary + /congestion/bottlenecks + /alerts,
// the map and "Camera Network" panel from GET /cameras/health (real
// ONLINE/NO_DATA per camera, not the hardcoded-ONLINE /cameras list), and
// System Status from GET /health (now backed by real DB/model checks -
// see backend/app/main.py - instead of hardcoded "operational" literals).

import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
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
      <div className="flex flex-col justify-center items-center h-full text-white space-y-4">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        >
          <Activity size={48} className="text-blue-400" />
        </motion.div>
        <p className="text-lg text-muted">Loading Operations Center…</p>
      </div>
    )
  }

  const openAlerts = alertStats?.open_alerts ?? alerts.filter(a => a.status === 'OPEN').length
  const onlineCameras = cameras.filter(c => c.status === 'ONLINE').length
  const trendData = analytics?.hourly_density?.hourly_totals
    ?.slice()
    .sort((a, b) => a.hour.localeCompare(b.hour))
    .map((h) => ({ hour: h.hour.slice(-5), vehicles: h.count })) || []

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.06, delayChildren: 0.05 } }
  }
  const itemVariants = {
    hidden: { opacity: 0, y: 16 },
    visible: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 140, damping: 18 } }
  }

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="visible" className="space-y-6">
      {loadError && (
        <motion.div
          variants={itemVariants}
          className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex items-center gap-2 text-red-300 text-sm"
        >
          <WifiOff size={16} />
          <span>{loadError}</span>
        </motion.div>
      )}
      <motion.div
        variants={itemVariants}
        className="bg-surface border border-border rounded-lg p-3 flex items-center justify-between text-sm text-muted"
      >
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          <span>Operating on recorded multi-camera feeds with genuine Indian plates for evaluation.</span>
        </div>
        <span className="text-xs bg-surface-light px-2 py-0.5 rounded font-mono border border-border">SIH 26127</span>
      </motion.div>

      <motion.h1 variants={itemVariants} className="text-3xl font-bold text-white flex items-center gap-3">
        <Shield className="text-blue-400" />
        Operations Center
      </motion.h1>

      {/* KPI Row */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard icon={Video} label="Active Cameras" value={`${onlineCameras}/${cameras.length}`} iconColor="bg-green-500/20 text-green-400" />
        <StatCard icon={Car} label="Vehicles Detected" value={analytics?.total_observations?.toLocaleString() || '0'} iconColor="bg-blue-500/20 text-blue-400" />
        <StatCard icon={Activity} label="Unique Vehicles" value={analytics?.total_vehicles?.toLocaleString() || '0'} iconColor="bg-purple-500/20 text-purple-400" />
        <StatCard icon={Gauge} label="Avg Speed" value={analytics?.average_speed != null ? `${analytics.average_speed.toFixed(1)} km/h` : '—'} iconColor="bg-cyan-500/20 text-cyan-400" />
        <StatCard icon={TrendingUp} label="Congestion Bottlenecks" value={bottlenecks.length.toString()} iconColor="bg-orange-500/20 text-orange-400" />
        <StatCard icon={AlertTriangle} label="Active Alerts" value={openAlerts.toString()} iconColor="bg-red-500/20 text-red-400" />
      </motion.div>

      {/* Main Content */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-500/20 border border-blue-500/30">
                  <Camera className="text-blue-400" size={22} />
                </div>
                City Camera Network
              </h2>
              <span className={`text-xs flex items-center gap-2 px-4 py-1.5 rounded-full font-semibold border ${
                onlineCameras === cameras.length
                  ? 'text-green-400 bg-green-500/10 border-green-500/30'
                  : 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30'
              }`}>
                <span className={`w-2 h-2 rounded-full ${onlineCameras === cameras.length ? 'bg-green-500' : 'bg-yellow-500'}`} />
                {onlineCameras} of {cameras.length} reporting
              </span>
            </div>
            <div className="h-[460px] rounded-xl overflow-hidden border border-border">
              <CameraMap cameras={cameras} />
            </div>
          </div>

          {/* Traffic Volume Trend */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
              <TrendingUp className="text-green-400" size={18} />
              Traffic Volume Trend
            </h3>
            <p className="text-xs text-muted mb-4">Vehicle observations per hour, city-wide.</p>
            {trendData.length === 0 ? (
              <div className="text-center py-10 text-muted text-sm">No hourly observation data yet.</div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={trendData}>
                  <defs>
                    <linearGradient id="dashTrendFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.5} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2f3a" />
                  <XAxis dataKey="hour" stroke="#8b93a7" fontSize={11} />
                  <YAxis stroke="#8b93a7" fontSize={11} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#151922', border: '1px solid #2a2f3a', borderRadius: 8, fontSize: 12 }} />
                  <Area type="monotone" dataKey="vehicles" stroke="#3b82f6" fill="url(#dashTrendFill)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Side Panel */}
        <div className="space-y-6">
          {/* System Status - every value below comes from GET /health, which
              actually checks the database and model availability
              (backend/app/api/v1/health.py's check_database()/check_models())
              rather than returning hardcoded "operational" strings. */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <div className="p-2 rounded-lg bg-green-500/20 border border-green-500/30">
                <Shield className="text-green-400" size={18} />
              </div>
              System Status
            </h3>
            <div className="space-y-1">
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
                <div key={status.label} className="flex items-center justify-between p-3 rounded-xl hover:bg-surface-light transition-all">
                  <span className="text-muted text-sm font-medium">{status.label}</span>
                  <span className={`text-sm flex items-center gap-2 font-semibold ${status.ok ? 'text-green-400' : 'text-yellow-400'}`}>
                    <span className={`w-2.5 h-2.5 rounded-full ${status.ok ? 'bg-green-500' : 'bg-yellow-500'}`} />
                    {status.value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Camera Network status breakdown */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Video className="text-blue-400" size={18} />
              Camera Network
            </h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">Online (recent observations)</span>
                <span className="text-green-400 font-semibold">{onlineCameras}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">No data yet</span>
                <span className="text-yellow-400 font-semibold">{cameras.length - onlineCameras}</span>
              </div>
              <Link to="/cameras" className="text-xs text-blue-400 hover:underline inline-block mt-2">
                View Camera Network →
              </Link>
            </div>
          </div>

          {/* Recent Activity */}
          <RecentActivity observations={recentObservations} />

          {/* Alerts Preview */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <AlertTriangle className="text-red-400" size={18} />
                Recent Alerts
              </h3>
              <Link to="/alerts" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">View All</Link>
            </div>
            <div className="space-y-3">
              <AnimatePresence>
                {alerts.length === 0 ? (
                  <div className="text-xs text-muted text-center py-4">No active security alerts</div>
                ) : (
                  alerts.slice(0, 3).map((alert, index) => (
                    <motion.div
                      key={alert.alert_id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 20 }}
                      transition={{ delay: index * 0.05 }}
                      className="p-3 rounded-lg bg-surface-light border border-border hover:border-blue-500/30 transition-all"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-white">{alert.alert_type.replace(/_/g, ' ')}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          alert.severity === 'HIGH'
                            ? 'bg-red-500/20 text-red-400'
                            : alert.severity === 'MEDIUM'
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'bg-green-500/20 text-green-400'
                        }`}>
                          {alert.severity}
                        </span>
                      </div>
                      <p className="text-sm text-white font-mono">{alert.plate_text || alert.camera_id}</p>
                      <p className="text-xs text-muted mt-1">{alert.description}</p>
                    </motion.div>
                  ))
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default DashboardPage
