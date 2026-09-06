"""Best-of-N preprocessing variants for LPRNet on the authoritative benchmark.

Tries a small set of adaptive pre-processing variants per crop and keeps the
highest-quality candidate: format-valid reads are preferred, then higher
confidence. Pure inference-time change - no retraining, no GT access.
"""
import json, os, re, sys, time
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath("."))
from recognition.lprnet_ocr import try_init_lprnet

BENCH = json.load(open("data/ocr_eval/authoritative_benchmark.json", encoding="utf-8"))
ENTRIES = BENCH["entries"]
CROP = "data/ocr_eval/plate_crops_external"

def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper()) if s else ""

def variants(img):
    out = [("orig", img)]
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if h < 60:
        out.append(("2x", cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)))
        out.append(("3x", cv2.resize(img, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)))
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    out.append(("clahe", cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR)))
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 11, 2)
    out.append(("thresh", cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)))
    return out

def fmt_ok(s):
    return bool(re.fullmatch(r"[A-Z]{2}\d{1,3}[A-Z]{1,3}\d{3,4}", s or ""))

def main():
    ocr = try_init_lprnet("models/lprnet_indian.pth")
    rows = []
    t0 = time.time()
    exact = 0
    for i, e in enumerate(ENTRIES):
        img = cv2.imread(os.path.join(CROP, e["filename"]))
        if img is None:
            continue
        best = None
        for name, v in variants(img):
            text, conf = ocr.read_plate(v)
            textn = norm(text)
            if not textn:
                continue
            key = (fmt_ok(textn), round(conf, 3), name)
            if best is None or key > best[0]:
                best = (key, textn, conf)
        pred = best[1] if best else None
        ok = pred == e["ground_truth"]
        exact += ok
        rows.append({"file": e["filename"], "gt": e["ground_truth"],
                     "pred": pred, "ok": ok, "conf": best[2] if best else 0.0})
        if (i + 1) % 250 == 0:
            print(i + 1, round(time.time() - t0))
    n = len(rows)
    print(f"n={n} exact={exact} ({exact/n*100:.1f}%) t={time.time()-t0:.0f}s")
    json.dump({"engine": "lprnet_variants", "rows": rows},
              open("outputs/ocr_baseline_lprnet_variants.json", "w"), indent=1)

if __name__ == "__main__":
    main()
