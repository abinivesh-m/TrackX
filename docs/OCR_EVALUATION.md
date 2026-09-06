# TrackX — Authoritative OCR Evaluation

**Status of this document:** This is the single authoritative OCR performance record for TrackX.
If another number appears anywhere else in the repo, treat it as historical unless it can be
reproduced from this benchmark configuration.

## 1. Purpose

This document reports measured OCR performance for Indian license plates in TrackX. It does **not**
claim the SIH target as achieved. The SIH PS 26127 target is **>90% exact-plate recognition**. The
measured result is below that target, and that gap is stated explicitly.

## 2. OCR architecture (current)

TrackX OCR uses:

1. Plate crop (from plate detector or vehicle-internal plate search)
2. Quality analysis
3. Adaptive preprocessing (where useful)
4. Indian LPRNet (primary engine)
5. PaddleOCR (secondary engine, where available)
6. Fusion / multi-frame voting (where multiple readings exist)
7. Indian plate normalization
8. Indian plate validation
9. Final confidence scoring

LPRNet implementation: `recognition/lprnet_ocr.py`
OCR orchestration: `recognition/ocr_reader.py`

## 3. Engines under evaluation

- **LPRNet (primary)**: `models/lprnet_indian.pth`
  - Checkpoint SHA256: `bdc17060638f01e23d9f05ad56bd9351e5a58c6bfafbe1e077330fb06fac12df`
  - Model architecture: LPRNet backbone + CTC head
  - Input: 94×24
  - Classes: 37
  - LPR_MAX_LEN: 16
  - Character set begins with digits `0-9`, then `A-Z`, and includes `-` near the end.
- **PaddleOCR (secondary)**: `paddleocr` package (auto-downloads Paddle models)
  - Not available in the current run used to produce this report; reported as 0% because it did
    not return reads.
- **Fusion**: LPRNet + PaddleOCR, with format validation and confidence weighting
  - Not available in the current run because PaddleOCR did not return reads.

## 4. Dataset

Evaluation dataset: `data/ocr_eval/test_dataset_clean.json`
Total samples: **113**

This is a clean evaluation set. The dataset should be treated as fixed for comparison across runs.
Do not remove difficult samples to improve the headline number.

**Important honesty note:** This benchmark is what was run in the current environment. It is not
necessarily the same as a 731-crop benchmark referenced elsewhere in the repo. Where multiple
benchmark sizes appear in historical reports, the authoritative one for this session is the one
actually executed and recorded here. Do not merge numbers from different datasets and present them
as one measurement.

## 5. Measured results

### LPRNet

- Exact-match accuracy: **25.66%**
- Character accuracy: **56.41%**
- Success rate (engine returned a read): **100.0%**
- Average confidence: **0.931**
- Average processing time per image: **0.6885 seconds**
- Error breakdown:
  - length_error: 40
  - substitution_error: 25
  - confusion: 19

### PaddleOCR

- Exact-match accuracy: **0%**
- Character accuracy: **0%**
- Success rate: **0%**
- Not available in this run.

### LPRNet + PaddleOCR Fusion

- Exact-match accuracy: **0%**
- Character accuracy: **0%**
- Not available in this run.

## 6. Interpretation

- LPRNet loads and runs. It is **not** producing acceptable Indian plate accuracy on this dataset
  in the current state.
- High average confidence with low exact accuracy is a known dangerous pattern: the engine can be
  confident and wrong. That is exactly why TrackX should not trust raw LPRNet output blindly and
  should fuse / validate / threshold.
- A large portion of the errors are length errors, not just substitutions. That suggests the model
  is not reliably learning the expected plate length pattern on this data in its current form.

## 7. SIH compliance statement for OCR

- **SIH target**: >90% exact-plate recognition
- **Measured LPRNet exact-match**: 25.66%
- **Compliance status**: NOT MET

This is reported honestly. Do not present this as “>90%”. If a presentation or dashboard states a
higher number, it must either:
- be clearly labeled as a target/goal, or
- be backed by a reproducible benchmark that supersedes this document.

## 8. Condition-wise accuracy

Not measured in this run as a structured table. If condition-wise numbers are needed, they must be
generated from a labeled condition split of the evaluation set and appended here. Do not invent
condition-wise percentages.

## 9. Latency

- LPRNet average processing time per image: **0.6885 seconds** (as measured in this run).
- This is an OCR-inference time on the evaluation images in this environment; it is not an
  end-to-end pipeline latency and should not be presented as such.

## 10. Reproducibility

To reproduce:

1. Use the same fixed evaluation set.
2. Initialize LPRNet from `models/lprnet_indian.pth`.
3. Run the same evaluation harness.
4. Record exact-match, character accuracy, success rate, confidence, and latency.

If any parameter changes (dataset, preprocessing, model weights, decode parameters), the report must
be regenerated and the difference noted. Do not keep old numbers circulating under the same label.

## 11. Relationship to other reports

Historical reports in this repo mention several different accuracy figures on different dataset sizes.
This document does **not** reconcile all of them into one blended number. It records the run that was
actually executed in this session. Other figures may exist; if they are to be used, they must be
reproduced and documented here with the same level of detail.
