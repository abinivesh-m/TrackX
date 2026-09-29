# Phase 5 — Building an Indian License-Plate OCR Training Dataset

Date: 2026-09-09
Scope: dataset acquisition and preparation only. **No production code was
modified.** No model was trained. `pipeline.py` and every other file under
production paths are byte-identical to before this phase.

Baseline preserved and re-confirmed at the end of this phase:
`python -m pytest tests/ -q` → **254 passed, 3 skipped, 0 failed** (identical
to the count at the start of this phase). The existing 37-sample TrackX
benchmark (`docs/a1_baseline_table_2026-09-09.csv`) was not read into any
training artifact — it was only used, in Part D below, to calibrate
augmentation ranges from its *already-computed scalar quality metrics*
(blur/brightness/contrast scores), never its images or ground-truth text.

---

## 0. Bottom line, up front

**Zero real, licensed, downloadable Indian license-plate images with
character-level OCR ground truth were obtained this phase.** Every
candidate source that is both (a) legitimately licensed for training use
and (b) actually reachable from this environment turned out to be either
too small (tens to low hundreds of images), detection-only (bounding boxes
with no plate-text transcription), or explicitly non-commercial/no-derivative
licensed. The one dataset that is the right size and has real
character-level ground truth (`sanchit2843/Indian_LPR`, 16,192 images /
21,683 annotated plates) is **not publicly downloadable at all** — its own
authors state this directly (Part A, source 1). This is consistent with
the pattern found in the prior Awiros investigation: the technically best
candidates keep failing on access or licensing, not on technical merit.

This is reported as found. No image was fabricated, no license was assumed,
and no dataset without a verifiable license was treated as usable.

---

## Part A — Legitimate data sources investigated

Every candidate below was checked through `WebSearch`/`WebFetch` (no
scraping, no bypassing of tool-reported access failures, no curl-based
workarounds). "License unverifiable" means the tooling in this environment
could not extract the license field, not that no license exists — Kaggle
and AIKosh serve their license/metadata via client-side JavaScript that the
page-fetching tool cannot execute, so their license badge is not present in
the fetched content. Per the hard rule ("no unlicensed dataset presented as
usable"), every such entry is treated as **not usable** until a human
verifies the license directly in a browser.

| # | Dataset | Source / URL | Images | Indian coverage | Plate types | OCR ground truth? | License | Commercial/competition use | Redistribution/training allowed | Image quality | Known limitations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Indian_LPR | [github.com/sanchit2843/Indian_LPR](https://github.com/sanchit2843/Indian_LPR) | 16,192 images / 21,683 plates (per-character 4-point annotations) | 10 Indian states, cars/bikes/trucks/three-wheelers/buses, front+rear | Single & dual-row, real CCTV/dashcam | **Yes** — full transcriptions | None stated | **Not applicable — data not released** | **Not applicable** | Unknown (never released) | Authors state directly: *"We can't make dataset public because of legalities involved in making Indian Road data public, feel free to contact if you need any other help in your work."* Confirmed by direct fetch of the repo and its arXiv paper (2111.06054) this session. Code/paper are public; the images are not. |
| 2 | Indian-Licence-Plate-Image-Dataset (DataCluster Labs, GitHub sample) | [github.com/datacluster-labs/Indian-Licence-Plate-Image-Dataset](https://github.com/datacluster-labs/Indian-Licence-Plate-Image-Dataset) | ~17 sample images publicly visible; vendor claims 6,000+ in the full paid set | Vendor claims 20+ states | Cars/bikes/trucks/autos | Unclear (sample too small to confirm) | **No LICENSE file present** (confirmed by direct repo file listing) | Unusable — no license | Unusable — no license | N/A | This is a marketing sample for a commercial vendor (Datacluster AI); the real dataset requires contacting `sales@datacluster.ai`, i.e. a paid commercial negotiation, which this investigation does not initiate (see Part A note below). |
| 3 | Indian-Number-Plates-Dataset (DataCluster Labs, GitHub sample) | [github.com/datacluster-labs/Indian-Number-Plates-Dataset](https://github.com/datacluster-labs/Indian-Number-Plates-Dataset) | Vendor claims 20,000+ full set; public sample much smaller | Vendor claims 700+ locations | Detection (bbox) | **No** — bounding boxes only, no transcription in the sample | **No LICENSE file present** in repo | Vendor states "no commercial use without a license" | No | HD+ (1920×1080 min, per vendor) | Same vendor as #2. Proprietary; full dataset is a paid product. |
| 4 | `Dataclusterlabspvtltd/indian-number-plates-dataset` (Hugging Face) | [huggingface.co/datasets/Dataclusterlabspvtltd/indian-number-plates-dataset](https://huggingface.co/datasets/Dataclusterlabspvtltd/indian-number-plates-dataset) | Public sample ~200 images (~200 bboxes); vendor's full set 15,000+ images / 12,000+ bboxes | Urban + rural India, mobile-captured | Detection, includes `number_plate_text` attribute per the card | Card states per-plate text attributes exist | **CC-BY-NC-ND-4.0** for the sample tier (confirmed by direct fetch of the dataset card) | **Explicitly prohibited**: card states *"No commercial use without a license from DataCluster Labs"* | **Explicitly prohibited**: *"No derivative works or redistribution"* and *"No use in training commercial ML models"* | Unknown | Same vendor as #2/#3, distributed through a third channel. This is the clearest license text found for any DataCluster Labs tier — and it is a hard "no" for training use without a purchased commercial license. The full 15,000+ set is reachable in principle only via a paid license from `sales@datacluster.ai` — a business/purchasing decision, not a technical download, and outside this investigation's scope per the standing purchase-authorization rules. |
| 5 | IND-VNP: Indian Vehicle and Number Plate Image Dataset | [ieee-dataport.org/documents/ind-vnp-...](https://ieee-dataport.org/documents/ind-vnp-indian-vehicle-and-number-plate-image-dataset) | 28,864 images (12,858 "Raw" + 16,006 "Blur") | India-focused, per title | Classification folders (Bikes, Cars, Trucks, Number-Plates, etc.) — **not per-plate transcriptions** | No evidence of character-level ground truth in the folder structure described on the page | **CC BY-NC-SA 4.0** (confirmed on page) | **Non-commercial only** — explicitly excluded by the license | Share-alike only, non-commercial | Unknown (paywalled) | Requires a **paid IEEE DataPort subscription** to even inspect the actual files; this investigation did not purchase access (purchase requires explicit user authorization, not made here). Even if accessed, the license forecloses commercial/competition use for a BEL-sponsored deliverable unless that use is confirmed non-commercial. |
| 6 | Indian License Plate Recognition Dataset (YOLO & OCR) | [ieee-dataport.org/documents/indian-license-plate-recognition-dataset-yolo-ocr](https://ieee-dataport.org/documents/indian-license-plate-recognition-dataset-yolo-ocr) | Not disclosed pre-purchase; archive is 63.28 MB | India-focused, per title | YOLO detection set + a **36-class (0-9, A-Z) per-character crop set** — genuinely useful shape for OCR training | Character-level crops exist (per page description), not full-plate transcriptions | **Not disclosed** pre-purchase | Unknown — cannot verify without paying | Unknown — cannot verify without paying | Unknown | Same paywall issue as #5. This is the single most structurally useful-sounding candidate found (native 36-class vocabulary matching TrackX's target vocabulary exactly) but its license cannot be legally confirmed without a purchase this investigation is not authorized to make. |
| 7 | "Indian License Plate" (Roboflow user `nivu`) | [universe.roboflow.com/nivu/indian-license-plate-knte7](https://universe.roboflow.com/nivu/indian-license-plate-knte7) | 1,650 images | Unspecified state coverage | Detection only, single class (`indian_licence_plate`) | **No** — bounding box only, no plate text | **CC BY 4.0** (confirmed on page) | **Allowed** with attribution | **Allowed** with attribution | Unverified (crowd-sourced) | The cleanest legitimately-usable license found this session — but it is a plate-*detector* dataset, not an OCR-recognition dataset, and at 1,650 images alone it does not reach the 5,000-image target even if it did have transcriptions. |
| 8 | "Indian Number Plates" (Roboflow, DataCluster Labs teaser) | [universe.roboflow.com/datacluster-labs-agryi/indian-number-plates-9oobq](https://universe.roboflow.com/datacluster-labs-agryi/indian-number-plates-9oobq) | 46 images public (vendor claims 20,000+ full set) | Unspecified | Detection only, single class | No | **CC BY 4.0** for the 46-image public sample | Allowed for the sample; full set is paid | Allowed for the sample only | Unverified | Confirms #2/#3's vendor is the same across all four channels (GitHub ×2, Hugging Face, Roboflow, Kaggle) — one commercial vendor, not four independent sources. |
| 9 | "Indian License Plates" (Kaggle, `thamizhsterio`) | [kaggle.com/datasets/thamizhsterio/indian-license-plates](https://www.kaggle.com/datasets/thamizhsterio/indian-license-plates) | Unknown | Unknown | Unknown | Unknown | **License unverifiable** — Kaggle's license badge is rendered client-side by JavaScript; neither `WebFetch` nor `WebSearch` could extract it (confirmed by two independent fetch attempts, including a check for embedded JSON-LD/schema.org metadata, which was also absent from the fetched markup) | Unverifiable | Unverifiable | Unverifiable | Treated as not usable per the hard rule against presenting an unlicensed dataset as usable — this is a tooling limitation, not a confirmed bad license, and should be re-checked by a person with a browser. |
| 10 | "Indian Vehicle License plates" (Kaggle, `ankitbarai507`) | [kaggle.com/datasets/ankitbarai507/indian-vehicle-license-plates](https://www.kaggle.com/datasets/ankitbarai507/indian-vehicle-license-plates) | Unknown | Unknown | Unknown | Unknown | License unverifiable (same tooling limitation as #9) | Unverifiable | Unverifiable | Unverifiable | Same caveat as #9. |
| 11 | "Indian vehicle license plate dataset" (Kaggle, `saisirishan`) | [kaggle.com/datasets/saisirishan/indian-vehicle-dataset](https://www.kaggle.com/datasets/saisirishan/indian-vehicle-dataset) | Unknown | Unknown | Unknown | Unknown | License unverifiable | Unverifiable | Unverifiable | Unverifiable | Same caveat as #9. |
| 12 | "Indian License Plates with Labels" (Kaggle, `kedarsai`) | [kaggle.com/datasets/kedarsai/indian-license-plates-with-labels](https://www.kaggle.com/datasets/kedarsai/indian-license-plates-with-labels) | Unknown | Unknown | Labels suggested by title | Possibly | License unverifiable | Unverifiable | Unverifiable | Unverifiable | Same caveat as #9. |
| 13 | Other Kaggle/Roboflow Indian-plate listings found (10,125-image general "License Plate Detection Dataset" by `barkataliarbab`, `bellair/indian-licence-plates`, `umar1103/final-licence`, several more Roboflow projects under 2,000 images each) | Various | Various, mostly under 2,000 each; the 10,125-image one is not India-specific per its title | Mixed/unconfirmed | Mostly detection-only | Mostly no | Mostly unverifiable (Kaggle) or CC BY 4.0 at small scale (Roboflow) | Unverifiable/mixed | Unverifiable/mixed | Unverifiable/mixed | Listed for completeness; none changes the conclusion below. |
| 14 | AIKosh (IndiaAI Mission's national AI dataset repository) | [aikosh.indiaai.gov.in](https://aikosh.indiaai.gov.in/) | Unknown | N/A | N/A | N/A | N/A | N/A | N/A | N/A | A real, government-run dataset platform exists and is plausible as a future source, but its catalogue is a client-side-rendered search UI that this session's fetch tool could not query. **Not ruled out — genuinely unchecked**, and worth a human visiting the site directly, distinct from every "unverifiable" Kaggle entry above where a license badge exists but couldn't be read. |
| 15 | `platerecognizer.com/number-plate-datasets/` (curated aggregator) | [platerecognizer.com](https://platerecognizer.com/number-plate-datasets/) | N/A (index page) | — | — | — | — | — | — | — | Checked as a cross-reference; it lists CCPD (China), UFPR-ALPR (Brazil), California, Croatia, Mercosur, and generic stock-photo sources — **no Indian-specific entry at all**, corroborating that a ready-made, well-known, freely licensed Indian OCR dataset does not appear on the field's own standard reference list. |

**Note on the DataCluster Labs purchase path (#2–#4, #8)**: this is the
same commercial entity across every channel it publishes to. Its licensing
terms are explicit and internally consistent: free public samples are
capped at roughly 46–200 images, are CC-BY-NC-ND (or unlicensed) depending
on channel, and its own text says outright that training a commercial ML
model on them is prohibited. A paid commercial license from DataCluster
Labs is a real, named path to 15,000–20,000 Indian plate images with
apparent OCR text attributes — but purchasing it is a business decision for
the user to make (cost unknown, not published), not a technical action this
investigation can take unilaterally.

---

## Part B — Dataset diversity requirements: assessed against what was found

None of the accessible, adequately-licensed sources (row 7, 1,650 images,
CC BY 4.0) come close to covering the required diversity axes on their own.
Assessed honestly against the request:

- Multiple state prefixes: unknown for the one usable source; not
  confirmed by any accessible metadata.
- Cars/motorcycles/trucks/buses: the DataCluster Labs vendor family claims
  this mix, but its usable tier is licensed non-commercial/no-derivative.
- Front and rear plates: same caveat.
- Single-row and dual-row: found in the *unavailable* Indian_LPR dataset
  (#1) and possibly in the paywalled IEEE OCR dataset (#6); not confirmed
  present in any accessible, adequately-licensed source.
- Day/night, rain, glare, shadow, motion blur, low resolution, oblique
  angle, dirty/damaged, partial occlusion, CCTV-style imagery: the
  DataCluster Labs and IND-VNP descriptions claim broad real-world capture
  conditions, but again sit behind the same license/paywall blockers.

No dataset was artificially inflated with near-duplicate frames in this
investigation, because no dataset was assembled at all — there is nothing
to deduplicate yet.

---

## Part C — Ground-truth quality validation

Not applicable this phase: zero training images were obtained, so there is
no ground-truth transcription set to validate, no character-count/illegal-
character check to run, and no duplicate-image check to run. The
**validation tooling itself was built and tested** so it is ready the
moment real, licensed data exists — see Part F.

The Indian OCR vocabulary constraint requested (`0-9A-Z`, no lowercase
without documented reason) is captured as a concrete artifact:
`docs/dataset_prep/indian_plate_vocab.txt` (36 characters, one per line,
in CTC classifier-index order). This is narrower than every candidate
model's shipped vocabulary found in the prior investigation (PaddleOCR's
95-class `en_dict.txt`, Awiros's 63-class vocabulary) and matches the
36-class structure independently used by the paywalled IEEE "YOLO & OCR"
dataset's per-character crop folders (#6 above) — external corroboration,
from a source this investigation could not access, that 36 classes is the
right target even though that source's images remain unobtained.

---

## Part D — Leakage prevention

This was built and **tested against synthetic fixture data**, not just
documented:

- `docs/dataset_prep/held_out_benchmark_plates.txt` — the exact 12 real
  plate texts (plus one corrected variant, `UP16CD5633`, alongside the
  original CSV value `UP16CO5633` for track154 — see
  `docs/PART_A_OCR_MODEL_OPTIMIZATION_2026-09-09.md`) that make up
  TrackX's existing 37-sample ground-truth benchmark
  (`docs/a1_baseline_table_2026-09-09.csv`). Any future training corpus
  row whose transcription exactly matches one of these strings must be
  dropped, not merely excluded from the training split.
- `docs/dataset_prep/leakage_guard_split.py` — a real, runnable splitter
  that groups by **both** `physical_plate_id` and `plate_text` (a union of
  the two, since some source datasets will only expose one of them) before
  assigning whole groups to train/val/test, and hard-drops every held-out
  benchmark plate before splitting at all. It was actually run this
  session:

  ```
  $ python3 docs/dataset_prep/leakage_guard_split.py --self-test
  SELF-TEST PASSED (synthetic fixture data only, no real plates):
    input rows (incl. injected leaks): 83
    dropped as benchmark leakage: 5
    train/val/test sizes: 63/8/7
    no physical_plate_id or plate_text crosses a split boundary
    no held-out benchmark plate text present in any split
  ```

  This first run caught a real bucket-assignment bug (the running-total
  check compared a single bucket's size against a cumulative-fraction
  threshold instead of tracking rows assigned so far, so `test` was never
  populated) — fixed and re-verified before being reported here, in
  keeping with "test everything for real."
- Because this session's own real ground-truth-plate inventory (Part C of
  `docs/AWIROS_VERIFICATION_AND_TRAINING_DECISION_2026-09-09.md`) found
  only 12 distinct physical plates across the entire existing TrackX
  corpus, that finding stands unchanged: **TrackX's own captured footage
  still cannot be the training source** — it can only remain the untouched
  test set, guarded by the mechanism above.

---

## Part E — Dataset statistics

No real images were obtained, so the requested statistics table (total
images, unique vehicles, state-prefix distribution, character frequency,
plate-length distribution, row-count distribution, vehicle-type
distribution, resolution distribution, blur/quality distribution,
day/night distribution, train/val counts, duplicate count, rejected-sample
count) **cannot be populated with real numbers without fabricating them**,
and is not fabricated here.

The one figure that is real and reportable: **rejected/blocked source
count = 13 of 15** candidate sources investigated (Part A), broken down as:

- 1 source with real annotations but the data is not released at all
  (Indian_LPR)
- 4 sources tied to one commercial vendor whose usable tier is
  non-commercial/no-derivative or unlicensed (DataCluster Labs, all
  channels)
- 2 sources paywalled behind an IEEE DataPort subscription this
  investigation did not purchase
- 5 Kaggle sources whose license could not be extracted by available
  tooling and are therefore treated as unusable
- 1 aggregator cross-check confirming no well-known Indian-specific
  dataset exists on the field's standard reference list

Only 1 of 15 sources (Roboflow `nivu`, 1,650 images, CC BY 4.0) is both
accessible and clearly licensed for use — and it has no OCR ground truth,
only detection boxes.

---

## Part F — Training preparation (infrastructure built, unblocked by data)

Everything that can be prepared *without* real images was built and is
committed under `docs/dataset_prep/` (explicitly outside any production
code path — nothing here is imported by `pipeline.py` or any other shipped
module):

| File | Purpose | Status |
|---|---|---|
| `indian_plate_vocab.txt` | 36-class `0-9A-Z` vocabulary, CTC classifier-index order | Ready |
| `held_out_benchmark_plates.txt` | Permanent training-exclusion list for the 12 real benchmark plates (13 lines incl. the track154 correction) | Ready |
| `manifest_schema.md` | Source manifest format (PaddleOCR-native `path\tlabel`) and extended JSONL metadata schema for split/statistics tooling | Ready |
| `leakage_guard_split.py` | Group-aware, benchmark-excluding train/val/test splitter | **Built and self-tested against synthetic data** (bug found and fixed this session) |
| `augmentation_config.yaml` | Geometric/photometric/blur/occlusion/noise augmentation ranges | Ready; ranges calibrated against real measured blur/brightness/contrast statistics from the 37-sample benchmark's already-computed scalar quality metrics (not its images or labels) |

What is **not** prepared, and cannot honestly be prepared yet: actual
training/val/test manifests (no real images exist to list), a fine-tuning
launch script or trained checkpoint (would require real data), and any
per-character or per-state frequency table (would require real data).

Fine-tuning target, per the prior Awiros/Training report (unchanged this
phase): `en_PP-OCRv4_rec` (SVTR_LCNet), input `3×48×320`, drop-in
replacement inside `PlateOCR._read_paddleocr` with no changes required to
`vote_plate_text()`, `CONFUSABLE_PAIRS`, or the spatial-outlier filter.

---

## Part G — Infrastructure requirements

Reconfirmed directly this session (not assumed):

```
torch.cuda.is_available() -> False
nvidia-smi -> command not found
nproc -> 2
free -h -> 7.8Gi total RAM
```

This sandbox has **no GPU**. Fine-tuning `en_PP-OCRv4_rec` — even on a
modest 5,000–15,000-image corpus — is not feasible here in reasonable time
on 2 CPU cores. Per Part B of the prior training-decision report, this
still requires external GPU infrastructure (a single mid-range consumer or
cloud GPU with ≥8GB VRAM is enough for this model size; multi-day CPU-only
training was explicitly ruled out as impractical, not merely slow).
Nothing about this phase's dataset findings changes that requirement.

---

## Part H — Rejected/blocked sources (full list)

See the "Known limitations" column of the Part A table for each of the 13
rejected/blocked sources and the exact reason. Summarized by blocker type:

- **Not publicly released** (1): Indian_LPR — authors explicitly decline
  to release the images.
- **No license / prohibits commercial training use** (4): all DataCluster
  Labs channels.
- **Paywalled, license unconfirmed pre-purchase** (2): both IEEE DataPort
  entries.
- **License unverifiable by available tooling** (5): Kaggle listings.
- **Confirmed no Indian-specific entry exists** (1): the field's own
  curated aggregator page.

---

## Part I — Decision gate

1. **Can Awiros be legitimately evaluated now?** No — unchanged from the
   prior report; huggingface.co remains blocked by this sandbox's static
   egress policy.
2. **Benchmark against PaddleOCR on identical 37 samples?** Not applicable
   — no alternative model or dataset was obtained this phase to benchmark.
3. **If no, what exact external artifact/environment is required?** A
   licensed, real Indian-plate OCR corpus of ≥5,000 images with
   character-level transcriptions — and, per this phase's findings, that
   requires one of: (a) a paid commercial license from DataCluster Labs
   (~15,000–20,000 images, cost and exact terms undetermined — a business
   decision for the user), (b) a paid IEEE DataPort subscription plus
   confirmation that dataset #5 or #6's actual license permits the
   intended use (undetermined pre-purchase), or (c) new data collection
   from properly consented/licensed sources, since no free, adequately
   licensed, adequately sized, OCR-labeled Indian plate dataset was found
   to be both accessible and usable this phase.
4. **Is custom Indian-plate OCR training now the highest-value path?**
   Directionally yes (unchanged from the prior report's conclusion) — but
   it is now clear the blocker is not architecture or training-plan
   design, which is ready (Part F), but **data acquisition itself**.
5. **What minimum dataset is required before training is worth doing?**
   Unchanged: 5,000–15,000 real images is the realistic floor for a
   fine-tuning run to generalize beyond TrackX's own 12-plate corpus; this
   phase found no accessible source that legitimately clears that floor
   with OCR ground truth included.
6. **What should NOT be worked on yet?** Writing a fine-tuning launch
   script, picking a learning-rate schedule, or any further OCR-library
   evaluation — all of that is now downstream of a licensing/data
   decision, not an engineering one.

---

## FINAL DECISION GATE

**NOT READY — DATASET/LICENSING BLOCKER**

Single most important next action: **a human (not this investigation)
needs to make a licensing decision** — specifically, contact DataCluster
Labs (`sales@datacluster.ai`) to get an actual price and exact commercial-
use terms for their ~15,000–20,000-image Indian plate dataset (the only
candidate found this phase that is realistically the right size and has
plate-text ground truth), and in parallel check the two paywalled IEEE
DataPort entries' true license text after subscribing. Until one of those
returns a dataset this investigation can legally train on, no further
engineering time should go into OCR-library evaluation, heuristic tuning,
or RTSP work — the training scaffolding in `docs/dataset_prep/` is ready
and tested, and is waiting on data, not on more code.
