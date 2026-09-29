"""
demo/clear_tn09cx7134.py

Deletes every stored observation AND every persisted alert for plate
TN09CX7134 (does NOT touch its watchlist entry - see
demo/add_watchlist_tn09cx7134.py, which manages that separately). Use this
once before recording the real demo (see DEMO_TN09CX7134.md), and again
any time you want to replay it from a clean slate.

Why observations needed clearing: demo/seed_demo_data.py used to include
TN09CX7134 in its generic background-traffic list (Gandhipuram Junction ->
Tidel Park Junction -> RS Puram Signal -> Town Hall Junction, 4 hops, all
tagged data_source="DEMO_SYNTHETIC"). That collision was fixed in
seed_demo_data.py (the entry was renamed to TN14PQ6655), but that fix only
takes effect on a fresh `python -m demo.seed_demo_data --reset` - it does
NOT retroactively remove rows a previous seed run already wrote to your
database.

Why alerts also need clearing (2026-09-26 addition): AlertStore.add_alert()
is idempotent on (plate, alert_type, camera_id, timestamp) - see
database/alert_store.py's docstring - so if an alert for this plate was
already persisted once (e.g. with an old/wrong watchlist description, or
against observations that get re-timed or replaced by a later run), a
rescan will NOT overwrite it; the stale row just sits there. Deleting it
here lets the next GET /alerts call create a fresh one from whatever
observations and watchlist entry currently exist.

Usage (from the project root):
    python -m demo.clear_tn09cx7134
"""
from database.observation_store import ObservationStore
from database.alert_store import AlertStore
from config import RESULTS_DIR

PLATE = "TN09CX7134"
DB_PATH = str(RESULTS_DIR / "observations.db")


def main():
    obs_store = ObservationStore(db_path=DB_PATH)
    before = obs_store.by_plate(PLATE)
    if before:
        by_source = {}
        for row in before:
            by_source[row.get("data_source")] = by_source.get(row.get("data_source"), 0) + 1
        print(f"[clear] found {len(before)} existing observation(s) for {PLATE}:")
        for source, count in by_source.items():
            print(f"    {count} row(s) with data_source={source!r}")
        obs_store.conn.execute("DELETE FROM observations WHERE plate_text = ?", (PLATE,))
        obs_store.conn.commit()
        after = obs_store.by_plate(PLATE)
        print(f"[clear] deleted. {len(after)} observation(s) remain for {PLATE} (expected 0).")
    else:
        print(f"[clear] no stored observations for {PLATE}.")
    obs_store.close()

    alert_store = AlertStore(db_path=DB_PATH)
    cur = alert_store.conn.execute("SELECT COUNT(*) FROM alerts WHERE plate = ?", (PLATE,))
    alert_count = cur.fetchone()[0]
    if alert_count:
        alert_store.conn.execute("DELETE FROM alerts WHERE plate = ?", (PLATE,))
        alert_store.conn.commit()
        print(f"[clear] deleted {alert_count} persisted alert(s) for {PLATE}.")
    else:
        print(f"[clear] no persisted alerts for {PLATE}.")
    alert_store.close()

    print("[clear] now run Detection Pipeline on CAM_02, CAM_03, CAM_07, "
          "then `python -m demo.scenario_tn09cx7134` per DEMO_TN09CX7134.md. "
          "The watchlist entry itself was left alone - re-run "
          "demo.add_watchlist_tn09cx7134 separately only if you changed its text.")


if __name__ == "__main__":
    main()
