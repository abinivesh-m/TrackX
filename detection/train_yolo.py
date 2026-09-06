"""
detection/train_yolo.py

Fine-tunes a YOLO model to detect ONE class: license plates. This is a
thin wrapper around ultralytics' own training loop - it does not
implement training itself (that would be reinventing a solved problem),
it just wires up sensible defaults for this project and points the
output at the exact path detection/detect_plates.py and
demo/visual_pipeline.py already look for.

You do NOT need a powerful GPU or a huge dataset for this to be useful
for a demo: a few hundred to a few thousand labeled plate images and
10-30 epochs on a small model (yolov8n.pt) is enough to get real,
non-fabricated plate boxes. It won't be production-grade, and that's a
fine thing to say plainly to a judge.

Typical flow:
    1. Get a labeled dataset (see detection/data.yaml.example for the
       expected folder layout - a Roboflow Universe "YOLOv8" export
       already matches this out of the box).
    2. python -m detection.validate_dataset --data_dir /path/to/dataset
    3. python -m detection.train_yolo --data /path/to/dataset/data.yaml
    4. Trained weights land at:
           detection/runs/detect/plate_train/weights/best.pt
       which is already one of the paths
       demo/visual_pipeline.find_plate_weights() checks automatically -
       no further wiring needed, just re-run the pipeline/dashboard.

Run (from the project root):
    python -m detection.train_yolo --data /path/to/dataset/data.yaml
    python -m detection.train_yolo --data /path/to/dataset/data.yaml --epochs 30 --model yolov8s.pt
"""
import argparse
import os

from ultralytics import YOLO

# Matches the FIRST candidate demo/visual_pipeline.find_plate_weights()
# looks for by convention - keeping these in sync means "train, then just
# re-run the pipeline" works with zero extra steps.
DEFAULT_PROJECT = "detection/runs/detect"
DEFAULT_RUN_NAME = "plate_train"


def train(data_yaml, base_model="yolov8n.pt", epochs=30, imgsz=640,
          project=DEFAULT_PROJECT, name=DEFAULT_RUN_NAME, patience=15):
    """
    base_model: starting weights for TRANSFER learning, not training from
    scratch - "yolov8n.pt" (the smallest/fastest stock COCO checkpoint) is
    a fine default for a hackathon timeframe; it has never seen a
    "license_plate" class, that's exactly what fine-tuning on your
    dataset teaches it.

    Returns the path to the best checkpoint this run produced.
    """
    if not os.path.isfile(data_yaml):
        raise FileNotFoundError(
            f"data.yaml not found at {data_yaml} - point --data at the "
            f"data.yaml inside your downloaded/prepared dataset folder."
        )

    model = YOLO(base_model)

    print(f"[train_yolo] fine-tuning {base_model} on {data_yaml} for {epochs} epoch(s)...")
    model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        project=project,
        name=name,
        patience=patience,   # stop early if val loss stalls for this many epochs
        exist_ok=True,        # re-running with the same --name overwrites, doesn't error
    )

    best_path = os.path.join(project, name, "weights", "best.pt")
    if os.path.isfile(best_path):
        print(f"[train_yolo] done. Best weights: {best_path}")
        print(f"[train_yolo] this is already a path demo/visual_pipeline.py checks "
              f"automatically - just re-run the pipeline/dashboard, no extra config needed.")
    else:
        print(f"[train_yolo] WARNING: training finished but expected checkpoint not found "
              f"at {best_path} - check the ultralytics output above for what actually happened.")

    return best_path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Fine-tune a YOLO plate detector for TrackX")
    p.add_argument("--data", required=True, help="path to your dataset's data.yaml")
    p.add_argument("--model", default="yolov8n.pt",
                    help="starting checkpoint for transfer learning (default: yolov8n.pt)")
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--patience", type=int, default=15,
                    help="stop early if validation loss doesn't improve for this many epochs")
    p.add_argument("--project", default=DEFAULT_PROJECT)
    p.add_argument("--name", default=DEFAULT_RUN_NAME)
    args = p.parse_args()

    train(
        data_yaml=args.data,
        base_model=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        patience=args.patience,
        project=args.project,
        name=args.name,
    )
