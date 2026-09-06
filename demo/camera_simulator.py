"""
camera_simulator.py

DAY 1 — "camera simulation" step.

There's no real CCTV/RTSP feed yet (that's explicitly Phase 2). Day 1
simulates a camera by treating a local folder of images/videos as if it
were that camera's footage:

    data/cameras/<CAM_ID>/images/*.jpg|.jpeg|.png
    data/cameras/<CAM_ID>/videos/*.mp4|.avi|.mov

This module only does discovery (which files exist for a camera) - it
does not open/decode any media itself, so it has no dependency on
OpenCV/YOLO/PaddleOCR and can be unit tested in isolation.

Camera IDs here are expected to line up with network.camera_network.CAMERAS
(CAM_01..CAM_04) so that Day 2 can attach lat/long from there, but this
module doesn't import that yet, since Day 1 explicitly stays disconnected
from the rest of the intelligence stack.
"""
import os

SUPPORTED_IMAGE_EXT = {".jpg", ".jpeg", ".png"}
SUPPORTED_VIDEO_EXT = {".mp4", ".avi", ".mov"}

DEFAULT_CAMERA_ROOT = "data/cameras"

STANDARD_CAMERA_IDS = ("CAM_01", "CAM_02", "CAM_03", "CAM_04", "CAM_05", "CAM_06", "CAM_07")


class CameraFeedNotFound(Exception):
    """Raised when the requested camera has no local folder at all."""


def camera_dir(camera_id, root=DEFAULT_CAMERA_ROOT):
    return os.path.join(root, camera_id)


def list_camera_media(camera_id, root=DEFAULT_CAMERA_ROOT):
    """
    Returns (image_paths, video_paths) for a given camera, sorted for
    deterministic ordering. Missing images/ or videos/ subfolders are
    treated as "zero files of that type", not an error - a camera might
    only have stills, or only have video. Only a completely missing
    camera folder raises CameraFeedNotFound.
    """
    base = camera_dir(camera_id, root)
    img_dir = os.path.join(base, "images")
    vid_dir = os.path.join(base, "videos")

    if not os.path.isdir(base):
        raise CameraFeedNotFound(
            f"No local feed folder for '{camera_id}' at '{base}'. "
            f"Expected '{img_dir}' and/or '{vid_dir}' to exist. "
            f"Run with --setup-dirs to create the standard folder layout."
        )

    images = []
    if os.path.isdir(img_dir):
        for fname in sorted(os.listdir(img_dir)):
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_IMAGE_EXT:
                images.append(os.path.join(img_dir, fname))

    videos = []
    if os.path.isdir(vid_dir):
        for fname in sorted(os.listdir(vid_dir)):
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_VIDEO_EXT:
                videos.append(os.path.join(vid_dir, fname))

    return images, videos


def ensure_camera_dirs(camera_ids=STANDARD_CAMERA_IDS, root=DEFAULT_CAMERA_ROOT):
    """Creates the standard per-camera images/ and videos/ subfolders if missing."""
    created = []
    for cam in camera_ids:
        for sub in ("images", "videos"):
            path = os.path.join(root, cam, sub)
            if not os.path.isdir(path):
                os.makedirs(path, exist_ok=True)
                created.append(path)
    return created


class CameraFeed:
    """
    Represents one simulated camera feed: a camera ID plus whatever local
    images/videos stand in for that camera's footage. This is the Day-1
    stand-in object for "a camera" - no RTSP/physical device involved,
    Phase 2 concern.
    """

    def __init__(self, camera_id, images, videos):
        self.camera_id = camera_id
        self.images = images
        self.videos = videos

    @property
    def has_media(self):
        return bool(self.images or self.videos)

    def __repr__(self):
        return f"CameraFeed({self.camera_id}: {len(self.images)} image(s), {len(self.videos)} video(s))"


def get_camera_feed(camera_id, root=DEFAULT_CAMERA_ROOT):
    """Discovers a camera's local media and wraps it as a CameraFeed."""
    images, videos = list_camera_media(camera_id, root)
    return CameraFeed(camera_id, images, videos)


def sample_frame_indices(frame_sample, max_frames=None):
    """
    Returns a `should_process(frame_idx) -> bool` predicate implementing
    the feed's frame-sampling policy: every Nth frame, optionally capped
    at max_frames. Lives here (not in visual_pipeline.py) because "which
    frames does this simulated feed actually deliver" is a camera-feed
    concern, not a detection concern - keeps frame_sample reusable for
    any future consumer that just wants sampled frames, not just the
    vehicle-detection pipeline.

    frame_sample must be >= 1 (1 = every frame).
    """
    if frame_sample < 1:
        raise ValueError("frame_sample must be >= 1")

    def should_process(frame_idx):
        if max_frames is not None and frame_idx >= max_frames:
            return False
        return frame_idx % frame_sample == 0

    return should_process


if __name__ == "__main__":
    import sys
    cam = sys.argv[1] if len(sys.argv) > 1 else "CAM_01"
    try:
        imgs, vids = list_camera_media(cam)
        print(f"{cam}: {len(imgs)} image(s), {len(vids)} video(s)")
        for p in imgs:
            print("  image:", p)
        for p in vids:
            print("  video:", p)
    except CameraFeedNotFound as e:
        print(e)
