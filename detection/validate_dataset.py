"""
detection/validate_dataset.py

Sanity-checks a YOLO-format plate-detection dataset BEFORE you spend time
training on it. Catches the mistakes that otherwise show up as a
confusing training crash an hour in, or (worse) a model that trains
"successfully" on garbage labels:

  - data.yaml exists and points at folders that actually exist
  - every image has a matching label file (and vice versa)
  - every label line has the right number of fields and all values are
    valid normalized YOLO coordinates (0-1), not raw pixel coordinates
    (a very common copy-paste mistake between annotation formats)
  - class ids in the labels are all within [0, nc) from data.yaml

This does NOT touch ultralytics/torch - it only reads text/yaml/image
files - so it can run in any environment, even one that can't install the
full ML stack, and won't burn training time on a broken dataset.

Usage (run from the project root):
    python -m detection.validate_dataset --data_dir /path/to/downloaded/dataset

That path should be the folder containing data.yaml (i.e. what you get
after extracting a Roboflow "YOLOv8" export zip).
"""
import argparse
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def _fail(msg):
    print(f"[FAIL] {msg}")
    return False


def _warn(msg):
    print(f"[WARN] {msg}")


def _ok(msg):
    print(f"[OK]   {msg}")


def _load_data_yaml(data_dir):
    yaml_path = os.path.join(data_dir, "data.yaml")
    if not os.path.isfile(yaml_path):
        _fail(f"no data.yaml found at {yaml_path}")
        return None

    if yaml is None:
        _fail("PyYAML is not installed (`pip install pyyaml`) - can't parse data.yaml")
        return None

    with open(yaml_path) as f:
        try:
            cfg = yaml.safe_load(f)
        except Exception as e:
            _fail(f"data.yaml is not valid YAML: {e}")
            return None

    for key in ("train", "val", "nc", "names"):
        if key not in cfg:
            _fail(f"data.yaml is missing required key '{key}'")
            return None

    _ok(f"data.yaml parsed: nc={cfg['nc']}, names={cfg['names']}")
    return cfg


def _resolve_split_dir(data_dir, split_path):
    """split_path in data.yaml is usually relative to data_dir (e.g. 'train/images')."""
    candidate = os.path.join(data_dir, split_path)
    return candidate if os.path.isdir(candidate) else None


def _labels_dir_for(images_dir):
    """Standard YOLO/Roboflow layout: .../train/images -> .../train/labels (sibling folder)."""
    parent = os.path.dirname(images_dir.rstrip("/"))
    return os.path.join(parent, "labels")


def _validate_split(name, images_dir, nc):
    print(f"\n--- checking '{name}' split: {images_dir} ---")
    labels_dir = _labels_dir_for(images_dir)
    if not os.path.isdir(labels_dir):
        return _fail(f"'{name}': expected a sibling 'labels/' folder at {labels_dir}, not found")

    images = sorted(f for f in os.listdir(images_dir)
                     if os.path.splitext(f)[1].lower() in IMAGE_EXTS)
    if not images:
        return _fail(f"'{name}': no images found in {images_dir}")

    n_ok = 0
    n_missing_label = 0
    n_empty_label = 0
    n_bad_line = 0
    n_bad_class = 0
    n_pixel_coords_suspected = 0

    for img_name in images:
        base = os.path.splitext(img_name)[0]
        label_path = os.path.join(labels_dir, base + ".txt")

        if not os.path.isfile(label_path):
            n_missing_label += 1
            continue

        with open(label_path) as f:
            lines = [l.strip() for l in f if l.strip()]

        if not lines:
            n_empty_label += 1  # a background image with no plate - fine, just noting the count
            n_ok += 1
            continue

        line_ok = True
        for line in lines:
            parts = line.split()
            if len(parts) != 5:
                n_bad_line += 1
                line_ok = False
                continue
            try:
                cls_id = int(parts[0])
                coords = [float(p) for p in parts[1:]]
            except ValueError:
                n_bad_line += 1
                line_ok = False
                continue

            if not (0 <= cls_id < nc):
                n_bad_class += 1
                line_ok = False

            if any(c > 1.0 or c < 0.0 for c in coords):
                # classic mistake: pixel coordinates pasted in instead of
                # normalized 0-1 YOLO coordinates
                n_pixel_coords_suspected += 1
                line_ok = False

        if line_ok:
            n_ok += 1

    # unmatched labels (label file with no corresponding image)
    image_bases = {os.path.splitext(f)[0] for f in images}
    label_files = [f for f in os.listdir(labels_dir) if f.endswith(".txt")]
    orphan_labels = [f for f in label_files if os.path.splitext(f)[0] not in image_bases]

    print(f"  images found:            {len(images)}")
    print(f"  usable image+label pairs:{n_ok}")
    if n_missing_label:
        _warn(f"{n_missing_label} image(s) have no matching label file (treated as background if intentional)")
    if n_empty_label:
        print(f"  ({n_empty_label} label file(s) are empty - background/no-plate images, this is normal)")
    if orphan_labels:
        _warn(f"{len(orphan_labels)} label file(s) have no matching image (e.g. {orphan_labels[0]})")
    if n_bad_line:
        _fail(f"{n_bad_line} label line(s) don't have the expected 5 fields or aren't numeric")
    if n_bad_class:
        _fail(f"{n_bad_class} label line(s) reference a class id outside [0, {nc})")
    if n_pixel_coords_suspected:
        _fail(f"{n_pixel_coords_suspected} label line(s) have values > 1.0 - looks like raw pixel "
              f"coordinates instead of normalized YOLO coordinates. Re-export in YOLO format.")

    split_passed = not (n_bad_line or n_bad_class or n_pixel_coords_suspected) and n_ok > 0
    if split_passed:
        _ok(f"'{name}' split looks valid ({n_ok} usable pairs)")
    return split_passed


def validate_dataset(data_dir):
    cfg = _load_data_yaml(data_dir)
    if cfg is None:
        return False

    nc = cfg["nc"]
    all_passed = True

    for split in ("train", "val"):
        split_path = cfg.get(split)
        if not split_path:
            all_passed = _fail(f"data.yaml has no '{split}' entry") and all_passed
            continue
        images_dir = _resolve_split_dir(data_dir, split_path)
        if images_dir is None:
            all_passed = _fail(f"'{split}' path in data.yaml ('{split_path}') does not exist under {data_dir}") and all_passed
            continue
        all_passed = _validate_split(split, images_dir, nc) and all_passed

    print()
    if all_passed:
        _ok("Dataset looks ready to train on. Next: "
            "python -m detection.train_yolo --data " + os.path.join(data_dir, "data.yaml"))
    else:
        _fail("Dataset has problems - fix the issues above before training "
              "(training on a broken dataset silently produces a useless model).")
    return all_passed


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Validate a YOLO-format plate-detection dataset before training")
    p.add_argument("--data_dir", required=True,
                    help="folder containing data.yaml (e.g. the extracted Roboflow export)")
    args = p.parse_args()

    if not os.path.isdir(args.data_dir):
        print(f"[FAIL] {args.data_dir} is not a directory")
        sys.exit(1)

    passed = validate_dataset(args.data_dir)
    sys.exit(0 if passed else 1)
