"""Sheet of crops whose GT looks suspicious / nonstandard."""
import json, os, re, glob, base64

out_dir = "outputs/contact_sheets"
os.makedirs(out_dir, exist_ok=True)


def img_tag(path, gt=None, label=""):
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return f"<div class='c'>ERR {e}</div>"
    gt_html = f"<div class='gt'>GT: {gt}</div>" if gt else ""
    lab = f"<div class='lb'>{label}</div>" if label else ""
    return f"<div class='c'><img src='data:image/jpeg;base64,{b64}'/><div class='nm'>{os.path.basename(path)}</div>{gt_html}{lab}</div>"


pre = json.load(open("data/ocr_eval/precropped_dataset.json", encoding="utf-8"))
entries = pre["entries"] if isinstance(pre, dict) else pre

# strict modern + common legacy formats
def plausible(gt):
    g = str(gt).strip()
    if not g:
        return False
    pats = [
        r"^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{3,4}$",  # modern + 3 digit num
        r"^[A-Z]{2}\d{1,3}\d{3,4}$",             # old all-digit
        r"^[A-Z]{2}\d{2,3}[A-Z]\d{3,4}$",        # DL 6 CM 6683 style -> DL6CM6683 actually no leading zero
        r"^[A-Z]{2}\d{1,4}[A-Z]?\d{3,4}$",
    ]
    # check letters/digits composition only
    if not re.fullmatch(r"[A-Z0-9]{5,11}", g):
        return False
    nletters = sum(1 for c in g if c.isalpha())
    ndigits = sum(1 for c in g if c.isdigit())
    if nletters < 2 or ndigits < 4:
        return False
    return True

sus = []
for e in entries:
    gt = e.get("ground_truth", "")
    if not plausible(gt):
        base = os.path.basename(e.get("image_path", ""))
        full = os.path.join("data/ocr_eval/plate_crops_external", base)
        if os.path.exists(full):
            sus.append((full, gt, e.get("source", ""), "implausible GT"))
# also duplicates with same GT
from collections import Counter
c = Counter(e.get("ground_truth") for e in entries)
dups = {g for g, n in c.items() if n > 1 and plausible(g)}
seen = set()
dlist = []
for e in entries:
    g = e.get("ground_truth")
    if g in dups and g not in seen:
        seen.add(g)
        base = os.path.basename(e.get("image_path", ""))
        full = os.path.join("data/ocr_eval/plate_crops_external", base)
        if os.path.exists(full):
            dlist.append((full, g, f"dup x{c[g]}", "duplicate GT group"))

css = """
body{font-family:monospace;background:#111;color:#ddd;margin:8px}
h2{color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:6px}
.c{border:1px solid #333;border-radius:4px;padding:4px;background:#1c1c1c;overflow:hidden}
.c img{display:block;max-height:140px;background:#000;margin:0 auto;image-rendering:pixelated}
.nm{font-size:10px;color:#999;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gt{font-size:13px;color:#f88}
.lb{font-size:11px;color:#fa0}
"""
def render(entries, title, path):
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body><h2>{title} ({len(entries)})</h2><div class='grid'>"
    html += "".join(img_tag(f, gt=g, label=l) for f, g, s, l in entries)
    html += "</div></body></html>"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", path, len(entries))

render(sus, "implausible GT", f"{out_dir}/suspect_gt.html")
render(dlist, "duplicate GT groups", f"{out_dir}/dup_gt.html")
