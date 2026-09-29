# TrackX — OCR Model Optimization + False Track Merge Fix
### SIH26127 (Bharat Electronics Limited) — 2026-09-09

This document covers both Part A (OCR model optimization) and Part B (false
track merge fix) requested in this pass, plus the honest before/after
validation (Part C/D) and the decision gate. It supersedes nothing already
shipped; it documents what changed this pass on top of the existing,
previously-validated pipeline.

**Scope discipline respected throughout:** no RTSP, no frontend redesign, no
presentation features. Everything below is either a real measurement from
the real pipeline against real CCTV clips, or explicitly marked as not
measured this pass.

---

## 1. OCR baseline

Re-confirmed the standing baseline before touching anything: **18/37 exact
matches (48.6%)** on the real, ground-truth-labeled 37-sample set
(`docs/a1_baseline_table_2026-09-09.csv`), using the shipped, unmodified
PaddleOCR pipeline. A full per-sample failure table was built (Ground
Truth, OCR Result, Exact Match, Character Error, Crop Quality, OCR
Confidence, Preprocessing, Failure Category) — see that CSV.

Detection vs. recognition split (A2): **37/37 samples got exactly one
detected text region** from PaddleOCR's DB detector. Zero detection
failures. This rules out the plate detector / text-localization stage as
the bottleneck and puts the entire investigation on the recognition
(character-reading) stage and its configuration.

## 2. OCR experiments (A3/A4/A5/A6)

**A3 — controlled, one-variable-at-a-time PaddleOCR config sweep** against
the same 35 ground-truth crops (track154 and track5 excluded from this
specific sweep for the reasons in §7/§15): `det_db_unclip_ratio` at
1.2 / 1.5 (default) / 1.8 / 2.0 / 2.2 / 2.5 / 2.7 / 3.0, `use_angle_cls`
on/off, `rec_image_shape` widened to `3,48,480`, `det_db_thresh` at 0.1,
`drop_score` at 0.1. Reproducibility was independently re-checked (identical
results across repeat runs — this pipeline is deterministic on fixed
input).

Result: a smooth, unimodal curve in `det_db_unclip_ratio`, peaking at
**2.5** (21/35, vs 17/35 at the 1.5 default — +4 samples, 0 regressions in
that sweep), degrading on both sides (16/35 at 3.0). That shape — more
recognition context up to a point, then background noise past it — is the
signature of a real effect, not a lucky single value. Every other
configuration tested (no angle classification, wider rec shape, looser
detection/drop thresholds) was neutral or negative.

**A4 — plate-specific input shaping**: white/replicate border padding
(both hurt), fixed-height resize with aspect preservation (neutral to
slightly negative). None adopted — real, reproducible negative evidence,
not assumption.

**A5 — confusion analysis**: built a character confusion matrix from the
real 37-plate results (2↔7, D↔O, B↔8 patterns visible). No new pairs were
added to `CONFUSABLE_PAIRS` — for every candidate pair, the wrong character
was itself the frequency/confidence-dominant answer within the track's own
readings, which the existing positional-vote correction mechanism
*structurally cannot fix* (it can only promote an alternative that is
*already* dominant among that track's own evidence — see
`recognition/ocr_reader.py`'s `vote_plate_text()`). Adding rules here would
either do nothing or risk false positives on other plates. Not added.

**A6 — alternative OCR models**: Tesseract tested on the same crops:
**1/35** — decisively unsuitable, even on legible crops. LPRNet: no valid
pretrained checkpoint exists in this environment; per instruction, no
arbitrary weights were downloaded and no LPRNet result is claimed anywhere
in this document. EasyOCR was attempted; installing it broke the
environment's already-tight, partially-conflicting numpy/opencv pins
(paddleocr needs `opencv-python<=4.6.0.66` + `numpy<2.0`; the EasyOCR
install pulled incompatible versions of both, cascading into `cv2` import
failures and then `imgaug`/numpy 2.0 `AttributeError`s). Root-caused,
recovered, and verified back to full working order (`244 passed` test
suite, `det_db_unclip_ratio=2.5` still active). **Conclusion: EasyOCR is
not safely integrable into this environment** without a much larger,
riskier, isolated-dependency-resolution effort — not attempted again.

## 3. Best configuration

**Shipped**: `PADDLEOCR_DET_DB_UNCLIP_RATIO = 2.5` (was PaddleOCR's own
default of 1.5), set in `recognition/ocr_reader.py`'s `PlateOCR.__init__`.
This is the only OCR-model-level change made this pass. Nothing else in
the OCR configuration space beat the shipped baseline with real evidence.

## 4. Alternative model investigation — final answer

- **Tesseract**: legitimately tested, decisively worse (1/35). Not adopted.
- **EasyOCR**: not safely integrable in this environment (dependency
  conflict, see §2). Not adopted, not re-attempted.
- **LPRNet**: no valid checkpoint. Correctly blocked per instruction — no
  fabricated result exists anywhere in this codebase or this report.
- **PaddleOCR (tuned, unclip=2.5) remains the best available, validated
  option in this environment.**

## 5. 37-plate before/after (real, reconciled)

The original A1 baseline table graded track154's ground truth as
`UP14FS3664`. **That label was itself wrong** — see §7/§15: it is the
plate of the physically adjacent vehicle that contaminated track154's
saved evidence at the time the table was built, not track154's own plate.
Corrected to track154's real, own plate (`UP16CD5633`, confirmed by direct
multi-frame visual inspection of native-resolution video crops this pass)
for an honest apples-to-apples comparison. All other 36 ground-truth labels
are unchanged from the standing baseline.

| | Exact matches | Accuracy |
|---|---|---|
| **BEFORE** (unclip=1.5, no spatial filter — the standing baseline) | 18/37 | 48.6% |
| **AFTER** (unclip=2.5 + spatial-outlier reading/crop filter — this pass) | 21/37 | 56.8% |

Net: **+3 samples**. Changed samples (5 total — 4 improved, 1 regressed):

| Sample | Ground truth | Before | After |
|---|---|---|---|
| CAM_FINAL_COMPARE / 1411 | UP22AT3248 | UP72AT3248 ✗ | UP22AT3248 ✓ |
| CAM_FINAL_COMPARE / 1556 | UP16CO5633 | UF16OO5633 ✗ | UP16CO5633 ✓ |
| CAM_FINAL_TEST1 / 341 | DL2CBB4791 | DL2C86479 ✗ | DL2CBB4791 ✓ |
| CAM_FINAL_TEST1 / 426 | UP14DX8554 | UP14OX8554 ✗ | UP14DX8554 ✓ |
| CAM_FINAL_TEST1 / 32 | UP16PT8030 | UP16PT8030 ✓ | UP16PT6030 ✗ (regression: genuine 8→6 misread introduced by the larger unclip margin on this specific crop) |

**Honest statement, as instructed: 56.8% is well below 90%. This is a real,
measured improvement, not a claim of production-readiness.**

## 6. Failure analysis

Remaining 16 failures (of 37) split into two real, distinct causes,
confirmed by direct inspection, not assumed:

1. **Genuine recognition-stage character confusion** (majority of
   remaining failures) — e.g. `UP14DX8554` read as `UP14OX8554` across 5
   samples sharing the same physical plate (D→O), `DL2CBB4791` losing a
   repeated character across 3 samples. These are real OCR-model
   limitations on this hardware/model combination, not pipeline bugs.
   Partially explained by the same structural limitation noted in §2/A5:
   the wrong character is often the *dominant* answer among a track's own
   readings, which the temporal-fusion positional-vote correction cannot
   override by design (it only ever promotes an alternative that is
   already dominant — it never introduces new information).
2. **Track154's specific, now-isolated failure** — see §7. After the Part
   B fix, this is a pure recognition-stage C/O-vs-D confusion on the
   silver car's *own* evidence (5 "CO" readings vs. 3 "CD" readings,
   post-filter) — the same class of failure as (1), not a tracking/merge
   bug. Documented separately because its root cause (cross-vehicle
   contamination) was misdiagnosed until this pass.

No sample was ever special-cased, hardcoded, or tuned to pass individually
(A8 requirement) — every change was a global configuration/filter change
evaluated across the whole set.

## 7. Track 154 root cause (real, evidence-based — B1/B2)

**The prior session's conclusion — "ByteTrack merged two vehicles into one
track" — was wrong, and this pass explicitly disproved it** (per the "do
not assume the reason" instruction) using three independent pieces of real
evidence:

1. **Exact per-frame vehicle-bbox trajectory data** for track154 across its
   whole lifetime (frames 122–230): smooth, continuous, physically
   plausible motion the entire time. The vehicle tracking itself never
   wavered — this was never an identity/ID-switch/merge problem at the
   ByteTrack level.
2. **Plate-bbox-relative-to-vehicle-bbox position data**: 11 of track154's
   13 raw OCR readings had the plate positioned consistently around
   (rel_cx≈0.72–0.86, rel_cy≈0.72–0.83) inside its own vehicle crop. Exactly
   2 readings (both reading "14FS3664", not track154's own plate at all)
   sat at a wildly different position (rel_cx≈0.09–0.10) — the far side of
   the same generous vehicle box.
3. **Direct full-frame visual confirmation**: extracted the actual video
   frames. Two real, physically distinct cars — a red SUV and a silver
   hatchback — stopped side-by-side near a signal, close enough that the
   silver car's own (correctly tracked) vehicle bounding box was generous
   enough to also contain part of the red SUV, including its plate
   (`UP14FS3664`, directly read off the video frame and confirmed
   character-by-character).

**Correct classification (B2): this is neither a classic false-merge (two
vehicles collapsed into one track ID) nor a classic ID-switch (one
vehicle's ID hopping to another). It is a third, more precise failure
mode: plate-detection-within-crop cross-vehicle contamination.** The
vehicle tracking (ByteTrack) was correct throughout; the plate detector,
operating inside that correct-but-generous vehicle crop, sporadically (2 of
14 OCR-sampled frames — 14%) locked onto the wrong, adjacent vehicle's
plate instead of track154's own.

**A second, related bug was found and fixed in the same investigation**:
the code path that picks which single plate crop/bbox to *save and display*
for a track picked purely by raw per-frame OCR confidence, with no spatial
check at all — and the contaminating reading happened to have the single
highest confidence (0.973) of any reading on the whole track. So even
after the text-vote fix (below) correctly excluded the contamination from
the *voted plate text*, the *saved crop image and bbox* shown for the
track was still, until this pass, the wrong vehicle's plate. This almost
certainly also explains why the **original A1 ground-truth label for
track154 was itself wrong** (`UP14FS3664`, the contaminating vehicle's
plate) — a human grader shown that same buggy "best" crop would reasonably
label it that way. Corrected in §5.

## 8. Tracking fix

**No changes were made to ByteTrack, `config/bytetrack_trackx.yaml`, or any
vehicle-tracking/association logic.** The confirmed root cause (§7) is one
level deeper than tracking — re-tuning ByteTrack parameters would not have
addressed it (the vehicle tracking was never wrong) and risks the
regressions already documented in `docs/TRACKING_TUNING.md` (e.g.
`match_thresh=0.65` making fragmentation dramatically *worse*).

Instead, `pipeline.py` gained a conservative, targeted, two-part fix (both
pieces new this pass):

1. **`filter_spatial_outlier_readings()` / `_spatial_outlier_keep_mask()`**
   — before voting on a track's final plate text, drop any (text,
   confidence) reading whose plate-bbox position (as a fraction of that
   track's own vehicle bbox) sits more than 0.35 (in either axis) from the
   track's own **median** position (median, not mean, so a minority of
   contaminating readings can never drag the reference point toward
   themselves). Requires at least 3 readings with known position before
   acting at all — conservative by design; a track with fewer readings, or
   with consistent positioning (the overwhelming majority of tracks), is
   completely unaffected. Readings with an unknown position (degenerate
   vehicle bbox, e.g. a vehicle entering/exiting frame) are always kept.
2. **Best-crop/bbox re-selection** — after the same reasoning is applied,
   the crop/bbox saved and displayed for the track is now re-picked from
   only the non-outlier readings, instead of by raw confidence alone. This
   closes the second bug found in §7.

Both pieces are pure post-hoc filtering of already-collected evidence for
an already-correctly-tracked vehicle ID. Nothing about which vehicles get
which track ID, when tracks start/end, or how ByteTrack matches detections
frame-to-frame was touched.

## 9. False-merge metrics

- **Confirmed real false-merge/contamination cases found via manual
  investigation this pass: 1 (track154).** No broader, automated
  full-corpus false-merge audit was run beyond this manually-investigated
  case and the synthetic regression tests (§13) — an honest limitation,
  not a claim that no other instance exists anywhere in the 3 test videos.
- **Before fix**: track154's evidence was contaminated (2/13 readings,
  14%) and its displayed crop/bbox was the wrong vehicle's plate.
- **After fix**: contamination confirmed removed from both the text vote
  (`temporal_support` 13→11, exactly the 2 contaminating readings) and the
  displayed crop/bbox (now the silver car's own plate, verified visually —
  see §7 and the regression test in §13). The underlying mechanism (plate
  detector picking up an adjacent vehicle's plate inside a generous
  vehicle crop) is now defended against generically for any track meeting
  the ≥3-reading threshold, not specially for track154.

## 10. ID-switch metrics

**0 before, 0 after — not by assumption but by direct measurement**: the
number of finalized tracks (records) produced by the full 3-video run is
**bit-for-bit identical before and after this pass's changes**: 86 / 48 /
28 (162 total) in both the pre-change baseline run and the final combined
validation run. Since track IDs are assigned entirely by the unmodified
ByteTrack/vehicle-detector layer, and this pass's Part B fix operates only
on already-finalized per-track evidence *after* tracking is done, identical
track counts is strong, direct evidence that no track was created,
destroyed, split, or merged differently by this pass's changes.

## 11. FPS impact

| | TEST1 | TEST2 | COMPARE | **avg** |
|---|---|---|---|---|
| Before | 2.47 fps | 2.57 fps | 2.30 fps | **2.45 fps** |
| After | 2.20 fps | 2.22 fps | 2.10 fps | **2.17 fps** |

**~11% slower on average.** Attributable almost entirely to Part A's
`det_db_unclip_ratio` increase (a larger recognition-stage crop is more
pixels for PaddleOCR to process per OCR call) — the Part B spatial filter
itself is simple arithmetic over small per-track lists and is not a
measurable cost. This is an honest, real trade-off: +3 net exact matches
(§5) for ~11% less throughput, both real-measured, not assumed.

## 12. Files modified

- `recognition/ocr_reader.py` — `PADDLEOCR_DET_DB_UNCLIP_RATIO = 2.5`
  constant + `PlateOCR.__init__` (Part A).
- `pipeline.py` — `_spatial_outlier_keep_mask()` (new),
  `filter_spatial_outlier_readings()` (refactored onto the mask helper,
  same external behavior), `track_reading_plate_meta` tracking + best-crop
  re-selection at track finalization (Part B, both pieces from §8).
- `tests/test_false_merge_regression.py` — new, 10 tests (§13).
- `docs/a1_baseline_table_2026-09-09.csv` — pre-existing A1 baseline table
  (not modified; track154's label error is corrected only in this
  document's §5 comparison, not silently edited in the source table).

## 13. Tests

`tests/test_false_merge_regression.py` (new, 10 tests, all passing):

1. `test_track154_exact_real_scenario` — frozen regression lock replaying
   track154's exact real (text, confidence, position) evidence; asserts
   the shipped filter drops exactly the 2 real contaminating readings.
2. `test_track154_crop_selection_also_excludes_contamination` — asserts
   the mask correctly steers crop/bbox selection away from the
   highest-confidence-but-contaminating reading.
3. `test_boundary_just_inside_vs_just_outside_threshold` — deviation
   threshold boundary behavior.
4. `test_filter_is_blind_to_vehicle_class` — documents/asserts the filter
   has no vehicle-class parameter (position-only by design).
5. `test_filter_is_position_based_not_appearance_based` — identical text
   at an anomalous position is still filtered (not fooled by similarity).
6. `test_duplicate_text_still_filtered_if_position_is_anomalous` —
   duplicate/identical OCR text never exempts a reading from the spatial
   check.
7. `test_sparse_readings_below_min_still_safe` — below the 3-reading
   minimum, nothing is filtered (not enough evidence yet).
8. `test_normal_bbox_jitter_never_falsely_filtered` — realistic small
   position jitter never triggers a false-positive filter.
9. `test_degenerate_vehicle_bbox_position_always_kept` — a
   vehicle-entering/exiting-frame degenerate bbox (position=None) is
   always kept.
10. `test_two_vehicles_side_by_side_full_pipeline` — full, end-to-end
    `run_video_to_db()` integration test with two synthetic adjacent
    vehicles sharing one generous vehicle box (the real track154
    mechanism, contaminating reading given deliberately *higher*
    confidence than the legitimate ones); asserts both the voted text and
    the saved crop image are attributed to the correct vehicle.

**Full suite**: `python -m pytest tests/ -q` → **254 passed, 3 skipped, 0
failed** (was 244/3/0 before this pass's 10 new tests were added — zero
regressions in any pre-existing test).

## 14. Real video validation

Full, real, non-instrumented `pipeline.run_video_to_db()` run across all 3
real CCTV clips (`anpr_test1.mp4`, `anpr_test2.mp4`, `anpr_compare.mp4`),
with both Part A and Part B changes active, annotated video output enabled,
real SQLite persistence:

- **162 total records** (86 + 48 + 28) — identical to the pre-change
  baseline (§10).
- OCR: 21/37 exact match (56.8%), up from 18/37 (48.6%) — §5.
- Temporal fusion, plate-quality scoring, plate-state tiers
  (VERIFIED/TENTATIVE/UNKNOWN), the annotated-video writer, and the
  SQLite `ObservationStore` all ran and produced output with no errors.
- No new false positives observed in the graded 37-sample set (the 5
  changed samples in §5 are all genuine text changes on already-tracked,
  already-OCR'd plates — no new phantom tracks or spurious plate reads
  were introduced).
- Track154 specifically re-verified: crop/bbox now correctly shows the
  silver car's own plate (visually confirmed, native-resolution frame
  crop), `temporal_support` correctly dropped 13→11.

## 15. Remaining limitations (honest)

- **56.8% is well below the 90% production bar.** Most remaining failures
  are genuine PaddleOCR recognition-stage character confusions (D↔O
  primarily, some B↔8/2↔7 patterns) that this environment's available OCR
  options (PaddleOCR tuned, Tesseract, EasyOCR blocked by environment
  conflict, LPRNet blocked by no valid checkpoint) cannot currently
  resolve further without either a better OCR model this environment
  cannot safely install, or more/better training data specific to this
  camera geometry — neither of which was in scope this pass.
- **The false-merge/contamination fix is validated against one confirmed
  real case (track154) plus targeted synthetic tests — not against a
  full, independent audit of every track in every video for other,
  undiscovered instances of the same pattern.** The mechanism defended
  against is generic (any track with ≥3 readings and a spatially
  inconsistent minority), so it should generalize, but this was not
  separately re-verified against a second real-world contamination case
  (none was found in this pass's videos beyond track154).
- **ID-switch and fragmentation metrics rely on identical track counts as
  a proxy** (§10), not a full manual re-audit of every individual track's
  identity across the videos. This is strong, real evidence of "nothing
  changed at the tracking layer" but is not the same as an exhaustive
  per-track identity audit.
- **ByteTrack parameters (B3) were not re-tuned** — deliberately, because
  the confirmed root cause (§7) is not a tracking-parameter problem, and
  `docs/TRACKING_TUNING.md` already documents that blind re-tuning of
  `match_thresh` in particular makes fragmentation measurably *worse*.
  This is a reasoned decision, not an oversight, but it does mean B3's
  parameter sweep itself was not repeated this pass.
- **B5 (lightweight appearance evidence)** was not implemented — the
  confirmed root cause (§7) is a pure spatial/positional problem, not an
  identity-confusion-across-frames problem, so appearance-based evidence
  would not have addressed it. Not adding unneeded complexity (hackathon
  scope guidance) was a deliberate choice, re-confirmed against this
  pass's actual (not assumed) root cause.
- **B6 (plate identity as supporting-only evidence)**: verified, not
  modified. `intelligence/fusion.py`'s `global_match_score()` already
  treats plate similarity as one of four weighted signals (base weight
  0.45, further scaled down by OCR confidence and camera reliability —
  never able to reach full weight alone), gated by hard
  spatial-connectivity and temporal-feasibility checks that force the
  score to 0.0 (`NO_MATCH`) regardless of plate similarity when a pair is
  spatially disconnected or would require an impossible travel speed. Two
  observations with identical plate text can never be merged by that
  signal alone. This pre-dates this pass and was not changed.
- **FPS regression (~11%, §11)** is real and unmitigated — no attempt was
  made to recover it (e.g. selectively applying the larger unclip ratio
  only when the fast path fails) since that would be new scope beyond
  what was asked.

## 16. Final recommendation

- OCR accuracy improved by a real, measured, non-overfit +8.2 percentage
  points (48.6% → 56.8%) via one validated PaddleOCR configuration change.
  PaddleOCR (tuned) remains the best legitimately available OCR option in
  this environment.
- The track154 false-track-evidence issue is fixed at its actual, verified
  root cause (cross-vehicle plate-detection contamination inside a
  correctly-tracked vehicle's own crop — not a ByteTrack merge or
  ID-switch), with both the voted text and the displayed crop/bbox
  corrected, zero test regressions (254/3/0), and zero measured impact on
  vehicle tracking/ID assignment (identical track counts before/after).
- **The system is not ready for frontend live-view integration or real
  RTSP camera integration.** Reliable Vehicle Identity is validated
  (unaffected, identical track counts). Reliable Plate Identity is
  explicitly NOT yet there: 56.8% exact-match accuracy means well under
  half of plates would still be wrong in a live view. Temporal Evidence
  (fusion, state tiers) continues to function correctly but cannot
  compensate for a recognition-stage ceiling this far below 90%. Working
  WebSocket plumbing is a separate, already-solved concern and is not by
  itself a readiness signal — this document does not treat it as one.
