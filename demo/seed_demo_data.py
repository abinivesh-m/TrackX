"""
seed_demo_data.py

Populates the observation database with realistic SYNTHETIC data, so the
whole downstream stack — trajectory reconstruction, fusion scoring, alerts,
analytics, the GIS map, and the web dashboards — is demoable RIGHT NOW,
without needing trained plate-detector weights or real multi-camera footage.

This does not touch detection/OCR/appearance-embedding code at all. It writes
directly to the same database schema that the real pipeline (demo/visual_pipeline.py
+ detection/* + recognition/*) produces, including normalized plates,
per-observation appearance vectors, bboxes and provenance tags. Everything
downstream — intelligence/trajectory.py, intelligence/fusion.py,
intelligence/alerts.py, analytics/analytics.py, gis/gis_map.py and the
FastAPI/React web app — runs unmodified against this data.

SAY THIS OUT LOUD IF A JUDGE ASKS: this data is SYNTHETIC (a demo scenario),
seeded to demonstrate matching/alerting/analytics/GIS end-to-end on a 7-camera
Coimbatore topology. The detection and OCR components underneath are real and
run separately (demo/visual_pipeline.py, scripts/run_real_pipeline.py). The web
app labels this clearly as DEMO MODE. Don't imply plate reads came from a live
camera when they came from the seeded scenario.

What gets seeded (feature-exercising scenarios plus background traffic):
  1. A clean multi-camera trajectory (TN10AB1234) CAM_01 -> CAM_02 -> CAM_03.
  2. A ring-road trajectory (TN22CD5678) CAM_01 -> CAM_04 (higher-speed edge).
  3. A blacklisted vehicle (TN38AB1234) crossing CAM_02 -> CAM_03 — triggers a
     BLACKLIST_MATCH alert.
  4. A "noisy OCR" vehicle (TN45BS9012) whose plate read drifts by one
     confusable character on one hop — exercises fuzzy plate matching.
  5. A vehicle re-appearing at the SAME camera 3 times in a short window
     (TN99ZZ0000) — REPEATED_CAMERA_SIGHTING anomaly.
  6. An IMPOSSIBLE TRANSITION vehicle (TN77IM9999) CAM_01 -> CAM_04 with an
     impossibly short gap — route anomaly.
  7. A POSSIBLE CLONED PLATE vehicle (TN88CL0000) — same plate at distant
     cameras with incompatible timing — cloned-plate anomaly.
  8. Additional multi-camera vehicles (KA01AB1234, MH12CD3456, DL8CAG4321,
     AP16ER7788) travelling along the CAM_01..CAM_07 corridor.
  9. ~40 single-camera background sightings (cars / motorcycles / trucks /
     buses) across all seven cameras — feeds analytics density, class mix,
     camera flow and GIS heatmap.

usage (from project root):
    python -m demo.seed_demo_data              # add to existing data
    python -m demo.seed_demo_data --reset       # wipe the demo db first
"""

import argparse
import os
import random
import string
import sys
from datetime import datetime, timedelta

import numpy as np

from database.observation_store import ObservationStore
from database.blacklist_store import BlacklistStore
from network.camera_network import CAMERAS
from config import RESULTS_DIR

DB_PATH = str(RESULTS_DIR / "observations.db")
VECTOR_DIM = 512  # matches the ResNet18 pooled-feature size recognition/appearance.py produces

# base time for the whole demo scenario - anchored a few hours before
# whenever this script actually runs (not a hardcoded calendar date), so
# every timestamp stays within the "last 24 hours" window several backend
# endpoints filter on (backend/app/api/v1/congestion.py's
# get_camera_traffic_metrics/process_camera_congestion default to hours=24,
# same for congestion/analytics/{camera_id}). A fixed past date (this used
# to be datetime(2026, 8, 24, 9, 0, 0)) ages out of that window the moment
# "today" moves past it - Process All Cameras would then silently find 0
# congested cameras against a full 84-observation demo dataset, not because
# nothing is congested but because every observation is invisible to a
# 24-hour lookback. Computed once at import time, so a single seeding run
# is still fully reproducible/readable - only the anchor point moves.
BASE_TIME = datetime.now() - timedelta(hours=3)

VEHICLE_TYPES = ["car", "car", "car", "motorcycle", "truck", "bus"]

# camera corridor order used to build realistic routes
CORRIDOR = ["CAM_01", "CAM_02", "CAM_03", "CAM_04", "CAM_05", "CAM_06", "CAM_07"]


def _confusable_swap(plate_text):
    """swap one character for a visually-confusable one, e.g. B -> 8,
    to simulate a realistic OCR misread on a later camera hit."""
    swaps = {"B": "8", "O": "0", "I": "1", "S": "5", "Z": "2", "G": "6"}
    chars = list(plate_text)
    for i, c in enumerate(chars):
        if c in swaps:
            chars[i] = swaps[c]
            return "".join(chars)
    return plate_text  # no swappable char found, return unchanged


def _random_plate():
    state = random.choice(["TN", "KA", "KL", "AP", "TS", "MH", "DL", "HR", "GJ"])
    digits1 = "".join(random.choices(string.digits, k=2))
    letters = "".join(random.choices(string.ascii_uppercase, k=2))
    digits2 = "".join(random.choices(string.digits, k=4))
    return f"{state}{digits1}{letters}{digits2}"


def _vehicle_appearance_vector(seed):
    """a random-but-consistent 'fingerprint' for one physical vehicle -
    same vehicle across camera hits gets this vector plus small noise
    (so cosine similarity stays high, ~0.95+), different vehicles get
    independently random vectors (cosine similarity near 0)."""
    rng = np.random.RandomState(seed)
    return rng.normal(size=VECTOR_DIM)


def _noisy_copy(vector, rng, noise_scale=0.05):
    return (vector + rng.normal(scale=noise_scale, size=vector.shape)).tolist()


def _record(plate_text, confidence, camera_id, timestamp, track_id, vehicle_type,
            appearance_vector=None):
    """Build one observation in the full visual-pipeline schema."""
    cam = CAMERAS[camera_id]
    plate = plate_text.replace(" ", "").upper()
    return {
        "normalized_plate_text": plate,      # maps to plate_text column
        "raw_plate_text": plate_text,        # as read
        "normalized_plate": plate,
        "ocr_confidence": confidence,
        "confidence": confidence,
        "plate_status": "detected",
        "camera_id": camera_id,
        "timestamp": timestamp.isoformat(),
        "lat": cam["lat"],
        "long": cam["long"],
        "track_id": track_id,
        "vehicle_class": vehicle_type,
        "vehicle_type": vehicle_type,
        "vehicle_confidence": round(min(0.99, 0.90 + confidence * 0.08), 3),
        "vehicle_bbox": [80, 120, 420, 640],
        "plate_bbox": [200, 130, 320, 180],
        "source_file": f"recorded_feed_{camera_id}.mp4",
        "source_type": "video",
        "frame_index": random.randint(0, 9000),
        "source": "synthetic_demo_seed",
        "data_source": "DEMO_SYNTHETIC",
        "appearance_vector": appearance_vector if appearance_vector is not None
                             else _vehicle_appearance_vector(seed=random.randint(1, 10 ** 6)),
    }


def rng_jitter():
    return random.uniform(-0.04, 0.04)


def seed(store, rng):
    records = []  # full-schema observation dicts

    # --- 1. clean multi-camera trajectory ---
    plate = "TN10AB1234"
    vec = _vehicle_appearance_vector(seed=1)
    t = BASE_TIME
    hops = [
        ("CAM_01", 0),
        ("CAM_02", 170),    # ~1.4km at ~30kmph
        ("CAM_03", 386),    # +0.6km at ~30kmph
        ("CAM_05", 560),    # continues along the corridor
    ]
    for i, (cam, gap) in enumerate(hops):
        ts = BASE_TIME + timedelta(seconds=gap)
        rec = _record(plate, round(0.93 + rng_jitter(), 3), cam, ts,
                       track_id=f"{plate}-{i}", vehicle_type="car",
                       appearance_vector=_noisy_copy(vec, np.random.RandomState(10 + i)))
        records.append(rec)

    # --- 2. ring-road 2-camera trajectory ---
    plate = "TN22CD5678"
    vec = _vehicle_appearance_vector(seed=2)
    t = BASE_TIME + timedelta(minutes=4)
    hops = [("CAM_01", t), ("CAM_04", t + timedelta(seconds=282))]  # ~3.5km ring edge
    for i, (cam, ts) in enumerate(hops):
        rec = _record(plate, round(0.90 + rng_jitter(), 3), cam, ts,
                       track_id=f"{plate}-{i}", vehicle_type="car",
                       appearance_vector=_noisy_copy(vec, np.random.RandomState(20 + i)))
        records.append(rec)

    # --- 3. blacklisted vehicle ---
    plate = "TN38AB1234"
    vec = _vehicle_appearance_vector(seed=3)
    t = BASE_TIME + timedelta(minutes=7)
    hops = [("CAM_02", t), ("CAM_03", t + timedelta(seconds=210)),
            ("CAM_04", t + timedelta(seconds=420))]
    for i, (cam, ts) in enumerate(hops):
        rec = _record(plate, round(0.95 + rng_jitter(), 3), cam, ts,
                       track_id=f"{plate}-{i}", vehicle_type="car",
                       appearance_vector=_noisy_copy(vec, np.random.RandomState(30 + i)))
        records.append(rec)

    # --- 4. noisy OCR vehicle - plate drifts one confusable char on a hop ---
    base_plate = "TN45BS9012"
    vec = _vehicle_appearance_vector(seed=4)
    t = BASE_TIME + timedelta(minutes=10)
    plate_reads = [base_plate, _confusable_swap(base_plate), base_plate]
    confidences = [0.91, 0.58, 0.88]
    hops = [("CAM_01", 0), ("CAM_02", 170), ("CAM_03", 386)]
    for i, ((cam, gap), plate_text, conf) in enumerate(zip(hops, plate_reads, confidences)):
        ts = BASE_TIME + timedelta(minutes=10, seconds=gap)
        rec = _record(plate_text, conf, cam, ts, track_id=f"{base_plate}-{i}",
                       vehicle_type="car",
                       appearance_vector=_noisy_copy(vec, np.random.RandomState(40 + i)))
        records.append(rec)

    # --- 5. repeated sighting at the SAME camera (loitering) ---
    plate = "TN99ZZ0000"
    vec = _vehicle_appearance_vector(seed=5)
    t = BASE_TIME + timedelta(minutes=15)
    for i, gap in enumerate([0, 90, 200]):
        ts = t + timedelta(seconds=gap)
        rec = _record(plate, round(0.85 + rng_jitter(), 3), "CAM_03", ts,
                       track_id=f"{plate}-{i}", vehicle_type="motorcycle",
                       appearance_vector=_noisy_copy(vec, np.random.RandomState(50 + i)))
        records.append(rec)

    # --- 6. IMPOSSIBLE TRANSITION vehicle ---
    plate = "TN77IM9999"
    vec = _vehicle_appearance_vector(seed=6)
    t = BASE_TIME + timedelta(minutes=18)
    for i, (cam, gap) in enumerate([("CAM_01", 0), ("CAM_04", 30)]):  # 3.5km in 30s
        ts = t + timedelta(seconds=gap)
        rec = _record(plate, round(0.92 + rng_jitter(), 3), cam, ts,
                       track_id=f"{plate}-{i}", vehicle_type="car",
                       appearance_vector=_noisy_copy(vec, np.random.RandomState(60 + i)))
        records.append(rec)

    # --- 7. POSSIBLE CLONED PLATE vehicle ---
    plate = "TN88CL0000"
    vec = _vehicle_appearance_vector(seed=7)
    t = BASE_TIME + timedelta(minutes=20)
    for i, (cam, gap) in enumerate([("CAM_01", 0), ("CAM_04", 25)]):  # 3.5km in 25s
        ts = t + timedelta(seconds=gap)
        rec = _record(plate, round(0.94 + rng_jitter(), 3), cam, ts,
                       track_id=f"{plate}-{i}", vehicle_type="car",
                       appearance_vector=_noisy_copy(vec, np.random.RandomState(70 + i)))
        records.append(rec)

    # --- 8. additional corridor vehicles (varied states / vehicle classes) ---
    extras = [
        # (plate, start_min, type, [(cam_idx, cumulative_seconds_from_route_start), ...])
        ("TN09CX7134", 0, "car", [(0, 0), (1, 157), (2, 368), (4, 560), (6, 767)]),
        ("KA01AB1234", 12, "car", [(0, 0), (2, 170), (4, 330)]),
        ("MH12CD3456", 22, "car", [(1, 0), (3, 160), (5, 340)]),
        ("DL8CAG4321", 26, "car", [(0, 0), (1, 150), (3, 330), (6, 560)]),
        ("AP16ER7788", 33, "motorcycle", [(2, 0), (4, 140), (6, 300)]),
        ("KL07MN9090", 41, "bus", [(5, 0), (6, 220)]),
        ("TS09UV1122", 47, "truck", [(1, 0), (3, 260), (5, 540)]),
    ]
    for seed_i, (plate, start_min, vtype, hop_spec) in enumerate(extras):
        # hop_spec entries are (camera_index, cumulative_seconds_from_route_start)
        vec = _vehicle_appearance_vector(seed=200 + seed_i)
        for i, (cam_idx, cum_sec) in enumerate(hop_spec):
            ts = BASE_TIME + timedelta(minutes=start_min) + timedelta(seconds=cum_sec)
            cam = CORRIDOR[cam_idx]
            rec = _record(plate, round(0.90 + rng_jitter(), 3), cam, ts,
                           track_id=f"{plate}-{i}", vehicle_type=vtype,
                           appearance_vector=_noisy_copy(vec, np.random.RandomState(200 + seed_i * 10 + i)))
            records.append(rec)

    # --- 9. background traffic - single-camera sightings across all 7 cameras ---
    for i in range(42):
        plate = _random_plate()
        vec = _vehicle_appearance_vector(seed=1000 + i)
        cam = random.choice(list(CAMERAS.keys()))
        ts = BASE_TIME + timedelta(minutes=random.uniform(0, 150))
        rec = _record(plate, round(random.uniform(0.72, 0.97), 3), cam, ts,
                       track_id=f"BG-{i}", vehicle_type=random.choice(VEHICLE_TYPES),
                       appearance_vector=_noisy_copy(vec, np.random.RandomState(1000 + i), noise_scale=0.0))
        records.append(rec)

    store.add_visual_observations(records)
    return len(records)


def run_seed(reset: bool = True, seed_value: int = 42) -> dict:
    """
    The actual seeding work, callable directly (not just from the CLI) -
    used by both main() below and, when AUTO_SEED_DEMO_DATA=true,
    backend/app/main.py's startup lifespan (Phase 14: a public deployment on
    ephemeral disk - Render's free tier, for one - loses its SQLite file on
    every restart/redeploy, so the app can re-seed itself on boot instead of
    coming up with an empty, undemoable database and no shell access to fix
    it). Returns a small summary dict instead of only printing, so a caller
    can log/inspect the result.
    """
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"removed existing {DB_PATH}")

    random.seed(seed_value)
    rng = np.random.RandomState(seed_value)

    store = ObservationStore(db_path=DB_PATH)
    count = seed(store, rng)
    store.close()

    # Blacklist is BlacklistStore-backed: register the demo blacklisted vehicle
    # so scenario #3 fires a BLACKLIST_MATCH alert. add_plate() is idempotent.
    blacklist_store = BlacklistStore(db_path=DB_PATH)
    blacklist_store.add_plate(
        "TN38AB1234",
        description="demo scenario #3 - seeded blacklist entry",
        severity="HIGH",
        source="DEMO_SEED",
    )
    # second blacklist entry so the Alerts page can show more than one match
    blacklist_store.add_plate(
        "DL8CAG4321",
        description="demo scenario #8 - watchlisted vehicle (suspect)",
        severity="MEDIUM",
        source="DEMO_SEED",
    )
    blacklist_store.close()

    print(f"seeded {count} observation(s) into {DB_PATH}")
    print("seeded 2 blacklist entries (TN38AB1234 HIGH, DL8CAG4321 MEDIUM)")

    # Bulletproof Demo Mode (Phase 11): congestion events are the one piece
    # of state on this database that nothing computes automatically -
    # GET /api/v1/alerts and GET /api/v1/gis/congestion recompute themselves
    # from raw observations on every call, but the persisted
    # ACTIVE/RESOLVED CongestionEvent rows the Congestion page's "Active
    # Bottlenecks" panel (and CONGESTION_BOTTLENECK alerts) read only exist
    # once someone clicks "Process All Cameras" - so a demo that resets and
    # goes straight to the Alerts or Overview page without visiting the
    # Congestion page first would show zero congestion alerts even if real
    # congestion exists in the data just seeded. Reusing the exact same
    # per-camera function POST /congestion/process/all calls (not a
    # reimplementation) makes a single `--reset` run leave every page
    # correct regardless of navigation order.
    try:
        import sys as _sys
        backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
        if backend_path not in _sys.path:
            _sys.path.insert(0, backend_path)
        # Import via the plain "app.X" path (not "backend.app.X") -
        # deliberately matching the convention every other module in this
        # backend uses. Phase 14 finding: backend/app/api/v1/health.py used
        # to import via "backend.app.X", which registers a SECOND, parallel
        # copy of the SQLAlchemy model classes under a different qualified
        # name. SQLAlchemy's configure_mappers() sweeps every registered
        # mapper in the process on the first ORM flush/commit ANYWHERE, so
        # that second copy - fine on its own, since nothing queries it -
        # crashed the very next real ORM write in the whole process with
        # "expression 'Observation' failed to locate a name", because that
        # copy's relationship() could never resolve. Fixed at the source in
        # health.py; matching the same convention here too so run_seed()
        # stays safe to call from inside the live app process (see
        # AUTO_SEED_DEMO_DATA in backend/app/main.py's lifespan).
        from app.api.v1.congestion import _process_one_camera
        from database.congestion_store import CongestionStore

        congestion_store = CongestionStore(db_path=DB_PATH)
        thresholds = congestion_store.get_thresholds()
        congestion_store.close()

        congested_ids = set()
        for camera_id in CAMERAS:
            outcome = _process_one_camera(camera_id, thresholds)
            if outcome and outcome.get("congested"):
                congested_ids.add(camera_id)

        congestion_store = CongestionStore(db_path=DB_PATH)
        try:
            congestion_store.resolve_events_not_in(congested_ids)
        finally:
            congestion_store.close()

        print(f"processed congestion for {len(CAMERAS)} camera(s) - {len(congested_ids)} congested")
        congested_count = len(congested_ids)
    except Exception as e:
        print(f"WARNING: could not pre-process congestion events ({e}). "
              f"Click 'Process All Cameras' on the Congestion page before demoing "
              f"congestion alerts/bottlenecks.")
        congested_count = None

    print("\nNext:")
    print("  Open the web app (FastAPI + React) - Overview, Camera Network,")
    print("  Vehicle Intelligence, Traffic Analytics, and Alerts are all live")
    print("  against this seeded data now. No further script needs to run.")

    return {
        "observations_seeded": count,
        "blacklist_entries_seeded": 2,
        "cameras_congestion_processed": len(CAMERAS),
        "cameras_congested": congested_count,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true",
                    help="delete the existing demo database before seeding fresh data")
    p.add_argument("--seed", type=int, default=42,
                    help="random seed, for reproducible demo data across runs")
    args = p.parse_args()
    run_seed(reset=args.reset, seed_value=args.seed)


if __name__ == "__main__":
    main()
