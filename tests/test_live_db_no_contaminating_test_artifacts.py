"""
tests/test_live_db_no_contaminating_test_artifacts.py

SIH26127 "Final Data Integrity" audit (2026-09-11) - real finding while
cross-page-checking a real plate (DL7CP8161, the user's own example) across
Vehicle Search / Trajectory / Alerts:

The live demo database's `alerts` table contained 24 rows (out of 59 total)
persisted against camera_id values like "CAM_ANPR_TEST1",
"CAM_COMPARE_NEWPLATE", "CAM_REGR_TEST1", "CAM_TEST_VTEST" - none of which
exist in network/camera_network.py's CAMERAS (the one real Coimbatore
camera network) or in the observations table itself. These were stale
artifacts from an earlier real-video regression validation run
(pipeline.py invoked directly with ad-hoc test camera-id labels, which
persists straight to the live AlertStore/DB_PATH_STR by default - see
intelligence/alerts.py's scan_trajectories_for_alerts) - the underlying
test observations were since cleaned up, but the ALERTS derived from them
were not, leaving 24 OPEN, real-looking alerts (including one for
DL7CP8161 itself, "IMPOSSIBLE vehicle speed - possible cloned plate",
41% confidence) with no connection to any current camera or observation.

Backed up to /tmp/observations_backup_before_alert_cleanup.db, then removed
via a direct, verified SQL DELETE (24 rows; confirmed 0 remain, confirmed
GET /alerts's real-time re-scan does not resurrect them since no
observation feeds them anymore).

This test is a durable guard against the SAME class of contamination
recurring silently: it runs against the real, live database (same pattern
already used elsewhere in this repo - e.g. the congestion/analytics
real-DB verifications - not a mocked/isolated fixture) and fails loudly if
any alert, route anomaly, or congestion event ever again references a
camera_id outside the real camera network.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from config import DB_PATH_STR
from network.camera_network import CAMERAS

REAL_CAMERA_IDS = set(CAMERAS.keys())


def _live_db_conn():
    if not os.path.exists(DB_PATH_STR):
        pytest.skip(f"no live database at {DB_PATH_STR} in this environment")
    conn = sqlite3.connect(DB_PATH_STR)
    conn.row_factory = sqlite3.Row
    return conn


def _existing_tables(conn):
    return {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


class TestLiveDatabaseHasNoOutOfNetworkCameraReferences:
    def test_alerts_table_only_references_real_cameras(self):
        conn = _live_db_conn()
        try:
            if "alerts" not in _existing_tables(conn):
                pytest.skip("alerts table does not exist in this database")
            rows = conn.execute(
                "SELECT alert_id, plate, camera_id FROM alerts "
                "WHERE camera_id IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()
        bogus = [dict(r) for r in rows if r["camera_id"] not in REAL_CAMERA_IDS]
        assert bogus == [], (
            f"{len(bogus)} alert(s) reference a camera_id outside the real "
            f"camera network {sorted(REAL_CAMERA_IDS)} - this is the exact "
            "test-artifact contamination class found and cleaned on "
            f"2026-09-11 (see this file's docstring): {bogus[:5]}"
        )

    def test_route_anomalies_table_only_references_real_cameras(self):
        conn = _live_db_conn()
        try:
            if "route_anomalies" not in _existing_tables(conn):
                pytest.skip("route_anomalies table does not exist in this database")
            rows = conn.execute(
                "SELECT anomaly_id, plate, from_camera, to_camera FROM route_anomalies"
            ).fetchall()
        finally:
            conn.close()
        bogus = [
            dict(r) for r in rows
            if r["from_camera"] not in REAL_CAMERA_IDS or r["to_camera"] not in REAL_CAMERA_IDS
        ]
        assert bogus == [], f"{len(bogus)} route anomaly row(s) reference an unknown camera: {bogus[:5]}"

    def test_congestion_events_table_only_references_real_cameras(self):
        conn = _live_db_conn()
        try:
            if "congestion_events" not in _existing_tables(conn):
                pytest.skip("congestion_events table does not exist in this database")
            rows = conn.execute(
                "SELECT id, camera_id FROM congestion_events WHERE camera_id IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()
        bogus = [dict(r) for r in rows if r["camera_id"] not in REAL_CAMERA_IDS]
        assert bogus == [], f"{len(bogus)} congestion event(s) reference an unknown camera: {bogus[:5]}"

    def test_observations_table_only_references_real_cameras(self):
        conn = _live_db_conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT camera_id FROM observations WHERE camera_id IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()
        bogus = sorted({r["camera_id"] for r in rows} - REAL_CAMERA_IDS)
        assert bogus == [], f"observations reference unknown camera_id(s): {bogus}"
