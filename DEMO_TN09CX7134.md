# TrackX Finale Demo — Vehicle TN09CX7134

This is the runbook for the SIH26127 final-round demo built around the three real
photographs of a white sedan bearing plate **TN 09 CX 7134**, taken at three staged
locations on private property (confirmed with the team — not public-road footage, not
AI-generated). It stands in for the same vehicle passing three of TrackX's seven camera
locations. Every number that ends up on screen — plate text, OCR confidence, plate
state, fusion score — is produced by running the project's real, already-existing code
against those photos. Nothing here is typed into a slide by hand.

One honesty note up front, because it changes how two of the eight scenes should be
scripted: a single still photo per camera gives the real pipeline exactly one OCR
reading at that camera. The "low confidence → multiple frames → temporal fusion →
verified" arc in the original script needs *several* real frames at one camera (a short
video clip) to genuinely happen — `recognition/ocr_reader.py`'s `vote_plate_text()` only
has something to fuse when there's more than one reading. With three stills, the honest
story is: one real OCR reading per camera, of whatever quality the photo actually
produces, fused **across** cameras by `intelligence/fusion.py`'s real matching function —
not fused **within** one camera over time. That's still a real, non-trivial demonstration
of the system's core claim (isolated sightings → one connected journey); it's just a
different claim than "watch confidence climb over multiple frames." If a within-camera
confidence-climb shot matters enough to keep, the fix is a 10–15 second phone video of
the car at one staging spot instead of a single photo there, dropped into that camera's
`videos/` folder — everything below still works unchanged, `process_video()` already
frames-out from video, `frameSpeed`/`maxFrames` on the Detection Pipeline page control
how many frames it samples.

Also: whatever OCR confidence CAM_02's real photo actually produces is what should be
called "low confidence" on screen. It is not being forced low — if the real reading comes
back high-confidence, don't relabel it; either pick a different, genuinely harder-to-read
photo for that beat, or drop that framing from the script.

**2026-09-26 update — CAM_05 dropped, CAM_07 added, watchlist alert added.** CAM_05's
staged photo framed the car too wide; even after a tighter re-crop the plate region stayed
too low-resolution for OCR to read reliably. It's replaced in the journey by CAM_07
(Singanallur Junction) — a fourth real staged photo, same car, same private-property
provenance, this time at night. `CAM_03 → CAM_07` is a real edge in
`network/camera_network.py`'s `ROAD_GRAPH` (10.5km bypass corridor, ~10.5min typical), so
the journey is still road-graph-valid, not an invented shortcut. Everything below now
reads CAM_02 → CAM_03 → CAM_07. Separately, `demo/add_watchlist_tn09cx7134.py` (new, see
step 7) puts this plate on TrackX's real, persisted watchlist
(`database/blacklist_store.py`) so the "suspicious vehicle" beat produces a genuine
`BLACKLISTED_VEHICLE` alert through the app's existing alert-scan + bell-icon flow, not a
slide claiming one.

## 1. Implementation plan

There are two ways to feed the three photos through the real pipeline, and the demo
should use the first one on stage:

**Path A — through the UI (recommended for the recording).** The sidebar's *Detection
Pipeline* page ("Capture & Recognition" section) has a *Camera Media* mode that reads
whatever is already sitting in `data/cameras/<CAMERA_ID>/images/`, runs the same
detection + OCR pipeline, and writes the results to the database live, on screen — a
judge watches inference happen rather than watching a terminal.

**Path B — from the command line**, as a fallback or for scripting: `python -m
demo.visual_pipeline --camera CAM_02` (and `CAM_03`, `CAM_07`). Confirmed in
`backend/app/api/v1/observations.py` that the UI's `POST /api/v1/observations/process-camera`
endpoint calls the *exact same* `process_image()` / `process_video()` /
`write_observations_to_db()` functions this CLI command calls — so both paths produce
identical, equally real rows in the database. Either is honest; Path A is simply the
better visual for a recording.

Either way, running the three cameras back-to-back writes three rows to `observations`
within seconds of each other — not the multi-minute, road-distance-consistent spacing a
real journey across Coimbatore would have. `demo/scenario_tn09cx7134.py` (already written
and committed to `demo/`) fixes exactly that one thing: it re-times those three specific
rows using the project's real `network/camera_network.py` road graph, and then prints the
real `intelligence.fusion.global_match_score()` for each camera-to-camera hop as proof —
not narration — that the matching algorithm actually links them. It touches only the
`timestamp` column; plate text, confidence, and plate_state stay exactly what the real
pipeline produced.

After that, the dashboard's own existing *Vehicle Search* and *Trajectory Search* pages
already reconstruct and map the journey — no new screen is needed.

## 2. Database schema changes required

None. `database/observation_store.py`'s `observations` table already has every column
this demo touches: `vehicle_id`, `plate_text`, `plate_state`, `camera_id`, `timestamp`,
`latitude`, `longitude`, `confidence`, `appearance_vector`, and `data_source` (which the
real pipeline stamps `"REAL_INFERENCE"` unconditionally, regardless of whether the input
photo was a live camera frame or a staged one — see the note in `scenario_tn09cx7134.py`'s
docstring). No migration, no new table, no new field.

## 3. Backend/API changes required

None. `POST /api/v1/observations/process-camera` (Path A above) and the CLI's
`run_camera()` (Path B) already run the real pipeline and persist real rows. `GET
/api/v1/observations/.../media-info`-style endpoint already reports how many images sit
in a camera's folder, which is what the Camera Media tab shows before you click anything.
Vehicle search, trajectory reconstruction, and the GIS endpoints the dashboard calls
already exist and already work off whatever is in the `observations` table — they don't
know or care that this particular vehicle's rows came from three still photos.

## 4. Frontend/dashboard changes required

None. Three existing pages already cover the whole script, confirmed by reading their
source directly:

- **Detection Pipeline** (`/ai-processing`, sidebar label "Detection Pipeline") — Camera
  Media mode. Shows "N image(s), N video(s) available" per camera, a *Start Detection
  Pipeline* button, and — once run — a result card ("Processed `<camera name>`: N vehicle
  observation(s), N written to the database.") plus a "Latest Plate" panel with the real
  plate text and confidence percentage.
- **Vehicle Search** (`/vehicles`, page heading "Vehicle Intelligence") — search by plate,
  returns the reconstructed multi-camera trajectory with a per-hop `plate_state` chip
  (VERIFIED / TENTATIVE / LOW_CONFIDENCE / UNKNOWN, already color-coded) and a "comes from
  plate + timing + topology matching" explainer on the fusion badge.
- **Trajectory Search** (`/trajectory`, page heading "Multi-Camera Trajectory
  Reconstruction") — same plate search, but drawn on the real Leaflet map over the real
  Coimbatore road corridors, with OCR confidence per hop.

All three already existed before this demo was scoped; nothing needed to be added or
changed for TN09CX7134 specifically.

## 5. Demo video — scene-by-scene

Mapped onto the real screens above, not invented ones:

1. **Camera 1 (CAM_02, Tidel Park Junction).** Open *Detection Pipeline* → Camera Media,
   select CAM_02, show the real "1 image(s) available" line, click *Start Detection
   Pipeline*. Let the real processing state show ("Processing…") for however long it
   actually takes.
2. **Result.** The real result card appears — read whatever it actually says, don't
   pre-write the numbers. If the real OCR confidence comes back low, that's the honest
   "needs verification" beat from the original script; if it comes back high, say so
   instead of forcing a "low confidence" line that isn't true.
3. **Camera 2 & 3 (CAM_03 RS Puram, CAM_07 Singanallur Junction, night).** Repeat the same
   two beats for each. This is the "isolated sightings at different places and times" half
   of the pitch — three independent, unlinked rows in the database at this point.
4. **The re-timing + fusion pass.** Run `python -m demo.scenario_tn09cx7134` once, on
   screen (terminal overlay is fine here — this step is inherently a backend/data step,
   not a UI one). Its printed output *is* the proof: the real per-hop
   plate/appearance/temporal/spatial breakdown and total score from
   `global_match_score()`, not a number someone typed.
5. **Vehicle Search.** Open `/vehicles`, type TN09CX7134, search. Show the reconstructed
   3-hop trajectory card with the real plate_state chips and the fusion explainer.
6. **Trajectory Search / GIS Map.** Same plate, now on the real Leaflet map — the three
   staged locations connected along TrackX's real road-corridor data.
7. **Suspicious-vehicle alert.** Click the bell icon (top right of every page). Because
   `demo/add_watchlist_tn09cx7134.py` was run beforehand, this click triggers a real
   `GET /alerts` call, which re-scans all current observations against the watchlist and
   finds this one — a genuine `BLACKLISTED_VEHICLE` / HIGH severity alert appears in the
   dropdown (and on the Alerts page), with this plate and camera. Nothing pre-staged in
   the UI; this is the same alert-scan path the app already uses for every other alert.
8. **Closing line, spoken or on a title card:** "TrackX transforms isolated CCTV
   observations into a connected vehicle journey." This is the one piece of scripted
   text in the whole sequence — everything before it is a live screen recording of real
   output.

## 6. Exact text and labels to use

Pulled verbatim from the source rather than reworded, so voiceover/captions match what's
actually on screen: sidebar labels *Detection Pipeline*, *Vehicle Search*, *Trajectory
Search*, *GIS Map*; button text *Start Detection Pipeline*; the result line "Processed
`<camera name>`: `<N>` vehicle observation(s), `<N>` written to the database."; the
"Latest Plate" panel; page headings "Vehicle Intelligence" and "Multi-Camera Trajectory
Reconstruction"; plate-state values `VERIFIED`, `TENTATIVE`, `LOW_CONFIDENCE`, `UNKNOWN`
exactly as the badge renders them (don't relabel "TENTATIVE" as "medium confidence" or
similar — it isn't what the code says). The one number that must never be pre-written is
the fusion match score or percentage — read it off `scenario_tn09cx7134.py`'s actual
printed output for that specific run, since it depends on the real image content and can
differ run to run.

## 7. How to run the complete demo, start to finish

1. Confirm the photos are already in place (done, committed this session):
   `data\cameras\CAM_02\images\cam02_tn09cx7134.jpg`, `data\cameras\CAM_03\images\cam03_tn09cx7134.jpg`,
   `data\cameras\CAM_07\images\cam07_tn09cx7134.jpg`. (Note: `data\cameras\CAM_07\images\` already
   had one other file in it, `WhatsApp Image 2026-09-04 at 5.22.18 PM.jpeg` — worth a quick look
   before recording in case it's an unrelated leftover; it won't break anything since the scenario
   script only keeps the newest matching-plate row per camera, but it will get processed too.)
2. Start the backend from the repo root: `pip install -r requirements.txt -r backend/requirements.txt`
   (first time only), then `cd backend` and `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
3. In a second terminal, start the frontend: `cd frontend`, `npm install` (first time
   only), `npm run dev` — opens at `http://localhost:3000` and talks to the backend
   automatically.
4. Log in (via `/docs` or the login screen, using whichever account exists against this
   backend — credentials aren't repeated here).
5. From the repo root, once: `python -m demo.add_watchlist_tn09cx7134` (puts the plate on
   the real watchlist — do this before recording, it only needs to run once).
6. On *Detection Pipeline* → Camera Media, run CAM_02, then CAM_03, then CAM_07 in turn
   (Scenes 1–3 above), or equivalently `python -m demo.visual_pipeline --camera CAM_02`
   / `CAM_03` / `CAM_07` from the repo root if recording the UI live isn't wanted for
   those beats.
7. From the repo root: `python -m demo.scenario_tn09cx7134` (Scene 4).
8. On *Vehicle Search*, search `TN09CX7134` (Scene 5).
9. On *Trajectory Search* or *GIS Map*, search/select the same plate for the map view
   (Scene 6).
10. Click the bell icon to trigger and show the real watchlist alert (Scene 7).

## 8. How to reset and replay

`ObservationStore` has no generic delete-by-plate method — only `delete_camera_observations(camera_id)`,
which would also remove any other traffic seeded on that camera. For a clean re-run of
just this scenario, delete only this plate's rows directly:

```bash
python -c "
from database.observation_store import ObservationStore
from config import RESULTS_DIR
store = ObservationStore(db_path=str(RESULTS_DIR / 'observations.db'))
store.conn.execute(\"DELETE FROM observations WHERE plate_text = 'TN09CX7134'\")
store.conn.commit()
store.close()
"
```

Then repeat steps 5–8 above. For a full reset of the entire demo database instead
(all cameras, all seeded background traffic, not just this plate), use the project's
existing `python -m demo.seed_demo_data --reset` from the repo root — this also reseeds
the generic background traffic list, which no longer collides with TN09CX7134 since that
plate was renamed to TN14PQ6655 in `demo/seed_demo_data.py`'s background list specifically
so the two scenarios can't overwrite each other's story.
