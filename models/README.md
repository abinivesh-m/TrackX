# TrackX Model Weights

This directory contains trained model weights for the TrackX vehicle intelligence system.

## Available Models

### Current Weights (Ready for Production Use)
- **best_plate_detector.pt** (5.4 MB): YOLO-based license plate detector trained on Indian plate dataset
  - mAP@0.5: 89% (on validation set)
  - Detection confidence: 97% average
  - Inference speed: ~15ms per image
  - Status: ✅ **INCLUDED and ready for production use**
- **best.onnx** (10.6 MB): ONNX-optimized model for deployment
  - Optimized for faster inference
  - Status: ✅ **INCLUDED and ready for production use**

### Required for Production
- **lprnet_indian.pth**: Indian plate-specific LPRNet weights (to be added)
  - Architecture: Implemented in `recognition/lprnet_ocr.py`
  - Status: Code ready, requires training on Indian plate dataset
  - Training data: 186-737 verified Indian plate crops available
  - Expected accuracy: >90% exact-match after fine-tuning

## Model Training Instructions

### Plate Detector Training
```bash
python -m detection.train_yolo --data /path/to/dataset/data.yaml
```
Output will be saved to: `detection/runs/detect/plate_train/weights/best.pt`

### LPRNet Training (Future)
```bash
python recognition/train_lprnet.py --train_data data/indian_plates/ --epochs 50
```

## Model Performance

### Plate Detector
- mAP@0.5: 89% (on validation set)
- Detection confidence: 97% average
- Inference speed: ~15ms per image

### OCR (Current - PaddleOCR)
- Exact-match accuracy: 72.4% (551 Indian plate samples)
- Character accuracy: 81.1%
- Status: Below 90% SIH requirement

### OCR (Target - LPRNet)
- Expected exact-match accuracy: >90%
- Character accuracy: >95%
- Specialized for Indian plate formats

## Model Download

For SIH demonstration, the system includes:
- ✅ **Pre-trained plate detector weights (best_plate_detector.pt) - INCLUDED and ready to use**
- PaddleOCR will auto-download models on first run
- LPRNet weights to be added after training completion

## Important Notes

- **DO NOT commit trained weights to public repositories** if they contain sensitive training data
- **Model weights are large** - ensure sufficient disk space
- **GPU recommended** for training but not required for inference
- **Model versioning** is managed through file naming and timestamps

## Troubleshooting

### "Model not found" errors
1. Check that model files exist in this directory
2. Verify file paths in configuration files
3. Ensure sufficient file permissions

### Training failures
1. Verify dataset integrity and format
2. Check GPU availability if training requires CUDA
3. Monitor disk space during training

### Inference slowness
1. Ensure using appropriate model size (use .onnx for faster inference)
2. Check GPU availability for acceleration
3. Consider batch processing for multiple images
