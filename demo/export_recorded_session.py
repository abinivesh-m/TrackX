"""demo/export_recorded_session.py

Builds demo/recorded_session.json.gz - a compact, committable export of the
REAL_INFERENCE observations this repo produced by running the actual
YOLO + plate-detector + OCR pipeline over the seven recorded camera feeds.

Why this exists
---------------
Render's free tier gives the service an ephemeral disk, so every redeploy
starts with an empty observations database. AUTO_SEED_DEMO_DATA already
worked around that, but it seeds demo/seed_demo_data.py's SYNTHETIC
scenario - and every traffic-metric endpoint deliberately filters
data_source='DEMO_SYNTHETIC' out (see ObservationStore.all_observations),
so the deployed dashboard honestly reported 0 vehicles and 0/7 cameras to
anyone who opened it.

This export is the honest alternative: real pipeline output over real
Indian number plates, replayed into the empty database on startup (see
demo/recorded_session.py). No observation is invented; the only thing that
moves is the clock, because a recorded session has to be anchored to the
current time to be visible to the "recent activity" queries.

Usage (from the repo root, against a local outputs/results/observations.db):

    python demo/export_recorded_session.py

Row selection keeps the showcase intact: every observation from the
multi-camera journeys, plus an even per-camera sample of the remaining
city-wide traffic so the dashboard has realistic volume. Appearance
vectors are rounded to 2 decimals (the fusion engine only needs cosine
similarity) which cuts the file from ~30 MB to well under a megabyte
without changing any match decision.
"""

import argparse
import gzip
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Works whether this is run as `python demo/export_recorded_session.py` or
# `python -m demo.export_recorded_session` from the repo root.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import PROJECT_ROOT, DB_PATH_STR

OUT_PATH = PROJECT_ROOT / "demo" / "recorded_session.json.gz"

# Columns carried into the export. Deliberately excludes `id` (reassigned on
# insert), absolute timestamps (stored as offsets so the replay can anchor
# them), and the annotated/crop media paths (those files are not shipped, so
# a null is more honest than a URL that 404s).
COLUMNS = [
    "plate_text", "confidence", "camera_id", "lat", "long",
    "appearance_vector", "track_id", "vehicle_type", "source_file",
    "source_type", "frame_index", "vehicle_bbox", "vehicle_confidence",
    "plate_bbox", "raw_plate_text", "ocr_confidence", "plate_status",
    "plate_status_reason", "normalized_plate", "direction", "data_source",
    "plate_confidence", "first_seen_frame", "last_seen_frame",
    "plate_quality_score", "blur_score", "brightness_score",
    "contrast_score", "preprocessing_mode", "ocr_candidate_count",
    "temporal_support", "final_fusion_score", "plate_state",
]

PER_CAMERA_SAMPLE = 110

# Appearance vectors are the bulk of the database (~30 MB of the 36 MB
# observations.db). The fusion engine can still link plates without them
# (plate + temporal + spatial signals), so the export keeps vectors only for
# the vehicles whose multi-camera journeys are actually demonstrated in the
# UI. That is what keeps this dataset committable instead of a 2+ MB blob.
KEEP_VECTORS_FOR_JOURNEYS_ONLY = True


def _journey_windows(rows):
    """Find (plate, camera) sets that form a real multi-camera journey.

    A plate counts as a journey when the same plate was read on more than one
    camera. Every observation of that plate is kept, so the exported data
    still contains the continuous pass the trajectory engine links.
    """
    cameras_by_plate = defaultdict(set)
    for row in rows:
        plate = row["normalized_plate"] or row["plate_text"]
        if plate:
            cameras_by_plate[plate].add(row["camera_id"])
    return {plate for plate, cams in cameras_by_plate.items() if len(cams) >= 2}


def build(db_path: str, per_camera: int = PER_CAMERA_SAMPLE):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM observations "
            "WHERE data_source != 'DEMO_SYNTHETIC' "
            "ORDER BY timestamp"
        )
    ]
    conn.close()
    if not rows:
        raise SystemExit("No REAL_INFERENCE observations found in %s" % db_path)

    journeys = _journey_windows(rows)
    kept = {}
    for row in rows:
        plate = row["normalized_plate"] or row["plate_text"]
        if plate in journeys:
            kept[row["id"]] = row

    # Every real observation is exported so dashboard volume, hourly density
    # and per-camera counts are the genuine recorded numbers, not a sample.
    for row in rows:
        kept.setdefault(row["id"], row)

    ordered = sorted(kept.values(), key=lambda r: r["timestamp"])
    start = datetime.fromisoformat(ordered[0]["timestamp"])
    exported = []
    for row in ordered:
        item = {}
        for col in COLUMNS:
            if col not in row:
                continue
            item[col] = row[col]
        if item.get("appearance_vector"):
            plate = item.get("normalized_plate") or item.get("plate_text")
            if KEEP_VECTORS_FOR_JOURNEYS_ONLY and plate not in journeys:
                item["appearance_vector"] = None
            else:
                item["appearance_vector"] = [
                    round(float(v), 2) for v in json.loads(item["appearance_vector"])
                ]
        item["t_offset_s"] = round(
            (datetime.fromisoformat(row["timestamp"]) - start).total_seconds(), 3
        )
        exported.append(item)

    meta = {
        "dataset": "TrackX recorded multi-camera session",
        "provenance": (
            "REAL_INFERENCE observations produced by running the repo's real "
            "YOLO vehicle detector + plate detector + OCR pipeline over the "
            "seven recorded Indian city-camera feeds. Not synthetic."
        ),
        "source_db": "outputs/results/observations.db",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "session_start": ordered[0]["timestamp"],
        "session_end": ordered[-1]["timestamp"],
        "observation_count": len(exported),
        "journey_plates": sorted(journeys),
        "cameras": sorted({r["camera_id"] for r in exported}),
        "plate_count": len({r["normalized_plate"] or r["plate_text"] for r in exported}),
    }
    return {"meta": meta, "observations": exported}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DB_PATH_STR)
    parser.add_argument("--out", default=str(OUT_PATH))
    parser.add_argument("--per-camera", type=int, default=PER_CAMERA_SAMPLE)
    args = parser.parse_args()

    payload = build(args.db, per_camera=args.per_camera)
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wb", compresslevel=9) as handle:
        handle.write(raw)

    meta = payload["meta"]
    print("wrote %s" % out_path)
    print("  observations : %d" % meta["observation_count"])
    print("  cameras      : %s" % ", ".join(meta["cameras"]))
    print("  plates       : %d (journeys: %s)" % (meta["plate_count"], ", ".join(meta["journey_plates"])))
    print("  session      : %s -> %s" % (meta["session_start"], meta["session_end"]))
    print("  json %.2f MB -> gzip %.2f MB" % (len(raw) / 1e6, out_path.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
