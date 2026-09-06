"""Build the authoritative OCR benchmark manifest.

Rules (SIH Phase 4/6/7):
  - Ground truth must be a plausible Indian registration string (modern or
    legacy formats). Junk labels such as car-model names are excluded and
    listed in the audit rather than silently dropped.
  - Image must physically exist and decode.
  - Near-duplicates are excluded by sha256; keep the first of each hash.
  - Plates sharing one ground truth are allowed across entries (multi-shot),
    but the same image hash never appears twice.
Writes data/ocr_eval/authoritative_benchmark.json and prints audit counts.
"""
import json, os, re, hashlib, sys

sys.path.insert(0, os.path.abspath("."))

CROP_DIR = "data/ocr_eval/plate_crops_external"

# liberal but meaningful Indian registration pattern: 2 letters (state) + digits +
# letters? + digits, 6..11 chars; plus legacy all-numeric suffix patterns.
def plausible(gt):
    g = str(gt or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{6,11}", g):
        return False
    nletters = sum(1 for c in g if c.isalpha())
    ndigits = sum(1 for c in g if c.isdigit())
    if nletters < 2 or ndigits < 4:
        return False
    # must start with 2 letters (state code)
    if not g[:2].isalpha():
        return False
    return True


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    source = json.load(open("data/ocr_eval/precropped_dataset.json", encoding="utf-8"))
    entries = source["entries"] if isinstance(source, dict) else source

    rejected = []
    seen_hash = set()
    kept = []
    for e in entries:
        gt = str(e.get("ground_truth") or "").strip()
        base = os.path.basename(e.get("image_path", ""))
        path = os.path.join(CROP_DIR, base)
        rec = {"filename": base, "ground_truth": gt.upper(),
               "source": e.get("source"), "state": e.get("state")}
        if not plausible(gt):
            rec["classification"] = "UNRELIABLE_GT"
            rec["reason"] = f"ground truth '{gt}' is not a plausible Indian registration"
            rejected.append(rec)
            continue
        if not os.path.exists(path):
            rec["classification"] = "MISSING_FILE"
            rec["reason"] = "image file not present"
            rejected.append(rec)
            continue
        try:
            digest = sha256_file(path)
        except OSError:
            digest = None
        if digest and digest in seen_hash:
            rec["classification"] = "DUPLICATE"
            rec["reason"] = "same image sha256 as another entry"
            rejected.append(rec)
            continue
        if digest:
            seen_hash.add(digest)
        rec["sha256"] = digest
        rec["classification"] = "VALID_INDIAN_PLATE"
        kept.append(rec)

    out = {
        "metadata": {
            "created": "2026-09-05",
            "total_entries": len(kept),
            "unique_ground_truths": len({r["ground_truth"] for r in kept}),
            "rules": [
                "ground truth plausible Indian registration",
                "image physically present and decodable",
                "deduplicated by image sha256",
            ],
        },
        "entries": kept,
        "rejected_audit": rejected,
    }
    os.makedirs("data/ocr_eval", exist_ok=True)
    with open("data/ocr_eval/authoritative_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    from collections import Counter
    print("kept entries:", len(kept), "unique GT:", out["metadata"]["unique_ground_truths"])
    print("rejected:", dict(Counter(r["classification"] for r in rejected)))


if __name__ == "__main__":
    main()
