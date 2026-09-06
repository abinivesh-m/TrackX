"""
LPRNet-based OCR for Indian License Plates.

This module implements LPRNet (License Plate Recognition Network) for
high-accuracy Indian license plate recognition. LPRNet is a lightweight CNN
designed specifically for license plate reading with CTC (Connectionist
Temporal Classification) loss.

Reference: "LPRNet: License Plate Recognition via Deep Neural Networks"
Adapted from the Indian_LPR project (sanchit2843/Indian_LPR,
arXiv:2111.06054 "Indian Licence Plate Dataset in the wild"), whose
`best_lprnet.pth` checkpoint was trained on ~21k Indian plates. The
architecture here matches that checkpoint exactly (Inception-style
small_basic_block backbone + CTC head), so `models/lprnet_indian.pth`
loads directly.

Inference contract (must match training):
    - input: BGR crop resized to (94, 24) (width, height)
    - normalization: (img - 127.5) * 0.0078125, channels-first (CHW)
    - output: (batch, class_num, seq_len) logits, greedy CTC decoding where
      the last charset index ("-" / blank, id 36) separates characters
"""

import torch
import torch.nn as nn
import numpy as np
import cv2
from typing import Tuple, Optional, List
import os
import re

# ---------------------------------------------------------------------------
# Character set (must match the training configuration of the checkpoint)
# ---------------------------------------------------------------------------
CHARS = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
    "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
    "U", "V", "W", "X", "Y", "Z",
    "-",  # blank / separator class used by CTC (index 36)
]
CHARS_DICT = {char: i for i, char in enumerate(CHARS)}
BLANK_INDEX = len(CHARS) - 1  # 36

# Inference input size (width, height) and normalization constants
IMG_SIZE = (94, 24)
IMG_MEAN = 127.5
IMG_SCALE = 0.0078125
LPR_MAX_LEN = 16
DROPOUT_RATE = 0.5


class small_basic_block(nn.Module):
    """Inception-style block: 1x1 -> 3x1 -> 1x3 -> 1x1 (channel bottleneck)."""

    def __init__(self, ch_in, ch_out):
        super(small_basic_block, self).__init__()
        self.block = nn.Sequential(
            nn.Conv2d(ch_in, ch_out // 4, kernel_size=1),
            nn.ReLU(),
            nn.Conv2d(ch_out // 4, ch_out // 4, kernel_size=(3, 1), padding=(1, 0)),
            nn.ReLU(),
            nn.Conv2d(ch_out // 4, ch_out // 4, kernel_size=(1, 3), padding=(0, 1)),
            nn.ReLU(),
            nn.Conv2d(ch_out // 4, ch_out, kernel_size=1),
        )

    def forward(self, x):
        return self.block(x)


class LPRNet(nn.Module):
    """
    LPRNet backbone + CTC head.

    Input:  (3, 24, 94) BGR crop, normalized
    Output: (batch, class_num, seq_len) logits over the character axis
    """

    def __init__(self, lpr_max_len, phase, class_num, dropout_rate):
        super(LPRNet, self).__init__()
        self.phase = phase
        self.lpr_max_len = lpr_max_len
        self.class_num = class_num
        self.backbone = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=64, kernel_size=3, stride=1),  # 0
            nn.BatchNorm2d(num_features=64),
            nn.ReLU(),  # 2
            nn.MaxPool3d(kernel_size=(1, 3, 3), stride=(1, 1, 1)),
            small_basic_block(ch_in=64, ch_out=128),  # *** 4 ***
            nn.BatchNorm2d(num_features=128),
            nn.ReLU(),  # 6
            nn.MaxPool3d(kernel_size=(1, 3, 3), stride=(2, 1, 2)),
            small_basic_block(ch_in=64, ch_out=256),  # 8
            nn.BatchNorm2d(num_features=256),
            nn.ReLU(),  # 10
            small_basic_block(ch_in=256, ch_out=256),  # *** 11 ***
            nn.BatchNorm2d(num_features=256),  # 12
            nn.ReLU(),
            nn.MaxPool3d(kernel_size=(1, 3, 3), stride=(4, 1, 2)),  # 14
            nn.Dropout(dropout_rate),
            nn.Conv2d(in_channels=64, out_channels=256, kernel_size=(1, 4), stride=1),  # 16
            nn.BatchNorm2d(num_features=256),
            nn.ReLU(),  # 18
            nn.Dropout(dropout_rate),
            nn.Conv2d(in_channels=256, out_channels=class_num, kernel_size=(13, 1), stride=1),  # 20
            nn.BatchNorm2d(num_features=class_num),
            nn.ReLU(),  # *** 22 ***
        )
        self.container = nn.Sequential(
            nn.Conv2d(
                in_channels=448 + self.class_num,
                out_channels=self.class_num,
                kernel_size=(1, 1),
                stride=(1, 1),
            ),
        )

    def forward(self, x):
        keep_features = list()
        for i, layer in enumerate(self.backbone.children()):
            x = layer(x)
            if i in [2, 6, 13, 22]:  # feature maps kept for the global context
                keep_features.append(x)

        global_context = list()
        for i, f in enumerate(keep_features):
            if i in [0, 1]:
                f = nn.AvgPool2d(kernel_size=5, stride=5)(f)
            if i in [2]:
                f = nn.AvgPool2d(kernel_size=(4, 10), stride=(4, 2))(f)
            f_pow = torch.pow(f, 2)
            f_mean = torch.mean(f_pow)
            f = torch.div(f, f_mean)
            global_context.append(f)

        x = torch.cat(global_context, 1)
        x = self.container(x)
        logits = torch.mean(x, dim=2)

        return logits


def build_lprnet(lpr_max_len=LPR_MAX_LEN, phase=False, class_num=len(CHARS),
                 dropout_rate=DROPOUT_RATE):
    """Build an LPRNet. phase=True returns the module in train mode."""
    net = LPRNet(lpr_max_len, phase, class_num, dropout_rate)
    if phase == "train":
        return net.train()
    return net.eval()


class LPRNetOCR:
    """
    TrackX-facing wrapper around the Indian-plate LPRNet checkpoint.

    Attributes:
        model_loaded: True only when a trained weight file was actually
            loaded. Never trust this engine when it is False - the checkpoint
            is what makes the reads meaningful.
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.device = device if torch.cuda.is_available() or device == "cpu" else "cpu"
        self.model = None
        self.model_loaded = False

        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
        else:
            # No trained weights available. Do NOT return a model with random
            # weights pretending it can read plates - garbage-in reads with a
            # fake high confidence would poison every tracker/alert downstream.
            # model_loaded stays False so callers (PlateOCR.__init__) fall
            # through to another engine instead.
            print("[LPRNet] No trained weight file found; LPRNet engine disabled. "
                  "Provide models/lprnet_indian.pth (Indian_LPR checkpoint).")
            self.model = None

    def load_model(self, model_path: str) -> bool:
        """Load a trained LPRNet state dict. Returns True on success."""
        try:
            self.model = build_lprnet(
                lpr_max_len=LPR_MAX_LEN,
                phase=False,
                class_num=len(CHARS),
                dropout_rate=DROPOUT_RATE,
            )
            state_dict = torch.load(model_path, map_location=self.device,
                                    weights_only=True)
            self.model.load_state_dict(state_dict)
            self.model.to(self.device)
            self.model.eval()
            self.model_loaded = True
            print(f"[LPRNet] Loaded trained weights from {model_path} "
                  f"({len(CHARS)} classes, input {IMG_SIZE[0]}x{IMG_SIZE[1]})")
            return True
        except Exception as e:
            print(f"[LPRNet] Failed to load model: {e}")
            # Never fall back to a random-weight model that would emit
            # garbage reads - keep the engine flagged as unloaded.
            self.model = None
            self.model_loaded = False
            return False


    def preprocess_image(self, image: np.ndarray) -> torch.Tensor:
        """
        Convert a BGR plate crop into the normalized network input.

        Matches the training pipeline exactly: resize to (94, 24),
        (img - 127.5) * 0.0078125, HWC -> CHW.
        """
        if image is None or image.size == 0:
            raise ValueError("empty image passed to LPRNetOCR")

        img = cv2.resize(image, IMG_SIZE)  # (width=94, height=24)
        img = img.astype("float32")
        img -= IMG_MEAN
        img *= IMG_SCALE
        img = np.transpose(img, (2, 0, 1))  # HWC -> CHW
        tensor = torch.from_numpy(img).unsqueeze(0)  # (1, 3, 24, 94)
        return tensor.to(self.device)

    def decode(self, logits: torch.Tensor) -> Tuple[str, float]:
        """
        Greedy CTC decoding of (1, class_num, seq_len) logits.

        Per-timestep argmax, collapsing repeated labels and dropping the
        blank class. Confidence is the mean of the winning softmax
        probabilities over the emitted (pre-collapse) positions.
        """
        preds = logits.detach().cpu().numpy()[0]  # (class_num, seq_len)

        # softmax over classes per timestep
        exps = np.exp(preds - preds.max(axis=0, keepdims=True))
        probs = exps / exps.sum(axis=0, keepdims=True)
        best = probs.argmax(axis=0)
        best_prob = probs.max(axis=0)

        chars = []
        confidences = []
        prev = -1
        for idx in range(best.shape[0]):
            cls = int(best[idx])
            if cls != prev and cls != BLANK_INDEX:
                chars.append(CHARS[cls])
                confidences.append(float(best_prob[idx]))
            prev = cls

        text = "".join(chars)
        confidence = float(np.mean(confidences)) if confidences else 0.0
        return text, confidence


    def read_plate(self, image: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Read license plate text from a BGR plate-crop image.

        Returns:
            Tuple of (plate_text, confidence_score); (None, 0.0) when the
            engine has no loaded model or the read fails.
        """
        if self.model is None:
            return None, 0.0

        try:
            input_tensor = self.preprocess_image(image)
            with torch.no_grad():
                logits = self.model(input_tensor)
            text, confidence = self.decode(logits)

            if text and len(text) >= 4:
                text = self.validate_indian_plate(text)
                return text, confidence

            return None, 0.0

        except Exception as e:
            print(f"[LPRNet] OCR failed: {e}")
            return None, 0.0

    def validate_indian_plate(self, text: str) -> str:
        """
        Validate and lightly correct an Indian license plate read.

        Removes non-alphanumerics and, when a standard-format plate is
        embedded in a longer read, extracts it.
        """
        if not text or len(text) < 6:
            return text

        text = "".join(c for c in text if c.isalnum()).upper()

        patterns = [
            r"^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$",  # standard current format
            r"^[A-Z]{2}\d{2}[A-Z]{2}\d{4}$",      # older 2-letter series
        ]
        for pattern in patterns:
            if re.match(pattern, text):
                return text

        match = re.search(r"([A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4})", text)
        if match:
            return match.group(1)

        return text


# Global LPRNet instance
_lprnet_instance = None


def get_lprnet_ocr(model_path: Optional[str] = None, device: str = "cpu") -> LPRNetOCR:
    """Get or create the global LPRNet OCR instance."""
    global _lprnet_instance
    if _lprnet_instance is None:
        _lprnet_instance = LPRNetOCR(model_path, device)
    return _lprnet_instance


def try_init_lprnet(model_path: Optional[str] = None) -> Optional[LPRNetOCR]:
    """
    Attempt to initialize LPRNet with error handling.

    Returns:
        LPRNetOCR instance if a trained checkpoint loaded, None otherwise
        (an unloaded LPRNet would only emit random-weight garbage, so it is
        reported as unavailable and callers fall through to another engine).
    """
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        ocr = LPRNetOCR(model_path, device)
        if not ocr.model_loaded:
            print("[LPRNet] Trained weights not loaded; LPRNet engine is unavailable.")
            return None
        print(f"[LPRNet] Initialized successfully on {device}")
        return ocr
    except Exception as e:
        print(f"[LPRNet] Initialization failed: {e}")
        return None


if __name__ == "__main__":
    # quick manual test: python -m recognition.lprnet_ocr <plate_crop.jpg>
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m recognition.lprnet_ocr <cropped_plate.jpg>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    ocr = try_init_lprnet("models/lprnet_indian.pth")
    if ocr is None:
        print("LPRNet engine unavailable (weights not loaded)")
        sys.exit(1)
    text, conf = ocr.read_plate(img)
    print(text, round(conf, 3))
