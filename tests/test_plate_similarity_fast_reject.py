# tests/test_plate_similarity_fast_reject.py
#
# Empirical proof that recognition.plate_matcher.plate_similarity_fast_reject
# (a Phase 4 performance optimization for intelligence/trajectory.py's
# windowed candidate search) NEVER disagrees with the real, unmodified
# plate_similarity() on whether a pair passes the 0.85 threshold. This is
# what makes it safe to use as a pre-filter: it can only skip the expensive
# DP for pairs it can decide with mathematical certainty (see its docstring
# for the proof) or defer (None) to the real check - it must never produce
# a false ACCEPT or false REJECT.

import random
import string

from recognition.plate_matcher import plate_similarity, plate_similarity_fast_reject, normalize_plate

ALPHABET = string.ascii_uppercase + string.digits
THRESHOLD = 0.85


def _random_plate(length):
    return "".join(random.choice(ALPHABET) for _ in range(length))


def _mutate(plate, n_mutations):
    chars = list(plate)
    for _ in range(n_mutations):
        pos = random.randrange(len(chars))
        chars[pos] = random.choice(ALPHABET)
    return "".join(chars)


def _check_agreement(a, b):
    """Assert fast_reject's verdict (when it commits to one) matches the
    real plate_similarity()'s threshold decision exactly."""
    real_pass = plate_similarity(a, b) >= THRESHOLD
    verdict = plate_similarity_fast_reject(a, b, threshold=THRESHOLD)
    if verdict is True:
        assert real_pass, f"fast_reject said ACCEPT but real similarity rejects: {a!r} vs {b!r}"
    elif verdict is False:
        assert not real_pass, f"fast_reject said REJECT but real similarity accepts: {a!r} vs {b!r}"
    # verdict is None -> no claim made, nothing to check


def test_fast_reject_agrees_with_real_similarity_equal_length_mutations():
    random.seed(7)
    for _ in range(50000):
        length = random.randint(4, 12)
        a = _random_plate(length)
        b = _mutate(a, random.randint(0, 5))
        _check_agreement(a, b)


def test_fast_reject_agrees_with_real_similarity_unequal_length():
    random.seed(11)
    for _ in range(20000):
        la = random.randint(4, 12)
        lb = max(1, la + random.choice([-2, -1, 1, 2]))
        a = _random_plate(la)
        b = _random_plate(lb)
        _check_agreement(a, b)


def test_fast_reject_agrees_on_realistic_indian_plate_formats():
    """Real-shaped plates (e.g. TN37AB1234) with 0-3 confusable-character
    misreads injected - the exact scenario this optimization targets."""
    random.seed(23)
    templates = ["TN37AB1234", "KA01AB1234", "MH12CD3456", "DL8CAG4321", "AP16ER7788"]
    confusable_subs = {"O": "0", "0": "O", "I": "1", "1": "I", "B": "8", "8": "B", "S": "5", "5": "S"}
    for _ in range(20000):
        base = random.choice(templates)
        chars = list(base)
        for _ in range(random.randint(0, 3)):
            pos = random.randrange(len(chars))
            c = chars[pos]
            chars[pos] = confusable_subs.get(c, random.choice(ALPHABET))
        mutated = "".join(chars)
        _check_agreement(normalize_plate(base), normalize_plate(mutated))


def test_fast_reject_identical_and_empty_edge_cases():
    assert plate_similarity_fast_reject("", "TN37AB1234") is False
    assert plate_similarity_fast_reject("TN37AB1234", "") is False
    assert plate_similarity_fast_reject("", "") is False
    assert plate_similarity_fast_reject("TN37AB1234", "TN37AB1234") is True
