// frontend/src/pages/CongestionPage.tsx
//
// Traffic Analytics / Congestion — city overview, congestion map, bottleneck
// list, active vs resolved event history, real origin-destination flow, and
// a real hourly traffic trend. None of the congestion math is reimplemented
// here: every number comes from the existing backend/app/api/v1/congestion.py
// and analytics.py endpoints, which are themselves thin wrappers over
// analytics/analytics.py's congestion_hotspots() model.

import React, { useState, useEffect } from 'react'
import { api } from '@/services/api'
import {
  Activity, AlertTriangle, Gauge, Clock, MapPin, TrendingUp, Play, Settings,
  ArrowRight, CheckCircle2,
} from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'
import type {
  CongestionEvent, TrafficThresholds, GisCongestionPoint, GisOdFlow, AnalyticsSummary,
} from '@/types'
import { toast } from 'react-toastify'
import CongestionMap from '@/components/maps/CongestionMap'

const LEVEL_STYLES: Record<string, string> = {
  SEVERE: 'bg-red-500/20 text-red-400 border-red-500/30',
  HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  CONGESTED: 'bg-red-500/20 text-red-400 border-red-500/30',
  MEDIUM: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  MODERATE: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  LOW: 'bg-green-500/20 text-green-400 border-green-500/30',
}

function levelStyle(level: string) {
  return LEVEL_STYLES[level] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'
}

function scoreColor(score: number) {
  if (score >= 80) return 'text-red-400'
  if (score >= 60) return 'text-orange-400'
  if (score >= 40) return 'text-yellow-400'
  return 'text-green-400'
}

function formatDate(dateString?: string) {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return dateString
  return date.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

const CongestionPage: React.FC = () => {
  const [bottlenecks, setBottlenecks] = useState<CongestionEvent[]>([])
  const [activeEvents, setActiveEvents] = useState<CongestionEvent[]>([])
  const [historyEvents, setHistoryEvents] = useState<CongestionEvent[]>([])
  const [congestionMap, setCongestionMap] = useState<GisCongestionPoint[]>([])
  const [odFlow, setOdFlow] = useState<GisOdFlow[]>([])
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [thresholds, setThresholds] = useState<TrafficThresholds | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isProcessing, setIsProcessing] = useState(false)
  const [eventTab, setEventTab] = useState<'active' | 'resolved'>('active')
  const [lastLoaded, setLastLoaded] = useState<Date | null>(null)
  // Which of the page's independent data sources failed on the last load -
  // tracked separately so a single bad call (e.g. thresholds) can't blank
  // out data that loaded fine (e.g. bottlenecks/events), the same
  // Promise.all -> Promise.allSettled fix already applied on AlertsPage.
  const [loadErrors, setLoadErrors] = useState<Record<string, boolean>>({})

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setIsLoading(true)
    const sources: [string, () => Promise<any>][] = [
      ['bottlenecks', () => api.getActiveBottlenecks(20)],
      ['active', () => api.getActiveCongestionEvents(undefined, 50)],
      ['history', () => api.getCongestionEventHistory(undefined, undefined, undefined, 50)],
      ['gisCongestion', () => api.getGISCongestion()],
      ['gisFlow', () => api.getGISFlow()],
      ['summary', () => api.getAnalyticsSummary()],
      ['thresholds', () => api.getTrafficThresholds()],
    ]
    const results = await Promise.allSettled(sources.map(([, fn]) => fn()))
    const errors: Record<string, boolean> = {}

    results.forEach((result, i) => {
      const [key] = sources[i]
      if (result.status === 'rejected') {
        console.error(`Failed to load congestion data (${key}):`, result.reason)
        errors[key] = true
        return
      }
      const value = result.value
      switch (key) {
        case 'bottlenecks':
          setBottlenecks(value?.bottlenecks || value || [])
          break
        case 'active':
          setActiveEvents(value || [])
          break
        case 'history':
          setHistoryEvents((value || []).filter((e: CongestionEvent) => e.status === 'RESOLVED'))
          break
        case 'gisCongestion':
          setCongestionMap(value || [])
          break
        case 'gisFlow':
          setOdFlow((value || []).slice(0, 10))
          break
        case 'summary':
          setSummary(value)
          break
        case 'thresholds':
          setThresholds(value)
          break
      }
    })

    setLoadErrors(errors)
    if (Object.keys(errors).length > 0) {
      toast.error('Some traffic analytics data could not be loaded — the rest of this page is still live.')
    }
    setLastLoaded(new Date())
    setIsLoading(false)
  }

  const processAllCameras = async () => {
    setIsProcessing(true)
    try {
      const result = await api.processAllCamerasCongestion(5)
      toast.success(`Processed ${result.processed_cameras} cameras — ${result.congested_cameras} congested`)
      await loadAll()
    } catch (error) {
      console.error('Processing failed:', error)
      toast.error('Congestion processing failed')
    } finally {
      setIsProcessing(false)
    }
  }

  // Real average, computed from the same per-camera scores shown on the map
  // and in the event lists below — not a fabricated level->number mapping.
  const avgCongestionScore = congestionMap.length > 0
    ? Math.round((congestionMap.reduce((sum, p) => sum + p.score, 0) / congestionMap.length) * 100)
    : null

  const trendData = summary?.hourly_density?.hourly_totals
    ?.slice()
    .sort((a, b) => a.hour.localeCompare(b.hour))
    .map((h) => ({ hour: h.hour.slice(-5), vehicles: h.count })) || []

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded-lg p-3 flex items-center justify-between text-sm text-muted">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          <span>Congestion and bottleneck detection computed live from stored ANPR observations.</span>
        </div>
        <span className="text-xs bg-surface-light px-2 py-0.5 rounded font-mono border border-border">
          {lastLoaded ? `Updated ${formatDate(lastLoaded.toISOString())}` : 'Loading…'}
        </span>
      </div>

      {Object.keys(loadErrors).length > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">
          Some traffic analytics data could not be loaded ({Object.keys(loadErrors).join(', ')}) — the rest of
          this page reflects real, successfully-loaded data. Try refreshing to retry the failed part.
        </div>
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Activity className="text-orange-400" />
          Traffic Analytics & Congestion
        </h1>
        <button
          onClick={processAllCameras}
          disabled={isProcessing}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-red-600 text-white font-bold hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
        >
          {isProcessing ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Processing…
            </>
          ) : (
            <>
              <Play size={16} />
              Process All Cameras
            </>
          )}
        </button>
      </div>

      {/* City Overview */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-2">
            <MapPin size={20} className="text-blue-400" />
            <span className="text-sm text-muted">Cameras Reporting</span>
          </div>
          <p className="text-3xl font-bold text-white">{congestionMap.length}</p>
        </div>
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle size={20} className="text-red-400" />
            <span className="text-sm text-muted">Active Bottlenecks</span>
          </div>
          <p className="text-3xl font-bold text-white">{bottlenecks.length}</p>
        </div>
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-2">
            <Activity size={20} className="text-orange-400" />
            <span className="text-sm text-muted">Active Events</span>
          </div>
          <p className="text-3xl font-bold text-white">{activeEvents.length}</p>
        </div>
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-2">
            <Gauge size={20} className="text-yellow-400" />
            <span className="text-sm text-muted">Avg Congestion Score</span>
          </div>
          <p className="text-3xl font-bold text-white">
            {avgCongestionScore != null ? `${avgCongestionScore}/100` : '—'}
          </p>
          <p className="text-xs text-muted mt-1">Across {congestionMap.length} reporting camera{congestionMap.length === 1 ? '' : 's'}</p>
        </div>
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp size={20} className="text-green-400" />
            <span className="text-sm text-muted">Total Vehicles Observed</span>
          </div>
          <p className="text-3xl font-bold text-white">{summary?.total_vehicles ?? '—'}</p>
        </div>
      </div>

      {/* Congestion Map */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
          <MapPin className="text-blue-400" />
          City Congestion Map
        </h3>
        <p className="text-xs text-muted mb-4">Live per-camera congestion level, from real observation density and speed.</p>
        {isLoading ? (
          <div className="h-[460px] flex items-center justify-center text-muted">Loading map…</div>
        ) : (
          <CongestionMap points={congestionMap} height={460} />
        )}
        <div className="flex items-center gap-6 mt-4 text-xs text-muted">
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-red-500" /> Congested</div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-amber-500" /> Moderate</div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-emerald-500" /> Normal / not reporting congestion</div>
        </div>
      </div>

      {/* Traffic Trend */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
          <TrendingUp className="text-green-400" />
          Traffic Volume Trend
        </h3>
        <p className="text-xs text-muted mb-4">Real vehicle counts per hour, aggregated across all cameras.</p>
        {trendData.length === 0 ? (
          <div className="text-center py-10 text-muted text-sm">No hourly observation data yet.</div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f97316" stopOpacity={0.5} />
                  <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2f3a" />
              <XAxis dataKey="hour" stroke="#8b93a7" fontSize={11} />
              <YAxis stroke="#8b93a7" fontSize={11} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#151922', border: '1px solid #2a2f3a', borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="vehicles" stroke="#f97316" fill="url(#trendFill)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bottlenecks */}
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <AlertTriangle className="text-red-400" />
              Active Bottlenecks
            </h3>
            <span className="text-sm text-red-400">{bottlenecks.length} detected</span>
          </div>
          {isLoading ? (
            <div className="text-center py-8 text-muted">Loading…</div>
          ) : bottlenecks.length === 0 ? (
            <div className="text-center py-8 text-muted">
              <AlertTriangle size={40} className="mx-auto mb-3 opacity-50" />
              <p>No active bottlenecks detected</p>
              <p className="text-sm mt-1">Click "Process All Cameras" to run the detector.</p>
            </div>
          ) : (
            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
              {bottlenecks.map((b) => (
                <div key={b.event_id} className="p-4 rounded-lg bg-surface-light border border-red-500/30">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-bold text-white">{b.camera_id}</span>
                    <span className={`text-xs px-2 py-1 rounded-full border ${levelStyle(b.congestion_level)}`}>{b.congestion_level}</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-muted mb-2 flex-wrap">
                    <span className="flex items-center gap-1"><Clock size={14} />{b.duration_minutes} min</span>
                    <span className="flex items-center gap-1"><Gauge size={14} />{b.avg_speed_kmh.toFixed(1)} km/h</span>
                    <span className="flex items-center gap-1"><Activity size={14} />{b.flow_rate_vehicles_per_hour.toFixed(0)} veh/h</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-muted">Bottleneck Score:</span>
                    <span className={`font-bold ${scoreColor(b.bottleneck_score)}`}>{b.bottleneck_score.toFixed(1)}/100</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* OD Flow */}
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
            <ArrowRight className="text-blue-400" />
            Top Origin → Destination Flows
          </h3>
          <p className="text-xs text-muted mb-4">Real routes reconstructed from multi-camera trajectories.</p>
          {odFlow.length === 0 ? (
            <div className="text-center py-8 text-muted text-sm">No multi-camera routes reconstructed yet.</div>
          ) : (
            <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
              {odFlow.map((f, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-surface-light border border-border text-sm">
                  <div className="flex items-center gap-2 text-white">
                    <span>{f.origin_name}</span>
                    <ArrowRight size={14} className="text-muted" />
                    <span>{f.dest_name}</span>
                  </div>
                  <span className="text-orange-400 font-bold">{f.count} trip{f.count === 1 ? '' : 's'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Event history: active vs resolved */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Activity className="text-orange-400" />
            Congestion Events
          </h3>
          <div className="flex items-center gap-2 text-sm">
            <button
              onClick={() => setEventTab('active')}
              className={`px-3 py-1 rounded-lg border ${eventTab === 'active' ? 'bg-orange-500/20 text-orange-300 border-orange-500/40' : 'text-muted border-border'}`}
            >
              Active ({activeEvents.length})
            </button>
            <button
              onClick={() => setEventTab('resolved')}
              className={`px-3 py-1 rounded-lg border ${eventTab === 'resolved' ? 'bg-green-500/20 text-green-300 border-green-500/40' : 'text-muted border-border'}`}
            >
              Resolved ({historyEvents.length})
            </button>
          </div>
        </div>

        {(eventTab === 'active' ? activeEvents : historyEvents).length === 0 ? (
          <div className="text-center py-8 text-muted">
            {eventTab === 'active' ? 'No active congestion events' : 'No resolved events yet'}
          </div>
        ) : (
          <div className="space-y-3">
            {(eventTab === 'active' ? activeEvents : historyEvents).map((event) => (
              <div key={event.event_id} className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-bold text-white">{event.camera_id}</span>
                      <span className={`text-xs px-2 py-1 rounded-full border ${levelStyle(event.congestion_level)}`}>{event.congestion_level}</span>
                      {event.is_bottleneck && (
                        <span className="text-xs px-2 py-1 rounded-full bg-red-500/20 text-red-400">BOTTLENECK</span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted flex-wrap">
                      <span className="flex items-center gap-1"><Clock size={14} />{formatDate(event.event_start)}</span>
                      <span className="flex items-center gap-1"><Gauge size={14} />{event.avg_speed_kmh.toFixed(1)} km/h</span>
                      <span className="flex items-center gap-1"><Activity size={14} />{event.flow_rate_vehicles_per_hour.toFixed(0)} veh/h</span>
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${event.status === 'ACTIVE' ? 'bg-orange-500/20 text-orange-400' : 'bg-green-500/20 text-green-400'}`}>
                    {event.status === 'RESOLVED' && <CheckCircle2 size={12} />}
                    {event.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Thresholds */}
      {thresholds && (
        <div className="card p-6">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            <Settings className="text-blue-400" />
            Detection Thresholds
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-surface-light p-4 rounded-lg">
              <span className="text-xs text-muted">Speed Threshold</span>
              <p className="text-xl font-bold text-white mt-1">{thresholds.speed_threshold_kmh} km/h</p>
              <p className="text-xs text-muted mt-1">Below this = congestion</p>
            </div>
            <div className="bg-surface-light p-4 rounded-lg">
              <span className="text-xs text-muted">Density Threshold</span>
              <p className="text-xl font-bold text-white mt-1">{thresholds.density_threshold_vehicles_per_km} veh/km</p>
              <p className="text-xs text-muted mt-1">Above this = congestion</p>
            </div>
            <div className="bg-surface-light p-4 rounded-lg">
              <span className="text-xs text-muted">Bottleneck Reduction</span>
              <p className="text-xl font-bold text-white mt-1">{thresholds.bottleneck_speed_reduction_percent}%</p>
              <p className="text-xs text-muted mt-1">Speed drop to trigger</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CongestionPage
