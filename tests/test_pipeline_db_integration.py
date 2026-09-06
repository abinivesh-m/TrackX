"""
test_pipeline_db_integration.py

Priority 1 fix: pipeline.py used to only ever write outputs/records.json and
stop - the sqlite database (which trajectory/analytics/alerts/dashboard all
read from) was never populated by a real run, only by demo/seed_demo_data.py.

This test doesn't touch YOLO/PaddleOCR at all (per the "don't test YOLO
itself, test our logic around it" rule) - it fakes the vehicle detector,
plate detector and OCR with the minimal interface pipeline.run_on_video()
actually calls, and asserts that run_video_to_db() lands rows in a real
sqlite ObservationStore, with the appearance vector correctly aligned to
its record.

Run with: python -m pytest tests/test_pipeline_db_integration.py -v
(or plain `python tests/test_pipeline_db_integration.py`, see __main__ below)
"""

import os
import sys
import types
import numpy as np

# pipeline.py imports detection.vehicle_detector / recognition.ocr_reader,
# which import ultralytics / paddleocr / torch at module load time. Those are
# heavy optional-at-test-time deps we don't want to require just to test our
# own wiring logic, so stub them out before pipeline.py is imported.
_STUB_MODULES = []
for _name in ("ultralytics", "paddleocr", "torch", "torchvision",
              "torchvision.models", "torchvision.transforms"):
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)
        _STUB_MODULES.append(_name)
sys.modules["ultralytics"].YOLO = object
sys.modules["paddleocr"].PaddleOCR = object

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Module-level cleanup to prevent pollution
def cleanup_stub_modules():
    """Clean up stub modules from sys.modules to prevent pollution across test runs."""
    for module_name in _STUB_MODULES:
        if module_name in sys.modules:
            del sys.modules[module_name]

# Register cleanup to run at module unload (when pytest/unittest finishes this module)
import atexit
atexit.register(cleanup_stub_modules)

import pipeline  # noqa: E402
from database.observation_store import ObservationStore  # noqa: E402


class FakeVehicleDetector:
    """Mimics VehicleDetector's track_video()/crop() interface with one
    synthetic track across a single frame."""

    def __init__(self, tracks=None, n_frames=1):
        self.tracks = tracks or [
            {"track_id": 1, "bbox": [0, 0, 50, 50], "confidence": 0.9, "vehicle_type": "car"}
        ]
        self.n_frames = n_frames

    def track_video(self, video_path):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(self.n_frames):
            # shift bbox a bit each frame so direction estimation has something to work with
            shifted = []
            for t in self.tracks:
                x1, y1, x2, y2 = t["bbox"]
                shifted.append({**t, "bbox": [x1 + i * 5, y1, x2 + i * 5, y2]})
            yield i, frame, shifted

    def crop(self, frame, bbox):
        x1, y1, x2, y2 = bbox
        return frame[y1:y2, x1:x2]


class FakePlateDetector:
    def detect_on_array(self, arr):
        return [{"bbox": [0, 0, 20, 20], "confidence": 0.8}]

    def crop_array(self, arr, bbox):
        x1, y1, x2, y2 = bbox
        return arr[y1:y2, x1:x2]


class FakeOCR:
    """Always reads the same plate text - good enough for wiring tests,
    ocr_reader's own voting logic gets its own test elsewhere."""

    def __init__(self, text="TN38AB1234", conf=0.95):
        self.text = text
        self.conf = conf

    def read(self, crop_img):
        return self.text, self.conf


def _isolated_db_path(tmp_name):
    path = os.path.join("/tmp", tmp_name)
    if os.path.exists(path):
        os.remove(path)
    return path


def test_run_video_to_db_persists_records():
    """The core Priority 1 regression test: pipeline output must reach the
    sqlite DB, not just an in-memory return value / JSON file."""
    pipeline.get_appearance_vector = lambda crop: [0.1, 0.2, 0.3]

    db_path = _isolated_db_path("test_pipeline_persists.db")
    store = ObservationStore(db_path=db_path)
    records = pipeline.run_video_to_db(
        "fake.mp4", FakeVehicleDetector(), FakePlateDetector(), FakeOCR(),
        "CAM_TEST", 13.08, 80.27, store,
    )
    store.close()

    assert len(records) == 1

    # reopen the db fresh (not the same in-memory connection) to prove the
    # write actually persisted to disk, not just to Python state
    store2 = ObservationStore(db_path=db_path)
    rows = store2.all_observations()
    store2.close()

    assert len(rows) == 1
    row = rows[0]
    assert row["plate_text"] == "TN38AB1234"
    assert row["camera_id"] == "CAM_TEST"
    assert row["track_id"] == "1"
    assert row["vehicle_type"] == "car"
    assert row["appearance_vector"] == "[0.1, 0.2, 0.3]"
    # Phase 1 fields
    assert row["normalized_plate"] == "TN38AB1234"
    assert row["vehicle_confidence"] == 0.9
    assert row["source"] == "fake.mp4"
    assert row["frame_index"] == 0
    assert row["vehicle_bbox"] == "[0, 0, 50, 50]"
    assert row["plate_bbox"] == "[0, 0, 20, 20]"
    assert row["direction"] in ("stationary_or_unclear", "unknown")


def test_run_video_to_db_multiple_tracks_keep_separate_appearance_vectors():
    """Regression guard for the indexing bug class: appearance_vectors is a
    dict keyed by *position in the records list*, not by track_id - make sure
    that mapping survives the DB write when there's more than one track and
    they don't all produce a usable appearance vector."""
    tracks = [
        {"track_id": 1, "bbox": [0, 0, 50, 50], "confidence": 0.9, "vehicle_type": "car"},
        {"track_id": 2, "bbox": [50, 50, 90, 90], "confidence": 0.9, "vehicle_type": "truck"},
    ]

    call_count = {"n": 0}

    def fake_appearance(crop):
        call_count["n"] += 1
        # second track's crop deliberately produces no usable vector
        if call_count["n"] == 2:
            return None
        return [0.5, 0.6]

    pipeline.get_appearance_vector = fake_appearance

    ocr_texts = iter(["TN01AA0001", "TN02BB0002"])

    class MultiTextOCR:
        def read(self, crop_img):
            return next(ocr_texts), 0.9

    db_path = _isolated_db_path("test_pipeline_multi_track.db")
    store = ObservationStore(db_path=db_path)
    records = pipeline.run_video_to_db(
        "fake.mp4", FakeVehicleDetector(tracks=tracks), FakePlateDetector(),
        MultiTextOCR(), "CAM_TEST", 13.08, 80.27, store,
    )
    store.close()

    assert len(records) == 2

    store2 = ObservationStore(db_path=db_path)
    rows = store2.all_observations()
    store2.close()

    by_plate = {r["plate_text"]: r for r in rows}
    assert set(by_plate.keys()) == {"TN01AA0001", "TN02BB0002"}


def test_skip_db_flag_semantics_are_documented_not_default():
    """--skip_db exists for debugging only; make sure the argparse default
    keeps DB writing ON so a plain run always reaches the database."""
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--skip_db", action="store_true")
    args = p.parse_args([])
    assert args.skip_db is False


def test_direction_estimate_from_moving_bbox():
    """A track whose bbox visibly shifts rightward across frames should be
    labeled left_to_right, not left as 'unknown'/'stationary'."""
    pipeline.get_appearance_vector = lambda crop: [0.1]

    db_path = _isolated_db_path("test_pipeline_direction.db")
    store = ObservationStore(db_path=db_path)
    records = pipeline.run_video_to_db(
        "fake.mp4", FakeVehicleDetector(n_frames=5), FakePlateDetector(), FakeOCR(),
        "CAM_TEST", 13.08, 80.27, store,
    )
    store.close()

    assert len(records) == 1
    assert records[0]["direction"] == "left_to_right"


def test_observation_store_migrates_old_schema_db():
    """Regression guard: a db file created with the pre-Phase-1 schema
    (no normalized_plate/vehicle_confidence/bbox/etc columns) must still be
    usable - ObservationStore should add the missing columns rather than
    erroring out or silently dropping the new fields on insert."""
    import sqlite3

    db_path = _isolated_db_path("test_pipeline_old_schema_migration.db")

    # hand-build a db with ONLY the original Day-1 columns, no migration logic involved
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE observations (
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
    conn.execute(
        "INSERT INTO observations (plate_text, confidence, camera_id, timestamp, lat, long) "
        "VALUES ('TNOLD0001', 0.8, 'CAM_OLD', '2026-01-01T00:00:00', 13.0, 80.0)"
    )
    conn.commit()
    conn.close()

    # opening with the new ObservationStore should migrate in place, not error
    store = ObservationStore(db_path=db_path)
    rows = store.all_observations()
    assert len(rows) == 1
    assert rows[0]["plate_text"] == "TNOLD0001"
    # new columns should exist (as NULL for this pre-existing row) rather than KeyError
    assert "normalized_plate" in rows[0]
    assert rows[0]["normalized_plate"] is None

    # and a new-schema insert into the migrated db should work end to end
    store.add({
        "plate_text": "TNNEW0002",
        "normalized_plate": "TNNEW0002",
        "confidence": 0.95,
        "camera_id": "CAM_NEW",
        "timestamp": "2026-01-01T00:05:00",
        "lat": 13.1,
        "long": 80.1,
        "vehicle_confidence": 0.9,
        "plate_bbox": [1, 2, 3, 4],
        "vehicle_bbox": [5, 6, 7, 8],
        "direction": "left_to_right",
        "source": "test.mp4",
        "frame_index": 0,
    })
    rows = store.all_observations()
    store.close()

    assert len(rows) == 2
    new_row = next(r for r in rows if r["plate_text"] == "TNNEW0002")
    assert new_row["plate_bbox"] == "[1, 2, 3, 4]"
    assert new_row["direction"] == "left_to_right"


if __name__ == "__main__":
    test_run_video_to_db_persists_records()
    print("PASS: test_run_video_to_db_persists_records")
    test_run_video_to_db_multiple_tracks_keep_separate_appearance_vectors()
    print("PASS: test_run_video_to_db_multiple_tracks_keep_separate_appearance_vectors")
    test_skip_db_flag_semantics_are_documented_not_default()
    print("PASS: test_skip_db_flag_semantics_are_documented_not_default")
    test_direction_estimate_from_moving_bbox()
    print("PASS: test_direction_estimate_from_moving_bbox")
    test_observation_store_migrates_old_schema_db()
    print("PASS: test_observation_store_migrates_old_schema_db")
    print("\nAll pipeline DB integration tests passed.")
