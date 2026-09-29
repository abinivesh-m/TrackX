"""
network/rtsp_camera.py

SIH26127 — real CP PLUS (RTSP) camera integration.

docs/LIVE_STREAMING.md and demo/camera_simulator.py both say, honestly, that
there was no real CCTV/RTSP camera connected in this environment and that
RTSP was "explicitly called out as future work from Day 1". This module is
that future work: it lets a real IP camera - specifically a CP PLUS
DVR/NVR/IP camera, which (like most Indian CCTV brands sold under other
names) uses the same Dahua-derived RTSP URL scheme - stand in for a
camera's video source instead of a local `data/cameras/<CAM_ID>/videos/`
file.

Why this is safe to wire straight into the existing pipeline: pipeline.py's
run_video_to_db() already only ever passes `video_path` down to
vehicle_detector.track_video(), which hands it to
`ultralytics.YOLO(...).track(source=video_path, ..., stream=True)`.
Ultralytics itself detects an `rtsp://` (or `rtmp://`/`http(s)://`) source
string and switches to its live-stream dataloader - no separate code path
was needed in pipeline.py or detection/vehicle_detector.py for this to
work, and no changes were made there. The one place that DOES need to know
"is this a live camera or a file" is `backend/app/api/v1/observations.py`'s
`/live-stream/{camera_id}` WebSocket handler, which today always resolves
`video_path` via `demo.camera_simulator.get_camera_feed()`
(local-file-only); `resolve_camera_source()` below is the drop-in
replacement for that resolution step - real RTSP camera first, honest
fallback to the existing simulated-video behavior second.

What this module deliberately does NOT do:
  - It does not hardcode any camera's IP, port, username, or password -
    every real camera is configured entirely through environment
    variables (see `_env_for` below), same pattern as
    backend/app/core/config.py's Settings / DATABASE_URL. Nothing here
    changes if `.env` is empty; every existing camera just keeps using
    its simulated video exactly as before.
  - It does not claim a camera is reachable just because it's configured.
    `probe_rtsp_connectivity()` does a real (time-bounded) connection
    attempt and reports what actually happened - "configured" and
    "reachable" are two different, independently-reported facts, echoing
    this repo's established rule (SyntheticDataBadge / data_source
    tagging / CamerasPage.tsx's "no live RTSP feed, say so honestly"
    comment) that nothing gets labeled real unless it verifiably is.
  - It does not log or return a credential-bearing URL anywhere -
    `redact_rtsp_url()` is applied before anything derived from a
    configured URL is put in an API response, a WebSocket message, or a
    log line.

Env vars, per camera id (matching network.camera_network.CAMERAS' ids,
e.g. CAM_01):

    TRACKX_RTSP_<CAM_ID>_URL        full RTSP/RTSPS URL override (any
                                     brand/vendor path) - takes priority
                                     over every other var below for that
                                     camera. This is the recommended way
                                     to configure a camera whose path
                                     doesn't match either built-in
                                     PATH_STYLE (see below) - e.g. the
                                     project's own verified CP PLUS camera
                                     (see docs/LIVE_STREAMING.md), which
                                     uses rtsps:// on a path this module
                                     also happens to have a built-in style
                                     for (PATH_STYLE=video_live), but a
                                     full _URL override works too and
                                     needs no other var except _TLS_VERIFY.
    TRACKX_RTSP_<CAM_ID>_HOST       required if _URL is not set.
    TRACKX_RTSP_<CAM_ID>_PORT       default 554 (RTSP/RTSPS default).
    TRACKX_RTSP_<CAM_ID>_USERNAME   default "" (no auth).
    TRACKX_RTSP_<CAM_ID>_PASSWORD   default "".
    TRACKX_RTSP_<CAM_ID>_CHANNEL    default 1 (1-indexed, CP PLUS/Dahua
                                     convention).
    TRACKX_RTSP_<CAM_ID>_SUBTYPE    default 0 (0 = main/high-res stream,
                                     1 = sub/low-res stream - CP PLUS/
                                     Dahua convention; use 1 for a lower-
                                     bandwidth feed).
    TRACKX_RTSP_<CAM_ID>_SCHEME     "rtsp" (default) or "rtsps" - only
                                     used when building a URL from the
                                     component vars above (_HOST etc.);
                                     ignored when _URL is set (its scheme
                                     is whatever the URL itself says).
    TRACKX_RTSP_<CAM_ID>_PATH_STYLE "dahua" (default -
                                     /cam/realmonitor?channel=N&subtype=M,
                                     the path CP PLUS's DVR/NVR hardware
                                     normally exposes) or "video_live" -
                                     /video/live?channel=N&subtype=M, the
                                     path this project's own real CP PLUS
                                     camera was verified against (over
                                     RTSPS - plain RTSP was tried on BOTH
                                     paths against that camera and refused
                                     the connection outright). Also
                                     ignored when _URL is set.
    TRACKX_RTSP_<CAM_ID>_TRANSPORT  "tcp" (default) or "udp" - passed as
                                     ffmpeg/OpenCV's `-rtsp_transport`.
                                     Applies regardless of how the URL was
                                     obtained (component vars or _URL).
    TRACKX_RTSP_<CAM_ID>_TLS_VERIFY "1"/"true" (default - verify the
                                     server's TLS certificate) or
                                     "0"/"false" (skip verification).
                                     Only meaningful for an rtsps:// URL;
                                     ignored for plain rtsp://. Defaults
                                     to ON (secure) - a camera with a
                                     self-signed certificate (like this
                                     project's real CP PLUS camera) needs
                                     this explicitly set to "0", it is
                                     never disabled implicitly. Applies
                                     regardless of how the URL was
                                     obtained (component vars or _URL).
    TRACKX_RTSP_<CAM_ID>_ROTATION   "0" (default), "90", "180", or "270" -
                                     clockwise degrees to rotate every
                                     decoded frame before detection runs on
                                     it. Found necessary in practice: this
                                     project's own real CP PLUS camera
                                     handed back an upside-down/sideways
                                     frame the first time it was actually
                                     watched end-to-end (see
                                     docs/LIVE_STREAMING.md) - correcting
                                     that in software here, rather than
                                     remounting the physical camera, is
                                     what this is for. Only applied on the
                                     RTSPS ffmpeg-bridge path
                                     (network/ffmpeg_frame_source.py) - see
                                     the "Known limitation" note below.

A camera with none of these set is untouched: resolve_camera_source()
falls back to the exact same demo.camera_simulator lookup that
/live-stream/{camera_id} always used.

RTSPS (RTSP-over-TLS) sources are read through a real `ffmpeg` subprocess
(network/ffmpeg_frame_source.py), not OpenCV/ultralytics' own source
loader - see that module's docstring for why (short version: OpenCV's
FFmpeg backend has no reliable per-camera way to pass `-tls_verify 0` /
`-rtsp_transport tcp`). Plain rtsp:// sources are completely unaffected -
they still go straight through ultralytics' native stream loader exactly
as before this existed.

Known limitation, stated honestly: TRACKX_RTSP_<CAM_ID>_ROTATION is only
applied on the RTSPS ffmpeg-bridge path. A plain rtsp:// real camera goes
straight through ultralytics' own `YOLO(...).track(source=video_path,
stream=True)` dataloader (see open_camera_frames() below), which gives no
per-frame hook to rotate a frame before detection runs on it - correcting
that would mean either patching ultralytics' loader or building a second,
parallel frame-reading path for plain rtsp:// the way this module already
has for rtsps://, neither of which has been done here. In practice this
hasn't mattered yet, since the one real camera this project has actually
verified is rtsps:// (see docs/LIVE_STREAMING.md); a future plain-rtsp://
camera that's also mounted sideways would need this extended.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urlsplit

from network.camera_network import CAMERAS

# CP PLUS DVR/NVR/IP-camera RTSP paths. "dahua" is CP PLUS's own
# hardware/firmware OEM path (CP PLUS OEMs from Dahua, so it shares this
# exact path/query scheme) and remains the default for the component-var
# URL builder. "video_live" is the path this project's own real CP PLUS
# camera was verified against - see the module docstring. channel is
# 1-indexed; subtype 0 = main stream, 1 = sub stream, for both styles.
_PATH_STYLES = {
    "dahua": "/cam/realmonitor?channel={channel}&subtype={subtype}",
    "video_live": "/video/live?channel={channel}&subtype={subtype}",
}
DEFAULT_PATH_STYLE = "dahua"
DEFAULT_SCHEME = "rtsp"
DEFAULT_TRANSPORT = "tcp"
DEFAULT_TLS_VERIFY = True  # secure by default - must be disabled explicitly, see _env_for(..., "TLS_VERIFY")
DEFAULT_ROTATION = 0  # no rotation - see TRACKX_RTSP_<CAM_ID>_ROTATION in the module docstring
VALID_ROTATIONS = (0, 90, 180, 270)

DEFAULT_RTSP_PORT = 554
DEFAULT_CHANNEL = 1
DEFAULT_SUBTYPE = 0

_TRUE_STRINGS = {"1", "true", "yes", "on"}
_FALSE_STRINGS = {"0", "false", "no", "off"}

# How long a connectivity probe is allowed to block before being treated as
# "unreachable" - cv2.VideoCapture has no reliable native timeout on all
# platforms/backends, so this is enforced with a worker thread instead (see
# probe_rtsp_connectivity below). Kept short: this exists to answer "is the
# camera up right now", not to wait out a slow network.
DEFAULT_PROBE_TIMEOUT_SECONDS = 5.0


class RTSPConfigError(ValueError):
    """Raised when a camera has partial/invalid RTSP configuration (e.g. a
    host with no way to reach it, or an unknown camera id) - distinct from
    "not configured at all", which is not an error (see resolve_rtsp_url)."""


def _env_for(camera_id, suffix, default=None):
    return os.environ.get(f"TRACKX_RTSP_{camera_id}_{suffix}", default)


def _parse_bool_env(value, default, camera_id, var_name):
    if value is None or value == "":
        return default
    lowered = value.strip().lower()
    if lowered in _TRUE_STRINGS:
        return True
    if lowered in _FALSE_STRINGS:
        return False
    raise RTSPConfigError(
        f"{camera_id}: TRACKX_RTSP_{camera_id}_{var_name}={value!r} is not a recognized "
        f"boolean (use one of {sorted(_TRUE_STRINGS | _FALSE_STRINGS)})"
    )


def _build_cpplus_url(host, port, username, password, channel, subtype, scheme=DEFAULT_SCHEME, path_style=DEFAULT_PATH_STYLE):
    """Assembles a CP PLUS / Dahua-style RTSP(S) URL. Username/password are
    percent-encoded (a real CP PLUS install's password can contain
    characters like '@' or '/' that would otherwise corrupt the URL) and
    omitted entirely when there's no username, so an unauthenticated
    camera doesn't get a stray "@" in its URL."""
    auth = ""
    if username:
        auth = quote(username, safe="")
        if password:
            auth += f":{quote(password, safe='')}"
        auth += "@"
    template = _PATH_STYLES.get(path_style)
    if template is None:
        raise RTSPConfigError(f"Unknown RTSP PATH_STYLE {path_style!r} - expected one of {sorted(_PATH_STYLES)}")
    path = template.format(channel=channel, subtype=subtype)
    return f"{scheme}://{auth}{host}:{port}{path}"


def resolve_rtsp_url(camera_id):
    """
    Returns the configured real-camera RTSP URL for `camera_id`, or None if
    no RTSP configuration exists for it at all (the normal/default case for
    every camera today - this is not an error).

    Raises RTSPConfigError for an unknown camera id, or for a camera with
    SOME RTSP env vars set but not enough to build a URL (e.g. a
    _USERNAME/_PASSWORD with no _HOST and no _URL) - that's very likely a
    typo'd env var name, and failing loudly beats silently falling back to
    the demo video as if nothing was configured.
    """
    if camera_id not in CAMERAS:
        raise RTSPConfigError(f"Unknown camera id: {camera_id!r}")

    full_url = _env_for(camera_id, "URL")
    if full_url:
        return full_url

    host = _env_for(camera_id, "HOST")
    username = _env_for(camera_id, "USERNAME", "")
    password = _env_for(camera_id, "PASSWORD", "")
    channel_raw = _env_for(camera_id, "CHANNEL")
    subtype_raw = _env_for(camera_id, "SUBTYPE")
    port_raw = _env_for(camera_id, "PORT")

    any_partial_config = any([username, password, channel_raw, subtype_raw, port_raw])

    if not host:
        if any_partial_config:
            raise RTSPConfigError(
                f"{camera_id}: TRACKX_RTSP_{camera_id}_HOST (or _URL) is not set, but other "
                f"TRACKX_RTSP_{camera_id}_* variables are - this looks like an incomplete/typo'd "
                f"camera config rather than 'no real camera configured'. Set _HOST (or a full "
                f"_URL) or remove the other TRACKX_RTSP_{camera_id}_* vars."
            )
        return None  # genuinely unconfigured - the normal, default case

    try:
        port = int(port_raw) if port_raw else DEFAULT_RTSP_PORT
    except ValueError:
        raise RTSPConfigError(f"{camera_id}: TRACKX_RTSP_{camera_id}_PORT={port_raw!r} is not an integer")
    try:
        channel = int(channel_raw) if channel_raw else DEFAULT_CHANNEL
    except ValueError:
        raise RTSPConfigError(f"{camera_id}: TRACKX_RTSP_{camera_id}_CHANNEL={channel_raw!r} is not an integer")
    try:
        subtype = int(subtype_raw) if subtype_raw else DEFAULT_SUBTYPE
    except ValueError:
        raise RTSPConfigError(f"{camera_id}: TRACKX_RTSP_{camera_id}_SUBTYPE={subtype_raw!r} is not an integer")

    scheme = _env_for(camera_id, "SCHEME", DEFAULT_SCHEME).strip().lower()
    if scheme not in ("rtsp", "rtsps"):
        raise RTSPConfigError(f"{camera_id}: TRACKX_RTSP_{camera_id}_SCHEME={scheme!r} must be 'rtsp' or 'rtsps'")

    path_style = _env_for(camera_id, "PATH_STYLE", DEFAULT_PATH_STYLE).strip().lower()
    if path_style not in _PATH_STYLES:
        raise RTSPConfigError(
            f"{camera_id}: TRACKX_RTSP_{camera_id}_PATH_STYLE={path_style!r} must be one of {sorted(_PATH_STYLES)}"
        )

    return _build_cpplus_url(host, port, username, password, channel, subtype, scheme=scheme, path_style=path_style)


@dataclass
class RTSPStreamOptions:
    """Connection-level options that apply to a camera's RTSP(S) source
    regardless of whether its URL came from the component vars above or a
    full `_URL` override - a real CP PLUS camera (see module docstring)
    is configured this way: `_URL` gives the exact verified URL, and
    `_TLS_VERIFY`/`_TRANSPORT` are read independently."""
    transport: str = DEFAULT_TRANSPORT
    tls_verify: bool = DEFAULT_TLS_VERIFY
    rotation: int = DEFAULT_ROTATION


def resolve_stream_options(camera_id):
    """Reads TRACKX_RTSP_<camera_id>_TRANSPORT / _TLS_VERIFY / _ROTATION
    (with secure/no-op defaults - see the module docstring) independent of
    how the camera's URL itself was configured. Raises RTSPConfigError for
    an unrecognized value, same "fail loudly on likely typo" policy as
    resolve_rtsp_url."""
    if camera_id not in CAMERAS:
        raise RTSPConfigError(f"Unknown camera id: {camera_id!r}")

    transport = (_env_for(camera_id, "TRANSPORT", DEFAULT_TRANSPORT) or DEFAULT_TRANSPORT).strip().lower()
    if transport not in ("tcp", "udp"):
        raise RTSPConfigError(f"{camera_id}: TRACKX_RTSP_{camera_id}_TRANSPORT={transport!r} must be 'tcp' or 'udp'")

    tls_verify = _parse_bool_env(
        _env_for(camera_id, "TLS_VERIFY"), DEFAULT_TLS_VERIFY, camera_id, "TLS_VERIFY",
    )

    rotation_raw = (_env_for(camera_id, "ROTATION", str(DEFAULT_ROTATION)) or str(DEFAULT_ROTATION)).strip()
    try:
        rotation = int(rotation_raw)
    except ValueError:
        raise RTSPConfigError(
            f"{camera_id}: TRACKX_RTSP_{camera_id}_ROTATION={rotation_raw!r} must be an integer "
            f"({', '.join(str(r) for r in VALID_ROTATIONS)})"
        )
    if rotation not in VALID_ROTATIONS:
        raise RTSPConfigError(
            f"{camera_id}: TRACKX_RTSP_{camera_id}_ROTATION={rotation!r} must be one of "
            f"{', '.join(str(r) for r in VALID_ROTATIONS)}"
        )

    return RTSPStreamOptions(transport=transport, tls_verify=tls_verify, rotation=rotation)


def get_configured_camera_ids():
    """All camera ids (from network.camera_network.CAMERAS) that currently
    have a real RTSP source configured. Used by admin/status surfaces, and
    by tests, rather than each caller re-deriving this by calling
    resolve_rtsp_url() over every camera id itself."""
    configured = []
    for camera_id in CAMERAS:
        if resolve_rtsp_url(camera_id) is not None:
            configured.append(camera_id)
    return configured


_CREDENTIAL_RE = re.compile(r"^(rtsp[s]?://)([^@/]+)@(.*)$")


def redact_rtsp_url(url):
    """Replaces any userinfo (username[:password]) in an rtsp:// URL with
    '****' so it's safe to put in an API response, a WebSocket message, or
    a log line. A URL with no userinfo (unauthenticated camera) is returned
    unchanged - there's nothing to redact and the host/path aren't
    sensitive on their own (same as this repo not redacting the
    DATABASE_URL host, only credentials).

    Deliberately conservative: on anything that doesn't match the expected
    rtsp(s)://user[:pass]@host... shape, this still masks past the scheme
    rather than ever risking a credential leaking through unmasked.
    """
    if not url:
        return url
    match = _CREDENTIAL_RE.match(url)
    if match:
        scheme, _userinfo, rest = match.groups()
        return f"{scheme}****@{rest}"
    if "@" in url:
        # Doesn't match the strict pattern (e.g. multiple '@'s) but clearly
        # still carries a userinfo segment - mask everything up to the last
        # '@' rather than risk leaking a credential through an edge case.
        scheme_sep = url.find("://")
        if scheme_sep != -1:
            last_at = url.rfind("@")
            return url[:scheme_sep + 3] + "****@" + url[last_at + 1:]
    return url


@dataclass
class CameraSource:
    """What /live-stream/{camera_id} (and anything else that wants 'the
    video source for this camera, real-camera-first') should actually
    read frames from, plus enough metadata to tell the operator/frontend
    the honest truth about what they're looking at."""
    camera_id: str
    kind: str          # "rtsp" (real CP PLUS/RTSP camera) or "simulated_video" (local file)
    path: str           # what to pass as video_path to pipeline.run_video_to_db / track_video
    label: str          # human-readable, credential-free description
    display_name: str   # short, credential-free (redacted URL, or video basename)
    # Only meaningful when kind == "rtsp" - a "simulated_video" source is a
    # plain filesystem path, not a URL, so these stay at their defaults.
    scheme: str = ""               # "rtsp" or "rtsps"
    transport: str = DEFAULT_TRANSPORT
    tls_verify: bool = DEFAULT_TLS_VERIFY
    rotation: int = DEFAULT_ROTATION  # clockwise degrees; only actually applied on the ffmpeg-bridge (rtsps) path - see module docstring

    @property
    def is_real_camera(self):
        return self.kind == "rtsp"

    @property
    def needs_ffmpeg_bridge(self):
        """True only for a real camera's RTSPS (RTSP-over-TLS) source -
        see network/ffmpeg_frame_source.py's docstring for why RTSPS can't
        go through ultralytics/OpenCV's own stream loader. Plain rtsp://
        real cameras and every simulated_video source are unaffected."""
        return self.kind == "rtsp" and self.scheme == "rtsps"


class NoCameraSourceAvailable(Exception):
    """Raised when a camera has neither a configured RTSP source nor any
    local simulated video/media - there is genuinely nothing to stream."""


def resolve_camera_source(camera_id):
    """
    The single place that decides "what do we actually read frames from
    for this camera" - real CP PLUS/RTSP camera if one is configured,
    otherwise the exact same local-video-file simulation
    demo.camera_simulator has always provided. Callers (the /live-stream
    WebSocket, the camera-media/status endpoints) should use this instead
    of calling demo.camera_simulator.get_camera_feed() directly, so real
    cameras are picked up automatically the moment they're configured,
    with no per-caller "is this camera real" branching.

    Raises RTSPConfigError for bad RTSP config (see resolve_rtsp_url).
    Raises NoCameraSourceAvailable if there's no RTSP config AND no local
    media - the caller decides how to present that (e.g. the WebSocket
    handler's existing "no local media folder" error message).
    """
    import os as _os
    from demo.camera_simulator import get_camera_feed, CameraFeedNotFound

    rtsp_url = resolve_rtsp_url(camera_id)  # may raise RTSPConfigError
    if rtsp_url is not None:
        options = resolve_stream_options(camera_id)  # may raise RTSPConfigError
        scheme = urlsplit(rtsp_url).scheme.lower()
        label = "Live CP PLUS RTSP camera" if scheme == "rtsp" else "Live CP PLUS RTSPS (TLS) camera"
        return CameraSource(
            camera_id=camera_id,
            kind="rtsp",
            path=rtsp_url,
            label=label,
            display_name=redact_rtsp_url(rtsp_url),
            scheme=scheme,
            transport=options.transport,
            tls_verify=options.tls_verify,
            rotation=options.rotation,
        )

    try:
        feed = get_camera_feed(camera_id)
    except CameraFeedNotFound:
        raise NoCameraSourceAvailable(
            f"No real RTSP camera configured and no local feed folder for '{camera_id}'."
        )
    if not feed.videos:
        raise NoCameraSourceAvailable(
            f"No real RTSP camera configured and '{camera_id}' has no video file to stream."
        )

    video_path = feed.videos[0]
    return CameraSource(
        camera_id=camera_id,
        kind="simulated_video",
        path=video_path,
        label="Simulated feed (local video file, no real camera configured)",
        display_name=_os.path.basename(video_path),
    )


def probe_rtsp_connectivity(url, timeout_seconds=DEFAULT_PROBE_TIMEOUT_SECONDS,
                             transport=DEFAULT_TRANSPORT, tls_verify=DEFAULT_TLS_VERIFY):
    """
    Attempts a real, time-bounded connection to an RTSP(S) URL and reads
    one frame. Returns a dict:

        {"reachable": bool, "detail": str, "width": int|None, "height": int|None}

    `detail` never contains the URL's credentials (only the redacted form
    is ever used in messages here).

    An rtsps:// URL is probed via the real `ffmpeg`/`ffprobe` binaries
    (network/ffmpeg_frame_source.py) using the exact same `transport`/
    `tls_verify` flags open_camera_frames() would use to actually stream
    it - OpenCV's cv2.VideoCapture has no reliable way to pass
    `-tls_verify`, so probing an RTSPS camera with cv2 would report
    "unreachable" even for a working camera (see that module's docstring).
    A plain rtsp:// URL is probed via cv2.VideoCapture exactly as before -
    unaffected by this.

    Either way, the actual connect-and-read-a-frame attempt runs in a
    worker thread with a hard wall-clock timeout enforced here, since
    neither cv2.VideoCapture nor a hung subprocess reliably honors its own
    timeout against a host that's down/unreachable/firewalled - if it
    doesn't finish in time this reports unreachable and abandons that
    thread/process rather than blocking the caller (e.g. an admin status
    API request).
    """
    redacted = redact_rtsp_url(url)
    is_rtsps = urlsplit(url).scheme.lower() == "rtsps"

    def _attempt():
        if is_rtsps:
            from network.ffmpeg_frame_source import probe_stream_dimensions, FFmpegNotAvailable, FFmpegStreamError
            try:
                width, height = probe_stream_dimensions(url, transport=transport, tls_verify=tls_verify, timeout_seconds=timeout_seconds)
            except FFmpegNotAvailable as e:
                return {"reachable": False, "detail": str(e), "width": None, "height": None}
            except FFmpegStreamError as e:
                return {"reachable": False, "detail": str(e), "width": None, "height": None}
            return {"reachable": True, "detail": f"Connected via ffmpeg and read stream info from {redacted}", "width": width, "height": height}

        import cv2
        cap = cv2.VideoCapture(url)
        try:
            if not cap.isOpened():
                return {"reachable": False, "detail": f"Could not open stream: {redacted}", "width": None, "height": None}
            ok, frame = cap.read()
            if not ok or frame is None:
                return {"reachable": False, "detail": f"Opened but read no frame: {redacted}", "width": None, "height": None}
            height, width = frame.shape[:2]
            return {"reachable": True, "detail": f"Connected and read a frame from {redacted}", "width": int(width), "height": int(height)}
        finally:
            cap.release()

    # Deliberately NOT a `with ThreadPoolExecutor(...) as pool:` block: that
    # form calls pool.shutdown(wait=True) on exit, which would block THIS
    # function on the slow/hung worker thread finishing anyway - defeating
    # the entire point of enforcing our own timeout below. shutdown(wait=False)
    # lets this function return on time even if `_attempt` is still stuck
    # inside a hung cv2.VideoCapture() call; that one worker thread is
    # abandoned (it will exit on its own once/if the underlying I/O ever
    # unblocks or errors) rather than dragging this call down with it.
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_attempt)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        return {
            "reachable": False,
            "detail": f"Timed out after {timeout_seconds}s connecting to {redacted}",
            "width": None,
            "height": None,
        }
    except Exception as e:
        # Defensive redaction: some underlying libraries (cv2 in
        # particular) can embed the exact source string they were given
        # in their own exception message - str(e).replace(...) makes sure
        # the raw credential-bearing URL can never ride along even then.
        safe_detail = str(e).replace(url, redacted) if url in str(e) else str(e)
        return {
            "reachable": False,
            "detail": f"Error connecting to {redacted}: {safe_detail}",
            "width": None,
            "height": None,
        }
    finally:
        pool.shutdown(wait=False)


def open_camera_frames(source, vehicle_detector):
    """
    Yields (frame_idx, frame, vehicle_detections) - the exact shape
    VehicleDetector.track_video() yields, and exactly what
    pipeline.run_video_to_db()'s frame loop expects - regardless of
    whether `source` needs the real ffmpeg-subprocess bridge (an RTSPS
    real camera - see network/ffmpeg_frame_source.py) or can go straight
    through ultralytics' own native stream/file loader (a plain rtsp://
    real camera, or a simulated_video local file - both completely
    unaffected by this function's existence).

    `vehicle_detector` must be the SAME detector instance used for
    everything else in this run (see VehicleDetector.track_frame()'s own
    docstring on why: ultralytics' persist=True tracker state lives on
    the detector's `self.model`, so a second concurrent live session on
    the same detector instance would corrupt both sessions' track IDs -
    this function does not add any new concurrency of its own, but
    inherits that same constraint from track_frame()).
    """
    if not source.needs_ffmpeg_bridge:
        yield from vehicle_detector.track_video(source.path)
        return

    from network.ffmpeg_frame_source import iter_frames_via_ffmpeg

    vehicle_detector.start_new_live_session()
    for frame_idx, frame in enumerate(iter_frames_via_ffmpeg(
        source.path, transport=source.transport, tls_verify=source.tls_verify, rotation=source.rotation,
    )):
        yield frame_idx, frame, vehicle_detector.track_frame(frame)
