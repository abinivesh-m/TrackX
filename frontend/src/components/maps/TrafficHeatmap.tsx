import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { HeatmapPoint } from '@/types'
import { MAP_TILE_URL, MAP_TILE_ATTRIBUTION } from '@/config/mapTiles'

interface TrafficHeatmapProps {
  points: HeatmapPoint[]
  height?: number
}

const TrafficHeatmap = ({ points, height = 360 }: TrafficHeatmapProps) => {
  const mapRef = useRef<L.Map | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    if (!mapRef.current) {
      mapRef.current = L.map(containerRef.current, { center: [11.0168, 76.9558], zoom: 13 })
      L.tileLayer(MAP_TILE_URL, {
        attribution: MAP_TILE_ATTRIBUTION,
      }).addTo(mapRef.current)
    }

    layerRef.current?.remove()
    const layer = L.layerGroup().addTo(mapRef.current)
    layerRef.current = layer
    const maxIntensity = Math.max(...points.map(point => point.intensity), 1)
    const bounds: L.LatLngExpression[] = []

    points.forEach(point => {
      if (point.intensity <= 0) return
      const ratio = point.intensity / maxIntensity
      const color = ratio > 0.66 ? '#ef4444' : ratio > 0.33 ? '#f59e0b' : '#10b981'
      const center: L.LatLngExpression = [point.latitude, point.longitude]
      bounds.push(center)
      L.circle(center, {
        color,
        fillColor: color,
        fillOpacity: 0.25 + ratio * 0.45,
        radius: 80 + ratio * 260,
        weight: 2,
      }).bindPopup(
        `<strong>${point.camera_id}</strong><br/>Traffic intensity: ${point.intensity}<br/>` +
        `Average speed: ${point.average_speed == null ? 'Insufficient data' : `${point.average_speed} km/h`}`,
      ).addTo(layer)
    })

    if (bounds.length) mapRef.current.fitBounds(L.latLngBounds(bounds).pad(0.15))
    return () => {
      layer.remove()
    }
  }, [points])

  return <div ref={containerRef} style={{ height: `${height}px`, width: '100%' }} className="rounded-lg overflow-hidden" />
}

export default TrafficHeatmap
