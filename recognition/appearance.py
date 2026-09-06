"""
appearance.py

v2: swapped color-histogram for a pretrained ImageNet CNN embedding.
no training needed - we just use a ResNet18 pretrained on ImageNet and
take its second-to-last layer as a general "visual fingerprint." this
isn't a proper vehicle Re-ID model (that would need training on actual
vehicle re-id data, which we don't have time for), but a generic pretrained
CNN embedding is a real step up from raw color histograms - it captures
shape/texture, not just color, and is much more robust to lighting changes.

The visual pipeline now passes the FULL VEHICLE crop into this module.
That is the correct input for vehicle appearance similarity; plate crops are
reserved for plate/OCR processing.

Input: Full vehicle crop (BGR numpy array)
Output: Fixed-length list of floats (appearance embedding vector)

falls back to the color-histogram method when PyTorch/torchvision is
unavailable or pretrained weights are not already cached. This avoids making
the test suite and demo depend on an internet connection. Set
TRACKX_ALLOW_MODEL_DOWNLOAD=1 to explicitly allow a first-time weight download.
"""

import cv2
import numpy as np
import os
from pathlib import Path

try:
    import torch
    import torchvision.transforms as T
    import torchvision.models as models
    TORCH_AVAILABLE = True
except (ImportError, OSError):
    # OSError catches torch DLL loading errors (e.g., WinError 127)
    TORCH_AVAILABLE = False


_model = None
_transform = None


def _load_model():
    global _model, _transform
    if _model is not None:
        return True
    if not TORCH_AVAILABLE:
        return False

    # Never make normal tests/demo execution depend on an external CDN.
    # If weights are already cached, use the pretrained model. A user who
    # explicitly wants first-time downloading can opt in.
    allow_download = os.getenv("TRACKX_ALLOW_MODEL_DOWNLOAD", "").lower() in {
        "1", "true", "yes", "on"
    }
    try:
        weights = models.ResNet18_Weights.IMAGENET1K_V1
        if not allow_download:
            cache_root = Path(torch.hub.get_dir()) / "checkpoints"
            cached = cache_root / "resnet18-f37072fd.pth"
            if not cached.exists():
                return False

        base = models.resnet18(weights=weights)
        # Drop the final classification layer, keep the 512-d feature vector.
        _model = torch.nn.Sequential(*list(base.children())[:-1])
        _model.eval()

        _transform = T.Compose([
            T.ToPILImage(),
            T.Resize((128, 128)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225]),
        ])
        return True
    except Exception as exc:
        # A failed optional appearance model must never take down detection.
        print(f"[appearance] pretrained model unavailable: {exc}; using histogram fallback")
        _model = None
        _transform = None
        return False


def _cnn_embedding(crop_bgr):
    if not _load_model():
        return None
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    tensor = _transform(rgb).unsqueeze(0)

    with torch.no_grad():
        features = _model(tensor)

    vec = features.squeeze().numpy().tolist()
    return vec


def _histogram_fallback(crop_bgr):
    resized = cv2.resize(crop_bgr, (64, 64))
    hist = cv2.calcHist([resized], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    h, w = crop_bgr.shape[:2]
    aspect_ratio = w / h if h > 0 else 0
    return hist.tolist() + [aspect_ratio]


def get_appearance_vector(crop_bgr):
    """
    crop_bgr: numpy array (BGR), preferably the full vehicle crop.
    returns a fixed-length list of floats, or None if crop is empty.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return None

    if TORCH_AVAILABLE:
        embedding = _cnn_embedding(crop_bgr)
        if embedding is not None:
            return embedding
    return _histogram_fallback(crop_bgr)


def appearance_similarity(vec_a, vec_b):
    """cosine similarity, 0-1, higher = more similar"""
    if vec_a is None or vec_b is None:
        return 0.0

    a = np.array(vec_a)
    b = np.array(vec_b)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0

    sim = np.dot(a, b) / (norm_a * norm_b)
    return round(max(0.0, float(sim)), 3)
