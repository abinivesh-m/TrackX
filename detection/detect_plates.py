from ultralytics import YOLO
import cv2
import os

# wrapper around yolo so rest of the code doesn't need to deal with ultralytics directly

class PlateDetector:
    def __init__(self, weights="yolov8n.pt", conf=0.25):
        self.model = YOLO(weights)
        self.conf = conf

    def detect(self, image_path):
        results = self.model.predict(source=image_path, conf=self.conf, verbose=False)

        dets = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                dets.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": round(float(box.conf[0]), 3)
                })
        return dets

    def detect_on_array(self, image_array):
        """same as detect(), but takes an in-memory image (numpy array)
        instead of a file path - needed now that plate detection runs on
        vehicle crops from vehicle_detector.py, not whole-frame files."""
        results = self.model.predict(source=image_array, conf=self.conf, verbose=False)

        dets = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                dets.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": round(float(box.conf[0]), 3),
                })
        return dets

    @staticmethod
    def crop_array(image_array, bbox):
        """crop a bbox out of an in-memory image array"""
        x1, y1, x2, y2 = bbox
        h, w = image_array.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        return image_array[y1:y2, x1:x2]

    def crop_detections(self, image_path, dets, save_dir=None):
        img = cv2.imread(image_path)
        h, w = img.shape[:2]
        crops = []

        if save_dir:
            os.makedirs(save_dir, exist_ok=True)

        for i, d in enumerate(dets):
            x1, y1, x2, y2 = d["bbox"]
            # clamp so we don't crash on boxes near the edge
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = img[y1:y2, x1:x2]
            crops.append(crop)
            if save_dir:
                cv2.imwrite(f"{save_dir}/plate_{i}.jpg", crop)

        return crops


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python detect_plates.py <image> [weights]")
        sys.exit(1)

    img_path = sys.argv[1]
    weights = sys.argv[2] if len(sys.argv) > 2 else "yolov8n.pt"

    det = PlateDetector(weights=weights)
    results = det.detect(img_path)
    print(f"found {len(results)} plates")
    for r in results:
        print(r)

    det.crop_detections(img_path, results, save_dir="outputs/crop")
