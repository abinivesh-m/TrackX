// frontend/src/components/maps/CameraMap.tsx

import React, { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Camera } from '@/types'
import { MAP_TILE_URL, MAP_TILE_ATTRIBUTION, MAP_TILE_MAX_ZOOM, DEFAULT_MAP_CENTER } from '@/config/mapTiles'

// SIH26127 "physical vs media status" correction (2026-09-14): this map's
// marker color/popup used to read camera.status directly - the SAME
// observation-activity-derived field CamerasPage.tsx no longer uses as the
// primary badge (see that file's comment). A camera whose demo media was
// just processed could show a green "ONLINE" dot here even with no RTSP
// configured at all - indistinguishable from CAM_01's real physical
// connection. physicalStatusById (optional, keyed by camera_id) carries the
// SAME real, config/probe-derived status CamerasPage now shows on its
// cards; when the caller doesn't pass it (or hasn't loaded it yet for a
// given camera), markers fall back to a neutral "checking" gray rather than
// asserting a status that was never actually checked.
type PhysicalStatus = 'LIVE' | 'OFFLINE' | 'NOT_CONFIGURED' | 'CHECKING'

const PHYSICAL_COLORS: Record<PhysicalStatus, string> = {
  LIVE: '#3f9e5c',
  OFFLINE: '#c8473d',
  NOT_CONFIGURED: '#7a8699',
  CHECKING: '#7a8699',
}

const PHYSICAL_LABELS: Record<PhysicalStatus, string> = {
  LIVE: 'LIVE CAMERA',
  OFFLINE: 'Camera offline',
  NOT_CONFIGURED: 'Camera not configured (demo/camera media)',
  CHECKING: 'Checking…',
}

interface CameraMapProps {
  cameras: Camera[]
  height?: number
  physicalStatusById?: Record<string, PhysicalStatus>
}

const CameraMap: React.FC<CameraMapProps> = ({ cameras, height = 500, physicalStatusById }) => {
  const mapRef = useRef<L.Map | null>(null)
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const markersRef = useRef<L.Marker[]>([])
  const isInitializedRef = useRef(false)

  useEffect(() => {
    if (!mapContainerRef.current) return
    
    // Initialize map only once
    if (!mapRef.current && !isInitializedRef.current) {
      mapRef.current = L.map(mapContainerRef.current, {
        center: DEFAULT_MAP_CENTER, // Coimbatore, Tamil Nadu - see src/config/mapTiles.ts
        zoom: 13,
        preferCanvas: true, // Use canvas renderer for better performance
        renderer: L.canvas()
      })
      
      // Tile provider - see src/config/mapTiles.ts. Was a hardcoded CARTO
      // dark-tile URL whose anonymous endpoint started serving placeholder
      // tiles reading "API KEY REQUIRED" in production instead of real map
      // imagery; now a reliable no-key default (OpenStreetMap), still
      // environment-configurable via VITE_MAP_TILE_URL.
      L.tileLayer(MAP_TILE_URL, {
        attribution: MAP_TILE_ATTRIBUTION,
        maxZoom: MAP_TILE_MAX_ZOOM,
        minZoom: 10
      }).addTo(mapRef.current)
      
      isInitializedRef.current = true
    }
    
    // Add camera markers
    markersRef.current.forEach(marker => marker.remove())
    markersRef.current = []
    
    cameras.forEach(camera => {
      if (camera.latitude != null && camera.longitude != null) {
        const physical: PhysicalStatus = physicalStatusById?.[camera.camera_id] || 'CHECKING'
        const color = PHYSICAL_COLORS[physical]
        const icon = L.divIcon({
          className: 'custom-camera-icon',
          html: `<div style="
            background: ${color};
            width: 10px;
            height: 10px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 0 8px ${color};
          "></div>`,
          iconSize: [10, 10],
          iconAnchor: [5, 5]
        })

        const marker = L.marker([camera.latitude, camera.longitude], { icon })
          .addTo(mapRef.current!)
          .bindPopup(`
            <div style="color: #333; min-width: 200px;">
              <strong>${camera.camera_id}</strong><br/>
              ${camera.name}<br/>
              ${camera.location}<br/>
              Feed: ${PHYSICAL_LABELS[physical]}<br/>
              Observations logged: ${camera.observation_count || 0}
            </div>
          `)
        
        markersRef.current.push(marker)
      }
    })
    
    // Fit bounds if we have markers
    if (markersRef.current.length > 0) {
      const group = L.featureGroup(markersRef.current)
      mapRef.current?.fitBounds(group.getBounds().pad(0.1), { animate: false }) // Disable animation for performance
    }
    
    return () => {
      markersRef.current.forEach(marker => marker.remove())
    }
  }, [cameras, physicalStatusById])

  return (
    <div 
      ref={mapContainerRef} 
      style={{ height: `${height}px`, width: '100%', minHeight: '300px' }}
      className="rounded overflow-hidden"
    />
  )
}

export default CameraMap
