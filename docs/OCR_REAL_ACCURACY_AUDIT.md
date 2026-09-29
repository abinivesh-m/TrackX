# TrackX — Real, Manually-Verified OCR Accuracy Audit (2026-09-08)

**Status: authoritative for the CURRENT running configuration** (PaddleOCR engine; LPRNet
unavailable in this environment — `[ocr_reader] Using PaddleOCR engine (LPRNet unavailable)`).
This is a **different engine configuration** from `docs/OCR_EVALUATION.md` (which measured LPRNet
with PaddleOCR unavailable — the opposite of today). Per that document's own rule, these numbers
are **not merged** with the old ones. If your environment has LPRNet working, re-run that harness
instead; if it's running PaddleOCR like this one, this document is the current truth.

## Why this exists

The direct question was: **"does OCR actually hit 90%+ accuracy?"** There was no reproducible
ground-truth dataset available to answer that (the dataset referenced by `docs/OCR_EVALUATION.md`,
`data/ocr_eval/test_dataset_clean.json`, does not exist in this environment or on the connected
machine). Rather than repeat an unmeasured claim, a real ground-truth set was built by hand from
real pipeline output and the answer was measured directly.

## Method

1. Took every plate record with `plate_state` in `VERIFIED` / `TENTATIVE` / `LOW_CONFIDENCE` from
   3 real, current-codebase pipeline runs already in `outputs/results/observations.db`
   (`CAM_REGR_TEST1` = `anpr_test1.mp4`, `CAM_REGR_TEST2` = `anpr_test2.mp4`, `CAM_CONTINUITY_TEST`
   = `anpr_compare.mp4`) — 37 real saved plate crops, real OCR output, nothing synthetic.
2. For each crop, the ground truth was read **blind** — visually, at 5-6x upscale, without looking
   at the OCR's stored answer first — then compared against what the pipeline actually stored.
   Evidence images (what was actually looked at) are attached: `ocr_accuracy_evidence/grid_*.png`
   and `g_*.png`.
3. Where a crop only showed part of the plate (tight vehicle-box crop cutting off characters), it
   was graded against the **full plate**, established from clearer crops of the same physical
   vehicle elsewhere in the sample — a partial/truncated read counts as **wrong**, because the SIH
   target is exact **full**-plate recognition, not partial-substring recognition. 2 of the 37 were
   excluded entirely: one crop whose true full plate could not be established from any available
   crop, and one that was not a plate at all (see Finding 4).

## Result

**15 / 35 gradable samples exact-matched the true plate: 42.9%.**

This does **not** meet the SIH >90% target. Reporting this plainly, not softening it, per the
project's own standing rule against presenting unmeasured or overstated accuracy.

This number should **not** be read as "TrackX is 43% accurate" in general — it's a specific,
real measurement on 35 hand-verified real crops from 3 videos, with the honesty caveats above. A
larger, independently-labeled dataset (the missing `data/ocr_eval/` set) would give a tighter,
more defensible number. But it is a real number, not a guess, and it is well below the target.

## What's actually going wrong (4 real, distinct root causes found)

**1. D↔O confusion — the single most common error (5 of the 20 wrong samples).**
`UP14DX8554` was read as `UP14OX8554` on two independent tracks (confirmed at high zoom — the true
character is unambiguously a D, not an O). `DL2CBB4791` was read as `OL2C884791` — a D→O and two
B→8 substitutions on the same plate. **Fix applied**: added `D`↔`O` to
`recognition/plate_matcher.py`'s `CONFUSABLE_PAIRS` (previously only `D`↔`0`, the digit, was
present — not the same pair as `D`↔`O`, the letter, and the two aren't currently treated as
transitively equal by the voting code). Honesty caveat: this only helps a track whose own readings
actually *disagree* on that character across frames — several of the failing tracks here had high
temporal support (13+ readings) with no correction, suggesting the OCR engine got it wrong
*consistently*, not just occasionally, on those particular crops. This fix is real and justified,
but not proven to flip these specific tracks — that needs a per-frame reading disagreement log,
which isn't currently persisted.

**2. Truncated plate crops — several failures aren't OCR errors at all.**
`8554`, `X8554`, `0364`, `13248` and similar short outputs are cases where the saved crop itself
only shows the tail of the plate — the vehicle bounding box or plate detector cut off the rest.
OCR read exactly what was in the image; the image itself didn't contain the whole plate. This is a
plate-detection/crop-boundary issue, not a character-recognition issue, and needs a different fix
(loosening the plate-crop margin) than the OCR engine itself.

**3. A specific plate (`UP14FS3664`) is read wrong on 4 out of 5 sightings, each differently
wrong** (`OP14E5366` twice, `UP13S3664`, `UP14F5366`) despite being clearly legible to the eye in
every one of those crops. This is a genuine, unexplained OCR weak spot on this one plate/font in
this environment — worth a closer look (font style, print contrast) but not root-caused here.

**4. One track's voted plate text didn't match its own saved crop at all** — `CAM_REGR_TEST1`
track 161's saved crop clearly reads `FS3664` (part of `UP14FS3664`), but its final voted
`plate_text` is `UP16CO5633` — a completely different plate that happens to match a *different*
vehicle seen elsewhere in the sample (`CAM_CONTINUITY_TEST` track 157). This looks like a real,
if rare, cross-track OCR-reading contamination bug — worth investigating (most likely a
tracking-ID handoff during occlusion pulling in a wrong track's OCR history) but not fixed in this
pass; flagging it rather than hiding it.

**5. One false-positive plate detection** (excluded from the accuracy count, reported separately):
`CAM_REGR_TEST2` track 7 has its plate-detector box landing on a "Number Plate" watermark/caption
in the source footage, and OCR dutifully read the caption text, producing `NUMBERPLATE` at 0.772
confidence, `VERIFIED` state. This is a plate-*detection* failure, not a character-reading one —
worth a sanity filter (e.g. rejecting all-letters-no-digits results, or a caption/watermark
exclusion zone) but not fixed in this pass.

## What this means for the demo

- Do **not** state ">90% OCR accuracy" to judges as a measured fact — it isn't, in this
  configuration, on this evidence. The honest, defensible claims are: real multi-frame temporal
  fusion, real adaptive preprocessing that measurably helps on blur/rain (see
  `trackx_quality_preprocessing_demo.png`), real confidence-tiered plate states that correctly
  withhold low-confidence reads (0 false "unavailable → wrong text" claims were found — every wrong
  answer was a *confident* wrong answer, not a fabricated one), and a real, reproducible accuracy
  audit methodology — which is itself a defensible, judge-friendly artifact ("we measured it, here's
  the real number and the real root causes") rather than an inflated claim.
- The D→O fix is shipped. The other 3 root causes (truncated crops, the one hard plate, the
  cross-track contamination) are documented, not yet fixed — real next steps, not silently dropped.
- To responsibly report a number closer to what could be achieved, the two highest-leverage next
  steps are: (a) loosen the plate-crop margin to stop truncating plates at the box edge, since that
  alone explains a handful of the 20 failures, and (b) get LPRNet running in whatever environment
  the demo runs in and compare it directly against this PaddleOCR run on the exact same 37 crops.
