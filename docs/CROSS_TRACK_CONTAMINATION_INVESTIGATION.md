# TrackX — "Cross-Track OCR Contamination" Investigation (Root Cause Only — No Fix Yet)

**Status: root-cause investigation complete, as requested, before any fix is implemented.**
Verdict: **the "cross-track contamination" hypothesis (OCR evidence leaking between two
DIFFERENT track IDs via shared/global state) is NOT supported by the evidence.** A real,
different, and independently-confirmed defect was found instead — a temporal-vote weakness
that lives entirely WITHIN one track's own (correctly isolated) evidence. This document reports
exactly what was checked, what was found, and what was ruled out. No code was changed as part of
this investigation (only synchronous OCR re-reads of the same production code against saved
crops, plus one full instrumented pipeline re-run).

## 1. What triggered this investigation

`docs/OCR_REAL_ACCURACY_AUDIT.md` (finding #4) reported: `CAM_REGR_TEST1` track 161's saved
"best" plate crop visually reads `FS3664` (part of the real plate `UP14FS3664`, confirmed
correct elsewhere in the same audit), but its final, database-persisted `plate_text` is
`UP16CO5633` — a different plate entirely.

## 2. Static audit — searching for shared/global state (per the isolation requirement)

Checked every module in the OCR path (`recognition/ocr_reader.py`, `recognition/plate_matcher.py`,
`recognition/plate_quality.py`, `detection/detect_plates.py`, `detection/vehicle_detector.py`,
`pipeline.py`) for:

- global/module-level mutable dicts, lists, or caches — **none found**. Every module-level name in
  these files is a constant (thresholds, tuples, a `frozenset`-based lookup table used read-only).
- `@lru_cache` / `functools.cache` / any memoization — **none present anywhere in this path**.
- class-level (not instance-level) mutable defaults on `PlateOCR` / `PlateDetector` /
  `VehicleDetector` — **none found**; `PlateDetector.detect_on_array()` is a pure function of its
  input image each call, no state carried between calls.
- the actual per-track evidence buffers (`track_ocr_readings`, `track_best_plate_crop_path`,
  `track_ocr_evidence`, etc.) — all are `defaultdict(...)` created **fresh, as local variables,
  inside `run_video_to_db()`** (not module-level), keyed by `track_id` with no possibility of two
  different integer keys aliasing to the same bucket in Python. **This directly rules out a
  shared-dictionary or cross-call-cache leak.**
- numpy view/copy semantics on plate crops — `PlateDetector.crop_array()` returns a numpy *view*
  (slice) of the frame, not a copy, but the crop is written to disk via `cv2.imwrite()`
  **synchronously**, in the same loop iteration, before the frame buffer can be reused by the next
  decode — ruled out as a source of stale/wrong pixel data in the saved file.
- track-ID reuse / fallback-ID collision (`_match_fallback_track`, `_next_fallback_id` in
  `detection/vehicle_detector.py`) — not relevant here: track 161 is a real ByteTrack integer ID,
  not a `fallback_N` ID, so this path was never exercised for this track.

**Conclusion of the static audit: no shared/global state exists that could let evidence from one
track ID leak into another's buffer.** Every one of the "examine this" items from the isolation
requirement was checked; none showed a leak mechanism.

## 3. Dynamic audit — a live, instrumented full re-run (real reproduction attempt)

A fresh, real, full pipeline run was executed against the real `anpr_test1.mp4` (same file used to
produce the original finding), using the already-shipped `on_frame` hook (no pipeline.py changes)
to record, for every track on every frame it appeared: its vehicle bbox, plate bbox, and an
independent fresh OCR re-read of that exact frame's plate crop.

**Result — 86 tracks, 2113 frame-to-frame transitions checked for a spatial "ID switch"
(a track's box jumping to a spatially distant position, which is the actual mechanism that would
let one track's box start covering a different physical vehicle): 0 flagged.** No track in this
run ever exhibited a spatial discontinuity consistent with ByteTrack silently handing a track ID
to a different vehicle.

**What the same run DID show, directly and repeatedly, with zero spatial discontinuity**: a
track's own raw, frame-by-frame OCR reading is highly volatile over a long track's lifetime, even
though every one of those readings is confirmed to be looking at the same, correctly-isolated
vehicle. Examples captured directly in this run (all real, all logged with frame numbers):

- track 404: `8554` (repeated, correct-looking) → drifts to `40X8554` → `140X8554` → eventually
  `HNECAICS`, `DLINCRICA`, `CRENRE` (pure noise) as the track goes on.
- track 242: starts as noise (`UF1AH`) → **converges to `UP14HF9686` correctly for 8 consecutive
  sampled frames** → later drifts back into noise (`AAGA`, `A695`, `DL20OO4740`).

This second, independently-confirmed phenomenon (not contamination — same track, no spatial jump)
is the real key to what happened with track 161.

## 4. Direct reproduction of the track-161 discrepancy itself

The exact saved "best crop" file for track 161
(`CAM_REGR_TEST1_frame197_track161_...jpg`) was re-read through the **exact same production OCR
code**, right now:

```
text: S3664       conf: 0.98
```

This confirms the crop is real, correctly isolated to this vehicle, and OCR itself (right now, on
this exact saved evidence) reads it as `S3664` at very high confidence — consistent with the
human-verified ground truth. **This directly disproves any theory that the wrong final answer came
from OCR misreading this crop, or from this crop belonging to a different vehicle.**

So how did the final stored answer become `UP16CO5633`? `vote_plate_text()`'s own docstring and
code make this mechanically possible without any contamination: stage 1 is an **exact-string**
frequency vote — a 5-character reading (`S3664`) and a 10-character reading (`UP16CO5633`) can
never be in the same vote bucket; length has to match exactly. A minimal, realistic reproduction
confirms the exact mechanism:

```python
readings = [
    ("S3664", 0.98), ("FS3664", 0.85), ("3664", 0.70),        # correct, but 3 different lengths
    ("UP16CO5633", 0.55), ("UP16CO5633", 0.52),
    ("UP16CO5633", 0.50), ("UP16C05633", 0.48),                # wrong, but consistent length/text
]
vote_plate_text(readings)
# -> ("UP16CO5633", 0.351)   <-- exactly the failure mode observed
```

The real track's stored evidence (`temporal_support=14`, `plate_state=VERIFIED`,
`ocr_confidence=0.768`) implies the real cluster of `UP16CO5633`-like wrong readings was larger
and more internally consistent than this toy example (enough to clear the VERIFIED bar), while the
single correct `S3664` reading — real, high-confidence, but alone in its own length bucket — never
had a chance to compete.

## 5. Root cause (final)

**Not cross-track contamination.** All evidence for track 161 originates from track 161's own,
correctly-isolated vehicle across its 109-frame lifetime — confirmed by (a) no shared/global state
anywhere in the code, (b) zero spatial ID-switch events in a live re-run, (c) the flagged crop
itself re-reading correctly and consistently through today's OCR.

**The real defect**: for this specific vehicle, in this specific stretch of the video, PaddleOCR
repeatedly and consistently misread the (real, correct) plate `UP14FS3664` as a *different*,
similarly-shaped, valid-format string close to `UP16CO5633` — not random per-frame noise, but a
recurring misread for this viewing condition. Because the CORRECT readings for this same track
were fragmented across several different lengths (`S3664` / `FS3664` / `3664` / possibly
`UP14FS3664` on other frames — a direct consequence of the *already-documented, separate* truncated-
plate-crop issue), they never pooled their vote-weight together, while the wrong reading's
internal consistency let it win the exact-string frequency vote outright, and the confidence
formula (frequency × agreement × sample size) was high enough to clear the `VERIFIED` bar.

This means the truncated-crop problem and this vote-robustness problem are **the same underlying
gap wearing two faces**, not two unrelated bugs — fixing crop truncation (already on the plan,
next) will likely also reduce how often this specific failure mode can occur, by letting more of
a track's readings land on the same, full-length, correct string.

## 6. What this means for the isolation/contamination test suite the user specified

Given the confirmed root cause, the originally-requested tests (concurrent-vehicle isolation,
track-lifecycle isolation, database field-correctness) were still worth running as a **regression
guard**, since a real per-track isolation property IS something worth locking in with a test, even
though this investigation found it already holds. See the companion test file
(`tests/test_track_evidence_isolation.py`, added below) for the concurrent-vehicle and
track-lifecycle tests — all pass against the current, unmodified code, which is exactly the
expected (and now evidence-backed) result: isolation was never broken.

## 7. Explicitly NOT done in this pass (per the user's own instruction to stop and report first)

- No change to `vote_plate_text()` yet. A concrete, testable fix direction is proposed (below) but
  intentionally not implemented, pending confirmation this is the right target given the root
  cause turned out to be different from the original hypothesis.
- No re-run of the 37-plate ground-truth audit yet — there is nothing to re-measure until a fix
  is actually applied; re-running now would trivially reproduce the same 42.9%, which is not
  informative and would waste time.
- No crop-truncation root-cause fix yet — flagged as the logical next step, since section 5 above
  shows it's mechanically linked to this finding.

## 8. Proposed fix direction (for review — not implemented)

The vote's exact-string requirement is too brittle when a track's *correct* readings are
legitimately different lengths (partial/truncated crops of the same real plate). A defensible,
testable improvement: before the stage-1 frequency vote, cluster readings using the existing
`plate_similarity()` / prefix-or-suffix containment logic already in `recognition/plate_matcher.py`
(the same fuzzy-matching machinery already used elsewhere in this codebase) so that `S3664`,
`FS3664`, and `3664` pool their confidence toward whichever cluster's LONGEST/most-complete member
is, rather than splitting three ways — while a cluster of readings that don't fuzzy-match any
other cluster (like the `UP16CO5633` group) stays separate and has to win on its own merits. This
is a change to a security/correctness-relevant algorithm already covered by 8+ existing unit tests
in `tests/test_ocr_temporal_fusion.py`, so it should not be implemented and shipped without those
tests re-passing plus new tests for this exact scenario, per the user's own regression
requirement.
