// frontend/src/components/maps/TrajectoryMap.tsx
//
// The Vehicle Intelligence hero map. Renders trajectory.hops (one node per
// camera actually visited) and trajectory.segments (real road-graph-aware
// distance/speed/plausibility between consecutive hops, from
// intelligence/spatio_temporal.py via backend/app/api/v1/vehicles.py).
//
// This replaces a previous version of this component that read a
// `trajectory.trajectory_points` field the backend never actually returned
// - the map silently rendered nothing for every real search. Real
// coordinates and real segment data only; nothing here is invented when a
// value is missing (a hop with no lat/lng is skipped, not plotted at a
// fake location).

import React, { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Trajectory } from '@/types'
import { MAP_TILE_URL, MAP_TILE_ATTRIBUTION, MAP_TILE_MAX_ZOOM } from '@/config/mapTiles'

interface TrajectoryMapProps {
  trajectory: Trajectory
  height?: number
  selectedHopIndex?: number | null
  onSelectHop?: (index: number) => void
}

// Camera network is centered on Coimbatore (network/camera_network.py) -
// used only as a last-resort fallback when a trajectory has zero plottable
// hops, so the map never silently defaults to an unrelated city.
const FALLBACK_CENTER: [number, number] = [11.0168, 76.9558]

function formatTime(ts?: string) {
  if (!ts) return 'N/A'
  const d = new Date(ts)
  return isNaN(d.getTime()) ? ts : d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const TrajectoryMap: React.FC<TrajectoryMapProps> = ({ trajectory, height = 500, selectedHopIndex = null, onSelectHop }) => {
  const mapRef = useRef<L.Map | null>(null)
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const layerGroupRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!mapContainerRef.current) return

    const hops = (trajectory?.hops || []).filter((h) => h.lat != null && h.lng != null)

    if (!mapRef.current) {
      mapRef.current = L.map(mapContainerRef.current, {
        center: FALLBACK_CENTER,
        zoom: 13,
        preferCanvas: true,
      })
      L.tileLayer(MAP_TILE_URL, {
        attribution: MAP_TILE_ATTRIBUTION,
        maxZoom: MAP_TILE_MAX_ZOOM,
        minZoom: 4,
      }).addTo(mapRef.current)
      layerGroupRef.current = L.layerGroup().addTo(mapRef.current)
    }

    const layer = layerGroupRef.current
    const map = mapRef.current
    if (!layer || !map) return
    layer.clearLayers()

    if (hops.length === 0) {
      return
    }

    const points: L.LatLngExpression[] = hops.map((h) => [h.lat as number, h.lng as number])

    // Segments first (so markers draw on top). Each connects hop[i-1] -> hop[i].
    for (let i = 1; i < hops.length; i++) {
      const from = points[i - 1]
      const to = points[i]
      const seg = hops[i].segment_from_prev
      const isAnomalous = seg?.is_plausible === false
      const isSelected = selectedHopIndex === i || selectedHopIndex === i - 1

      const line = L.polyline([from, to], {
        color: isAnomalous ? '#ef4444' : '#3b82f6',
        weight: isSelected ? 5 : isAnomalous ? 4 : 3,
        opacity: isAnomalous ? 0.9 : 0.65,
        dashArray: isAnomalous ? undefined : '8, 8',
      })

      const segInfo = seg
        ? `Distance: <b>${seg.distance_km != null ? seg.distance_km.toFixed(2) + ' km' : 'unknown'}</b><br/>
           Speed: <b>${seg.required_speed_kmph != null ? seg.required_speed_kmph.toFixed(1) + ' km/h' : 'unknown'}</b><br/>
           Time: <b>${seg.elapsed_time_formatted || 'unknown'}</b>${isAnomalous ? `<br/><span style="color:#ef4444;font-weight:bold">⚠ ${seg.reason}</span>` : ''}`
        : 'Segment data unavailable'

      line.bindPopup(`<div style="color:#222;font-family:sans-serif;font-size:12px;min-width:200px;">
          <strong>${hops[i - 1].camera_name} → ${hops[i].camera_name}</strong><br/>${segInfo}
        </div>`)
      if (onSelectHop) line.on('click', () => onSelectHop(i))
      layer.addLayer(line)
    }

    // Markers
    hops.forEach((hop, idx) => {
      const isStart = idx === 0
      const isEnd = idx === hops.length - 1
      const hasAnomalyIntoHop = hop.segment_from_prev?.is_plausible === false
      const color = isStart ? '#10b981' : isEnd ? '#ef4444' : hasAnomalyIntoHop ? '#f59e0b' : '#3b82f6'
      const isSelected = selectedHopIndex === idx

      const icon = L.divIcon({
        className: 'trajectory-hop-marker',
        html: `<div style="
            background:${color};color:#fff;width:${isSelected ? 30 : 24}px;height:${isSelected ? 30 : 24}px;
            border-radius:50%;display:flex;align-items:center;justify-content:center;
            font-size:11px;font-weight:bold;border:2px solid #fff;
            box-shadow:0 0 ${isSelected ? 14 : 8}px ${color};">${idx + 1}</div>`,
        iconSize: [isSelected ? 30 : 24, isSelected ? 30 : 24],
        iconAnchor: [isSelected ? 15 : 12, isSelected ? 15 : 12],
      })

      const marker = L.marker([hop.lat as number, hop.lng as number], { icon }).bindPopup(`
        <div style="color:#222;font-family:sans-serif;font-size:12px;min-width:190px;">
          <strong>${isStart ? 'START — ' : isEnd ? 'END — ' : ''}${hop.camera_name}</strong> (${hop.camera_id})<br/>
          Time: ${formatTime(hop.timestamp)}<br/>
          ${hop.direction && hop.direction !== 'unknown' ? `Direction: ${hop.direction.replace(/_/g, ' ')}<br/>` : ''}
          ${hop.confidence != null ? `Confidence: <span style="color:#16a34a">${(hop.confidence * 100).toFixed(0)}%</span><br/>` : ''}
          ${hasAnomalyIntoHop ? `<span style="color:#ef4444;font-weight:bold">⚠ Anomalous arrival</span>` : ''}
        </div>
      `)
      if (onSelectHop) marker.on('click', () => onSelectHop(idx))
      layer.addLayer(marker)
    })

    if (points.length > 0) {
      map.fitBounds(L.latLngBounds(points).pad(0.15), { animate: false })
    }
  }, [trajectory, selectedHopIndex])

  const hasPlottableHops = (trajectory?.hops || []).some((h) => h.lat != null && h.lng != null)

  return (
    <div className="relative" style={{ height: `${height}px`, width: '100%', minHeight: '300px' }}>
      <div ref={mapContainerRef} className="h-full w-full rounded-lg overflow-hidden" />
      {!hasPlottableHops && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface/90 rounded-lg text-sm text-muted text-center px-6">
          No camera coordinates available to plot this trajectory.
        </div>
      )}
    </div>
  )
}

export default TrajectoryMap
