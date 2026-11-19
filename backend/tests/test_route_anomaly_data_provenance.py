"""
backend/tests/test_route_anomaly_data_provenance.py

SIH26127 "Final Data Integrity" audit (2026-09-11) - regression tests for a
real Class D bug found while auditing route anomaly detection:

Route Anomaly Detection (backend/app/api/v1/route_anomaly.py) ran
detect_impossible_transitions() over a plate's ENTIRE observation history,
including demo/seed_demo_data.py's DEMO_SYNTHETIC rows (that script
deliberately seeds an "impossible transition" scenario, plate TN77IM9999,
to exercise exactly this detector), and persisted the result with no
data_source at all - route_anomalies had no such column. RouteAnomalyPage.tsx
then rendered every anomaly identically, with none of the "SYNTHETIC DEMO
SCENARIO" warning badge that VehiclesPage.tsx/TrajectoryMap.tsx already show
for the same underlying observations. An operator (or a judge) could see a
precise, real-looking "impossible travel" anomaly with no indication it was
demo-seeded, not a genuine live-camera detection.

Fixed by: adding a data_source column to route_anomalies (additive
migration, same PRAGMA table_info pattern as congestion_events.reason),
deriving it in _persist_impossible_transitions() from the two contributing
observations' own data_source fields (never guessed), and adding the same
warning badge to RouteAnomalyPage.tsx (verified separately by
tests/test_route_anomaly_frontend_labeling.py's regex scan, since this file
has no JS test runner available).

No ultralytics/paddleocr/torch dependency.
"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, _BACKEND_DIR)

from database.route_anomaly_store import RouteAnomalyStore
# app.main also does this sys.path setup (project_root + backend_path) on
# import, but inserting it here first keeps this file runnable standalone -
# route_anomaly.py itself is only ever importable as "app.api.v1..." (the
# backend/ dir is what's on sys.path as the package root, there is no
# backend/__init__.py making "backend" itself a package).
import app.api.v1.route_anomaly as route_anomaly_module

BASE_TIME = datetime(2026, 8, 24, 10, 0, 0)


def _obs(plate, camera, ts, data_source=None):
    obs = {
        "plate_text": plate,
        "normalized_plate": plate,
        "camera_id": camera,
        "timestamp": ts.isoformat(),
    }
    if data_source is not None:
        obs["data_source"] = data_source
    return obs


class TestRouteAnomalyStoreDataSourceMigration(unittest.TestCase):
    """Layer 1: the additive schema migration + persistence, in isolation
    from the detection logic."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migration_adds_data_source_column_and_preserves_existing_rows(self):
        import sqlite3
        # Build a pre-migration table (no data_source column) with one row,
        # matching the schema route_anomalies had before this fix.
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE route_anomalies (
                anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT NOT NULL,
                from_camera TEXT NOT NULL,
                to_camera TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'MEDIUM',
                status TEXT NOT NULL DEFAULT 'OPEN',
                anomaly_score REAL NOT NULL DEFAULT 0,
                unexpected_transition INTEGER NOT NULL DEFAULT 0,
                impossible_travel_time INTEGER NOT NULL DEFAULT 0,
                unreasonable_speed INTEGER NOT NULL DEFAULT 0,
                observed_speed_kmph REAL,
                expected_min_time REAL,
                distance_km REAL,
                reason TEXT,
                investigated_by TEXT,
                investigation_notes TEXT,
                resolution_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO route_anomalies
            (plate, from_camera, to_camera, timestamp, anomaly_type, anomaly_score,
             created_at, updated_at)
            VALUES ('TN10AB1234', 'CAM_01', 'CAM_02', '2026-01-01T00:00:00',
                    'IMPOSSIBLE_TRAVEL', 90, '2026-01-01T00:00:00', '2026-01-01T00:00:00')
        """)
        conn.commit()
        conn.close()

        # Opening a RouteAnomalyStore against this pre-existing db must not
        # raise "duplicate column name", and the old row must survive with
        # data_source NULL (not fabricated as REAL or DEMO).
        store = RouteAnomalyStore(db_path=self.db_path)
        cols = {row["name"] for row in store.conn.execute("PRAGMA table_info(route_anomalies)")}
        self.assertIn("data_source", cols)
        rows = store.list_anomalies()
        store.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["plate"], "TN10AB1234")
        self.assertIsNone(rows[0]["data_source"])

    def test_migration_is_idempotent(self):
        store1 = RouteAnomalyStore(db_path=self.db_path)
        store1.close()
        store2 = RouteAnomalyStore(db_path=self.db_path)  # would raise if not idempotent
        store2.close()

    def test_add_anomaly_persists_data_source_at_top_level(self):
        store = RouteAnomalyStore(db_path=self.db_path)
        anomaly_id, created = store.add_anomaly(
            plate="TN77IM9999", from_camera="CAM_01", to_camera="CAM_04",
            timestamp="2026-01-01T00:00:30", anomaly_type="IMPOSSIBLE_TRAVEL",
            anomaly_score=95.0, reason="test", data_source="DEMO_SYNTHETIC",
        )
        self.assertTrue(created)
        row = store.get_anomaly(anomaly_id)
        store.close()
        self.assertEqual(row["data_source"], "DEMO_SYNTHETIC")
        # must be a top-level field (matching hop.data_source elsewhere),
        # not nested inside details
        self.assertNotIn("data_source", row["details"])

    def test_add_anomaly_without_data_source_stores_none(self):
        store = RouteAnomalyStore(db_path=self.db_path)
        anomaly_id, _ = store.add_anomaly(
            plate="TN10AB1234", from_camera="CAM_01", to_camera="CAM_02",
            timestamp="2026-01-01T00:00:00", anomaly_type="UNREASONABLE_SPEED",
            anomaly_score=50.0, reason="test",
        )
        row = store.get_anomaly(anomaly_id)
        store.close()
        self.assertIsNone(row["data_source"])


class TestPersistImpossibleTransitionsLabelsDataSource(unittest.TestCase):
    """Layer 2: backend/app/api/v1/route_anomaly.py's
    _persist_impossible_transitions() must derive data_source from the two
    contributing observations, never guess or default to 'real'."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")

        # _persist_impossible_transitions() constructs RouteAnomalyStore()
        # with no args (the production default path) - redirect it to an
        # isolated temp db for this test, same monkeypatch-the-class
        # pattern backend/tests already uses for ObservationStore's
        # DB_PATH_STR (see test_demo_reliability.py's isolated_db fixture),
        # adapted because RouteAnomalyStore's db_path default is bound at
        # import time and a bare attribute patch wouldn't reach it.
        self._real_store_cls = route_anomaly_module.RouteAnomalyStore
        db_path = self.db_path

        class _IsolatedRouteAnomalyStore(self._real_store_cls):
            def __init__(self_inner):
                super().__init__(db_path=db_path)

        route_anomaly_module.RouteAnomalyStore = _IsolatedRouteAnomalyStore

    def tearDown(self):
        route_anomaly_module.RouteAnomalyStore = self._real_store_cls
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stored_anomalies(self):
        store = self._real_store_cls(db_path=self.db_path)
        rows = store.list_anomalies()
        store.close()
        return rows

    def test_labels_demo_synthetic_when_either_contributing_observation_is_synthetic(self):
        observations = [
            _obs("TN77IM9999", "CAM_01", BASE_TIME, data_source="DEMO_SYNTHETIC"),
            _obs("TN77IM9999", "CAM_04", BASE_TIME + timedelta(seconds=30), data_source="DEMO_SYNTHETIC"),
        ]
        created = route_anomaly_module._persist_impossible_transitions(observations)
        self.assertEqual(created, 1)
        rows = self._stored_anomalies()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["data_source"], "DEMO_SYNTHETIC")

    def test_labels_demo_synthetic_even_when_only_one_observation_is_synthetic(self):
        # A mixed pair (one real detection, one seeded row sharing the same
        # plate) must still be flagged as containing synthetic data - never
        # silently presented as fully real.
        observations = [
            _obs("TN88MX0000", "CAM_01", BASE_TIME, data_source="REAL_INFERENCE"),
            _obs("TN88MX0000", "CAM_04", BASE_TIME + timedelta(seconds=30), data_source="DEMO_SYNTHETIC"),
        ]
        route_anomaly_module._persist_impossible_transitions(observations)
        rows = self._stored_anomalies()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["data_source"], "DEMO_SYNTHETIC")

    def test_labels_real_inference_when_both_observations_are_real(self):
        observations = [
            _obs("TN10AB1234", "CAM_01", BASE_TIME, data_source="REAL_INFERENCE"),
            _obs("TN10AB1234", "CAM_04", BASE_TIME + timedelta(seconds=30), data_source="REAL_INFERENCE"),
        ]
        route_anomaly_module._persist_impossible_transitions(observations)
        rows = self._stored_anomalies()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["data_source"], "REAL_INFERENCE")

    def test_leaves_data_source_none_when_contributing_observations_are_unlabeled(self):
        # Neither observation carries a data_source at all (e.g. an older,
        # pre-tagging row) - must not be asserted as REAL_INFERENCE just
        # because it isn't explicitly DEMO_SYNTHETIC.
        observations = [
            _obs("TN20CD5678", "CAM_01", BASE_TIME),
            _obs("TN20CD5678", "CAM_04", BASE_TIME + timedelta(seconds=30)),
        ]
        route_anomaly_module._persist_impossible_transitions(observations)
        rows = self._stored_anomalies()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["data_source"])


if __name__ == "__main__":
    unittest.main()
