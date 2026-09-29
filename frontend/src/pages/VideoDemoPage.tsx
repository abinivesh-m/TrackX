// frontend/src/pages/VideoDemoPage.tsx
//
// CCTV video upload -> real detection/OCR -> observations, the one
// end-to-end product flow that previously had no UI at all. Calls the real
// POST /api/v1/observations/ingest-video endpoint (backend/app/api/v1/
// observations.py) - no mocked results anywhere on this page. If OCR is
// unavailable in this environment, that is shown honestly per-observation
// ("OCR unavailable"), never a fabricated plate.

import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/services/api'
import type { Camera } from '@/types'
import {
  UploadCloud,
  Video,
  Loader2,
  CheckCircle2,
  XCircle,
  Car,
  ScanLine,
  Search,
  Route as RouteIcon,
  FileVideo,
  RotateCcw,
  Info,
  Image as ImageIcon,
  Play,
  Radio,
  Square,
} from 'lucide-react'

type Stage = 'idle' | 'uploading' | 'processing' | 'done' | 'error'
type Mode = 'camera-media' | 'upload' | 'live-ws'

// SIH26127 department-freeze Mode 2: connects to the already-proven
// WS /api/v1/observations/live-stream/{camera_id} endpoint (backend/app/
// api/v1/observations.py) and pushes each frame's real, freshly-computed
// detections out live, instead of waiting for the whole video/stream and
// returning one final response the way "Camera Media"/"Upload Video" above
// do. Every frame image and every stat here comes straight from that
// endpoint's real inference - nothing is prerecorded client-side or
// simulated.
//
// Update (SIH26127 real CP PLUS/RTSP camera integration): when this was
// first written, every camera here read from a REAL VIDEO FILE already
// sitting in that camera's local folder (see demo/camera_simulator.py) -
// hence the original "Recorded CCTV, never LIVE" framing. That's no
// longer universally true: `/live-stream/{camera_id}` now resolves a real
// RTSP/RTSPS camera first when one is configured for that camera_id (see
// network/rtsp_camera.py), falling back to the same local-video-file
// simulation only when it isn't. The label below reflects the server's
// own `is_real_camera` field from the "started" message honestly, per
// connection - "Live Camera" when it really is one, "Recorded CCTV"
// otherwise - rather than a hardcoded assumption baked in when this was
// written. (LiveWebcamPage.tsx remains the one that uses a real, live
// BROWSER webcam feed - a different real source from this page's
// per-camera CCTV/RTSP one.)
interface LiveStreamFrameMsg {
  type: 'frame'
  frame_idx: number
  jpeg_b64: string
  vehicles_in_frame: number
  elapsed_seconds: number
  fps_so_far: number
}
interface LiveStreamDoneMsg {
  type: 'done'
  tracks: number
  plates_verified: number
  plates_tentative: number
  duration_seconds: number
}

interface CameraMediaInfo {
  camera_id: string
  available_images: number
  available_videos: number
  folder_exists: boolean
}

interface CameraProcessObservation {
  track_id: string | null
  vehicle_type: string | null
  plate_text: string | null
  plate_status: 'recognized' | 'detected_not_read' | 'no_plate_detected' | 'unavailable'
  ocr_confidence: number | null
  plate_confidence: number | null
  vehicle_confidence: number | null
  timestamp: string | null
  source_file: string | null
  source_type: 'image' | 'video' | null
  frame_index: number | null
  plate_crop_url: string | null
  annotated_url: string | null
}

interface CameraProcessResult {
  camera_id: string
  camera_name: string
  plate_detector_available: boolean
  ocr_available: boolean
  statistics: {
    images_processed: number
    videos_processed: number
    vehicles_detected: number
    plates_detected: number
    plates_recognized: number
    observations_stored: number
    processing_duration_seconds: number
  }
  observations: CameraProcessObservation[]
}

interface IngestObservation {
  track_id: string | null
  vehicle_type: string | null
  plate_text: string | null
  plate_status: 'recognized' | 'low_confidence' | 'detected_not_read' | 'no_plate_detected' | 'unavailable'
  ocr_confidence: number | null
  plate_confidence: number | null
  vehicle_confidence: number | null
  timestamp: string | null
  frame_index: number | null
  first_seen_frame: number | null
  last_seen_frame: number | null
  first_seen_timestamp: string | null
  last_seen_timestamp: string | null
  direction: string | null
  plate_crop_url: string | null
  // "Adaptive Multi-Frame ANPR Intelligence" evidence fields (SIH26127) -
  // real measured quality/preprocessing/temporal-fusion data behind the
  // final plate text, not decorative metadata. See pipeline.py's
  // _plate_state_for_track()/vote_plate_text() for how these are computed.
  plate_state: 'UNKNOWN' | 'LOW_CONFIDENCE' | 'TENTATIVE' | 'VERIFIED' | null
  plate_quality_score: number | null
  blur_score: number | null
  brightness_score: number | null
  contrast_score: number | null
  preprocessing_mode: string | null
  ocr_candidate_count: number | null
  temporal_support: number | null
  final_fusion_score: number | null
}

interface IngestResult {
  camera_id: string
  camera_name: string
  video_filename: string
  plate_detector_available: boolean
  ocr_available: boolean
  annotated_video_url: string | null
  statistics: {
    frames_processed: number
    video_duration_seconds: number
    video_width: number
    video_height: number
    vehicles_detected: number
    active_tracks: number
    plates_detected: number
    plates_recognized: number
    plates_low_confidence: number
    plates_verified: number
    plates_tentative: number
    observations_stored: number
    processing_duration_seconds: number
    processing_fps: number
  }
  observations: IngestObservation[]
}

const MAX_DEMO_DURATION_SECONDS = 180

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function plateStatusLabel(obs: {
  plate_status: string
  plate_text: string | null
}): { label: string; tone: 'ok' | 'muted' | 'warn' } {
  switch (obs.plate_status) {
    case 'recognized':
      return { label: obs.plate_text || 'Recognized', tone: 'ok' }
    case 'low_confidence':
      return { label: `${obs.plate_text || '?'} — low confidence, verification required`, tone: 'warn' }
    case 'detected_not_read':
      return { label: 'Plate detected, text not read', tone: 'warn' }
    case 'unavailable':
      return { label: 'OCR unavailable — plate text cannot be generated', tone: 'warn' }
    case 'no_plate_detected':
    default:
      return { label: 'No plate detected', tone: 'muted' }
  }
}

const VideoDemoPage: React.FC = () => {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [mode, setMode] = useState<Mode>('camera-media')

  const [cameras, setCameras] = useState<Camera[]>([])
  const [camerasError, setCamerasError] = useState<string | null>(null)
  const [selectedCamera, setSelectedCamera] = useState<string>('')

  const [file, setFile] = useState<File | null>(null)
  const [videoDurationSec, setVideoDurationSec] = useState<number | null>(null)

  const [stage, setStage] = useState<Stage>('idle')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<IngestResult | null>(null)

  // Camera-folder AI processing (images and/or video already sitting in
  // this camera's local folder - see demo/camera_simulator.py). Distinct
  // from the "upload your own video" flow above.
  const [mediaInfo, setMediaInfo] = useState<CameraMediaInfo | null>(null)
  const [mediaInfoError, setMediaInfoError] = useState<string | null>(null)
  const [frameSpeed, setFrameSpeed] = useState<number>(5)
  const [maxFrames, setMaxFrames] = useState<number>(0) // 0 = no cap
  const [camProcessing, setCamProcessing] = useState(false)
  const [camError, setCamError] = useState<string | null>(null)
  const [camResult, setCamResult] = useState<CameraProcessResult | null>(null)

  // Mode 2 (real-time validation stream over the existing WebSocket) state.
  const liveWsRef = useRef<WebSocket | null>(null)
  const [liveStatus, setLiveStatus] = useState<'idle' | 'connecting' | 'streaming' | 'done' | 'error'>('idle')
  const [liveFrame, setLiveFrame] = useState<LiveStreamFrameMsg | null>(null)
  const [liveDone, setLiveDone] = useState<LiveStreamDoneMsg | null>(null)
  const [liveError, setLiveError] = useState<string | null>(null)
  const [liveVideoName, setLiveVideoName] = useState<string | null>(null)
  // SIH26127 real CP PLUS/RTSP camera integration: the "started" message's
  // own is_real_camera field - which camera this stream actually turned
  // out to be for this connection, not assumed in advance. Defaults to
  // false (the pre-existing "Recorded CCTV" behavior) until a real
  // "started" message says otherwise.
  const [liveIsRealCamera, setLiveIsRealCamera] = useState(false)

  useEffect(() => {
    api
      .getCameras()
      .then((list) => {
        setCameras(list)
        if (list.length > 0) setSelectedCamera(list[0].camera_id)
      })
      .catch(() => setCamerasError('Could not load the camera list. Traffic Analytics and other pages may also be affected.'))
  }, [])

  useEffect(() => {
    if (!selectedCamera || mode !== 'camera-media') return
    setMediaInfo(null)
    setMediaInfoError(null)
    api
      .getCameraMedia(selectedCamera)
      .then((info) => setMediaInfo(info))
      .catch(() => setMediaInfoError('Could not check this camera\'s media folder.'))
  }, [selectedCamera, mode])

  const handleProcessCameraMedia = async () => {
    if (!selectedCamera) return
    setCamError(null)
    setCamResult(null)
    setCamProcessing(true)
    try {
      const response = await api.processCamera(selectedCamera, frameSpeed, maxFrames > 0 ? maxFrames : null)
      setCamResult(response)
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'AI processing failed unexpectedly. Please try again.'
      setCamError(typeof detail === 'string' ? detail : 'AI processing failed.')
    } finally {
      setCamProcessing(false)
    }
  }

  const stopLiveStream = () => {
    const ws = liveWsRef.current
    if (ws) {
      ws.close()
      liveWsRef.current = null
    }
  }

  // Release the WebSocket if the operator navigates away mid-stream - a
  // real backend inference job must not keep running unwatched.
  useEffect(() => stopLiveStream, [])

  const startLiveStream = () => {
    if (!selectedCamera) return
    stopLiveStream()
    setLiveStatus('connecting')
    setLiveFrame(null)
    setLiveDone(null)
    setLiveError(null)
    setLiveVideoName(null)
    setLiveIsRealCamera(false)

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/api/v1/observations/live-stream/${selectedCamera}`)
    liveWsRef.current = ws

    ws.onmessage = (event) => {
      let msg: any
      try {
        msg = JSON.parse(event.data)
      } catch {
        return
      }
      if (msg.type === 'started') {
        setLiveStatus('streaming')
        setLiveVideoName(msg.source_label || msg.video || null)
        setLiveIsRealCamera(msg.is_real_camera === true)
      } else if (msg.type === 'frame') {
        setLiveFrame(msg)
      } else if (msg.type === 'done') {
        setLiveDone(msg)
        setLiveStatus('done')
      } else if (msg.type === 'error') {
        setLiveError(msg.detail || 'The live stream ended unexpectedly.')
        setLiveStatus('error')
      }
    }
    ws.onerror = () => {
      setLiveError('Could not connect to the real-time validation stream.')
      setLiveStatus('error')
    }
    ws.onclose = () => {
      setLiveStatus((prev) => (prev === 'streaming' || prev === 'connecting' ? 'idle' : prev))
    }
  }

  const resetFile = () => {
    setFile(null)
    setVideoDurationSec(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleFileChosen = (chosen: File | null) => {
    setError(null)
    setResult(null)
    setStage('idle')
    if (!chosen) {
      resetFile()
      return
    }
    setFile(chosen)
    // Read real duration from the browser's own video metadata - not a
    // guess, an actual client-side probe of the file the user picked.
    const url = URL.createObjectURL(chosen)
    const probe = document.createElement('video')
    probe.preload = 'metadata'
    probe.onloadedmetadata = () => {
      setVideoDurationSec(probe.duration)
      URL.revokeObjectURL(url)
    }
    probe.onerror = () => {
      setVideoDurationSec(null)
      URL.revokeObjectURL(url)
    }
    probe.src = url
  }

  const handleProcess = async () => {
    if (!file || !selectedCamera) return
    setError(null)
    setResult(null)
    setStage('uploading')
    setUploadProgress(0)
    try {
      const response = await api.ingestVideo(file, selectedCamera, (pct) => {
        setUploadProgress(pct)
        if (pct >= 100) setStage('processing')
      })
      setResult(response)
      setStage('done')
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Video processing failed unexpectedly. Please try a shorter clip or a different file.'
      setError(typeof detail === 'string' ? detail : 'Video processing failed.')
      setStage('error')
    }
  }

  const handleReset = () => {
    resetFile()
    setResult(null)
    setError(null)
    setStage('idle')
    setUploadProgress(0)
  }

  const recognizedPlates = (result?.observations || []).filter((o) => o.plate_status === 'recognized' && o.plate_text)

  const isProcessing = stage === 'uploading' || stage === 'processing'
  const durationTooLong = videoDurationSec !== null && videoDurationSec > MAX_DEMO_DURATION_SECONDS

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <ScanLine className="text-signal-400" />
          Detection Pipeline
        </h1>
        <p className="text-sm text-muted">
          Run the real vehicle detection, plate detection, and OCR pipeline on camera footage —
          either media already sitting in a camera's folder, or a video you upload. Every result
          below is a live output of the pipeline, written to the same database the rest of TrackX reads.
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 border-b border-border">
        <button
          onClick={() => setMode('camera-media')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            mode === 'camera-media'
              ? 'border-signal-500 text-white'
              : 'border-transparent text-muted hover:text-white'
          }`}
        >
          <ImageIcon size={15} /> Camera Media
        </button>
        <button
          onClick={() => setMode('upload')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            mode === 'upload'
              ? 'border-signal-500 text-white'
              : 'border-transparent text-muted hover:text-white'
          }`}
        >
          <UploadCloud size={15} /> Upload Video
        </button>
        <button
          onClick={() => setMode('live-ws')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            mode === 'live-ws'
              ? 'border-signal-500 text-white'
              : 'border-transparent text-muted hover:text-white'
          }`}
        >
          <Radio size={15} /> Live Stream (WS)
        </button>
      </div>

      {mode === 'camera-media' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 card p-5 space-y-5">
            <div>
              <label className="text-xs font-semibold text-muted uppercase tracking-wide">Camera</label>
              {camerasError ? (
                <div className="mt-2 text-xs text-critical-400 flex items-center gap-1.5">
                  <XCircle size={14} /> {camerasError}
                </div>
              ) : (
                <select
                  value={selectedCamera}
                  onChange={(e) => setSelectedCamera(e.target.value)}
                  disabled={camProcessing || cameras.length === 0}
                  className="mt-2 w-full bg-surface-light border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-signal-500 disabled:opacity-60"
                >
                  {cameras.length === 0 && <option>Loading cameras…</option>}
                  {cameras.map((cam) => (
                    <option key={cam.camera_id} value={cam.camera_id}>
                      {cam.camera_id} — {cam.name}
                    </option>
                  ))}
                </select>
              )}

              <div className="mt-2 text-xs">
                {mediaInfoError ? (
                  <span className="text-critical-400">{mediaInfoError}</span>
                ) : mediaInfo ? (
                  mediaInfo.folder_exists ? (
                    <span className="text-muted">
                      <b className="text-white">{mediaInfo.available_images}</b> image(s),{' '}
                      <b className="text-white">{mediaInfo.available_videos}</b> video(s) available for{' '}
                      {selectedCamera}.
                    </span>
                  ) : (
                    <span className="text-caution-400">
                      No local media folder for {selectedCamera} yet — add files under
                      data/cameras/{selectedCamera}/images/ or videos/.
                    </span>
                  )
                ) : (
                  <span className="text-muted">Checking available media…</span>
                )}
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted uppercase tracking-wide" title="Only affects video files, not still images">
                Frame Speed (every Nth frame)
              </label>
              <input
                type="number"
                min={1}
                value={frameSpeed}
                disabled={camProcessing}
                onChange={(e) => setFrameSpeed(Math.max(1, parseInt(e.target.value, 10) || 1))}
                className="mt-2 w-full bg-surface-light border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-signal-500 disabled:opacity-60"
              />
              <p className="mt-1 text-[11px] text-muted">Only affects video files in this camera's folder — still images are always processed in full.</p>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted uppercase tracking-wide">Max Frames (0 = all)</label>
              <input
                type="number"
                min={0}
                value={maxFrames}
                disabled={camProcessing}
                onChange={(e) => setMaxFrames(Math.max(0, parseInt(e.target.value, 10) || 0))}
                className="mt-2 w-full bg-surface-light border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-signal-500 disabled:opacity-60"
              />
            </div>

            <button
              onClick={handleProcessCameraMedia}
              disabled={!selectedCamera || camProcessing || !mediaInfo?.folder_exists}
              className="w-full bg-signal-600 hover:bg-signal-500 disabled:bg-surface-light disabled:text-muted text-white px-4 py-2.5 rounded text-sm font-semibold transition-colors flex items-center justify-center gap-2"
            >
              {camProcessing ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Processing…
                </>
              ) : (
                <>
                  <Play size={16} /> Start Detection Pipeline
                </>
              )}
            </button>

            {camProcessing && (
              <p className="text-[11px] text-muted text-center">
                Running vehicle detection, plate detection, and OCR on this camera's media. This can
                take a few seconds to a couple of minutes depending on how much media is available.
              </p>
            )}
          </div>

          <div className="lg:col-span-2 space-y-6">
            {!camResult && !camProcessing && !camError && (
              <div className="card p-10 text-center text-muted">
                <ScanLine size={36} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm">Choose a camera and click Start Detection Pipeline.</p>
                <p className="text-xs mt-1">Results will appear here — nothing is generated until you run the pipeline.</p>
              </div>
            )}

            {camError && (
              <div className="card p-5 border-critical-500/40 bg-critical-500/10 text-critical-400 text-sm flex items-start gap-2">
                <XCircle size={18} className="shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Processing failed</p>
                  <p className="mt-1 text-critical-400/90">{camError}</p>
                </div>
              </div>
            )}

            {camResult && (
              <>
                <div className="card p-4 border-clear-500/30 bg-clear-500/5 flex items-center gap-2 text-clear-400 text-sm">
                  <CheckCircle2 size={18} />
                  <span>
                    Processed <b>{camResult.camera_name}</b>: {camResult.statistics.vehicles_detected} vehicle
                    observation(s), {camResult.statistics.observations_stored} written to the database.
                  </span>
                </div>

                {!camResult.ocr_available && (
                  <div className="card p-3 border-caution-500/30 bg-caution-500/5 text-caution-400 text-xs flex items-center gap-2">
                    <Info size={14} />
                    OCR unavailable — plate text cannot be generated for this run.
                  </div>
                )}
                {camResult.ocr_available && !camResult.plate_detector_available && (
                  <div className="card p-3 border-caution-500/30 bg-caution-500/5 text-caution-400 text-xs flex items-center gap-2">
                    <Info size={14} />
                    Plate detector unavailable — only vehicle detections are shown below.
                  </div>
                )}

                {(() => {
                  const latest = [...camResult.observations].reverse().find((o) => o.plate_status === 'recognized' && o.plate_text)
                  if (!latest) return null
                  return (
                    <div className="card p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs text-muted uppercase tracking-wide">Latest Plate</p>
                          <p className="text-2xl font-bold text-white font-mono">{latest.plate_text}</p>
                        </div>
                        {latest.ocr_confidence !== null && (
                          <span className="text-xs font-semibold text-clear-400 bg-clear-500/10 border border-clear-500/20 rounded px-2 py-1">
                            {Math.round((latest.ocr_confidence || 0) * 100)}% confidence
                          </span>
                        )}
                      </div>
                      {/*
                        SIH26127 fix (2026-09-14): this used to render the
                        same real annotated_url image inside a tiny 80x80px
                        box with object-cover - on a wide source photo (the
                        car crops we're actually processing run well past
                        1000px wide) that crops down to a near-meaningless
                        sliver, which is exactly why "I don't clearly see
                        anything" - the image loading correctly was never
                        the remaining problem, its display size was. Shown
                        full-width with object-contain (whole frame visible,
                        never cropped) and click-to-open-full-size, matching
                        how the annotated frame is meant to be read: the
                        vehicle box, the plate box, and the plate-text label
                        the pipeline actually drew on it.
                      */}
                      {latest.annotated_url ? (
                        <a href={latest.annotated_url} target="_blank" rel="noopener noreferrer" title="Open full size">
                          <img
                            src={latest.annotated_url}
                            alt="Latest detection - annotated frame"
                            className="w-full max-h-[440px] object-contain rounded border border-border bg-black cursor-zoom-in"
                          />
                        </a>
                      ) : (
                        <div className="w-full h-40 rounded bg-surface flex items-center justify-center border border-border">
                          <Car size={26} className="text-muted" />
                        </div>
                      )}
                    </div>
                  )
                })()}

                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  <StatCard label="Images Processed" value={camResult.statistics.images_processed} />
                  <StatCard label="Videos Processed" value={camResult.statistics.videos_processed} />
                  <StatCard label="Vehicles Detected" value={camResult.statistics.vehicles_detected} icon={<Car size={14} />} />
                  <StatCard label="Plates Detected" value={camResult.statistics.plates_detected} />
                  <StatCard label="Plates Recognized" value={camResult.statistics.plates_recognized} />
                  <StatCard label="Processing Time" value={`${camResult.statistics.processing_duration_seconds}s`} />
                </div>

                <div className="card p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-white">Detected Vehicles &amp; Plates</h3>
                    <span className="text-xs text-muted">{camResult.observations.length} vehicle(s)</span>
                  </div>

                  {camResult.observations.length === 0 ? (
                    <p className="text-sm text-muted text-center py-6">
                      No vehicles were detected in this camera's media. This is a real result, not an
                      error — the folder may only contain empty/background frames.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {camResult.observations.map((obs, idx) => {
                        const status = plateStatusLabel(obs)
                        return (
                          <div
                            key={idx}
                            className="flex items-center gap-3 bg-surface-light border border-border rounded p-2.5"
                          >
                            {obs.annotated_url || obs.plate_crop_url ? (
                              <a
                                href={obs.annotated_url || obs.plate_crop_url || ''}
                                target="_blank"
                                rel="noopener noreferrer"
                                title="Open full size"
                                className="w-24 h-24 rounded bg-black flex items-center justify-center overflow-hidden shrink-0 border border-border"
                              >
                                <img
                                  src={obs.annotated_url || obs.plate_crop_url || ''}
                                  alt="Detection - annotated frame"
                                  className="w-full h-full object-contain cursor-zoom-in"
                                />
                              </a>
                            ) : (
                              <div className="w-24 h-24 rounded bg-surface flex items-center justify-center shrink-0 border border-border">
                                <Car size={20} className="text-muted" />
                              </div>
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-semibold text-white capitalize">
                                  {obs.vehicle_type || 'Vehicle'}
                                </span>
                                <span className="text-[11px] text-muted">
                                  {obs.source_type === 'image' ? 'Image' : 'Video'}
                                  {obs.source_file ? `: ${obs.source_file}` : ''}
                                </span>
                              </div>
                              <div
                                className={`text-xs mt-0.5 font-mono ${
                                  status.tone === 'ok'
                                    ? 'text-clear-400'
                                    : status.tone === 'warn'
                                    ? 'text-caution-400'
                                    : 'text-muted'
                                }`}
                              >
                                {status.label}
                              </div>
                            </div>
                            {obs.plate_status === 'recognized' && obs.plate_text && (
                              <button
                                onClick={() => navigate(`/vehicles?plate=${encodeURIComponent(obs.plate_text!)}`)}
                                className="text-xs bg-signal-600/20 text-signal-400 hover:bg-signal-600/40 px-3 py-1.5 rounded transition-colors font-medium flex items-center gap-1 shrink-0"
                              >
                                <Search size={12} /> Vehicle Intelligence
                              </button>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {mode === 'upload' && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Step 1 + 2: camera + upload */}
        <div className="lg:col-span-1 card p-5 space-y-5">
          <div>
            <label className="text-xs font-semibold text-muted uppercase tracking-wide">1. Camera</label>
            {camerasError ? (
              <div className="mt-2 text-xs text-critical-400 flex items-center gap-1.5">
                <XCircle size={14} /> {camerasError}
              </div>
            ) : (
              <select
                value={selectedCamera}
                onChange={(e) => setSelectedCamera(e.target.value)}
                disabled={isProcessing || cameras.length === 0}
                className="mt-2 w-full bg-surface-light border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-signal-500 disabled:opacity-60"
              >
                {cameras.length === 0 && <option>Loading cameras…</option>}
                {cameras.map((cam) => (
                  <option key={cam.camera_id} value={cam.camera_id}>
                    {cam.camera_id} — {cam.name}
                  </option>
                ))}
              </select>
            )}
            <p className="mt-1.5 text-[11px] text-muted">
              Observations from this run are attributed to the selected camera's real coordinates.
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-muted uppercase tracking-wide">2. CCTV Video</label>
            <div
              className={`mt-2 border-2 border-dashed rounded p-5 text-center transition-colors ${
                file ? 'border-signal-500/50 bg-signal-500/5' : 'border-border hover:border-signal-500/40'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="video/mp4,video/avi,video/quicktime,video/x-matroska,video/webm,.mp4,.avi,.mov,.mkv,.webm"
                className="hidden"
                id="video-upload-input"
                disabled={isProcessing}
                onChange={(e) => handleFileChosen(e.target.files?.[0] || null)}
              />
              {!file ? (
                <label htmlFor="video-upload-input" className="cursor-pointer flex flex-col items-center gap-2 text-muted">
                  <UploadCloud size={28} className="text-signal-400" />
                  <span className="text-sm text-white">Click to choose a video file</span>
                  <span className="text-[11px]">MP4, AVI, MOV, MKV, WebM — up to 200 MB, {MAX_DEMO_DURATION_SECONDS}s</span>
                </label>
              ) : (
                <div className="flex flex-col items-center gap-1.5">
                  <FileVideo size={26} className="text-signal-400" />
                  <span className="text-sm text-white font-medium break-all">{file.name}</span>
                  <span className="text-xs text-muted">
                    {formatBytes(file.size)}
                    {videoDurationSec !== null && ` • ${videoDurationSec.toFixed(1)}s`}
                  </span>
                  {!isProcessing && (
                    <button
                      onClick={() => handleFileChosen(null)}
                      className="mt-1 text-[11px] text-critical-400 hover:text-critical-300 underline"
                    >
                      Remove
                    </button>
                  )}
                </div>
              )}
            </div>
            {durationTooLong && (
              <div className="mt-2 text-xs text-caution-400 flex items-center gap-1.5">
                <Info size={13} />
                This clip is ~{Math.round(videoDurationSec!)}s, over the {MAX_DEMO_DURATION_SECONDS}s demo
                limit — the server will reject it. Trim it and try again.
              </div>
            )}
          </div>

          <button
            onClick={handleProcess}
            disabled={!file || !selectedCamera || isProcessing || durationTooLong}
            className="w-full bg-signal-600 hover:bg-signal-500 disabled:bg-surface-light disabled:text-muted text-white px-4 py-2.5 rounded text-sm font-semibold transition-colors flex items-center justify-center gap-2"
          >
            {isProcessing ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                {stage === 'uploading' ? `Uploading… ${uploadProgress}%` : 'Processing video…'}
              </>
            ) : (
              <>
                <ScanLine size={16} />
                Process Video
              </>
            )}
          </button>

          {stage === 'processing' && (
            <p className="text-[11px] text-muted text-center">
              Running vehicle detection, plate detection, and OCR frame by frame. A short demo clip
              usually takes a few seconds to a couple of minutes.
            </p>
          )}

          {(result || error) && !isProcessing && (
            <button
              onClick={handleReset}
              className="w-full text-xs text-muted hover:text-white flex items-center justify-center gap-1.5"
            >
              <RotateCcw size={12} /> Process another video
            </button>
          )}
        </div>

        {/* Steps 5-9: result */}
        <div className="lg:col-span-2 space-y-6">
          {stage === 'idle' && !result && (
            <div className="card p-10 text-center text-muted">
              <Video size={36} className="mx-auto mb-3 opacity-40" />
              <p className="text-sm">Choose a camera and a video, then click Process Video.</p>
              <p className="text-xs mt-1">Results will appear here — nothing is generated until you run the pipeline.</p>
            </div>
          )}

          {error && stage === 'error' && (
            <div className="card p-5 border-critical-500/40 bg-critical-500/10 text-critical-400 text-sm flex items-start gap-2">
              <XCircle size={18} className="shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Processing failed</p>
                <p className="mt-1 text-critical-400/90">{error}</p>
              </div>
            </div>
          )}

          {result && stage === 'done' && (
            <>
              <div className="card p-4 border-clear-500/30 bg-clear-500/5 flex items-center gap-2 text-clear-400 text-sm">
                <CheckCircle2 size={18} />
                <span>
                  Processed <b>{result.video_filename}</b> on <b>{result.camera_name}</b> in{' '}
                  {result.statistics.processing_duration_seconds}s.
                </span>
              </div>

              {!result.ocr_available && (
                <div className="card p-3 border-caution-500/30 bg-caution-500/5 text-caution-400 text-xs flex items-center gap-2">
                  <Info size={14} />
                  OCR unavailable — plate text cannot be generated for this run. Vehicles and plate
                  regions were still detected below.
                </div>
              )}
              {result.ocr_available && !result.plate_detector_available && (
                <div className="card p-3 border-caution-500/30 bg-caution-500/5 text-caution-400 text-xs flex items-center gap-2">
                  <Info size={14} />
                  Plate detector unavailable — only vehicle detections are shown below.
                </div>
              )}

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard label="Frames Processed" value={result.statistics.frames_processed} />
                <StatCard label="Active Tracks" value={result.statistics.active_tracks} icon={<Car size={14} />} />
                <StatCard label="Plates Detected" value={result.statistics.plates_detected} />
                <StatCard label="Plates Recognized" value={result.statistics.plates_recognized} />
                <StatCard label="Verified" value={result.statistics.plates_verified} />
                <StatCard label="Tentative" value={result.statistics.plates_tentative} />
                <StatCard label="Low Confidence" value={result.statistics.plates_low_confidence} />
                <StatCard label="Resolution" value={result.statistics.video_width ? `${result.statistics.video_width}×${result.statistics.video_height}` : '—'} />
                <StatCard label="Processing Time" value={`${result.statistics.processing_duration_seconds}s`} />
                <StatCard label="Processing FPS" value={result.statistics.processing_fps} />
              </div>

              {result.annotated_video_url ? (
                <div className="card p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-white">Annotated Output Video</h3>
                    <span className="text-xs text-muted">Real detection overlays drawn on the processed footage</span>
                  </div>
                  <video
                    src={result.annotated_video_url}
                    controls
                    className="w-full rounded border border-border bg-black"
                  />
                  <p className="mt-2 text-[11px] text-muted">
                    Every box, Track ID, and plate label in this video comes from an actual detection recorded during
                    processing of the uploaded clip — nothing is drawn from an estimate or template.
                  </p>
                </div>
              ) : (
                <div className="card p-3 border-caution-500/30 bg-caution-500/5 text-caution-400 text-xs flex items-center gap-2">
                  <Info size={14} />
                  Annotated output video could not be generated for this run (see server logs). Detection results
                  below are still real.
                </div>
              )}

              <div className="card p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-white">Detected Vehicles &amp; Plates</h3>
                  <span className="text-xs text-muted">{result.observations.length} vehicle(s)</span>
                </div>

                {result.observations.length === 0 ? (
                  <p className="text-sm text-muted text-center py-6">
                    No vehicles were detected in this clip. This is a real result, not an error — try a
                    clip with clearer vehicle content.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {result.observations.map((obs, idx) => {
                      const status = plateStatusLabel(obs)
                      return (
                        <div
                          key={idx}
                          className="flex items-center gap-3 bg-surface-light border border-border rounded p-2.5"
                        >
                          <div className="w-14 h-14 rounded bg-surface flex items-center justify-center overflow-hidden shrink-0 border border-border">
                            {obs.plate_crop_url ? (
                              <img src={obs.plate_crop_url} alt="Plate crop" className="w-full h-full object-cover" />
                            ) : (
                              <Car size={20} className="text-muted" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-semibold text-white capitalize">
                                {obs.vehicle_type || 'Vehicle'}
                              </span>
                              <span className="text-[11px] text-muted">Track #{obs.track_id ?? '—'}</span>
                              {obs.direction && obs.direction !== 'unknown' && (
                                <span className="text-[11px] text-muted">• {obs.direction.replace(/_/g, ' ')}</span>
                              )}
                              {obs.first_seen_frame !== null && obs.last_seen_frame !== null && (
                                <span className="text-[11px] text-muted">
                                  • frames {obs.first_seen_frame}–{obs.last_seen_frame}
                                </span>
                              )}
                              {obs.plate_state && (
                                <span
                                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide ${
                                    obs.plate_state === 'VERIFIED'
                                      ? 'bg-clear-500/15 text-clear-400'
                                      : obs.plate_state === 'TENTATIVE'
                                      ? 'bg-caution-500/15 text-caution-400'
                                      : obs.plate_state === 'LOW_CONFIDENCE'
                                      ? 'bg-caution-500/15 text-caution-400'
                                      : 'bg-surface text-muted'
                                  }`}
                                >
                                  {obs.plate_state}
                                </span>
                              )}
                            </div>
                            <div
                              className={`text-xs mt-0.5 font-mono ${
                                status.tone === 'ok'
                                  ? 'text-clear-400'
                                  : status.tone === 'warn'
                                  ? 'text-caution-400'
                                  : 'text-muted'
                              }`}
                            >
                              {status.label}
                            </div>
                            {(obs.temporal_support || obs.preprocessing_mode || obs.plate_quality_score !== null) && (
                              <div className="text-[10px] text-muted mt-0.5">
                                {obs.temporal_support ? `${obs.temporal_support} frame(s) of evidence` : null}
                                {obs.final_fusion_score !== null && obs.final_fusion_score !== undefined
                                  ? ` • fusion score ${obs.final_fusion_score.toFixed(2)}`
                                  : null}
                                {obs.preprocessing_mode ? ` • ${obs.preprocessing_mode}` : null}
                                {obs.plate_quality_score !== null && obs.plate_quality_score !== undefined
                                  ? ` • crop quality ${obs.plate_quality_score.toFixed(2)}`
                                  : null}
                              </div>
                            )}
                          </div>
                          {obs.plate_status === 'recognized' && obs.plate_text && (
                            <button
                              onClick={() => navigate(`/vehicles?plate=${encodeURIComponent(obs.plate_text!)}`)}
                              className="text-xs bg-signal-600/20 text-signal-400 hover:bg-signal-600/40 px-3 py-1.5 rounded transition-colors font-medium flex items-center gap-1 shrink-0"
                            >
                              <Search size={12} /> Vehicle Intelligence
                            </button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {recognizedPlates.length > 0 && (
                <div className="card p-4">
                  <h3 className="text-sm font-bold text-white mb-3">Search a Recognized Plate</h3>
                  <div className="flex flex-wrap gap-2">
                    {recognizedPlates.map((obs, idx) => (
                      <button
                        key={idx}
                        onClick={() => navigate(`/vehicles?plate=${encodeURIComponent(obs.plate_text!)}`)}
                        className="text-xs font-mono bg-surface-light border border-border hover:border-signal-500/50 text-white px-3 py-1.5 rounded transition-colors flex items-center gap-1.5"
                      >
                        <Search size={12} className="text-signal-400" />
                        {obs.plate_text}
                      </button>
                    ))}
                    <button
                      onClick={() => navigate('/trajectory')}
                      className="text-xs bg-surface-light border border-border hover:border-signal-500/50 text-muted hover:text-white px-3 py-1.5 rounded transition-colors flex items-center gap-1.5"
                    >
                      <RouteIcon size={12} />
                      Open Trajectory Search
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      )}

      {mode === 'live-ws' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 card p-5 space-y-5">
            <div>
              <label className="text-xs font-semibold text-muted uppercase tracking-wide">Camera</label>
              {camerasError ? (
                <div className="mt-2 text-xs text-critical-400 flex items-center gap-1.5">
                  <XCircle size={14} /> {camerasError}
                </div>
              ) : (
                <select
                  value={selectedCamera}
                  onChange={(e) => setSelectedCamera(e.target.value)}
                  disabled={liveStatus === 'connecting' || liveStatus === 'streaming' || cameras.length === 0}
                  className="mt-2 w-full bg-surface-light border border-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-signal-500 disabled:opacity-60"
                >
                  {cameras.length === 0 && <option>Loading cameras…</option>}
                  {cameras.map((cam) => (
                    <option key={cam.camera_id} value={cam.camera_id}>
                      {cam.camera_id} — {cam.name}
                    </option>
                  ))}
                </select>
              )}
              <p className="mt-1.5 text-[11px] text-muted">
                Streams this camera frame by frame over a WebSocket instead of waiting for the whole
                run to finish - a real-time validation view of the same pipeline, not a second demo.
                If this camera has a real RTSP/RTSPS source configured it streams from that live;
                otherwise it re-processes a real video already sitting in the camera's local folder.
              </p>
            </div>

            {liveStatus !== 'streaming' && liveStatus !== 'connecting' ? (
              <button
                onClick={startLiveStream}
                disabled={!selectedCamera}
                className="w-full bg-signal-600 hover:bg-signal-500 disabled:bg-surface-light disabled:text-muted text-white px-4 py-2.5 rounded text-sm font-semibold transition-colors flex items-center justify-center gap-2"
              >
                <Radio size={16} /> Connect &amp; Stream
              </button>
            ) : (
              <button
                onClick={stopLiveStream}
                className="w-full bg-critical-600/20 hover:bg-critical-600/30 text-critical-400 border border-critical-500/30 px-4 py-2.5 rounded text-sm font-semibold transition-colors flex items-center justify-center gap-2"
              >
                <Square size={15} /> Disconnect
              </button>
            )}
          </div>

          <div className="lg:col-span-2 space-y-4">
            <div className="card p-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
              <span className="flex items-center gap-1.5">
                <span className={`live-dot ${liveStatus === 'streaming' ? 'is-live' : ''}`} />
                <span className="font-semibold text-white">
                  {liveStatus === 'streaming' ? 'PROCESSING' : liveStatus === 'connecting' ? 'CONNECTING…' : liveStatus === 'done' ? 'FINISHED' : liveStatus === 'error' ? 'ERROR' : 'IDLE'}
                </span>
              </span>
              {liveStatus === 'streaming' || liveStatus === 'done' ? (
                <span className={liveIsRealCamera ? 'text-clear-400 font-semibold' : 'text-muted'}>
                  Source: {liveIsRealCamera ? 'Live Camera' : 'Recorded CCTV'}
                  {liveVideoName ? ` (${liveVideoName})` : ''}
                </span>
              ) : (
                <span className="text-muted">Source: not yet known — connect to find out</span>
              )}
              <span className="text-muted">Mode: Real-time validation stream</span>
            </div>

            {liveStatus === 'idle' && !liveFrame && (
              <div className="card p-10 text-center text-muted">
                <Radio size={36} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm">Choose a camera with a video and click Connect &amp; Stream.</p>
              </div>
            )}

            {liveStatus === 'error' && liveError && (
              <div className="card p-5 border-critical-500/40 bg-critical-500/10 text-critical-400 text-sm flex items-start gap-2">
                <XCircle size={18} className="shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Stream failed</p>
                  <p className="mt-1 text-critical-400/90">{liveError}</p>
                </div>
              </div>
            )}

            {liveFrame && (
              <div className="card p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-white">Live Annotated Frame</h3>
                  <span className="text-xs text-muted">frame #{liveFrame.frame_idx}</span>
                </div>
                <img
                  src={`data:image/jpeg;base64,${liveFrame.jpeg_b64}`}
                  alt="Live processed frame"
                  className="w-full rounded border border-border bg-black"
                />
                <div className="grid grid-cols-3 gap-3 mt-3">
                  <StatCard label="Vehicles In Frame" value={liveFrame.vehicles_in_frame} icon={<Car size={14} />} />
                  <StatCard label="Elapsed" value={`${liveFrame.elapsed_seconds}s`} />
                  <StatCard label="Processing FPS" value={liveFrame.fps_so_far} />
                </div>
              </div>
            )}

            {liveDone && (
              <div className="card p-4 border-clear-500/30 bg-clear-500/5">
                <div className="flex items-center gap-2 text-clear-400 text-sm mb-3">
                  <CheckCircle2 size={18} />
                  <span>Stream finished in {liveDone.duration_seconds}s.</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <StatCard label="Tracks" value={liveDone.tracks} />
                  <StatCard label="Verified Plates" value={liveDone.plates_verified} />
                  <StatCard label="Tentative Plates" value={liveDone.plates_tentative} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const StatCard: React.FC<{ label: string; value: React.ReactNode; icon?: React.ReactNode }> = ({ label, value, icon }) => (
  <div className="card p-3">
    <div className="flex items-center gap-1.5 text-[11px] text-muted uppercase tracking-wide">
      {icon}
      {label}
    </div>
    <p className="text-xl font-bold text-white mt-1">{value}</p>
  </div>
)

export default VideoDemoPage
