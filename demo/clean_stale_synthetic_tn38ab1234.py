"""
demo/clean_stale_synthetic_tn38ab1234.py

Targeted cleanup for the "24963m 3s" / "0 km/h" / weird "Impossible travel
time" anomaly seen on the live Vehicle Search page for TN38AB1234.

Root cause: this plate collided with an OLD DEMO_SYNTHETIC seed entry
(3 rows: CAM_02 Tidel Park, CAM_03 RS Puram, CAM_04 Lakshmi Mills, dated
~10 Sept 2026) that happened to reuse the same plate text, left over from
an earlier demo/seed_demo_data.py run. Once the real TN38AB1234 photo was
run through the pipeline (fresh REAL_INFERENCE rows, ~27 Sept 2026), the
trajectory reconstruction spans BOTH sets - first_seen ~10 Sept, last_seen
~27 Sept - a genuine ~17-day gap. That is where "24963m 3s" comes from
(backend/app/api/v1/vehicles.py literally computes
(last_seen - first_seen).total_seconds() // 60, with no day/hour rollover),
and why average speed rounds to "0 km/h" (a few km over 17 days is ~0).

Unlike demo/clear_tn38ab1234.py (which wipes EVERY observation for this
plate, real ones included, for a full reset-and-replay), this script keeps
your real detections and removes ONLY the stale, unrelated DEMO_SYNTHETIC
rows that are polluting the trajectory. Safe to run any time; re-running it
is a no-op once the synthetic rows are gone.

Usage (from the project root, in your own venv):
    python -m demo.clean_stale_synthetic_tn38ab1234
"""
from database.observation_store import ObservationStore
from database.alert_store import AlertStore
from config import RESULTS_DIR

PLATE = "TN38AB1234"
DB_PATH = str(RESULTS_DIR / "observations.db")


def main():
    obs_store = ObservationStore(db_path=DB_PATH)
    rows = obs_store.by_plate(PLATE)
    if not rows:
        print(f"[clean] no observations found for {PLATE} at all.")
        obs_store.close()
        return

    by_source = {}
    for r in rows:
        by_source.setdefault(r.get("data_source"), []).append(r)

    print(f"[clean] {len(rows)} total observation(s) for {PLATE}:")
    for source, group in by_source.items():
        cams = sorted({r.get("camera_id") for r in group})
        print(f"    {len(group)} row(s) with data_source={source!r}  cameras={cams}")

    stale = [r for r in rows if r.get("data_source") != "REAL_INFERENCE"]
    if not stale:
        print(f"[clean] nothing to remove - every row for {PLATE} is already REAL_INFERENCE.")
        obs_store.close()
        return

    ids = [r["id"] for r in stale]
    placeholders = ",".join("?" * len(ids))
    obs_store.conn.execute(
        f"DELETE FROM observations WHERE id IN ({placeholders})", ids
    )
    obs_store.conn.commit()
    print(f"[clean] deleted {len(ids)} stale non-REAL_INFERENCE row(s) for {PLATE}.")

    remaining = obs_store.by_plate(PLATE)
    print(f"[clean] {len(remaining)} row(s) remain for {PLATE}, all REAL_INFERENCE:")
    for r in sorted(remaining, key=lambda r: r["timestamp"]):
        print(f"    {r['camera_id']:8s} {r['timestamp']}  confidence={r.get('confidence')}")
    obs_store.close()

    # Any alert already persisted against the stale observations would still
    # reference this plate correctly (alerts key on plate, not observation
    # id), so nothing to clean there - but if the Alerts page still shows a
    # stale-looking entry after this, re-open the bell icon / Alerts page to
    # force a fresh GET /alerts scan against the now-clean observation set.
    print("\n[clean] done. Re-open Vehicle Search -> TN38AB1234 - Travel Time and "
          "Avg Speed should now reflect only the real observations.")


if __name__ == "__main__":
    main()
