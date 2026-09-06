import json
import cv2
import random

# Load the dataset
with open('data/ocr_eval/clean_evaluation_dataset.json', 'r') as f:
    data = json.load(f)

print('Sample plate crops:')
sample = random.sample(data, 5)
for i, entry in enumerate(sample):
    image_path = entry['image']
    ground_truth = entry['ground_truth']
    
    # Check if image exists and get its dimensions
    if cv2.imread(image_path) is not None:
        img = cv2.imread(image_path)
        h, w = img.shape[:2]
        print(f'{i+1}. {image_path}')
        print(f'   GT: {ground_truth}')
        print(f'   Size: {w}x{h}')
    else:
        print(f'{i+1}. {image_path} - MISSING')
        print(f'   GT: {ground_truth}')
