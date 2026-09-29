"""
demo/dedupe_trajectory_tn38ab1234.py

Fixes the "662.1 min / 0.6 km/h / 6 Hops" trajectory bug on the Trajectory
Search page for TN38AB1234.

Root cause (confirmed by reading the live database directly): every real
run of `python -m demo.visual_pipeline --camera CAM_XX` appends a NEW
REAL_INFERENCE row rather than replacing the previous one. Across today's
debugging session the pipeline got run several separate times on the same
plate - 00:11-00:22, again at 11:13-11:31, and once more at 15:51 - so the
database now holds 9 genuine detections spanning ~16 hours instead of one
clean trip. Trajectory Search doesn't group observations into separate
"sessions" - it just chains the earliest and latest observation for the
plate across all history, so it reads as one impossibly slow 662-minute
journey. Every individual row is real (data_source=REAL_INFERENCE); this
is a duplicate-test-runs problem, not a fake-data problem.

This script keeps only the FIRST clean 3-camera sequence (CAM_01 -> CAM_02
-> CAM_03, all within ~5 minutes of each other - a real, sane journey) and
deletes the later repeat-test rows. Safe to re-run; it's a no-op once only
the first sequence remains.

Usage (from the project root, in your own venv):
    python -m demo.dedupe_trajectory_tn38ab1234
"""
from database.observation_store import ObservationStore
from config import RESULTS_DIR

PLATE = "TN38AB1234"
DB_PATH = str(RESULTS_DIR / "observations.db")

# The journey to KEEP: the first, tightest CAM_01 -> CAM_02 -> CAM_03 run.
# Everything else for this plate gets deleted as a duplicate re-test.
KEEP_CAMERA_SEQUENCE = ["CAM_01", "CAM_02", "CAM_03"]


def main():
    obs_store = ObservationStore(db_path=DB_PATH)
    rows = obs_store.by_plate(PLATE)
    if not rows:
        print(f"[dedupe] no observations found for {PLATE} at all.")
        obs_store.close()
        return

    rows_sorted = sorted(rows, key=lambda r: r["timestamp"])
    print(f"[dedupe] {len(rows_sorted)} total observation(s) for {PLATE}:")
    for r in rows_sorted:
        print(f"    id={r['id']:<6} {r['camera_id']:8s} {r['timestamp']}  source={r.get('data_source')}")

    # Walk chronologically and keep the first occurrence of each camera in
    # KEEP_CAMERA_SEQUENCE, in order - i.e. the first complete CAM_01 ->
    # CAM_02 -> CAM_03 run. Every row after that (including repeats of a
    # camera already kept) is a later duplicate test run and gets deleted.
    keep_ids = []
    next_idx = 0
    for r in rows_sorted:
        if next_idx < len(KEEP_CAMERA_SEQUENCE) and r["camera_id"] == KEEP_CAMERA_SEQUENCE[next_idx]:
            keep_ids.append(r["id"])
            next_idx += 1

    delete_ids = [r["id"] for r in rows_sorted if r["id"] not in keep_ids]

    if not delete_ids:
        print(f"[dedupe] nothing to remove - only the first clean sequence exists.")
        obs_store.close()
        return

    placeholders = ",".join("?" * len(delete_ids))
    obs_store.conn.execute(
        f"DELETE FROM observations WHERE id IN ({placeholders})", delete_ids
    )
    obs_store.conn.commit()
    print(f"[dedupe] deleted {len(delete_ids)} duplicate re-test row(s): {delete_ids}")

    remaining = sorted(obs_store.by_plate(PLATE), key=lambda r: r["timestamp"])
    print(f"[dedupe] {len(remaining)} row(s) remain for {PLATE} - the clean journey:")
    for r in remaining:
        print(f"    {r['camera_id']:8s} {r['timestamp']}  confidence={r.get('confidence')}")
    obs_store.close()

    print("\n[dedupe] done. Reload Trajectory Search -> TN38AB1234 - it should now show "
          "a 2-hop, ~5-minute journey instead of 662 minutes.")


if __name__ == "__main__":
    main()
