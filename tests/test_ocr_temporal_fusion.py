"""
test_ocr_temporal_fusion.py

SIH26127 "Adaptive Multi-Frame ANPR Intelligence" pass - regression tests
for the character-level temporal voting upgrade to vote_plate_text()
(recognition/ocr_reader.py), the plate quality assessment module
(recognition/plate_quality.py), and the plate_state rollup
(pipeline._plate_state_for_track()).

These lock in the exact real-world failure modes this pass was built to
fix, using synthetic reproductions of the two ACTUALLY DOCUMENTED OCR
errors found during real-CCTV validation this session:
    KA02MN1826 (ground truth) misread as KA02MN1828 (6->8 confusion)
    KA02MH7256 (ground truth) misread as KA02HH7256 (M->H confusion)
and the real-video-testing-discovered risk that OCR-call-sampling +
early-stop can let a small, coincidentally-agreeing subset of readings
look as "confident" as a much larger genuine consensus (see
docs/PERFORMANCE_PROFILE.md for the real run that surfaced this).

Run with: python -m pytest tests/test_ocr_temporal_fusion.py -v
"""
import numpy as np

from recognition.ocr_reader import vote_plate_text
from recognition.plate_quality import assess_plate_quality
from pipeline import _plate_state_for_track, link_plate_continuity


# ---------------------------------------------------------------------------
# vote_plate_text: whole-string frequency vote (baseline, unchanged behavior)
# ---------------------------------------------------------------------------

def test_simple_majority_wins():
    readings = [("TN38AB1234", 0.9), ("TN38AB1234", 0.85), ("TN38A81234", 0.5)]
    text, conf = vote_plate_text(readings)
    assert text == "TN38AB1234"
    assert conf > 0


def test_empty_readings_returns_none():
    assert vote_plate_text([]) == (None, 0.0)
    assert vote_plate_text([(None, 0.5), ("", 0.3)]) == (None, 0.0)


# ---------------------------------------------------------------------------
# The two REAL documented character-level errors from this session's CCTV
# validation - reproduced synthetically as regression guards.
# ---------------------------------------------------------------------------

def test_6_vs_8_confusion_corrects_when_6_is_the_real_majority():
    """KA02MN1826 misread as KA02MN1828 on some frames - when the '6'
    reading genuinely dominates, the vote must land on '6', not the more
    numerous-by-accident '8'."""
    readings = [
        ("KA02MN1826", 0.85), ("KA02MN1826", 0.80), ("KA02MN1826", 0.90),
        ("KA02MN1828", 0.60), ("KA02MN1826", 0.75),
    ]
    text, conf = vote_plate_text(readings)
    assert text == "KA02MN1826"


def test_6_vs_8_confusion_does_not_force_correct_against_real_evidence():
    """The confusable-pair gate must never flip a position AWAY from what
    the evidence actually supports - if '8' is the genuine majority, the
    result must stay '8', not get blindly force-corrected to '6' just
    because they're a known confusable pair."""
    readings = [
        ("KA02MN1828", 0.90), ("KA02MN1828", 0.88), ("KA02MN1828", 0.92),
        ("KA02MN1826", 0.40),
    ]
    text, conf = vote_plate_text(readings)
    assert text == "KA02MN1828"


def test_m_vs_h_confusion_corrects_when_m_is_the_real_majority():
    """KA02MH7256 misread as KA02HH7256 on some frames."""
    readings = [
        ("KA02MH7256", 0.82), ("KA02MH7256", 0.79), ("KA02HH7256", 0.55),
        ("KA02MH7256", 0.88),
    ]
    text, conf = vote_plate_text(readings)
    assert text == "KA02MH7256"


def test_non_confusable_single_outlier_never_flips_majority():
    """A single stray high-confidence misread on a NON-confusable
    character swap must never override an otherwise-consistent majority -
    this is the 'never blindly replace characters' requirement."""
    readings = [
        ("TN38AB1234", 0.70), ("TN38AB1234", 0.72), ("TN38AB1234", 0.68),
        ("TN38AB1284", 0.99),  # 3<->8 is not in CONFUSABLE_PAIRS
    ]
    text, conf = vote_plate_text(readings)
    assert text == "TN38AB1234"


# ---------------------------------------------------------------------------
# Confidence must reflect real consensus depth, not just "how confident was
# the winning cluster" - this is what let OCR-sampling's early-stop trust a
# small, coincidentally-agreeing sample during real-video perf testing.
# ---------------------------------------------------------------------------

def test_confidence_penalizes_low_agreement_ratio():
    """A text only a minority of readings support should score lower than
    one most readings agree on, even at similar individual confidences."""
    strong_majority = [("UP16GT4814", 0.85)] * 6 + [("13228", 0.90)] * 2
    _, strong_conf = vote_plate_text(strong_majority)

    weak_minority_readings = [("UP16GT4814", 0.85)] * 3 + [("13228", 0.90)] * 3
    text, weak_conf = vote_plate_text(weak_minority_readings)
    # with an even 3/3 split the majority is ambiguous, but the winning
    # side's agreement ratio is only 0.5 either way - the point of this
    # test is the STRONG majority case must score higher confidence than
    # any evenly-contested case, not a specific text.
    assert strong_conf > weak_conf


def test_confidence_penalizes_small_sample_even_with_full_agreement():
    """Two readings that both happen to fully agree is still weaker
    evidence than six that do - this was the actual root cause behind a
    real-video regression seen during OCR-sampling testing (a 4-reading,
    fully-agreeing but WRONG vote scored as confidently as a genuine
    14-reading consensus)."""
    few_readings = [("13228", 0.90), ("13228", 0.88)]
    _, few_conf = vote_plate_text(few_readings)

    many_readings = [("13228", 0.90)] * 8
    _, many_conf = vote_plate_text(many_readings)

    assert many_conf > few_conf


def test_return_evidence_structure():
    readings = [("KA02MN1826", 0.85), ("KA02MN1826", 0.80), ("KA02MN1828", 0.60)]
    text, conf, evidence = vote_plate_text(readings, return_evidence=True)
    assert text == "KA02MN1826"
    assert evidence["num_readings"] == 3
    assert evidence["frequency_winner"] == "KA02MN1826"
    assert 0.0 <= evidence["agreement_ratio"] <= 1.0
    assert evidence["final_text"] == text
    assert len(evidence["all_readings"]) == 3


# ---------------------------------------------------------------------------
# plate_quality.assess_plate_quality - real measured metrics, not invented
# ---------------------------------------------------------------------------

def test_assess_plate_quality_empty_crop_is_safe():
    q = assess_plate_quality(None)
    assert q["quality_score"] == 0.0
    assert q["is_small"] is True

    q2 = assess_plate_quality(np.zeros((0, 0, 3), dtype=np.uint8))
    assert q2["quality_score"] == 0.0


def test_assess_plate_quality_flags_small_dark_crop():
    tiny_dark = np.full((15, 40, 3), 10, dtype=np.uint8)  # small, near-black
    q = assess_plate_quality(tiny_dark)
    assert q["is_small"] is True
    assert q["is_low_light"] is True
    assert q["height"] == 15 and q["width"] == 40


def test_assess_plate_quality_good_crop_scores_higher_than_bad_crop():
    good = np.random.randint(100, 180, (100, 300, 3), dtype=np.uint8)
    bad = np.full((15, 40, 3), 5, dtype=np.uint8)
    q_good = assess_plate_quality(good)
    q_bad = assess_plate_quality(bad)
    assert q_good["quality_score"] > q_bad["quality_score"]


# ---------------------------------------------------------------------------
# pipeline._plate_state_for_track - VERIFIED requires real temporal depth,
# not just one confident frame ("Do not mark VERIFIED based on one weak
# frame").
# ---------------------------------------------------------------------------

def test_plate_state_unknown_when_not_recognized():
    assert _plate_state_for_track("unavailable", 0, None) == "UNKNOWN"
    assert _plate_state_for_track("no_plate_detected", 0, None) == "UNKNOWN"
    assert _plate_state_for_track("detected_not_read", 0, None) == "UNKNOWN"


def test_plate_state_low_confidence_passthrough():
    assert _plate_state_for_track("low_confidence", 5, 0.9) == "LOW_CONFIDENCE"


def test_plate_state_tentative_needs_more_evidence_than_verified():
    # recognized, but thin evidence (single reading) - TENTATIVE, not VERIFIED
    assert _plate_state_for_track("recognized", 1, 0.95) == "TENTATIVE"


def test_plate_state_verified_requires_both_depth_and_confidence():
    # enough readings but weak confidence -> still TENTATIVE
    assert _plate_state_for_track("recognized", 5, 0.60) == "TENTATIVE"
    # enough readings AND strong confidence -> VERIFIED
    assert _plate_state_for_track("recognized", 5, 0.85) == "VERIFIED"


# ---------------------------------------------------------------------------
# pipeline.link_plate_continuity() - plate-assisted track continuity
# (SIH26127 Priority 2 sub-part). Reproduces the real Track #448/#698
# occlusion-fragmentation shape (same plate, same vehicle_type, small gap,
# spatially close) plus three should-NOT-link cases guarding the "only
# merge when evidence is strong" requirement.
# ---------------------------------------------------------------------------

def _mk(track_id, plate, vtype, first_frame, last_frame, first_bbox, last_bbox, state="VERIFIED"):
    return {
        "track_id": track_id, "plate_state": state, "normalized_plate": plate,
        "vehicle_type": vtype, "first_seen_frame": first_frame, "last_seen_frame": last_frame,
        "first_seen_bbox": first_bbox, "last_seen_bbox": last_bbox,
    }


def test_continuity_links_real_occlusion_shape():
    """Same plate, same vehicle type, short gap, spatially close - the
    exact shape of the documented Track #448/#698 case."""
    a = _mk("448", "DL7CP8161", "car", 450, 500, [750, 290, 850, 390], [800, 300, 900, 400])
    b = _mk("698", "DL7CP8161", "car", 530, 560, [810, 305, 910, 405], [820, 310, 920, 410], state="TENTATIVE")
    records = [a, b]
    link_plate_continuity(records)
    assert a["continuity_linked_track_id"] == "698"
    assert b["continuity_linked_track_id"] == "448"
    assert a["continuity_confidence"] > 0.5


def test_continuity_never_links_different_vehicle_types():
    a = _mk("100", "TN01AB1234", "car", 150, 200, [90, 90, 190, 190], [100, 100, 200, 200])
    b = _mk("101", "TN01AB1234", "truck", 210, 240, [105, 105, 205, 205], [110, 110, 210, 210])
    records = [a, b]
    link_plate_continuity(records)
    assert a.get("continuity_linked_track_id") is None
    assert b.get("continuity_linked_track_id") is None


def test_continuity_never_links_spatially_implausible_pair():
    """Matching plate text alone is NOT enough - two vehicles on opposite
    sides of the frame must not be linked just because of a plate-text
    coincidence (e.g. two OCR misreads that happen to converge)."""
    a = _mk("300", "KA02MN1826", "car", 650, 700, [40, 40, 90, 90], [50, 50, 100, 100])
    b = _mk("301", "KA02MN1826", "car", 720, 750, [1800, 1000, 1850, 1050], [1810, 1010, 1860, 1060])
    records = [a, b]
    link_plate_continuity(records)
    assert a.get("continuity_linked_track_id") is None
    assert b.get("continuity_linked_track_id") is None


def test_continuity_never_links_across_a_large_gap():
    a = _mk("400", "UP22AT3248", "motorcycle", 80, 100, [490, 490, 540, 540], [500, 500, 550, 550])
    b = _mk("401", "UP22AT3248", "motorcycle", 400, 430, [505, 505, 555, 555], [510, 510, 560, 560])
    records = [a, b]
    link_plate_continuity(records)
    assert a.get("continuity_linked_track_id") is None
    assert b.get("continuity_linked_track_id") is None


def test_continuity_ignores_low_confidence_and_unknown_plates():
    """Evidence must be strong (TENTATIVE/VERIFIED) - LOW_CONFIDENCE/UNKNOWN
    plates are not trustworthy enough to link identity on."""
    a = _mk("500", "TN01AB1234", "car", 100, 150, [10, 10, 60, 60], [15, 15, 65, 65], state="LOW_CONFIDENCE")
    b = _mk("501", "TN01AB1234", "car", 160, 190, [16, 16, 66, 66], [20, 20, 70, 70], state="TENTATIVE")
    records = [a, b]
    link_plate_continuity(records)
    assert a.get("continuity_linked_track_id") is None
    assert b.get("continuity_linked_track_id") is None


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
