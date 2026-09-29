"""
demo/diagnose_camera.py

Diagnostic: prints every observation currently stored for one camera,
regardless of plate text, so you can see exactly what the real pipeline
did or didn't produce - instead of guessing why a plate search came up
empty (e.g. `python -m demo.scenario_tn38ab1234` reporting a camera as
"missing" even after you ran `visual_pipeline` against it).

Usage (from the project root):
    python -m demo.diagnose_camera CAM_05
    python -m demo.diagnose_camera CAM_05 --limit 20
"""
import argparse

from database.observation_store import ObservationStore
from config import RESULTS_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("camera_id")
    parser.add_argument("--limit", type=int, default=1000,
                         help="how many of the most recent observations (any camera) to scan")
    args = parser.parse_args()

    store = ObservationStore(db_path=str(RESULTS_DIR / "observations.db"))
    rows = [r for r in store.recent_observations(limit=args.limit) if r.get("camera_id") == args.camera_id]
    store.close()

    if not rows:
        print(f"[diagnose] zero observations of ANY plate stored for {args.camera_id}.")
        print(f"[diagnose] that means the pipeline never reached write_observations_to_db() for this "
              f"camera - most likely no vehicle was detected in the image at all (angle/crop/lighting), "
              f"or the run hit an error before writing. Re-run:")
        print(f"    python -m demo.visual_pipeline --camera {args.camera_id}")
        print("and read ITS OWN console output this time (vehicles detected / plate detected / OCR result "
              "lines, or an error/traceback) - this script only reports what's already IN the database, "
              "not what that run actually did.")
        return

    print(f"[diagnose] {len(rows)} observation(s) stored for {args.camera_id} (most recent last):")
    for r in rows[-20:]:
        print(f"  ts={r.get('timestamp')}  plate_text={r.get('plate_text')!r}  "
              f"plate_status={r.get('plate_status')}  reason={r.get('plate_status_reason')!r}  "
              f"raw_ocr_text={r.get('raw_plate_text')!r}  confidence={r.get('confidence')}  "
              f"ocr_confidence={r.get('ocr_confidence')}  plate_state={r.get('plate_state')}  "
              f"data_source={r.get('data_source')}  track_id={r.get('track_id')}")
        # Adaptive-ANPR quality signals - explain WHY OCR failed on a plate that
        # WAS detected ("plate detected, text not read"), not just that it did.
        if r.get("plate_status") in ("detected", "detected_not_read", "detected_no_ocr", "ocr_failed"):
            print(f"      quality: blur={r.get('blur_score')}  brightness={r.get('brightness_score')}  "
                  f"contrast={r.get('contrast_score')}  preprocessing_mode={r.get('preprocessing_mode')!r}  "
                  f"ocr_candidate_count={r.get('ocr_candidate_count')}  "
                  f"plate_quality_score={r.get('plate_quality_score')}")

    exact = [r for r in rows if r.get("plate_text") == "TN38AB1234"]
    if not exact:
        distinct_plates = sorted({r.get("plate_text") for r in rows if r.get("plate_text")})
        print(f"\n[diagnose] none of these {args.camera_id} rows have plate_text exactly matching "
              f"'TN38AB1234'.")
        print(f"[diagnose] distinct plate_text values actually seen for {args.camera_id}: {distinct_plates!r}")
        print("[diagnose] if one of those is close but not identical (one character off), that's a real "
              "OCR misread on this specific photo, not a bug in scenario_tn38ab1234.py - by_plate() only "
              "does an exact string match. Options: re-shoot/crop that camera's photo for a cleaner plate "
              "read, or narrate the real OCR text on screen instead of forcing it to match the other two "
              "cameras.")
        no_plate = [r for r in rows if not r.get("plate_text")]
        if no_plate:
            print(f"[diagnose] also: {len(no_plate)} row(s) for {args.camera_id} have no plate_text at all "
                  f"(plate_status={[r.get('plate_status') for r in no_plate]}) - a vehicle was detected but "
                  "the plate itself wasn't, or OCR produced nothing usable.")
    else:
        real = [r for r in exact if r.get("data_source") == "REAL_INFERENCE"]
        if not real:
            sources = sorted({r.get("data_source") for r in exact})
            print(f"\n[diagnose] {len(exact)} row(s) for {args.camera_id} DO match plate_text exactly, "
                  f"but none are tagged data_source='REAL_INFERENCE' (found: {sources!r}). "
                  "scenario_tn38ab1234.py filters to REAL_INFERENCE only, so these won't count.")
        else:
            print(f"\n[diagnose] {len(real)} exact-match REAL_INFERENCE row(s) found for {args.camera_id} - "
                  "scenario_tn38ab1234.py should pick this up. If it still says 'missing', double check "
                  "you're running it from the same project root / same observations.db as this script.")


if __name__ == "__main__":
    main()
