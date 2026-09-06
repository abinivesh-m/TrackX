import React, { useEffect, useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle } from 'react-leaflet'
import { apiClient } from '../App'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'

// Fix for default marker icons in React-Leaflet
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
})

// Custom camera icon
const cameraIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSIjM2I4MmY2IiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMSI+PHBhdGggZD0iTTIzIDRsLTMgMi00LTRoLThsLTQgNCAzIDEtNCAzaDh6Ii8+PHBhdGggZD0iTTEgMTloMjJ2MkgxeiIvPjwvc3ZnPg==',
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32]
})

export default function MapView({ searchPlate = null }) {
  const [cameras, setCameras] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [searchPlate])

  const fetchData = async () => {
    try {
      const [camerasRes, vehiclesRes] = await Promise.all([
        apiClient.get('/api/v1/cameras'),
        apiClient.get('/api/v1/vehicles')
      ])
      setCameras(camerasRes.data.cameras || [])
      setVehicles(vehiclesRes.data.vehicles || [])
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch map data:', error)
      setLoading(false)
    }
  }

  // Calculate map center from cameras
  const getMapCenter = () => {
    if (cameras.length === 0) return [12.9716, 77.5946] // Default to Bangalore
    const avgLat = cameras.reduce((sum, cam) => sum + (cam.latitude || 12.9716), 0) / cameras.length
    const avgLng = cameras.reduce((sum, cam) => sum + (cam.longitude || 77.5946), 0) / cameras.length
    return [avgLat, avgLng]
  }

  // Generate trajectory lines for vehicles
  const getVehicleTrajectories = () => {
    if (!searchPlate) return []
    const vehicle = vehicles.find(v => v.plate_text === searchPlate)
    if (!vehicle) return []
    
    // Mock trajectory data - in real app, fetch from backend
    return [{
      positions: cameras.slice(0, 3).map(c => [c.latitude, c.longitude]),
      color: '#3b82f6'
    }]
  }

  // Generate heatmap circles for traffic density
  const getTrafficHeatmap = () => {
    return cameras.map((cam, idx) => ({
      center: [cam.latitude || 12.9716, cam.longitude || 77.5946],
      radius: Math.random() * 300 + 100, // Mock data
      intensity: Math.random()
    }))
  }

  if (loading) {
    return (
      <div className="w-full h-96 bg-slate-800 rounded-lg flex items-center justify-center">
        <p className="text-gray-400">Loading map...</p>
      </div>
    )
  }

  return (
    <div className="w-full h-96 rounded-lg overflow-hidden border border-slate-700">
      <MapContainer
        center={getMapCenter()}
        zoom={13}
        style={{ height: '100%', width: '100%' }}
        className="z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {/* Camera markers */}
        {cameras.map((camera) => (
          <Marker
            key={camera.id}
            position={[camera.latitude || 12.9716, camera.longitude || 77.5946]}
            icon={cameraIcon}
          >
            <Popup>
              <div className="text-sm">
                <p className="font-bold">{camera.name || camera.id}</p>
                <p className="text-gray-600">{camera.id}</p>
                <p className="text-green-600">Status: {camera.status || 'online'}</p>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Traffic heatmap circles */}
        {!searchPlate && getTrafficHeatmap().map((heat, idx) => (
          <Circle
            key={`heat-${idx}`}
            center={heat.center}
            radius={heat.radius}
            pathOptions={{
              fillColor: heat.intensity > 0.5 ? '#ef4444' : '#3b82f6',
              fillOpacity: heat.intensity * 0.3,
              color: 'transparent'
            }}
          />
        ))}

        {/* Vehicle trajectory lines */}
        {getVehicleTrajectories().map((traj, idx) => (
          <Polyline
            key={`traj-${idx}`}
            positions={traj.positions}
            pathOptions={{
              color: traj.color,
              weight: 3,
              opacity: 0.7
            }}
          />
        ))}
      </MapContainer>
    </div>
  )
}
