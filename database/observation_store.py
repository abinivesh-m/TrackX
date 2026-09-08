"""
observation_store.py

stores every plate observation coming out of the Day-1 pipeline (pipeline.py)
into a sqlite db so the trajectory engine can query across cameras later.

schema matches what pipeline.py already outputs, plus an auto id and
an optional appearance_vector column (json-encoded list of floats).

DAY 2 (SIH26127): the real visual pipeline (demo/visual_pipeline.py) produces
a richer flat observation per vehicle - full detection provenance (bbox,
detection confidence, source file/frame, raw vs normalized plate text, plate
detector status, annotated frame path), not just the plate_text/confidence
this table was originally sized for. Rather than a second table/database,
_migrate() adds those columns to the SAME observations table (idempotent -
safe to call on an existing db that predates them), and add_visual_observation()
maps the visual pipeline's flat dict onto this schema. Every original
column/method (add/add_many/all_observations/by_plate) is untouched, so
anything already writing plain records keeps working exactly as before.
"""

import sqlite3
import json
import os
from datetime import datetime

from network.camera_network import CAMERAS
from config import DB_PATH_STR

# columns beyond the original Day-1 set (plate_text, confidence, camera_id,
# timestamp, lat, long, appearance_vector, track_id, vehicle_type), added by
# the Day-2 visual-pipeline bridge. All nullable - a row from the original
# pipeline simply has NULLs here.
_VISUAL_COLUMNS = {
    "source_file": "TEXT",
    "source_type": "TEXT",
    "frame_index": "INTEGER",
    "vehicle_bbox": "TEXT",         # JSON-encoded [x1,y1,x2,y2]
    "vehicle_confidence": "REAL",
    "plate_bbox": "TEXT",           # JSON-encoded [x1,y1,x2,y2], FRAME coordinates
    "raw_plate_text": "TEXT",       # OCR output BEFORE normalization - never discarded
    "ocr_confidence": "REAL",
    "plate_status": "TEXT",         # "detected" | "plate_not_detected" | "unavailable" | "detected_no_ocr" | "ocr_failed"
    "plate_status_reason": "TEXT",
    "annotated_output": "TEXT",     # path to the annotated frame this observation came from
    "normalized_plate": "TEXT",     # normalized plate text (without IND artifacts)
}

# Day 3 (SIH26127): fields pipeline.run_video_to_db() writes that don't map
# onto _VISUAL_COLUMNS above - kept as a SEPARATE dict on purpose, so
# add_visual_observation()'s hardcoded value tuple (built against
# _VISUAL_COLUMNS specifically) doesn't silently go out of sync with the
# column list again, the way it just did when these were added to that dict
# directly. add() (below) is the only method that writes these.
_DAY3_COLUMNS = {
    "source": "TEXT",                # the video/image path this observation came from
    "direction": "TEXT",             # coarse movement direction estimate, or
                                      # "stationary_or_unclear" / "unknown"
}

# SIH Requirement: Data source tagging for real vs synthetic data
_DATA_SOURCE_COLUMNS = {
    "data_source": "TEXT",           # "REAL_INFERENCE" or "SYNTHETIC_DEMO"
}

# Day 4 (SIH26127): plate crop path for separate zoom display
_DAY4_COLUMNS = {
    "plate_crop_path": "TEXT",      # path to saved plate-only crop image
}

# Video-ingest demo flow (SIH26127): the plate DETECTOR's own confidence
# (bbox detection score) was already computed by pipeline.run_video_to_db()
# and discarded - only ocr_confidence (the OCR text-reading confidence) was
# kept, which is a different number. Captured here as its own column rather
# than overloading ocr_confidence.
_PLATE_DETECTOR_COLUMNS = {
    "plate_confidence": "REAL",     # plate detector bbox confidence, NOT ocr_confidence
}


class ObservationStore:
    def __init__(self, db_path=None):
        db_path = db_path or DB_PATH_STR
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_table()
        self._migrate()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_text TEXT,
                confidence REAL,
                camera_id TEXT,
                timestamp TEXT,
                lat REAL,
                long REAL,
                appearance_vector TEXT,
                track_id TEXT,
                vehicle_type TEXT
            )
        """)
        self.conn.commit()

    def _migrate(self):
        """Adds any _VISUAL_COLUMNS / _DAY3_COLUMNS / _DAY4_COLUMNS / _DATA_SOURCE_COLUMNS missing from an existing
        table. Safe to call every time __init__ runs - checks PRAGMA
        table_info first, so it never tries to re-add a column that's
        already there (which sqlite would reject with 'duplicate column
        name')."""
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(observations)")}
        for col, sqltype in {**_VISUAL_COLUMNS, **_DAY3_COLUMNS, **_DAY4_COLUMNS, **_DATA_SOURCE_COLUMNS, **_PLATE_DETECTOR_COLUMNS}.items():
            if col not in existing:
                self.conn.execute(f"ALTER TABLE observations ADD COLUMN {col} {sqltype}")
        self.conn.commit()
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Creates indexes on commonly-searched columns if they don't already exist.
        Safe to call multiple times - uses CREATE INDEX IF NOT EXISTS.
        Indexes optimize:
        - trajectory search by plate_text
        - analytics queries by camera_id and timestamp
        - combined plate+timestamp queries for multi-camera trajectory linking
        """
        indexes = [
            ("idx_plate_text", "plate_text"),
            ("idx_camera_id", "camera_id"),
            ("idx_timestamp", "timestamp"),
            ("idx_plate_timestamp", "plate_text, timestamp"),
            ("idx_camera_timestamp", "camera_id, timestamp"),
        ]
        for idx_name, idx_columns in indexes:
            self.conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON observations({idx_columns})")
        self.conn.commit()

    def add(self, record, appearance_vector=None):
        """
        Writes one observation. Original columns (plate_text, confidence,
        camera_id, timestamp, lat, long, appearance_vector, track_id,
        vehicle_type) are always written from `record`.

        Day 3 (SIH26127): additionally writes vehicle_bbox, plate_bbox,
        vehicle_confidence, frame_index, normalized_plate, source, direction
        IF the record dict contains them - callers that don't set these
        (e.g. demo/seed_demo_data.py, older code) simply get NULLs there,
        exactly as before. This keeps add()/add_many() backward compatible
        while letting pipeline.run_video_to_db() persist full provenance.

        Day 4 (SIH26127): additionally writes plate_crop_path for separate zoom display.
        Day 4.5 (SIH26127): additionally writes raw_plate_text and ocr_confidence for pipeline.
        """
        extra_keys = ["vehicle_bbox", "plate_bbox", "vehicle_confidence",
                      "frame_index", "source", "direction", "plate_crop_path",
                      "raw_plate_text", "ocr_confidence", "data_source",
                      "plate_confidence"]
        extra_values = []
        for key in extra_keys:
            val = record.get(key)
            if key in ("vehicle_bbox", "plate_bbox") and val is not None:
                val = json.dumps(val)
            extra_values.append(val)

        self.conn.execute(f"""
            INSERT INTO observations
            (plate_text, confidence, camera_id, timestamp, lat, long, appearance_vector,
             track_id, vehicle_type, {", ".join(extra_keys)}, normalized_plate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, {", ".join(["?"] * len(extra_keys))}, ?)
        """, (
            record["plate_text"],
            record["confidence"],
            record["camera_id"],
            record["timestamp"],
            record["lat"],
            record["long"],
            json.dumps(appearance_vector) if appearance_vector else None,
            record.get("track_id"),
            record.get("vehicle_type"),
            *extra_values,
            record.get("normalized_plate"),
        ))
        self.conn.commit()

    def add_many(self, records, appearance_vectors=None):
        appearance_vectors = appearance_vectors or [None] * len(records)
        for r, av in zip(records, appearance_vectors):
            self.add(r, av)

    def add_visual_observation(self, obs, appearance_vector=None, lat=None, long=None):
        """
        Maps ONE flat vehicle observation from demo/visual_pipeline.py's
        schema (see that module's docstring) onto this table and inserts it -
        this is the "bridge" that was missing: real detections previously
        only ever reached outputs/results/CAM_0X_visual_results.json and
        stopped there.

        Field mapping (visual-pipeline schema -> this table):
            normalized_plate_text -> plate_text   (what the fuzzy plate
                matcher/fusion engine compares against; raw text is kept
                separately in raw_plate_text, never discarded)
            ocr_confidence         -> confidence   (0.0, not NULL, when no
                plate was read - fusion.py does arithmetic on this field,
                e.g. `obs.get("confidence", 1.0) + ...`, which would raise
                on None; 0.0 correctly means "no OCR evidence" and just
                zeroes out this observation's plate weight in matching)
            vehicle_class          -> vehicle_type
            everything else (source_file, source_type, frame_index,
                vehicle_bbox, vehicle_confidence, plate_bbox, plate_status,
                plate_status_reason, annotated_output, plate_crop_path) lands in the matching
                new column, JSON-encoding bbox lists.

        lat/long: if not given explicitly, looked up from
        network.camera_network.CAMERAS by camera_id (falls back to None,
        None for a camera_id not in that bootstrap dict - GIS display just
        won't be able to plot it, everything else still works).
        """
        camera_id = obs["camera_id"]
        if lat is None or long is None:
            cam_info = CAMERAS.get(camera_id, {})
            lat = lat if lat is not None else cam_info.get("lat")
            long = long if long is not None else cam_info.get("long")

        self.conn.execute(f"""
            INSERT INTO observations
            (plate_text, confidence, camera_id, timestamp, lat, long, appearance_vector,
             track_id, vehicle_type, {", ".join(_VISUAL_COLUMNS.keys())}, plate_crop_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, {", ".join(["?"] * len(_VISUAL_COLUMNS))}, ?)
        """, (
            obs.get("normalized_plate_text"),
            obs.get("ocr_confidence") or 0.0,
            camera_id,
            obs["timestamp"],
            lat,
            long,
            json.dumps(appearance_vector) if appearance_vector else None,
            str(obs["track_id"]) if obs.get("track_id") is not None else None,
            obs.get("vehicle_class"),
            obs.get("source_file"),
            obs.get("source_type"),
            obs.get("frame_index"),
            json.dumps(obs["vehicle_bbox"]) if obs.get("vehicle_bbox") is not None else None,
            obs.get("vehicle_confidence"),
            json.dumps(obs["plate_bbox"]) if obs.get("plate_bbox") is not None else None,
            obs.get("raw_plate_text"),
            obs.get("ocr_confidence"),
            obs.get("plate_status"),
            obs.get("plate_status_reason"),
            obs.get("annotated_output"),
            obs.get("normalized_plate"),  # Now part of _VISUAL_COLUMNS
            obs.get("plate_crop_path"),  # Separate field, not in _VISUAL_COLUMNS
        ))
        self.conn.commit()

    def add_visual_observations(self, observations):
        """Bulk version of add_visual_observation(); appearance_vector is
        read from each obs dict's own 'appearance_vector' field (see
        demo/visual_pipeline.py, which computes it from the vehicle crop).
        Returns the count actually inserted."""
        n = 0
        for obs in observations:
            self.add_visual_observation(obs, appearance_vector=obs.get("appearance_vector"))
            n += 1
        return n

    def all_observations(self):
        cur = self.conn.execute("SELECT * FROM observations ORDER BY timestamp")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def by_plate(self, plate_text):
        cur = self.conn.execute(
            "SELECT * FROM observations WHERE plate_text = ? ORDER BY timestamp",
            (plate_text,)
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def by_camera_and_timestamp(self, camera_id, start_timestamp, end_timestamp):
        """Query observations by camera and time range using indexes.
        Used for analytics and trajectory queries."""
        cur = self.conn.execute(
            "SELECT * FROM observations WHERE camera_id = ? AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
            (camera_id, start_timestamp, end_timestamp)
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def recent_observations(self, limit=1000):
        """Get the most recent observations, limited by count (for dashboard caching)."""
        cur = self.conn.execute(
            "SELECT * FROM observations ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return list(reversed([dict(zip(cols, row)) for row in rows]))  # Reverse to get chronological order

    def delete_camera_observations(self, camera_id):
        """Delete generated observations for one camera before a fresh demo run."""
        cur = self.conn.execute("DELETE FROM observations WHERE camera_id = ?", (camera_id,))
        self.conn.commit()
        return cur.rowcount

    def close(self):
        self.conn.close()


def database_file_exists(db_path=None):
    """Checks whether the db file exists ON DISK, WITHOUT creating it (unlike
    instantiating ObservationStore, which always creates the file/table).
    Lets the dashboard show a clean 'no database yet' state."""
    if db_path is None:
        db_path = DB_PATH_STR
    return os.path.exists(db_path)


if __name__ == "__main__":
    # quick manual test
    from config import RESULTS_DIR
    test_db_path = str(RESULTS_DIR / "test_observations.db")
    store = ObservationStore(db_path=test_db_path)
    store.add({
        "plate_text": "TN10AB1234",
        "confidence": 0.9,
        "camera_id": "CAM_01",
        "timestamp": datetime.now().isoformat(),
        "lat": 13.0827,
        "long": 80.2707,
    })
    print(store.all_observations())
    store.close()
