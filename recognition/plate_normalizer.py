"""
plate_normalizer.py

Conservative normalization for Indian license plate OCR text.

Standard Indian format: SS DD L[L[L]] NNNN
    SS   - 2-letter state code            (e.g. TN, KA, MH)
    DD   - 1 or 2 digit RTO/district code (e.g. 38, 05)
    L..  - 1 to 3 letter series           (e.g. A, AB, ABC)
    NNNN - 4 digit registration number

This is intentionally conservative: it only "corrects" a character when
the position it's in has an unambiguous expected type (letter-only or
digit-only zone) AND the character is a known OCR-confusable of the
expected type (reuses recognition.plate_matcher's CONFUSABLE_PAIRS so
both stay consistent). If the cleaned text doesn't end up matching the
standard pattern after that, correction is NOT forced - the cleaned
(uppercase, alnum-only) text is returned unchanged, and pattern_matched
tells the caller whether to trust it as a well-formed Indian plate.

Raw OCR text is never discarded by this function. The caller
(demo/visual_pipeline.py) is responsible for keeping raw_text alongside
normalized_text in the structured output - normalization never replaces
the raw read, only supplements it.
"""
import re
import sys
import os

# Add parent directory to path for imports when running module directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recognition.plate_matcher import normalize_plate

INDIAN_PLATE_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$")

# digit <-> letter look-alikes. Same character pairs plate_matcher.py
# already treats as OCR-confusable, just split by direction so we know
# which way to "correct" depending on what the position expects.
# Enhanced with additional common confusions found in error analysis
_DIGIT_LOOKS_LIKE_LETTER = {"0": "O", "1": "I", "5": "S", "8": "B", "6": "G", "2": "Z", "3": "E", "4": "A", "7": "T"}
_LETTER_LOOKS_LIKE_DIGIT = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2", "G": "6", "D": "0", "Q": "0", "H": "M", "M": "H", "E": "3", "A": "4", "T": "7", "L": "1"}


def _force_letter(ch):
    return _DIGIT_LOOKS_LIKE_LETTER.get(ch, ch) if ch.isdigit() else ch


def _force_digit(ch):
    return _LETTER_LOOKS_LIKE_DIGIT.get(ch, ch) if ch.isalpha() else ch


def _try_correct(cleaned):
    """
    only attempts positional correction for strings of a plausible
    Indian-plate length (9-11 chars: SSDDLNNNN .. SSDDLLLNNNN). anything
    outside that range is left completely alone - we don't guess at
    where the boundaries are for non-standard-length reads.
    """
    n = len(cleaned)
    if n < 9 or n > 11:
        return cleaned

    series_len = n - 8  # total - (2 state + 2 district + 4 number)
    chars = list(cleaned)

    for i in (0, 1):                        # state code: letters
        chars[i] = _force_letter(chars[i])
    for i in (2, 3):                        # district code: digits
        chars[i] = _force_digit(chars[i])
    for i in range(4, 4 + series_len):       # series: letters
        chars[i] = _force_letter(chars[i])
    for i in range(n - 4, n):                # registration number: digits
        chars[i] = _force_digit(chars[i])

    return "".join(chars)


def _remove_country_marker_artifacts(text):
    """
    Removes Indian country marker artifacts (IND, ND, IND-, -ND, etc.) from OCR text.
    Only removes these when they appear as clear prefix/suffix artifacts, not when
    they could be legitimate plate characters.
    
    This handles cases where OCR partially reads the physical "IND" marking on Indian plates:
    - "INDTN09CQ1234" -> "TN09CQ1234"
    - "TN09CQ1234IND" -> "TN09CQ1234"
    - "NDTN09CQ1234" -> "TN09CQ1234"
    - "TN09CQ1234ND" -> "TN09CQ1234"
    - "IND-TN09CQ1234" -> "TN09CQ1234"
    - "TN09CQ1234-IND" -> "TN09CQ1234"
    - "TN09CQ1234-ND" -> "TN09CQ1234"
    
    Does NOT remove legitimate plate characters that happen to be I, N, or D.
    """
    if not text or len(text) < 9:
        return text
    
    result = text
    
    # Try each pattern in order of specificity
    patterns_to_try = [
        # Most specific patterns first
        (r"^IND-", "prefix"),     # IND- prefix
        (r"-IND$", "suffix"),     # -IND suffix
        (r"^-ND", "prefix"),     # -ND prefix
        (r"-ND$", "suffix"),     # -ND suffix
        # Less specific patterns
        (r"^IND", "prefix"),     # IND prefix
        (r"IND$", "suffix"),     # IND suffix
        (r"^ND", "prefix"),      # ND prefix
        (r"ND$", "suffix"),      # ND suffix
    ]
    
    for pattern, position in patterns_to_try:
        if position == "prefix":
            match = re.match(pattern, result)
            if match:
                remaining = result[match.end():]
                # Only remove if remaining text is long enough to be a plate
                if len(remaining) >= 9:
                    result = remaining
                    break  # Only remove one artifact
        else:  # suffix
            match = re.search(pattern, result)
            if match:
                remaining = result[:match.start()]
                # Only remove if remaining text is long enough to be a plate
                if len(remaining) >= 9:
                    result = remaining
                    break  # Only remove one artifact
    
    return result


def normalize_indian_plate(raw_text):
    """
    returns (normalized_text, pattern_matched)

    pattern_matched=True  -> result matches the standard SSDDL[LL]NNNN
                              shape after conservative correction; safe
                              to treat as a well-formed plate read.
    pattern_matched=False -> cleaned (uppercase, alnum-only) text is
                              returned UNCHANGED, no correction forced.
                              Caller should treat this as a lower-trust
                              read (non-standard format, partial read,
                              OCR noise, etc.) - it is not discarded,
                              just not claimed to be a valid plate.

    Day 4 (SIH26127): Added safe removal of "IND" country-marking artifact.
    Indian plates physically contain "IND" on the left side, which OCR may
    read as a prefix (e.g., "INDTN09CQ1234") or suffix (e.g., "TN09CQ1234IND").
    This now also handles partial artifacts like "ND", "IND-", "-ND", etc.
    Only removes country markers when they appear as clear prefix/suffix artifacts,
    not arbitrary letters from the actual registration number.
    """
    cleaned = normalize_plate(raw_text)
    if not cleaned:
        return "", False

    # Remove country marker artifacts (IND, ND, IND-, -ND, etc.)
    cleaned = _remove_country_marker_artifacts(cleaned)

    if INDIAN_PLATE_RE.match(cleaned):
        return cleaned, True

    corrected = _try_correct(cleaned)
    if INDIAN_PLATE_RE.match(corrected):
        return corrected, True

    return cleaned, False


if __name__ == "__main__":
    samples = [
        "TN38AB1234",         # already valid
        "TN38A81234",         # B misread as 8 in series position -> correctable
        "TN388B1Z34",         # digits/letters swapped in number zone
        "XYZ",                # too short, left alone
        "SOMEJUNK12345678",   # too long, left alone
        # Country marker artifact tests
        "INDTN09CQ1234",      # IND prefix
        "TN09CQ1234IND",      # IND suffix
        "NDTN09CQ1234",       # ND prefix (partial artifact)
        "TN09CQ1234ND",       # ND suffix (partial artifact)
        "IND-TN09CQ1234",     # IND- prefix with dash
        "TN09CQ1234-IND",     # -IND suffix with dash
        "TN09CQ1234-ND",      # -ND suffix with dash
        "-NDTN09CQ1234",      # -ND prefix with dash
        "TN09CQ1234",         # No artifact (should remain unchanged)
        "KA01AB1234",         # Different state, no artifact
        "MH02CD5678IND",      # IND suffix on different plate
        "INDKA01AB1234",      # IND prefix on different plate
    ]
    print("Testing Indian plate normalization with country marker artifact removal:")
    for s in samples:
        normalized, matched = normalize_indian_plate(s)
        status = "[MATCHED]" if matched else "[NO MATCH]"
        print(f"{s:20s} -> {normalized:15s} {status}")
