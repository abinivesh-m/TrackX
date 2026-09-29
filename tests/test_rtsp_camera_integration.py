"""
tests/test_rtsp_camera_integration.py

SIH26127 real CP PLUS (RTSP) camera integration - see network/rtsp_camera.py
for the full design rationale. Covers, without needing a real physical
camera or network access:

  - CP PLUS/Dahua-style RTSP URL construction from env vars (defaults,
    overrides, percent-encoding of credentials, full-URL override).
  - "unconfigured" (fall back to simulated video) vs "misconfigured"
    (fail loudly) are genuinely different outcomes.
  - credentials are never present in anything this module returns for
    display/logging (redact_rtsp_url, and CameraSource.display_name/label
    end to end via resolve_camera_source).
  - resolve_camera_source()'s real-camera-first, honest-fallback-second
    behavior, using this repo's real network.camera_network.CAMERAS ids.
  - probe_rtsp_connectivity()'s reachable / unreachable / timeout outcomes,
    with cv2.VideoCapture mocked out (no real network I/O in this test
    suite - matches this repo's other tests, which never depend on real
    external devices/services).

No ultralytics/paddleocr/torch dependency - pure Python plus a mocked cv2
for the probe tests.

Run with: python -m pytest tests/test_rtsp_camera_integration.py -v
"""
import os
import sys
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from network.camera_network import CAMERAS
from network.rtsp_camera import (
    resolve_rtsp_url,
    get_configured_camera_ids,
    redact_rtsp_url,
    resolve_camera_source,
    probe_rtsp_connectivity,
    RTSPConfigError,
    NoCameraSourceAvailable,
    DEFAULT_RTSP_PORT,
    DEFAULT_CHANNEL,
    DEFAULT_SUBTYPE,
)

REAL_CAMERA_ID = "CAM_01"
assert REAL_CAMERA_ID in CAMERAS  # sanity: this test relies on a real camera id


def _clear_rtsp_env(camera_id):
    for suffix in ("URL", "HOST", "PORT", "USERNAME", "PASSWORD", "CHANNEL", "SUBTYPE"):
        os.environ.pop(f"TRACKX_RTSP_{camera_id}_{suffix}", None)


@pytest.fixture(autouse=True)
def _isolated_rtsp_env():
    """Every test in this file gets a clean slate for CAM_01's RTSP env
    vars, and cleans up after itself, so test order/parallelism can't leak
    config between tests or into the rest of the suite."""
    _clear_rtsp_env(REAL_CAMERA_ID)
    yield
    _clear_rtsp_env(REAL_CAMERA_ID)


class TestResolveRtspUrl:
    def test_unconfigured_camera_returns_none_not_an_error(self):
        assert resolve_rtsp_url(REAL_CAMERA_ID) is None

    def test_unknown_camera_id_raises(self):
        with pytest.raises(RTSPConfigError):
            resolve_rtsp_url("CAM_DOES_NOT_EXIST")

    def test_host_only_uses_cpplus_defaults(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "192.168.1.50"
        url = resolve_rtsp_url(REAL_CAMERA_ID)
        assert url == f"rtsp://192.168.1.50:{DEFAULT_RTSP_PORT}/cam/realmonitor?channel={DEFAULT_CHANNEL}&subtype={DEFAULT_SUBTYPE}"

    def test_full_component_config_builds_expected_cpplus_url(self):
        env = {
            "HOST": "10.0.0.20",
            "PORT": "5540",
            "USERNAME": "admin",
            "PASSWORD": "S3cret!",
            "CHANNEL": "2",
            "SUBTYPE": "1",
        }
        for suffix, val in env.items():
            os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_{suffix}"] = val

        url = resolve_rtsp_url(REAL_CAMERA_ID)
        assert url == "rtsp://admin:S3cret%21@10.0.0.20:5540/cam/realmonitor?channel=2&subtype=1"

    def test_username_without_password_omits_colon(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.20"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_USERNAME"] = "admin"
        url = resolve_rtsp_url(REAL_CAMERA_ID)
        assert url.startswith("rtsp://admin@10.0.0.20:")
        assert ":@" not in url

    def test_credentials_with_special_characters_are_percent_encoded(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.20"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_USERNAME"] = "user/name"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_PASSWORD"] = "p@ss:word"
        url = resolve_rtsp_url(REAL_CAMERA_ID)
        # An unescaped '/' or ':' in the userinfo would corrupt the URL's
        # own structure (get parsed as a path or port separator).
        assert "user/name" not in url
        assert "p@ss:word" not in url
        assert "user%2Fname" in url
        assert "p%40ss%3Aword" in url

    def test_full_url_override_takes_priority_over_component_vars(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_URL"] = "rtsp://override.example.com/stream1"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "ignored.example.com"
        assert resolve_rtsp_url(REAL_CAMERA_ID) == "rtsp://override.example.com/stream1"

    def test_partial_config_without_host_or_url_raises_loudly(self):
        # A stray/typo'd TRACKX_RTSP_CAM_01_USERNAME with no _HOST or _URL
        # must not silently behave like "not configured at all" - that
        # would fall back to the simulated video while an operator
        # believes a real camera is wired up.
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_USERNAME"] = "admin"
        with pytest.raises(RTSPConfigError):
            resolve_rtsp_url(REAL_CAMERA_ID)

    def test_non_integer_port_raises(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.20"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_PORT"] = "not-a-port"
        with pytest.raises(RTSPConfigError):
            resolve_rtsp_url(REAL_CAMERA_ID)


class TestGetConfiguredCameraIds:
    def test_reflects_current_env_state(self):
        assert REAL_CAMERA_ID not in get_configured_camera_ids()
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.20"
        assert REAL_CAMERA_ID in get_configured_camera_ids()


class TestRedactRtspUrl:
    def test_redacts_username_and_password(self):
        redacted = redact_rtsp_url("rtsp://admin:S3cret@10.0.0.20:554/cam/realmonitor?channel=1&subtype=0")
        assert "admin" not in redacted
        assert "S3cret" not in redacted
        assert redacted == "rtsp://****@10.0.0.20:554/cam/realmonitor?channel=1&subtype=0"

    def test_username_only_is_also_redacted(self):
        redacted = redact_rtsp_url("rtsp://admin@10.0.0.20:554/stream")
        assert "admin" not in redacted
        assert redacted == "rtsp://****@10.0.0.20:554/stream"

    def test_unauthenticated_url_is_unchanged(self):
        url = "rtsp://10.0.0.20:554/cam/realmonitor?channel=1&subtype=0"
        assert redact_rtsp_url(url) == url

    def test_none_and_empty_pass_through(self):
        assert redact_rtsp_url(None) is None
        assert redact_rtsp_url("") == ""


class TestResolveCameraSource:
    def test_falls_back_to_simulated_video_when_unconfigured(self, tmp_path):
        # Fake out demo.camera_simulator.get_camera_feed() itself (rather
        # than DEFAULT_CAMERA_ROOT, which is a plain default-argument value
        # already bound into get_camera_feed's signature at import time and
        # so can't be redirected by reassigning the module attribute after
        # the fact) so this test doesn't depend on whatever happens to be
        # under the real repo's data/cameras/ in this checkout.
        from demo.camera_simulator import CameraFeed

        cam_dir = tmp_path / REAL_CAMERA_ID / "videos"
        cam_dir.mkdir(parents=True)
        fake_video = cam_dir / "clip.mp4"
        fake_video.write_bytes(b"not a real video, just needs to exist")
        fake_feed = CameraFeed(REAL_CAMERA_ID, images=[], videos=[str(fake_video)])

        with patch("demo.camera_simulator.get_camera_feed", return_value=fake_feed):
            source = resolve_camera_source(REAL_CAMERA_ID)

        assert source.kind == "simulated_video"
        assert source.is_real_camera is False
        assert source.path == str(fake_video)
        assert source.display_name == "clip.mp4"

    def test_no_source_at_all_raises_no_camera_source_available(self):
        from demo.camera_simulator import CameraFeedNotFound

        with patch("demo.camera_simulator.get_camera_feed", side_effect=CameraFeedNotFound("no folder")):
            with pytest.raises(NoCameraSourceAvailable):
                resolve_camera_source(REAL_CAMERA_ID)

    def test_real_camera_takes_priority_and_never_leaks_credentials(self):
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_HOST"] = "10.0.0.20"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_USERNAME"] = "admin"
        os.environ[f"TRACKX_RTSP_{REAL_CAMERA_ID}_PASSWORD"] = "S3cret"

        source = resolve_camera_source(REAL_CAMERA_ID)

        assert source.kind == "rtsp"
        assert source.is_real_camera is True
        # The real, credential-bearing URL is only ever in `path` (what
        # actually gets passed to the detector/pipeline) - display_name and
        # label, the two fields anything user-facing/loggable should use,
        # must never contain it.
        assert "admin" not in source.display_name
        assert "S3cret" not in source.display_name
        assert "admin" not in source.label
        assert "S3cret" not in source.label
        assert "admin:S3cret" in source.path  # the real URL itself is untouched


class TestProbeRtspConnectivity:
    def test_reachable_when_capture_opens_and_reads_a_frame(self):
        fake_frame = MagicMock()
        fake_frame.shape = (480, 640, 3)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, fake_frame)

        with patch("cv2.VideoCapture", return_value=mock_cap):
            result = probe_rtsp_connectivity("rtsp://admin:S3cret@10.0.0.20:554/stream", timeout_seconds=2)

        assert result["reachable"] is True
        assert result["width"] == 640
        assert result["height"] == 480
        assert "S3cret" not in result["detail"]
        mock_cap.release.assert_called_once()

    def test_unreachable_when_capture_does_not_open(self):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=mock_cap):
            result = probe_rtsp_connectivity("rtsp://admin:S3cret@10.0.0.20:554/stream", timeout_seconds=2)

        assert result["reachable"] is False
        assert "S3cret" not in result["detail"]
        mock_cap.release.assert_called_once()

    def test_unreachable_when_opened_but_no_frame(self):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)

        with patch("cv2.VideoCapture", return_value=mock_cap):
            result = probe_rtsp_connectivity("rtsp://10.0.0.20:554/stream", timeout_seconds=2)

        assert result["reachable"] is False

    def test_times_out_rather_than_blocking_forever(self):
        def _slow_video_capture(_url):
            mock_cap = MagicMock()
            mock_cap.isOpened.side_effect = lambda: time.sleep(5) or True
            return mock_cap

        with patch("cv2.VideoCapture", side_effect=_slow_video_capture):
            start = time.time()
            result = probe_rtsp_connectivity("rtsp://10.0.0.20:554/stream", timeout_seconds=0.5)
            elapsed = time.time() - start

        assert result["reachable"] is False
        assert "Timed out" in result["detail"]
        assert elapsed < 3  # bounded by timeout_seconds, not the 5s sleep


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
