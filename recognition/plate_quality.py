"""
plate_quality.py

SIH26127 "Adaptive Multi-Frame ANPR Intelligence" - Plate Quality
Assessment module.

This is a single, reusable place to answer "how good is this plate crop,
and what's actually wrong with it" - blur, brightness, contrast,
resolution, aspect ratio. Two things previously computed this same math
ad hoc and threw it away:

  - recognition/ocr_reader.py's preprocess_plate_crop() already computed
    brightness/contrast/blur internally just to decide which preprocessing
    variants to generate, then discarded the numbers.
  - nothing recorded WHY a plate was hard to read, or which preprocessing
    strategy was actually used, anywhere in the DB/API/annotated video.

assess_plate_quality() is that shared source of truth: preprocess_plate_crop()
now calls it instead of recomputing the same metrics, and pipeline.py calls
it (via PlateOCR.read(..., return_debug=True), see ocr_reader.py) to
persist quality_score/blur_score/brightness_score/contrast_score and the
condition flags that drove preprocessing selection - real numbers from the
actual crop, not an invented "AI quality score".
"""

import cv2
import numpy as np

# Thresholds below are the same ones preprocess_plate_crop() used
# informally before this module existed - kept identical so refactoring
# to call assess_plate_quality() doesn't change existing preprocessing
# selection behavior, just gives it a name and makes the numbers visible.
BLUR_VARIANCE_THRESHOLD = 100.0   # Laplacian variance below this = blurry
LOW_LIGHT_BRIGHTNESS_THRESHOLD = 80.0    # mean pixel value below this = low light
LOW_CONTRAST_STD_THRESHOLD = 50.0        # stddev below this = low contrast
SMALL_CROP_MIN_HEIGHT = 80
SMALL_CROP_MIN_WIDTH = 200
VERY_SMALL_CROP_MIN_HEIGHT = 40
VERY_SMALL_CROP_MIN_WIDTH = 100


def assess_plate_quality(plate_crop):
    """
    Computes real, measured visual-quality metrics for one plate crop.
    Returns a dict (never raises on a bad/empty crop - returns a
    zeroed-out, all-flags-true "unusable" dict instead, so callers can
    treat that uniformly rather than special-casing None).

    Fields:
        height, width          - actual crop dimensions (px)
        aspect_ratio            - width / height (0.0 if height is 0)
        brightness               - mean grayscale pixel value (0-255)
        contrast                 - grayscale pixel stddev (0-255-ish)
        blur_score                - Laplacian variance (higher = sharper;
                                     unbounded, typically 0-a few thousand
                                     for plate-sized crops)
        is_low_light, is_low_contrast, is_blurry, is_small - booleans
        quality_score             - single 0.0-1.0 summary, NOT used for
                                     any pass/fail gate on its own (per
                                     SIH26127 requirement: quality informs
                                     PROCESSING choice, it does not itself
                                     decide whether a plate is "verified" -
                                     that remains vote_plate_text()'s job,
                                     which also weighs actual OCR
                                     confidence and cross-frame agreement).
                                     Computed as an unweighted average of
                                     three independently-normalized
                                     sub-scores (sharpness, brightness
                                     closeness-to-mid-range, contrast) -
                                     documented here, not a black box.
    """
    empty = {
        "height": 0, "width": 0, "aspect_ratio": 0.0,
        "brightness": 0.0, "contrast": 0.0, "blur_score": 0.0,
        "is_low_light": True, "is_low_contrast": True, "is_blurry": True,
        "is_small": True, "quality_score": 0.0,
    }
    if plate_crop is None or plate_crop.size == 0:
        return empty

    h, w = plate_crop.shape[:2]
    if h == 0 or w == 0:
        return empty

    gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY) if plate_crop.ndim == 3 else plate_crop
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    is_blurry = blur_score < BLUR_VARIANCE_THRESHOLD
    is_low_light = brightness < LOW_LIGHT_BRIGHTNESS_THRESHOLD
    is_low_contrast = contrast < LOW_CONTRAST_STD_THRESHOLD
    is_small = h < SMALL_CROP_MIN_HEIGHT or w < SMALL_CROP_MIN_WIDTH

    # Three independent 0-1 sub-scores, unweighted average - documented,
    # not a mystery formula. Each saturates rather than being unbounded.
    sharpness_score = min(1.0, blur_score / (BLUR_VARIANCE_THRESHOLD * 3))
    # brightness is best around the middle of the 0-255 range; penalize
    # both too-dark and too-bright/washed-out crops symmetrically
    brightness_score = 1.0 - min(1.0, abs(brightness - 127.5) / 127.5)
    contrast_score = min(1.0, contrast / (LOW_CONTRAST_STD_THRESHOLD * 2))
    quality_score = round((sharpness_score + brightness_score + contrast_score) / 3.0, 3)

    return {
        "height": h, "width": w,
        "aspect_ratio": round(w / h, 3) if h > 0 else 0.0,
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "blur_score": round(blur_score, 2),
        "is_low_light": is_low_light,
        "is_low_contrast": is_low_contrast,
        "is_blurry": is_blurry,
        "is_small": is_small,
        "quality_score": quality_score,
    }
