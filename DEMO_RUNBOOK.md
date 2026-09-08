# TrackX — Demo Runbook (SIH 26127)

One command resets the whole demo to a known-good state. Everything below
was verified live this session against a fresh reset — not assumed.

## Reset before you present (or before a rehearsal)

From the project root:

```
python -m demo.seed_demo_data --reset
```

This does everything needed in one step:
- Wipes the demo database (observations, blacklist, alerts, congestion
  events — one shared SQLite file) and reseeds it with the same fixed
  scenario every time (`--seed 42` by default) — **deterministic**, not
  randomized per run.
- Seeds 84 observations across all 7 cameras: clean multi-camera
  trajectories, a blacklisted vehicle, a watchlisted vehicle, a noisy-OCR
  plate-matching case, a repeated-camera-sighting case, an impossible-
  transition route anomaly, and a possible-cloned-plate case — plus ~40
  background sightings for realistic density/analytics.
- Registers the 2 demo blacklist/watchlist entries (tagged `DEMO_SEED`,
  never shown as if they were a real operational list).
- **Pre-computes congestion events** for all 7 cameras (added this phase —
  previously this required clicking "Process All Cameras" on the Congestion
  page before congestion alerts/bottlenecks would show; now it's baked into
  the reset itself, so page order during the demo can't leave something
  looking empty by accident).

You do **not** need to touch the database directly, run any other script,
or click anything else afterward. If you re-run the same command again
(rehearsing), you get the exact same 84 observations / 11 alerts / 2
congested cameras — verified twice in a row this session.

## Suggested walkthrough (~3 minutes)

1. **Overview** (`/dashboard`) — system status (all real: DB/model
   health from `GET /health`), KPI row, live camera map, recent alerts,
   traffic trend.
2. **Camera Network** (`/cameras`) — all 7 cameras ONLINE with real
   last-heartbeat times; note the "DEMO FEED" labels — this is the honest
   answer to "is this live CCTV?" (it isn't; say so if asked).
3. **Vehicle Intelligence** (`/vehicles`) — search `TN38AB1234` (the seeded
   blacklisted vehicle). Shows its full GIS trajectory, the blacklist
   match, and `risk_level: HIGH`. Try `TN77IM9999` afterward for the
   impossible-transition anomaly if there's time.
4. **Traffic Analytics** (`/congestion`) — congestion map, the 2
   already-active bottleneck cameras, hourly trend, top OD flow.
5. **Alerts** (`/alerts`) — all 11 alerts: blacklist matches, route
   anomalies, a repeated-camera sighting, and a congestion bottleneck alert,
   each with real evidence fields. Point out the DEMO WATCHLIST tag on the
   two seeded entries versus what an operator-added entry would look like.

## Known gap — action needed before presenting

**No sample video file is bundled in this repo.** The video-upload page
(`/video-demo`, Phase 2's real detection/OCR pipeline path — vehicle
detection → plate detection → OCR, not the seeded scenario data) needs an
actual video clip to upload live. If you plan to demo that page, have your
own short CCTV-style clip ready beforehand (`.mp4/.avi/.mov/.mkv/.webm`,
under 200MB, under 3 minutes) — nothing here can source or fabricate a
realistic traffic clip for you.

## If something looks wrong mid-demo

- Re-run `python -m demo.seed_demo_data --reset` — it's safe, fast (well
  under a second), and gets you back to the exact same known-good state.
- If the reset command reports it couldn't remove the database file, the
  backend was mid-request against it — wait a few seconds and retry, or
  briefly stop/restart the backend first.
