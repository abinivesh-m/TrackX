"""
Real demonstration of TrackX's plate-quality-aware adaptive preprocessing.

IMPORTANT / HONEST LABELING: the base plate crop is REAL (a genuine saved
crop from this session's real anpr_test1.mp4 pipeline run, ground-truth
plate UP22AT3248). The blur/low-light/rain degradations applied to it are
SYNTHETIC - there is no real rain/night footage available in this
environment, so these are constructed degradations (gaussian blur,
brightness reduction, additive noise + rain streaks) applied to a real
crop, used only to exercise and visually demonstrate the real,
already-implemented adaptive preprocessing pipeline (assess_plate_quality
-> preprocess_plate_crop -> PlateOCR). Every quality score and OCR result
shown is a REAL measurement from REAL code running on these images - only
the degradation itself is synthetic, and this script says so.
"""
import sys, os
sys.path.insert(0, "/home/claude/trackx-work/repo")
os.chdir("/home/claude/trackx-work/repo")

import cv2
import numpy as np
from recognition.plate_quality import assess_plate_quality
from recognition.ocr_reader import preprocess_plate_crop, try_init_ocr

BASE_CROP_PATH = "/home/claude/trackx-work/repo/outputs/results/plate_crops/CAM_ANPR_TEST1_frame122_track16_20260908_132224_784674.jpg"
GROUND_TRUTH = "UP22AT3248"

base = cv2.imread(BASE_CROP_PATH)
assert base is not None
# Upscale the tiny base crop a bit just for display legibility in the
# screenshot grid (does not affect any of the real measurements below,
# which all run on the analysis-resolution image separately).
DISPLAY_SCALE = 3


def make_blurry(img):
    return cv2.GaussianBlur(img, (0, 0), sigmaX=4.0)


def make_low_light(img):
    dark = (img.astype(np.float32) * 0.25).astype(np.uint8)
    noise = np.random.normal(0, 6, dark.shape).astype(np.int16)
    dark = np.clip(dark.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return dark


def make_rain(img):
    out = img.copy().astype(np.float32)
    # slight blur (rain/wet-lens softening) + brightness/contrast wash
    out = cv2.GaussianBlur(out, (0, 0), sigmaX=1.2)
    out = out * 0.75 + 15
    # additive sensor/rain noise
    noise = np.random.normal(0, 18, out.shape)
    out = out + noise
    out = np.clip(out, 0, 255).astype(np.uint8)
    # diagonal rain streaks
    h, w = out.shape[:2]
    streak_layer = np.zeros((h, w), dtype=np.uint8)
    rng = np.random.default_rng(7)
    for _ in range(max(6, (h * w) // 400)):
        x0 = rng.integers(0, w)
        y0 = rng.integers(0, h)
        length = rng.integers(4, 10)
        x1 = min(w - 1, x0 + length)
        y1 = min(h - 1, y0 + length)
        cv2.line(streak_layer, (x0, y0), (x1, y1), 255, 1)
    streak_bgr = cv2.cvtColor(streak_layer, cv2.COLOR_GRAY2BGR).astype(np.float32) * 0.35
    out = np.clip(out.astype(np.float32) + streak_bgr, 0, 255).astype(np.uint8)
    return out


def raw_ocr(ocr, img):
    """Bypasses TrackX's adaptive preprocessing entirely - the raw engine
    on the raw image, to show what OCR would produce WITHOUT the adaptive
    pipeline (fair naive baseline for comparison)."""
    try:
        result = ocr.ocr.ocr(img, cls=True)
    except Exception as e:
        return None, 0.0
    if not result or not result[0]:
        return None, 0.0
    texts, confs = [], []
    for line in result[0]:
        texts.append(line[1][0])
        confs.append(line[1][1])
    import re
    text = re.sub(r"[^A-Z0-9]", "", "".join(texts).upper())
    conf = round(sum(confs) / len(confs), 3) if confs else 0.0
    return (text or None), conf


def panel(label_lines, img, target_w=360, target_h=170):
    """Builds one labeled panel: image on top, text lines below, on a
    fixed-size dark canvas so panels line up in a grid."""
    canvas = np.full((target_h, target_w, 3), 24, dtype=np.uint8)
    ih, iw = img.shape[:2]
    scale = min((target_w - 16) / iw, (target_h - 70) / ih)
    rw, rh = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = cv2.resize(img, (rw, rh), interpolation=cv2.INTER_NEAREST)
    x_off = (target_w - rw) // 2
    canvas[8:8 + rh, x_off:x_off + rw] = resized
    y = 8 + rh + 16
    for line, color in label_lines:
        cv2.putText(canvas, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)
        y += 16
    return canvas


def hconcat_panels(panels):
    h = max(p.shape[0] for p in panels)
    return np.hstack([p if p.shape[0] == h else cv2.copyMakeBorder(p, 0, h - p.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(24, 24, 24)) for p in panels])


ocr = try_init_ocr()
assert ocr is not None, "OCR engine failed to initialize"

conditions = [
    ("GOOD (real crop, no degradation)", base),
    ("BLUR (synthetic gaussian blur)", make_blurry(base)),
    ("LOW LIGHT (synthetic darkening)", make_low_light(base)),
    ("RAIN (synthetic noise + streaks)", make_rain(base)),
]

rows = []
GREEN = (120, 230, 120)
RED = (110, 110, 240)
GRAY = (190, 190, 190)
YELLOW = (110, 220, 240)

for label, img in conditions:
    q = assess_plate_quality(img)
    raw_text, raw_conf = raw_ocr(ocr, img)
    text, conf, dbg = ocr.read(img, return_debug=True)

    raw_ok = raw_text == GROUND_TRUTH
    final_ok = text == GROUND_TRUTH

    left_lines = [
        (label, GRAY),
        (f"quality={q['quality_score']:.2f}  blur={q['blur_score']:.0f}  bright={q['brightness']:.0f}", GRAY),
        (f"WITHOUT adaptive preproc: {raw_text or '(no read)'}  conf={raw_conf:.2f}",
         GREEN if raw_ok else RED),
    ]
    left_panel = panel(left_lines, img)

    variants, _ = preprocess_plate_crop(img, quality=q)
    chosen_name = dbg.get("preprocessing_mode") or "original"
    chosen_img = next((v for n, v in variants if n == chosen_name), img)
    right_lines = [
        (f"preprocessing_mode = {chosen_name}", YELLOW),
        (f"candidates tried = {dbg.get('ocr_candidate_count')}", GRAY),
        (f"WITH adaptive pipeline: {text or '(no read)'}  conf={conf:.2f}",
         GREEN if final_ok else RED),
    ]
    right_panel = panel(right_lines, chosen_img)

    rows.append(hconcat_panels([left_panel, right_panel]))

grid = np.vstack(rows)

# Header banner
header_h = 70
header = np.full((header_h, grid.shape[1], 3), 15, dtype=np.uint8)
cv2.putText(header, "TrackX - Adaptive Plate Quality / Preprocessing (real OCR, real quality metrics)",
            (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
cv2.putText(header, f"Base crop: REAL saved plate crop, ground truth = {GROUND_TRUTH}. Degradations (blur/low-light/rain) are SYNTHETIC - applied to the real crop, no real rain/night footage available.",
            (12, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1, cv2.LINE_AA)
cv2.putText(header, "Left = raw OCR on the degraded crop directly. Right = TrackX's real adaptive pipeline (quality-aware preprocessing) on the same crop.",
            (12, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1, cv2.LINE_AA)

final = np.vstack([header, grid])
out_path = "/mnt/user-data/outputs/trackx_quality_preprocessing_demo.png"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
cv2.imwrite(out_path, final)
print("saved", out_path, final.shape)
