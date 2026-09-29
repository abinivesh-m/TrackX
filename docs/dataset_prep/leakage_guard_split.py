#!/usr/bin/env python3
"""
Leakage-safe train/val/test splitter for a future TrackX Indian-plate OCR
training corpus.

STATUS: infrastructure only. This script contains no real training data and
is not wired into pipeline.py or any other production code. It exists so
that the moment a properly licensed dataset is obtained, the split can be
produced deterministically and auditably rather than ad hoc.

Guarantees enforced (all checked programmatically, not just documented):
  1. No `physical_plate_id` appears in more than one of train/val/test.
  2. No `plate_text` appears in more than one of train/val/test (a stricter
     guard than (1) alone, since plate_text is sometimes used as a proxy
     for physical_plate_id per docs/dataset_prep/manifest_schema.md).
  3. Every plate_text listed in held_out_benchmark_plates.txt is dropped
     from the corpus entirely (not merely kept out of train) so the
     existing 37-sample TrackX benchmark can never leak into training,
     validation, OR the new dataset's own internal test split.
  4. The split is deterministic for a given random seed and input, so it
     is reproducible.

Input:  a JSONL manifest matching docs/dataset_prep/manifest_schema.md
Output: train_manifest.jsonl / val_manifest.jsonl / test_manifest.jsonl

Usage:
    python leakage_guard_split.py --input <manifest.jsonl> --out-dir <dir> \
        [--train-frac 0.8] [--val-frac 0.1] [--seed 42]

Run with --self-test to verify the guarantees above against synthetic
(non-real) fixture data with no network or filesystem dependency:
    python leakage_guard_split.py --self-test
"""
import argparse
import json
import os
import random
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
HELD_OUT_PATH = os.path.join(THIS_DIR, "held_out_benchmark_plates.txt")


def load_held_out_plates(path=HELD_OUT_PATH):
    plates = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            plates.add(line.upper())
    return plates


def load_manifest(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_no}: invalid JSON — {e}")
            for required in ("image_path", "plate_text", "physical_plate_id"):
                if required not in obj:
                    raise ValueError(f"{path}:{line_no}: missing required field '{required}'")
            obj["plate_text"] = obj["plate_text"].strip().upper()
            rows.append(obj)
    return rows


def filter_held_out(rows, held_out_plates):
    kept, dropped = [], []
    for r in rows:
        if r["plate_text"] in held_out_plates:
            dropped.append(r)
        else:
            kept.append(r)
    return kept, dropped


def split_rows(rows, train_frac=0.8, val_frac=0.1, seed=42):
    """Group rows by BOTH physical_plate_id and plate_text so neither can
    straddle a split boundary, then assign whole groups to train/val/test.
    """
    if train_frac + val_frac >= 1.0:
        raise ValueError("train_frac + val_frac must be < 1.0 to leave room for test")

    # Union-find style grouping: two rows are in the same group if they
    # share a physical_plate_id OR a plate_text.
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    def key_id(r):
        return ("pid", r["physical_plate_id"])

    def key_text(r):
        return ("text", r["plate_text"])

    for r in rows:
        for k in (key_id(r), key_text(r)):
            if k not in parent:
                parent[k] = k
        union(key_id(r), key_text(r))

    groups = defaultdict(list)
    for r in rows:
        groups[find(key_id(r))].append(r)

    group_keys = list(groups.keys())
    rng = random.Random(seed)
    rng.shuffle(group_keys)

    n_total = len(rows)
    train, val, test = [], [], []
    assigned = 0
    for gk in group_keys:
        group = groups[gk]
        if assigned < train_frac * n_total:
            bucket = train
        elif assigned < (train_frac + val_frac) * n_total:
            bucket = val
        else:
            bucket = test
        bucket.extend(group)
        assigned += len(group)

    return train, val, test


def assert_no_leakage(train, val, test, held_out_plates):
    def ids(rows):
        return {r["physical_plate_id"] for r in rows}

    def texts(rows):
        return {r["plate_text"] for r in rows}

    assert not (ids(train) & ids(val)), "physical_plate_id leaked between train/val"
    assert not (ids(train) & ids(test)), "physical_plate_id leaked between train/test"
    assert not (ids(val) & ids(test)), "physical_plate_id leaked between val/test"
    assert not (texts(train) & texts(val)), "plate_text leaked between train/val"
    assert not (texts(train) & texts(test)), "plate_text leaked between train/test"
    assert not (texts(val) & texts(test)), "plate_text leaked between val/test"
    for rows in (train, val, test):
        assert not (texts(rows) & held_out_plates), "TrackX benchmark plate leaked into split"


def write_jsonl(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run(input_path, out_dir, train_frac, val_frac, seed):
    held_out = load_held_out_plates()
    rows = load_manifest(input_path)
    kept, dropped = filter_held_out(rows, held_out)
    train, val, test = split_rows(kept, train_frac, val_frac, seed)
    assert_no_leakage(train, val, test, held_out)
    os.makedirs(out_dir, exist_ok=True)
    write_jsonl(train, os.path.join(out_dir, "train_manifest.jsonl"))
    write_jsonl(val, os.path.join(out_dir, "val_manifest.jsonl"))
    write_jsonl(test, os.path.join(out_dir, "test_manifest.jsonl"))
    return {
        "input_rows": len(rows),
        "dropped_benchmark_rows": len(dropped),
        "train": len(train),
        "val": len(val),
        "test": len(test),
    }


def _self_test():
    """Exercise the guarantees against synthetic, clearly-fake fixture
    data. No real plate images or real plate strings are used anywhere in
    this function."""
    rng = random.Random(7)
    synth_rows = []
    # 50 synthetic "vehicles", 1-3 crops each, fabricated plate strings
    # that are obviously not real (prefixed ZZ, never used on an actual
    # Indian plate) so this can never be mistaken for real data.
    for i in range(50):
        plate = f"ZZ{i:02d}FAKE{i%10}"
        n_crops = rng.choice([1, 1, 2, 3])
        for c in range(n_crops):
            synth_rows.append({
                "image_path": f"synthetic/{i:04d}_{c}.jpg",
                "plate_text": plate,
                "physical_plate_id": f"vehicle_{i:04d}",
            })
    # Inject 5 rows whose plate_text matches a held-out benchmark plate —
    # these must be dropped entirely by the split.
    held_out = load_held_out_plates()
    sample_held_out = sorted(held_out)[:5]
    for j, plate in enumerate(sample_held_out):
        synth_rows.append({
            "image_path": f"synthetic/leak_{j}.jpg",
            "plate_text": plate,
            "physical_plate_id": f"leak_vehicle_{j}",
        })

    kept, dropped = filter_held_out(synth_rows, held_out)
    assert len(dropped) == 5, f"expected 5 dropped rows, got {len(dropped)}"
    assert all(r["plate_text"] in held_out for r in dropped)

    train, val, test = split_rows(kept, train_frac=0.8, val_frac=0.1, seed=42)
    assert_no_leakage(train, val, test, held_out)
    assert len(train) + len(val) + len(test) == len(kept)
    assert len(train) > 0 and len(val) > 0 and len(test) > 0

    print("SELF-TEST PASSED (synthetic fixture data only, no real plates):")
    print(f"  input rows (incl. injected leaks): {len(synth_rows)}")
    print(f"  dropped as benchmark leakage: {len(dropped)}")
    print(f"  train/val/test sizes: {len(train)}/{len(val)}/{len(test)}")
    print("  no physical_plate_id or plate_text crosses a split boundary")
    print("  no held-out benchmark plate text present in any split")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", help="path to source JSONL manifest")
    ap.add_argument("--out-dir", help="directory to write train/val/test manifests into")
    ap.add_argument("--train-frac", type=float, default=0.8)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--self-test", action="store_true", help="run synthetic self-test and exit")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    if not args.input or not args.out_dir:
        print("error: --input and --out-dir are required unless --self-test is given", file=sys.stderr)
        sys.exit(2)

    stats = run(args.input, args.out_dir, args.train_frac, args.val_frac, args.seed)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
