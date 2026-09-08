// frontend/src/pages/CamerasPage.tsx
//
// Camera Network - real per-camera status (ONLINE / OFFLINE / NOT
// CONFIGURED, computed server-side from actual observation activity - see
// backend/app/api/v1/cameras.py's _camera_status()), location/road/
// direction, a real "last heartbeat" (time since its last observation, not
// a fabricated FPS or uptime number), and search/filtering. No camera here
// has a live RTSP feed - the "DEMO FEED" label says exactly what that
// means instead of claiming a stream is active.

import React, { useState, useEffect, useMemo } from 'react'
import { toast } from 'react-toastify'
import { api } from '@/services/api'
import CameraMap from '@/components/maps/CameraMap'
import { Camera as CameraIcon, Activity, MapPin, Video, Search, Navigation, Clock, WifiOff } from 'lucide-react'
import type { Camera } from '@/types'

const STATUS_META: Record<string, { badge: string; dot: string; label: string }> = {
  ONLINE: { badge: 'bg-green-500/20 text-green-400', dot: 'bg-green-500', label: 'ONLINE' },
  OFFLINE: { badge: 'bg-red-500/20 text-red-400', dot: 'bg-red-500', label: 'OFFLINE' },
  NOT_CONFIGURED: { badge: 'bg-gray-500/20 text-gray-400', dot: 'bg-gray-400', label: 'NOT CONFIGURED' },
}

function statusMeta(status?: string) {
  return STATUS_META[status || ''] || STATUS_META.NOT_CONFIGURED
}

function relativeTime(iso?: string | null): string {
  if (!iso) return 'Never'
  const then = new Date(iso).getTime()
  if (isNaN(then)) return 'Unknown'
  const diffMs = Date.now() - then
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

const CamerasPage: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ONLINE' | 'OFFLINE' | 'NOT_CONFIGURED'>('ALL')
  // Tells "backend unreachable" apart from "zero cameras configured" - a
  // silent failure previously rendered as an identical empty grid either way.
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    const fetchCameras = async () => {
      try {
        const data = await api.getCameraHealth()
        setCameras(data || [])
        setLoadError(null)
      } catch (error) {
        console.error('Failed to fetch cameras:', error)
        setLoadError('Could not reach the TrackX API.')
        toast.error('Failed to load camera network')
      } finally {
        setIsLoading(false)
      }
    }
    fetchCameras()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return cameras.filter((c) => {
      if (statusFilter !== 'ALL' && (c.status || 'NOT_CONFIGURED') !== statusFilter) return false
      if (!q) return true
      return (
        c.camera_id.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q) ||
        (c.location || '').toLowerCase().includes(q)
      )
    })
  }, [cameras, search, statusFilter])

  const counts = useMemo(() => {
    const c = { ONLINE: 0, OFFLINE: 0, NOT_CONFIGURED: 0 }
    cameras.forEach((cam) => {
      const s = (cam.status || 'NOT_CONFIGURED') as keyof typeof c
      if (s in c) c[s]++
    })
    return c
  }, [cameras])

  if (isLoading) {
    return <div className="flex justify-center items-center h-full text-white">Loading Camera Network...</div>
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center gap-2 text-red-300">
        <WifiOff size={32} />
        <p className="text-lg font-medium">{loadError}</p>
        <p className="text-sm text-muted">Camera network could not be loaded. Try refreshing the page.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded-lg p-3 flex items-center justify-between text-sm text-muted">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          <span>Cameras run on recorded/reproducible footage processed through the real detection pipeline — no live RTSP feed is connected.</span>
        </div>
        <span className="text-xs bg-surface-light px-2 py-0.5 rounded font-mono border border-border">RECORDED FEEDS</span>
      </div>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <CameraIcon className="text-blue-400" />
          Camera Network
        </h1>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-green-400">{counts.ONLINE} online</span>
          <span className="text-red-400">{counts.OFFLINE} offline</span>
          <span className="text-gray-400">{counts.NOT_CONFIGURED} not configured</span>
        </div>
      </div>

      {/* Map Overview */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-white mb-4">City Camera Coverage</h3>
        <div className="h-[400px] rounded-lg overflow-hidden">
          <CameraMap cameras={cameras} />
        </div>
      </div>

      {/* Search / filter */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
          <input
            type="text"
            placeholder="Search by camera ID, name, or location…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-white text-sm"
          />
        </div>
        <div className="flex gap-2">
          {(['ALL', 'ONLINE', 'OFFLINE', 'NOT_CONFIGURED'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                statusFilter === s
                  ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                  : 'bg-surface-light text-muted border-border hover:text-white'
              }`}
            >
              {s === 'NOT_CONFIGURED' ? 'NOT CONFIGURED' : s}
            </button>
          ))}
        </div>
      </div>

      {/* Camera Grid */}
      {filtered.length === 0 ? (
        <div className="card p-8 text-center text-muted">
          {cameras.length === 0 ? 'No cameras registered in network topology.' : 'No cameras match your search/filter.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((camera) => {
            const meta = statusMeta(camera.status)
            return (
              <div key={camera.camera_id} className="card p-6 hover:border-blue-500/50 transition-colors relative">
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
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
                    <span className={`text-xs px-2 py-1 rounded-full ${meta.badge}`}>{meta.label}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <MapPin size={14} />
                    {camera.location || 'Location not configured'}
                    {camera.road ? ` · ${camera.road}` : ''}
                  </div>
                  {camera.direction && (
                    <div className="flex items-center gap-2 text-sm text-muted">
                      <Navigation size={14} />
                      Facing {camera.direction.replace(/_/g, ' ')}
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <Activity size={14} />
                    {camera.observation_count ?? 0} vehicle observations logged
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <Clock size={14} />
                    Last heartbeat: {relativeTime(camera.last_seen)}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <span>GPS: {camera.latitude?.toFixed(4)}, {camera.longitude?.toFixed(4)}</span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-xs">
                  <span className="text-amber-400/90 font-mono bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                    DEMO FEED
                  </span>
                  <span className="text-muted">No live RTSP feed connected</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default CamerasPage
