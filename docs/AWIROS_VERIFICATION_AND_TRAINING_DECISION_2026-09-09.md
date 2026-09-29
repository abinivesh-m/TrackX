# TrackX — Awiros Verification + Indian Plate Training Decision Gate
### SIH26127 (Bharat Electronics Limited) — 2026-09-09

No production code was modified this pass. Confirmed before and after:
`pipeline.py`, `recognition/ocr_reader.py`, and everything under `tests/`
are byte-for-byte unchanged from the end of the prior phase, and
`python -m pytest tests/ -q` still reports **254 passed, 3 skipped, 0
failed** throughout.

---

## Part A — Awiros/anpr-ocr

### What was legitimately determined from public metadata

| Field | Value |
|---|---|
| Architecture | PaddlePaddle **PP-OCRv5**, `PPHGNetV2_B4` backbone, `MultiHead` decoder combining a CTC head and an NRTR head |
| Parameters | 37.3M |
| Input | 3×48×320 (channels×height×width), same tensor shape family as the currently-shipped PP-OCRv4 recognizer |
| Character vocabulary | 63 classes: `0-9`, `A-Z`, `a-z`, space — narrower than PaddleOCR's shipped 95-char dict (no punctuation), but **not** as tight as a plate-only vocabulary (still carries lowercase + space, which a plate never needs) |
| Max text length | 25 |
| Weight format | SafeTensors, 149MB |
| Training data | Reported as a 558,767-sample corpus, grown from 6,839 real public-labeled samples via synthetic synthesis, two-model consensus pseudo-labeling, distribution-aware/state-balanced curation, and VLM-assisted cleanup — covers both single-row and dual-row Indian plate formats |
| Reported evaluation (vendor's own, **not independently verified**) | 98.42% overall on their own held-out set (98.83% single-row, 96.91% dual-row), 5.09ms latency on an RTX 3090 |
| License | Apache-2.0 |
| Checkpoint source | `huggingface.co/Awiros/anpr-ocr` (`model.safetensors`, plus `test.py`, `en_dict.txt`, `TechnicalReport.pdf`) |
| Inference requirements | `paddlepaddle`/`paddlepaddle-gpu`, `safetensors`, `opencv-python>=4.8.0` (conflicts with this repo's pinned `opencv-python<=4.6.0.66` — would need isolation, same as every other candidate tested), full `PaddleOCR` GitHub source clone (not just the `paddleocr` pip package — PP-OCRv5 isn't in the installed 2.7.3 pip release) |

### Download attempt — exact blocker, documented as instructed

Two independent, real attempts this pass:

1. `curl` directly to `huggingface.co/Awiros/anpr-ocr/resolve/main/model.safetensors`
   → `curl: (56) CONNECT tunnel failed, response 403`.
2. The official `huggingface_hub` Python library's `hf_hub_download()` →
   `ProxyError 403 Forbidden`.

Checked the sandbox's own proxy status endpoint directly: its `noProxy`
allowlist is an explicit, static list of hosts (`pypi.org`,
`files.pythonhosted.org`, `registry.npmjs.org`, a handful of Anthropic
endpoints, etc.) that does **not** include `huggingface.co` or any Hugging
Face CDN host. This is a deliberate organizational network policy, not a
transient failure — retrying, using a different tool, or a different
download method would not change the outcome, and per the hard rules for
this environment, circumventing an org network policy is not attempted.

**Verdict: Awiros/anpr-ocr could NOT be run this pass. No accuracy number
for it is claimed anywhere in this document beyond the vendor's own
reported figures, which are explicitly and repeatedly labeled
"vendor-reported, not independently verified" above.** This is a real,
fully-documented candidate sitting in a distinct, honest state: neither
"proven better" nor "proven worse" than PaddleOCR — genuinely unknown,
blocked by environment, not by the model's own merit or license.

---

## Part B — Training feasibility: three architectures compared

| | **CRNN + CTC** | **SVTR / PP-OCR-style** (what's shipped now, and what Awiros itself is) | **LPRNet-style** |
|---|---|---|---|
| Core idea | CNN feature extractor → BiLSTM sequence layer → CTC decode | CNN/attention hybrid ("SVTR" transformer blocks) → CTC (or CTC+attention MultiHead like Awiros) | Pure CNN (Inception-style blocks), no recurrent/attention layer → CTC |
| Params (typical) | 5–10M | 10–40M (PP-OCRv4 rec ≈ 10M, Awiros's PPHGNetV2_B4 ≈ 37M) | **~500K–2M** (this project's own already-cloned `sirius-ai/LPRNet_Pytorch` checkpoint is 1.8MB on disk) |
| Real accuracy on plate-shaped text (this project's own measurements) | Not directly tested this project (no CRNN checkpoint available), but architecturally the predecessor to SVTR — generally lower accuracy ceiling than transformer-hybrid designs on curved/rotated text | **Best measured so far**: PaddleOCR's shipped SVTR_LCNet gets 51.4% raw / 56.8% with temporal fusion on our real 37-sample set | **Worst measured so far** on our data with the one available checkpoint (0/37) — but that specific checkpoint's failure is a vocabulary/plate-grammar mismatch (Chinese plates), not evidence against the architecture family itself |
| Fine-tuning vs. from-scratch feasibility given TrackX's real data volume (Part C) | From-scratch: needs the most data of the three. Fine-tuning an existing CRNN plate checkpoint: not found (searched this session and the prior phase — no legitimately licensed CRNN plate checkpoint was located, only PaddleOCR/SVTR-family and LPRNet-family checkpoints) | **Best fit for fine-tuning**: `en_PP-OCRv4_rec` is already installed and already proven to work reasonably on this exact data; PaddleOCR's own `tools/train.py` supports fine-tuning a `.pdparams` checkpoint directly, and a from-scratch Indian-vocabulary head is a smaller lift than a full architecture swap | Smallest model, fastest to train and to run, but this session's own real, empirical result (0/37 with the only found checkpoint) shows the family is unforgiving of vocabulary/grammar mismatch — a from-scratch Indian-vocabulary LPRNet would need to be trained fully from zero (no legitimate Indian-plate LPRNet checkpoint was found with a usable license — see Phase 3's `Indian_LPR` verdict) |
| Inference latency (CPU, this project's actual deployment target — no GPU, confirmed this session: `torch.cuda.is_available()` → `False` in this sandbox) | Moderate | PaddleOCR's shipped model already measured on real CPU: ~100ms/crop (this project's own benchmark, this session) | Fastest by a wide margin — LPRNet's own architecture and this session's real CPU run of the 1.8MB checkpoint both point to well under 10ms/crop, consistent with `fast-plate-ocr`'s CCT-based `cct-xs` model (a comparably small architecture) measuring 3.2ms/crop on this same CPU this session |
| **Recommendation** | Not recommended — no accuracy advantage identified, and no legitimate fine-tune-able checkpoint exists for it in this project's stack | **Recommended primary path**: fine-tune the already-integrated `en_PP-OCRv4_rec` (or migrate to PP-OCRv5/Awiros's architecture if that model is ever obtained and separately verified) | Worth a from-scratch attempt only as a *secondary*, lightweight/edge-deployment track once real Indian training data exists — not the first thing to build, given the near-total data gap identified in Part C |

### Data requirements

- **Fine-tuning `en_PP-OCRv4_rec` on Indian plates**: realistically **5,000–15,000** labeled real Indian plate crops as a practical minimum for a fine-tune to meaningfully move the needle (fine-tuning an existing, already-competent checkpoint needs far less than training from zero). Awiros's own reported pipeline needed 558,767 samples, but the overwhelming majority of that was *synthetic/pseudo-labeled*, grown from only 6,839 real labeled seed samples — a realistic, honest signal that a much smaller *real* seed set, expanded synthetically, is the actual practical path, not 500K+ real photographs.
- **From-scratch LPRNet-style**: needs comparably more data per parameter than a fine-tune (no pretrained initialization to lean on), realistically in the same 5,000–15,000+ range or more before it would be competitive, despite the smaller model.

### Annotation format

Plate crop image + exact transcription string. For a PaddleOCR fine-tune
specifically: PaddleOCR's own native recognition-training label format
(`relative/image/path\tGROUND_TRUTH_STRING`, one line per sample, UTF-8),
directly compatible with `PaddleOCR/tools/train.py -c
configs/rec/PP-OCRv4/en_PP-OCRv4_rec.yml` with `Global.pretrained_model`
pointed at the already-downloaded `en_PP-OCRv4_rec_infer` checkpoint this
repo already has cached — this is the lowest-friction integration path
available, since it reuses infrastructure this environment has already
proven to work.

### Indian character vocabulary

Exactly `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ` (36 classes) + a CTC blank
— matching `fast-plate-ocr`'s real, shipped, working precedent (its
`plate_config.yaml`, inspected directly in the prior phase) rather than
Awiros's slightly looser 63-class vocabulary (which still carries
lowercase + space that an Indian plate never needs). Per Phase 3's
decisive, empirical finding, **this vocabulary must be trained in from the
start** (or the classifier head specifically re-initialized and
fine-tuned against it) — it cannot be swapped into the existing pretrained
checkpoint via config alone (confirmed: `IndexError` when attempted).

### Augmentation

Unchanged from the prior phase's Phase 12 plan, still the right list,
still grounded in this project's own real measured crop-quality range
(`docs/a1_baseline_table_2026-09-09.csv`: blur 366–17,201, brightness
80–172, contrast 34–85 across the 37 real samples) — **and now sharpened
further by Part D below**, which maps each specific known confusion
pattern to whether augmentation is even the right fix for it.

### Train / validation / test split, and identity-leakage avoidance

See Part C — this is where the real constraint actually bites.

### Evaluation

Exact-match accuracy (primary, matches how this whole project has been
graded throughout), character accuracy via `difflib`-based alignment
(secondary, already the methodology used in every benchmark this project
has run), plus a confusion matrix specifically tracking the pairs in Part
D, re-measured after training to directly verify whether training closed
the gaps this investigation identified — not just that overall accuracy
went up.

### GPU requirements

**This cloud sandbox has no GPU** (`torch.cuda.is_available()` → `False`,
2 CPU cores, 7.8GB RAM, confirmed directly this session — not assumed).
Fine-tuning even a 10M-parameter recognition model on 5,000+ images is
impractical here — PaddleOCR's own recognition training documentation
targets GPU training as the norm. **Training itself must happen on a
GPU-equipped machine** (a cloud GPU instance, or the user's own hardware
if it has one — unknown from here, the linked Windows device's GPU status
was not checked this pass and is a fair thing to verify before committing
to this path). Inference of the *result*, however, stays CPU-friendly and
consistent with this project's existing deployment target — every
candidate model actually run this project (PaddleOCR, `fast-plate-ocr`,
LPRNet) has run acceptably fast on CPU alone.

### Expected inference latency

Extrapolating from this project's own real, measured numbers rather than
guessing: a fine-tuned `en_PP-OCRv4_rec`-family model would be expected to
keep roughly PaddleOCR's current real CPU latency (~100ms/crop, measured
this session) since the architecture and size wouldn't meaningfully
change — a fine-tune changes weights, not FLOPs. A from-scratch,
LPRNet-style Indian model would be expected to land in the same range as
this session's real LPRNet/`fast-plate-ocr` CPU measurements (single-digit
milliseconds per crop) given the much smaller parameter count.

### Integration with the existing temporal-fusion pipeline

No change needed to `recognition/ocr_reader.py`'s `vote_plate_text()`,
`recognition/plate_matcher.py`'s `CONFUSABLE_PAIRS`, or `pipeline.py`'s
spatial-outlier filter — all of that operates on `(text, confidence)`
tuples regardless of which model produced them. A trained/fine-tuned model
would slot in as a drop-in replacement inside `PlateOCR._read_paddleocr`
(or a new sibling method, if the architecture differs enough to need a
different pre/post-processing path), with the exact same evidence
structure flowing into the exact same, already-validated fusion and
false-merge-protection layers. This is a real, concrete integration
advantage of the fine-tuning path specifically (over training a
completely different architecture from a different framework) — it
extends infrastructure this project has already built and tested, rather
than requiring a second, parallel OCR pipeline.

---

## Part C — Dataset strategy

### What TrackX actually has, measured directly this session (not assumed)

- **3 distinct source videos** (`anpr_test1.mp4`, `anpr_test2.mp4`,
  `anpr_compare.mp4`) — a single location, a narrow time window, one
  camera angle family, daytime only.
- **162 distinct (camera, track) pairs** across all three in one clean
  pipeline run — but this counts every tracked vehicle, not every
  *distinct physical vehicle*: `anpr_compare.mp4` visibly overlaps the
  other two clips (e.g. `DL7CP8161` and `UP22AT3248` both reappear across
  TEST1 and COMPARE in the ground-truth table).
  - **37 samples have a human-verified ground-truth label at all.**
  - Of those 37, there are only **12 distinct physical plates** — the same
    handful of real vehicles re-appear across many tracks (passing the
    camera more than once, or being visible in more than one of the three
    clips).
  - Those 12 plates carry only **3 distinct state codes** (`DL`, `KA`,
    `UP`) — out of roughly three dozen real Indian state/UT codes.

**Honest conclusion: TrackX's own captured data, as it exists today, is
not just short of the ~5,000–15,000-real-image minimum from Part B — it
is short by two to three orders of magnitude, and what little exists has
almost no state, lighting, angle, or plate-format diversity.** This is the
single most important, concrete finding of Part C, and it directly shapes
the Part E recommendation: no realistic amount of *augmentation* alone
turns 12 real plates into a usable Indian-plate training set — augmentation
multiplies existing diversity, it does not manufacture diversity that was
never captured in the first place (a blurred/rotated copy of a `UP`-state
Maruti Swift is still not evidence about what a `TN`-state truck's plate
font looks like).

### What's needed

- Real, additional Indian plate imagery spanning materially more states,
  vehicle types, plate formats (including the dual-row format Awiros's
  own documentation specifically calls out as a separate, harder case —
  none of TrackX's own 12 real plates are dual-row, so this project has
  *zero* real coverage of that format today), lighting conditions, and
  camera angles than the current 3-clip corpus provides. Public,
  properly-licensed Indian plate datasets (the same category of source
  Awiros itself started from — "6,839 publicly available labeled
  samples") are the realistic seed; this project's own 3 clips cannot be
  the training source, full stop, because of the diversity gap just
  measured.

### Clean split — no benchmark contamination

```
[ any newly-acquired/public Indian plate data ] ──▶ train / val split
                                                      (80/10, by vehicle,
                                                       not by frame)

[ TrackX's existing 37-sample, ground-truth-labeled benchmark ] ──▶
                                                      permanently held out,
                                                      NEVER in train or val,
                                                      used only as the
                                                      final, independent
                                                      test set
```

- The 37-sample benchmark (and the 12 distinct physical plates behind it)
  stays **completely outside** any training or validation split, in both
  directions: none of its images are used for training, and — just as
  important, and easy to miss — **none of its 12 *plate texts* should
  appear in the training set either**, even from a different camera angle
  or a different day, since that would let the model "know" the answer to
  a benchmark sample indirectly rather than genuinely generalizing to it.
  This is a slightly stronger guarantee than the usual "don't put the same
  image in both splits" rule, and it matters specifically because this
  project's benchmark plates are few enough that this leak is realistic to
  happen by accident with public data (e.g. `KA02MM9091` or `DL7CP8161`
  format patterns showing up incidentally).
- Within the training data itself, split **by vehicle/plate identity, not
  by frame or by crop** — multiple frames/crops of one physical plate must
  never span train and validation, for the same reason already noted in
  the temporal-fusion context: it would let the model trivially memorize a
  plate it already saw, inflating validation accuracy without real
  generalization.

---

## Part D — Error-driven augmentation: which failure modes belong where

Real, measured occurrence data behind each pair (from this project's own
prior confusion-matrix work, `docs/PHASE4_CROP_VS_OCR_INVESTIGATION_2026-09-09.md`,
plus this session's fresh raw-benchmark re-check):

| Failure mode | Measured occurrences (this project's real data) | Fixed by training augmentation? | Fixed by detector/crop improvement? | Fixed by recognition architecture/vocabulary? | Fixed by temporal fusion? |
|---|---|---|---|---|---|
| **D ↔ O** | 6 occurrences, 6 distinct tracks | Partially — more real examples of both characters in varied fonts/lighting helps the model learn the distinction, but... | No — this is a pure character-shape confusion, not a cropping issue | **Primary fix**: a model trained with a restricted, Indian-plate-correct vocabulary and enough real D/O examples in context has the best shot; this pair is already in the shipped `CONFUSABLE_PAIRS` table | Already tried — confirmed (this and prior sessions) that temporal fusion's positional-vote correction **cannot** fix this specific pattern, because the wrong character is usually already the *dominant* answer among a track's own repeated readings, and the correction mechanism can only promote an alternative that's already dominant, never introduce new information |
| **8 ↔ B** | 6 occurrences (this session's fresh raw-benchmark re-check, largest single pair found) | Partially, same reasoning as D↔O | No | **Primary fix**, same reasoning | Already in `CONFUSABLE_PAIRS`; same structural limitation as D↔O applies when the wrong character is already dominant |
| **2 ↔ 7** | 3 occurrences, tracks 93/1411/1488 | Partially | No | **Primary fix** — not yet in `CONFUSABLE_PAIRS`; a real, previously-investigated case where the wrong character (`7`) was confirmed position-dominant in the track's own real per-frame evidence, so temporal fusion structurally cannot help without a better base recognizer | Already tried, confirmed cannot fix (real per-frame vote data reviewed in a prior session: 7 confident `7`-reads vs 3 confident `2`-reads on the richest sample) |
| **6 ↔ 8** | Not separately isolated with its own occurrence count in this project's real data yet (appears grouped in the >1-per-pair confusion tail); listed in the task brief as a known pattern | Partially | No | Primary fix, same reasoning | Same structural limitation likely applies, not separately re-verified this pass |
| **M ↔ H** | Already present in the shipped `recognition/plate_matcher.py` `CONFUSABLE_PAIRS` table from an earlier engineering pass; no fresh occurrence count was measured against this specific 37-sample set this pass | Partially | No | Primary fix | Structural limitation likely applies |
| **Crop truncation** | Directly re-confirmed this session (Phase 3, Phase 7): identical truncated reads (`X8554` for `UP14DX8554`) appear across **both** PaddleOCR and `fast-plate-ocr` on the same samples | No — this is not a recognition problem at all | **This is the real, primary fix** — the truncation happens before any OCR engine ever sees the full plate; already partially addressed by the existing `PLATE_CROP_PAD_RATIO` (12%, previously measured as near-optimal) but evidently not fully sufficient for every sample | No — swapping recognition models cannot fix a crop that never contained the missing characters | No — temporal fusion can only vote among readings it receives; if every reading of a track is truncated the same way, there's nothing to fuse toward |
| **Blur** | Real measured range this project's own data: blur score 366–17,201 (median 628) | **Yes, directly** — this is exactly what blur augmentation exists to cover, and the real measured range gives a concrete target to augment across (and somewhat beyond) | Indirectly — better plate-detector localization doesn't reduce optical/motion blur itself | No | No — fusion can average out *some* single-frame confidence, but a track with genuinely blurry crops on every frame gets no help |
| **Angled plates** | Not separately measured with a numeric metric in this project's data (no perspective/angle score currently computed) | **Yes, directly** — perspective augmentation is the correct, standard fix | Partially — a tighter, angle-aware detector crop helps but doesn't undo perspective distortion of the characters themselves | No | No |
| **Lighting variation** | Real measured range: brightness 80–172 (median 132), contrast 34–85 (median 67) | **Yes, directly** — brightness/contrast/gamma augmentation, targeted at and beyond this measured range | No | No | Partially — the existing adaptive preprocessing (CLAHE/gamma variants) already helps at inference time; this is a real, already-shipped mitigation distinct from training-time augmentation |

**No special-case substitutions were introduced to improve this
benchmark specifically** — every "fix" identified above is a general
mechanism (a training augmentation category, a detector/crop change, a
vocabulary/architecture change, or a fusion mechanism), never a rule
keyed to a specific plate string or track ID.

---

## Part E — Decision gate

1. **Can Awiros be legitimately evaluated now?** No — its weights are
   hosted only on `huggingface.co`, and this sandbox's network policy
   explicitly blocks that host (confirmed twice, via `curl` and via the
   official `huggingface_hub` library, both returning a clean 403 from the
   organization's own egress proxy, not a transient error).
2. **If yes, benchmark it against PaddleOCR on the identical 37 samples.**
   N/A — condition in (1) not met. No benchmark was run, no accuracy
   number for Awiros is claimed.
3. **If no, what exact external artifact/environment is required?** Any
   execution environment with unblocked access to `huggingface.co` (or a
   manual, out-of-band transfer of `model.safetensors`, `test.py`, and
   `en_dict.txt` into an environment that does have Hugging Face access —
   for example, the user's own linked computer, if its own network policy
   differs from this sandbox's, which was not checked this pass), plus a
   full `PaddleOCR` GitHub source checkout (already proven to clone
   successfully via `git` in this sandbox) and an isolated Python
   environment with `opencv-python>=4.8.0` (which conflicts with this
   repo's pinned `opencv-python<=4.6.0.66` and must not be installed into
   the main environment — the same isolation discipline already used
   successfully for `fast-plate-ocr` and LPRNet this investigation).
4. **Is custom Indian-plate OCR training now the highest-value path?**
   Yes, conditionally — *if and only if* real training data at the volume
   identified in Part C is actually acquired. Training is not
   automatically higher-value than continuing to look for a usable
   pretrained checkpoint (Awiros remains a live, unresolved possibility);
   it is the higher-value path specifically because it is the only one of
   the two that is fully within this project's own control regardless of
   external network/hosting policy.
5. **What minimum dataset is required before training is worth doing?**
   Realistically **5,000–15,000 real, labeled Indian plate crops**,
   spanning materially more than the current 3 states / 12 plates /
   single-row-only coverage — see Part B/C. Below that volume, training is
   very unlikely to beat the current, already-tuned PaddleOCR baseline
   meaningfully, and risks producing a model *worse* than PaddleOCR on
   the very diversity axes (state code, dual-row format, lighting) it
   wasn't shown.
6. **What should NOT be worked on yet?**
   - No further OCR-library shopping (`fast-plate-ocr`, LPRNet, and now
     Awiros's *metadata* have all been legitimately investigated; adding a
     fourth or fifth candidate without new information would be exactly
     the "another random OCR library" pattern this task explicitly warned
     against).
   - No further PaddleOCR config/heuristic tuning aimed at squeezing the
     37-sample benchmark specifically (Part A of the *prior* phase already
     found and shipped the one real, validated config win available;
     anything further risks the benchmark-overfitting this task's hard
     rules explicitly forbid).
   - No production pipeline changes based on this investigation (none were
     made, per the instruction).
   - No RTSP or live-camera work — unchanged from every prior phase's
     conclusion, and now additionally blocked on the data-volume finding
     in Part C, not just the accuracy gap.

---

## RECOMMENDED NEXT ENGINEERING TASK

**Acquire and label 5,000–15,000 real Indian license-plate images from a
properly-licensed public source (or sources), covering materially more
than the current 3-state / single-row-only coverage, and use them to
fine-tune the already-integrated `en_PP-OCRv4_rec` recognition model
against a restricted 36-character (`0-9A-Z`) Indian-plate vocabulary —
with TrackX's existing 37-sample benchmark permanently held out (by
image AND by plate text, per Part C) as the sole final evaluation set —
before any further work is done on RTSP, live-camera integration, or
additional OCR-library evaluation.**

This single task directly targets the actual, measured bottleneck (a
generic recognition model's character-level confusion, confirmed
structural and un-fixable by fusion or config alone) with the one lever
proven, in this same investigation, to be fully within this project's own
control — unlike Awiros, which remains genuinely blocked by an external
network policy this project cannot resolve from inside this environment.
