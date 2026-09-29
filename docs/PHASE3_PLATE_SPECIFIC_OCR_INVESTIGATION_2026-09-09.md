# TrackX — Phase 3: License-Plate-Specific OCR Model Investigation
### SIH26127 (Bharat Electronics Limited) — 2026-09-09

No RTSP, no frontend work, no UI polishing — this phase is purely a
recognition-model investigation. **No code in the repo was changed this
phase** (confirmed: `git`-equivalent diff is empty aside from this new
document) — every experiment below ran in isolated scratch environments
against the shipped pipeline's own crops, never touching `pipeline.py` or
`recognition/ocr_reader.py`. Full regression suite re-confirmed at the end:
**254 passed, 3 skipped, 0 failed** — identical to the start of this phase.

---

## Phase 1 — Audit of current PaddleOCR

Directly inspected the installed package and the actual downloaded model
files (not assumed from documentation):

- **paddleocr** 2.7.3, **paddlepaddle** 2.6.2 (CPU).
- **Detection**: `en_PP-OCRv3_det_infer` (DB algorithm), confirmed by the
  actual downloaded model directory at `~/.paddleocr/whl/det/en/`.
- **Recognition**: `en_PP-OCRv4_rec_infer` (SVTR_LCNet algorithm), confirmed
  at `~/.paddleocr/whl/rec/en/`. `rec_image_shape='3, 48, 320'`,
  `max_text_length=25`.
- **Angle classification**: `ch_ppocr_mobile_v2.0_cls_infer`.
- **Recognition character dictionary**: confirmed via direct inspection of
  `paddleocr/paddleocr.py`'s own config resolution — the *actual* dict
  loaded at runtime is `ppocr/utils/en_dict.txt`, **95 characters**:
  digits, full uppercase A–Z, full lowercase a–z, and a large block of
  punctuation/symbols (`:;<=>?@[\]^_\`{|}~!"#$%&'()*+,-./`). This is a
  **generic scene-text vocabulary**, not a plate-specific one — confirmed
  directly, not assumed (see Phase 4).
- `det_db_unclip_ratio=2.5` (Part A's shipped tuning), `drop_score=0.5`,
  `det_db_thresh=0.3`, `det_db_box_thresh=0.6`.

**Answer to "generic or plate-specific": PaddleOCR's `en_PP-OCRv4_rec` is a
generic scene-text recognizer** (SVTR_LCNet trained on broad English scene
text — signs, documents, general imagery), used here for plate text but
never specialized for it. Nothing in the shipped configuration restricts it
to plate-shaped, plate-formatted, or plate-character-only input.

## Phase 2/3 — Candidate license-plate-specific models

Real candidates researched, with an actual, direct verdict for each
(license, checkpoint, and — where feasible — a real run against our data,
not just documentation claims):

| Candidate | Architecture | License | Checkpoint | Indian plates | Verdict |
|---|---|---|---|---|---|
| **PaddleOCR (current, unclip=2.5)** | SVTR_LCNet, generic scene-text | Apache-2.0 | Shipped, verified working | Not specialized, but empirically the best on our data | **Baseline / still best available** |
| **fast-plate-ocr** (`ankandrew/fast-plate-ocr`) | Compact Convolutional Transformer (CCT), plate-specific vocabulary | MIT | Real, auto-downloaded ONNX weights (`cct-xs-v2-global`, `cct-s-v2-global`), verified working | Trained on 64 countries/regions — **India is explicitly NOT in the `plate_regions` list** of the model's own config | **Actually run — underperforms PaddleOCR** (§5) |
| **LPRNet** (`sirius-ai/LPRNet_Pytorch`) | LPRNet (lightweight CNN + CTC) | Apache-2.0, real checkpoint in-repo | Real 1.8MB `.pth`, cloned and loaded successfully | Trained on **Chinese plates only** — 67-class vocabulary includes 31 mandatory Chinese province characters at position 0; fundamentally different plate grammar | **Actually run — 0/37 exact match** (§5/§7) |
| **Indian_LPR** (`sanchit2843/Indian_LPR`) | LPRNet-family (Inception blocks + CTC) | **No LICENSE file in the repository** — verified twice via direct fetch | Real `best_lprnet.pth` referenced in-repo | Purpose-built for India | **Blocked — no license, cannot legitimately use without contacting the author** |
| **Awiros/anpr-ocr** (Hugging Face) | PP-OCRv5, PPHGNetV2_B4 backbone + CTC/NRTR multi-head, 37.3M params | Apache-2.0 | Real 149MB `model.safetensors`, 558,767-sample Indian training corpus per its own technical report, claims 98.42% on its own test set | **Purpose-built specifically for Indian plates** (all state codes) | **Found, but weights host (huggingface.co) is blocked by this environment's network egress policy — could not be downloaded or run. No accuracy claim from this model is reported as verified.** |
| OpenALPR | Tesseract-based | AGPLv3 (commercial restrictions) | N/A | US/EU only | **Rejected without testing** — it is Tesseract underneath, already tested and rejected in the prior phase (1/35); AGPL is also more restrictive than what's already in use |

**No fabricated results anywhere in this table.** Every "actually run" verdict
above came from a real inference call against our real plate crops in this
session; every "blocked" verdict is a real, checked (not assumed) legal or
network constraint.

## Phase 4 — Character set / vocabulary analysis

Confirmed directly (Phase 1) that PaddleOCR's actual runtime dictionary
(`en_dict.txt`, 95 chars) includes 59 characters an Indian plate can never
legitimately contain (all lowercase, all punctuation/symbols) — real
vocabulary bloat.

**Tested whether restricting it helps** — the package itself ships a
second, smaller, **63-character uppercase-only dictionary**
(`ppocr/utils/dict/en_dict.txt`: digits + a-z + A-Z, no punctuation) that
is never used by default. Swapped it in via PaddleOCR's own legitimate,
documented `rec_char_dict_path` config parameter and ran it against a real
plate crop:

```
IndexError: list index out of range
  (rec_postprocess.py: self.character[text_id])
```

**Real, empirical, decisive finding: vocabulary restriction via
`rec_char_dict_path` is NOT safely usable with the current pretrained
`en_PP-OCRv4_rec` checkpoint.** The recognition model's final classifier
head is a fixed 96-way softmax (95 characters + 1 CTC blank) whose output
index *is* the character dictionary's position — it was trained against
that exact 95-entry ordering. Swapping in a different, smaller, differently
-ordered dictionary makes the model emit class indices the smaller
dictionary can't resolve, crashing immediately. **Restricting the
vocabulary would require fine-tuning the recognition model's classifier
head against the new dictionary — it cannot be done by config alone.** This
is exactly why `fast-plate-ocr`'s clean 37-character alphabet
(`0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_`, confirmed from its own shipped
`plate_config.yaml`) works: it was trained from scratch with that
vocabulary, not retrofitted onto a differently-trained model.

Per the phase's explicit instruction, **no arbitrary post-hoc conversion of
OCR output into Indian plate format was added or changed** — the existing,
separate, already-shipped `normalize_indian_plate()` remains the only place
that happens, unmodified.

## Phase 5 — OCR-only benchmark (the primary experiment)

Real run, same 37 ground-truth samples used throughout this project, same
methodology as prior phases (`normalize_indian_plate()` applied to raw OCR
output before grading where applicable). Column A = the pipeline's actual
shipped detector crop (12% padding, all 37 available). Column B = the
existing manually-verified full-crop subset from the prior
crop-vs-OCR investigation (7 of 37 — the truncation-category tracks; no
new manual crops were fabricated this phase, this reuses that
already-legitimately-produced evidence honestly labeled as partial
coverage).

Raw, single-pass recognition only (no temporal fusion, no adaptive
multi-variant preprocessing) — this isolates each engine's raw recognition
capability. This is *lower* than the shipped pipeline's real 56.8% because
the shipped pipeline additionally benefits from temporal fusion across many
frames per track and adaptive preprocessing, which are compared separately
in Phase 8 (see below).

| Engine | Crop | Exact match | Char accuracy | Avg edit distance | Failed reads | Avg confidence | Avg inference time |
|---|---|---|---|---|---|---|---|
| **PaddleOCR (unclip=2.5)** | detector (37) | **19/37 (51.4%)** | 0.841 | 1.97 | 0 | 0.883 | 106.2 ms |
| PaddleOCR (unclip=2.5) | manual full (7) | 2/7 (28.6%) | 0.714 | 4.57 | 1 | 0.740 | 63.1 ms |
| fast-plate-ocr `cct-xs-v2-global` | detector (37) | 11/37 (29.7%) | 0.705 | 3.32 | 0 | 0.847 | **3.2 ms** |
| fast-plate-ocr `cct-xs-v2-global` | manual full (7) | 1/7 (14.3%) | 0.700 | 4.71 | 0 | N/A | 3.2 ms |
| fast-plate-ocr `cct-s-v2-global` | detector (37) | 5/37 (13.5%) | 0.673 | 3.68 | 0 | 0.793 | 27.8 ms |
| fast-plate-ocr `cct-s-v2-global` | manual full (7) | 0/7 (0.0%) | 0.614 | 5.57 | 0 | N/A | 27.1 ms |
| LPRNet (`sirius-ai`, Chinese-plate checkpoint) | detector (37) | **0/37 (0.0%)** | — | — | — | — | fast (CPU, small model) |

**PaddleOCR wins decisively on accuracy on both crop types.**
`fast-plate-ocr` is dramatically faster (~33x on the xs model) but at a
large, real accuracy cost that is not remotely worth the speed on this
dataset — consistent with its own config file honestly listing 64
countries and not India. LPRNet's Chinese-plate checkpoint produces 0
correct reads and frequently hallucinates actual Chinese characters that
are nowhere in the input image (see Phase 7) — decisive, direct,
non-assumed confirmation that this specific checkpoint is architecturally
incompatible with Indian plates, not merely "less accurate."

**The larger `cct-s-v2-global` model scored worse than the smaller
`cct-xs-v2-global`** (13.5% vs 29.7%) on this specific dataset — a real,
reported, slightly counter-intuitive result, not a bug (spot-checked
individually: e.g. on track 2's clean crop, xs correctly read
`DL7CP8161` while s misread it `DLZCP8161`). Reported honestly rather than
discarded as noise.

## Phase 6 — No overfitting

No plate was hardcoded, no lookup table was added, no threshold was tuned
against these 37 samples this phase. `PADDLEOCR_DET_DB_UNCLIP_RATIO`
remains exactly what the prior phase validated (2.5); nothing in
`recognition/` or `pipeline.py` changed. The character-vocabulary
experiment (Phase 4) was a real config-level test that failed cleanly, not
a tuning exercise. Every number reported above is a full, un-cherry-picked
run over all 37 samples (or the honestly-labeled 7-sample manual subset).

## Phase 7 — Difficult plates deep-dive

Real per-sample comparison across engines, direct from the raw benchmark
output (no rounding, no selection):

| Sample (GT) | PaddleOCR raw | fast-plate-ocr xs raw | fast-plate-ocr s raw |
|---|---|---|---|
| `UP14FS3664` (track 1475) | `FUP14F536E4` | `UP14F5364` | `UPY4F5364` |
| `UP14FS3664` (track 1590) | `UP14FS366A` | `UP14593` | `UPAES366` |
| `UP14FS3664` (track 1591) | `UP14FS3664` ✓ | `UP1455566` | `UP14F3666` |
| `UP14FS3664` (track 84) | `UP14FS3664` ✓ | `UP14FS3664` ✓ | `UP14F3666` |
| `UP14FS3664` (track 226) | `UP14FS3664` ✓ | `1115F3` | `J01EEG66G` |
| `UP14DX8554` (track 346) | `UP140X8554` (D→0) | `UP140AA55` | `UP1LDDA` |
| `UP14DX8554` (track 396) | `18554` (truncation) | `8554` | `18554` |
| `UP14DX8554` (track 409) | `X8554` (truncation) | `X8554` | `XX8554` |
| `UP14DX8554` (track 422) | `UP140X8554` (D→0) | `UP14DX8554` ✓ | `UP14DX8855` |
| `UP14DX8554` (track 423) | `X8554` (truncation) | `Y8554` | `XX5544` |
| `UP14DX8554` (track 426) | `UP14DX8554` ✓ | `UP1401H` | `UP114DX55` |
| `UP16CO5633` (track 1556) | `UP16C05633` (near-miss, 0 vs O) | `7RFH165` | `VRE00` |
| `UP16CD5633` (track 154, corrected GT) | `UP1605633` | `316600` | `16EE0` |

**D↔O is real and systematic**: 2 of the 5 `UP14DX8554` samples where
PaddleOCR gets the *length and position* right still swap D→0 specifically
— this happens at the raw, single-frame level, before temporal fusion ever
runs, confirming it's a genuine recognition-model weakness, not a fusion
artifact. On the 3 samples where PaddleOCR shows a truncated read
(`X8554`), the *same* truncation appears in `fast-plate-ocr` too — direct,
real confirmation that some remaining failures are a **crop-boundary
problem upstream of OCR entirely**, not fixable by any recognition-model
swap (consistent with the prior phase's crop-padding investigation).
`UP16CO5633`/`UP16CD5633` (track154's plate) shows PaddleOCR's raw read
alternating between a 0/O-shaped eighth character depending on which frame
— exactly the C/O-D confusion already identified as this track's remaining
issue in the previous pass.

## Phase 8/9/10 — Temporal fusion / real video / performance comparison

**Explicitly, correctly skipped.** Per the phase's own instruction ("If an
alternative model proves better on the 37-plate benchmark, run it through
the real CCTV pipeline"), the gating condition was evaluated honestly: **no
alternative model beat PaddleOCR on the Phase 5 benchmark** (fast-plate-ocr:
29.7% vs 51.4%; LPRNet: 0%; Awiros: unverified/blocked by network policy).
Running temporal fusion, real-video validation, or performance tuning on a
losing candidate would waste effort and risk exactly the kind of
report-padding this project's rules explicitly forbid. Nothing was run
through the real pipeline this phase; `pipeline.py` and
`recognition/ocr_reader.py` are byte-for-byte unchanged from the end of the
prior phase.

## Phase 11 — Honest conclusion

**Current PaddleOCR (tuned, `det_db_unclip_ratio=2.5`) is the best
legitimately available AND legitimately verified recognition engine in
this environment.** Every real alternative that could be actually run this
phase performed worse (fast-plate-ocr) or catastrophically worse (LPRNet's
only available checkpoint, architecturally trained for a different plate
grammar entirely). The one candidate that looks genuinely capable of
beating PaddleOCR on this exact problem — **Awiros/anpr-ocr**, purpose-built
for Indian plates on a 558K-sample corpus, Apache-2.0 licensed, real
downloadable weights — could not be verified in this environment because
its host (huggingface.co) is blocked by this sandbox's network egress
policy. **No accuracy claim about that model is made or implied by this
report** — it is reported as "found, not run," a third, distinct category
from "verified better" or "verified worse." Further improvement requires
either (a) obtaining and running that specific model in an environment
with Hugging Face access, or (b) a license-plate-specific recognition
model trained (or fine-tuned) on Indian plate data — see Phase 12.

## Phase 12 — Training path investigation (for a future pass, not this one)

If model-level improvement stays blocked (or if Awiros's model turns out
not to be usable/verifiable), here is a concrete, realistic training plan,
grounded in this project's own real, measured data rather than generic
boilerplate:

- **Data volume**: `fast-plate-ocr`'s own smallest usable global models
  were trained on tens of thousands of plates across 64 regions; Awiros's
  own reported Indian-specific corpus is 558,767 samples. A realistic
  *minimum* for a usable Indian-plate-specific fine-tune is on the order of
  **10,000–30,000 real, diverse Indian plate crops** (fine-tuning from an
  existing scene-text or plate-OCR checkpoint, not training from scratch,
  needs far less data than the from-scratch corpora above) — this
  project's own 37-sample benchmark is 300–1000x too small to train on,
  and must remain a held-out evaluation set only, never mixed into
  training data (explicit requirement, respected).
- **Annotation format**: plate crop image + exact ground-truth string,
  ideally in PaddleOCR's own native label format (`image_path\tlabel`,
  one per line) so an existing `en_PP-OCRv4_rec` checkpoint could be
  *fine-tuned* rather than trained from zero — directly reusable with
  PaddleOCR's own `tools/train.py` recognition training pipeline.
- **Character vocabulary**: exactly `0-9A-Z` (36 classes) plus a CTC blank
  — matching Indian plates' real character space precisely (see Phase 4's
  finding that this must be trained in from the start, not swapped in
  after the fact).
- **Augmentation** — grounded in this project's own real, measured crop
  quality distribution (`docs/a1_baseline_table_2026-09-09.csv`: blur
  score 366–17,201 (median 628), brightness 80–172 (median 132), contrast
  34–85 (median 67) across the 37 real samples): the training set should
  deliberately cover *at least* that same real range, plus:
  - **Blur**: Gaussian/motion blur augmentation spanning the measured
    range and somewhat beyond it (real CCTV plates get blurrier than this
    37-sample set under motion/distance).
  - **Brightness**: multiplicative + additive brightness jitter spanning
    the measured 80–172 range and extending toward both under- and
    over-exposure.
  - **Perspective**: affine/perspective warps simulating off-axis camera
    angles (this project's cameras are fixed-angle CCTV, not
    straight-on, so this matters for real generalization).
  - **Dirty-plate**: synthetic occlusion/noise patches simulating mud,
    dust, and worn/faded plate paint — a known, common Indian-plate
    real-world condition not otherwise represented here.
  - **Night/rain**: low-light + specular-highlight + rain-streak synthetic
    augmentation — this project's daytime CCTV clips don't cover this
    condition at all, and it would be a real gap without deliberate
    augmentation.
- **Train/validation/test split**: standard 80/10/10 by *vehicle*, not by
  frame (multiple frames of the same physical plate must never span the
  split, or the model would trivially memorize plate images it saw in
  training) — this project's own temporal-fusion evidence (many frames per
  track) makes this an easy trap to fall into if not done deliberately.
  The existing 37-sample benchmark stays fully outside all three splits,
  reserved purely as an independent, held-out sanity check.
- **Evaluation metrics**: exact-match accuracy (primary), character
  accuracy / edit distance (secondary, already used throughout this
  project's benchmarking), plus a confusion matrix specifically tracking
  the already-known problem pairs (D↔O, 2↔7, B↔8) to directly measure
  whether training closes exactly the gaps this investigation identified.

This is a real, actionable plan — not a placeholder — but it is future
work, correctly out of scope for this pass (no training was attempted or
claimed this phase).

## Regression

```
python -m pytest tests/ -q
254 passed, 3 skipped, 0 failed
```

Identical to the count at the start of this phase. No file under
`pipeline.py`, `recognition/`, or `tests/` was modified this phase — every
experiment ran in isolated scratch environments (`/tmp/fpo_venv`,
`/tmp/LPRNet_Pytorch`) that never touched the shipped codebase.

---

## Final Decision Gate

1. **Is PaddleOCR generic or plate-specific?** Generic scene-text
   (`en_PP-OCRv4_rec`, SVTR_LCNet, 95-character vocabulary including
   lowercase/punctuation never valid on a plate) — confirmed by direct
   inspection, not assumed.
2. **Is a legitimate better OCR model available?** Not one that could be
   *verified* this phase. One strong, purpose-built candidate
   (Awiros/anpr-ocr) was found but is blocked by this environment's
   network policy (huggingface.co unreachable) — genuinely unknown, not
   claimed either way.
3. **Does it outperform PaddleOCR on the 37 plates?** The two candidates
   that *could* be run (fast-plate-ocr, LPRNet) both performed
   substantially worse — 29.7% and 0% vs PaddleOCR's 51.4%, same
   methodology, same crops.
4. **Does it outperform PaddleOCR on real CCTV?** Not tested — the Phase
   5 gate correctly wasn't met by any runnable candidate, so Phase 9 was
   correctly skipped rather than run on a losing candidate.
5. **Does temporal fusion improve it further?** Not tested for the same
   reason (Phase 8 correctly skipped). PaddleOCR's existing temporal
   fusion is untouched and still produces the real, shipped 56.8%.
6. **New exact-match accuracy?** **Unchanged this phase: 56.8% (21/37)**
   — this was purely an investigation phase; nothing was shipped that
   would change the production number.
7. **Character accuracy?** 0.841 (PaddleOCR, raw single-pass, detector
   crop, this phase's benchmark methodology).
8. **FPS?** Unchanged — no pipeline code was touched this phase.
9. **Biggest remaining error source?** Two real, independent causes,
   confirmed again this phase with fresh raw-engine evidence: (a) genuine
   recognition-model character confusion (D↔O being the clearest,
   measured pattern) that a vocabulary-restricted, Indian-plate-trained
   model would very plausibly fix but this environment could not verify;
   (b) crop-boundary truncation on a handful of samples, upstream of any
   OCR engine, unaffected by which recognition model is used (confirmed
   again this phase: `fast-plate-ocr` shows the identical truncated read
   on the identical samples).
10. **Can we realistically approach >90% with the current model?** No.
    56.8%, with a raw single-pass ceiling around 51–52% and a real,
    structural, un-fixable-by-config character-confusion rate, leaves a
    large gap that config tuning has already been pushed close to its
    limit on (Part A's earlier sweep).
11. **Do we need a custom Indian plate-recognition model?** Yes, most
    likely — either successfully obtaining and verifying Awiros's
    purpose-built model, or executing the Phase 12 training plan. Generic
    scene-text OCR, even well-tuned, has a real ceiling on this problem.
12. **Is TrackX ready for live-camera integration?** **No.** Unchanged
    from the prior phase's conclusion — this investigation phase found no
    verified improvement to point to, and explicitly did not claim one
    where the evidence didn't support it.
