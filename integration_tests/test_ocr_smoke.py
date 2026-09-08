"""
integration_tests/test_ocr_smoke.py

Deterministic real-OCR smoke test for recognition/ocr_reader.py's PlateOCR
wrapper (the class the actual pipeline uses, via try_init_ocr()) - not a
mock, not a stub, and not dependent on whatever plate-crop files happen to
be lying around in outputs/ (integration_tests/test_real_ocr.py does that,
non-deterministically, and only exercises raw PaddleOCR directly, not this
repo's own wrapper).

What this test does:
1. Renders a plate image with FIXED, KNOWN text at test time (no random
   seed dependency beyond a fixed one for the "noisy" variant, no
   committed binary fixture to rot).
2. Calls recognition.ocr_reader.try_init_ocr() - the exact function
   demo/visual_pipeline.py calls in production.
3. Reads the image through PlateOCR.read() - the exact method the
   pipeline calls per-frame.
4. Asserts the recognized text, not just "did it return something".

This intentionally targets the bug found and fixed 2026-09-07: both
PaddleOCR code paths in _read_paddleocr() called an undefined function
(validate_indian_plate_format), so every PaddleOCR-backed read raised
NameError before ever reaching a caller. That bug would have shipped
silently, because no existing test exercised PlateOCR.read() with
PaddleOCR actually selected as the engine - if this test regresses the
same way, it will fail loudly instead.

Skips (does not fail) when no OCR engine can actually be constructed in
this environment - e.g. neither paddleocr nor its cached model weights
are present. That is an environment gap, not a code bug, and is reported
as a skip with a clear reason, same convention as the rest of this suite.
"""
import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

GROUND_TRUTH_PLATE = "TN38AB1234"


def _render_plate(text, degrade=False):
    """Render `text` on a white canvas sized to fit it exactly (a canvas
    narrower than the text would silently clip the last characters - a
    real mistake made and caught while writing this test)."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thickness = 2.2, 6
    (text_w, text_h), _ = cv2.getTextSize(text, font, scale, thickness)
    w, h = text_w + 60, text_h + 70
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    cv2.putText(img, text, (25, h - 35), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)

    if degrade:
        img = cv2.GaussianBlur(img, (3, 3), 0.8)
        noise = np.random.default_rng(0).normal(0, 8, img.shape).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return img


class TestOCRSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Other unit-test files in this suite (tests/test_day4_plate_crop.py
        # and siblings) stub sys.modules["paddleocr"] with a fake class for
        # their own fast, offline unit tests. recognition/ocr_reader.py does
        # `from paddleocr import PaddleOCR` at IMPORT time, so whichever
        # test file's import happens first in the whole pytest session
        # decides - permanently, for the rest of the process - whether that
        # name is bound to the real class or the fake one; importing again
        # later does not undo an already-cached binding. Force a clean, real
        # re-import here so this test exercises real OCR regardless of
        # collection order, instead of silently skipping every time it
        # happens to run after one of those files.
        sys.modules.pop("paddleocr", None)
        sys.modules.pop("recognition.ocr_reader", None)
        from recognition.ocr_reader import try_init_ocr

        cls.ocr = try_init_ocr(lang="en")
        if cls.ocr is None:
            raise unittest.SkipTest(
                "No OCR engine could be constructed (neither LPRNet weights nor a "
                "usable PaddleOCR install/cache are present in this environment) - "
                "see recognition/ocr_reader.py try_init_ocr() and models/README.md."
            )

    def test_clean_plate_is_read_correctly(self):
        img = _render_plate(GROUND_TRUTH_PLATE, degrade=False)
        text, confidence = self.ocr.read(img)
        self.assertEqual(text, GROUND_TRUTH_PLATE)
        self.assertGreater(confidence, 0.5)

    def test_degraded_plate_is_still_read_correctly(self):
        """Gaussian blur + additive noise - a mild stand-in for a real
        camera capture, not a claim about all-weather/all-angle accuracy."""
        img = _render_plate(GROUND_TRUTH_PLATE, degrade=True)
        text, confidence = self.ocr.read(img)
        self.assertEqual(text, GROUND_TRUTH_PLATE)
        self.assertGreater(confidence, 0.5)


if __name__ == "__main__":
    unittest.main()
