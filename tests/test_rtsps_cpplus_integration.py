"""
tests/test_rtsps_cpplus_integration.py

SIH26127 real CP PLUS camera integration, RTSPS follow-up.

The operator ran a real, physical CP PLUS camera end-to-end with `ffmpeg`
and reported:

    - rtsps://<user>:<pass>@192.168.137.2:554/video/live?channel=1&subtype=0
      connects over RTSPS with `-tls_verify 0 -rtsp_transport tcp`: real
      HEVC/H.265, 2560x1440 @ 25fps, 250 frames in 10 real seconds.
    - Plain rtsp:// on BOTH /video/live and /cam/realmonitor was rejected
      outright (connection reset / ffmpeg error -10054) by this camera -
      RTSPS is mandatory for it, and its self-signed certificate means TLS
      verification must be explicitly disabled to connect.

This file covers what changed to support that, on top of
tests/test_rtsp_camera_integration.py (still fully valid and unchanged -
generic rtsp:// support was not touched):

  - A full rtsps:// TRACKX_RTSP_<CAM_ID>_URL override resolves and is
    treated as a real, configured camera.
  - TRACKX_RTSP_<CAM_ID>_TLS_VERIFY / _TRANSPORT are read independently of
    how the URL itself was obtained (full override or component vars),
    default to the secure/standard choice, and reject garbage values.
  - Credentials are never present in anything returned for
    display/logging, end to end through CameraSource, exactly as already
    proven for plain rtsp:// in test_rtsp_camera_integration.py.
  - resolve_camera_source() correctly identifies an rtsps:// camera as
    needing the ffmpeg bridge (network/ffmpeg_frame_source.py), while a
    plain rtsp:// real camera and the local-video simulation do not.
  - network/ffmpeg_frame_source.py's own command construction (transport/
    tls_verify flags, credential redaction in error paths) and frame
    decoding, with `subprocess.Popen`/`subprocess.run` mocked out - no
    real ffmpeg process or network I/O, matching this repo's other tests.
  - network.rtsp_camera.open_camera_frames() dispatches to the ffmpeg
    bridge only for an RTSPS source, and to the existing
    VehicleDetector.track_video()/track_frame() path otherwise.
  - pipeline._safe_source_label() - the fix for a real credential-leak
    risk this integration would otherwise introduce (record["source"]
    written to the observations DB/API).

No physical camera, no real ffmpeg subprocess, no real network I/O in this
suite - see docs/LIVE_STREAMING.md for exactly what was (and was not)
verified against the real hardware.

Run with: python -m pytest tests/test_rtsps_cpplus_integration.py -v
"""
import os
import sys
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from network.camera_network import CAMERAS
from network.rtsp_camera import (
    resolve_rtsp_url,
    resolve_stream_options,
    resolve_camera_source,
    redact_rtsp_url,
    open_camera_frames,
    RTSPConfigError,
    RTSPStreamOptions,
    DEFAULT_TRANSPORT,
    DEFAULT_TLS_VERIFY,
)
from network.ffmpeg_frame_source import (
    iter_frames_via_ffmpeg,
    probe_stream_dimensions,
    _transport_and_tls_args,
    _redact,
    FFmpegStreamError,
)
from pipeline import _safe_source_label

REAL_CAMERA_ID = "CAM_01"
assert REAL_CAMERA_ID in CAMERAS

# Deliberately NOT the operator's real camera password - a placeholder
# only, so nothing resembling the actual credential ever appears in this
# repo's source/tests/git history (see network/rtsp_camera.py's module
# docstring: credentials only ever come from environment variables at
# runtime, never hardcoded).
_TEST_PASSWORD = "test-placeholder-pw"
_VERIFIED_CPPLUS_RTSPS_URL = (
    f"rtsps://admin:{_TEST_PASSWORD}@192.168.137.2:554/video/live?channel=1&subtype=0"
)


def _clear_rtsp_env(camera_id):
    for suffix in ("URL", "HOST", "PORT", "USERNAME", "PASSWORD", "CHANNEL", "SUBTYPE",
                   "SCHEME", "PATH_STYLE", "TRANSPORT", "TLS_VERIFY"):
        os.environ.pop(f"TRACKX_RTSP_{camera_id}_{suffix}", None)


@pytest.fixture(autouse=True)
def _isolated_rtsp_env():
    _clear_rtsp_env(REAL_CAMERA_ID)
    yield
    _clear_rtsp_env(REAL_CAMERA_ID)


class TestRtspsUrlOverride:
    def test_full_rtsps_url_override_resolves_verbatim(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = _VERIFIED_CPPLUS_RTSPS_URL
        assert resolve_rtsp_url(REAL_CAMERA_ID) == _VERIFIED_CPPLUS_RTSPS_URL

    def test_rtsps_camera_is_reported_as_configured_and_real(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = _VERIFIED_CPPLUS_RTSPS_URL
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TLS_VERIFY"] = "0"

        source = resolve_camera_source(REAL_CAMERA_ID)

        assert source.kind == "rtsp"
        assert source.is_real_camera is True
        assert source.scheme == "rtsps"
        assert source.path == _VERIFIED_CPPLUS_RTSPS_URL

    def test_component_vars_can_also_build_an_rtsps_url_with_the_verified_path_style(self):
        # A camera configured via component vars (not a full _URL override)
        # can still reach the same rtsps://.../video/live?... shape the
        # real camera needed - PATH_STYLE=video_live is exactly the path
        # style verified against real hardware (distinct from the
        # cpplus/Dahua-default /cam/realmonitor path, which this same real
        # camera REJECTED).
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "192.168.137.2"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_SCHEME"] = "rtsps"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_PATH_STYLE"] = "video_live"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_USERNAME"] = "admin"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_PASSWORD"] = _TEST_PASSWORD

        url = resolve_rtsp_url(REAL_CAMERA_ID)
        assert url == _VERIFIED_CPPLUS_RTSPS_URL

    def test_dahua_path_style_stays_the_default_not_overridden_by_rtsps_support(self):
        # Item 1 of the follow-up request: the Dahua-derived
        # /cam/realmonitor URL must NOT become the default for this real
        # camera (it was tried against the real hardware and rejected on
        # both rtsp:// and rtsps://) - it remains available (other CP PLUS
        # units may still use it) but is never assumed.
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "192.168.1.50"
        url = resolve_rtsp_url(REAL_CAMERA_ID)
        assert url.startswith("rtsp://192.168.1.50:554/cam/realmonitor")

    def test_plain_rtsp_support_for_other_cameras_is_unaffected(self):
        # Item 7: keep existing rtsp:// support; do not remove it.
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.5"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_SCHEME"] = "rtsp"
        source = resolve_camera_source(REAL_CAMERA_ID)
        assert source.scheme == "rtsp"
        assert source.needs_ffmpeg_bridge is False


class TestStreamOptions:
    def test_defaults_are_tcp_transport_and_tls_verify_on(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = _VERIFIED_CPPLUS_RTSPS_URL
        options = resolve_stream_options(REAL_CAMERA_ID)
        assert options == RTSPStreamOptions(transport=DEFAULT_TRANSPORT, tls_verify=DEFAULT_TLS_VERIFY)
        assert options.transport == "tcp"
        assert options.tls_verify is True  # secure by default

    def test_tls_verify_must_be_explicitly_disabled(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = _VERIFIED_CPPLUS_RTSPS_URL
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TLS_VERIFY"] = "0"
        assert resolve_stream_options(REAL_CAMERA_ID).tls_verify is False

    @pytest.mark.parametrize("value", ["1", "true", "True", "YES", "on"])
    def test_various_truthy_spellings_of_tls_verify(self, value):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TLS_VERIFY"] = value
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.5"
        assert resolve_stream_options(REAL_CAMERA_ID).tls_verify is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "NO", "off"])
    def test_various_falsy_spellings_of_tls_verify(self, value):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TLS_VERIFY"] = value
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.5"
        assert resolve_stream_options(REAL_CAMERA_ID).tls_verify is False

    def test_garbage_tls_verify_value_raises_rather_than_guessing(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TLS_VERIFY"] = "maybe"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.5"
        with pytest.raises(RTSPConfigError):
            resolve_stream_options(REAL_CAMERA_ID)

    def test_garbage_transport_value_raises(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TRANSPORT"] = "carrier-pigeon"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.5"
        with pytest.raises(RTSPConfigError):
            resolve_stream_options(REAL_CAMERA_ID)

    def test_transport_and_tls_verify_apply_even_with_full_url_override(self):
        # This is exactly the real camera's actual configuration shape:
        # a full _URL override (item 3) plus independent _TLS_VERIFY.
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = _VERIFIED_CPPLUS_RTSPS_URL
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TRANSPORT"] = "tcp"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TLS_VERIFY"] = "0"

        source = resolve_camera_source(REAL_CAMERA_ID)
        assert source.transport == "tcp"
        assert source.tls_verify is False


class TestCredentialRedactionForRtsps:
    def test_redact_rtsp_url_handles_rtsps_scheme(self):
        redacted = redact_rtsp_url(_VERIFIED_CPPLUS_RTSPS_URL)
        assert _TEST_PASSWORD not in redacted
        assert "admin" not in redacted
        assert redacted == "rtsps://****@192.168.137.2:554/video/live?channel=1&subtype=0"

    def test_camera_source_never_leaks_the_real_camera_credentials(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = _VERIFIED_CPPLUS_RTSPS_URL
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TLS_VERIFY"] = "0"

        source = resolve_camera_source(REAL_CAMERA_ID)

        # display_name/label are the two fields anything user-facing/
        # loggable (the WebSocket "started" message, the camera-source API
        # endpoint) actually uses - see backend/app/api/v1/observations.py.
        assert _TEST_PASSWORD not in source.display_name
        assert _TEST_PASSWORD not in source.label
        # The real, usable URL is only ever in `.path` (what actually gets
        # opened) - this is expected and required, not a leak: `.path` is
        # never itself put in a log line or API response.
        assert _TEST_PASSWORD in source.path

    def test_pipeline_source_label_redacts_a_credentialed_url(self):
        # This is the actual fix for a real leak risk: pipeline.py used to
        # write record["source"] = video_path verbatim, which - once
        # video_path can be a real camera's credentialed URL - would have
        # written the camera's username/password straight into the
        # observations DB (and from there, the observations API).
        safe = _safe_source_label(_VERIFIED_CPPLUS_RTSPS_URL)
        assert _TEST_PASSWORD not in safe
        assert "admin" not in safe
        assert safe == "rtsps://****@192.168.137.2:554/video/live?channel=1&subtype=0"

    def test_pipeline_source_label_leaves_a_local_file_path_untouched(self):
        # Every existing (non-RTSP) caller must see zero behavior change.
        assert _safe_source_label("data/cameras/CAM_01/videos/anpr_test1.mp4") == "data/cameras/CAM_01/videos/anpr_test1.mp4"


class TestNeedsFfmpegBridge:
    def test_rtsps_real_camera_needs_the_ffmpeg_bridge(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = _VERIFIED_CPPLUS_RTSPS_URL
        source = resolve_camera_source(REAL_CAMERA_ID)
        assert source.needs_ffmpeg_bridge is True

    def test_plain_rtsp_real_camera_does_not_need_the_ffmpeg_bridge(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.5"
        source = resolve_camera_source(REAL_CAMERA_ID)
        assert source.needs_ffmpeg_bridge is False

    def test_simulated_video_does_not_need_the_ffmpeg_bridge(self):
        from demo.camera_simulator import CameraFeed
        fake_feed = CameraFeed(REAL_CAMERA_ID, images=[], videos=["/tmp/does-not-matter.mp4"])
        with patch("demo.camera_simulator.get_camera_feed", return_value=fake_feed):
            source = resolve_camera_source(REAL_CAMERA_ID)
        assert source.kind == "simulated_video"
        assert source.needs_ffmpeg_bridge is False


class TestFfmpegFrameSourceCommandConstruction:
    def test_tls_verify_flag_only_added_for_rtsps_scheme(self):
        rtsps_args = _transport_and_tls_args(_VERIFIED_CPPLUS_RTSPS_URL, "tcp", tls_verify=False)
        assert rtsps_args == ["-rtsp_transport", "tcp", "-tls_verify", "0"]

        rtsp_args = _transport_and_tls_args("rtsp://10.0.0.5:554/cam/realmonitor?channel=1&subtype=0", "tcp", tls_verify=False)
        assert rtsp_args == ["-rtsp_transport", "tcp"]  # no -tls_verify for a non-TLS source

    def test_tls_verify_true_maps_to_ffmpeg_value_1(self):
        args = _transport_and_tls_args(_VERIFIED_CPPLUS_RTSPS_URL, "tcp", tls_verify=True)
        assert args == ["-rtsp_transport", "tcp", "-tls_verify", "1"]

    def test_udp_transport_is_passed_through(self):
        args = _transport_and_tls_args(_VERIFIED_CPPLUS_RTSPS_URL, "udp", tls_verify=False)
        assert args[:2] == ["-rtsp_transport", "udp"]

    def test_redact_masks_credentials_in_error_messages(self):
        assert _TEST_PASSWORD not in _redact(_VERIFIED_CPPLUS_RTSPS_URL)
        assert _redact(_VERIFIED_CPPLUS_RTSPS_URL) == "rtsps://****@192.168.137.2:554/video/live?channel=1&subtype=0"


class TestProbeStreamDimensions:
    def test_uses_the_exact_verified_flags_and_parses_real_dimensions(self):
        # Mirrors the operator's own verified command
        # (`ffmpeg -tls_verify 0 -rtsp_transport tcp -i "rtsps://..." ...`)
        # - this test asserts the SAME flags get built, with ffprobe's
        # subprocess call itself mocked out (no real network I/O).
        fake_result = MagicMock(returncode=0, stdout=b"2560x1440\n", stderr=b"")
        with patch("subprocess.run", return_value=fake_result) as mock_run, \
             patch("shutil.which", return_value="/usr/bin/ffprobe"):
            width, height = probe_stream_dimensions(_VERIFIED_CPPLUS_RTSPS_URL, transport="tcp", tls_verify=False)

        assert (width, height) == (2560, 1440)
        cmd = mock_run.call_args[0][0]
        assert "-tls_verify" in cmd and cmd[cmd.index("-tls_verify") + 1] == "0"
        assert "-rtsp_transport" in cmd and cmd[cmd.index("-rtsp_transport") + 1] == "tcp"
        assert cmd[-1] == _VERIFIED_CPPLUS_RTSPS_URL

    def test_ffprobe_failure_is_reported_without_leaking_credentials(self):
        fake_result = MagicMock(returncode=1, stdout=b"", stderr=f"connecting to {_VERIFIED_CPPLUS_RTSPS_URL} failed".encode())
        with patch("subprocess.run", return_value=fake_result), \
             patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with pytest.raises(FFmpegStreamError) as excinfo:
                probe_stream_dimensions(_VERIFIED_CPPLUS_RTSPS_URL, tls_verify=False)
        assert _TEST_PASSWORD not in str(excinfo.value)


class TestIterFramesViaFfmpeg:
    def test_yields_correctly_shaped_frames_decoded_from_raw_pipe_output(self):
        width, height = 4, 3  # tiny, so the test frame bytes are trivial to construct
        frame_bytes = width * height * 3
        two_frames = bytes(range(256)) * ((frame_bytes * 2 // 256) + 1)
        two_frames = two_frames[:frame_bytes * 2]

        fake_proc = MagicMock()
        fake_proc.stdout = MagicMock()
        fake_proc.stdout.read.side_effect = [
            two_frames[:frame_bytes], two_frames[frame_bytes:], b"",  # EOF after 2 frames
        ]
        fake_proc.stderr = MagicMock()
        fake_proc.stderr.read.return_value = b""
        fake_proc.poll.return_value = 0

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("network.ffmpeg_frame_source.probe_stream_dimensions", return_value=(width, height)), \
             patch("subprocess.Popen", return_value=fake_proc):
            frames = list(iter_frames_via_ffmpeg(_VERIFIED_CPPLUS_RTSPS_URL, tls_verify=False))

        assert len(frames) == 2
        for frame in frames:
            assert isinstance(frame, np.ndarray)
            assert frame.shape == (height, width, 3)

    def test_process_is_terminated_on_early_break(self):
        fake_proc = MagicMock()
        fake_proc.stdout = MagicMock()
        fake_proc.stdout.read.return_value = b"\x00" * (2 * 2 * 3)  # infinite-looking supply of one tiny frame
        fake_proc.stderr = MagicMock()
        fake_proc.poll.return_value = None  # still "running"

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("network.ffmpeg_frame_source.probe_stream_dimensions", return_value=(2, 2)), \
             patch("subprocess.Popen", return_value=fake_proc):
            gen = iter_frames_via_ffmpeg(_VERIFIED_CPPLUS_RTSPS_URL, tls_verify=False)
            next(gen)  # get one real frame
            gen.close()  # simulate the caller breaking out of the loop

        fake_proc.terminate.assert_called_once()


class TestOpenCameraFrames:
    def test_dispatches_rtsps_source_to_the_ffmpeg_bridge(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = _VERIFIED_CPPLUS_RTSPS_URL
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_TLS_VERIFY"] = "0"
        source = resolve_camera_source(REAL_CAMERA_ID)

        fake_frame = np.zeros((4, 4, 3), dtype=np.uint8)
        mock_detector = MagicMock()
        mock_detector.track_frame.return_value = [{"track_id": 1, "bbox": [0, 0, 1, 1], "confidence": 0.9, "vehicle_type": "car"}]

        with patch("network.ffmpeg_frame_source.iter_frames_via_ffmpeg", return_value=iter([fake_frame, fake_frame])):
            results = list(open_camera_frames(source, mock_detector))

        assert len(results) == 2
        mock_detector.start_new_live_session.assert_called_once()
        assert mock_detector.track_frame.call_count == 2
        for i, (frame_idx, frame, dets) in enumerate(results):
            assert frame_idx == i
            assert dets == [{"track_id": 1, "bbox": [0, 0, 1, 1], "confidence": 0.9, "vehicle_type": "car"}]

    def test_dispatches_non_rtsps_source_straight_to_track_video(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.5"  # plain rtsp://
        source = resolve_camera_source(REAL_CAMERA_ID)

        mock_detector = MagicMock()
        mock_detector.track_video.return_value = iter([(0, "frame0", []), (1, "frame1", [])])

        results = list(open_camera_frames(source, mock_detector))

        mock_detector.track_video.assert_called_once_with(source.path)
        mock_detector.track_frame.assert_not_called()
        mock_detector.start_new_live_session.assert_not_called()
        assert len(results) == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
