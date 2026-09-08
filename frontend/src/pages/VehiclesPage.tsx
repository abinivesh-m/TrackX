// frontend/src/pages/VehiclesPage.tsx
//
// Vehicle Intelligence - the hero experience of TrackX:
//   plate -> observations -> camera sequence -> GIS trajectory ->
//   distance/time/speed -> route anomaly / alerts.
//
// Every field rendered here comes from a real API response
// (backend/app/api/v1/vehicles.py) - nothing is fabricated. A vehicle with
// no observations gets an explanatory empty state, never invented data.

import React, { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/services/api'
import {
  Search,
  Loader2,
  Car,
  MapPin,
  Clock,
  AlertTriangle,
  Navigation,
  XCircle,
  ShieldAlert,
  Gauge,
  Route as RouteIcon,
  ShieldCheck,
  Video,
  Eye,
} from 'lucide-react'
import TrajectoryMap from '@/components/maps/TrajectoryMap'
import type { VehicleSearchResponse, RouteAnomaly, TrajectoryHop } from '@/types'
import { toast } from 'react-toastify'
import { Link } from 'react-router-dom'

const VehiclesPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const [searchQuery, setSearchQuery] = useState(searchParams.get('plate') || '')
  const [searchResults, setSearchResults] = useState<VehicleSearchResponse | null>(null)
  const [routeAnomalies, setRouteAnomalies] = useState<RouteAnomaly[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [selectedHopIndex, setSelectedHopIndex] = useState<number | null>(null)

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault()

    if (!searchQuery.trim()) {
      toast.error('Please enter a license plate')
      return
    }

    setIsLoading(true)
    setHasSearched(true)
    setSelectedHopIndex(null)

    try {
      const results = await api.searchVehicle({ plate: searchQuery.trim() })
      setSearchResults(results)

      try {
        const anomalies = await api.getRouteAnomalies({ plate: searchQuery.trim(), limit: 10 })
        setRouteAnomalies(anomalies)
      } catch (anomalyError) {
        console.error('Failed to load route anomalies:', anomalyError)
        setRouteAnomalies([])
      }

      if (!results.vehicle_found) {
        toast.info('No observations found for this plate')
      } else {
        toast.success(`Found ${results.observations.length} observation(s) across ${results.trajectory?.camera_count ?? '?'} camera(s)`)
      }
    } catch (error) {
      console.error('Search failed:', error)
      toast.error('Search failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return dateString
    return date.toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }

  const getRiskBadge = (risk?: string) => {
    switch (risk) {
      case 'HIGH': return 'bg-red-500/20 text-red-400 border border-red-500/30'
      case 'MEDIUM': return 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
      default: return 'bg-green-500/20 text-green-400 border border-green-500/30'
    }
  }

  const trajectory = searchResults?.trajectory
  const hops: TrajectoryHop[] = trajectory?.hops || []
  const found = !!searchResults?.vehicle_found

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded-lg p-3 flex items-center gap-2 text-sm text-muted">
        <span className="w-2 h-2 rounded-full bg-green-400" />
        <span>Search a plate to reconstruct its multi-camera trajectory from stored observations.</span>
      </div>

      <h1 className="text-2xl font-bold text-white">Vehicle Intelligence</h1>

      {/* Search Bar */}
      <div className="card p-6">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={20} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter license plate (e.g., TN38AB1234)"
              className="w-full pl-10 pr-4 py-3 rounded-lg bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-white uppercase"
              autoFocus
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isLoading ? <Loader2 className="animate-spin" size={20} /> : <Search size={20} />}
            Search
          </button>
        </form>
      </div>

      {/* Empty states */}
      {hasSearched && !isLoading && !found && (
        <div className="card p-10 text-center">
          <Car size={40} className="mx-auto mb-3 text-muted opacity-40" />
          <h3 className="text-white font-semibold mb-1">No vehicle observations found for this period.</h3>
          <p className="text-sm text-muted max-w-md mx-auto">
            "{searchQuery.toUpperCase()}" hasn't been seen by any camera in the current dataset. Try one of the
            seeded demo plates (e.g. TN38AB1234) or check the plate for typos.
          </p>
        </div>
      )}

      {hasSearched && found && trajectory && (
        <>
          {/* Blacklist / risk banner */}
          {trajectory.is_blacklisted && (
            <div className="card p-4 border-red-500/40 bg-red-500/10 flex items-start gap-3">
              <ShieldAlert className="text-red-400 shrink-0 mt-0.5" size={20} />
              <div>
                <p className="text-sm font-semibold text-red-300">Operator watchlist match — requires operator review</p>
                <p className="text-xs text-red-300/80 mt-0.5">
                  Severity: {trajectory.blacklist_severity || 'N/A'}
                  {trajectory.blacklist_reason ? ` — ${trajectory.blacklist_reason}` : ''}
                </p>
              </div>
            </div>
          )}

          {/* 1. Vehicle summary + 2. Journey metrics */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="card p-5 lg:col-span-1">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-blue-600/20 flex items-center justify-center">
                  <Car size={22} className="text-blue-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white font-mono">{trajectory.plate_text}</h2>
                  <span className={`text-[11px] px-2 py-0.5 rounded-full ${getRiskBadge(trajectory.risk_level)}`}>
                    {trajectory.risk_level || 'LOW'}
                  </span>
                </div>
              </div>
              <dl className="space-y-2 text-xs">
                <Row label="Vehicle Type" value={trajectory.vehicle_type ? cap(trajectory.vehicle_type) : 'Unknown'} />
                <Row label="First Seen" value={formatDate(trajectory.first_seen)} />
                <Row label="Last Seen" value={formatDate(trajectory.last_seen)} />
                <Row label="Cameras Visited" value={String(trajectory.camera_count)} />
                <Row label="Observations" value={String(trajectory.observation_count)} />
              </dl>
            </div>

            <StatCard icon={<RouteIcon size={16} />} label="Total Distance" value={`${trajectory.total_distance_km ?? 0} km`} />
            <StatCard icon={<Clock size={16} />} label="Travel Time" value={trajectory.total_journey_time || '—'} />
            <StatCard
              icon={<Gauge size={16} />}
              label="Avg Speed"
              value={`${trajectory.average_speed_kmh ?? 0} km/h`}
              sub={
                trajectory.trajectory_confidence != null
                  ? `Trajectory confidence: ${trajectory.trajectory_confidence}%`
                  : 'Single observation — no link confidence yet'
              }
            />
          </div>

          {/* 3. GIS TRAJECTORY MAP - HERO */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Navigation size={18} className="text-blue-400" /> Reconstructed Trajectory
              </h3>
              <div className="flex items-center gap-3 text-[11px] text-muted">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500 inline-block" /> Start</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> End</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> Anomalous arrival</span>
              </div>
            </div>
            <TrajectoryMap trajectory={trajectory} height={560} selectedHopIndex={selectedHopIndex} onSelectHop={setSelectedHopIndex} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 4. Observation timeline (one row per camera visit = one map hop) */}
            <div className="card p-5">
              <h3 className="text-sm font-bold text-white mb-3">Observation Timeline</h3>
              {hops.length === 0 ? (
                <p className="text-sm text-muted">No camera visits to display.</p>
              ) : (
                <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
                  {hops.map((hop, idx) => {
                    const isStart = idx === 0
                    const isEnd = idx === hops.length - 1
                    const seg = hop.segment_from_prev
                    const anomalous = seg?.is_plausible === false
                    return (
                      <div key={idx}>
                        {seg && (
                          <div className={`ml-4 pl-4 border-l-2 text-[11px] py-1.5 ${anomalous ? 'border-red-500/60 text-red-300' : 'border-border text-muted'}`}>
                            {anomalous ? <AlertTriangle size={11} className="inline mr-1" /> : null}
                            {seg.distance_km != null ? `${seg.distance_km.toFixed(2)} km` : 'distance unknown'} •{' '}
                            {seg.required_speed_kmph != null ? `${seg.required_speed_kmph.toFixed(1)} km/h` : ''} •{' '}
                            {seg.elapsed_time_formatted || ''}
                            {anomalous && <span className="block mt-0.5">{seg.reason}</span>}
                          </div>
                        )}
                        <button
                          onClick={() => setSelectedHopIndex(idx)}
                          className={`w-full text-left flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                            selectedHopIndex === idx
                              ? 'border-blue-500/60 bg-blue-500/10'
                              : 'border-border bg-surface-light hover:border-blue-500/30'
                          }`}
                        >
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                            isStart ? 'bg-green-500/20 text-green-400' : isEnd ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'
                          }`}>
                            {idx + 1}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-semibold text-white text-sm">{hop.camera_name}</span>
                              {isStart && <span className="text-[10px] text-green-400 uppercase">Start</span>}
                              {isEnd && <span className="text-[10px] text-red-400 uppercase">End</span>}
                            </div>
                            <div className="text-[11px] text-muted mt-0.5 flex flex-wrap items-center gap-x-2">
                              <span className="flex items-center gap-1"><Clock size={10} />{formatDate(hop.timestamp)}</span>
                              {hop.direction && hop.direction !== 'unknown' && (
                                <span className="flex items-center gap-1"><Navigation size={10} />{hop.direction.replace(/_/g, ' ')}</span>
                              )}
                              {hop.plate_confidence != null && <span>Plate conf: {(hop.plate_confidence * 100).toFixed(0)}%</span>}
                              {hop.vehicle_confidence != null && <span>Vehicle conf: {(hop.vehicle_confidence * 100).toFixed(0)}%</span>}
                            </div>
                          </div>
                          {hop.plate_crop_url ? (
                            <img src={hop.plate_crop_url} alt="Plate crop" className="w-14 h-10 object-cover rounded border border-border shrink-0" />
                          ) : (
                            <Eye size={16} className="text-muted shrink-0" />
                          )}
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* 6. Intelligence */}
            <div className="space-y-4">
              <div className="card p-5">
                <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                  <ShieldAlert size={16} className="text-amber-400" /> Intelligence Summary
                </h3>
                <div className="space-y-2 text-xs">
                  <IntelRow
                    ok={!trajectory.is_blacklisted}
                    okLabel="No watchlist match"
                    badLabel="Operator watchlist match — requires operator review"
                  />
                  <IntelRow
                    ok={!trajectory.anomalous_segment_count}
                    okLabel="No route anomalies on this journey"
                    badLabel={`${trajectory.anomalous_segment_count} segment(s) flagged as a suspicious movement pattern`}
                  />
                  <IntelRow
                    ok={trajectory.trajectory_confidence == null || trajectory.trajectory_confidence >= 75}
                    okLabel={trajectory.trajectory_confidence != null ? `High trajectory-link confidence (${trajectory.trajectory_confidence}%)` : 'Single observation — nothing to link yet'}
                    badLabel={`Lower-confidence camera linking (${trajectory.trajectory_confidence}%) — treat this route as tentative`}
                    neutral={trajectory.trajectory_confidence == null}
                  />
                </div>
              </div>

              {routeAnomalies.length > 0 && (
                <div className="card p-5 border-red-500/30 bg-red-500/5">
                  <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                    <AlertTriangle className="text-red-400" size={16} />
                    Recorded Route Anomalies ({routeAnomalies.length})
                  </h3>
                  <div className="space-y-3">
                    {routeAnomalies.map((anomaly) => (
                      <div key={anomaly.anomaly_id} className="p-3 rounded-lg bg-surface-light border border-red-500/30 text-xs">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-bold text-white">{anomaly.from_camera} → {anomaly.to_camera}</span>
                          <span className={`px-2 py-0.5 rounded-full ${
                            anomaly.severity === 'HIGH' || anomaly.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                            anomaly.severity === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400' : 'bg-blue-500/20 text-blue-400'
                          }`}>
                            {anomaly.severity}
                          </span>
                        </div>
                        <div className="text-muted space-y-1">
                          {anomaly.details?.unexpected_transition && (
                            <div className="flex items-center gap-1 text-red-300"><XCircle size={12} /> Unexpected camera transition</div>
                          )}
                          {anomaly.details?.impossible_travel_time && (
                            <div className="flex items-center gap-1 text-red-300"><AlertTriangle size={12} /> Impossible travel time</div>
                          )}
                          {anomaly.details?.unreasonable_speed && (
                            <div className="flex items-center gap-1 text-amber-300"><Navigation size={12} /> Unreasonable speed</div>
                          )}
                        </div>
                        <div className="flex items-center justify-between mt-2 text-[11px] text-muted">
                          <span>{formatDate(anomaly.timestamp)}</span>
                          <span className={`px-2 py-0.5 rounded-full ${
                            anomaly.status === 'OPEN' ? 'bg-red-500/20 text-red-400' :
                            anomaly.status === 'UNDER_INVESTIGATION' ? 'bg-amber-500/20 text-amber-400' :
                            'bg-green-500/20 text-green-400'
                          }`}>
                            {anomaly.status.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <Link
                to="/trajectory"
                className="card p-4 flex items-center justify-between text-sm text-muted hover:text-white hover:border-blue-500/40 transition-colors"
              >
                <span className="flex items-center gap-2"><Video size={14} /> Open full Trajectory Search for more detail</span>
                <span>→</span>
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

const Row: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex items-center justify-between">
    <dt className="text-muted">{label}</dt>
    <dd className="text-white font-medium text-right">{value}</dd>
  </div>
)

const StatCard: React.FC<{ icon: React.ReactNode; label: string; value: string; sub?: string }> = ({ icon, label, value, sub }) => (
  <div className="card p-5 flex flex-col justify-center">
    <span className="text-[11px] text-muted uppercase tracking-wide flex items-center gap-1.5">{icon}{label}</span>
    <span className="text-2xl font-bold text-white mt-1">{value}</span>
    {sub && <span className="text-[11px] text-muted mt-1">{sub}</span>}
  </div>
)

const IntelRow: React.FC<{ ok: boolean; okLabel: string; badLabel: string; neutral?: boolean }> = ({ ok, okLabel, badLabel, neutral }) => (
  <div className={`flex items-start gap-2 p-2.5 rounded-lg ${neutral ? 'bg-surface-light text-muted' : ok ? 'bg-green-500/10 text-green-300' : 'bg-red-500/10 text-red-300'}`}>
    {neutral ? <MapPin size={14} className="mt-0.5 shrink-0" /> : ok ? <ShieldCheck size={14} className="mt-0.5 shrink-0" /> : <AlertTriangle size={14} className="mt-0.5 shrink-0" />}
    <span>{neutral ? okLabel : ok ? okLabel : badLabel}</span>
  </div>
)

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export default VehiclesPage
