# TrackX Model Weights

This directory contains (or references) model weights for the TrackX vehicle
intelligence system. All numbers below are either verified this session
(dated) or explicitly marked unverified - nothing here is a target dressed
up as a measurement. See `docs/CLAUDE_PHASE0_AUDIT.md` for the full history
of why this file used to contradict itself.

## Plate detector

- **`best.onnx`**: present in this directory, loads successfully via
  `ultralytics.YOLO("models/best.onnx", task="detect")`, reports a single
  class `{0: 'license_plate'}`. This is the detector actually used today
  (`demo/visual_pipeline.py`, `backend/app/core/config.py`, `pipeline.py`
  all resolve to it automatically - see `find_plate_weights()` /
  `_resolve_plate_weights()`). Verified by loading it, not by a training
  log; no mAP/confidence numbers are reported here because none have been
  independently measured against a held-out set in this checkout.
- **`best_plate_detector.pt`**: NOT present in this checkout (`.gitignore`
  excludes `models/*.pt`). Earlier versions of this file claimed it was
  "✅ INCLUDED and ready for production use" - that was false; `best.onnx`
  above is the real, working fallback and needs no `.pt` file to function.

## OCR

- **`lprnet_indian.pth`**: NOT present in this checkout, and has no public
  download - the code names its exact intended source
  (`sanchit2843/Indian_LPR`, arXiv:2111.06054), which has never published
  this checkpoint. `recognition/lprnet_ocr.py` deliberately refuses to load
  with random weights (it will not silently emit garbage reads), so LPRNet
  stays unavailable until a real trained checkpoint exists - either that
  project publishes one, or it's trained from scratch on a real labeled
  Indian-plate OCR dataset.
- **PaddleOCR (`lang="en"`)** is the fallback `recognition/ocr_reader.py`
  uses when LPRNet isn't available, and as of **2026-09-07 it is verified
  working end-to-end on this machine**: this machine's `~/.paddleocr/whl/`
  already has the `en` detection/recognition/angle-classification models
  cached from a prior run, so `PaddleOCR(use_angle_cls=True, lang="en")`
  constructs with **no network access required**. Verified by actually
  constructing it and reading a rendered plate image
  (`"TN38AB1234"`, clean and mildly degraded/blurred) through the real
  `recognition.ocr_reader.PlateOCR` class - both reads were exact-text
  matches. See `integration_tests/test_ocr_smoke.py`, which repeats this
  check deterministically (skips cleanly, doesn't fail, on a machine
  without the cache and without network to build it).
- A real bug was found and fixed the same day: both PaddleOCR code paths in
  `_read_paddleocr()` called an undefined function
  (`validate_indian_plate_format`), so **every PaddleOCR-backed OCR read
  raised `NameError` before this fix** - the fallback path had never
  actually been exercised end-to-end before. Fixed by using the
  already-imported `recognition.plate_normalizer.normalize_indian_plate()`
  instead, which is strictly more capable (it also strips the "IND"
  country-marker artifact and corrects OCR-confusable characters).
- **No exact-match / character-accuracy percentage is reported here.** The
  previous version of this file claimed "72.4% exact-match, 81.1% character
  accuracy (551 Indian plate samples)" - there is no dataset, script, or log
  in this repository that produced that number, so it has been removed
  rather than repeated. A real accuracy benchmark needs a real, labeled set
  of Indian plate images (or video), which this checkout does not have (see
  `docs/CLAUDE_PHASE0_AUDIT.md`).
- **A machine without this cache**, or a from-scratch clone, will need
  network access to `bj.bcebos.com` (PaddleOCR's own model CDN) the first
  time `PlateOCR()` is constructed - `recognition/ocr_reader.py`'s
  `try_init_ocr()` catches that failure (including PaddleOCR's own
  `sys.exit()` on a failed download) and degrades to "OCR unavailable"
  rather than crashing the process.

## Plate detector training (from scratch)

```bash
python -m detection.train_yolo --data /path/to/dataset/data.yaml
```
Output goes to `detection/runs/detect/plate_train/weights/best.pt`, which
`find_plate_weights()` / `_resolve_plate_weights()` will pick up
automatically ahead of `best.onnx`.

## LPRNet training (from scratch)

```bash
python recognition/train_lprnet.py --train_data data/indian_plates/ --epochs 50
```
Needs a real labeled Indian-plate dataset first - see
`docs/CLAUDE_PHASE0_AUDIT.md` for what was and wasn't found this session.

## Notes

- Do not commit trained weights containing sensitive/private training data.
- GPU is recommended for training, not required for inference.
- `models/*.pt` and `models/*.pth` are gitignored on purpose - weight files
  are distributed out-of-band, not through this repo.

## Troubleshooting

### "Model not found" / plate detection not working
1. Confirm `models/best.onnx` exists in this directory.
2. Check `find_plate_weights()` (`demo/visual_pipeline.py`) resolves it -
   run `python -c "from demo.visual_pipeline import find_plate_weights; print(find_plate_weights())"`.

### OCR reports "unavailable"
1. Check `pip show paddleocr paddlepaddle` - install per `requirements.txt`
   if missing.
2. If installed but still unavailable, PaddleOCR likely needs to download
   its `en` models once and has no network access. Check for an existing
   cache at `~/.paddleocr/whl/{det,rec,cls}/...` first (see above) - if it's
   there, construction should succeed offline.
3. Run `python -m pytest integration_tests/test_ocr_smoke.py -v` for a
   direct, real pass/fail/skip answer instead of guessing.

### Inference slowness
1. `best.onnx` is already the faster-inference option versus a `.pt` file.
2. Check GPU availability for acceleration.
3. Consider batch processing for multiple images.
