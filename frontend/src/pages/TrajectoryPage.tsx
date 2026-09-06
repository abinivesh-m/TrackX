import React, { useState, useEffect, useRef } from 'react'
import { api } from '@/services/api'
import { Search, Route, Navigation, Clock, AlertTriangle, ShieldCheck, ArrowRight } from 'lucide-react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const TrajectoryPage: React.FC = () => {
  const [plateQuery, setPlateQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [trajectoryData, setTrajectoryData] = useState<any>(null)
  const [recentTrips, setRecentTrips] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)

  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerGroupRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    loadRecent()
  }, [])

  const loadRecent = async () => {
    try {
      const recent = await api.getRecentTrajectories(10)
      setRecentTrips(recent || [])
    } catch (e) {
      console.error('Failed to load recent journeys', e)
    }
  }

  const handleSearch = async (plateToSearch?: string) => {
    const q = (plateToSearch || plateQuery).trim()
    if (!q) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.searchTrajectory(q)
      if (res && res.trajectory && res.trajectory.length > 0) {
        setTrajectoryData(res)
      } else {
        setTrajectoryData(null)
        setError("No multi-camera trajectory observations recorded for plate " + q.toUpperCase())
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to search trajectory')
      setTrajectoryData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!mapContainerRef.current) return

    if (!mapRef.current) {
      mapRef.current = L.map(mapContainerRef.current, {
        center: [18.5204, 73.8567],
        zoom: 12,
      })
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
      }).addTo(mapRef.current)
      layerGroupRef.current = L.layerGroup().addTo(mapRef.current)
    }

    if (layerGroupRef.current) {
      layerGroupRef.current.clearLayers()
    }

    if (trajectoryData && trajectoryData.trajectory && trajectoryData.trajectory.length > 0) {
      const hops = trajectoryData.trajectory
      const latlngs: L.LatLngExpression[] = []

      hops.forEach((hop: any, idx: number) => {
        const pt: [number, number] = [hop.lat, hop.lng]
        latlngs.push(pt)

        const isStart = idx === 0
        const isEnd = idx === hops.length - 1
        const color = isStart ? '#10b981' : isEnd ? '#ef4444' : '#3b82f6'

        const icon = L.divIcon({
          className: 'custom-trajectory-hop',
          html: '<div style="background: ' + color + '; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; border: 2px solid white; box-shadow: 0 0 8px ' + color + ';">' + (idx + 1) + '</div>',
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        })

        const marker = L.marker(pt, { icon }).bindPopup(
          '<div style="color: #222; font-family: sans-serif; font-size: 12px;">' +
            '<strong>Hop #' + (idx + 1) + ': ' + hop.camera_name + ' (' + hop.camera_id + ')</strong><br/>' +
            'Time: ' + (hop.timestamp ? new Date(hop.timestamp).toLocaleTimeString() : 'N/A') + '<br/>' +
            'Confidence: ' + (hop.confidence * 100).toFixed(1) + '%<br/>' +
            (hop.speed_kmh ? 'Leg Speed: <b>' + hop.speed_kmh + ' km/h</b>' : '') +
          '</div>'
        )
        layerGroupRef.current?.addLayer(marker)
      })

      if (latlngs.length > 1) {
        const polyline = L.polyline(latlngs, {
          color: '#60a5fa',
          weight: 4,
          dashArray: '8, 8',
          opacity: 0.9
        })
        layerGroupRef.current?.addLayer(polyline)
      }

      if (latlngs.length > 0) {
        mapRef.current.fitBounds(L.latLngBounds(latlngs).pad(0.15))
      }
    }
  }, [trajectoryData])

  return (
    <div className="space-y-6">
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center justify-between text-amber-300 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span><b>DEMO MODE (SIH-26127):</b> Multi-camera trajectory tracking powered by high-accuracy ANPR & graph correlation.</span>
        </div>
        <span className="text-xs bg-amber-500/20 px-2 py-0.5 rounded font-mono">BEL PROTOTYPE</span>
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Route className="text-blue-400" />
            Multi-Camera Trajectory Reconstruction
          </h1>
          <p className="text-sm text-muted">Reconstruct exact vehicle route, speed profiles, and anomaly alerts across city cameras.</p>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); handleSearch(); }} className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={18} />
            <input
              type="text"
              placeholder="Enter Indian plate (e.g. MH12DE1433)..."
              value={plateQuery}
              onChange={(e) => setPlateQuery(e.target.value)}
              className="bg-surface border border-border rounded-lg pl-9 pr-4 py-2 text-white text-sm focus:outline-none focus:border-blue-500 w-64 md:w-80 uppercase"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? 'Tracing...' : 'Trace Vehicle'}
          </button>
        </form>
      </div>

      {error && (
        <div className="card p-4 border-red-500/40 bg-red-500/10 text-red-300 text-sm flex items-center gap-2">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {trajectoryData && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card p-4">
              <span className="text-xs text-muted">Target Vehicle Plate</span>
              <p className="text-xl font-bold text-white font-mono mt-1">{trajectoryData.plate}</p>
              <span className="text-xs text-blue-400">Verified Indian Plate</span>
            </div>
            <div className="card p-4">
              <span className="text-xs text-muted">Corridor Cameras Logged</span>
              <p className="text-xl font-bold text-white mt-1">{trajectoryData.observation_count} Hops</p>
              <span className="text-xs text-green-400">Multi-Camera Verified</span>
            </div>
            <div className="card p-4">
              <span className="text-xs text-muted">Journey Distance & Time</span>
              <p className="text-xl font-bold text-white mt-1">{trajectoryData.total_distance_km} km / {trajectoryData.total_duration_min} min</p>
              <span className="text-xs text-muted">GPS Coordinate Graph</span>
            </div>
            <div className="card p-4">
              <span className="text-xs text-muted">Average Speed</span>
              <p className="text-xl font-bold text-white mt-1">{trajectoryData.average_speed_kmh} km/h</p>
              {trajectoryData.anomaly_flags && trajectoryData.anomaly_flags.length > 0 ? (
                <span className="text-xs text-red-400 flex items-center gap-1 mt-1"><AlertTriangle size={12}/> Anomaly Flagged</span>
              ) : (
                <span className="text-xs text-green-400 flex items-center gap-1 mt-1"><ShieldCheck size={12}/> Normal Speed</span>
              )}
            </div>
          </div>

          {trajectoryData.anomaly_flags && trajectoryData.anomaly_flags.length > 0 && (
            <div className="card p-4 border-red-500/40 bg-red-500/10">
              <h3 className="text-sm font-bold text-red-400 flex items-center gap-2">
                <AlertTriangle size={16} /> Route Anomalies Detected
              </h3>
              <ul className="list-disc list-inside text-xs text-red-300 mt-2 space-y-1">
                {trajectoryData.anomaly_flags.map((ano: string, i: number) => (
                  <li key={i}>{ano}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 card p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Navigation size={16} className="text-blue-400" /> GIS Trajectory Route Map
                </h3>
                <span className="text-xs text-muted">Dark Basemap &bull; Real Corridors</span>
              </div>
              <div ref={mapContainerRef} className="h-[440px] w-full rounded-lg" />
            </div>

            <div className="card p-4 space-y-4 max-h-[500px] overflow-y-auto">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Clock size={16} className="text-blue-400" /> Chronological Sighting Sequence
              </h3>
              <div className="space-y-3 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
                {trajectoryData.trajectory.map((hop: any, idx: number) => (
                  <div key={idx} className="relative pl-8 text-xs">
                    <div className="absolute left-1.5 top-1.5 w-3 h-3 rounded-full bg-blue-500 border-2 border-surface" />
                    <div className="bg-surface-light p-2.5 rounded border border-border">
                      <div className="flex items-center justify-between font-bold text-white">
                        <span>{hop.camera_name}</span>
                        <span className="text-muted">{hop.timestamp ? new Date(hop.timestamp).toLocaleTimeString() : 'N/A'}</span>
                      </div>
                      <div className="text-muted text-[11px] mt-1 flex items-center justify-between">
                        <span>Camera: {hop.camera_id}</span>
                        <span className="text-green-400">OCR Conf: {(hop.confidence * 100).toFixed(0)}%</span>
                      </div>
                      {hop.distance_from_prev_km != null && (
                        <div className="mt-1.5 pt-1.5 border-t border-border/50 text-blue-300 text-[11px] flex justify-between">
                          <span>Hop Distance: {hop.distance_from_prev_km} km</span>
                          <span>Hop Speed: {hop.speed_kmh} km/h</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-white">Recent Multi-Camera Journeys</h2>
            <p className="text-xs text-muted">Select any detected vehicle to immediately map its multi-camera trajectory.</p>
          </div>
          <span className="text-xs text-green-400">{recentTrips.length} Active Corridors</span>
        </div>

        {recentTrips.length === 0 ? (
          <div className="text-center py-8 text-muted text-sm">No multi-camera trips logged yet. Run inference demo to populate.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-muted">
              <thead className="text-xs text-muted uppercase bg-surface-light border-b border-border">
                <tr>
                  <th className="px-4 py-3">Plate Number</th>
                  <th className="px-4 py-3">Hops Count</th>
                  <th className="px-4 py-3">Origin &rarr; Destination</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Last Seen</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recentTrips.map((trip: any, idx: number) => (
                  <tr key={idx} className="hover:bg-surface-light/50 transition-colors">
                    <td className="px-4 py-3 font-mono font-bold text-white">{trip.plate}</td>
                    <td className="px-4 py-3 text-blue-400">{trip.observation_count} cameras</td>
                    <td className="px-4 py-3">{trip.start_camera} &rarr; {trip.end_camera}</td>
                    <td className="px-4 py-3">{trip.duration_minutes} mins</td>
                    <td className="px-4 py-3 text-xs">{trip.last_seen ? new Date(trip.last_seen).toLocaleTimeString() : 'N/A'}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => { setPlateQuery(trip.plate); handleSearch(trip.plate); }}
                        className="text-xs bg-blue-600/20 text-blue-400 hover:bg-blue-600/40 px-3 py-1.5 rounded transition-colors font-medium flex items-center gap-1 ml-auto"
                      >
                        View Path <ArrowRight size={12}/>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default TrajectoryPage