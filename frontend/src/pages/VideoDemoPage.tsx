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
} from 'lucide-react'

type Stage = 'idle' | 'uploading' | 'processing' | 'done' | 'error'
type Mode = 'camera-media' | 'upload'

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
  plate_status: 'recognized' | 'detected_not_read' | 'no_plate_detected' | 'unavailable'
  ocr_confidence: number | null
  plate_confidence: number | null
  vehicle_confidence: number | null
  timestamp: string | null
  frame_index: number | null
  direction: string | null
  plate_crop_url: string | null
}

interface IngestResult {
  camera_id: string
  camera_name: string
  video_filename: string
  plate_detector_available: boolean
  ocr_available: boolean
  statistics: {
    frames_processed: number
    video_duration_seconds: number
    vehicles_detected: number
    plates_detected: number
    plates_recognized: number
    observations_stored: number
    processing_duration_seconds: number
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
          <ScanLine className="text-blue-400" />
          AI Processing
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
              ? 'border-blue-500 text-white'
              : 'border-transparent text-muted hover:text-white'
          }`}
        >
          <ImageIcon size={15} /> Camera Media
        </button>
        <button
          onClick={() => setMode('upload')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            mode === 'upload'
              ? 'border-blue-500 text-white'
              : 'border-transparent text-muted hover:text-white'
          }`}
        >
          <UploadCloud size={15} /> Upload Video
        </button>
      </div>

      {mode === 'camera-media' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 card p-5 space-y-5">
            <div>
              <label className="text-xs font-semibold text-muted uppercase tracking-wide">Camera</label>
              {camerasError ? (
                <div className="mt-2 text-xs text-red-300 flex items-center gap-1.5">
                  <XCircle size={14} /> {camerasError}
                </div>
              ) : (
                <select
                  value={selectedCamera}
                  onChange={(e) => setSelectedCamera(e.target.value)}
                  disabled={camProcessing || cameras.length === 0}
                  className="mt-2 w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 disabled:opacity-60"
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
                  <span className="text-red-300">{mediaInfoError}</span>
                ) : mediaInfo ? (
                  mediaInfo.folder_exists ? (
                    <span className="text-muted">
                      <b className="text-white">{mediaInfo.available_images}</b> image(s),{' '}
                      <b className="text-white">{mediaInfo.available_videos}</b> video(s) available for{' '}
                      {selectedCamera}.
                    </span>
                  ) : (
                    <span className="text-amber-300">
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
                className="mt-2 w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 disabled:opacity-60"
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
                className="mt-2 w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 disabled:opacity-60"
              />
            </div>

            <button
              onClick={handleProcessCameraMedia}
              disabled={!selectedCamera || camProcessing || !mediaInfo?.folder_exists}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-surface-light disabled:text-muted text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2"
            >
              {camProcessing ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Processing…
                </>
              ) : (
                <>
                  <Play size={16} /> Start AI Processing
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
                <p className="text-sm">Choose a camera and click Start AI Processing.</p>
                <p className="text-xs mt-1">Results will appear here — nothing is generated until you run the pipeline.</p>
              </div>
            )}

            {camError && (
              <div className="card p-5 border-red-500/40 bg-red-500/10 text-red-300 text-sm flex items-start gap-2">
                <XCircle size={18} className="shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Processing failed</p>
                  <p className="mt-1 text-red-300/90">{camError}</p>
                </div>
              </div>
            )}

            {camResult && (
              <>
                <div className="card p-4 border-green-500/30 bg-green-500/5 flex items-center gap-2 text-green-300 text-sm">
                  <CheckCircle2 size={18} />
                  <span>
                    Processed <b>{camResult.camera_name}</b>: {camResult.statistics.vehicles_detected} vehicle
                    observation(s), {camResult.statistics.observations_stored} written to the database.
                  </span>
                </div>

                {!camResult.ocr_available && (
                  <div className="card p-3 border-amber-500/30 bg-amber-500/5 text-amber-300 text-xs flex items-center gap-2">
                    <Info size={14} />
                    OCR unavailable — plate text cannot be generated for this run.
                  </div>
                )}
                {camResult.ocr_available && !camResult.plate_detector_available && (
                  <div className="card p-3 border-amber-500/30 bg-amber-500/5 text-amber-300 text-xs flex items-center gap-2">
                    <Info size={14} />
                    Plate detector unavailable — only vehicle detections are shown below.
                  </div>
                )}

                {(() => {
                  const latest = [...camResult.observations].reverse().find((o) => o.plate_status === 'recognized' && o.plate_text)
                  return latest ? (
                    <div className="card p-4 flex items-center gap-4">
                      <div className="w-20 h-20 rounded-lg bg-surface flex items-center justify-center overflow-hidden shrink-0 border border-border">
                        {latest.annotated_url ? (
                          <img src={latest.annotated_url} alt="Latest detection" className="w-full h-full object-cover" />
                        ) : (
                          <Car size={26} className="text-muted" />
                        )}
                      </div>
                      <div>
                        <p className="text-xs text-muted uppercase tracking-wide">Latest Plate</p>
                        <p className="text-2xl font-bold text-white font-mono">{latest.plate_text}</p>
                        {latest.ocr_confidence !== null && (
                          <p className="text-xs text-green-400 mt-0.5">{Math.round((latest.ocr_confidence || 0) * 100)}% confidence</p>
                        )}
                      </div>
                    </div>
                  ) : null
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
                            className="flex items-center gap-3 bg-surface-light border border-border rounded-lg p-2.5"
                          >
                            <div className="w-14 h-14 rounded bg-surface flex items-center justify-center overflow-hidden shrink-0 border border-border">
                              {obs.annotated_url || obs.plate_crop_url ? (
                                <img
                                  src={obs.annotated_url || obs.plate_crop_url || ''}
                                  alt="Detection"
                                  className="w-full h-full object-cover"
                                />
                              ) : (
                                <Car size={20} className="text-muted" />
                              )}
                            </div>
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
                                    ? 'text-green-400'
                                    : status.tone === 'warn'
                                    ? 'text-amber-300'
                                    : 'text-muted'
                                }`}
                              >
                                {status.label}
                              </div>
                            </div>
                            {obs.plate_status === 'recognized' && obs.plate_text && (
                              <button
                                onClick={() => navigate(`/vehicles?plate=${encodeURIComponent(obs.plate_text!)}`)}
                                className="text-xs bg-blue-600/20 text-blue-400 hover:bg-blue-600/40 px-3 py-1.5 rounded transition-colors font-medium flex items-center gap-1 shrink-0"
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
              <div className="mt-2 text-xs text-red-300 flex items-center gap-1.5">
                <XCircle size={14} /> {camerasError}
              </div>
            ) : (
              <select
                value={selectedCamera}
                onChange={(e) => setSelectedCamera(e.target.value)}
                disabled={isProcessing || cameras.length === 0}
                className="mt-2 w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 disabled:opacity-60"
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
              className={`mt-2 border-2 border-dashed rounded-lg p-5 text-center transition-colors ${
                file ? 'border-blue-500/50 bg-blue-500/5' : 'border-border hover:border-blue-500/40'
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
                  <UploadCloud size={28} className="text-blue-400" />
                  <span className="text-sm text-white">Click to choose a video file</span>
                  <span className="text-[11px]">MP4, AVI, MOV, MKV, WebM — up to 200 MB, {MAX_DEMO_DURATION_SECONDS}s</span>
                </label>
              ) : (
                <div className="flex flex-col items-center gap-1.5">
                  <FileVideo size={26} className="text-blue-400" />
                  <span className="text-sm text-white font-medium break-all">{file.name}</span>
                  <span className="text-xs text-muted">
                    {formatBytes(file.size)}
                    {videoDurationSec !== null && ` • ${videoDurationSec.toFixed(1)}s`}
                  </span>
                  {!isProcessing && (
                    <button
                      onClick={() => handleFileChosen(null)}
                      className="mt-1 text-[11px] text-red-300 hover:text-red-200 underline"
                    >
                      Remove
                    </button>
                  )}
                </div>
              )}
            </div>
            {durationTooLong && (
              <div className="mt-2 text-xs text-amber-300 flex items-center gap-1.5">
                <Info size={13} />
                This clip is ~{Math.round(videoDurationSec!)}s, over the {MAX_DEMO_DURATION_SECONDS}s demo
                limit — the server will reject it. Trim it and try again.
              </div>
            )}
          </div>

          <button
            onClick={handleProcess}
            disabled={!file || !selectedCamera || isProcessing || durationTooLong}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-surface-light disabled:text-muted text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2"
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
            <div className="card p-5 border-red-500/40 bg-red-500/10 text-red-300 text-sm flex items-start gap-2">
              <XCircle size={18} className="shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Processing failed</p>
                <p className="mt-1 text-red-300/90">{error}</p>
              </div>
            </div>
          )}

          {result && stage === 'done' && (
            <>
              <div className="card p-4 border-green-500/30 bg-green-500/5 flex items-center gap-2 text-green-300 text-sm">
                <CheckCircle2 size={18} />
                <span>
                  Processed <b>{result.video_filename}</b> on <b>{result.camera_name}</b> in{' '}
                  {result.statistics.processing_duration_seconds}s.
                </span>
              </div>

              {!result.ocr_available && (
                <div className="card p-3 border-amber-500/30 bg-amber-500/5 text-amber-300 text-xs flex items-center gap-2">
                  <Info size={14} />
                  OCR unavailable — plate text cannot be generated for this run. Vehicles and plate
                  regions were still detected below.
                </div>
              )}
              {result.ocr_available && !result.plate_detector_available && (
                <div className="card p-3 border-amber-500/30 bg-amber-500/5 text-amber-300 text-xs flex items-center gap-2">
                  <Info size={14} />
                  Plate detector unavailable — only vehicle detections are shown below.
                </div>
              )}

              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <StatCard label="Frames Processed" value={result.statistics.frames_processed} />
                <StatCard label="Vehicles Detected" value={result.statistics.vehicles_detected} icon={<Car size={14} />} />
                <StatCard label="Plates Detected" value={result.statistics.plates_detected} />
                <StatCard label="Plates Recognized" value={result.statistics.plates_recognized} />
                <StatCard label="Observations Stored" value={result.statistics.observations_stored} />
                <StatCard label="Processing Time" value={`${result.statistics.processing_duration_seconds}s`} />
              </div>

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
                          className="flex items-center gap-3 bg-surface-light border border-border rounded-lg p-2.5"
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
                            </div>
                            <div
                              className={`text-xs mt-0.5 font-mono ${
                                status.tone === 'ok'
                                  ? 'text-green-400'
                                  : status.tone === 'warn'
                                  ? 'text-amber-300'
                                  : 'text-muted'
                              }`}
                            >
                              {status.label}
                            </div>
                          </div>
                          {obs.plate_status === 'recognized' && obs.plate_text && (
                            <button
                              onClick={() => navigate(`/vehicles?plate=${encodeURIComponent(obs.plate_text!)}`)}
                              className="text-xs bg-blue-600/20 text-blue-400 hover:bg-blue-600/40 px-3 py-1.5 rounded transition-colors font-medium flex items-center gap-1 shrink-0"
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
                        className="text-xs font-mono bg-surface-light border border-border hover:border-blue-500/50 text-white px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
                      >
                        <Search size={12} className="text-blue-400" />
                        {obs.plate_text}
                      </button>
                    ))}
                    <button
                      onClick={() => navigate('/trajectory')}
                      className="text-xs bg-surface-light border border-border hover:border-blue-500/50 text-muted hover:text-white px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
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
