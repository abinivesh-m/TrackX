// frontend/src/pages/CamerasPage.tsx

import React, { useState, useEffect } from 'react'
import { api } from '@/services/api'
import CameraMap from '@/components/maps/CameraMap'
import { Camera as CameraIcon, Activity, MapPin, Video } from 'lucide-react'
import type { Camera } from '@/types'

const CamerasPage: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchCameras = async () => {
      try {
        const data = await api.getCameraHealth()
        setCameras(data || [])
      } catch (error) {
        console.error('Failed to fetch cameras:', error)
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchCameras()
  }, [])

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ONLINE':
        return 'bg-green-500/20 text-green-400'
      case 'DEGRADED':
        return 'bg-yellow-500/20 text-yellow-400'
      case 'OFFLINE':
        return 'bg-red-500/20 text-red-400'
      default:
        return 'bg-blue-500/20 text-blue-400'
    }
  }

  const getStatusDot = (status: string) => {
    switch (status) {
      case 'ONLINE':
        return 'bg-green-500'
      case 'DEGRADED':
        return 'bg-yellow-500'
      case 'OFFLINE':
        return 'bg-red-500'
      default:
        return 'bg-blue-500'
    }
  }

  if (isLoading) {
    return <div className="flex justify-center items-center h-full text-white">Loading Camera Network...</div>
  }

  return (
    <div className="space-y-6">
      {/* Demo Mode Notice Banner */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center justify-between text-amber-300 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span><b>DEMO MODE:</b> Real-time live feeds simulated via reproducible high-resolution CCTV recordings.</span>
        </div>
        <span className="text-xs bg-amber-500/20 px-2 py-0.5 rounded font-mono">REPRODUCIBLE TEST FEEDS</span>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <CameraIcon className="text-blue-400" />
          Camera Network Infrastructure
        </h1>
        <span className="text-sm text-muted">
          {cameras.length} cameras registered in corridor topology
        </span>
      </div>

      {/* Map Overview */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-white mb-4">City Camera Coverage Topology</h3>
        <div className="h-[400px] rounded-lg overflow-hidden">
          <CameraMap cameras={cameras} />
        </div>
      </div>

      {/* Camera Grid */}
      {cameras.length === 0 ? (
        <div className="card p-8 text-center text-muted">
          No cameras detected in network. Verify backend observation store.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cameras.map((camera) => (
            <div 
              key={camera.camera_id}
              className="card p-6 hover:border-blue-500/50 transition-colors relative"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                    <Video size={20} className="text-blue-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white">{camera.camera_id}</h3>
                    <p className="text-xs text-muted">{camera.name}</p>
                  </div>
                </div>
                
                {/* Status */}
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${getStatusDot(camera.status || 'ONLINE')} pulse`} />
                  <span className={`text-xs px-2 py-1 rounded-full ${getStatusBadge(camera.status || 'ONLINE')}`}>
                    {camera.status || 'ONLINE'}
                  </span>
                </div>
              </div>

              {/* Location & Metadata */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm text-muted">
                  <MapPin size={14} />
                  {camera.location || 'Urban Corridor'}
                </div>
                <div className="flex items-center gap-2 text-sm text-muted">
                  <Activity size={14} />
                  {camera.observation_count || 0} vehicle observations logged
                </div>
                <div className="flex items-center gap-2 text-xs text-muted">
                  <span>GPS: {camera.latitude?.toFixed(4)}, {camera.longitude?.toFixed(4)}</span>
                </div>
              </div>

              {/* Feed Mode Label */}
              <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-xs">
                <span className="text-amber-400/90 font-mono bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                  DEMO FEED
                </span>
                <span className="text-blue-400">
                  ANPR Stream Active &rarr;
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default CamerasPage