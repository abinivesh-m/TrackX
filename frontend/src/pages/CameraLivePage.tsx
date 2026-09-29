// frontend/src/pages/CameraLivePage.tsx
//
// SIH26127 real CP PLUS/RTSP(S) camera integration - live per-camera
// viewer. Opens the real WebSocket at
// backend/app/api/v1/observations.py's `/live-stream/{camera_id}` and
// renders exactly what it sends: real, freshly-computed detections drawn
// onto a real decoded frame, as they are produced - see docs/LIVE_STREAMING.md.
//
// Every value shown here is real, not simulated by this page:
//   - the JPEG frame itself and its drawn boxes come straight from the
//     backend's own on_frame() callback - this page never draws or fakes
//     a box.
//   - "LIVE CAMERA" vs "DEMO FEED" reflects the server's own
//     `is_real_camera` field from the "started" message, not a guess made
//     here.
//   - fps_so_far / vehicles_in_frame / elapsed are the server's own
//     numbers for that exact frame - never recomputed or rounded up by
//     this page.
// This page proves nothing beyond what the WebSocket actually sends -
// e.g. `vehicles_in_frame: 0` on every frame from a real camera means no
// vehicle was in view, not a bug, and is shown as-is.

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Radio, Video, RefreshCw, AlertTriangle, Gauge, Car, Clock, RotateCw, ScanLine, Eye, Search } from 'lucide-react'
import { api } from '@/services/api'
import type { Observation } from '@/types'

type StreamState = 'connecting' | 'streaming' | 'done' | 'error' | 'closed'

interface StartedInfo {
  video: string
  camera_id: string
  source: 'rtsp' | 'simulated_video'
  is_real_camera: boolean
  source_label: string
}

interface DoneInfo {
  tracks: number
  plates_verified: number
  plates_tentative: number
  duration_seconds: number
}

function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${path}`
}

const CameraLivePage: React.FC = () => {
  const { cameraId } = useParams<{ cameraId: string }>()
  const wsRef = useRef<WebSocket | null>(null)
  const [connectAttempt, setConnectAttempt] = useState(0)

  const [state, setState] = useState<StreamState>('connecting')
  const [errorDetail, setErrorDetail] = useState<string | null>(null)
  const [started, setStarted] = useState<StartedInfo | null>(null)
  const [done, setDone] = useState<DoneInfo | null>(null)
  const [frameSrc, setFrameSrc] = useState<string | null>(null)
  const [frameCount, setFrameCount] = useState(0)
  const [lastFrame, setLastFrame] = useState<{
    frame_idx: number
    vehicles_in_frame: number
    elapsed_seconds: number
    fps_so_far: number
  } | null>(null)
  // TRACKX_RTSP_<id>_ROTATION, fetched separately from GET
  // camera-source/{camera_id} - the "started" WebSocket message itself
  // doesn't carry it (see backend/app/api/v1/observations.py). Only ever
  // non-zero when the server is actually applying it (needs_ffmpeg_bridge)
  // - see network/rtsp_camera.py.
  const [rotation, setRotation] = useState<number>(0)

  // Latest Detections panel - real, database-backed observations for THIS
  // camera (GET /observations?camera_id=..., already used elsewhere by
  // VehiclesPage). This is deliberately NOT reconstructed from per-frame
  // WebSocket data (which only carries a live box count, no plate/crop) -
  // it's the same persisted rows pipeline.py writes once OCR fusion has
  // actually finished for a track, so a plate shown here was really read,
  // never guessed from a single frame. Polled while the stream is live so
  // a new observation appears without a manual refresh; a null plate_text
  // is shown as "Plate not read" rather than hidden or invented.
  const [recentObservations, setRecentObservations] = useState<Observation[] | null>(null)
  const [observationsError, setObservationsError] = useState(false)

  const refreshObservations = useCallback(() => {
    if (!cameraId) return
    api
      .getObservations({ camera_id: cameraId, limit: 8 })
      .then((obs) => {
        setRecentObservations(obs)
        setObservationsError(false)
      })
      .catch(() => setObservationsError(true))
  }, [cameraId])

  useEffect(() => {
    if (!cameraId) return
    api
      .getCameraSourceStatus(cameraId)
      .then((s) => setRotation(s.rotation || 0))
      .catch(() => setRotation(0))
  }, [cameraId])

  useEffect(() => {
    refreshObservations()
    const interval = setInterval(refreshObservations, 5000)
    return () => clearInterval(interval)
  }, [refreshObservations])

  useEffect(() => {
    if (!cameraId) return

    setState('connecting')
    setErrorDetail(null)
    setStarted(null)
    setDone(null)
    setFrameSrc(null)
    setFrameCount(0)
    setLastFrame(null)

    const ws = new WebSocket(wsUrl(`/api/v1/observations/live-stream/${cameraId}`))
    wsRef.current = ws

    ws.onopen = () => {
      // Still "connecting" until the real "started" message arrives -
      // the socket opening only means the TCP/HTTP handshake succeeded,
      // not that the backend found a usable camera/video source yet.
    }

    ws.onmessage = (evt) => {
      let msg: any
      try {
        msg = JSON.parse(evt.data)
      } catch {
        return
      }
      switch (msg.type) {
        case 'started':
          setStarted(msg as StartedInfo)
          setState('streaming')
          break
        case 'frame':
          setFrameSrc(`data:image/jpeg;base64,${msg.jpeg_b64}`)
          setFrameCount((n) => n + 1)
          setLastFrame({
            frame_idx: msg.frame_idx,
            vehicles_in_frame: msg.vehicles_in_frame,
            elapsed_seconds: msg.elapsed_seconds,
            fps_so_far: msg.fps_so_far,
          })
          break
        case 'done':
          setDone(msg as DoneInfo)
          setState('done')
          break
        case 'error':
          setErrorDetail(msg.detail || 'Unknown error from the live-stream endpoint.')
          setState('error')
          break
        default:
          break
      }
    }

    ws.onerror = () => {
      // The real "error" JSON message (handled above) carries the useful
      // detail when the backend sends one; this only fires for a
      // transport-level failure (e.g. the backend is not reachable at
      // all), so it only sets state if nothing more specific has already.
      setState((prev) => (prev === 'connecting' ? 'error' : prev))
      setErrorDetail((prev) => prev ?? 'Could not reach the live-stream WebSocket. Is the backend running?')
    }

    ws.onclose = () => {
      setState((prev) => (prev === 'streaming' || prev === 'connecting' ? 'closed' : prev))
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [cameraId, connectAttempt])

  const reconnect = useCallback(() => setConnectAttempt((n) => n + 1), [])

  const isReal = started?.is_real_camera === true
  // SIH26127 "physical vs media status" correction (2026-09-14): "DEMO
  // FEED" read as if the feed itself were fake; relabeled to name what it
  // actually is - real footage from this camera's local media folder, run
  // through the same real pipeline, just not a live RTSP connection.
  const feedBadge = started
    ? isReal
      ? { cls: 'bg-clear-500/15 text-clear-400 border-clear-500/30', label: 'LIVE CAMERA' }
      : { cls: 'bg-caution-500/15 text-caution-400 border-caution-500/30', label: 'DEMO / CAMERA MEDIA' }
    : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link
            to="/cameras"
            className="w-9 h-9 rounded bg-surface-light border border-border flex items-center justify-center text-muted hover:text-white transition-colors"
          >
            <ArrowLeft size={16} />
          </Link>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Radio className="text-signal-400" />
            {cameraId} — Live Feed
          </h1>
          {feedBadge && (
            <span className={`text-xs font-mono px-2 py-0.5 rounded border ${feedBadge.cls}`}>{feedBadge.label}</span>
          )}
        </div>
        <button
          onClick={reconnect}
          className="flex items-center gap-2 px-3 py-2 rounded text-xs font-medium border border-border bg-surface-light text-muted hover:text-white transition-colors"
        >
          <RefreshCw size={14} className={state === 'connecting' ? 'animate-spin' : ''} />
          Reconnect
        </button>
      </div>

      {started && (
        <div className="bg-surface border border-border rounded p-3 text-sm text-muted flex items-center gap-4">
          <span>
            Source: <span className="text-white font-mono">{started.source_label}</span>
          </span>
          {rotation !== 0 && (
            <span className="flex items-center gap-1 text-xs">
              <RotateCw size={12} />
              Rotation corrected: {rotation}° clockwise
            </span>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="card p-6 lg:col-span-2">
        {state === 'connecting' && (
          <div className="aspect-video rounded bg-surface-light flex flex-col items-center justify-center gap-2 text-muted">
            <RefreshCw size={24} className="animate-spin" />
            <span>Connecting to live-stream/{cameraId}…</span>
          </div>
        )}

        {state === 'error' && (
          <div className="aspect-video rounded bg-surface-light flex flex-col items-center justify-center gap-2 text-critical-400 text-center px-6">
            <AlertTriangle size={24} />
            <span className="font-medium">Live stream error</span>
            <span className="text-sm text-muted">{errorDetail}</span>
            <button
              onClick={reconnect}
              className="mt-2 px-3 py-2 rounded text-xs font-medium border border-border bg-surface-light text-white hover:border-signal-500/50 transition-colors"
            >
              Try again
            </button>
          </div>
        )}

        {(state === 'streaming' || state === 'done' || state === 'closed') && (
          <div className="relative rounded overflow-hidden bg-black">
            {frameSrc ? (
              <img src={frameSrc} alt={`Live frame from ${cameraId}`} className="w-full h-auto block" />
            ) : (
              <div className="aspect-video flex items-center justify-center text-muted">
                <Video size={24} className="mr-2" /> Waiting for the first frame…
              </div>
            )}
            {lastFrame && (
              <div className="absolute bottom-2 left-2 flex items-center gap-3 bg-black/70 rounded px-3 py-1.5 text-xs font-mono text-white">
                <span className="flex items-center gap-1">
                  <Car size={12} /> {lastFrame.vehicles_in_frame} in frame
                </span>
                <span className="flex items-center gap-1">
                  <Gauge size={12} /> {lastFrame.fps_so_far} fps
                </span>
                <span className="flex items-center gap-1">
                  <Clock size={12} /> {lastFrame.elapsed_seconds}s
                </span>
              </div>
            )}
            {state === 'done' && (
              <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                <span className="text-white font-medium">Stream finished</span>
              </div>
            )}
            {state === 'closed' && (
              <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                <span className="text-white font-medium">Connection closed</span>
              </div>
            )}
          </div>
        )}

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div className="bg-surface-light rounded p-3">
            <div className="text-muted text-xs">Frames received</div>
            <div className="text-white font-mono text-lg">{frameCount}</div>
          </div>
          <div className="bg-surface-light rounded p-3">
            <div className="text-muted text-xs">Vehicles in latest frame</div>
            <div className="text-white font-mono text-lg">{lastFrame?.vehicles_in_frame ?? '—'}</div>
          </div>
          <div className="bg-surface-light rounded p-3">
            <div className="text-muted text-xs">Throughput so far</div>
            <div className="text-white font-mono text-lg">{lastFrame ? `${lastFrame.fps_so_far} fps` : '—'}</div>
          </div>
          <div className="bg-surface-light rounded p-3">
            <div className="text-muted text-xs">Connection</div>
            <div className="text-white font-mono text-lg capitalize">{state}</div>
          </div>
        </div>

        {done && (
          <div className="mt-4 bg-surface-light rounded p-3 text-sm text-muted">
            Run finished in {done.duration_seconds}s — {done.tracks} vehicle track(s), {done.plates_verified} plate(s)
            verified, {done.plates_tentative} tentative.
          </div>
        )}
      </div>

      {/* Latest Detections - real GET /observations?camera_id=... rows for
          this camera (see the refreshObservations() effect above), polled
          every 5s while this page is open. Deliberately separate from the
          WebSocket frame stream above: a frame message only ever carries a
          live box count, never a plate - a plate only exists here once
          pipeline.py's temporal-fusion voting has actually finished for a
          track and written a row to the database. */}
      <div className="card p-6 lg:col-span-1 flex flex-col">
        <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
          <ScanLine size={16} className="text-signal-400" /> Latest Detections
        </h3>
        <p className="text-xs text-muted mb-1">Real observations stored for {cameraId} — refreshes automatically.</p>
        {/* Same is_real_camera the LIVE CAMERA / DEMO / CAMERA MEDIA badge
            above uses - so these observations are never shown as "Live
            Camera" evidence when they actually came from this camera's
            local demo/camera-media folder. */}
        <p className="text-xs text-muted mb-4">
          Source: <span className={isReal ? 'text-clear-400' : 'text-caution-400/90'}>{isReal ? 'Live Camera' : 'Camera Media'}</span>
        </p>

        {observationsError && (
          <p className="text-xs text-critical-400 mb-3">Could not load observations for this camera.</p>
        )}

        {recentObservations === null ? (
          <div className="flex-1 flex items-center justify-center text-muted text-sm">
            <RefreshCw size={16} className="animate-spin mr-2" /> Loading…
          </div>
        ) : recentObservations.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center text-muted py-8">
            <Eye size={28} className="opacity-40 mb-2" />
            <p className="text-sm">No vehicle observations recorded yet.</p>
          </div>
        ) : (
          <div className="space-y-2 overflow-y-auto max-h-[560px] pr-1">
            {recentObservations.map((obs) => (
              <div key={obs.id} className="flex items-center gap-3 p-2.5 rounded bg-surface-light border border-border">
                {obs.plate_crop_url ? (
                  <img
                    src={obs.plate_crop_url}
                    alt="Plate crop"
                    className="w-14 h-10 object-cover rounded border border-border shrink-0"
                  />
                ) : (
                  <div className="w-14 h-10 rounded bg-surface flex items-center justify-center shrink-0">
                    <Car size={16} className="text-muted" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-white truncate">
                      {obs.plate_text || 'Plate not read'}
                    </span>
                    {obs.confidence != null && (
                      <span className="text-[10px] text-muted shrink-0">{Math.round(obs.confidence * 100)}%</span>
                    )}
                  </div>
                  <div className="text-[11px] text-muted flex items-center gap-1">
                    <Clock size={10} />
                    {obs.timestamp ? new Date(obs.timestamp).toLocaleTimeString('en-IN') : 'Unknown time'}
                    {obs.vehicle_type && <span className="capitalize"> · {obs.vehicle_type}</span>}
                  </div>
                </div>
                {obs.plate_text && (
                  <Link
                    to={`/vehicles?plate=${encodeURIComponent(obs.plate_text)}`}
                    className="text-muted hover:text-white shrink-0"
                    title="Open in Vehicle Intelligence"
                  >
                    <Search size={14} />
                  </Link>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      </div>
    </div>
  )
}

export default CameraLivePage
