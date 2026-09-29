import re
import cv2
import numpy as np

# Graceful import handling for OCR engines.
# PaddleOCR is the only OCR engine actually used - see the PlateOCR
# docstring below for why LPRNet was removed from this live path.
PADDLEOCR_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PaddleOCR = None

# SIH26127 "Final Demo Hardening" audit (2026-09-10): the real, human-
# readable reason the LAST try_init_ocr() call returned None, or None if
# the last call succeeded (or none has run yet). This is a module-level
# side channel, not a change to try_init_ocr()'s existing (instance | None)
# return contract, so every existing caller keeps working identically -
# it exists purely so a caller that gets None back (e.g. backend health
# checks, the webcam-stream WebSocket's "ready" message) can report WHY,
# instead of collapsing a real, specific failure (package not installed vs.
# model-CDN unreachable vs. some other construction error) into a single
# opaque "unavailable" with no way for an operator to act on it.
LAST_OCR_INIT_ERROR = None

# Import canonical plate validator from plate_normalizer
from recognition.plate_normalizer import normalize_indian_plate
# Shared OCR-confusable character-pair table (also used for cross-camera
# fuzzy plate matching) - reused here so both places agree on what counts
# as a plausible OCR swap vs. a strange, unjustified one.
from recognition.plate_matcher import CONFUSABLE_PAIRS
from recognition.plate_quality import (
    assess_plate_quality, VERY_SMALL_CROP_MIN_HEIGHT, VERY_SMALL_CROP_MIN_WIDTH,
)


# SIH26127 screening-demo task ("FPS architecture"): auto-detect a real
# GPU-enabled PaddlePaddle install and pass use_gpu=True to PaddleOCR when
# one is actually usable, instead of hardcoding CPU. This never installs
# or assumes paddlepaddle-gpu - it only asks whichever paddle build is
# already installed whether it was compiled with CUDA support and whether
# a device is visible, and falls back to use_gpu=False (today's actual
# behavior, unchanged) otherwise. This project's own requirements.txt pins
# paddlepaddle==2.6.2 (the CPU wheel), so on an unmodified install this
# will honestly report False - it only turns on automatically if someone
# later swaps in a GPU build of paddlepaddle.
def _resolve_paddle_gpu() -> bool:
    try:
        import paddle
        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            print("[ocr_reader] GPU-enabled PaddlePaddle detected - using use_gpu=True")
            return True
    except Exception as e:
        print(f"[ocr_reader] Paddle GPU check failed ({e}) - using use_gpu=False (CPU)")
        return False
    print(
        "[ocr_reader] No GPU-enabled PaddlePaddle build available (this "
        "project's pinned paddlepaddle==2.6.2 is the CPU wheel, see "
        "requirements.txt) - using use_gpu=False (CPU)"
    )
    return False


def preprocess_plate_crop(plate_crop, quality=None, max_variants=4):
    """
    Condition-AWARE preprocessing: instead of unconditionally generating
    every possible variant (the old version of this function generated
    ~10-12 variants on every single call regardless of whether the crop
    needed any help at all - expensive, and not actually "adaptive" since
    every condition branch just kept appending to one big list that the
    caller then filtered against a hardcoded name list), this picks a
    SMALL, targeted set of variants based on assess_plate_quality()'s real
    measured condition flags for THIS crop - a decent crop gets "original"
    plus at most one general enhancement; a genuinely small/dark/blurry
    crop gets variants aimed specifically at that problem.

    Bug fix (SIH26127 OCR-correctness pass): the previous version of this
    function generated variants named "upscaled_2x_cubic"/"upscaled_2x_lanczos"
    etc., but the caller (PlateOCR._read_paddleocr's slow path) filtered
    for a variant literally named "upscaled_2x" - a name that was never
    produced, so upscaling silently never ran for small crops, exactly the
    condition it exists for. This version's variant names are exactly the
    names the caller now iterates (see _read_paddleocr), so there is no
    filter step left to go stale.

    Returns (variants, quality) where variants is a list of (name, image)
    tuples - "original" is always first - and quality is the
    assess_plate_quality() dict this selection was based on (so the caller
    can log/persist it without recomputing).
    """
    if plate_crop is None or plate_crop.size == 0:
        return [], assess_plate_quality(plate_crop)

    if quality is None:
        quality = assess_plate_quality(plate_crop)

    variants = [("original", plate_crop)]
    gray = None

    def _gray():
        nonlocal gray
        if gray is None:
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        return gray

    h, w = quality["height"], quality["width"]

    # Small crop -> upscaling is the single highest-value variant (OCR
    # models generally need a minimum character pixel height to work at
    # all). Lanczos tends to preserve edges slightly better than cubic for
    # text; used for very small crops where every pixel of sharpness
    # matters, cubic otherwise (cheaper).
    if quality["is_small"]:
        scale = 3 if (h < VERY_SMALL_CROP_MIN_HEIGHT or w < VERY_SMALL_CROP_MIN_WIDTH) else 2
        interp = cv2.INTER_LANCZOS4 if scale >= 3 else cv2.INTER_CUBIC
        upscaled = cv2.resize(plate_crop, (w * scale, h * scale), interpolation=interp)
        variants.append((f"upscaled_{scale}x", upscaled))

    if quality["is_low_light"]:
        clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(_gray())
        gamma_corrected = np.uint8(np.power(enhanced / 255.0, 1.5) * 255.0)
        variants.append(("low_light_clahe_gamma", cv2.cvtColor(gamma_corrected, cv2.COLOR_GRAY2BGR)))
    elif quality["is_low_contrast"]:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(_gray())
        variants.append(("clahe_contrast", cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)))

    if quality["is_blurry"]:
        gaussian = cv2.GaussianBlur(plate_crop, (0, 0), 2.0)
        unsharp = cv2.addWeighted(plate_crop, 1.5, gaussian, -0.5, 0)
        variants.append(("unsharp_mask", unsharp))

    # Good-quality crop with none of the above conditions triggered: still
    # give OCR one general-purpose enhanced variant as a fallback, per
    # "if quality is good: original + one enhanced variant".
    if len(variants) == 1:
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        variants.append(("sharpened", cv2.filter2D(plate_crop, -1, kernel)))

    return variants[:max_variants], quality


# SIH26127 "OCR MODEL OPTIMIZATION" pass (2026-09-09): PaddleOCR's DB text
# detector expands its raw (shrunk) text-region prediction back out by this
# factor before handing the box to the recognizer - a bigger value gives the
# recognizer a bit more margin around each character. A controlled sweep of
# 1.2/1.5(PaddleOCR default)/1.8/2.0/2.2/2.5/2.7/3.0 against the same 35
# gt-known real plate crops (script: /tmp/a3_config_sweep.py,
# /tmp/a3_unclip_extra.py) found a smooth, unimodal curve peaking at 2.5
# (21/35 exact match vs 17/35 at the 1.5 default - +4 samples, 0
# regressions), degrading on both sides (16/35 at 3.0) - the shape of a real
# effect (more recognition context up to a point, then background noise
# past it), not a lucky single value. Reproduced identically across repeat
# runs (deterministic on a fixed input). See
# docs/PART_A_OCR_MODEL_OPTIMIZATION_2026-09-09.md section A3 for the full
# sweep table and the full-pipeline (not just single-crop) validation this
# was checked against before being kept.
PADDLEOCR_DET_DB_UNCLIP_RATIO = 2.5


class PlateOCR:
    def __init__(self, lang="en"):
        self.ocr_engine = None
        self.engine_type = None
        self.lprnet = None

        # LPRNet is intentionally NOT used here. It requires a trained
        # Indian-plate checkpoint (models/lprnet_indian.pth) that this repo
        # has never shipped - models/README.md itself documents it as
        # "Required for Production... requires training". Without that
        # checkpoint it can only ever fall through to PaddleOCR below anyway
        # (see the git history of this file for the old try/fallback
        # branch), so keeping the LPRNet code path wired in here just adds a
        # second, permanently-unused OCR engine and import to reason about
        # for no real benefit. recognition/lprnet_ocr.py itself is left in
        # place (training scripts in detection/ can still target it later),
        # it's simply not imported/attempted from the live OCR path anymore.

        # PaddleOCR is the OCR engine actually used.
        if PADDLEOCR_AVAILABLE:
            try:
                # SIH26127 OOM hotfix (2026-09-29): use_angle_cls=True loads
                # a THIRD PaddleOCR model (the rotation classifier) on top of
                # the detection and recognition models it already needs -
                # real extra download + real extra RAM, and it exists to fix
                # upside-down/sideways text, which a vehicle-mounted ANPR
                # camera's plate crops essentially never are (plates aren't
                # photographed rotated 90-180 degrees in this dataset).
                # Dropping it was one of the two changes that got this app's
                # peak memory back under Render's free-tier 512MB limit
                # after an actual OOM kill (see backend/app/main.py's
                # get_model_status(trigger_load=...) for the other one) -
                # this isn't a guess, it's cutting a model this pipeline
                # doesn't need for its real inputs.
                self.ocr = PaddleOCR(
                    use_angle_cls=False, lang=lang,
                    det_db_unclip_ratio=PADDLEOCR_DET_DB_UNCLIP_RATIO,
                    use_gpu=_resolve_paddle_gpu(),
                )
                self.ocr_engine = self.ocr
                self.engine_type = "paddleocr"
                print(f"[ocr_reader] Using PaddleOCR engine (LPRNet unavailable)")
                return
            except Exception as e:
                print(f"[ocr_reader] PaddleOCR initialization failed: {e}")

        raise ImportError("No OCR engine available. Neither LPRNet nor PaddleOCR could be initialized.")

    def read(self, crop_img, return_debug=False):
        # NOTE: the actual OCR call below can raise; that's handled by the
        # caller (build_plate_fields in demo/visual_pipeline.py treats a
        # failed/absent PlateOCR instance as "OCR unavailable", never a
        # fabricated read). See try_init_ocr() for the construction-time
        # failure mode (SystemExit from PaddleOCR's own model download).
        #
        # return_debug=True (SIH26127 "Plate Quality-Aware Processing"):
        # also returns a third dict with the real measured quality metrics
        # for this crop and which preprocessing variant actually produced
        # the winning text - for persisting to the DB/API/annotated video
        # so a judge (or a developer) can see WHY a plate was hard to read,
        # not just that it was. Default is unchanged (text, conf) so every
        # existing caller keeps working exactly as before.
        if self.engine_type == "paddleocr":
            return self._read_paddleocr(crop_img, return_debug=return_debug)
        if return_debug:
            return None, 0.0, {"preprocessing_mode": "unavailable", "ocr_candidate_count": 0}
        return None, 0.0

    def _read_paddleocr(self, crop_img, return_debug=False):
        """
        Fast-path multi-pass OCR with PaddleOCR.
        Strategy: Try original first, only use multi-pass if confidence is low or format invalid.
        Enhanced with multi-factor scoring for better result selection.

        SIH26127 "Adaptive Multi-Frame ANPR Intelligence" pass: the slow
        path used to generate every preprocessing variant unconditionally
        and then filter by a hardcoded name list that didn't match what
        was actually generated (upscaled_2x was never produced - see
        preprocess_plate_crop()'s docstring) - so upscaling silently never
        ran. It now asks preprocess_plate_crop() for a small,
        condition-driven set of variants (already selected FOR this crop's
        actual measured quality) and just tries all of them - no second
        filter step to go stale again.
        """
        quality = assess_plate_quality(crop_img)

        def _debug(preprocessing_mode, candidate_count):
            return {
                "preprocessing_mode": preprocessing_mode,
                "ocr_candidate_count": candidate_count,
                "quality": quality,
            }

        # Fast path: Try original crop first
        # cls=False matches use_angle_cls=False at construction above - no
        # angle-classifier model was loaded, so asking for one here would be
        # inconsistent with what was actually built.
        result = self.ocr.ocr(crop_img, cls=False)

        if result and result[0]:
            texts = []
            confs = []
            for line in result[0]:
                texts.append(line[1][0])
                confs.append(line[1][1])

            text = "".join(texts)
            text = text.upper()
            text = re.sub(r"[^A-Z0-9]", "", text)

            # Apply Indian plate format validation. normalize_indian_plate()
            # (recognition/plate_normalizer.py) both validates AND corrects
            # OCR-confusable characters (0/O, 1/I, ...) and strips the "IND"
            # country-marker artifact - strictly better than a bare regex
            # check, and it was already imported at module level. The old
            # call here was to validate_indian_plate_format(), a function
            # that does not exist anywhere in this codebase; every
            # PaddleOCR-fallback read hit a NameError before this fix (see
            # docs/CLAUDE_PHASE0_AUDIT.md follow-up notes).
            normalized_text, is_valid_format = normalize_indian_plate(text)

            avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0

            # Adaptive multi-pass decision - now also triggered by the real
            # measured quality flags (blurry/low-light/low-contrast), not
            # just size and confidence, so a poor-quality-but-accidentally-
            # confident first read still gets a second, condition-targeted
            # opinion.
            should_use_multipass = quality["is_small"] or quality["is_blurry"] or quality["is_low_light"]

            if avg_conf < 0.8:
                should_use_multipass = True
            if not is_valid_format:
                should_use_multipass = True

            # Fast path success: high confidence AND valid format AND good image quality
            if not should_use_multipass and ((avg_conf >= 0.85 and is_valid_format) or avg_conf >= 0.90):
                if return_debug:
                    return normalized_text, avg_conf, _debug("original", 1)
                return normalized_text, avg_conf

        # Slow path: Try multi-pass for low-confidence or invalid format results
        candidates = []
        variants, quality = preprocess_plate_crop(crop_img, quality=quality)

        for variant_name, variant_crop in variants:
            try:
                result = self.ocr.ocr(variant_crop, cls=False)  # matches use_angle_cls=False above

                if result and result[0]:
                    texts = []
                    confs = []
                    for line in result[0]:
                        texts.append(line[1][0])
                        confs.append(line[1][1])

                    text = "".join(texts)
                    text = text.upper()
                    text = re.sub(r"[^A-Z0-9]", "", text)

                    # Apply Indian plate format validation (see fast-path
                    # comment above for why normalize_indian_plate() is used
                    # instead of the previously-undefined
                    # validate_indian_plate_format()).
                    normalized_text, is_valid_format = normalize_indian_plate(text)

                    avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0

                    if text and len(text) >= 4:
                        # Enhanced multi-factor scoring
                        base_score = avg_conf

                        # Format bonus
                        if is_valid_format:
                            base_score *= 1.2

                        # Length penalty for unrealistic lengths
                        length = len(normalized_text)
                        if 8 <= length <= 10:
                            base_score *= 1.1
                        elif length < 6 or length > 12:
                            base_score *= 0.8

                        # Character distribution bonus (reasonable mix of letters and digits)
                        letter_count = sum(1 for c in normalized_text if c.isalpha())
                        digit_count = sum(1 for c in normalized_text if c.isdigit())
                        if 2 <= letter_count <= 5 and 4 <= digit_count <= 6:
                            base_score *= 1.05

                        candidates.append({
                            "text": normalized_text,
                            "confidence": avg_conf,
                            "is_valid_format": is_valid_format,
                            "variant": variant_name,
                            "enhanced_score": base_score
                        })
            except Exception:
                continue

        if not candidates:
            if return_debug:
                return None, 0.0, _debug(None, len(variants))
            return None, 0.0

        # Select best candidate: prioritize enhanced score, then valid format, then confidence
        valid_format = [c for c in candidates if c["is_valid_format"]]
        invalid_format = [c for c in candidates if not c["is_valid_format"]]

        if valid_format:
            best_candidate = max(valid_format, key=lambda x: x["enhanced_score"])
        else:
            best_candidate = max(invalid_format, key=lambda x: x["enhanced_score"])

        if return_debug:
            return best_candidate["text"], best_candidate["confidence"], _debug(best_candidate["variant"], len(variants))
        return best_candidate["text"], best_candidate["confidence"]


def try_init_ocr(lang="en"):
    """
    Attempts to construct a PlateOCR instance, and never lets that attempt
    take the calling process down.

    Real, observed failure mode: PaddleOCR's constructor downloads its
    detection/recognition/classification models from its own CDN
    (bj.bcebos.com) the first time it's instantiated. If that host isn't
    reachable (offline sandbox, restrictive network policy, etc.),
    PaddleOCR's own internal code calls sys.exit() - which raises
    SystemExit, NOT a normal Exception. A bare `except Exception` around
    PlateOCR() would NOT catch that, so the whole process (including a
    running Streamlit app) would die with no error surfaced to the user.

    Catching BaseException-level SystemExit is deliberately scoped to just
    this one call (nowhere else in this codebase does that) so this one
    known-flaky construction path degrades to "OCR unavailable" instead of
    silently killing the run. Vehicle detection and everything else keep
    working; only plate text reading is affected, and that is reported
    honestly via plate_status="unavailable" (see
    demo/visual_pipeline.py:build_plate_fields), never faked.

    Returns a PlateOCR instance, or None if it could not be constructed.
    See LAST_OCR_INIT_ERROR (module-level, above) for the real reason when
    None is returned.
    """
    global LAST_OCR_INIT_ERROR
    if not PADDLEOCR_AVAILABLE:
        LAST_OCR_INIT_ERROR = ("The 'paddleocr' Python package is not installed in this "
                                "environment (import paddleocr failed). Install it with "
                                "'pip install paddleocr' in the same Python/venv the backend "
                                "runs from.")
        print(f"[ocr_reader] PaddleOCR is not installed - OCR will be "
              f"reported as unavailable for this run; vehicle detection is unaffected.")
        return None

    try:
        # Construction is the contract of this helper. Do not perform an
        # artificial post-construction validation here: tests, adapters and
        # future OCR-compatible implementations may return proxy objects
        # that intentionally do not expose the internal ``ocr`` attribute.
        # Actual usability is verified naturally when PlateOCR.read() is called.
        ocr_instance = PlateOCR(lang=lang)
        LAST_OCR_INIT_ERROR = None
        print(f"[ocr_reader] OCR initialized successfully using {ocr_instance.engine_type} for language '{lang}'")
        return ocr_instance
    except SystemExit as e:
        LAST_OCR_INIT_ERROR = (f"PaddleOCR's own constructor called sys.exit(code={e.code}) - "
                                f"most likely it could not reach its model-weight CDN "
                                f"(bj.bcebos.com) to download the PP-OCRv4 detection/"
                                f"recognition/classification models on first use, and no "
                                f"already-downloaded copy was found in ~/.paddleocr. Either "
                                f"restore network access to that host once (so PaddleOCR can "
                                f"download and cache its models), or pre-populate ~/.paddleocr "
                                f"from a machine that already has them.")
        print(f"[ocr_reader] OCR failed to initialize (it called sys.exit "
              f"internally, exit code {e.code}) - most likely it could not reach "
              f"its model-weight CDN. OCR will be reported as unavailable for "
              f"this run; vehicle detection is unaffected.")
        return None
    except Exception as e:
        LAST_OCR_INIT_ERROR = f"{type(e).__name__}: {e}"
        print(f"[ocr_reader] OCR failed to initialize ({type(e).__name__}: {e}) - "
              f"OCR will be reported as unavailable for this run; vehicle detection "
              f"is unaffected.")
        return None


if __name__ == "__main__":
    import sys
    import cv2

    if len(sys.argv) < 2:
        print("usage: python ocr_reader.py <cropped_plate.jpg>")
        sys.exit(1)

    img = cv2.imread(sys.argv[1])
    ocr = PlateOCR()
    text, conf = ocr.read(img)
    print(text, conf)


# A single position's positional-vote winner is only allowed to override
# the whole-string majority's character at that position when it holds at
# least this fraction of that position's total confidence weight - i.e. a
# character that only showed up once, even with high individual
# confidence, cannot flip a position on its own (SIH26127 requirement:
# "Never blindly replace characters").
POSITION_DOMINANCE_RATIO = 0.60

# Per-character positional voting is only meaningful with at least this
# many same-length readings to vote across - below this, there isn't
# enough independent evidence to trust a position-by-position comparison
# over the plain whole-string majority.
MIN_SAME_LENGTH_READINGS_FOR_POSITIONAL_VOTE = 3

# Number of independent readings needed before a vote's confidence is
# allowed to reach its full value - fewer readings than this get their
# confidence proportionally discounted, since a handful of readings (even
# if they all agree) is weaker evidence than a track that was read many
# times. See the sample_size_factor comment below.
SAMPLE_SIZE_FULL_CONFIDENCE = 6

# SIH26127 fragment-clustering fix (see
# docs/CROSS_TRACK_CONTAMINATION_INVESTIGATION.md section 8): a track's
# genuinely-correct OCR readings can legitimately come out at different
# lengths across frames (a partially-truncated crop on one frame, a
# full-length crop on another) - the stage-1 exact-string vote below used
# to treat these as unrelated candidates and split their vote weight
# instead of pooling it, which let an unrelated but internally-consistent
# WRONG reading win outright even when it was actually rarer supporting
# evidence overall. A reading shorter than this is not merged into any
# cluster no matter how well it matches - a very short fragment (e.g. 2-3
# characters) is too likely to coincidentally be a prefix/suffix of a
# completely different, unrelated plate to safely cluster.
MIN_FRAGMENT_CLUSTER_LEN = 4


def _is_fuzzy_fragment(shorter, longer):
    """
    True if `shorter` is a plausible truncated reading of `longer` - i.e.
    `shorter` lines up, character-for-character, against either the first
    or the last len(shorter) characters of `longer`, where "lines up"
    allows an exact match OR a known OCR-confusable substitution
    (recognition.plate_matcher.CONFUSABLE_PAIRS - the same confusable-pair
    table already used by the positional vote above and by
    plate_matcher._levenshtein(), never an arbitrary character swap).

    This is deliberately NOT a general similarity/edit-distance check
    (plate_matcher.plate_similarity() was considered and rejected for this
    - a short fragment like "S3664" scores far below any similarity
    threshold against "UP14FS3664" simply because of the length gap, even
    though it's a perfect suffix match). Only prefix/suffix containment
    is trusted here, since that's the actual shape a truncated crop
    produces (missing characters off one end, not scattered gaps).
    """
    if len(shorter) < MIN_FRAGMENT_CLUSTER_LEN or len(shorter) >= len(longer):
        return False

    def _chars_compatible(a, b):
        return a == b or frozenset((a, b)) in CONFUSABLE_PAIRS

    prefix_match = all(
        _chars_compatible(a, b) for a, b in zip(shorter, longer[: len(shorter)])
    )
    suffix_match = all(
        _chars_compatible(a, b) for a, b in zip(shorter, longer[-len(shorter):])
    )
    return prefix_match or suffix_match


def vote_plate_text(readings, return_evidence=False):
    """
    combines multiple OCR readings of the SAME physical plate (e.g. from
    consecutive video frames while a vehicle is in view) into one best
    guess, instead of trusting a single frame's OCR result.

    readings: list of (text, confidence) tuples, e.g.
        [("TN38AB1234", 0.91), ("TN38A81234", 0.62), ("TN38AB1234", 0.88)]

    requires per-vehicle frame tracking to actually group readings together
    (e.g. ByteTrack/BoT-SORT assigning a track id across frames) - this
    function assumes that grouping has already happened elsewhere and you're
    just handing it the readings for one tracked vehicle.

    SIH26127 OCR-correctness pass (this function was previously PLAIN
    whole-string confidence-weighted frequency voting only - "a result
    occurring more frequently does not automatically mean it is correct"
    was flagged explicitly because that alone can't fix a same-type
    character confusion like 6<->8 or M<->H: if 3 frames read
    "KA02MN1826" and 2 frames read "KA02MN1828", frequency voting picks
    the more common string even if that's actually the wrong one at that
    single position). This is now a two-stage vote:

      1. whole-string frequency vote (as before) - the safe default.
      2. confidence-weighted PER-CHARACTER positional vote among readings
         that share the majority string length - for each character
         position, whichever character holds the confidence-weighted
         majority at THAT position wins. A position's positional-vote
         winner is only allowed to override the frequency-vote's
         character there if (a) the two characters are a known
         OCR-confusable pair (recognition.plate_matcher.CONFUSABLE_PAIRS -
         "confidence + ... surrounding characters" -> only plausible
         swaps are ever considered, never an arbitrary substitution) and
         (b) that position's winner holds >= POSITION_DOMINANCE_RATIO of
         the confidence weight seen at that position ("confidence +
         position" - never a single stray high-confidence misread
         flipping a position on its own). Every other position is left
         exactly as the frequency vote had it - this is a set of
         independent, individually-justified per-position corrections,
         not a wholesale re-vote or a forced format fit (normalize_indian_plate()
         remains the only format-aware step, and it runs on the OUTPUT of
         this function, not the other way around).

    Confidence: no longer just "average confidence of whatever text
    happened to win" - that let a small, coincidental cluster of
    high-individual-confidence readings look like a settled result even
    when most of the track's readings actually disagreed (this was found
    to actively hurt accuracy on OCR_ALWAYS_ATTEMPTS/early-stop sampling -
    see docs/PERFORMANCE_PROFILE.md). Confidence is now the winning
    reading's average confidence scaled down by how much of the TOTAL
    evidence actually agreed with it (agreement_ratio) - a text only 2 of
    8 total readings support is reported at meaningfully lower confidence
    than one 7 of 8 readings support, even if the individual confidences
    are similar.

    Raw OCR text is not altered by anything upstream of this function and
    the winning text returned here is still raw OCR text (uppercase/clean
    -up, if any, happens in the OCR engine itself) - normalize_indian_plate()
    is applied separately by the caller, keeping raw vs normalized text
    distinct per SIH26127 requirement #9.

    returns: (best_text, combined_confidence), or with return_evidence=True:
        (best_text, combined_confidence, evidence) where evidence is a
        dict describing what the vote actually saw and decided - reading
        count, per-text tally, majority length, and any per-position
        corrections applied - intended for the accuracy report / manual
        inspection, not for any runtime decision.
    """
    from collections import defaultdict

    def _empty():
        return (None, 0.0, {}) if return_evidence else (None, 0.0)

    if not readings:
        return _empty()

    readings = [(t, c) for (t, c) in readings if t]
    if not readings:
        return _empty()

    # ---- stage 0: fragment clustering. Before the frequency vote, merge
    # any reading that is a plausible truncated fragment of a LONGER
    # reading also present in this track's evidence into that longer
    # reading's bucket, so a track's real, correct plate doesn't lose to
    # an unrelated wrong-but-consistent reading purely because its own
    # correct evidence was split across several different crop lengths.
    # See docs/CROSS_TRACK_CONTAMINATION_INVESTIGATION.md section 8 and
    # MIN_FRAGMENT_CLUSTER_LEN / _is_fuzzy_fragment() above. ----
    distinct_texts = sorted(set(t for t, _c in readings), key=len, reverse=True)
    merge_target = {}
    for shorter in distinct_texts:
        best_match = None
        for longer in distinct_texts:
            if len(longer) <= len(shorter):
                continue
            if _is_fuzzy_fragment(shorter, longer):
                # distinct_texts is longest-first, so the first match found
                # is already the longest candidate - no need to compare.
                best_match = longer
                break
        if best_match is not None:
            merge_target[shorter] = best_match

    def _resolve(text):
        # follow shorter -> longer chains to their final target. Each hop
        # strictly increases string length, so this always terminates.
        seen = set()
        while text in merge_target and text not in seen:
            seen.add(text)
            text = merge_target[text]
        return text

    # ---- stage 1: whole-string confidence-weighted frequency vote (the
    # long-standing, safe default result), now operating on fragment-
    # resolved text so a track's correct-but-differently-truncated
    # readings pool their vote weight instead of splitting it. ----
    votes = defaultdict(float)
    counts = defaultdict(int)
    for text, conf in readings:
        resolved = _resolve(text)
        votes[resolved] += conf
        counts[resolved] += 1

    total_weight = sum(votes.values())
    freq_text = max(votes, key=votes.get)
    freq_group_weight = votes[freq_text]
    freq_group_count = counts[freq_text]

    # ---- stage 2: confidence-weighted per-character positional vote,
    # restricted to the length that carries the most total confidence
    # weight. A reading of a different length is missing/adding a whole
    # character (e.g. a clipped crop) - not comparable position-by-position
    # to the majority length, so it only participates in stage 1. ----
    length_weight = defaultdict(float)
    for text, conf in readings:
        length_weight[len(text)] += conf
    majority_len = max(length_weight, key=length_weight.get)
    same_len_readings = [(t, c) for (t, c) in readings if len(t) == majority_len]

    best_text = freq_text
    corrections = []

    if (
        len(same_len_readings) >= MIN_SAME_LENGTH_READINGS_FOR_POSITIONAL_VOTE
        and majority_len == len(freq_text)
    ):
        position_votes = [defaultdict(float) for _ in range(majority_len)]
        for text, conf in same_len_readings:
            for i, ch in enumerate(text):
                position_votes[i][ch] += conf

        candidate_chars = list(freq_text)
        for i, freq_ch in enumerate(freq_text):
            pv = position_votes[i]
            if not pv:
                continue
            pos_best_ch = max(pv, key=pv.get)
            if pos_best_ch == freq_ch:
                continue
            pos_total = sum(pv.values())
            dominance = (pv[pos_best_ch] / pos_total) if pos_total > 0 else 0.0
            if dominance >= POSITION_DOMINANCE_RATIO and frozenset((pos_best_ch, freq_ch)) in CONFUSABLE_PAIRS:
                candidate_chars[i] = pos_best_ch
                corrections.append({
                    "position": i, "from": freq_ch, "to": pos_best_ch,
                    "dominance": round(dominance, 3),
                })

        corrected_text = "".join(candidate_chars)
        if corrected_text != freq_text:
            best_text = corrected_text

    # ---- confidence: scaled by real agreement across ALL readings, not
    # just the average confidence of whichever text happened to win, AND
    # by how much total evidence exists at all. Agreement ratio alone
    # isn't enough - 2 readings that both happen to agree still isn't much
    # independent evidence (this was found during OCR-sampling perf
    # testing: a track with only ~4 readings that all coincidentally
    # agreed on a WRONG text scored as confidently as a track with 6+
    # readings that genuinely converged on the right one - see
    # docs/PERFORMANCE_PROFILE.md). sample_size_factor ramps from 0.7 (a
    # single reading) up to 1.0 once at least SAMPLE_SIZE_FULL_CONFIDENCE
    # independent readings exist. ----
    agreement_ratio = (freq_group_weight / total_weight) if total_weight > 0 else 0.0
    avg_conf_of_agreeing = freq_group_weight / freq_group_count
    sample_size_factor = 0.7 + 0.3 * min(1.0, len(readings) / SAMPLE_SIZE_FULL_CONFIDENCE)
    combined_confidence = round(
        avg_conf_of_agreeing * (0.5 + 0.5 * agreement_ratio) * sample_size_factor, 3
    )

    if not return_evidence:
        return best_text, combined_confidence

    evidence = {
        "num_readings": len(readings),
        "frequency_winner": freq_text,
        "frequency_winner_count": freq_group_count,
        "agreement_ratio": round(agreement_ratio, 3),
        "majority_length": majority_len,
        "positional_readings_used": len(same_len_readings),
        "corrections_applied": corrections,
        "final_text": best_text,
        "final_confidence": combined_confidence,
        "all_readings": [{"text": t, "confidence": c} for t, c in readings],
    }
    return best_text, combined_confidence, evidence
