"""
tests/test_pytest_never_writes_to_live_alert_store.py

SIH26127 "Final Data Integrity" audit (2026-09-11) - a real, ACTIVE
contamination bug found while cross-checking the live `alerts` table (see
tests/test_live_db_no_contaminating_test_artifacts.py for the first,
historical contamination this audit found and cleaned):

intelligence/alerts.py's scan_trajectories_for_alerts() defaults to
persist_to_db=True, which opens a real AlertStore() against the live
database (config.DB_PATH_STR) unless the caller explicitly passes
persist_to_db=False. Two test files called it WITHOUT that flag:
tests/test_intelligence.py (3 call sites: TN38AB1234 on CAM_02/CAM_03,
TN99ZZ0000 on CAM_03 x3) and tests/test_observation_bridge.py (1 call
site: TN99ZZ0000 on CAM_01/CAM_02). This meant every single pytest run of
this repo's own test suite was silently writing test-fixture alerts
straight into the live/demo database - confirmed by an exact match: two
rows in the live alerts table carried the literal timestamp
"2026-08-24T09:00:00" (tests/test_intelligence.py's BASE_TIME constant,
not a real detection time), for exactly the plate/camera combinations
those tests use. Backed up to
/tmp/observations_backup_before_test_contamination_cleanup.db, then
removed (2 rows; AlertStore's idempotent insert key means this did not
multiply on every prior run, but it never should have been possible at
all).

Fixed by adding persist_to_db=False to all 4 call sites (those tests only
assert on the returned `alerts` list, never on persistence, so nothing
about what they test changed).

This file is the durable regression guard: a static check that no test
file ever again calls scan_trajectories_for_alerts(...) without
persist_to_db=False, plus a behavioral check that persist_to_db=False
genuinely leaves the real live database's alert count untouched.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from config import DB_PATH_STR
from database.alert_store import AlertStore
from intelligence.alerts import scan_trajectories_for_alerts
from intelligence.trajectory import build_trajectories

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _iter_call_sites(call_pattern, filename_globs):
    """Yields (path, line_no, line_text) for every regex match across the
    given glob patterns, skipping this file itself and the function's own
    definition/docstring in intelligence/alerts.py."""
    for pattern in filename_globs:
        for path in glob.glob(os.path.join(REPO_ROOT, pattern), recursive=True):
            if os.path.abspath(path) == os.path.abspath(__file__):
                continue
            if path.endswith(os.path.join("intelligence", "alerts.py")):
                continue
            with open(path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, start=1):
                    if call_pattern.search(line):
                        yield path, lineno, line.strip()


class TestNoTestFileCallsScanTrajectoriesWithoutPersistToDbFalse:
    def test_every_test_file_call_site_passes_persist_to_db_false(self):
        # Matches an actual call with at least one argument (every real
        # call site in this repo passes `trajs`/`trajectories`), not a bare
        # `scan_trajectories_for_alerts()` prose/docstring mention.
        call_pattern = re.compile(r"=\s*scan_trajectories_for_alerts\(\s*\w")
        bad = []
        for path, lineno, line in _iter_call_sites(
            call_pattern, ["tests/**/*.py", "backend/tests/**/*.py"]
        ):
            # A call can legitimately span multiple lines; look at the next
            # couple of lines too before deciding persist_to_db=False is
            # missing (matches this repo's existing call-site style, which
            # keeps the call on one line, but be lenient rather than brittle).
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            window = "".join(lines[max(0, lineno - 1):lineno + 2])
            if "persist_to_db=False" not in window:
                bad.append((os.path.relpath(path, REPO_ROOT), lineno, line))
        assert bad == [], (
            "test file(s) call scan_trajectories_for_alerts() without "
            "persist_to_db=False - this silently writes test-fixture alerts "
            f"into the live database (see this file's docstring): {bad}"
        )

    def test_persist_to_db_false_does_not_touch_the_live_alert_count(self):
        if not os.path.exists(DB_PATH_STR):
            pytest.skip(f"no live database at {DB_PATH_STR} in this environment")
        store = AlertStore(db_path=DB_PATH_STR)
        before = len(store.list_alerts())
        store.close()

        obs = [
            {"plate_text": "ZZ_REGRESSION_GUARD_PLATE", "confidence": 0.9,
             "camera_id": "CAM_01", "timestamp": "2026-01-01T00:00:00",
             "lat": 11.0205, "long": 76.9667, "track_id": "1",
             "data_source": "REAL_INFERENCE"},
            {"plate_text": "ZZ_REGRESSION_GUARD_PLATE", "confidence": 0.9,
             "camera_id": "CAM_01", "timestamp": "2026-01-01T00:01:30",
             "lat": 11.0205, "long": 76.9667, "track_id": "1",
             "data_source": "REAL_INFERENCE"},
            {"plate_text": "ZZ_REGRESSION_GUARD_PLATE", "confidence": 0.9,
             "camera_id": "CAM_01", "timestamp": "2026-01-01T00:03:20",
             "lat": 11.0205, "long": 76.9667, "track_id": "1",
             "data_source": "REAL_INFERENCE"},
        ]
        trajs = build_trajectories(obs)
        alerts = scan_trajectories_for_alerts(trajs, all_observations=obs, persist_to_db=False)
        assert isinstance(alerts, list)  # detection logic still runs

        store = AlertStore(db_path=DB_PATH_STR)
        after = len(store.list_alerts())
        store.close()
        assert after == before, (
            f"live alert count changed ({before} -> {after}) even though "
            "persist_to_db=False was passed - this defeats the whole point "
            "of the flag"
        )

    def test_historical_test_contamination_literal_timestamp_is_gone(self):
        # The exact fingerprint that proved the bug (tests/test_intelligence.py's
        # BASE_TIME literal appearing in the live alerts table) must not
        # reappear.
        if not os.path.exists(DB_PATH_STR):
            pytest.skip(f"no live database at {DB_PATH_STR} in this environment")
        import sqlite3
        conn = sqlite3.connect(DB_PATH_STR)
        try:
            rows = conn.execute(
                "SELECT alert_id, plate, camera_id FROM alerts WHERE timestamp = '2026-08-24T09:00:00'"
            ).fetchall()
        finally:
            conn.close()
        assert rows == [], f"test-fixture contamination reappeared: {rows}"
