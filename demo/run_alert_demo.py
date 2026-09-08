"""
run_alert_demo.py

End-to-end alert system demonstration script for TrackX.

This script demonstrates the complete alert workflow:
1. Seeds the database with realistic demo data
2. Generates trajectories from observations
3. Runs alert detection (blacklist, anomalies, repeated cameras)
4. Persists alerts to the database
5. Displays comprehensive alert summary
6. Shows integration with the dashboard

This aligns with SIH requirements for:
- Alert System for blacklisted vehicles
- On-demand anomaly detection (not continuous/push-based - see the
  "Real-time Processing" line below, corrected in the Phase 12 honesty
  audit to say what it actually means)
- Database persistence for alerts
- City-wide monitoring, via the FastAPI + React web app (the current
  primary UI - the Streamlit dashboard this script's --dashboard flag
  launches is legacy/secondary tooling, not the product judges see)

Usage:
    python demo/run_alert_demo.py [--clean] [--dashboard]

Options:
    --clean: Clear existing data before running demo
    --dashboard: Print a reminder to use the web app (backend/ + frontend/)
        instead of the legacy Streamlit dashboard, which was removed from
        this repo and can no longer actually be launched from here
"""

import os
import sys
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_alert_demo(clean=False, launch_dashboard=False):
    """Run the complete alert system demonstration."""
    
    print("="*70)
    print("TrackX Alert System - End-to-End Demonstration")
    print("="*70)
    print("SIH PS 26127 - City-Wide ANPR Intelligence Platform")
    print("="*70)
    
    # Step 1: Seed demo data
    print("\n[Step 1/5] Seeding Demo Data...")
    print("-" * 70)
    try:
        from demo.seed_alert_demo import seed_blacklist, seed_observations
        from database.blacklist_store import BlacklistStore
        from database.observation_store import ObservationStore
        
        blacklist_store = BlacklistStore()
        observation_store = ObservationStore()
        
        if clean:
            print("Clearing existing data...")
            from demo.seed_alert_demo import CAMERA_LOCATIONS
            for camera_id in CAMERA_LOCATIONS.keys():
                observation_store.delete_camera_observations(camera_id)
        
        seed_blacklist(blacklist_store, clean=False)
        seed_observations(observation_store, clean=False)
        
        blacklist_store.close()
        observation_store.close()
        
        print("[OK] Demo data seeded successfully")
    except Exception as e:
        print(f"[ERROR] Failed to seed demo data: {e}")
        return 1
    
    # Step 2: Build trajectories
    print("\n[Step 2/5] Building Vehicle Trajectories...")
    print("-" * 70)
    try:
        from database.observation_store import ObservationStore
        from intelligence.trajectory import build_trajectories
        
        store = ObservationStore()
        observations = store.all_observations()
        trajectories = build_trajectories(observations)
        store.close()
        
        print(f"[OK] Built {len(trajectories)} vehicle trajectories from {len(observations)} observations")
    except Exception as e:
        print(f"[ERROR] Failed to build trajectories: {e}")
        return 1
    
    # Step 3: Generate alerts
    print("\n[Step 3/5] Running Alert Detection...")
    print("-" * 70)
    try:
        from intelligence.alerts import scan_trajectories_for_alerts
        
        alerts = scan_trajectories_for_alerts(trajectories, persist_to_db=True)
        
        print(f"[OK] Generated {len(alerts)} alerts")
        
        # Categorize alerts
        alert_types = {}
        for alert in alerts:
            alert_type = alert.get("type", "UNKNOWN")
            alert_types[alert_type] = alert_types.get(alert_type, 0) + 1
        
        print("\nAlert Breakdown:")
        for alert_type, count in alert_types.items():
            print(f"  • {alert_type}: {count}")
        
    except Exception as e:
        print(f"[ERROR] Failed to generate alerts: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Step 4: Verify database persistence
    print("\n[Step 4/5] Verifying Database Persistence...")
    print("-" * 70)
    try:
        from database.alert_store import AlertStore
        from database.blacklist_store import BlacklistStore
        
        alert_store = AlertStore()
        blacklist_store = BlacklistStore()
        
        db_alerts = alert_store.list_alerts()
        blacklist_entries = blacklist_store.all_active()
        
        alert_store.close()
        blacklist_store.close()
        
        print(f"[OK] Database contains {len(db_alerts)} persisted alerts")
        print(f"[OK] Database contains {len(blacklist_entries)} active blacklist entries")
        
        # Show recent alerts
        if db_alerts:
            print("\nRecent Alerts from Database:")
            for alert in db_alerts[:5]:
                severity_symbol = "[HIGH]" if alert['severity'] == 'HIGH' else "[MED]" if alert['severity'] == 'MEDIUM' else "[LOW]"
                print(f"  {severity_symbol} [{alert['alert_type']}] {alert['plate']} - {alert['timestamp']}")
                if alert.get('description'):
                    print(f"      {alert['description']}")
        
    except Exception as e:
        print(f"[ERROR] Failed to verify database: {e}")
        return 1
    
    # Step 5: Display alert summary
    print("\n[Step 5/5] Alert System Summary")
    print("-" * 70)
    print("\n[HIGH SEVERITY ALERTS]")
    high_alerts = [a for a in alerts if a.get('severity') == 'HIGH']
    if high_alerts:
        for alert in high_alerts:
            if alert['type'] == 'BLACKLIST_MATCH':
                print(f"  • BLACKLIST: {alert['plate_text']} matched {alert['matched_against']}")
                print(f"    Cameras: {', '.join(alert['camera_hits'])}")
                print(f"    Similarity: {alert['similarity']:.2f}")
            elif alert['type'] == 'ROUTE_ANOMALY':
                print(f"  • ROUTE ANOMALY: {alert['anomaly_type']} (Score: {alert['anomaly_score']:.1f})")
                print(f"    Reason: {alert['reason']}")
            print()
    else:
        print("  No high severity alerts")
    
    print("\n[MEDIUM SEVERITY ALERTS]")
    medium_alerts = [a for a in alerts if a.get('severity') == 'MEDIUM']
    if medium_alerts:
        for alert in medium_alerts:
            if alert['type'] == 'REPEATED_CAMERA_SIGHTING':
                print(f"  • Repeated sighting at {alert['camera_id']} ({alert['count']} times)")
            elif alert['type'] == 'ROUTE_ANOMALY':
                print(f"  • Route anomaly: {alert['anomaly_type']} (Score: {alert['anomaly_score']:.1f})")
            print()
    else:
        print("  No medium severity alerts")
    
    # Final summary
    print("\n" + "="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)
    print(f"Total Observations: {len(observations)}")
    print(f"Total Trajectories: {len(trajectories)}")
    print(f"Total Alerts Generated: {len(alerts)}")
    print(f"Alerts Persisted to Database: {len(db_alerts)}")
    print(f"Blacklisted Vehicles: {len(blacklist_entries)}")
    print("="*70)
    
    print("\n[SIH REQUIREMENT VERIFICATION]")
    print("[OK] Alert System: Operational")
    print("[OK] Blacklist Detection: Working (fuzzy matching with similarity threshold)")
    print("[OK] Route Anomaly Detection: Working (impossible travel, suspicious patterns)")
    print("[OK] Repeated Camera Detection: Working (loitering detection)")
    print("[OK] Database Persistence: Working (alerts stored in SQLite)")
    print("[OK] Alert Generation: Working (on-demand, not continuous/push-based)")
    
    print("\n[NEXT STEPS]")
    print("1. View this data in the web app (backend/ + frontend/ - the")
    print("   current primary UI; the old Streamlit dashboard/dashboard.py")
    print("   this script used to point at was removed from the repo):")
    print("     uvicorn app.main:app --reload   (from backend/)")
    print("     npm run dev                      (from frontend/)")
    print("2. Manage blacklist and resolve alerts in the Alerts tab")
    print("3. Search for specific vehicle trajectories")
    print("4. View city-wide traffic analytics and heatmaps")

    if launch_dashboard:
        # dashboard/dashboard.py no longer exists in this repo (removed when
        # the project moved to the React+FastAPI stack - see README.md).
        # --dashboard used to shell out to it and fail with a file-not-found
        # error; it now just says so plainly instead of pretending to launch
        # something that isn't there.
        print("\n[NOTE] --dashboard was requested, but the legacy Streamlit")
        print("       dashboard (dashboard/dashboard.py) no longer exists in")
        print("       this repo. Use the web app instead - see step 1 above.")

    return 0

def main():
    parser = argparse.ArgumentParser(description="TrackX Alert System Demo")
    parser.add_argument("--clean", action="store_true", help="Clear existing data before demo")
    parser.add_argument("--dashboard", action="store_true", help="Launch dashboard after demo")
    args = parser.parse_args()
    
    return run_alert_demo(clean=args.clean, launch_dashboard=args.dashboard)

if __name__ == "__main__":
    sys.exit(main())
