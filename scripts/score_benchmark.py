"""Score saved engine rows (outputs/ocr_baseline_*.json) against the
authoritative benchmark and print exact/char metrics with a legibility split."""
import json, os, sys, glob
import cv2
from collections import Counter

BENCH = json.load(open("data/ocr_eval/authoritative_benchmark.json", encoding="utf-8"))
ENTRIES = BENCH["entries"]
GT = {e["filename"]: e["ground_truth"] for e in ENTRIES}
VALID = set(GT.keys())

def lev(a, b):
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        nd = [i]
        for j, cb in enumerate(b, 1):
            nd.append(min(dp[j] + 1, nd[-1] + 1, dp[j - 1] + (ca != cb)))
        dp = nd
    return dp[-1]

def norm(s):
    import re
    return re.sub(r"[^A-Z0-9]", "", str(s).upper()) if s else ""

def height_of(fn):
    img = cv2.imread(os.path.join("data/ocr_eval/plate_crops_external", fn))
    return img.shape[0] if img is not None else 0

def score_rows(rows):
    per = {}
    for r in rows:
        fn = r.get("file")
        if fn not in VALID:
            continue
        g = GT[fn]
        p = norm(r.get("pred"))
        per[fn] = (g, p, r.get("ok"), r.get("conf"))
    total = len(per)
    exact = sum(1 for _, p, ok, _ in per.values() if ok)
    char_ok = tot = 0
    dist = Counter()
    for g, p, _, _ in per.values():
        d = lev(g, p)
        dist[d] += 1
        m = max(len(g), len(p))
        char_ok += m - d
        tot += m
    return per, {"n": total, "exact": exact,
                 "exact_pct": round(exact / total * 100, 1) if total else 0,
                 "char_pct": round(char_ok / tot * 100, 1) if tot else 0,
                 "dist": dict(sorted(dist.items()))}

leg_cache = {}

def height_of(fn):
    if fn in leg_cache:
        return leg_cache[fn]
    img = cv2.imread(os.path.join("data/ocr_eval/plate_crops_external", fn))
    leg_cache[fn] = img.shape[0] if img is not None else 0
    return leg_cache[fn]

def report(rows, tag):
    per, m = score_rows(rows)
    print(f"\n=== {tag} ===")
    print(f"n={m['n']} exact={m['exact']} ({m['exact_pct']}%)  char={m['char_pct']}%")
    print("error distance:", m["dist"])
    # legibility split
    leg_ok = {fn for fn in per if height_of(fn) >= 24}
    leg_bad = {fn for fn in per if height_of(fn) < 24}
    for label, subset in [(">=24px height", leg_ok), ("<24px height", leg_bad)]:
        if not subset:
            continue
        sub_exact = sum(1 for fn in subset if per[fn][2])
        sub_char_ok = sub_tot = 0
        for fn in subset:
            g, p, _, _ = per[fn]
            d = lev(g, p)
            m2 = max(len(g), len(p))
            sub_char_ok += m2 - d
            sub_tot += m2
        print(f"  {label}: n={len(subset)} exact={sub_exact} ({round(sub_exact/len(subset)*100,1)}%) char={round(sub_char_ok/sub_tot*100,1) if sub_tot else 0}%")

if __name__ == "__main__":
    for p in sys.argv[1:]:
        data = json.load(open(p, encoding="utf-8"))
        report(data["rows"], p)
