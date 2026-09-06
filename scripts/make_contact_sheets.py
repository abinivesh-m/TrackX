"""Build an HTML contact sheet of plate crops for visual inspection."""
import json, glob, base64, os, sys, random

random.seed(7)
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


def render(entries, title, path):
    css = """
    body{font-family:monospace;background:#111;color:#ddd;margin:8px}
    h2{color:#fff}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:6px}
    .c{border:1px solid #333;border-radius:4px;padding:4px;background:#1c1c1c;overflow:hidden}
    .c img{display:block;max-height:140px;background:#000;margin:0 auto;image-rendering:pixelated}
    .nm{font-size:10px;color:#999;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .gt{font-size:13px;color:#4f8}
    .lb{font-size:11px;color:#fa0}
    """
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body><h2>{title}</h2><div class='grid'>"
    html += "".join(entries)
    html += "</div></body></html>"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", path, len(entries))


crops = sorted(glob.glob("data/ocr_eval/plate_crops_external/*.jpg"))

# 1) known-GT video crops (filename-derived GT) sample
video_crops = [c for c in crops if "/video_" in c or "\\video_" in c]
render([img_tag(c) for c in video_crops[:60]], "video crops w/ filename GT", f"{out_dir}/video_sample.html")

# 2) sample of OLX crops with GT from precropped dataset
pre = json.load(open("data/ocr_eval/precropped_dataset.json", encoding="utf-8"))
entries = pre["entries"] if isinstance(pre, dict) else pre
gtmap = {}
for e in entries:
    p = e.get("image_path", "")
    base = os.path.basename(p)
    gtmap[base] = e.get("ground_truth", "")
random.shuffle(entries)
sel = []
for e in entries:
    base = os.path.basename(e.get("image_path", ""))
    full = os.path.join("data/ocr_eval/plate_crops_external", base)
    if os.path.exists(full):
        sel.append((full, e.get("ground_truth", ""), e.get("source", "")))
    if len(sel) >= 80:
        break
render([img_tag(f, gt=g, label=s) for f, g, s in sel], "OLX crop sample (with GT)", f"{out_dir}/olx_sample.html")

# 3) smallest crops (hardest)
small = sorted([c for c in crops], key=lambda c: os.path.getsize(c))[:60]
render([img_tag(c) for c in small], "smallest files", f"{out_dir}/small_sample.html")

# 4) huggingface additional crops
hf = sorted(glob.glob("data/ocr_eval/plate_crops_additional/*.jpg"))
render([img_tag(c) for c in hf], "huggingface additional crops", f"{out_dir}/hf_sample.html")
