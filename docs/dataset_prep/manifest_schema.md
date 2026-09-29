# TrackX Indian-Plate OCR Training Manifest Schema

Status: **specification only — no real data has been collected yet.** This
file defines the format a future licensed dataset must be converted into
before `leakage_guard_split.py` or any fine-tuning run can use it. Nothing
here contains or references real training images.

## 1. Source manifest (per licensed dataset, before splitting)

One row per plate crop, tab-separated, UTF-8, no header (matches
PaddleOCR's native recognition-training format so the existing
`en_PP-OCRv4_rec` fine-tuning tooling can consume it directly):

```
<relative_image_path>\t<plate_text>
```

Example (illustrative only — not real data):

```
images/0001.jpg	KA05HF1234
images/0002.jpg	MH12DE3456
```

## 2. Extended metadata manifest (JSON Lines, one object per crop)

Used for dataset-statistics reporting, deduplication, and the leakage-safe
split. Required fields:

| field | type | notes |
|---|---|---|
| `image_path` | string | relative path to the crop |
| `plate_text` | string | ground-truth transcription, `0-9A-Z` only |
| `physical_plate_id` | string | a stable identifier for the physical vehicle/plate — **not** the image filename. Two crops of the same real plate (even under different lighting/angle) MUST share this id so the split can group by vehicle identity rather than by image. When the source dataset gives no vehicle id, `plate_text` itself is used as a conservative proxy (documented, not fabricated — see note below). |
| `state_prefix` | string | first 2 letters, e.g. `KA`, `UP`, `DL` |
| `vehicle_type` | string | car / motorcycle / truck / bus / auto / unknown |
| `plate_rows` | int | 1 (single-row) or 2 (dual-row) |
| `plate_position` | string | front / rear / unknown |
| `image_width`, `image_height` | int | pixels |
| `source_dataset` | string | which licensed source this row came from |
| `license` | string | the exact license tag that source was released under |
| `capture_context` | string | day / night / rain / cctv / handheld / unknown, where stated by the source |

**Proxy-identity caveat**: using `plate_text` as a stand-in for
`physical_plate_id` is a real limitation, not a shortcut — if a source
dataset does not track which images share a physical vehicle, grouping by
transcribed text is the only leakage-safe option available (it is strictly
more conservative than grouping by image, since it also catches repeat
sightings of the same vehicle). It must never be silently assumed accurate;
each dataset entry in the final report states whether real vehicle-level
identity was available or this proxy was required.

## 3. Split output

Three files, same JSONL schema as above, with disjoint `physical_plate_id`
sets and disjoint `plate_text` sets:

- `train_manifest.jsonl`
- `val_manifest.jsonl`
- `test_manifest.jsonl` (a held-out slice of the *newly acquired* training
  data, distinct from and in addition to TrackX's existing 37-sample
  benchmark — that benchmark is never written into any of these three
  files; see `held_out_benchmark_plates.txt`)

## 4. Vocabulary file

`indian_plate_vocab.txt` — 36 lines, one character per line, in the exact
order the CTC classifier head's output indices must map to (`0-9` then
`A-Z`). Index 0 is reserved for the CTC blank token by convention and is
not listed in the file (PaddleOCR's training code inserts it
automatically); this matches how the existing `en_dict.txt`
95-class dictionary is consumed, confirmed in Phase 3 of this
investigation (`docs/PHASE3_PLATE_SPECIFIC_OCR_INVESTIGATION_2026-09-09.md`,
section 1).

Lowercase letters and the wide symbol/punctuation block present in the
current 95-class `en_dict.txt` are intentionally absent — Indian
registration plates use `0-9A-Z` exclusively, and Part B of the prior
Awiros/Training report identified this narrower vocabulary as more
restrictive (and therefore a better fit) than Awiros's own 63-class
vocabulary (`0-9A-Za-z` + space).
