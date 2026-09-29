"""
network/ffmpeg_frame_source.py

SIH26127 real CP PLUS camera integration — RTSPS bridge.

Real hardware verification (reported by the operator, not simulated) found
that this project's actual CP PLUS camera:

    rtsps://<user>:<pass>@192.168.137.2:554/video/live?channel=1&subtype=0

connects and streams real HEVC/H.265 video (2560x1440 @ 25 fps — confirmed
with `ffmpeg -tls_verify 0 -rtsp_transport tcp -i "<url>" -t 10 -f null -`,
250 frames received in 10 real seconds), but plain `rtsp://` on both
`/video/live` and `/cam/realmonitor` was REJECTED outright by the camera
(connection reset, ffmpeg error -10054/WSAECONNRESET) on both paths. For
this camera, RTSPS is not optional, and its self-signed certificate means
TLS verification must be explicitly disabled to connect at all.

Why this needs its own bridge instead of going through OpenCV/ultralytics
directly: `vehicle_detector.track_video(video_path)` hands `video_path`
straight to `ultralytics.YOLO(...).track(source=video_path, stream=True)`,
which opens it via `cv2.VideoCapture()` (OpenCV's FFmpeg backend). That
backend has no per-call way to pass `-tls_verify 0` / `-rtsp_transport
tcp` — the only bridge it exposes for arbitrary libavformat options is the
`OPENCV_FFMPEG_CAPTURE_OPTIONS` environment variable, which is GLOBAL to
the whole process. This app already runs one live-stream/webcam session
per background thread (see backend/app/api/v1/observations.py), so a
process-global env var would race the moment two camera streams with
different transport/TLS needs run concurrently — silently applying one
camera's settings to another's connection attempt. Rather than depend on
that, this module runs the real `ffmpeg` binary as a subprocess — the
exact command verified above — per stream, and decodes its raw video
output directly, so each camera's connection is fully independent and
uses exactly the flags proven to work against the real hardware.

The frames this module yields are fed into the EXISTING detection/tracking
pipeline via `VehicleDetector.track_frame()` (see
`network.rtsp_camera.open_camera_frames`) — the same "capture your own
frame, call track_frame(frame) per frame" pattern already used for the
browser-webcam live session, not a new detection code path.

What this module has NOT been verified against, honestly: there was no
real network path to the physical camera from the environment this was
implemented and tested in (see docs/LIVE_STREAMING.md's "What this is
honestly, and isn't yet" section for the exact boundary of what was and
wasn't run against real hardware). Every function here is covered by
tests/test_rtsp_camera_integration.py with `subprocess.Popen`/`.run` mocked
out — the *commands* this module builds match the operator's own verified
ffmpeg invocation, but this module's own subprocess plumbing around that
command has not itself been exercised against the real camera.
"""
import logging
import queue
import shutil
import subprocess
import threading
from typing import Iterator, Optional, Tuple
from urllib.parse import urlsplit

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_TRANSPORT = "tcp"
DEFAULT_PROBE_TIMEOUT_SECONDS = 10
DEFAULT_ROTATION = 0
VALID_ROTATIONS = (0, 90, 180, 270)
# SIH26127 fix (2026-09-14, "video upload/live stream hangs forever" bug):
# max seconds of total silence on ffmpeg's raw-video pipe before this is
# treated as a stalled/dropped connection rather than "still working".
# Real, observed failure mode: the operator's physical CP PLUS camera
# stays connected long enough to pass the initial ffprobe (see
# probe_stream_dimensions below) but then its stream stalls mid-session
# (the camera runs off a charging adapter, not verified stable long-term
# power/network) - ffmpeg's stdout pipe then simply stops producing bytes
# without ffmpeg itself exiting. Reading that pipe (`stream.read()`, no
# timeout parameter exists on it) then blocks forever, which hung this
# whole generator - and therefore the live-stream WebSocket session in
# backend/app/api/v1/observations.py - silently: no "frame", no "error",
# no "done", just the client stuck at PROCESSING indefinitely. That
# handler already correctly turns any exception from this generator into
# a real {"type":"error"} message the frontend shows as "Stream failed" -
# it just never got the chance to, because nothing here ever raised.
# 15s is generous for a camera confirmed doing ~25fps in real testing
# (over 300 missed frames) - long enough that a normal decode hiccup never
# trips it, short enough that a demo doesn't sit frozen for minutes.
DEFAULT_STALL_TIMEOUT_SECONDS = 15.0


def _rotate_frame(frame: np.ndarray, rotation: int) -> np.ndarray:
    """Rotates a decoded BGR frame clockwise by `rotation` degrees (one of
    VALID_ROTATIONS). SIH26127 real CP PLUS camera integration: found,
    honestly, while first watching real frames from the physical camera
    (not something anticipated in advance) - some camera mounts hand back
    an upside-down or sideways image, and there is no way to fix that on
    the camera side without physically remounting it. `rotation=0` (the
    default) is a true no-op - this function is never called in that case
    (see iter_frames_via_ffmpeg below) - so a camera with no
    TRACKX_RTSP_<CAM_ID>_ROTATION set behaves exactly as before this
    existed. `np.rot90`'s own convention is counter-clockwise, hence the
    negated `k` below to get a clockwise rotation matching how a person
    would describe "this camera is mounted 90 degrees clockwise"."""
    if rotation == 0:
        return frame
    k = {90: -1, 180: 2, 270: 1}[rotation]
    # np.rot90 returns a view with non-contiguous strides; downstream code
    # (cv2.imencode, YOLO's own preprocessing) expects a normal contiguous
    # array, so copy rather than pass the view through.
    return np.ascontiguousarray(np.rot90(frame, k=k))


class FFmpegNotAvailable(Exception):
    """Raised when the `ffmpeg` (or `ffprobe`) binary isn't on PATH."""


class FFmpegStreamError(Exception):
    """Raised when ffmpeg/ffprobe fails to open/describe the stream. Never
    carries the source URL's credentials - see _redact() below."""


def _require_binary(name):
    path = shutil.which(name)
    if not path:
        raise FFmpegNotAvailable(
            f"'{name}' was not found on PATH - required to read an rtsps:// "
            f"camera source (see network/ffmpeg_frame_source.py)."
        )
    return path


def _redact(url):
    """Local, dependency-free redaction (avoids importing
    network.rtsp_camera at module scope, which would create a circular
    import - that module imports this one). Deliberately conservative,
    same rule as network.rtsp_camera.redact_rtsp_url: mask past the scheme
    whenever a userinfo segment is present, never risk leaking a
    credential through an edge case in the exact match."""
    if not url:
        return url
    scheme_sep = url.find("://")
    if scheme_sep == -1 or "@" not in url:
        return url
    last_at = url.rfind("@")
    return url[:scheme_sep + 3] + "****@" + url[last_at + 1:]


def _is_rtsps(url):
    return urlsplit(url).scheme.lower() == "rtsps"


def _transport_and_tls_args(url, transport, tls_verify):
    """`-rtsp_transport` applies to every rtsp(s):// source. `-tls_verify`
    is only meaningful (and only ever passed) for an rtsps:// source - the
    real camera this was verified against only required it there, and
    omitting it entirely for a plain rtsp:// source avoids any risk of an
    ffmpeg build/version rejecting an option a non-TLS connection has no
    use for."""
    args = ["-rtsp_transport", transport]
    if _is_rtsps(url):
        args += ["-tls_verify", "0" if not tls_verify else "1"]
    return args


def probe_stream_dimensions(url, transport=DEFAULT_TRANSPORT, tls_verify=True,
                             timeout_seconds=DEFAULT_PROBE_TIMEOUT_SECONDS) -> Tuple[int, int]:
    """
    Uses ffprobe to discover the real decoded frame width/height - needed
    to know the byte size of each raw frame ffmpeg will emit on its raw
    video pipe (see iter_frames_via_ffmpeg) - using the exact same
    connection flags (transport/tls_verify) the actual stream will use.
    Never touches OpenCV; this is the real `ffprobe` binary, same as the
    real hardware verification used `ffmpeg` directly.
    """
    ffprobe = _require_binary("ffprobe")
    cmd = [
        ffprobe, "-v", "error",
        *_transport_and_tls_args(url, transport, tls_verify),
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        raise FFmpegStreamError(f"ffprobe timed out after {timeout_seconds}s connecting to {_redact(url)}")
    if proc.returncode != 0:
        stderr_tail = _redact(proc.stderr.decode("utf-8", "replace"))[-500:]
        raise FFmpegStreamError(f"ffprobe failed (exit {proc.returncode}) for {_redact(url)}: {stderr_tail}")
    out = proc.stdout.decode("utf-8", "replace").strip()
    try:
        width_str, height_str = out.split("x")
        width, height = int(width_str), int(height_str)
    except (ValueError, AttributeError):
        raise FFmpegStreamError(f"ffprobe returned unexpected output for {_redact(url)}: {out!r}")
    if width <= 0 or height <= 0:
        raise FFmpegStreamError(f"ffprobe reported invalid dimensions {width}x{height} for {_redact(url)}")
    return width, height


def iter_frames_via_ffmpeg(url, transport=DEFAULT_TRANSPORT, tls_verify=True,
                            probe_timeout_seconds=DEFAULT_PROBE_TIMEOUT_SECONDS,
                            rotation: int = DEFAULT_ROTATION,
                            stall_timeout_seconds: float = DEFAULT_STALL_TIMEOUT_SECONDS) -> Iterator[np.ndarray]:
    """
    Yields real, freshly-decoded BGR frames (numpy arrays, shape
    (height, width, 3) — OpenCV's own convention, so callers can feed them
    straight into VehicleDetector.track_frame()) from a live rtsp(s)://
    source, by running `ffmpeg` as a subprocess exactly as verified against
    the real CP PLUS camera and reading its raw video output.

    `rotation` (one of VALID_ROTATIONS - see network.rtsp_camera's
    TRACKX_RTSP_<CAM_ID>_ROTATION) corrects a camera that's physically
    mounted sideways or upside-down - applied to every decoded frame
    before it's handed to detection, so YOLO/OCR see an upright frame and
    every downstream consumer (the live-stream WebSocket's JPEG, the
    saved observation) is rotated consistently, not just the display.
    `rotation=0` (the default) never touches a frame - a camera with
    nothing configured behaves exactly as before this existed.

    This is a generator: the ffmpeg subprocess starts on first iteration
    and is torn down (process + pipes) in the `finally` block below,
    including when a caller `break`s out of the loop early (Python sends
    GeneratorExit into an abandoned generator, which lands right where the
    generator was paused at its last `yield`, inside the `try` below).
    """
    if rotation not in VALID_ROTATIONS:
        raise ValueError(f"rotation={rotation!r} must be one of {VALID_ROTATIONS}")
    ffmpeg = _require_binary("ffmpeg")
    width, height = probe_stream_dimensions(
        url, transport=transport, tls_verify=tls_verify, timeout_seconds=probe_timeout_seconds,
    )
    frame_bytes = width * height * 3

    # SIH26127 real-camera fps fix (2026-09-15): live-testing this session
    # against the real CP PLUS camera found ~7-8fps end-to-end regardless of
    # which stream subtype was requested (0, 1, and 2 all landed in the same
    # 3-8.6fps range) while Windows Task Manager showed the GPU's 3D engine
    # busy (YOLO inference) but its dedicated "Video Decode" engine at a flat
    # 0% - i.e. ffmpeg was decoding this camera's real 2560x1440 HEVC/H.265
    # stream entirely in software (CPU), never touching the GPU's NVDEC
    # hardware decoder that was sitting completely idle. Confirmed this
    # operator's actual ffmpeg build supports it (`ffmpeg -hwaccels` lists
    # `cuda` on this machine) before adding this flag - an ffmpeg build
    # without CUDA/NVDEC support would otherwise fail every connection.
    # `-hwaccel cuda` (no explicit `-c:v ..._cuvid` / `-hwaccel_output_format`)
    # lets ffmpeg auto-select the matching NVDEC decoder for whatever codec
    # the stream actually uses and auto-downloads decoded frames back to
    # system memory for the `-pix_fmt bgr24` rawvideo output below - the
    # simplest, least invasive way to offload decode to idle hardware
    # without changing this function's raw-BGR24-frames-out contract that
    # every caller (VehicleDetector.track_frame, the live-stream WebSocket)
    # already depends on. If this ever regresses on different hardware/
    # camera combination, reverting is exactly removing these two list
    # entries - no other logic here depends on hardware decode succeeding.
    cmd = [
        ffmpeg, "-loglevel", "error", "-nostdin",
        *_transport_and_tls_args(url, transport, tls_verify),
        "-hwaccel", "cuda",
        "-i", url,
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-an", "-sn",
        "-",
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=frame_bytes)

    # frame_queue carries each read's result across from the reader thread:
    # a full frame's bytes, or None once _read_exact reports EOF/short read
    # (the source really ended). maxsize=2 gives the reader a little room
    # to run ahead without letting it buffer unboundedly if the consumer
    # below is slow.
    frame_queue: "queue.Queue[Optional[bytes]]" = queue.Queue(maxsize=2)

    def _reader():
        while True:
            raw = _read_exact(proc.stdout, frame_bytes)
            frame_queue.put(raw)
            if raw is None:
                return

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    try:
        while True:
            try:
                raw = frame_queue.get(timeout=stall_timeout_seconds)
            except queue.Empty:
                # See DEFAULT_STALL_TIMEOUT_SECONDS above - no data at all
                # for stall_timeout_seconds despite a successful initial
                # probe. The reader thread is left blocked on the now-dead
                # pipe (daemon=True so it never blocks process/interpreter
                # exit); terminating proc below closes that pipe out from
                # under it.
                stderr_tail = _redact(proc.stderr.read(2000).decode("utf-8", "replace")) if proc.stderr else ""
                raise FFmpegStreamError(
                    f"No video data received from {_redact(url)} for "
                    f"{stall_timeout_seconds:.0f}s - the camera connection "
                    f"stalled or dropped mid-stream (it answered the initial "
                    f"connection probe, so this is not a configuration "
                    f"problem, just a live network/camera drop). "
                    f"{stderr_tail.strip()}"
                )
            if raw is None:
                exit_code = proc.poll()
                if exit_code not in (None, 0):
                    stderr_tail = _redact(proc.stderr.read(2000).decode("utf-8", "replace")) if proc.stderr else ""
                    logger.warning("ffmpeg RTSP(S) stream for %s ended (exit %r): %s", _redact(url), exit_code, stderr_tail.strip())
                break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
            yield _rotate_frame(frame, rotation) if rotation else frame
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()


def _read_exact(stream, n) -> Optional[bytes]:
    """Reads exactly n bytes from a subprocess pipe, or None on EOF/short
    read (the stream ended). Raw video framing has no delimiters, so a
    short read can only mean the source stopped - never 'try again'."""
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)
