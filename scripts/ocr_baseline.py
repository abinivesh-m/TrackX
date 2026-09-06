"""Reproduce genuine OCR baselines: LPRNet (torch) over all physical crops.

Resolves JSON path entries against the actual on-disk crop folders (the JSONs
contain stale machine-specific OneDrive absolute paths), so results are real.
"""
import json, os, glob, re, sys, time, argparse
import cv2
import numpy as np
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath("."))

CROP_DIRS = [
    "data/ocr_eval/plate_crops_external",
    "data/ocr_eval/plate_crops_additional",
    "data/ocr_eval/huggingface_import/images",
]

def resolve(base):
    if os.path.exists(base):
        return base
    for d in CROP_DIRS:
        p = os.path.join(d, os.path.basename(base))
        if os.path.exists(p):
            return p
    return None


def normalize_gt(gt):
    return re.sub(r"[^A-Z0-9]", "", str(gt).upper())


def load_lprnet():
    from recognition.lprnet_ocr import try_init_lprnet
    ocr = try_init_lprnet("models/lprnet_indian.pth")
    return ocr

def load_paddle():
    # PaddleOCR in py3.11 env only
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return ocr


def lprnet_read(ocr, img):
    text, conf = ocr.read_plate(img)
    return text, conf


def paddle_read(ocr, img):
    res = ocr.ocr(img, cls=True)
    if not res or not res[0]:
        return None, 0.0
    texts, confs = [], []
    for line in res[0]:
        texts.append(line[1][0])
        confs.append(line[1][1])
    text = re.sub(r"[^A-Z0-9]", "", "".join(texts).upper())
    return text or None, (sum(confs)/len(confs) if confs else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="lprnet", choices=["lprnet", "paddle"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    datasets = {
        "precropped_737": "data/ocr_eval/precropped_dataset.json",
        "video_654": "data/ocr_eval/video_dataset.json",
        "clean551": "data/ocr_eval/clean_evaluation_dataset.json",
    }
    # build filename -> gt map per dataset
    seen = {}
    for name, path in datasets.items():
        d = json.load(open(path, encoding="utf-8"))
        entries = d["entries"] if isinstance(d, dict) else d
        for e in entries:
            gt = normalize_gt(e.get("ground_truth"))
            base = os.path.basename(e.get("image_path", ""))
            if base and gt and base not in seen:
                seen[base] = {"gt": gt, "ds": name, "src": e.get("source")}

    files = sorted(seen.keys())
    print(f"engine={args.engine} unique crops={len(files)}")
    if args.limit:
        files = files[:args.limit]

    if args.engine == "lprnet":
        ocr = load_lprnet()
        read = lambda img: lprnet_read(ocr, img)
    else:
        ocr = load_paddle()
        read = lambda img: paddle_read(ocr, img)

    results = defaultdict(list)
    t0 = time.time()
    exact = 0
    nores = 0
    rows = []
    for i, base in enumerate(files):
        path = resolve(base)
        if not path:
            continue
        img = cv2.imread(path)
        if img is None:
            continue
        pred, conf = read(img)
        info = seen[base]
        predn = normalize_gt(pred) if pred else None
        ok = predn == info["gt"]
        exact += ok
        if predn is None:
            nores += 1
        rows.append((base, info["gt"], predn, conf, ok, info["ds"]))
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(files)} elapsed={time.time()-t0:.0f}s")
    dt = time.time() - t0
    print(f"\nTOTAL n={len(rows)} exact={exact} ({exact/len(rows)*100:.1f}%) no-result={nores} ({nores/len(rows)*100:.1f}%) elapsed={dt:.0f}s")
    per = defaultdict(lambda: [0, 0])
    for r in rows:
        per[r[5]][1] += 1
        if r[4]:
            per[r[5]][0] += 1
    for ds, (e, n) in sorted(per.items()):
        print(f"  {ds}: n={n} exact={e} ({e/n*100:.1f}%)")
    # save raw rows for error analysis
    out = f"outputs/ocr_baseline_{args.engine}.json"
    os.makedirs("outputs", exist_ok=True)
    json.dump({"engine": args.engine, "rows": [{"file": r[0], "gt": r[1], "pred": r[2], "conf": r[3], "ok": r[4], "ds": r[5]} for r in rows]},
              open(out, "w", encoding="utf-8"), indent=1)
    print("saved", out)


if __name__ == "__main__":
    main()
