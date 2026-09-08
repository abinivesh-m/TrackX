"""
alert_store.py

Phase 2 (SIH26127 audit): persistent ALERTS table.

intelligence/alerts.py currently (pre-Phase-13) computes alerts fresh every
time by re-scanning trajectories, and doesn't persist them anywhere -
that's exactly what Phase 13's event-driven alert flow (new observation ->
blacklist check -> anomaly check -> alert creation -> DB persistence ->
dashboard) will use this table for. This module just gets the storage
layer in place first, ahead of that wiring.

alert_type is intentionally a free-text field, not an enum column, but the
values Phase 13 will use are: BLACKLISTED_VEHICLE, IMPOSSIBLE_TRAVEL,
SUSPICIOUS_ROUTE, REPEATED_CAMERA.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH_STR as DEFAULT_DB_PATH


class AlertStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'MEDIUM',
                camera_id TEXT,
                timestamp TEXT NOT NULL,
                description TEXT,
                confidence REAL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolution_notes TEXT
            )
        """)
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(alerts)")}
        if "updated_at" not in existing:
            self.conn.execute("ALTER TABLE alerts ADD COLUMN updated_at TEXT")
            self.conn.execute("UPDATE alerts SET updated_at = created_at WHERE updated_at IS NULL")
        if "resolution_notes" not in existing:
            self.conn.execute("ALTER TABLE alerts ADD COLUMN resolution_notes TEXT")
        if "evidence" not in existing:
            # Structured, per-alert-type proof (matched plate + similarity,
            # camera sequence, anomaly signal breakdown, congestion/offline
            # metrics - whatever the detector actually computed). Stored as
            # JSON text since the fields differ per alert_type; NULL for any
            # alert persisted before this column existed. See
            # intelligence/alerts.py for what each alert_type puts here.
            self.conn.execute("ALTER TABLE alerts ADD COLUMN evidence TEXT")
        self.conn.commit()

    def add_alert(self, plate: str, alert_type: str, timestamp: str,
                  severity: str = "MEDIUM", camera_id: Optional[str] = None,
                  description: Optional[str] = None, confidence: Optional[float] = None,
                  evidence: Optional[dict] = None):
        """
        Idempotent on the natural key (plate, alert_type, camera_id,
        timestamp) - re-running the same detection logic over the same data
        (e.g. re-scanning trajectories) won't pile up duplicate alert rows.
        Returns (alert_id, created) where created is False if this exact
        alert already existed.

        `plate` is a vehicle plate for vehicle-scoped alert types
        (BLACKLISTED_VEHICLE, REPEATED_CAMERA, SUSPICIOUS_ROUTE) and a
        camera_id for camera-scoped types (CAMERA_OFFLINE,
        CONGESTION_BOTTLENECK) - there's no vehicle to key those on, and
        reusing this column keeps the existing idempotency key working
        without a schema change. Callers/consumers tell the two apart by
        alert_type, not by inspecting the plate field's shape.
        """
        cur = self.conn.execute("""
            SELECT alert_id FROM alerts
            WHERE plate = ? AND alert_type = ? AND timestamp = ?
              AND (camera_id IS ? OR camera_id = ?)
        """, (plate, alert_type, timestamp, camera_id, camera_id))
        existing = cur.fetchone()
        if existing:
            return existing[0], False

        cur = self.conn.execute("""
            INSERT INTO alerts
            (plate, alert_type, severity, camera_id, timestamp, description, confidence, evidence, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
        """, (plate, alert_type, severity, camera_id, timestamp, description,
              confidence, json.dumps(evidence) if evidence is not None else None,
              datetime.now().isoformat(), datetime.now().isoformat()))
        self.conn.commit()
        return cur.lastrowid, True

    def list_alerts(self, status: Optional[str] = None, severity: Optional[str] = None,
                    limit: Optional[int] = None):
        clauses, values = [], []
        if status:
            clauses.append("status = ?")
            values.append(status)
        if severity:
            clauses.append("severity = ?")
            values.append(severity)
        query = "SELECT * FROM alerts"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp DESC"
        if limit is not None:
            query += " LIMIT ?"
            values.append(limit)
        cur = self.conn.execute(query, values)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        for row in rows:
            raw = row.get("evidence")
            if raw:
                try:
                    row["evidence"] = json.loads(raw)
                except (TypeError, ValueError):
                    row["evidence"] = None
            else:
                row["evidence"] = None
        return rows

    def update_status(self, alert_id: int, status: str, notes: Optional[str] = None):
        if status not in {"OPEN", "ACKNOWLEDGED", "RESOLVED"}:
            raise ValueError("Invalid alert status")
        cur = self.conn.execute(
            "UPDATE alerts SET status = ?, updated_at = ?, resolution_notes = COALESCE(?, resolution_notes) "
            "WHERE alert_id = ?",
            (status, datetime.now().isoformat(), notes, alert_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def resolve_alert(self, alert_id: int, notes: Optional[str] = None):
        return self.update_status(alert_id, "RESOLVED", notes)

    def acknowledge_alert(self, alert_id: int):
        return self.update_status(alert_id, "ACKNOWLEDGED")

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    store = AlertStore(db_path="outputs/results/test_alerts.db")
    aid1, created1 = store.add_alert("TN38AB1234", "BLACKLISTED_VEHICLE", "2026-08-24T09:00:00",
                                      severity="HIGH", camera_id="CAM_02",
                                      description="blacklist match")
    aid2, created2 = store.add_alert("TN38AB1234", "BLACKLISTED_VEHICLE", "2026-08-24T09:00:00",
                                      severity="HIGH", camera_id="CAM_02",
                                      description="blacklist match")  # duplicate, should not re-insert
    print(f"first insert: id={aid1} created={created1}")
    print(f"duplicate attempt: id={aid2} created={created2}")
    print(store.list_alerts())
    store.close()
