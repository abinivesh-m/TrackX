"""
fusion.py

combines 4 independent signals into one Global Match Score:

    - plate similarity      (base weight 0.45)
    - appearance similarity (base weight 0.25)
    - temporal feasibility  (base weight 0.15)
    - spatial connectivity  (base weight 0.15)

v3: plate's contribution is now scaled by how confident the OCR reads
were on both observations. a 97%-confidence plate read should count for
more than a 51%-confidence one - previously we treated them identically,
which meant a low-quality OCR result could wrongly drag down (or falsely
confirm) a match just as much as a clean read.
"""

from datetime import datetime

from recognition.plate_matcher import plate_similarity
from network.camera_network import is_temporally_feasible, is_spatially_connected, get_camera_reliability

# Optional torch-dependent import
try:
    from recognition.appearance import appearance_similarity
    _appearance_available = True
except (ImportError, OSError):
    # torch may fail to load on some systems (e.g., Windows DLL issues)
    appearance_similarity = None
    _appearance_available = False

BASE_WEIGHTS = {
    "plate": 0.45,
    "appearance": 0.25,
    "temporal": 0.15,
    "spatial": 0.15,
}

MATCH_THRESHOLD = 0.55  # Lowered to better handle OCR variations while maintaining reasonable matching


def confidence_label(score):
    if score >= 0.90:
        return "HIGH"
    elif score >= 0.75:
        return "MEDIUM"
    elif score >= MATCH_THRESHOLD:
        return "LOW"
    else:
        return "NO_MATCH"

def explain_match(obs_a, obs_b, appearance_vec_a=None, appearance_vec_b=None):
    """
    Provide detailed explanation of why two observations are considered a match.
    This is the "Why This Vehicle Match?" feature for TrackX.
    
    Returns a detailed breakdown explaining each factor in the matching decision.
    """
    score, breakdown = global_match_score(obs_a, obs_b, appearance_vec_a, appearance_vec_b)
    
    explanation = {
        "overall_decision": {
            "is_match": score >= MATCH_THRESHOLD,
            "global_match_score": score,
            "confidence_level": breakdown["confidence_label"],
            "threshold": MATCH_THRESHOLD
        },
        "evidence_breakdown": {
            "plate_similarity": {
                "value": breakdown["plate"],
                "weight_used": breakdown["effective_weights"]["plate"],
                "description": f"License plate similarity: {breakdown['plate']:.1%}",
                "plate_a": obs_a.get("normalized_plate") or obs_a.get("plate_text", "UNKNOWN"),
                "plate_b": obs_b.get("normalized_plate") or obs_b.get("plate_text", "UNKNOWN"),
                "contribution": breakdown["plate"] * breakdown["effective_weights"]["plate"]
            },
            "appearance_similarity": {
                "value": breakdown["appearance"],
                "weight_used": breakdown["effective_weights"]["appearance"],
                "description": f"Vehicle appearance similarity: {breakdown['appearance']:.1%}",
                "contribution": breakdown["appearance"] * breakdown["effective_weights"]["appearance"]
            },
            "temporal_feasibility": {
                "value": breakdown["temporal"],
                "weight_used": breakdown["effective_weights"]["temporal"],
                "description": f"Time feasibility: {breakdown['temporal']:.1%}",
                "time_diff_seconds": abs((datetime.fromisoformat(obs_b["timestamp"]) - 
                                         datetime.fromisoformat(obs_a["timestamp"])).total_seconds()),
                "camera_a": obs_a["camera_id"],
                "camera_b": obs_b["camera_id"],
                "contribution": breakdown["temporal"] * breakdown["effective_weights"]["temporal"]
            },
            "spatial_connectivity": {
                "value": breakdown["spatial"],
                "weight_used": breakdown["effective_weights"]["spatial"],
                "description": f"Road network connectivity: {breakdown['spatial']:.1%}",
                "camera_a": obs_a["camera_id"],
                "camera_b": obs_b["camera_id"],
                "contribution": breakdown["spatial"] * breakdown["effective_weights"]["spatial"]
            }
        },
        "quality_factors": {
            "ocr_confidence": breakdown.get("ocr_confidence_used", 0.0),
            "camera_reliability": "Average reliability of both camera locations",
            "signal_redistribution": "Low OCR confidence reduces plate weight, redistributed to other signals"
        },
        "vehicle_class_match": {
            "class_a": obs_a.get("vehicle_class", "UNKNOWN"),
            "class_b": obs_b.get("vehicle_class", "UNKNOWN"),
            "matches": obs_a.get("vehicle_class") == obs_b.get("vehicle_class"),
            "description": "Vehicle type consistency check"
        },
        "timestamp_info": {
            "observation_a_time": obs_a.get("timestamp"),
            "observation_b_time": obs_b.get("timestamp"),
            "time_gap_formatted": format_time_gap(abs((datetime.fromisoformat(obs_b["timestamp"]) - 
                                                   datetime.fromisoformat(obs_a["timestamp"])).total_seconds()))
        }
    }
    
    # Add rejection reason if not a match
    if "rejected_reason" in breakdown:
        explanation["rejection_reason"] = breakdown["rejected_reason"]
    
    return explanation

def format_time_gap(seconds):
    """Format time gap in human-readable format"""
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def global_match_score(obs_a, obs_b, appearance_vec_a=None, appearance_vec_b=None):
    # Use normalized_plate if available, fall back to plate_text
    plate_a = obs_a.get("normalized_plate") or obs_a.get("plate_text")
    plate_b = obs_b.get("normalized_plate") or obs_b.get("plate_text")
    
    # Handle missing plates
    if not plate_a or not plate_b:
        p_sim = 0.0
    else:
        p_sim = plate_similarity(plate_a, plate_b)
    
    # Handle appearance similarity (may be None if torch unavailable)
    if appearance_similarity is not None:
        a_sim = appearance_similarity(appearance_vec_a, appearance_vec_b)
    else:
        a_sim = 0.0  # Default when torch/appearance is unavailable

    connected, spatial_score = is_spatially_connected(obs_a["camera_id"], obs_b["camera_id"])

    if not connected:
        return 0.0, {
            "plate": p_sim, "appearance": a_sim, "temporal": 0.0, "spatial": 0.0,
            "total": 0.0, "confidence_label": "NO_MATCH",
            "rejected_reason": "no road connection between these cameras",
        }

    t1 = datetime.fromisoformat(obs_a["timestamp"])
    t2 = datetime.fromisoformat(obs_b["timestamp"])
    time_diff = abs((t2 - t1).total_seconds())

    feasible, temporal_score = is_temporally_feasible(
        obs_a["camera_id"], obs_b["camera_id"], time_diff
    )

    if not feasible:
        return 0.0, {
            "plate": p_sim, "appearance": a_sim, "temporal": 0.0, "spatial": spatial_score,
            "total": 0.0, "confidence_label": "NO_MATCH",
            "rejected_reason": "would require an impossible travel speed",
        }

    # --- confidence-weighting ---
    # obs["confidence"] already exists in our schema (combined detection+OCR
    # confidence from pipeline.py). average the two observations' confidence
    # and use it to scale how much the plate signal counts this time.
    # low-confidence reads shrink plate's weight; that weight gets
    # redistributed proportionally to the other three signals instead of
    # just being lost, so the total still adds up sensibly.
    ocr_conf = (obs_a.get("confidence", 1.0) + obs_b.get("confidence", 1.0)) / 2
    ocr_conf = max(0.0, min(1.0, ocr_conf))  # clamp, just in case

    # camera reliability factors in too - an observation from a known-bad-angle
    # camera should count for less, even if OCR itself reported high confidence
    # on that frame (OCR confidence doesn't know the camera has bad geometry)
    cam_reliability = (get_camera_reliability(obs_a["camera_id"])
                       + get_camera_reliability(obs_b["camera_id"])) / 2
    ocr_conf = ocr_conf * cam_reliability

    effective_plate_weight = BASE_WEIGHTS["plate"] * ocr_conf
    freed_weight = BASE_WEIGHTS["plate"] - effective_plate_weight

    remaining_base = BASE_WEIGHTS["appearance"] + BASE_WEIGHTS["temporal"] + BASE_WEIGHTS["spatial"]
    weights = {
        "plate": effective_plate_weight,
        "appearance": BASE_WEIGHTS["appearance"] + freed_weight * (BASE_WEIGHTS["appearance"] / remaining_base),
        "temporal": BASE_WEIGHTS["temporal"] + freed_weight * (BASE_WEIGHTS["temporal"] / remaining_base),
        "spatial": BASE_WEIGHTS["spatial"] + freed_weight * (BASE_WEIGHTS["spatial"] / remaining_base),
    }

    score = (
        weights["plate"] * p_sim
        + weights["appearance"] * a_sim
        + weights["temporal"] * temporal_score
        + weights["spatial"] * spatial_score
    )
    score = round(score, 3)

    breakdown = {
        "plate": p_sim,
        "appearance": a_sim,
        "temporal": temporal_score,
        "spatial": spatial_score,
        "total": score,
        "confidence_label": confidence_label(score),
        "ocr_confidence_used": round(ocr_conf, 3),
        "effective_weights": {k: round(v, 3) for k, v in weights.items()},
    }

    return score, breakdown


def is_match(obs_a, obs_b, appearance_vec_a=None, appearance_vec_b=None):
    score, breakdown = global_match_score(obs_a, obs_b, appearance_vec_a, appearance_vec_b)
    return score >= MATCH_THRESHOLD, score, breakdown
