"""
demo/add_watchlist_tn38ab1234.py

Flags TN38AB1234 on TrackX's real, persisted operational watchlist
(database/blacklist_store.py - the same store backend/app/api/v1/vehicles.py's
POST /watchlist endpoint writes to), so the demo's "suspicious vehicle"
beat is a genuine alert, not a slide claiming one. Replaces the earlier
TN09CX7134 watchlist entry for the finale demo vehicle swap.

How this actually surfaces during the demo (no new UI/code needed - this
already exists and is wired up):
  1. Run this script once, before recording.
  2. Process CAM_01, CAM_02, CAM_03 (Detection Pipeline or `visual_pipeline`
     CLI) so real observations for this plate exist.
  3. Run `python -m demo.scenario_tn38ab1234` as usual.
  4. Open the app and click the bell icon (top right) OR open the Alerts
     page. Both call GET /api/v1/alerts, which runs
     intelligence.alerts.scan_trajectories_for_alerts() fresh on every call
     (see backend/app/api/v1/alerts.py's _refresh_detected_alerts) - it
     will find the real observations matching this now-blacklisted plate
     and persist a real BLACKLISTED_VEHICLE alert, which then shows up in
     the bell's dropdown and on /alerts, both already built.

Usage (from the project root, run once):
    python -m demo.add_watchlist_tn38ab1234

Safe to re-run: unlike a bare add_plate() call (which is idempotent and
would silently keep an old entry's description), this script always
deactivates any existing active entry for this plate first, then adds a
fresh one - so re-running it after an edit here (e.g. to fix the
description text) actually replaces what's on screen instead of leaving
the old one active underneath the new one.
"""
from database.blacklist_store import BlacklistStore

PLATE = "TN38AB1234"

# Same convention as the TN09CX7134 version this replaces: the card's own
# "DEMO WATCHLIST - not a real record" badge (AlertsPage.tsx) already
# carries the honesty disclosure, so this text reads like a real ANPR
# watchlist entry would, not like an internal dev note.
DESCRIPTION = "Reported stolen vehicle - flagged for tracking and interception."


def main():
    store = BlacklistStore()
    try:
        # Always refresh rather than rely on add_plate()'s idempotency, so
        # re-running this script after editing DESCRIPTION/severity above
        # actually takes effect instead of silently keeping the old entry.
        store.deactivate_plate(PLATE)
        entry_id = store.add_plate(
            PLATE,
            description=DESCRIPTION,
            severity="HIGH",
            # 'DEMO_SEED' (not the default 'OPERATOR') - honest labeling per
            # this project's own convention: a real operator didn't flag
            # this car, the demo script did. See BlacklistStore.add_plate's
            # docstring for the two valid source values.
            source="DEMO_SEED",
        )
    finally:
        active = store.get_active_entry(PLATE)
        store.close()

    print(f"[watchlist] {PLATE} is on the active watchlist (entry id={entry_id}).")
    if active:
        print(f"[watchlist] severity={active.get('severity')}  source={active.get('source')}  "
              f"description={active.get('description')!r}")
    print("[watchlist] next: process CAM_01/CAM_02/CAM_03, run demo.scenario_tn38ab1234, "
          "then open the app and click the bell icon (or the Alerts page) to trigger the real "
          "alert scan and see the BLACKLISTED_VEHICLE alert appear for real.")


if __name__ == "__main__":
    main()
