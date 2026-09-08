import React, { useState, useEffect, useRef } from 'react'
import { api } from '@/services/api'
import { Map, Layers, Camera, AlertTriangle, ArrowRightLeft, RefreshCw } from 'lucide-react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const GISPage: React.FC = () => {
  const [cameras, setCameras] = useState<any[]>([])
  const [heatmap, setHeatmap] = useState<any>(null)
  const [congestion, setCongestion] = useState<any[]>([])
  const [flows, setFlows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  // Layer toggles
  const [showCameras, setShowCameras] = useState(true)
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [showCongestion, setShowCongestion] = useState(true)
  const [showFlows, setShowFlows] = useState(true)

  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const cameraLayerRef = useRef<L.LayerGroup | null>(null)
  const heatLayerRef = useRef<L.LayerGroup | null>(null)
  const congestionLayerRef = useRef<L.LayerGroup | null>(null)
  const flowLayerRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    loadGISData()
  }, [])

  const loadGISData = async () => {
    setLoading(true)
    try {
      const [cams, heat, cong, flws] = await Promise.all([
        api.getGISCameras(),
        api.getGISHeatmap(),
        api.getGISCongestion(),
        api.getGISFlow(),
      ])
      setCameras(cams || [])
      setHeatmap(heat || null)
      setCongestion(cong || [])
      setFlows(flws || [])
    } catch (err) {
      console.error('Failed to load GIS layers', err)
    } finally {
      setLoading(false)
    }
  }

  // Initialize Map
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

      cameraLayerRef.current = L.layerGroup().addTo(mapRef.current)
      heatLayerRef.current = L.layerGroup().addTo(mapRef.current)
      congestionLayerRef.current = L.layerGroup().addTo(mapRef.current)
      flowLayerRef.current = L.layerGroup().addTo(mapRef.current)
    }
  }, [])

  // Update Camera Layer
  useEffect(() => {
    if (!cameraLayerRef.current) return
    cameraLayerRef.current.clearLayers()
    if (!showCameras) return

    cameras.forEach((cam) => {
      const icon = L.divIcon({
        className: 'custom-gis-cam',
        html: '<div style="background: #3b82f6; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px #3b82f6;"></div>',
        iconSize: [14, 14],
        iconAnchor: [7, 7]
      })

      const marker = L.marker([cam.lat, cam.lng], { icon }).bindPopup(
        '<div style="color: #222; font-family: sans-serif; font-size: 12px; min-width: 180px;">' +
          '<strong>' + cam.name + ' (' + cam.camera_id + ')</strong><br/>' +
          'Road: ' + cam.road + '<br/>' +
          'Direction: ' + cam.direction + '<br/>' +
          'Observations: <b>' + cam.observation_count + '</b><br/>' +
          'Reliability: ' + (cam.reliability * 100).toFixed(0) + '%' +
        '</div>'
      )
      cameraLayerRef.current?.addLayer(marker)
    })
  }, [cameras, showCameras])

  // Update Heatmap / Density Circles Layer
  useEffect(() => {
    if (!heatLayerRef.current) return
    heatLayerRef.current.clearLayers()
    if (!showHeatmap || !heatmap?.points) return

    heatmap.points.forEach((pt: [number, number, number]) => {
      const [lat, lng, weight] = pt
      const radius = 250 + weight * 450
      const color = weight > 0.7 ? '#ef4444' : weight > 0.4 ? '#f59e0b' : '#10b981'

      const circle = L.circle([lat, lng], {
        radius,
        fillColor: color,
        color: color,
        weight: 1,
        opacity: 0.8,
        fillOpacity: 0.25 + weight * 0.35
      }).bindPopup(
        '<div style="color: #222; font-size: 11px;">Traffic Density Intensity: <b>' + (weight * 100).toFixed(0) + '%</b></div>'
      )
      heatLayerRef.current?.addLayer(circle)
    })
  }, [heatmap, showHeatmap])

  // Update Congestion Layer
  useEffect(() => {
    if (!congestionLayerRef.current) return
    congestionLayerRef.current.clearLayers()
    if (!showCongestion) return

    congestion.forEach((cong) => {
      const isHigh = cong.level === 'HIGH'
      const color = isHigh ? '#ef4444' : '#f59e0b'

      const icon = L.divIcon({
        className: 'custom-gis-cong',
        html: '<div style="background: ' + color + '; color: white; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; border: 2px solid white; box-shadow: 0 0 12px ' + color + ';">!</div>',
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      })

      const marker = L.marker([cong.lat, cong.lng], { icon }).bindPopup(
        '<div style="color: #222; font-family: sans-serif; font-size: 12px;">' +
          '<strong style="color: ' + color + ';">' + cong.level + ' CONGESTION BOTTLENECK</strong><br/>' +
          '<b>' + cong.camera_name + '</b> (' + cong.camera_id + ')<br/>' +
          'Traffic Volume: <b>' + cong.vehicle_count + ' vehicles</b><br/>' +
          'Congestion Score: ' + (cong.score * 100).toFixed(0) + '/100' +
        '</div>'
      )
      congestionLayerRef.current?.addLayer(marker)
    })
  }, [congestion, showCongestion])

  // Update OD Flow Layer
  useEffect(() => {
    if (!flowLayerRef.current) return
    flowLayerRef.current.clearLayers()
    if (!showFlows) return

    flows.forEach((flow) => {
      const line = L.polyline([
        [flow.origin_lat, flow.origin_lng],
        [flow.dest_lat, flow.dest_lng]
      ], {
        color: '#818cf8',
        weight: Math.min(Math.max(flow.count * 1.5, 2), 6),
        opacity: 0.75,
        dashArray: '6, 6'
      }).bindPopup(
        '<div style="color: #222; font-size: 12px;">' +
          '<strong>Route: ' + flow.origin_name + ' &rarr; ' + flow.dest_name + '</strong><br/>' +
          'Vehicle Flow Volume: <b>' + flow.count + ' trips</b>' +
        '</div>'
      )
      flowLayerRef.current?.addLayer(line)
    })
  }, [flows, showFlows])

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded-lg p-3 flex items-center justify-between text-sm text-muted">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          <span>Geographic Information System (GIS) traffic analytics &amp; multi-layer correlation.</span>
        </div>
        <button
          onClick={loadGISData}
          disabled={loading}
          className="text-xs bg-surface-light hover:bg-border px-3 py-1 rounded font-medium flex items-center gap-1 border border-border"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh Data
        </button>
      </div>

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Map className="text-blue-400" />
            GIS Command Map & Urban Traffic Topology
          </h1>
          <p className="text-sm text-muted">City-wide traffic density, congestion hotspots, camera positions, and OD flows - computed fresh from stored observations each time this page loads.</p>
        </div>

        {/* Layer Toggles Bar */}
        <div className="flex items-center gap-2 bg-surface p-1.5 rounded-lg border border-border text-xs">
          <span className="text-muted flex items-center gap-1 px-2 font-medium"><Layers size={14}/> Layers:</span>
          <button
            onClick={() => setShowCameras(!showCameras)}
            className={`px-2.5 py-1 rounded transition-colors ${showCameras ? 'bg-blue-600 text-white' : 'text-muted hover:text-white'}`}
          >
            Cameras ({cameras.length})
          </button>
          <button
            onClick={() => setShowHeatmap(!showHeatmap)}
            className={`px-2.5 py-1 rounded transition-colors ${showHeatmap ? 'bg-green-600 text-white' : 'text-muted hover:text-white'}`}
          >
            Density Heatmap
          </button>
          <button
            onClick={() => setShowCongestion(!showCongestion)}
            className={`px-2.5 py-1 rounded transition-colors ${showCongestion ? 'bg-red-600 text-white' : 'text-muted hover:text-white'}`}
          >
            Bottlenecks ({congestion.length})
          </button>
          <button
            onClick={() => setShowFlows(!showFlows)}
            className={`px-2.5 py-1 rounded transition-colors ${showFlows ? 'bg-indigo-600 text-white' : 'text-muted hover:text-white'}`}
          >
            OD Flows ({flows.length})
          </button>
        </div>
      </div>

      {/* Stats Summary - each figure below reads directly from this page's
          real GET /gis/* fetches (cameras/heatmap/congestion/flows state).
          A "Network Health 98.4% / AI Fusion Engine Online" card and a
          hardcoded "100% Operational Status" line used to sit here with no
          backing data at all - fabricated precision with nothing real
          behind it. Removed rather than replaced with another invented
          number; camera coverage now just states the real node count. */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <span className="text-xs text-muted flex items-center gap-1.5"><Camera size={14} className="text-blue-400"/> Camera Coverage</span>
          <p className="text-2xl font-bold text-white mt-1">{cameras.length} Nodes</p>
          <span className="text-xs text-muted">From camera network topology</span>
        </div>
        <div className="card p-4">
          <span className="text-xs text-muted flex items-center gap-1.5"><AlertTriangle size={14} className="text-red-400"/> Congestion Hotspots</span>
          <p className="text-2xl font-bold text-white mt-1">{congestion.length} Identified</p>
          <span className="text-xs text-red-400">{congestion.filter(c => c.level === 'HIGH').length} High Priority</span>
        </div>
        <div className="card p-4">
          <span className="text-xs text-muted flex items-center gap-1.5"><ArrowRightLeft size={14} className="text-indigo-400"/> Active OD Corridors</span>
          <p className="text-2xl font-bold text-white mt-1">{flows.length} Routes</p>
          <span className="text-xs text-muted">Cross-camera vehicle journeys</span>
        </div>
      </div>

      {/* Main Leaflet GIS Map */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-sm font-bold text-white">GIS Network View</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block"/> Camera</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block"/> Normal Flow</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"/> Bottleneck</span>
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-indigo-400 inline-block"/> Flow Corridor</span>
          </div>
        </div>
        <div ref={mapContainerRef} className="h-[520px] w-full rounded-lg" />
      </div>

      {/* Congestion Hotspots & Flow Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Hotspots */}
        <div className="card p-5">
          <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-400" /> Congestion Bottleneck Priority List
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-muted">
              <thead className="text-muted uppercase bg-surface-light border-b border-border">
                <tr>
                  <th className="px-3 py-2">Camera / Location</th>
                  <th className="px-3 py-2">Severity</th>
                  <th className="px-3 py-2">Volume</th>
                  <th className="px-3 py-2">Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {congestion.map((c, i) => (
                  <tr key={i} className="hover:bg-surface-light/50">
                    <td className="px-3 py-2.5 font-medium text-white">{c.camera_name} <span className="text-muted">({c.camera_id})</span></td>
                    <td className="px-3 py-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${c.level === 'HIGH' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'}`}>
                        {c.level}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-white">{c.vehicle_count} vehicles</td>
                    <td className="px-3 py-2.5 font-mono">{(c.score * 100).toFixed(0)}/100</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Origin Destination Flow */}
        <div className="card p-5">
          <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
            <ArrowRightLeft size={16} className="text-indigo-400" /> Top Origin &rarr; Destination Corridors
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-muted">
              <thead className="text-muted uppercase bg-surface-light border-b border-border">
                <tr>
                  <th className="px-3 py-2">Corridor Route</th>
                  <th className="px-3 py-2">Traffic Volume</th>
                  <th className="px-3 py-2">Directionality</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {flows.slice(0, 6).map((f, i) => (
                  <tr key={i} className="hover:bg-surface-light/50">
                    <td className="px-3 py-2.5 text-white font-medium">{f.origin_name} &rarr; {f.dest_name}</td>
                    <td className="px-3 py-2.5 text-indigo-400 font-bold">{f.count} trips</td>
                    <td className="px-3 py-2.5 text-muted">Bilateral Corridor</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

export default GISPage