// frontend/src/components/maps/CameraMap.tsx

import React, { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Camera } from '@/types'
import { MAP_TILE_URL, MAP_TILE_ATTRIBUTION, MAP_TILE_MAX_ZOOM } from '@/config/mapTiles'

interface CameraMapProps {
  cameras: Camera[]
  height?: number
}

const CameraMap: React.FC<CameraMapProps> = ({ cameras, height = 500 }) => {
  const mapRef = useRef<L.Map | null>(null)
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const markersRef = useRef<L.Marker[]>([])
  const isInitializedRef = useRef(false)

  useEffect(() => {
    if (!mapContainerRef.current) return
    
    // Initialize map only once
    if (!mapRef.current && !isInitializedRef.current) {
      mapRef.current = L.map(mapContainerRef.current, {
        center: [11.0168, 76.9558], // Coimbatore center
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
        const icon = L.divIcon({
          className: 'custom-camera-icon',
          html: `<div style="
            background: ${camera.status === 'ONLINE' ? '#10b981' : camera.status === 'OFFLINE' ? '#ef4444' : '#f59e0b'};
            width: 10px;
            height: 10px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 0 8px ${camera.status === 'ONLINE' ? '#10b981' : camera.status === 'OFFLINE' ? '#ef4444' : '#f59e0b'};
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
              Status: ${camera.status || 'Unknown'}<br/>
              Observations: ${camera.observation_count || 0}
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
  }, [cameras])

  return (
    <div 
      ref={mapContainerRef} 
      style={{ height: `${height}px`, width: '100%', minHeight: '300px' }}
      className="rounded-lg overflow-hidden"
    />
  )
}

export default CameraMap
