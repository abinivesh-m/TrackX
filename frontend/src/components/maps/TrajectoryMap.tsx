// frontend/src/components/maps/TrajectoryMap.tsx

import React, { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Trajectory } from '@/types'

interface TrajectoryMapProps {
  trajectory: Trajectory
  height?: number
}

const TrajectoryMap: React.FC<TrajectoryMapProps> = ({ trajectory, height = 500 }) => {
  const mapRef = useRef<L.Map | null>(null)
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const markersRef = useRef<L.Marker[]>([])
  const polylineRef = useRef<L.Polyline | null>(null)
  const isInitializedRef = useRef(false)

  useEffect(() => {
    if (!mapContainerRef.current || !trajectory.trajectory_points) return
    
    // Initialize map only once
    if (!mapRef.current && !isInitializedRef.current) {
      // Calculate center from trajectory points
      let centerLat = 11.0168;
      let centerLong = 76.9558;
      if (trajectory.trajectory_points && trajectory.trajectory_points.length > 0) {
        const validPoints = trajectory.trajectory_points.filter(p => p.latitude != null && p.longitude != null);
        if (validPoints.length > 0) {
          centerLat = validPoints.reduce((sum, p) => sum + p.latitude, 0) / validPoints.length;
          centerLong = validPoints.reduce((sum, p) => sum + p.longitude, 0) / validPoints.length;
        }
      }
      mapRef.current = L.map(mapContainerRef.current, {
        center: [centerLat, centerLong], // Dynamic center based on trajectory
        zoom: 13,
        preferCanvas: true, // Use canvas renderer for better performance
        renderer: L.canvas()
      })
      
      // Add dark tiles with better performance settings
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        maxZoom: 18,
        minZoom: 10
      }).addTo(mapRef.current)
      
      isInitializedRef.current = true
    }
    
    // Clear existing markers and lines
    markersRef.current.forEach(marker => marker.remove())
    markersRef.current = []
    if (polylineRef.current) {
      polylineRef.current.remove()
      polylineRef.current = null
    }
    
    // Add trajectory points (optimize by limiting markers)
    const points: L.LatLngExpression[] = []
    
    // Only show markers for every 2nd point to improve performance
    trajectory.trajectory_points.forEach((point, index) => {
      if (point.latitude != null && point.longitude != null) {
        const latLng: L.LatLngExpression = [point.latitude, point.longitude]
        points.push(latLng)
        
        // Skip intermediate markers for better performance
        if (index > 0 && index < trajectory.trajectory_points.length - 1 && index % 2 !== 0) {
          return
        }
        
        // Create marker with numbering
        const icon = L.divIcon({
          className: 'custom-trajectory-icon',
          html: `<div style="
            background: #3b82f6;
            color: white;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: bold;
            border: 2px solid white;
            box-shadow: 0 0 8px #3b82f6;
          ">${index + 1}</div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10]
        })
        
        const marker = L.marker(latLng, { icon })
          .addTo(mapRef.current!)
          .bindPopup(`
            <div style="color: #333; min-width: 200px;">
              <strong>${point.camera_id}</strong><br/>
              ${point.camera_name}<br/>
              ${point.location}<br/>
              Time: ${new Date(point.timestamp).toLocaleString()}<br/>
              Plate: ${point.plate_text}<br/>
              Confidence: ${(point.confidence * 100).toFixed(1)}%
            </div>
          `)
        
        markersRef.current.push(marker)
      }
    })
    
    // Draw trajectory line with optimized settings
    if (points.length > 1) {
      polylineRef.current = L.polyline(points, {
        color: '#3b82f6',
        weight: 3, // Reduced weight for performance
        opacity: 0.6, // Reduced opacity for performance
        dashArray: '10, 10',
        smoothFactor: 1 // Simplify line for better performance
      }).addTo(mapRef.current!)
    }
    
    // Fit bounds to show entire trajectory
    if (points.length > 0) {
      const bounds = L.latLngBounds(points)
      mapRef.current?.fitBounds(bounds.pad(0.1), { animate: false }) // Disable animation for performance
    }
    
    return () => {
      markersRef.current.forEach(marker => marker.remove())
      if (polylineRef.current) {
        polylineRef.current.remove()
      }
    }
  }, [trajectory])

  return (
    <div 
      ref={mapContainerRef} 
      style={{ height: `${height}px`, width: '100%', minHeight: '300px' }}
      className="rounded-lg overflow-hidden"
    />
  )
}

export default TrajectoryMap
