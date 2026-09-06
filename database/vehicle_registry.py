"""
vehicle_registry.py

Comprehensive vehicle registry database for TrackX.

Stores detailed vehicle information including:
- Plate numbers and registration details
- Vehicle type, fuel type, registration status
- Watchlist status and reasons
- Integration with blacklist system for alerts
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict

from recognition.plate_matcher import normalize_plate
from config import DB_PATH_STR as DEFAULT_DB_PATH


class VehicleRegistry:
    """
    Vehicle registry database for storing comprehensive vehicle information.
    Thread-safe design: each operation opens a fresh connection.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._create_tables()

    @contextmanager
    def _connect(self):
        """Opens a fresh connection for a single call, always closes after."""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _create_tables(self):
        with self._connect() as conn:
            # Main vehicle registry table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_number TEXT NOT NULL,
                    normalized_plate TEXT NOT NULL UNIQUE,
                    state_code TEXT NOT NULL,
                    rto_code INTEGER,
                    vehicle_type TEXT NOT NULL,
                    fuel_type TEXT,
                    registration_status TEXT NOT NULL,
                    watchlist_status TEXT NOT NULL DEFAULT 'CLEAR',
                    watchlist_reason TEXT,
                    data_source TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sync_status TEXT DEFAULT 'PENDING'
                )
            """)

            # Index for fast plate lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_normalized_plate 
                ON vehicle_registry(normalized_plate)
            """)

            # Index for watchlist filtering
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_watchlist_status 
                ON vehicle_registry(watchlist_status)
            """)

    def add_vehicle(self, vehicle_data: Dict) -> Optional[int]:
        """
        Add a single vehicle to the registry.
        Returns the vehicle ID or None if failed.
        """
        try:
            plate = vehicle_data.get('plate_number', '').strip()
            if not plate:
                return None

            norm = normalize_plate(plate)
            now = datetime.now().isoformat()

            with self._connect() as conn:
                cur = conn.execute("""
                    INSERT OR REPLACE INTO vehicle_registry 
                    (plate_number, normalized_plate, state_code, rto_code, vehicle_type,
                     fuel_type, registration_status, watchlist_status, watchlist_reason,
                     data_source, last_updated, created_at, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    plate,
                    norm,
                    vehicle_data.get('state_code', ''),
                    vehicle_data.get('rto_code'),
                    vehicle_data.get('vehicle_type', 'Unknown'),
                    vehicle_data.get('fuel_type', 'Unknown'),
                    vehicle_data.get('registration_status', 'VALID'),
                    vehicle_data.get('watchlist_status', 'CLEAR'),
                    vehicle_data.get('watchlist_reason', ''),
                    vehicle_data.get('data_source', 'MANUAL'),
                    vehicle_data.get('last_updated', now),
                    now,
                    'SYNCED'
                ))
                return cur.lastrowid
        except Exception as e:
            print(f"Error adding vehicle {vehicle_data.get('plate_number')}: {e}")
            return None

    def bulk_import(self, vehicles_df) -> Dict[str, int]:
        """
        Bulk import vehicles from a pandas DataFrame.
        Returns statistics about the import.
        """
        stats = {
            'total': len(vehicles_df),
            'success': 0,
            'failed': 0,
            'watchlisted': 0
        }

        for _, row in vehicles_df.iterrows():
            vehicle_data = {
                'plate_number': str(row.get('plate_number', '')).strip(),
                'state_code': str(row.get('state_code', '')).strip(),
                'rto_code': row.get('rto_code'),
                'vehicle_type': str(row.get('vehicle_type', 'Unknown')).strip(),
                'fuel_type': str(row.get('fuel_type', 'Unknown')).strip(),
                'registration_status': str(row.get('registration_status', 'VALID')).strip(),
                'watchlist_status': str(row.get('watchlist_status', 'CLEAR')).strip(),
                'watchlist_reason': str(row.get('watchlist_reason', '')).strip(),
                'data_source': str(row.get('data_source', 'IMPORT')).strip(),
                'last_updated': str(row.get('last_updated', datetime.now().isoformat())).strip()
            }

            if self.add_vehicle(vehicle_data):
                stats['success'] += 1
                if vehicle_data['watchlist_status'] in ['BLOCKLISTED', 'REVIEW']:
                    stats['watchlisted'] += 1
            else:
                stats['failed'] += 1

        return stats

    def get_vehicle(self, plate: str) -> Optional[Dict]:
        """Look up a vehicle by plate number."""
        norm = normalize_plate(plate)
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM vehicle_registry WHERE normalized_plate = ?",
                (norm,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    def get_watchlisted_vehicles(self) -> List[Dict]:
        """Get all vehicles with watchlist status."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM vehicle_registry WHERE watchlist_status IN ('BLOCKLISTED', 'REVIEW') ORDER BY watchlist_status, plate_number"
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def sync_to_blacklist(self, blacklist_store) -> Dict[str, int]:
        """
        Sync watchlisted vehicles to the blacklist system.
        Returns sync statistics.
        """
        stats = {
            'total': 0,
            'high_severity': 0,
            'medium_severity': 0,
            'failed': 0
        }

        watchlisted = self.get_watchlisted_vehicles()
        stats['total'] = len(watchlisted)

        for vehicle in watchlisted:
            try:
                plate = vehicle['plate_number']
                status = vehicle['watchlist_status']
                reason = vehicle['watchlist_reason']

                # Map watchlist status to blacklist severity
                if status == 'BLOCKLISTED':
                    severity = 'HIGH'
                    stats['high_severity'] += 1
                elif status == 'REVIEW':
                    severity = 'MEDIUM'
                    stats['medium_severity'] += 1
                else:
                    continue

                # Add to blacklist with description
                description = f"{status}: {reason}" if reason else status
                blacklist_store.add_plate(plate, description=description, severity=severity)

                # Update sync status
                with self._connect() as conn:
                    conn.execute(
                        "UPDATE vehicle_registry SET sync_status = 'SYNCED' WHERE id = ?",
                        (vehicle['id'],)
                    )

            except Exception as e:
                print(f"Error syncing vehicle {vehicle['plate_number']}: {e}")
                stats['failed'] += 1

        return stats

    def get_registry_stats(self) -> Dict:
        """Get statistics about the vehicle registry."""
        with self._connect() as conn:
            # Total vehicles
            cur = conn.execute("SELECT COUNT(*) FROM vehicle_registry")
            total = cur.fetchone()[0]

            # Watchlist distribution
            cur = conn.execute("""
                SELECT watchlist_status, COUNT(*) 
                FROM vehicle_registry 
                GROUP BY watchlist_status
            """)
            watchlist_dist = dict(cur.fetchall())

            # Vehicle type distribution
            cur = conn.execute("""
                SELECT vehicle_type, COUNT(*) 
                FROM vehicle_registry 
                GROUP BY vehicle_type
            """)
            vehicle_types = dict(cur.fetchall())

            # State distribution
            cur = conn.execute("""
                SELECT state_code, COUNT(*) 
                FROM vehicle_registry 
                GROUP BY state_code
            """)
            state_dist = dict(cur.fetchall())

            return {
                'total_vehicles': total,
                'watchlist_distribution': watchlist_dist,
                'vehicle_types': vehicle_types,
                'state_distribution': state_dist
            }

    def search_vehicles(self, plate_pattern: str = None, state_code: str = None,
                      vehicle_type: str = None, watchlist_status: str = None) -> List[Dict]:
        """
        Search vehicles with optional filters.
        Returns list of matching vehicles.
        """
        query = "SELECT * FROM vehicle_registry WHERE 1=1"
        params = []

        if plate_pattern:
            norm_pattern = normalize_plate(plate_pattern)
            query += " AND normalized_plate LIKE ?"
            params.append(f"%{norm_pattern}%")

        if state_code:
            query += " AND state_code = ?"
            params.append(state_code)

        if vehicle_type:
            query += " AND vehicle_type = ?"
            params.append(vehicle_type)

        if watchlist_status:
            query += " AND watchlist_status = ?"
            params.append(watchlist_status)

        query += " ORDER BY plate_number LIMIT 100"

        with self._connect() as conn:
            cur = conn.execute(query, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self):
        """No-op for backward compatibility."""
        pass


if __name__ == "__main__":
    # Test the vehicle registry
    registry = VehicleRegistry(db_path="outputs/results/test_vehicle_registry.db")

    # Add a test vehicle
    test_vehicle = {
        'plate_number': 'TN38AB1234',
        'state_code': 'TN',
        'rto_code': 38,
        'vehicle_type': 'Car',
        'fuel_type': 'Petrol',
        'registration_status': 'VALID',
        'watchlist_status': 'BLOCKLISTED',
        'watchlist_reason': 'Reported stolen',
        'data_source': 'TEST',
        'last_updated': datetime.now().isoformat()
    }

    vehicle_id = registry.add_vehicle(test_vehicle)
    print(f"Added vehicle with ID: {vehicle_id}")

    # Look up the vehicle
    found = registry.get_vehicle('TN38AB1234')
    print(f"Found vehicle: {found}")

    # Get statistics
    stats = registry.get_registry_stats()
    print(f"Registry stats: {stats}")

    registry.close()