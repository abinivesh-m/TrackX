import re
import cv2
import numpy as np

# Graceful import handling for OCR engines.
# Final OCR engines: LPRNet (primary) and PaddleOCR (secondary) only.
PADDLEOCR_AVAILABLE = False
LPRNET_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PaddleOCR = None

try:
    from recognition.lprnet_ocr import LPRNetOCR, try_init_lprnet
    LPRNET_AVAILABLE = True
except ImportError:
    LPRNetOCR = None
    try_init_lprnet = None

# Import canonical plate validator from plate_normalizer
from recognition.plate_normalizer import normalize_indian_plate


def preprocess_plate_crop(plate_crop):
    """
    Apply adaptive preprocessing to improve OCR on challenging plate crops.
    
    Enhanced with condition-specific preprocessing for:
    - Daylight/low-light conditions
    - Blurred images
    - Angled/perspective-distorted plates
    - Various weather conditions
    
    Returns a list of processed variants optimized for different conditions.
    """
    variants = []
    
    if plate_crop is None or plate_crop.size == 0:
        return variants
    
    # Always include the original
    variants.append(("original", plate_crop))
    
    h, w = plate_crop.shape[:2]
    
    # Analyze image conditions
    gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    contrast = np.std(gray)
    
    # Detect blur using Laplacian variance
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_blurry = laplacian_var < 100  # Threshold for blur detection
    
    # Detect low light
    is_low_light = brightness < 80
    
    # Detect low contrast
    is_low_contrast = contrast < 50
    
    # Upscale small crops more aggressively
    if h < 80 or w < 200:
        # 2x upscale with different interpolation methods
        h_2x, w_2x = h * 2, w * 2
        upscaled_2x_cubic = cv2.resize(plate_crop, (w_2x, h_2x), interpolation=cv2.INTER_CUBIC)
        variants.append(("upscaled_2x_cubic", upscaled_2x_cubic))
        
        upscaled_2x_lanczos = cv2.resize(plate_crop, (w_2x, h_2x), interpolation=cv2.INTER_LANCZOS4)
        variants.append(("upscaled_2x_lanczos", upscaled_2x_lanczos))
        
        # 3x upscale
        h_3x, w_3x = h * 3, w * 3
        upscaled_3x = cv2.resize(plate_crop, (w_3x, h_3x), interpolation=cv2.INTER_CUBIC)
        variants.append(("upscaled_3x", upscaled_3x))
        
        # 4x upscale for very small crops
        if h < 40 or w < 100:
            h_4x, w_4x = h * 4, w * 4
            upscaled_4x = cv2.resize(plate_crop, (w_4x, h_4x), interpolation=cv2.INTER_CUBIC)
            variants.append(("upscaled_4x", upscaled_4x))
    
    # Adaptive contrast enhancement based on lighting conditions
    if is_low_light:
        # Aggressive contrast enhancement for low light
        clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)
        # Gamma correction for low light
        gamma = 1.5
        gamma_corrected = np.power(enhanced / 255.0, gamma) * 255.0
        gamma_corrected = np.uint8(gamma_corrected)
        enhanced_bgr = cv2.cvtColor(gamma_corrected, cv2.COLOR_GRAY2BGR)
        variants.append(("low_light_enhanced", enhanced_bgr))
    else:
        # Standard contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        variants.append(("enhanced_contrast", enhanced_bgr))
    
    # Blur-specific preprocessing
    if is_blurry:
        # Sharpening with stronger kernel for blurry images
        kernel_sharp = np.array([[-2, -2, -2],
                                [-2, 17, -2],
                                [-2, -2, -2]])
        sharpened_strong = cv2.filter2D(plate_crop, -1, kernel_sharp)
        variants.append(("sharpened_strong", sharpened_strong))
        
        # Unsharp masking
        gaussian = cv2.GaussianBlur(plate_crop, (0, 0), 2.0)
        unsharp_mask = cv2.addWeighted(plate_crop, 1.5, gaussian, -0.5, 0)
        variants.append(("unsharp_mask", unsharp_mask))
    else:
        # Standard sharpening
        kernel = np.array([[-1, -1, -1],
                           [-1,  9, -1],
                           [-1, -1, -1]])
        sharpened = cv2.filter2D(plate_crop, -1, kernel)
        variants.append(("sharpened", sharpened))
    
    # Denoising (helpful for weather conditions like rain/snow)
    denoised = cv2.fastNlMeansDenoisingColored(plate_crop, None, 10, 10, 7, 21)
    variants.append(("denoised", denoised))
    
    # Adaptive thresholding for different contrast conditions
    if is_low_contrast:
        # More aggressive thresholding for low contrast
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 15, 4)
    else:
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
    adaptive_bgr = cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR)
    variants.append(("adaptive_threshold", adaptive_bgr))
    
    # Morphological operations for text enhancement
    kernel_morph = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morph = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel_morph)
    morph_bgr = cv2.cvtColor(morph, cv2.COLOR_GRAY2BGR)
    variants.append(("morphological", morph_bgr))
    
    # Gaussian blur + OTSU threshold (good for varying lighting)
    gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, blur_thresh = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    blur_thresh_bgr = cv2.cvtColor(blur_thresh, cv2.COLOR_GRAY2BGR)
    variants.append(("blur_threshold", blur_thresh_bgr))
    
    # Edge enhancement for poorly defined characters
    edges = cv2.Canny(gray, 100, 200)
    edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    variants.append(("edge_enhanced", edges_bgr))
    
    return variants


class PlateOCR:
    def __init__(self, lang="en"):
        self.ocr_engine = None
        self.engine_type = None
        
        # Try LPRNet first for Indian plates (highest accuracy potential)
        if LPRNET_AVAILABLE:
            try:
                model_path = "models/lprnet_indian.pth"  # Path to trained Indian LPRNet weights
                self.lprnet = try_init_lprnet(model_path)
                # Only trust LPRNet when a real trained weight file was
                # loaded. Without weights it returns garbage reads at a fake
                # 0.9 confidence, which silently destroys OCR accuracy.
                if self.lprnet and getattr(self.lprnet, "model_loaded", False):
                    self.ocr_engine = self.lprnet
                    self.engine_type = "lprnet"
                    print(f"[ocr_reader] Using LPRNet engine for Indian plates")
                    return
                if self.lprnet is not None and self.lprnet.model is None:
                    print("[ocr_reader] LPRNet weights not available - falling back to a real OCR engine")
                self.lprnet = None
            except Exception as e:
                print(f"[ocr_reader] LPRNet initialization failed: {e}")
                self.lprnet = None
        
        # Fallback to PaddleOCR
        if PADDLEOCR_AVAILABLE:
            try:
                self.ocr = PaddleOCR(use_angle_cls=True, lang=lang)
                self.ocr_engine = self.ocr
                self.engine_type = "paddleocr"
                print(f"[ocr_reader] Using PaddleOCR engine (LPRNet unavailable)")
                return
            except Exception as e:
                print(f"[ocr_reader] PaddleOCR initialization failed: {e}")
        
        raise ImportError("No OCR engine available. Neither LPRNet nor PaddleOCR could be initialized.")

    def read(self, crop_img):
        # NOTE: the actual OCR call below can raise; that's handled by the
        # caller (build_plate_fields in demo/visual_pipeline.py treats a
        # failed/absent PlateOCR instance as "OCR unavailable", never a
        # fabricated read). See try_init_ocr() for the construction-time
        # failure mode (SystemExit from PaddleOCR's own model download).
        
        if self.engine_type == "lprnet":
            return self._read_lprnet(crop_img)
        elif self.engine_type == "paddleocr":
            return self._read_paddleocr(crop_img)
        else:
            return None, 0.0
    
    def _read_lprnet(self, crop_img):
        """
        LPRNet-based OCR for Indian license plates.

        The Indian_LPR checkpoint was trained on cv2.imread BGR crops, so the
        crop is passed through unconverted (the old pixel-heuristic BGR->RGB
        swap here used to corrupt reads).
        """
        try:
            if self.lprnet is None:
                return None, 0.0

            # read_plate() preprocesses (94x24, normalize) and decodes CTC,
            # and already applies Indian-plate validation internally.
            text, confidence = self.lprnet.read_plate(crop_img)

            if text and len(text) >= 4:
                return text, confidence

            return None, 0.0

        except Exception as e:
            print(f"[ocr_reader] LPRNet OCR failed: {e}")
            return None, 0.0
    
    def _read_paddleocr(self, crop_img):
        """
        Fast-path multi-pass OCR with PaddleOCR.
        Strategy: Try original first, only use multi-pass if confidence is low or format invalid.
        Enhanced with multi-factor scoring for better result selection.
        """
        # Fast path: Try original crop first
        result = self.ocr.ocr(crop_img, cls=True)
        
        if result and result[0]:
            texts = []
            confs = []
            for line in result[0]:
                texts.append(line[1][0])
                confs.append(line[1][1])

            text = "".join(texts)
            text = text.upper()
            text = re.sub(r"[^A-Z0-9]", "", text)
            
            # Apply Indian plate format validation
            normalized_text = validate_indian_plate_format(text)
            
            avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0
            
            # Adaptive multi-pass decision
            h, w = crop_img.shape[:2]
            should_use_multipass = False
            
            # Always use multi-pass for small crops
            if h < 50 or w < 100:
                should_use_multipass = True
            # Use multi-pass if first result has low confidence
            elif avg_conf < 0.8:
                should_use_multipass = True
            # Use multi-pass if first result has invalid format
            is_valid_format = bool(re.match(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$", normalized_text))
            if not is_valid_format:
                should_use_multipass = True
            
            # Fast path success: high confidence AND valid format AND good image quality
            if not should_use_multipass and ((avg_conf >= 0.85 and is_valid_format) or avg_conf >= 0.90):
                return normalized_text, avg_conf
        
        # Slow path: Try multi-pass for low-confidence or invalid format results
        candidates = []
        
        # Generate preprocessing variants (only a subset for speed)
        h, w = crop_img.shape[:2]
        if h < 50 or w < 100:
            # For small crops, try more variants
            variant_names = ["original", "upscaled_2x", "upscaled_3x", "enhanced_contrast", "sharpened"]
        else:
            # For normal crops, try fewer variants
            variant_names = ["original", "enhanced_contrast", "sharpened"]
        
        all_variants = preprocess_plate_crop(crop_img)
        variant_dict = {name: crop for name, crop in all_variants}
        
        for variant_name in variant_names:
            if variant_name not in variant_dict:
                continue
                
            variant_crop = variant_dict[variant_name]
            
            try:
                result = self.ocr.ocr(variant_crop, cls=True)
                
                if result and result[0]:
                    texts = []
                    confs = []
                    for line in result[0]:
                        texts.append(line[1][0])
                        confs.append(line[1][1])

                    text = "".join(texts)
                    text = text.upper()
                    text = re.sub(r"[^A-Z0-9]", "", text)
                    
                    # Apply Indian plate format validation
                    normalized_text = validate_indian_plate_format(text)
                    
                    avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0
                    
                    if text and len(text) >= 4:
                        is_valid_format = bool(re.match(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$", normalized_text))
                        
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
            return None, 0.0
        
        # Select best candidate: prioritize enhanced score, then valid format, then confidence
        valid_format = [c for c in candidates if c["is_valid_format"]]
        invalid_format = [c for c in candidates if not c["is_valid_format"]]
        
        if valid_format:
            best_candidate = max(valid_format, key=lambda x: x["enhanced_score"])
        else:
            best_candidate = max(invalid_format, key=lambda x: x["enhanced_score"])
        
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
    """
    if not LPRNET_AVAILABLE and not PADDLEOCR_AVAILABLE:
        print(f"[ocr_reader] Neither LPRNet nor PaddleOCR is installed - OCR will be "
              f"reported as unavailable for this run; vehicle detection is unaffected.")
        return None
    
    try:
        # Construction is the contract of this helper. Do not perform an
        # artificial post-construction validation here: tests, adapters and
        # future OCR-compatible implementations may return proxy objects
        # that intentionally do not expose the internal ``ocr`` attribute.
        # Actual usability is verified naturally when PlateOCR.read() is called.
        ocr_instance = PlateOCR(lang=lang)
        print(f"[ocr_reader] OCR initialized successfully using {ocr_instance.engine_type} for language '{lang}'")
        return ocr_instance
    except SystemExit as e:
        print(f"[ocr_reader] OCR failed to initialize (it called sys.exit "
              f"internally, exit code {e.code}) - most likely it could not reach "
              f"its model-weight CDN. OCR will be reported as unavailable for "
              f"this run; vehicle detection is unaffected.")
        return None
    except Exception as e:
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


def vote_plate_text(readings):
    """
    combines multiple OCR readings of the SAME physical plate (e.g. from
    consecutive video frames while a vehicle is in view) into one best guess,
    instead of trusting a single frame's OCR result.

    readings: list of (text, confidence) tuples, e.g.
        [("TN38AB1234", 0.91), ("TN38A81234", 0.62), ("TN38AB1234", 0.88)]

    requires per-vehicle frame tracking to actually group readings together
    (e.g. ByteTrack/BoT-SORT assigning a track id across frames) - this
    function assumes that grouping has already happened elsewhere and you're
    just handing it the readings for one tracked vehicle.

    returns: (best_text, combined_confidence)
    """
    if not readings:
        return None, 0.0

    # weighted vote: each distinct text gets the sum of confidences of all
    # readings that produced it. highest total wins.
    from collections import defaultdict
    votes = defaultdict(float)
    counts = defaultdict(int)

    for text, conf in readings:
        if not text:
            continue
        votes[text] += conf
        counts[text] += 1

    if not votes:
        return None, 0.0

    best_text = max(votes, key=votes.get)
    # confidence = average confidence of readings that agreed on the winner
    best_confidence = round(votes[best_text] / counts[best_text], 3)

    return best_text, best_confidence
