# TrackX repair pass — 2026-08-25

This build is a stability-focused repair of the uploaded TrackX project.

Verified:
- Full pytest suite: 176 passed, 6 skipped.
- OCR init success regression fixed: try_init_ocr now returns the constructed instance.
- Appearance model no longer requires an internet download by default. It uses cached ResNet18 weights when present and falls back to the existing histogram embedding otherwise. Set TRACKX_ALLOW_MODEL_DOWNLOAD=1 to opt into first-time downloads.
- Project paths for the visual pipeline, database and dashboard use config.py/project-root paths.
- Dashboard "Latest AI Result" now selects the newest observation by DB id/timestamp instead of preferring an older successful OCR result.
- Plate bbox documentation now correctly states that stored coordinates are frame coordinates.
- Added ObservationStore.delete_camera_observations().
- Added `--fresh` to the visual pipeline so a camera can be reprocessed without stale generated observations/artifacts.
- Vehicle appearance embeddings are computed from the full vehicle crop.

Important:
- Existing generated DB/media are historical artifacts. Re-run the camera with `--fresh` to regenerate its observation-specific annotated images and database rows.
- Do not delete source images/videos.
- Integration tests remain skipped where the real external model/runtime stack is unavailable; this is expected.

Recommended first run:
    python -m pytest -q

Then, for a clean camera rebuild:
    python -m demo.visual_pipeline --camera CAM_02 --fresh

For the dashboard:
    streamlit run dashboard/dashboard.py
