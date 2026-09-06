"""Temporary diagnostic: measure LPRNet engine accuracy on the clean 551-sample eval set."""
import json
import time

import cv2

from recognition.lprnet_ocr import try_init_lprnet

with open("data/ocr_eval/clean_evaluation_dataset.json", encoding="utf-8") as f:
    data = json.load(f)
entries = data.get("entries", [])
print("total entries:", len(entries))

ocr = try_init_lprnet("models/lprnet_indian.pth")
assert ocr is not None, "LPRNet engine failed to load"

def _clean(s):
    return "".join(c for c in (s or "").upper() if c.isalnum())

exact = 0
char_acc_sum = 0.0
counted = 0
no_read = 0
results = []
t0 = time.time()
for i, e in enumerate(entries):
    img_path = e.get("image_path")
    gt = _clean(e.get("ground_truth"))
    img = cv2.imread(img_path)
    if img is None:
        no_read += 1
        continue
    text, conf = ocr.read_plate(img)
    pred = _clean(text)
    if not gt or not pred:
        counted += 1
        results.append((gt, pred, 0.0))
        continue
    if pred == gt:
        exact += 1
    n = max(len(gt), len(pred))
    match = sum(1 for a, b in zip(pred, gt) if a == b) / n if n else 0.0
    char_acc_sum += match
    counted += 1
    results.append((gt, pred, round(match, 2)))
elapsed = time.time() - t0

n = counted
lines = [
    "samples: %d" % n,
    "unreadable_images: %d" % no_read,
    "exact_matches: %d" % exact,
    "exact_match_accuracy: %.4f" % (exact / n if n else 0),
    "character_accuracy: %.4f" % (char_acc_sum / n if n else 0),
    "elapsed_seconds: %.1f" % elapsed,
    "ms_per_image: %.1f" % (elapsed * 1000 / n if n else 0),
]
lines.append("sample_results(first 15):")
for r in results[:15]:
    lines.append("  gt=%s pred=%s char=%.2f" % r)
open("_lpr_eval.txt", "w", encoding="utf-8").write("\n".join(lines))
print("DONE")
