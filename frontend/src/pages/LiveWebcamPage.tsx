// frontend/src/pages/LiveWebcamPage.tsx
//
// SIH26127 "Live Webcam + Phone Number-Plate Demo": the laptop's OWN
// webcam is a real, live video source feeding the exact same AI pipeline
// (YOLO vehicle detection -> ByteTrack -> plate detection -> adaptive
// preprocessing -> PaddleOCR -> temporal multi-frame fusion -> plate
// state) that the CCTV-upload flow (VideoDemoPage) uses - see
// backend/app/api/v1/observations.py's webcam_stream() and live_webcam.py.
//
// Every value on this page is real:
//   - the video feed is the browser's actual camera stream (getUserMedia),
//     never a prerecorded clip or a static image.
//   - every detection/box/plate/confidence/state comes from a real
//     "result" message the backend sent after actually running inference
//     on a real captured frame - nothing here is drawn from a template or
//     a hardcoded example.
//   - Camera FPS (how often THIS BROWSER captures a frame) and Processing
//     FPS (how often the backend actually finishes analyzing one) are
//     measured independently and shown as two separate numbers - never
//     averaged together or presented as one "FPS".
//   - no aggregate "accuracy" number is shown anywhere on this page. The
//     only validated benchmark TrackX has is described in
//     docs/AWIROS_VERIFICATION_AND_TRAINING_DECISION_2026-09-09.md (48.6%
//     exact-match on 37 real plates) - that is an offline validation
//     figure, not something a live webcam session can measure about
//     itself, and is not fabricated or implied here.

import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Camera as CameraIcon,
  Play,
  Square,
  AlertTriangle,
  Info,
  Gauge,
  Car,
  ScanLine,
} from 'lucide-react'

type PermissionState = 'idle' | 'requesting' | 'granted' | 'error'
type SocketState = 'idle' | 'connecting' | 'ready' | 'closed' | 'error'

interface LiveVehicle {
  track_id: string
  bbox: [number, number, number, number]
  vehicle_type: string
  vehicle_confidence: number
  plate_bbox: [number, number, number, number] | null
  plate_detector_confidence: number | null
  plate_text: string | null
  plate_status: string
  plate_state: 'UNKNOWN' | 'LOW_CONFIDENCE' | 'TENTATIVE' | 'VERIFIED'
  ocr_confidence: number | null
  temporal_support: number
  final_fusion_score: number | null
  plate_quality_score: number | null
  blur_score: number | null
  preprocessing_mode: string | null
  first_seen_frame: number | null
}

// Capture at a bounded resolution before JPEG-encoding - the same
// bandwidth-not-accuracy reasoning the existing live-stream endpoint uses
// for its own outgoing frames (_LIVE_STREAM_MAX_SIDE = 640 in
// observations.py) - detection quality is unaffected, this only bounds
// how large the JPEG sent per frame is.
const CAPTURE_MAX_SIDE = 640
const CAPTURE_INTERVAL_MS = 500 // target ~2 real camera-capture attempts/sec
const CAM_ID = 'CAM_WEBCAM_01'
const FPS_WINDOW = 8 // rolling window size for measured FPS figures
// SIH26127 "Final Demo Hardening" audit (2026-09-10) - real gap found while
// testing this page end-to-end: video.videoWidth/videoHeight can report a
// real but degenerate size (e.g. a webcam driver falling back to a tiny
// placeholder frame instead of a real signal) without ever being exactly
// 0 - the only case the capture loop used to guard against. A frame that
// small can never contain a real vehicle no matter how good the model is,
// so this is reported to the operator instead of silently producing
// "0 vehicles" forever with no visible reason.
const MIN_VALID_CAPTURE_SIDE = 32

function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${path}`
}

function plateStateBadgeClass(state: string) {
  switch (state) {
    case 'VERIFIED':
      return 'bg-clear-500/15 text-clear-400'
    case 'TENTATIVE':
      return 'bg-caution-500/15 text-caution-400'
    case 'LOW_CONFIDENCE':
      return 'bg-caution-500/15 text-caution-400'
    default:
      return 'bg-surface text-muted'
  }
}

const LiveWebcamPage: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const captureCanvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const captureTimerRef = useRef<number | null>(null)
  const awaitingResultRef = useRef(false)
  const captureTimestampsRef = useRef<number[]>([])
  const processingLatenciesRef = useRef<number[]>([])
  const uniqueTrackIdsRef = useRef<Set<string>>(new Set())

  const [permissionState, setPermissionState] = useState<PermissionState>('idle')
  const [permissionError, setPermissionError] = useState<string | null>(null)
  const [socketState, setSocketState] = useState<SocketState>('idle')
  const [socketError, setSocketError] = useState<string | null>(null)
  const [capabilities, setCapabilities] = useState<{
    plate_detector_available: boolean
    plate_detector_reason: string | null
    ocr_available: boolean
    ocr_reason: string | null
  } | null>(null)
  // SIH26127 "Final Demo Hardening" audit (2026-09-10): frame_error
  // messages used to be silently swallowed here - a real per-frame
  // processing failure (e.g. every frame erroring out) looked EXACTLY
  // like "CAMERA CONNECTED" + "0 vehicles" forever, with zero visible
  // diagnostic for the operator. Now tracked and shown.
  const [frameErrorCount, setFrameErrorCount] = useState(0)
  const [lastFrameError, setLastFrameError] = useState<string | null>(null)
  const [degenerateFrameWarning, setDegenerateFrameWarning] = useState<string | null>(null)
  const [vehicles, setVehicles] = useState<LiveVehicle[]>([])
  const [framesSent, setFramesSent] = useState(0)
  const [cameraFps, setCameraFps] = useState(0)
  const [processingFps, setProcessingFps] = useState(0)
  const [uniqueTracks, setUniqueTracks] = useState(0)
  const [captureSize, setCaptureSize] = useState<{ w: number; h: number } | null>(null)

  const isLive = permissionState === 'granted' && socketState === 'ready'

  const drawOverlay = useCallback((vs: LiveVehicle[]) => {
    const canvas = overlayRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    for (const v of vs) {
      const [x1, y1, x2, y2] = v.bbox
      ctx.strokeStyle = '#f3b53e'
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
      const label = `#${v.track_id} ${v.vehicle_type}`
      ctx.font = '14px "JetBrains Mono", monospace'
      const labelW = ctx.measureText(label).width + 8
      ctx.fillStyle = 'rgba(18,21,26,0.85)'
      ctx.fillRect(x1, Math.max(0, y1 - 20), labelW, 20)
      ctx.fillStyle = '#f3b53e'
      ctx.fillText(label, x1 + 4, Math.max(14, y1 - 6))

      if (v.plate_bbox) {
        const [px1, py1, px2, py2] = v.plate_bbox
        ctx.strokeStyle = v.plate_state === 'VERIFIED' ? '#5fb87a' : '#e8ab3d'
        ctx.lineWidth = 2
        ctx.strokeRect(px1, py1, px2 - px1, py2 - py1)
        const plateLabel = v.plate_text
          ? `${v.plate_text} (${v.plate_state})`
          : v.plate_status === 'detected_not_read'
          ? 'PLATE UNKNOWN'
          : v.plate_state
        ctx.font = '13px "JetBrains Mono", monospace'
        const plW = ctx.measureText(plateLabel).width + 8
        ctx.fillStyle = 'rgba(18,21,26,0.85)'
        ctx.fillRect(px1, py2 + 2, plW, 18)
        ctx.fillStyle = v.plate_state === 'VERIFIED' ? '#5fb87a' : '#e8ab3d'
        ctx.fillText(plateLabel, px1 + 4, py2 + 15)
      }
    }
  }, [])

  const stopEverything = useCallback(() => {
    if (captureTimerRef.current !== null) {
      window.clearInterval(captureTimerRef.current)
      captureTimerRef.current = null
    }
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: 'stop' }))
      } catch {
        // ignore - closing anyway
      }
    }
    if (ws) {
      ws.close()
      wsRef.current = null
    }
    const stream = streamRef.current
    if (stream) {
      stream.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) videoRef.current.srcObject = null
    awaitingResultRef.current = false
    captureTimestampsRef.current = []
    processingLatenciesRef.current = []
    setSocketState('idle')
    setVehicles([])
    setCameraFps(0)
    setProcessingFps(0)
    setFrameErrorCount(0)
    setLastFrameError(null)
    setDegenerateFrameWarning(null)
  }, [])

  // Release the camera / close the socket if the operator navigates away
  // without clicking Stop - a live camera must never keep running
  // invisibly in the background.
  useEffect(() => stopEverything, [stopEverything])

  const captureAndSendFrame = useCallback(() => {
    const now = performance.now()
    captureTimestampsRef.current.push(now)
    captureTimestampsRef.current = captureTimestampsRef.current.slice(-FPS_WINDOW)
    if (captureTimestampsRef.current.length >= 2) {
      const span = (captureTimestampsRef.current[captureTimestampsRef.current.length - 1] - captureTimestampsRef.current[0]) / 1000
      const fps = span > 0 ? (captureTimestampsRef.current.length - 1) / span : 0
      setCameraFps(Math.round(fps * 10) / 10)
    }

    const video = videoRef.current
    const canvas = captureCanvasRef.current
    const ws = wsRef.current
    if (!video || !canvas || !ws || ws.readyState !== WebSocket.OPEN) return
    // Backpressure: never queue a second frame while one is still being
    // processed - "processing FPS" must reflect real completed work, not
    // an ever-growing backlog of unprocessed frames.
    if (awaitingResultRef.current) return
    if (video.videoWidth === 0 || video.videoHeight === 0) return
    if (video.videoWidth < MIN_VALID_CAPTURE_SIDE || video.videoHeight < MIN_VALID_CAPTURE_SIDE) {
      setDegenerateFrameWarning(
        `Camera is reporting an abnormally small video size (${video.videoWidth}x${video.videoHeight}px) - ` +
        `too small for any real vehicle to be detected. This usually means the camera driver isn't producing ` +
        `a real video signal (try a different camera/browser, or check it isn't in use by another app).`
      )
      return
    }
    // Unconditional clear (not gated on reading current state, since this
    // callback is memoized with an empty dep array) - setting the same
    // `null` value again is a no-op re-render, so this is cheap and always
    // correct once a valid frame is captured.
    setDegenerateFrameWarning(null)

    const scale = Math.min(1, CAPTURE_MAX_SIDE / Math.max(video.videoWidth, video.videoHeight))
    const w = Math.round(video.videoWidth * scale)
    const h = Math.round(video.videoHeight * scale)
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
      setCaptureSize({ w, h })
      const overlay = overlayRef.current
      if (overlay) {
        overlay.width = w
        overlay.height = h
      }
    }
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(video, 0, 0, w, h)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
    const jpegB64 = dataUrl.split(',')[1]
    if (!jpegB64) return

    awaitingResultRef.current = true
    const sentAt = performance.now()
    ws.send(JSON.stringify({ type: 'frame', jpeg_b64: jpegB64, client_sent_at: sentAt }))
    setFramesSent((n) => n + 1)
    // stash sentAt on the socket instance for latency measurement on reply
    ;(ws as any)._lastSentAt = sentAt
  }, [])

  const startSession = useCallback(async () => {
    setPermissionError(null)
    setSocketError(null)

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setPermissionState('error')
      setPermissionError('This browser does not support camera access (navigator.mediaDevices.getUserMedia is unavailable). Try a recent Chrome, Edge, or Firefox.')
      return
    }

    setPermissionState('requesting')
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      })
    } catch (err: any) {
      setPermissionState('error')
      const name = err?.name || ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setPermissionError('Camera permission was denied. Allow camera access for this page in your browser settings and try again.')
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        setPermissionError('No camera was found on this device.')
      } else if (name === 'NotReadableError' || name === 'TrackStartError') {
        setPermissionError('The camera could not be started - it may already be in use by another application (Zoom, another browser tab, etc.). Close it and try again.')
      } else {
        setPermissionError(`Could not access the camera: ${err?.message || 'unknown error'}.`)
      }
      return
    }

    streamRef.current = stream
    setPermissionState('granted')
    if (videoRef.current) {
      videoRef.current.srcObject = stream
      try {
        await videoRef.current.play()
      } catch {
        // Autoplay can be blocked in some browsers until user interaction -
        // the Start button click itself is the interaction, so this should
        // succeed; if not, the <video> element still shows once the
        // browser allows it, this is not a fatal error.
      }
    }

    setSocketState('connecting')
    const ws = new WebSocket(wsUrl(`/api/v1/observations/webcam-stream/${CAM_ID}`))
    wsRef.current = ws

    ws.onopen = () => {
      // Wait for the server's "ready" message before capturing - it also
      // tells us whether the plate detector/OCR are actually available in
      // this deployment, so the UI never implies capability that isn't
      // really there.
    }

    ws.onmessage = (event) => {
      let msg: any
      try {
        msg = JSON.parse(event.data)
      } catch {
        return
      }

      if (msg.type === 'ready') {
        setCapabilities({
          plate_detector_available: !!msg.plate_detector_available,
          plate_detector_reason: msg.plate_detector_reason || null,
          ocr_available: !!msg.ocr_available,
          ocr_reason: msg.ocr_reason || null,
        })
        setFrameErrorCount(0)
        setLastFrameError(null)
        setSocketState('ready')
        captureTimerRef.current = window.setInterval(captureAndSendFrame, CAPTURE_INTERVAL_MS)
        return
      }

      if (msg.type === 'result') {
        awaitingResultRef.current = false
        const sentAt = (ws as any)._lastSentAt
        if (typeof sentAt === 'number') {
          const latency = performance.now() - sentAt
          processingLatenciesRef.current = [...processingLatenciesRef.current, latency].slice(-FPS_WINDOW)
          const avgMs = processingLatenciesRef.current.reduce((a, b) => a + b, 0) / processingLatenciesRef.current.length
          setProcessingFps(avgMs > 0 ? Math.round((1000 / avgMs) * 10) / 10 : 0)
        }
        const vs: LiveVehicle[] = msg.vehicles || []
        vs.forEach((v) => uniqueTrackIdsRef.current.add(v.track_id))
        setUniqueTracks(uniqueTrackIdsRef.current.size)
        setVehicles(vs)
        drawOverlay(vs)
        return
      }

      if (msg.type === 'frame_error') {
        awaitingResultRef.current = false
        setFrameErrorCount((n) => n + 1)
        setLastFrameError(msg.detail || 'Unknown frame error.')
        return
      }

      if (msg.type === 'error') {
        setSocketError(msg.detail || 'The live session ended unexpectedly.')
        setSocketState('error')
        stopEverything()
      }
    }

    ws.onerror = () => {
      setSocketError('Could not connect to the live processing backend.')
      setSocketState('error')
    }

    ws.onclose = () => {
      setSocketState((prev) => (prev === 'error' ? prev : 'closed'))
      if (captureTimerRef.current !== null) {
        window.clearInterval(captureTimerRef.current)
        captureTimerRef.current = null
      }
    }
  }, [captureAndSendFrame, drawOverlay, stopEverything])

  const verifiedCount = vehicles.filter((v) => v.plate_state === 'VERIFIED').length
  const tentativeCount = vehicles.filter((v) => v.plate_state === 'TENTATIVE').length
  const platesDetectedCount = vehicles.filter((v) => v.plate_bbox !== null).length

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <CameraIcon className="text-signal-400" />
          Live Webcam Demo
        </h1>
        <p className="text-sm text-muted">
          Hold a vehicle (photo, video, or the real thing) up to this laptop's webcam. Every frame below
          is captured live from the browser's camera and run through the real detection pipeline -
          nothing here is prerecorded.
        </p>
      </div>

      <div className="card p-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <span className="flex items-center gap-1.5">
          <span className={`live-dot ${isLive ? 'is-live' : ''}`} />
          <span className="font-semibold text-white">
            {isLive ? 'CAMERA CONNECTED' : permissionState === 'requesting' || socketState === 'connecting' ? 'CONNECTING…' : 'NOT CONNECTED'}
          </span>
        </span>
        <span className="text-muted">Source: Laptop Webcam</span>
        <span className="text-muted">Mode: {isLive ? 'LIVE' : 'IDLE'}</span>
        <span className="text-muted">Camera: {CAM_ID}</span>
        {capabilities && !capabilities.plate_detector_available && (
          <span className="text-caution-400 flex items-center gap-1" title={capabilities.plate_detector_reason || undefined}>
            <Info size={12} /> Plate detector unavailable{capabilities.plate_detector_reason ? `: ${capabilities.plate_detector_reason}` : ''}
          </span>
        )}
        {capabilities && capabilities.plate_detector_available && !capabilities.ocr_available && (
          <span className="text-caution-400 flex items-center gap-1" title={capabilities.ocr_reason || undefined}>
            <Info size={12} /> OCR unavailable{capabilities.ocr_reason ? `: ${capabilities.ocr_reason}` : ' in this deployment'}
          </span>
        )}
        {frameErrorCount > 0 && (
          <span className="text-critical-400 flex items-center gap-1" title={lastFrameError || undefined}>
            <AlertTriangle size={12} /> {frameErrorCount} frame error{frameErrorCount === 1 ? '' : 's'}
            {lastFrameError ? ` - ${lastFrameError}` : ''}
          </span>
        )}
      </div>

      {degenerateFrameWarning && (
        <div className="card p-3 border-critical-500/40 bg-critical-500/10 flex items-start gap-2 text-sm text-critical-400">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>{degenerateFrameWarning}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="card p-3">
            <div className="relative w-full bg-black rounded overflow-hidden" style={{ aspectRatio: '16/9' }}>
              <video
                ref={videoRef}
                muted
                playsInline
                className="absolute inset-0 w-full h-full object-contain"
              />
              <canvas
                ref={overlayRef}
                className="absolute inset-0 w-full h-full object-contain pointer-events-none"
              />
              <canvas ref={captureCanvasRef} className="hidden" />

              {!isLive && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/60">
                  {permissionState === 'error' && permissionError ? (
                    <div className="max-w-sm text-center px-4">
                      <AlertTriangle className="mx-auto mb-2 text-critical-400" size={28} />
                      <p className="text-sm text-critical-400">{permissionError}</p>
                    </div>
                  ) : socketState === 'error' && socketError ? (
                    <div className="max-w-sm text-center px-4">
                      <AlertTriangle className="mx-auto mb-2 text-critical-400" size={28} />
                      <p className="text-sm text-critical-400">{socketError}</p>
                    </div>
                  ) : (
                    <div className="text-center">
                      <CameraIcon className="mx-auto mb-2 text-muted opacity-50" size={32} />
                      <p className="text-sm text-muted">Camera feed will appear here</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="mt-3 flex items-center gap-2">
              {!isLive ? (
                <button
                  onClick={startSession}
                  disabled={permissionState === 'requesting' || socketState === 'connecting'}
                  className="bg-signal-600 hover:bg-signal-500 disabled:bg-surface-light disabled:text-muted text-white px-4 py-2 rounded text-sm font-semibold flex items-center gap-2"
                >
                  <Play size={15} /> Start Webcam
                </button>
              ) : (
                <button
                  onClick={stopEverything}
                  className="bg-critical-600/20 hover:bg-critical-600/30 text-critical-400 px-4 py-2 rounded text-sm font-semibold flex items-center gap-2 border border-critical-500/30"
                >
                  <Square size={15} /> Stop
                </button>
              )}
              {captureSize && (
                <span className="text-[11px] text-muted">Capture resolution: {captureSize.w}×{captureSize.h}</span>
              )}
            </div>
          </div>

          <div className="card p-4">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-1.5">
              <Gauge size={15} className="text-signal-400" /> Live Processing
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <p className="text-muted uppercase tracking-wide text-[10px]">Camera FPS</p>
                <p className="text-white font-bold text-lg font-data">{cameraFps || '—'}</p>
                <p className="text-muted text-[10px]">frames the browser captures/sec</p>
              </div>
              <div>
                <p className="text-muted uppercase tracking-wide text-[10px]">Processing FPS</p>
                <p className="text-white font-bold text-lg font-data">{processingFps || '—'}</p>
                <p className="text-muted text-[10px]">frames the AI pipeline finishes/sec</p>
              </div>
              <div>
                <p className="text-muted uppercase tracking-wide text-[10px]">Frames Sent</p>
                <p className="text-white font-bold text-lg font-data">{framesSent}</p>
              </div>
              <div>
                <p className="text-muted uppercase tracking-wide text-[10px]">Tracks Seen</p>
                <p className="text-white font-bold text-lg font-data">{uniqueTracks}</p>
              </div>
              <div>
                <p className="text-muted uppercase tracking-wide text-[10px]">Vehicles Now</p>
                <p className="text-white font-bold text-lg font-data">{vehicles.length}</p>
              </div>
              <div>
                <p className="text-muted uppercase tracking-wide text-[10px]">Plates Now</p>
                <p className="text-white font-bold text-lg font-data">{platesDetectedCount}</p>
              </div>
              <div>
                <p className="text-muted uppercase tracking-wide text-[10px]">Verified</p>
                <p className="text-clear-400 font-bold text-lg font-data">{verifiedCount}</p>
              </div>
              <div>
                <p className="text-muted uppercase tracking-wide text-[10px]">Tentative</p>
                <p className="text-caution-400 font-bold text-lg font-data">{tentativeCount}</p>
              </div>
            </div>
            <p className="mt-3 text-[11px] text-muted flex items-start gap-1.5">
              <Info size={12} className="mt-0.5 shrink-0" />
              Camera FPS (how often the browser captures a frame) and Processing FPS (1 ÷ the real
              measured per-frame pipeline latency) are independent and can differ in either direction:
              when the pipeline has spare capacity, Processing FPS can read higher than Camera FPS
              (a frame is only ever sent once the previous one finished, so no backlog ever queues) -
              when the pipeline is the bottleneck, Camera FPS stays capped by how fast Processing FPS
              can actually clear frames. Neither number is assumed from camera hardware specs.
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                <Car size={15} className="text-signal-400" /> Live Detections
              </h3>
              <span className="text-xs text-muted">{vehicles.length} now visible</span>
            </div>
            {vehicles.length === 0 ? (
              <p className="text-xs text-muted text-center py-8">
                {isLive ? 'No vehicle currently in view.' : 'Start the webcam to see live detections.'}
              </p>
            ) : (
              <div className="space-y-2">
                {vehicles.map((v) => (
                  <div key={v.track_id} className="bg-surface-light border border-border rounded p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-white capitalize">
                        Track #{v.track_id} · {v.vehicle_type}
                      </span>
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide ${plateStateBadgeClass(v.plate_state)}`}>
                        {v.plate_state}
                      </span>
                    </div>
                    <p className="text-sm font-mono mt-1 text-white">
                      {v.plate_text || (v.plate_status === 'no_plate_detected' ? 'No plate detected' : v.plate_status === 'detected_not_read' ? 'Plate detected, not read' : v.plate_status === 'unavailable' ? 'OCR unavailable' : '—')}
                    </p>
                    <div className="text-[10px] text-muted mt-1 flex flex-wrap gap-x-2">
                      {v.ocr_confidence !== null && <span>OCR {Math.round(v.ocr_confidence * 100)}%</span>}
                      <span>Temporal support: {v.temporal_support}</span>
                      {v.final_fusion_score !== null && <span>Fusion {v.final_fusion_score.toFixed(2)}</span>}
                      {v.plate_quality_score !== null && <span>Quality {v.plate_quality_score.toFixed(2)}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card p-4 text-xs text-muted space-y-2">
            <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
              <ScanLine size={15} className="text-signal-400" /> Demo Notes
            </h3>
            <p>
              Plate detection currently runs on the AREA INSIDE a detected vehicle's bounding box (the
              same architecture the recorded-CCTV pipeline uses) - a phone showing only a close-up plate
              with no vehicle body will not be detected. Show a complete vehicle (car/bus/truck/motorcycle)
              with the plate visible for a reliable read.
            </p>
            <p>
              Only one live webcam session can run at a time. If you see "a live webcam session is
              already running", stop the other tab/session first.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LiveWebcamPage
