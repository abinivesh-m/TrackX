"""
camera_store.py

Phase 2 (SIH26127 audit): persistent CAMERAS table, separate from the
observations they produce.

This does NOT replace network/camera_network.py's ROAD_GRAPH or the
matching/connectivity logic that lives there - that's still Phase 9 work.
This is just a place for camera metadata (location, name, road/segment,
direction, active status) to live in the shared db instead of only ever
existing as a hardcoded Python dict, so e.g. the dashboard or a future
admin UI could add/deactivate a camera without editing source code.

Until Phase 9 wires camera_network.py to read from here, the two are
independent: camera_network.py's CAMERAS dict remains the source of truth
for matching/road-graph logic, and this table is additive infrastructure.
Don't assume they're in sync yet.
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH_STR as DEFAULT_DB_PATH


class CameraStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id TEXT PRIMARY KEY,
                latitude REAL,
                longitude REAL,
                name TEXT,
                road TEXT,
                direction TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    def upsert_camera(self, camera_id: str, latitude: float, longitude: float,
                       name: Optional[str] = None, road: Optional[str] = None,
                       direction: Optional[str] = None, active: bool = True):
        """
        Idempotent by design: calling this again for the same camera_id
        updates the existing row instead of creating a duplicate, so seeding
        camera metadata on every startup is safe.
        """
        self.conn.execute("""
            INSERT INTO cameras (camera_id, latitude, longitude, name, road, direction, active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(camera_id) DO UPDATE SET
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                name=excluded.name,
                road=excluded.road,
                direction=excluded.direction,
                active=excluded.active,
                updated_at=excluded.updated_at
        """, (
            camera_id, latitude, longitude, name, road, direction,
            1 if active else 0, datetime.now().isoformat(),
        ))
        self.conn.commit()

    def get_camera(self, camera_id: str):
        cur = self.conn.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

    def all_cameras(self, active_only: bool = False):
        query = "SELECT * FROM cameras"
        if active_only:
            query += " WHERE active = 1"
        cur = self.conn.execute(query)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def deactivate_camera(self, camera_id: str):
        self.conn.execute(
            "UPDATE cameras SET active = 0, updated_at = ? WHERE camera_id = ?",
            (datetime.now().isoformat(), camera_id),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    store = CameraStore(db_path="outputs/results/test_cameras.db")
    store.upsert_camera("CAM_01", 13.0827, 80.2707, name="Junction A",
                         road="Anna Salai", direction="northbound")
    print(store.all_cameras())
    store.close()
