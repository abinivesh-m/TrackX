"""
blacklist_store.py

Phase 2 (SIH26127 audit): persistent BLACKLIST table.

intelligence/alerts.py currently (pre-Phase-13) still checks against a
hardcoded Python BLACKLIST list - that's flagged as a known limitation
there and is exactly what Phase 13 will fix by reading from this table
instead. This module just gets the storage layer in place first.

Plates are stored normalized (see recognition.plate_matcher.normalize_plate)
so lookups aren't sensitive to formatting differences like spaces or
lowercase input.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from recognition.plate_matcher import normalize_plate
from config import DB_PATH_STR as DEFAULT_DB_PATH


class BlacklistStore:
    """
    NOTE (thread-safety): this store deliberately does NOT keep a persistent
    sqlite3.Connection on `self`. sqlite3 connections may only be used from
    the thread that created them, but a BlacklistStore instance itself (e.g.
    the module-level singleton in intelligence/alerts.py) can be constructed
    in one thread and then have its methods called from another - which is
    exactly what happens across Streamlit script reruns/cached functions.
    Each method below opens a short-lived connection scoped to that single
    call (in whichever thread is actually calling it) and closes it before
    returning, so no connection object ever crosses a thread boundary.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._create_table()

    @contextmanager
    def _connect(self):
        """
        Opens a fresh connection for a single call, commits on success /
        rolls back on error (via the sqlite3 connection context manager
        semantics), and always closes the connection afterwards so nothing
        persists past this call's thread.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _create_table(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate TEXT NOT NULL,
                    normalized_plate TEXT NOT NULL,
                    description TEXT,
                    severity TEXT NOT NULL DEFAULT 'MEDIUM',
                    created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                )
            """)
            existing = {row[1] for row in conn.execute("PRAGMA table_info(blacklist)")}
            if "source" not in existing:
                # Distinguishes entries seeded by demo/seed_demo_data.py
                # ('DEMO_SEED') from entries an operator actually added via
                # POST /api/v1/vehicles/watchlist ('OPERATOR', the default)
                # - so the UI can label demo scenario plates as demo data
                # and never present them as a real operational watchlist.
                conn.execute("ALTER TABLE blacklist ADD COLUMN source TEXT NOT NULL DEFAULT 'OPERATOR'")

    def add_plate(self, plate: str, description: Optional[str] = None,
                  severity: str = "MEDIUM", source: str = "OPERATOR"):
        """
        Idempotent: if this plate already has an ACTIVE blacklist entry,
        returns that entry's id instead of inserting a duplicate row.
        Re-blacklisting a plate that was previously deactivated DOES create
        a new row (deliberately - keeps the old entry as history rather than
        silently reviving/overwriting it).

        source: 'OPERATOR' (default - a real user added this via the app)
        or 'DEMO_SEED' (demo/seed_demo_data.py's scripted scenario data).
        """
        norm = normalize_plate(plate)
        existing = self.get_active_entry(plate)
        if existing:
            return existing["id"]

        with self._connect() as conn:
            cur = conn.execute("""
                INSERT INTO blacklist (plate, normalized_plate, description, severity, created_at, active, source)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (plate, norm, description, severity, datetime.now().isoformat(), source))
            return cur.lastrowid

    def get_active_entry(self, plate: str):
        norm = normalize_plate(plate)
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM blacklist WHERE normalized_plate = ? AND active = 1 "
                "ORDER BY created_at DESC LIMIT 1",
                (norm,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    def deactivate_plate(self, plate: str):
        norm = normalize_plate(plate)
        with self._connect() as conn:
            conn.execute(
                "UPDATE blacklist SET active = 0 WHERE normalized_plate = ? AND active = 1",
                (norm,),
            )

    def all_active(self):
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM blacklist WHERE active = 1 ORDER BY created_at DESC"
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self):
        """
        No-op kept for backward compatibility: this store no longer holds a
        persistent connection to close (each operation manages its own),
        but existing callers (tests, demo scripts) call store.close() and
        should keep working unchanged.
        """
        pass


if __name__ == "__main__":
    store = BlacklistStore(db_path="outputs/results/test_blacklist.db")
    store.add_plate("TN38AB1234", description="reported stolen", severity="HIGH")
    store.add_plate("TN38AB1234")  # should NOT create a second row (idempotent)
    print(store.all_active())
    store.close()
