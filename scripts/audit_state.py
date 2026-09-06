"""Temporary audit helper — summarize OCR dataset state."""
import json, os, re, collections

def load(p):
    return json.load(open(p, encoding="utf-8"))

def summarize(name):
    d = load(name)
    entries = d["entries"] if isinstance(d, dict) else d
    meta = d.get("metadata", {}) if isinstance(d, dict) else {}
    print("=" * 70)
    print("FILE:", name)
    print("metadata:", json.dumps(meta, indent=1)[:500])
    print("entries:", len(entries))
    # Path fields
    sample = entries[0] if entries else {}
    print("sample keys:", list(sample.keys()))
    # find path-like fields
    for field in ("image_path", "filename", "image", "path"):
        vals = [e.get(field) for e in entries if e.get(field)]
        if vals:
            print(f"field {field}: {len(vals)} present; first: {vals[0]!r}")
    # ground truths
    gts = [e.get("ground_truth") for e in entries if e.get("ground_truth")]
    print("ground truths:", len(gts), "unique:", len(set(gts)))
    badgt = [g for g in set(gts) if not re.fullmatch(r"[A-Z]{2}\d{1,3}[A-Z]{1,3}\d{3,4}", str(g).upper().replace(" ", ""))]
    print("nonstandard GT examples:", badgt[:10])
    # splits field
    sp = collections.Counter(e.get("split") for e in entries)
    print("split field values:", dict(sp))
    src = collections.Counter(e.get("source") for e in entries)
    print("sources:", dict(src))
    if "quality" in sample:
        q = collections.Counter(e.get("quality") for e in entries)
        print("quality:", dict(q))

for f in [
    "data/ocr_eval/clean_evaluation_dataset.json",
    "data/ocr_eval/clean_indian_plates_dataset.json",
    "data/ocr_eval/train_dataset_clean.json",
    "data/ocr_eval/validation_dataset_clean.json",
    "data/ocr_eval/test_dataset_clean.json",
    "data/ocr_eval/video_dataset.json",
    "data/ocr_eval/precropped_dataset.json",
    "data/ocr_eval/dataset_audit_manifest.json",
]:
    try:
        summarize(f)
    except Exception as e:
        print("ERR", f, e)
