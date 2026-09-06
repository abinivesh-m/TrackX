"""
plate_matcher.py

fuzzy string matching for OCR-read license plates.

why fuzzy and not exact match: OCR on real-world plates (motion blur, dirt,
angled shots) commonly confuses visually similar characters - O/0, I/1,
B/8, S/5, Z/2 - so two reads of the SAME physical plate can come out as
slightly different strings. Comparing with plain string equality would
wrongly treat those as different vehicles.

this is a lightweight, explainable implementation (no external fuzzy-match
dependency) - normalized edit-distance similarity, plus a small bonus for
known OCR-confusable character swaps. good enough for a hackathon demo;
a production system would tune this against a real confusion matrix
learned from your OCR model's actual error patterns.
"""

import re

# characters that PaddleOCR (or any plate OCR) commonly confuses on
# low-quality plate crops - used to slightly discount edit-distance
# penalties when the substitution is one of these known look-alikes
CONFUSABLE_PAIRS = {
    frozenset(("O", "0")),
    frozenset(("I", "1")),
    frozenset(("B", "8")),
    frozenset(("S", "5")),
    frozenset(("Z", "2")),
    frozenset(("G", "6")),
    frozenset(("D", "0")),
}


def normalize_plate(text):
    """uppercase + strip anything that isn't a letter or digit"""
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _is_confusable(a, b):
    return frozenset((a, b)) in CONFUSABLE_PAIRS


def _levenshtein(a, b):
    """standard edit distance, but a confusable-character substitution
    costs 0.5 instead of 1.0 - a single O/0 misread shouldn't count the
    same as a genuinely different character."""
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev_row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur_row = [i]
        for j, cb in enumerate(b, start=1):
            if ca == cb:
                cost = 0
            elif _is_confusable(ca, cb):
                cost = 0.5
            else:
                cost = 1
            cur_row.append(min(
                prev_row[j] + 1,        # deletion
                cur_row[j - 1] + 1,     # insertion
                prev_row[j - 1] + cost  # substitution
            ))
        prev_row = cur_row

    return prev_row[-1]


def plate_similarity(plate_a, plate_b):
    """
    returns a 0-1 similarity score between two plate strings.
    1.0 = identical (after normalization), 0.0 = completely different.
    """
    a = normalize_plate(plate_a)
    b = normalize_plate(plate_b)

    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    max_len = max(len(a), len(b))
    if max_len == 0:
        return 0.0

    dist = _levenshtein(a, b)
    similarity = 1 - (dist / max_len)
    return round(max(0.0, similarity), 3)


if __name__ == "__main__":
    tests = [
        ("TN38AB1234", "TN38AB1234"),   # identical
        ("TN38AB1234", "TN38A81234"),   # B misread as 8
        ("TN38AB1234", "TN380B1234"),   # A misread as 0 (not in confusable set - genuine diff)
        ("TN10AB1234", "TN99ZZ0000"),   # very different
    ]
    for p1, p2 in tests:
        print(f"{p1} vs {p2} -> similarity {plate_similarity(p1, p2)}")
