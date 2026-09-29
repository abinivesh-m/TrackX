"""
demo/clear_tn38ab1234.py

Deletes every stored observation AND every persisted alert for plate
TN38AB1234 (does NOT touch its watchlist entry - see
demo/add_watchlist_tn38ab1234.py, which manages that separately). Use this
once before recording the real demo, and again any time you want to
replay it from a clean slate. Mirrors demo/clear_tn09cx7134.py, which this
replaces for the finale demo vehicle swap.

Usage (from the project root):
    python -m demo.clear_tn38ab1234
"""
from database.observation_store import ObservationStore
from database.alert_store import AlertStore
from config import RESULTS_DIR

PLATE = "TN38AB1234"
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

    print("[clear] now run Detection Pipeline on CAM_01, CAM_02, CAM_03, "
          "then `python -m demo.scenario_tn38ab1234`. "
          "The watchlist entry itself was left alone - re-run "
          "demo.add_watchlist_tn38ab1234 separately only if you changed its text.")


if __name__ == "__main__":
    main()
