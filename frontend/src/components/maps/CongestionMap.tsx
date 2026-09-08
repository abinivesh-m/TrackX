// frontend/src/components/maps/CongestionMap.tsx
//
// City-wide congestion map for the Traffic Analytics page. Plots real
// per-camera congestion readings from GET /api/v1/gis/congestion
// (backend/app/api/v1/gis.py - analytics.congestion_hotspots(), the same
// multi-factor density/speed model every other congestion number on this
// page comes from). No invented positions or scores - a camera with no
// congestion reading is simply not plotted, not shown as fake "clear".

import React, { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { GisCongestionPoint } from '@/types'
import { MAP_TILE_URL, MAP_TILE_ATTRIBUTION, MAP_TILE_MAX_ZOOM } from '@/config/mapTiles'

interface CongestionMapProps {
  points: GisCongestionPoint[]
  height?: number
}

const CENTER: [number, number] = [11.0168, 76.9558] // Coimbatore camera network center

function colorForLevel(level: string) {
  if (level === 'CONGESTED') return '#ef4444'
  if (level === 'MODERATE') return '#f59e0b'
  return '#10b981'
}

const CongestionMap: React.FC<CongestionMapProps> = ({ points, height = 460 }) => {
  const mapRef = useRef<L.Map | null>(null)
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!mapContainerRef.current) return

    if (!mapRef.current) {
      mapRef.current = L.map(mapContainerRef.current, {
        center: CENTER,
        zoom: 13,
        preferCanvas: true,
      })
      L.tileLayer(MAP_TILE_URL, {
        attribution: MAP_TILE_ATTRIBUTION,
        maxZoom: MAP_TILE_MAX_ZOOM,
        minZoom: 10,
      }).addTo(mapRef.current)
      layerRef.current = L.layerGroup().addTo(mapRef.current)
    }

    const layer = layerRef.current
    const map = mapRef.current
    if (!layer || !map) return
    layer.clearLayers()

    const plottable = points.filter((p) => p.lat != null && p.lng != null)
    plottable.forEach((p) => {
      const color = colorForLevel(p.level)
      const radius = 10 + Math.min(p.score, 1) * 14
      const marker = L.circleMarker([p.lat, p.lng], {
        radius,
        fillColor: color,
        color: '#fff',
        weight: 2,
        fillOpacity: 0.75,
      }).bindPopup(`
        <div style="color:#222;font-family:sans-serif;font-size:12px;min-width:190px;">
          <strong>${p.camera_name}</strong> (${p.camera_id})<br/>
          Level: <b style="color:${color}">${p.level}</b><br/>
          Congestion score: ${(p.score * 100).toFixed(1)}/100<br/>
          Vehicles observed: ${p.vehicle_count}
        </div>
      `)
      layer.addLayer(marker)
    })

    if (plottable.length > 0) {
      const bounds = L.latLngBounds(plottable.map((p) => [p.lat, p.lng] as L.LatLngExpression))
      map.fitBounds(bounds.pad(0.2), { animate: false })
    } else {
      map.setView(CENTER, 13)
    }
  }, [points])

  const hasData = points.some((p) => p.lat != null && p.lng != null)

  return (
    <div className="relative" style={{ height: `${height}px`, width: '100%', minHeight: '300px' }}>
      <div ref={mapContainerRef} className="h-full w-full rounded-lg overflow-hidden" />
      {!hasData && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface/90 rounded-lg text-sm text-muted text-center px-6">
          No congestion readings yet for any camera.
        </div>
      )}
    </div>
  )
}

export default CongestionMap
