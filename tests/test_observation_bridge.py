"""
tests/test_observation_bridge.py

Day 2 (SIH26127): tests for the bridge from demo/visual_pipeline.py's flat
observation schema into database/observation_store.py's ObservationStore -
this is the piece that was explicitly missing ("CRITICAL CURRENT GAP").

No ultralytics/paddleocr/torch dependency - these tests exercise the
storage/mapping layer directly with plain dicts, same style as the existing
Day-1 tests' stub classes.

Run with:
    python -m unittest discover -s tests -p "test_*.py" -v
or just this file:
    python -m unittest tests.test_observation_bridge -v
"""
import json
import os
import shutil
import tempfile
import unittest

from database.observation_store import ObservationStore, database_file_exists
from intelligence.trajectory import build_trajectories
from intelligence.alerts import scan_trajectories_for_alerts


def _visual_obs(camera_id="CAM_01", timestamp="2026-01-01T09:00:00",
                 plate_status="detected", normalized_plate_text="TN10AB1234",
                 raw_plate_text="TN10AB1234", ocr_confidence=0.9,
                 vehicle_class="car", vehicle_confidence=0.8, track_id=3,
                 appearance_vector=None, **overrides):
    """Builds one flat observation dict matching demo/visual_pipeline.py's
    real schema, without importing that module (avoids the ultralytics/
    paddleocr/torch dependency this test suite shouldn't need)."""
    obs = {
        "camera_id": camera_id,
        "timestamp": timestamp,
        "source_file": "data/cameras/CAM_01/images/sample.jpg",
        "source_type": "image",
        "frame_index": None,
        "vehicle_bbox": [10, 10, 100, 100],
        "vehicle_class": vehicle_class,
        "vehicle_confidence": vehicle_confidence,
        "track_id": track_id,
        "plate_bbox": [5, 5, 40, 20] if plate_status in ("detected", "detected_no_ocr", "ocr_failed") else None,
        "raw_plate_text": raw_plate_text if plate_status == "detected" else None,
        "normalized_plate_text": normalized_plate_text if plate_status == "detected" else None,
        "ocr_confidence": ocr_confidence if plate_status == "detected" else None,
        "plate_status": plate_status,
        "plate_status_reason": None if plate_status == "detected" else ("no plate detector configured" if plate_status == "unavailable" else None),
        "annotated_output": "outputs/results/annotated/CAM_01_sample_annotated.jpg",
        "plate_crop_path": "outputs/results/plate_crops/test.jpg" if plate_status in ("detected", "detected_no_ocr", "ocr_failed") else None,
        "normalized_plate": normalized_plate_text if plate_status == "detected" else None,
        "appearance_vector": appearance_vector,
    }
    obs.update(overrides)
    return obs


class TestObservationStoreMigration(unittest.TestCase):
    """The new visual-pipeline columns must appear on a schema that
    predates them, without ever breaking the original 9 columns/methods."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migration_adds_visual_columns(self):
        store = ObservationStore(db_path=self.db_path)
        cols = {row[1] for row in store.conn.execute("PRAGMA table_info(observations)")}
        store.close()
        for expected in ("source_file", "vehicle_bbox", "plate_status",
                          "ocr_confidence", "annotated_output"):
            self.assertIn(expected, cols)

    def test_migration_is_idempotent(self):
        # opening the store twice against the same db must not raise
        # "duplicate column name"
        store1 = ObservationStore(db_path=self.db_path)
        store1.close()
        store2 = ObservationStore(db_path=self.db_path)  # would raise if _migrate() weren't idempotent
        store2.close()

    def test_original_add_method_still_works_unmodified(self):
        store = ObservationStore(db_path=self.db_path)
        store.add({
            "plate_text": "TN10AB1234", "confidence": 0.9, "camera_id": "CAM_01",
            "timestamp": "2026-01-01T00:00:00", "lat": 13.08, "long": 80.27,
        })
        rows = store.all_observations()
        store.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["plate_text"], "TN10AB1234")
        # new columns should just be NULL for a row written the old way
        self.assertIsNone(rows[0]["source_file"])


class TestVisualObservationBridge(unittest.TestCase):
    """The actual bridge: flat visual-pipeline dict -> a real row the
    intelligence layer can consume, with no plate/vehicle data fabricated."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        self.store = ObservationStore(db_path=self.db_path)

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detected_plate_maps_correctly(self):
        obs = _visual_obs(plate_status="detected", normalized_plate_text="TN10AB1234",
                           raw_plate_text="TN1O AB1234", ocr_confidence=0.87)
        self.store.add_visual_observation(obs)
        row = self.store.all_observations()[0]

        self.assertEqual(row["plate_text"], "TN10AB1234")       # what fusion/matching compares
        self.assertEqual(row["raw_plate_text"], "TN1O AB1234")  # raw OCR never discarded
        self.assertEqual(row["confidence"], 0.87)
        self.assertEqual(row["camera_id"], "CAM_01")
        self.assertEqual(row["vehicle_type"], "car")
        self.assertEqual(json.loads(row["vehicle_bbox"]), [10, 10, 100, 100])

    def test_undetected_plate_never_fabricates_a_plate_value(self):
        """This is the core honesty requirement: a vehicle with no
        real plate reading must land in the db as no-plate, not as
        some placeholder/guessed value, and must not crash matching."""
        obs = _visual_obs(plate_status="unavailable")
        self.store.add_visual_observation(obs)
        row = self.store.all_observations()[0]

        self.assertIsNone(row["plate_text"])
        self.assertIsNone(row["raw_plate_text"])
        self.assertEqual(row["confidence"], 0.0)  # never None - see mapping docstring
        self.assertEqual(row["plate_status"], "unavailable")
        self.assertIsNotNone(row["plate_status_reason"])

    def test_lat_long_looked_up_from_camera_network_when_not_given(self):
        obs = _visual_obs(camera_id="CAM_02")
        self.store.add_visual_observation(obs)
        row = self.store.all_observations()[0]
        # Updated to use actual Coimbatore coordinates from camera network
        self.assertAlmostEqual(row["lat"], 11.0167, places=3)
        self.assertAlmostEqual(row["long"], 76.9707, places=3)

    def test_bulk_write_returns_count_and_all_rows_present(self):
        obs_list = [_visual_obs(camera_id=c, plate_status="plate_not_detected") for c in ("CAM_01", "CAM_02", "CAM_03")]
        n = self.store.add_visual_observations(obs_list)
        self.assertEqual(n, 3)
        self.assertEqual(len(self.store.all_observations()), 3)

    def test_bridged_observations_flow_through_trajectory_and_alerts_without_crash(self):
        """The full downstream chain (Task 6): observation -> ObservationStore
        -> build_trajectories -> scan_trajectories_for_alerts must not care
        whether a row came from the old pipeline.py or the new visual bridge."""
        self.store.add_visual_observation(
            _visual_obs(camera_id="CAM_01", timestamp="2026-01-01T09:00:00",
                        plate_status="detected", normalized_plate_text="TN99ZZ0000")
        )
        self.store.add_visual_observation(
            _visual_obs(camera_id="CAM_02", timestamp="2026-01-01T09:02:30",
                        plate_status="detected", normalized_plate_text="TN99ZZ0000")
        )
        rows = self.store.all_observations()
        trajs = build_trajectories(rows)   # must not raise
        alerts = scan_trajectories_for_alerts(trajs)  # must not raise
        self.assertIsInstance(trajs, list)
        self.assertIsInstance(alerts, list)


class TestDatabaseFileExists(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "results", "observations.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_false_before_any_store_created(self):
        self.assertFalse(database_file_exists(self.db_path))

    def test_true_after_store_created(self):
        store = ObservationStore(db_path=self.db_path)
        store.close()
        self.assertTrue(database_file_exists(self.db_path))

    def test_checking_existence_does_not_itself_create_the_file(self):
        database_file_exists(self.db_path)  # just checking
        self.assertFalse(os.path.exists(self.db_path))


class TestRealCam01Fixture(unittest.TestCase):
    """
    Uses the ACTUAL JSON output already produced by a real YOLO run on the
    user's machine (outputs/results/CAM_01_visual_results.json) as a fixture -
    proof the bridge works against genuine detector output, not just
    hand-built synthetic dicts. Skips gracefully if that file isn't present
    (e.g. a clean checkout that hasn't run the pipeline yet).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from config import RESULTS_DIR
        self.FIXTURE = str(RESULTS_DIR / "CAM_01_visual_results.json")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_real_yolo_output_reaches_the_database(self):
        if not os.path.isfile(self.FIXTURE):
            self.skipTest(f"{self.FIXTURE} not present - run demo.visual_pipeline first")

        with open(self.FIXTURE) as f:
            real_observations = json.load(f)

        store = ObservationStore(db_path=self.db_path)
        n = store.add_visual_observations(real_observations)
        rows = store.all_observations()
        store.close()

        self.assertEqual(n, len(real_observations))
        self.assertEqual(len(rows), len(real_observations))
        if rows:
            # must be able to run the full intelligence chain on real data
            trajs = build_trajectories(rows)
            self.assertIsInstance(trajs, list)


if __name__ == "__main__":
    unittest.main()
