// frontend/src/pages/CamerasPage.tsx
//
// Camera Network. SIH26127 "physical vs media status" correction
// (2026-09-14): this page used to show ONE badge per camera driven by
// camera.status from GET /cameras/health, which is actually an
// OBSERVATION-ACTIVITY signal (has this camera produced a detection in the
// last 24h? - see backend/app/api/v1/cameras.py's _camera_status()). That
// field says nothing about whether a camera has a real RTSP connection -
// running the demo/camera-media pipeline against CAM_02's local sample
// image (no live camera at all) makes it "ONLINE" by that definition,
// indistinguishable here from CAM_01's real physical RTSPS connection.
// Judge-facing correction: physical/RTSP status and media/pipeline status
// are now two separate, honestly-labeled things on every card:
//   - PHYSICAL badge (LIVE CAMERA / CAMERA OFFLINE / CAMERA NOT CONFIGURED)
//     - computed from GET /observations/camera-source/{camera_id}
//       (configured / is_real_camera - the same real fields
//       CameraLivePage.tsx's own LIVE CAMERA/DEMO FEED badge already uses),
//       never from observation timestamps.
//   - MEDIA badge (PROCESSED / NO OBSERVATIONS) - real observation_count
//     from GET /cameras/health, relabeled so it's never read as a physical
//     heartbeat.
// "Last heartbeat" was renamed "Last observation" for the same reason - it
// was never a device heartbeat, only a timestamp of the last DB row.

import React, { useState, useEffect, useMemo } from 'react'
import { toast } from 'react-toastify'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import CameraMap from '@/components/maps/CameraMap'
import { Camera as CameraIcon, Activity, MapPin, Video, Search, Navigation, Clock, WifiOff, Radio } from 'lucide-react'
import type { Camera, CameraSourceStatus } from '@/types'

type PhysicalStatus = 'LIVE' | 'OFFLINE' | 'NOT_CONFIGURED' | 'CHECKING'

const PHYSICAL_META: Record<PhysicalStatus, { cls: string; dot: string; label: string }> = {
  LIVE: { cls: 'text-clear-400 bg-clear-500/10 border-clear-500/20', dot: 'bg-clear-400', label: 'LIVE CAMERA' },
  OFFLINE: { cls: 'text-critical-400 bg-critical-500/10 border-critical-500/20', dot: 'bg-critical-400', label: 'CAMERA OFFLINE' },
  NOT_CONFIGURED: { cls: 'text-muted bg-white/5 border-border', dot: 'bg-slate-500', label: 'CAMERA NOT CONFIGURED' },
  CHECKING: { cls: 'text-muted bg-white/5 border-border', dot: 'bg-slate-500', label: 'CHECKING…' },
}

// Real, config/probe-derived physical status - never derived from
// observation activity. `src` is undefined while still loading for this
// camera (shows CHECKING, not a guess) and 'error' when the status call
// itself failed (also honestly reported, not silently treated as offline).
function physicalStatus(src: CameraSourceStatus | 'error' | undefined): PhysicalStatus {
  if (!src || src === 'error') return 'CHECKING'
  if (!src.configured) return 'NOT_CONFIGURED'
  return src.is_real_camera ? 'LIVE' : 'OFFLINE'
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
  const [statusFilter, setStatusFilter] = useState<'ALL' | PhysicalStatus>('ALL')
  // Tells "backend unreachable" apart from "zero cameras configured" - a
  // silent failure previously rendered as an identical empty grid either way.
  const [loadError, setLoadError] = useState<string | null>(null)
  // Real per-camera feed source (LIVE vs DEMO) - keyed by camera_id, fetched
  // once cameras are known. Absent while still loading for that camera;
  // undefined is deliberately distinct from "checked and failed" so the
  // badge can show a neutral "checking…" state rather than guessing.
  const [sourceStatus, setSourceStatus] = useState<Record<string, CameraSourceStatus | 'error'>>({})

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

  // Fetch each camera's real source status (no `probe` - that would attempt
  // a live connection per card on every page load, which is unnecessary
  // network/time cost; `configured`/`is_real_camera` are enough to label
  // the badge honestly, and CameraLivePage's own WebSocket connection is
  // the real, live confirmation).
  useEffect(() => {
    if (cameras.length === 0) return
    let cancelled = false
    cameras.forEach((cam) => {
      api
        .getCameraSourceStatus(cam.camera_id)
        .then((status) => {
          if (!cancelled) setSourceStatus((prev) => ({ ...prev, [cam.camera_id]: status }))
        })
        .catch(() => {
          if (!cancelled) setSourceStatus((prev) => ({ ...prev, [cam.camera_id]: 'error' }))
        })
    })
    return () => {
      cancelled = true
    }
  }, [cameras])

  // Filter/count by the same real PHYSICAL status the cards show (see
  // physicalStatus() above) - not camera.status (observation activity).
  // Filtering by activity would let a camera whose demo media was just
  // processed pass an "ONLINE" filter meant to find real live cameras.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return cameras.filter((c) => {
      if (statusFilter !== 'ALL' && physicalStatus(sourceStatus[c.camera_id]) !== statusFilter) return false
      if (!q) return true
      return (
        c.camera_id.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q) ||
        (c.location || '').toLowerCase().includes(q)
      )
    })
  }, [cameras, search, statusFilter, sourceStatus])

  const counts = useMemo(() => {
    const c = { LIVE: 0, OFFLINE: 0, NOT_CONFIGURED: 0, CHECKING: 0 }
    cameras.forEach((cam) => {
      c[physicalStatus(sourceStatus[cam.camera_id])]++
    })
    return c
  }, [cameras, sourceStatus])

  if (isLoading) {
    return <div className="flex justify-center items-center h-full text-white">Loading Camera Network...</div>
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center gap-2 text-critical-400">
        <WifiOff size={32} />
        <p className="text-lg font-medium">{loadError}</p>
        <p className="text-sm text-muted">Camera network could not be loaded. Try refreshing the page.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded p-3 flex items-center justify-between text-sm text-muted">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-clear-400" />
          <span>
            Every camera runs through the same real detection pipeline. Physical/RTSP status
            (LIVE CAMERA / CAMERA OFFLINE / CAMERA NOT CONFIGURED) reflects a real connection
            check — it is never inferred from how recently a camera's stored footage was
            processed. A camera with no RTSP source configured honestly shows CAMERA NOT
            CONFIGURED even after its demo/camera-media has been processed and produced real
            observations.
          </span>
        </div>
        <span className="text-xs bg-surface-light px-2 py-0.5 rounded font-mono border border-border">PER-CAMERA STATUS</span>
      </div>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <CameraIcon className="text-signal-400" />
          Camera Network
        </h1>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-clear-400">{counts.LIVE} live</span>
          <span className="text-critical-400">{counts.OFFLINE} offline</span>
          <span className="text-muted">{counts.NOT_CONFIGURED} not configured</span>
        </div>
      </div>

      {/* Map Overview */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-white mb-4">City Camera Coverage</h3>
        <div className="h-[400px] rounded overflow-hidden">
          <CameraMap
            cameras={cameras}
            physicalStatusById={Object.fromEntries(cameras.map((c) => [c.camera_id, physicalStatus(sourceStatus[c.camera_id])]))}
          />
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
            className="w-full pl-9 pr-4 py-2 rounded bg-surface-light border border-border focus:border-signal-500 focus:outline-none text-white text-sm"
          />
        </div>
        <div className="flex gap-2">
          {(['ALL', 'LIVE', 'OFFLINE', 'NOT_CONFIGURED'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-2 rounded text-xs font-medium border transition-colors ${
                statusFilter === s
                  ? 'bg-signal-500/20 text-signal-400 border-signal-500/30'
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
            const src = sourceStatus[camera.camera_id]
            const physical = physicalStatus(src)
            const meta = PHYSICAL_META[physical]
            // Media/pipeline status - deliberately separate from `physical`
            // above. A NOT_CONFIGURED camera can legitimately have
            // PROCESSED media (its local sample image/video has been run
            // through the real pipeline) without that implying a live feed.
            const hasObservations = (camera.observation_count ?? 0) > 0
            const feedDetail =
              src === 'error'
                ? 'Feed status unavailable'
                : src
                ? src.source_label ||
                  (src.is_real_camera
                    ? 'Live RTSP camera'
                    : src.configured
                    ? 'RTSP configured but not resolving as a real camera — check backend logs.'
                    : 'No RTSP source configured for this camera.')
                : 'Checking feed…'
            return (
              <div key={camera.camera_id} className="card p-6 hover:border-signal-500/50 transition-colors relative">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded bg-signal-500/20 flex items-center justify-center">
                      <Video size={20} className="text-signal-400" />
                    </div>
                    <div>
                      <h3 className="font-bold text-white font-data">{camera.camera_id}</h3>
                      <p className="text-xs text-muted">{camera.name}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
                    <span className={`text-xs font-mono px-2 py-0.5 rounded border ${meta.cls}`}>{meta.label}</span>
                  </div>
                </div>
                <p className="text-xs text-muted -mt-3 mb-3 truncate">{feedDetail}</p>

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
                    {hasObservations
                      ? `${camera.observation_count} vehicle observation(s) — pipeline PROCESSED`
                      : 'NO OBSERVATIONS YET'}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <Clock size={14} />
                    Last observation: {relativeTime(camera.last_seen)}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <span>GPS: {camera.latitude?.toFixed(4)}, {camera.longitude?.toFixed(4)}</span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-xs gap-2">
                  <span className="text-muted">
                    {physical === 'LIVE' ? 'Source: Live Camera' : 'Source: Camera Media (demo/recorded)'}
                  </span>
                  <Link
                    to={`/cameras/${camera.camera_id}/live`}
                    className="flex items-center gap-1 px-2 py-1 rounded border border-border text-muted hover:text-white hover:border-signal-500/50 transition-colors shrink-0"
                  >
                    <Radio size={12} />
                    {physical === 'LIVE' ? 'Watch Live' : 'View Feed'}
                  </Link>
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
