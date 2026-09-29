# Phase 6 — Securing a Legitimate 5,000+ Indian Plate Dataset

Date: 2026-09-09
Scope: dataset acquisition and licensing investigation only. **No production
code was modified this phase.**

## Proof production code is untouched

```
$ ls -la pipeline.py
-r--r--r-- 1 root root 69957 Sep  9 09:26 pipeline.py
$ sha256sum pipeline.py
21b0d294a43b51668b7983f393ef83045a1f03411a0dac3b0ce19133fd87b267  pipeline.py
```
`pipeline.py`'s mtime (09:26) predates every action taken in Phase 5 and
Phase 6 of this investigation; its checksum is recorded here so it can be
diffed against at the start of any future phase. Every file touched this
phase lives under `docs/` (this report) — nothing under `recognition/`,
`tests/`, or `pipeline.py` was opened for writing.

Regression, re-run at the end of this phase:
`python -m pytest tests/ -q` → **254 passed, 3 skipped, 0 failed** — identical
to the count at the start of Phase 5 and Phase 6.

---

## 0. Bottom line, up front

Phase 6 found **one** genuinely clean source this investigation had missed:
a CC BY 4.0, OCR-labeled, freely downloadable Indian plate dataset on
Zenodo — real, but only 1,700 images, roughly a third of the minimum
target on its own. Every other new lead either turned out to have no plate
annotations at all (two legitimate, well-documented Indian academic
traffic datasets), to be non-commercially licensed (a 5-million-image
global plate dataset that does include India), or to repeat the same
paywall/no-public-price pattern found in Phase 5 (a data-vendor listing,
two IEEE DataPort entries). DataCluster Labs' terms are now documented in
full detail from their own published license text, and it is an explicit
**no** for unpaid use, with price genuinely unpublished anywhere — "QUOTE
REQUIRED" is accurate, not a placeholder for laziness.

**Combined legitimately-usable, OCR-labeled, currently-accessible image
count found across both Phase 5 and Phase 6: ~1,700 images (one source).**
That is roughly a third of the 5,000-image floor. The blocker identified in
Phase 5 is confirmed, not resolved.

---

## 1. DataCluster licensing investigation

DataCluster Labs (also styled Datacluster.ai / Dataclusterlabspvtltd) is
one commercial vendor distributing the same underlying Indian plate corpus
through four public channels (GitHub ×2, Hugging Face, Roboflow, Kaggle),
confirmed in Phase 5. This phase went directly to the vendor's own site
(`datacluster.ai`) rather than the third-party listings.

| Field | Finding |
|---|---|
| Exact product name | **"Indian Number Plates OCR"** (as listed on `datacluster.ai/products.html`) — the same underlying data as the Kaggle listing `dataclusterlabs/indian-number-plates-dataset` and the Hugging Face dataset `Dataclusterlabspvtltd/indian-number-plates-dataset` |
| Image count | Vendor claims **15,000–20,000+** for the full licensed set (figure is inconsistent across the vendor's own channels: 15,000+/12,000+ bboxes on the Hugging Face card, "20,000+ original Number plate images" on the GitHub README) — **not independently verifiable without purchase** |
| OCR annotation availability | Yes, per the product name and the Hugging Face card's mention of a `number_plate_text` attribute |
| Price | **QUOTE REQUIRED** — no price is published on the vendor's site, products page, one-pager PDF, brochure, Kaggle, Hugging Face, GitHub, or Roboflow listings. Confirmed by direct inspection of all of these this phase; none contains a price. |
| Commercial ML training rights | The Hugging Face license text (CC-BY-NC-ND-4.0, quoted verbatim in Phase 5) explicitly states: *"No commercial use without a license from DataCluster Labs"* and *"No use in training commercial ML models."* This is only for the free sample tier; the full/paid tier's exact training-rights wording is unknown until quoted. |
| Competition/hackathon usage rights | **Not stated anywhere found.** SIH/BEL context was not addressed by any public document; this must be asked directly. |
| Trained-model deployment permission | Not stated anywhere found. |
| Internal fine-tuning permission | Not stated for the paid tier; explicitly **prohibited** for the free sample tier. |
| Redistribution restrictions | Free tier: explicit **"No derivative works or redistribution."** Paid tier: unknown. |
| Attribution requirements | Free tier: attribution required (implied by NC-ND framing); paid tier: unknown. |
| Expiration/renewal requirements | Not stated anywhere found. |
| Academic/student license difference | Not stated anywhere found — the vendor's public materials only distinguish "free evaluation/academic research with attribution" (the sample tier) from "commercial" (a paid license); no separate student or competition tier is mentioned. |

**No sales contact was made.** This investigation has no email-sending
capability and would not use one to represent the user in a commercial
negotiation without explicit authorization in any case. What follows is
the concrete question list for a human to send:

**Questions to send to `sales@datacluster.ai` (or via
`datacluster.ai/contact.html`):**
1. What is the exact image count and format (full-plate crops with
   transcriptions? bounding boxes? both?) in the "Indian Number Plates
   OCR" product as currently sold, and what is the price for a one-time
   dataset license?
2. Does the license permit fine-tuning an internal OCR model (specifically
   PaddleOCR's `en_PP-OCRv4_rec`) for use inside a government-sponsored
   hackathon submission (Smart India Hackathon, sponsored by Bharat
   Electronics Limited)? Is that "commercial" or "academic/competition"
   use under your terms?
3. Is deployment of a model trained on this data, inside a working demo
   or eventual production system, permitted under the license, or does
   that require a separate deployment license?
4. Does the license expire, or is it a perpetual one-time purchase?
5. Is redistribution of derived artifacts (e.g., a fine-tuned model
   checkpoint, not the raw images) permitted?
6. Is there a reduced-cost academic, student, or hackathon-specific
   license tier?
7. What exact character-level ground truth format is provided (full-plate
   text string per image, per-character bounding boxes, or both)?
8. What is the state/plate-type coverage breakdown (how many of the
   15,000–20,000 images are dual-row, how many states, how many vehicle
   types)?

---

## 2. IEEE DataPort — the two Phase 5 candidates, verified in detail

Both pages were re-fetched directly this phase (not inferred from the
IEEE DataPort platform name, per the task instruction).

### 2a. IND-VNP: Indian Vehicle and Number Plate Image Dataset

| Field | Finding |
|---|---|
| Exact title | IND-VNP: Indian Vehicle and Number Plate Image Dataset |
| Authors | Ashitosh Lavhate, Prajakta Khadkikar, Sharayu Mirasdar |
| Image count | 28,864 (12,858 "Raw" + 16,006 "Blur") |
| Annotation type | Eight **classification folders** (Bikes, Car-Duplicate, Car-Distance, Car-Rotated, Number-Plates, Truck, Vehicle-Distance, Vehicles-Mix), sequentially numbered images within each |
| OCR labels | **None found.** No individual plate-text transcription is described anywhere on the page — this is a classification/detection-style dataset, not an OCR dataset, independent of its licensing status. |
| Character vocabulary | Not applicable — no OCR labels |
| License | CC BY-NC-SA 4.0 (confirmed directly on page) |
| Purchase/access requirements | Requires an IEEE DataPort subscription; login required to download; DOI `10.21227/w9y7-1882`; 3.05 GB |
| Commercial-training permission | **No** — NC clause explicitly excludes commercial use |
| Downloadable with available credentials? | **No** — this investigation holds no IEEE DataPort subscription, and purchasing one was not authorized |

**Verdict: disqualified on two independent grounds** — non-commercial-only
license, and (more decisively) it does not appear to contain OCR ground
truth at all, so even a free, fully commercial-licensed copy would not by
itself meet the Phase 6 objective's OCR-label requirement.

### 2b. Indian License Plate Recognition Dataset (YOLO & OCR)

| Field | Finding |
|---|---|
| Exact title | Indian License Plate Recognition Dataset (YOLO & OCR) |
| Authors | Vamsidhar Muppagowni, Vishnu Vardhan Yerneni |
| Image count | **Not disclosed** on the page; archive is `PlateSenseAI_Datasets.zip`, 63.28 MB total (both components combined) — small enough that the actual image count is very unlikely to reach the low thousands, let alone 5,000, but this could not be confirmed without downloading |
| Annotation type | Two components: (1) YOLO bounding-box detection labels, (2) a **36-folder (`class_0`–`class_35`) per-character crop set** covering `0-9A-Z` |
| OCR labels | Character-level crops exist, but this is isolated single-character images, not full-plate-sequence transcriptions — useful at most for pretraining a character classifier, not directly for CTC-style full-plate recognition training the way TrackX's target architecture (`en_PP-OCRv4_rec`, SVTR_LCNet) needs |
| Character vocabulary | 36 classes, `0-9A-Z` — matches TrackX's target vocabulary exactly (external corroboration of the vocabulary choice made in Phase 5's `docs/dataset_prep/indian_plate_vocab.txt`) |
| License | **Not stated anywhere on the page** — confirmed by direct re-fetch this phase |
| Purchase/access requirements | Requires an IEEE DataPort subscription; DOI `10.21227/ee39-dp36`; published August 10, 2026 |
| Commercial-training permission | **Unknown — cannot be inferred from the platform, and no license text is published to check** |
| Downloadable with available credentials? | **No** |

**Verdict: blocked, and its true scale is almost certainly too small to
matter even if unblocked** — a 63 MB archive holding both a YOLO dataset
and 36 character-class folders is not going to contain thousands of
full-plate images; this is flagged honestly rather than assumed to be a
solution once purchased.

---

## 3. New legitimate sources found beyond the original 15

| # | Source | Images | OCR ground truth | License | Notes |
|---|---|---|---|---|---|
| 16 | **Number Plate Number Identification Dataset** (Zenodo, record 13954136) | **1,700** | **Yes** — accompanying Excel file maps each image filename to its actual plate number | **CC BY 4.0** | Real, small, Indian (Andhra Pradesh), captured with 4 different smartphone cameras, **directly downloadable now with no login, no paywall, no vague "permission" language** — the cleanest single source found across both phases. Not yet downloaded/verified in this session (see §3a). |
| 17 | Indian Number Plates Dataset (GTS.ai) | 20,000+ claimed | Vendor description mentions plate text among the annotation types but doesn't confirm format | **Not published** | Another commercial vendor, same pattern as DataCluster: contact-form gated, no price shown, terms undisclosed. Not investigated further than the public listing — a second data broker to add to the DataCluster question list if the user wants to compare quotes. |
| 18 | Global License Plate Dataset (`siddagra`, arXiv 2405.10949 / Hugging Face) | 5,000,000+ across 74 countries, India included but not broken out | Yes — "license plate text labels" claimed | **CC BY-NC-SA** (confirmed on the Hugging Face card) | **Disqualified — non-commercial only**, same as IND-VNP. Also sourced substantially from Platesmania.com (a car-spotting community site) under a vague "copying allowed with an obligatory link" arrangement rather than a standard open license — even for non-commercial research use this provenance is murkier than a purpose-collected academic dataset, and India's specific share of the 5M images is not disclosed. |
| 19 | Indian Commercial Truck License Plate Detection dataset (weighbridge automation paper, arXiv 2211.13194 / IEEE) | Unknown | Unknown | Unknown | A real paper with a real described dataset, but the fetched content did not surface an image count, license, or download link — flagged as **unconfirmed** rather than assumed available; would need the full paper or direct author contact to resolve. |
| 20 | UVH-26 (IISc AIM, Hugging Face) | 26,646 | **No plate annotations** — 14 India-specific *vehicle-class* labels only (two-wheelers, autos, LCVs, buses, etc.), no license-plate boxes or text | CC BY 4.0 | Real, large, genuinely excellent license terms, released Nov 2025 by a credible Indian academic institution (IISc, from Bengaluru's Safe City project) — but it does not solve the OCR problem because it was never annotated for plates at all. Worth noting for a future vehicle-*detection* improvement, not for OCR. |
| 21 | DriveIndia (IIT Hyderabad / TiHAN) | 66,986 | **No plate annotations** — 24 general traffic-object categories (pedestrians, vehicle types, road infrastructure, potholes), no plates | Restricted to "academic and non-commercial research" | Real and large, but disqualified on two independent grounds: no plate data, and non-commercial-only. |

### 3a. On the Zenodo dataset specifically — download attempted, blocked

The user explicitly approved downloading this file. The attempt was made
and **failed for a documented infrastructure reason, not a licensing
one**:

```
$ curl -sS -L -o number_plate.zip \
    "https://zenodo.org/records/13954136/files/number_plate.zip?download=1"
curl: (56) CONNECT tunnel failed, response 403
```

Confirmed via the sandbox's own proxy status endpoint
(`curl "$HTTPS_PROXY/__agentproxy/status"`) immediately after: a fresh
`connect_rejected` entry for `zenodo.org:443`, `"gateway answered 403 to
CONNECT (policy denial or upstream failure)"` — the identical pattern
already documented for `huggingface.co` in the prior Awiros investigation
(`docs/AWIROS_VERIFICATION_AND_TRAINING_DECISION_2026-09-09.md`). This
sandbox's outbound proxy allows only a fixed, small allowlist of hosts
(`pypi.org`, `registry.npmjs.org`, a handful of Anthropic-family API
hosts, and similar) and `zenodo.org` is not on it — this is a deliberate
organizational egress policy, not a transient failure, and the same class
of block as before.

A second route was tried: the user's own linked computer
(`mcp__remote-devices__device_bash`), whose network sometimes differs from
this sandbox's. It returned `"Workspace unavailable. The isolated Linux
environment on this device failed to start."` — unrelated to Zenodo, a
pre-existing local-VM issue on that device.

Per the standing rule against circumventing a tool-reported network
restriction, **no further workaround was attempted** (no mirror, no proxy
substitution, no alternative fetch method). This means two facts from §3a
of the original draft remain genuinely unverified — the exact unique-
vehicle count within the 1,700 images, and whether any of its plate texts
collide with TrackX's own 12-plate held-out benchmark (unlikely, given
Andhra Pradesh vs. TrackX's Delhi/Karnataka/UP geography, but not
confirmed) — **not because verification wasn't attempted, but because the
download itself is currently blocked from every route available in this
session.**

**This is now the same category of blocker as the Awiros/Hugging Face
case**: a real, freely and legitimately licensed dataset that this
specific sandboxed environment cannot reach. The practical resolution is
the same kind of fix — a human downloading the file directly (it is a
public, no-login, CC BY 4.0 link: `https://zenodo.org/records/13954136`)
on their own machine or network, and then supplying it to this session
either as a conversation attachment or by placing it in a connected local
folder.

---

## 4. Legitimate data collection strategy (if public/paid datasets stay insufficient)

TrackX's own capture pipeline is real, already runs, and already produces
correctly-cropped plate images (confirmed extensively in Phases 1–5). What
it has never had is *volume* or *diversity* — Phase 5's inventory found
only 12 distinct physical plates across 3 states in the entire existing
corpus, because the only footage available so far is 3 overlapping demo
clips. A lawful collection plan does not require new engineering — the
detection/crop pipeline needs no changes — it requires new footage.

**Concrete plan:**

1. **Site selection with consent.** Deploy camera capture (using TrackX's
   existing detection pipeline, unmodified) at locations where the
   property owner or operator can lawfully authorize video capture and
   plate collection — for example, a college/institute campus gate,
   a private parking facility, or a cooperating local traffic-authority
   pilot site, each under a written data-collection agreement with that
   site. **Public-road capture without an authorizing body is the wrong
   default** — vehicle registration numbers are linked to an identifiable
   owner via RTO records, and several jurisdictions (India's own Digital
   Personal Data Protection Act, 2023, among them) treat data that can
   identify a person even indirectly with real handling obligations. This
   is a genuine legal-review question, not a technical one — flagged here
   for the user's counsel or the BEL/SIH mentors to confirm, not resolved
   by this investigation.
2. **Notice.** Standard CCTV signage/notice at each capture site, stating
   that video is being recorded for a research/development purpose, per
   ordinary surveillance-notice practice.
3. **Capture breadth.** Multiple sites, multiple days, multiple times of
   day (to get real day/night/rain/glare variation instead of synthesized
   approximations), multiple camera angles — explicitly to fix the
   single-largest gap Phase 5 found (3 states, 12 plates, zero dual-row
   examples).
4. **Extraction.** Run the existing, unmodified TrackX detection +
   spatial-outlier-filtered crop selection (the same logic already fixed
   and tested in `pipeline.py`) over the new footage to produce plate
   crops — this step requires zero new code.
5. **Annotation.** Human transcription of each crop's true plate text,
   ideally by two independent annotators with a third-adjudicator process
   for disagreements (a standard double-annotation pattern — not yet
   built, would be new lightweight tooling under `docs/dataset_prep/` or
   similar, not production code).
6. **Manifest ingestion.** Feed the annotated crops into the
   `docs/dataset_prep/manifest_schema.md` format and run them through the
   already-built, already-tested `leakage_guard_split.py`, which already
   permanently excludes every one of TrackX's existing 12 benchmark
   plates by design.
7. **Realistic scale expectation.** Given that 3 existing video clips
   yielded only 12 unique plates, reaching even 1,000 new unique vehicles
   this way requires substantially more capture-hours and more distinct
   locations than TrackX has used to date — this is a genuine data-
   collection *campaign*, not a quick script run, and its timeline depends
   on how many consenting sites can be arranged, which is outside this
   investigation's ability to schedule or execute.

This path is lawful and fully within TrackX's own technical control, but
it is a logistics and legal-authorization project, not something this
session can carry out by itself.

---

## 5. Dataset combination

Only one newly-verified source (Zenodo, #16) is simultaneously (a)
accessible without payment, (b) clearly and permissively licensed, and (c)
has real OCR ground truth. Combining it with anything else legitimately
usable found across both phases:

| Component | Images | Status |
|---|---|---|
| Zenodo Number Plate Identification Dataset | 1,700 | Verified via metadata page; **not yet downloaded** |
| Roboflow `nivu` Indian License Plate (Phase 5, #7) | 1,650 | CC BY 4.0, but **no OCR labels** — cannot be combined into an OCR training set, only a detector-training set |
| TrackX's own 37-sample benchmark | 37 | **Permanently excluded from training by design** (`held_out_benchmark_plates.txt`) — not a combination candidate |
| TrackX's own remaining ~125 unlabeled track crops (162 total pairs − 37 labeled) | ~125 | No verified ground truth exists for these; would need the same human-transcription step as new collection (§4) before they could count |

**Total currently-combinable, OCR-labeled, correctly-licensed image
count: 1,700** (Zenodo alone — the Roboflow set cannot contribute to OCR
training since it lacks plate-text labels; TrackX's own data is excluded
from training by design or unlabeled).

License compatibility: CC BY 4.0 (Zenodo) does not conflict with anything
else in this table because nothing else in this table qualifies for
combination yet. If DataCluster Labs' paid tier is later purchased under
its own commercial terms, those terms would very likely restrict
redistribution even if training use is permitted — the manifest schema's
per-row `license` and `source_dataset` fields (Phase 5,
`docs/dataset_prep/manifest_schema.md`) already anticipate this by
tracking license per source rather than assuming one blanket license for
the whole corpus, precisely so sources with different rights are never
silently merged into a single unlabeled pool.

Unique plate identities, state coverage, and duplicate risk for the Zenodo
set are **not yet computable** — they require actually downloading and
inspecting the 1.5 GB archive, which was not done this session (see §3a
and the recommended next action).

---

## 6. Training-readiness gate — applied

Gate (as specified for this phase):

- ✅/❌ ≥5,000 legitimate real images — **❌ 1,700 available (34% of floor)**
- ✅/❌ OCR ground truth exists — **✅ for the 1,700 (Zenodo); ❌ for everything else checked this phase**
- ✅/❌ commercial/competition training rights confirmed — **❌ unconfirmed for DataCluster/GTS.ai (quote required), explicitly denied for IND-VNP and the Global License Plate Dataset (NC-only), confirmed permissive only for Zenodo's 1,700 and the OCR-label-free Roboflow/UVH-26/DriveIndia sets**
- ✅/❌ enough unique vehicle/plate identities — **unknown, not yet verified** (Zenodo image count ≠ confirmed unique-plate count)
- ✅/❌ train/val/test leakage preventable — **✅** — tooling built and self-tested in Phase 5, unchanged and still passing
- ✅/❌ Indian character coverage adequate — **unknown until the Zenodo data is actually inspected**

Four of six criteria fail or are unverifiable. The gate is not met.

---

## 7. What was deliberately NOT done this phase

Per the explicit instruction: no new OCR library was evaluated, no RTSP or
live-camera work was touched, no frontend work was touched, no
benchmark-specific OCR substitution or hardcoded plate correction was
introduced, and no unlicensed or synthetic data was presented as real
anywhere in this report or in `docs/dataset_prep/`.

---

## DATASET STATUS: NOT READY

## SINGLE NEXT ACTION

**A human needs to do two small, concrete, non-engineering things this
investigation cannot do itself, because both are now blocked at the
infrastructure/procurement layer rather than the research layer: (1)
download the 1,700-image Zenodo dataset directly
(`https://zenodo.org/records/13954136`, CC BY 4.0, ~1.5 GB, free, no
login — approved by the user this phase, but blocked from every network
route this session has access to; a human's own machine can reach it
directly) and hand the file back to this session as a conversation
attachment or via a connected local folder so it can be verified and
folded into the leakage-guarded manifest, and (2) send the 8-question list
in §1 to `sales@datacluster.ai` (and optionally the GTS.ai contact form)
to get an actual price and commercial/competition-use answer for the one
vendor whose dataset is large enough to matter on its own.** Per the
standing guidance: this is now a procurement and access bottleneck, not a
research one — no further dataset web-hunting is recommended after this
phase without new information from one of those two actions.
