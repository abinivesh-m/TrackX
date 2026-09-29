# TrackX — ByteTrack Parameter Tuning (Priority 2: Occlusion-Aware Tracking)

**Status of this document:** Real measurements from real runs against `anpr_test1.mp4` (the clip
with the documented Track #448/#698 occlusion-fragmentation case from an earlier validation
pass), not guessed values. Referenced from `detection/vehicle_detector.py` and
`config/bytetrack_trackx.yaml`.

## Method

Detection+tracking only (no plate detection/OCR, to keep iteration fast), same video, same YOLO
weights, only the tracker YAML changed between runs. Two metrics: total unique track IDs
produced (fewer, all else equal, means less ID fragmentation) and a frame-to-frame "implausible
jump" check (a track whose bbox center moves more than 3x its own box size within a 5-frame gap
is flagged as a suspicious/likely-wrong association, not a real occlusion recovery) — used as a
cheap proxy for "did this config just merge two different vehicles" rather than genuinely
recovering one.

## Results

| Config | Unique tracks | Short tracks (≤3 frames, likely fragments) | Avg track duration (frames) | Suspicious jumps |
|---|---|---|---|---|
| Default (`track_buffer=30`, `match_thresh=0.8`) | 113 | 28 | 24.8 | 0 |
| `track_buffer=60`, `match_thresh=0.8` (**shipped**, `config/bytetrack_trackx.yaml`) | 110 | 26 | 26.6 | 0 |
| `track_buffer=60`, `match_thresh=0.65` | 192 | 115 | 13.0 | 0 |
| `track_buffer=60`, `match_thresh=0.9` | 93 | 20 | 32.7 | 0 |

## Interpretation

- **Doubling `track_buffer` (30→60) gives a real but modest improvement**: 3 fewer fragmented
  tracks, no suspicious jumps. This only affects how long a track that stopped being detected
  stays eligible for re-matching before being dropped — a low-risk lever since it doesn't change
  how strict any single match decision is.
- **Lowering `match_thresh` to 0.65 made fragmentation dramatically WORSE** (113→192 tracks) —
  counter to the naive expectation that "looser matching = fewer fragments." This is empirical,
  not assumed: a lower `match_thresh` in ultralytics' ByteTrack implementation makes association
  *stricter*, not looser, so this direction was wrong and is not used.
- **Raising `match_thresh` to 0.9 gives the biggest fragmentation reduction measured** (113→93,
  ~18%) with zero suspicious jumps detected by the coarse check above. **This was NOT adopted**
  for the shipped config, because loosening `match_thresh` changes matching behavior for *every*
  association decision across the whole video, not just genuine occlusion recovery — the
  jump-distance check here cannot detect the specific risky case (two distinct vehicles that are
  spatially close, e.g. queued at a signal, getting merged because their boxes never travel far
  apart). That failure mode wouldn't produce a large spatial jump, so this check would not catch
  it. Root-causing this properly needs either a stronger identity check (e.g. requiring plate
  text or appearance-embedding agreement before accepting a borderline match) or manual visual
  review of the specific tracks whose count changed between the two configs — neither was done
  in this pass, so `match_thresh=0.9` remains a documented, measured option, not a shipped one.

## What actually shipped

`config/bytetrack_trackx.yaml`: `track_buffer: 60`, everything else at ultralytics' defaults.
Used automatically by `detection.vehicle_detector.VehicleDetector` unless a different
`tracker_config` is passed explicitly.

## Known remaining gap

The original Track #448/#698 case (documented in an earlier validation pass on this exact
video) was previously root-caused to a **same-frame** partial-occlusion IoU failure
(measured IoU ≈ 0.070 between two YOLO boxes of the same vehicle in the same frame), not a
multi-frame gap — `track_buffer` only helps with the latter (a track that goes briefly
undetected then reappears), not the former (a track that's detected every frame but with a
badly-shaped box during occlusion). This is why the buffer increase alone gives a real but
modest improvement rather than a fix for that specific case. The plate-assisted continuity
heuristic (`pipeline.py::link_plate_continuity()`) is the mechanism intended to catch that
remaining case — see its docstring for how it works and its limits.
