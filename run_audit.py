import os, json, cv2, hashlib

base_dir = r'c:\Users\abini\OneDrive\Desktop\sih26127\TrackX'
crops_dir = os.path.join(base_dir, 'data', 'ocr_eval', 'plate_crops_external')
excluded_dir = os.path.join(base_dir, 'data', 'ocr_eval', 'excluded')
os.makedirs(excluded_dir, exist_ok=True)

eval_json_path = os.path.join(base_dir, 'data', 'ocr_eval', 'clean_evaluation_dataset.json')
train_json_path = os.path.join(base_dir, 'data', 'ocr_eval', 'training_dataset.json')

eval_entries = {}
if os.path.exists(eval_json_path):
    with open(eval_json_path, 'r', encoding='utf-8') as f:
        d = json.load(f)
        items = d.get('entries', d) if isinstance(d, dict) else d
        for item in items:
            fname = os.path.basename(item.get('image_path', ''))
            eval_entries[fname] = item

train_entries = {}
if os.path.exists(train_json_path):
    with open(train_json_path, 'r', encoding='utf-8') as f:
        d = json.load(f)
        items = d.get('entries', d) if isinstance(d, dict) else d
        for item in items:
            fname = os.path.basename(item.get('image_path', ''))
            train_entries[fname] = item

all_files = [f for f in os.listdir(crops_dir) if os.path.isfile(os.path.join(crops_dir, f))]
print('Total files:', len(all_files))

usable = []
excluded_corrupt = []
excluded_unannotated = []
seen_hashes = {}
excluded_duplicates = []

for fname in sorted(all_files):
    fpath = os.path.join(crops_dir, fname)
    img = cv2.imread(fpath)
    if img is None or img.size == 0:
        excluded_corrupt.append(fname)
        continue

    h, w = img.shape[:2]
    with open(fpath, 'rb') as fp:
        imghash = hashlib.sha256(fp.read()).hexdigest()

    if imghash in seen_hashes:
        excluded_duplicates.append({
            'filename': fname,
            'duplicate_of': seen_hashes[imghash]
        })
        continue
    seen_hashes[imghash] = fname

    in_eval = fname in eval_entries
    in_train = fname in train_entries

    if not (in_eval or in_train):
        excluded_unannotated.append(fname)
        continue

    meta = eval_entries.get(fname) or train_entries.get(fname)
    gt = meta.get('ground_truth', '')
    aspect = w / h if h > 0 else 0

    usable.append({
        'filename': fname,
        'height': h,
        'width': w,
        'aspect_ratio': round(aspect, 2),
        'ground_truth': gt,
        'split': 'evaluation' if in_eval else 'training',
        'source': meta.get('source', 'State-wise_OLX'),
        'sha256': imghash
    })

manifest = {
    'audit_timestamp': '2026-09-05T12:52:00',
    'total_audited': len(all_files),
    'usable_count': len(usable),
    'excluded_corrupt_count': len(excluded_corrupt),
    'excluded_duplicate_count': len(excluded_duplicates),
    'excluded_unannotated_count': len(excluded_unannotated),
    'usable_evaluation_count': len([u for u in usable if u['split'] == 'evaluation']),
    'usable_training_count': len([u for u in usable if u['split'] == 'training']),
    'excluded_corrupt': excluded_corrupt,
    'excluded_duplicates': excluded_duplicates,
    'excluded_unannotated': excluded_unannotated,
    'usable_manifest': usable
}

manifest_path = os.path.join(base_dir, 'data', 'ocr_eval', 'dataset_audit_manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)

print('Manifest written to:', manifest_path)
print('Usable:', manifest['usable_count'], '(Eval:', manifest['usable_evaluation_count'], ', Train:', manifest['usable_training_count'], ')')
print('Corrupt:', len(excluded_corrupt), 'Duplicates:', len(excluded_duplicates), 'Unannotated:', len(excluded_unannotated))
