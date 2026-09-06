"""
test_database.py

Phase 2: tests for the three new tables (CAMERAS, BLACKLIST, ALERTS) added
alongside the existing observations table. No YOLO/PaddleOCR/torch needed -
these are plain sqlite CRUD, and normalize_plate() is pure string logic.

Run with: python -m pytest tests/test_database.py -v
(or plain `python tests/test_database.py`, see __main__ below)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.camera_store import CameraStore
from database.blacklist_store import BlacklistStore
from database.alert_store import AlertStore
from database.observation_store import ObservationStore


def _isolated_db_path(tmp_name):
    path = os.path.join("/tmp", tmp_name)
    if os.path.exists(path):
        os.remove(path)
    return path


def test_camera_store_upsert_is_idempotent():
    db_path = _isolated_db_path("test_cameras.db")
    store = CameraStore(db_path=db_path)

    store.upsert_camera("CAM_01", 13.0827, 80.2707, name="Junction A", road="Anna Salai")
    store.upsert_camera("CAM_01", 13.0827, 80.2707, name="Junction A (renamed)", road="Anna Salai")

    all_cams = store.all_cameras()
    assert len(all_cams) == 1  # second upsert updated, did not duplicate
    assert all_cams[0]["name"] == "Junction A (renamed)"
    assert all_cams[0]["active"] == 1

    store.deactivate_camera("CAM_01")
    assert store.all_cameras(active_only=True) == []
    assert len(store.all_cameras()) == 1  # still exists, just inactive

    store.close()


def test_blacklist_store_add_is_idempotent_and_normalizes():
    db_path = _isolated_db_path("test_blacklist.db")
    store = BlacklistStore(db_path=db_path)

    id1 = store.add_plate("TN38AB1234", description="reported stolen", severity="HIGH")
    id2 = store.add_plate("tn38ab1234")  # same plate, different case/formatting

    assert id1 == id2  # idempotent - no duplicate active entry
    assert len(store.all_active()) == 1

    entry = store.get_active_entry("TN38AB1234")
    assert entry is not None
    assert entry["severity"] == "HIGH"

    store.deactivate_plate("TN38AB1234")
    assert store.get_active_entry("TN38AB1234") is None

    # re-blacklisting after deactivation creates a NEW row (kept as history)
    id3 = store.add_plate("TN38AB1234", severity="MEDIUM")
    assert id3 != id1
    assert len(store.all_active()) == 1

    store.close()


def test_alert_store_add_is_idempotent_on_natural_key():
    db_path = _isolated_db_path("test_alerts.db")
    store = AlertStore(db_path=db_path)

    id1, created1 = store.add_alert(
        "TN38AB1234", "BLACKLISTED_VEHICLE", "2026-08-24T09:00:00",
        severity="HIGH", camera_id="CAM_02", description="blacklist match",
    )
    id2, created2 = store.add_alert(
        "TN38AB1234", "BLACKLISTED_VEHICLE", "2026-08-24T09:00:00",
        severity="HIGH", camera_id="CAM_02", description="blacklist match",
    )

    assert created1 is True
    assert created2 is False
    assert id1 == id2
    assert len(store.list_alerts()) == 1

    # a different alert_type at the same plate/time/camera is a DIFFERENT alert
    id3, created3 = store.add_alert(
        "TN38AB1234", "IMPOSSIBLE_TRAVEL", "2026-08-24T09:00:00",
        severity="HIGH", camera_id="CAM_02",
    )
    assert created3 is True
    assert id3 != id1
    assert len(store.list_alerts()) == 2

    assert len(store.list_alerts(status="OPEN")) == 2
    store.resolve_alert(id1)
    assert len(store.list_alerts(status="OPEN")) == 1
    assert len(store.list_alerts(status="RESOLVED")) == 1

    store.close()


def test_new_tables_coexist_with_observations_table_in_same_db_file():
    """All four stores can point at the SAME db file without clobbering
    each other's tables - this is how the real app uses them."""
    db_path = _isolated_db_path("test_shared_db.db")

    obs_store = ObservationStore(db_path=db_path)
    obs_store.add({
        "plate_text": "TN10AB1234", "confidence": 0.9, "camera_id": "CAM_01",
        "timestamp": "2026-08-24T09:00:00", "lat": 13.08, "long": 80.27,
    })
    obs_store.close()

    cam_store = CameraStore(db_path=db_path)
    cam_store.upsert_camera("CAM_01", 13.08, 80.27, name="Junction A")
    cam_store.close()

    bl_store = BlacklistStore(db_path=db_path)
    bl_store.add_plate("TN10AB1234", severity="LOW")
    bl_store.close()

    alert_store = AlertStore(db_path=db_path)
    alert_store.add_alert("TN10AB1234", "BLACKLISTED_VEHICLE", "2026-08-24T09:00:00")
    alert_store.close()

    # reopen everything fresh and confirm nothing was lost/overwritten
    obs_store2 = ObservationStore(db_path=db_path)
    assert len(obs_store2.all_observations()) == 1
    obs_store2.close()

    cam_store2 = CameraStore(db_path=db_path)
    assert len(cam_store2.all_cameras()) == 1
    cam_store2.close()

    bl_store2 = BlacklistStore(db_path=db_path)
    assert len(bl_store2.all_active()) == 1
    bl_store2.close()

    alert_store2 = AlertStore(db_path=db_path)
    assert len(alert_store2.list_alerts()) == 1
    alert_store2.close()


if __name__ == "__main__":
    test_camera_store_upsert_is_idempotent()
    print("PASS: test_camera_store_upsert_is_idempotent")
    test_blacklist_store_add_is_idempotent_and_normalizes()
    print("PASS: test_blacklist_store_add_is_idempotent_and_normalizes")
    test_alert_store_add_is_idempotent_on_natural_key()
    print("PASS: test_alert_store_add_is_idempotent_on_natural_key")
    test_new_tables_coexist_with_observations_table_in_same_db_file()
    print("PASS: test_new_tables_coexist_with_observations_table_in_same_db_file")
    print("\nAll Phase 2 database tests passed.")
