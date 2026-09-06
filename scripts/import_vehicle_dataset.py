"""
import_vehicle_dataset.py

Script to import the SIH_ANPR_10000_vehicle_demo_dataset.xlsx into the TrackX vehicle registry.

Usage:
    python -m scripts.import_vehicle_dataset --input path/to/dataset.xlsx
    python -m scripts.import_vehicle_dataset --input path/to/dataset.xlsx --sync-blacklist
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from database.vehicle_registry import VehicleRegistry
from database.blacklist_store import BlacklistStore
from config import DB_PATH_STR


def import_dataset(excel_path: str, sync_blacklist: bool = False) -> dict:
    """
    Import vehicle dataset from Excel file into the vehicle registry.

    Args:
        excel_path: Path to the Excel file
        sync_blacklist: Whether to sync watchlisted vehicles to blacklist system

    Returns:
        Dictionary with import statistics
    """
    print(f"Starting vehicle dataset import from: {excel_path}")

    # Load the Excel file
    try:
        df = pd.read_excel(excel_path)
        print(f"Loaded {len(df)} vehicle records from Excel file")
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return {'error': str(e)}

    # Initialize vehicle registry
    registry = VehicleRegistry(db_path=DB_PATH_STR)
    print(f"Vehicle registry initialized at: {DB_PATH_STR}")

    # Import vehicles
    print("Importing vehicles into registry...")
    import_stats = registry.bulk_import(df)

    print(f"Import completed:")
    print(f"   Total records: {import_stats['total']}")
    print(f"   Successfully imported: {import_stats['success']}")
    print(f"   Failed: {import_stats['failed']}")
    print(f"   Watchlisted vehicles: {import_stats['watchlisted']}")

    # Get registry statistics
    registry_stats = registry.get_registry_stats()
    print(f"\nRegistry Statistics:")
    print(f"   Total vehicles in registry: {registry_stats['total_vehicles']}")
    print(f"   Watchlist distribution: {registry_stats['watchlist_distribution']}")
    print(f"   Vehicle types: {registry_stats['vehicle_types']}")
    print(f"   State distribution: {registry_stats['state_distribution']}")

    # Sync to blacklist if requested
    blacklist_stats = {}
    if sync_blacklist:
        print(f"\nSyncing watchlisted vehicles to blacklist system...")
        blacklist_store = BlacklistStore(db_path=DB_PATH_STR)
        blacklist_stats = registry.sync_to_blacklist(blacklist_store)

        print(f"Blacklist sync completed:")
        print(f"   Total watchlisted vehicles: {blacklist_stats['total']}")
        print(f"   HIGH severity (BLOCKLISTED): {blacklist_stats['high_severity']}")
        print(f"   MEDIUM severity (REVIEW): {blacklist_stats['medium_severity']}")
        print(f"   Failed: {blacklist_stats['failed']}")

        blacklist_store.close()

    registry.close()

    return {
        'import_stats': import_stats,
        'registry_stats': registry_stats,
        'blacklist_stats': blacklist_stats
    }


def main():
    parser = argparse.ArgumentParser(
        description="Import SIH vehicle dataset into TrackX vehicle registry"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the Excel dataset file"
    )
    parser.add_argument(
        "--sync-blacklist",
        action="store_true",
        help="Sync watchlisted vehicles to the blacklist system"
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    try:
        results = import_dataset(args.input, args.sync_blacklist)
        print(f"\nDataset import completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()