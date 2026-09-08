"""
database/route_anomaly_store.py

Persists detected route anomalies (impossible travel time / unexpected
camera transitions / unreasonable speed) with a status lifecycle, so the
already-built frontend RouteAnomalyPage.tsx (OPEN -> UNDER_INVESTIGATION ->
RESOLVED/FALSE_POSITIVE workflow) has something real to read from and
write to instead of hitting a 404.

Detection logic itself is NOT reimplemented here - it lives in
intelligence/spatio_temporal.py (detect_impossible_transitions /
calculate_spatial_temporal_plausibility) and network/camera_network.py
(road topology). This module only stores what those already-tested
modules find, the same pattern database/alert_store.py already uses for
blacklist/anomaly alerts.

Table is intentionally sqlite3 (not the async SQLAlchemy ORM under
backend/app/models/) to match how backend/app/api/v1/analytics.py and
database/alert_store.py already read/write TrackX's real observation data
(ObservationStore, outputs/results/observations.db) - see
docs/CLAUDE_PHASE0_AUDIT.md for why: the SQLAlchemy Observation model
under backend/trackx.db exists but is not what the working API routes
actually read from.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH_STR as DEFAULT_DB_PATH

VALID_STATUSES = {"OPEN", "UNDER_INVESTIGATION", "RESOLVED", "FALSE_POSITIVE"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _severity_for_score(score: float) -> str:
    if score >= 85:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


class RouteAnomalyStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS route_anomalies (
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
        self.conn.commit()

    def add_anomaly(self, plate: str, from_camera: str, to_camera: str, timestamp: str,
                     anomaly_type: str, anomaly_score: float, reason: str,
                     unexpected_transition: bool = False, impossible_travel_time: bool = False,
                     unreasonable_speed: bool = False, observed_speed_kmph: Optional[float] = None,
                     expected_min_time: Optional[float] = None, distance_km: Optional[float] = None,
                     severity: Optional[str] = None):
        """
        Idempotent on (plate, from_camera, to_camera, timestamp) - re-running
        detection over the same observations won't pile up duplicate rows.
        Returns (anomaly_id, created).
        """
        severity = severity or _severity_for_score(anomaly_score)
        cur = self.conn.execute("""
            SELECT anomaly_id FROM route_anomalies
            WHERE plate = ? AND from_camera = ? AND to_camera = ? AND timestamp = ?
        """, (plate, from_camera, to_camera, timestamp))
        existing = cur.fetchone()
        if existing:
            return existing["anomaly_id"], False

        now = datetime.now().isoformat()
        cur = self.conn.execute("""
            INSERT INTO route_anomalies
            (plate, from_camera, to_camera, timestamp, anomaly_type, severity, status,
             anomaly_score, unexpected_transition, impossible_travel_time, unreasonable_speed,
             observed_speed_kmph, expected_min_time, distance_km, reason, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (plate, from_camera, to_camera, timestamp, anomaly_type, severity,
              round(anomaly_score, 1), int(unexpected_transition), int(impossible_travel_time),
              int(unreasonable_speed), observed_speed_kmph, expected_min_time, distance_km,
              reason, now, now))
        self.conn.commit()
        return cur.lastrowid, True

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        d["unexpected_transition"] = bool(d["unexpected_transition"])
        d["impossible_travel_time"] = bool(d["impossible_travel_time"])
        d["unreasonable_speed"] = bool(d["unreasonable_speed"])
        # Shape to match frontend/src/types/index.ts RouteAnomaly.details
        d["details"] = {
            "unexpected_transition": d["unexpected_transition"],
            "impossible_travel_time": d["impossible_travel_time"],
            "unreasonable_speed": d["unreasonable_speed"],
            "observed_speed_kmph": d.pop("observed_speed_kmph"),
            "expected_min_time": d.pop("expected_min_time"),
            "distance_km": d.pop("distance_km"),
            "reason": d.pop("reason"),
        }
        return d

    def list_anomalies(self, plate: Optional[str] = None, severity: Optional[str] = None,
                        status: Optional[str] = None, limit: Optional[int] = None):
        clauses, values = [], []
        if plate:
            clauses.append("plate = ?")
            values.append(plate)
        if severity:
            clauses.append("severity = ?")
            values.append(severity)
        if status:
            clauses.append("status = ?")
            values.append(status)
        query = "SELECT * FROM route_anomalies"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp DESC"
        if limit is not None:
            query += " LIMIT ?"
            values.append(limit)
        cur = self.conn.execute(query, values)
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def get_anomaly(self, anomaly_id: int):
        cur = self.conn.execute("SELECT * FROM route_anomalies WHERE anomaly_id = ?", (anomaly_id,))
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def update_status(self, anomaly_id: int, status: str, investigated_by: Optional[str] = None,
                       investigation_notes: Optional[str] = None, resolution_notes: Optional[str] = None):
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}', must be one of {VALID_STATUSES}")
        cur = self.conn.execute("""
            UPDATE route_anomalies
            SET status = ?, updated_at = ?,
                investigated_by = COALESCE(?, investigated_by),
                investigation_notes = COALESCE(?, investigation_notes),
                resolution_notes = COALESCE(?, resolution_notes)
            WHERE anomaly_id = ?
        """, (status, datetime.now().isoformat(), investigated_by, investigation_notes,
              resolution_notes, anomaly_id))
        self.conn.commit()
        return cur.rowcount > 0

    def statistics(self, start_time: Optional[str] = None, end_time: Optional[str] = None) -> dict:
        clauses, values = [], []
        if start_time:
            clauses.append("timestamp >= ?")
            values.append(start_time)
        if end_time:
            clauses.append("timestamp <= ?")
            values.append(end_time)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        total = self.conn.execute(f"SELECT COUNT(*) FROM route_anomalies{where}", values).fetchone()[0]
        by_status = {r["status"]: r["c"] for r in self.conn.execute(
            f"SELECT status, COUNT(*) c FROM route_anomalies{where} GROUP BY status", values)}
        by_severity = {r["severity"]: r["c"] for r in self.conn.execute(
            f"SELECT severity, COUNT(*) c FROM route_anomalies{where} GROUP BY severity", values)}
        by_type = {r["anomaly_type"]: r["c"] for r in self.conn.execute(
            f"SELECT anomaly_type, COUNT(*) c FROM route_anomalies{where} GROUP BY anomaly_type", values)}
        return {
            "total_anomalies": total,
            "by_status": by_status,
            "by_severity": by_severity,
            "by_type": by_type,
            "open_count": by_status.get("OPEN", 0),
        }

    def close(self):
        self.conn.close()
