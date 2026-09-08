"""
database/congestion_store.py

Persists congestion/bottleneck events and configurable thresholds, so the
already-built frontend CongestionPage.tsx has something real to read/write
instead of hitting a 404. Detection math itself is NOT reimplemented here -
it lives in analytics/analytics.py's congestion_hotspots() (density + speed
+ efficiency multi-factor model, already used by backend/app/api/v1/
analytics.py's /summary endpoint). This module just gives that computation
a place to land as a persisted, queryable event with a lifecycle
(ACTIVE -> RESOLVED), matching the pattern database/alert_store.py already
uses.

Sqlite3, not the async SQLAlchemy ORM - see database/route_anomaly_store.py
module docstring for why (matches what the working API routes actually
read from: ObservationStore / outputs/results/observations.db).
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH_STR as DEFAULT_DB_PATH

DEFAULT_THRESHOLDS = {
    "speed_threshold_kmh": 15.0,
    "density_threshold_vehicles_per_km": 40.0,
    "flow_threshold_vehicles_per_hour": 600.0,
    "congestion_duration_minutes": 10.0,
    "bottleneck_speed_reduction_percent": 40.0,
    "anomaly_deviation_percent": 30.0,
}


class CongestionStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS congestion_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                camera_id TEXT NOT NULL,
                road_segment_id TEXT NOT NULL,
                event_start TEXT NOT NULL,
                event_end TEXT,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                congestion_level TEXT NOT NULL,
                congestion_score REAL NOT NULL,
                avg_speed_kmh REAL NOT NULL,
                vehicle_density REAL NOT NULL,
                flow_rate_vehicles_per_hour REAL NOT NULL DEFAULT 0,
                is_bottleneck INTEGER NOT NULL DEFAULT 0,
                bottleneck_score REAL NOT NULL DEFAULT 0,
                affected_cameras TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS traffic_thresholds (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                speed_threshold_kmh REAL NOT NULL,
                density_threshold_vehicles_per_km REAL NOT NULL,
                flow_threshold_vehicles_per_hour REAL NOT NULL,
                congestion_duration_minutes REAL NOT NULL,
                bottleneck_speed_reduction_percent REAL NOT NULL,
                anomaly_deviation_percent REAL NOT NULL
            )
        """)
        cur = self.conn.execute("SELECT COUNT(*) FROM traffic_thresholds")
        if cur.fetchone()[0] == 0:
            self.conn.execute("""
                INSERT INTO traffic_thresholds (id, speed_threshold_kmh, density_threshold_vehicles_per_km,
                    flow_threshold_vehicles_per_hour, congestion_duration_minutes,
                    bottleneck_speed_reduction_percent, anomaly_deviation_percent)
                VALUES (1, ?, ?, ?, ?, ?, ?)
            """, (
                DEFAULT_THRESHOLDS["speed_threshold_kmh"],
                DEFAULT_THRESHOLDS["density_threshold_vehicles_per_km"],
                DEFAULT_THRESHOLDS["flow_threshold_vehicles_per_hour"],
                DEFAULT_THRESHOLDS["congestion_duration_minutes"],
                DEFAULT_THRESHOLDS["bottleneck_speed_reduction_percent"],
                DEFAULT_THRESHOLDS["anomaly_deviation_percent"],
            ))
        self.conn.commit()

    # ---- thresholds -----------------------------------------------------

    def get_thresholds(self) -> dict:
        row = self.conn.execute("SELECT * FROM traffic_thresholds WHERE id = 1").fetchone()
        d = dict(row)
        d.pop("id", None)
        return d

    def update_thresholds(self, **kwargs) -> dict:
        allowed = set(DEFAULT_THRESHOLDS.keys())
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return self.get_thresholds()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        self.conn.execute(f"UPDATE traffic_thresholds SET {set_clause} WHERE id = 1",
                           list(updates.values()))
        self.conn.commit()
        return self.get_thresholds()

    # ---- events -----------------------------------------------------------

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        d["is_bottleneck"] = bool(d["is_bottleneck"])
        d["affected_cameras"] = json.loads(d["affected_cameras"] or "[]")
        if d["event_end"]:
            start = datetime.fromisoformat(d["event_start"])
            end = datetime.fromisoformat(d["event_end"])
            d["duration_minutes"] = round((end - start).total_seconds() / 60, 1)
        else:
            start = datetime.fromisoformat(d["event_start"])
            d["duration_minutes"] = round((datetime.now() - start).total_seconds() / 60, 1)
        return d

    def upsert_active_event(self, camera_id: str, congestion_level: str, congestion_score: float,
                             avg_speed_kmh: float, vehicle_density: float,
                             flow_rate_vehicles_per_hour: float = 0.0,
                             is_bottleneck: bool = False, bottleneck_score: float = 0.0,
                             affected_cameras: Optional[list] = None) -> dict:
        """
        One camera has at most one ACTIVE event at a time: if it already has
        one, update it in place (this is a continuing congestion episode);
        otherwise open a new one. Returns the resulting event dict.
        """
        now = datetime.now().isoformat()
        existing = self.conn.execute(
            "SELECT * FROM congestion_events WHERE camera_id = ? AND status = 'ACTIVE'",
            (camera_id,)
        ).fetchone()

        if existing:
            self.conn.execute("""
                UPDATE congestion_events
                SET congestion_level = ?, congestion_score = ?, avg_speed_kmh = ?,
                    vehicle_density = ?, flow_rate_vehicles_per_hour = ?, is_bottleneck = ?,
                    bottleneck_score = ?, affected_cameras = ?, updated_at = ?
                WHERE id = ?
            """, (congestion_level, congestion_score, avg_speed_kmh, vehicle_density,
                  flow_rate_vehicles_per_hour, int(is_bottleneck), bottleneck_score,
                  json.dumps(affected_cameras or []), now, existing["id"]))
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM congestion_events WHERE id = ?", (existing["id"],)).fetchone()
            return self._row_to_dict(row)

        event_id = f"{camera_id}_{now}"
        cur = self.conn.execute("""
            INSERT INTO congestion_events
            (event_id, camera_id, road_segment_id, event_start, status, congestion_level,
             congestion_score, avg_speed_kmh, vehicle_density, flow_rate_vehicles_per_hour,
             is_bottleneck, bottleneck_score, affected_cameras, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_id, camera_id, camera_id, now, congestion_level, congestion_score,
              avg_speed_kmh, vehicle_density, flow_rate_vehicles_per_hour, int(is_bottleneck),
              bottleneck_score, json.dumps(affected_cameras or []), now, now))
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM congestion_events WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self._row_to_dict(row)

    def resolve_events_not_in(self, still_congested_camera_ids: set):
        """Close out ACTIVE events for cameras that are no longer congested."""
        now = datetime.now().isoformat()
        active = self.conn.execute("SELECT id, camera_id FROM congestion_events WHERE status = 'ACTIVE'").fetchall()
        for row in active:
            if row["camera_id"] not in still_congested_camera_ids:
                self.conn.execute(
                    "UPDATE congestion_events SET status = 'RESOLVED', event_end = ?, updated_at = ? WHERE id = ?",
                    (now, now, row["id"])
                )
        self.conn.commit()

    def list_active_events(self, camera_id: Optional[str] = None, limit: int = 50):
        query = "SELECT * FROM congestion_events WHERE status = 'ACTIVE'"
        values = []
        if camera_id:
            query += " AND camera_id = ?"
            values.append(camera_id)
        query += " ORDER BY congestion_score DESC LIMIT ?"
        values.append(limit)
        cur = self.conn.execute(query, values)
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def list_history(self, camera_id: Optional[str] = None, start_time: Optional[str] = None,
                      end_time: Optional[str] = None, limit: int = 50):
        clauses, values = [], []
        if camera_id:
            clauses.append("camera_id = ?")
            values.append(camera_id)
        if start_time:
            clauses.append("event_start >= ?")
            values.append(start_time)
        if end_time:
            clauses.append("event_start <= ?")
            values.append(end_time)
        query = "SELECT * FROM congestion_events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY event_start DESC LIMIT ?"
        values.append(limit)
        cur = self.conn.execute(query, values)
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def list_bottlenecks(self, limit: int = 20):
        cur = self.conn.execute("""
            SELECT * FROM congestion_events WHERE status = 'ACTIVE' AND is_bottleneck = 1
            ORDER BY bottleneck_score DESC LIMIT ?
        """, (limit,))
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def close(self):
        self.conn.close()
