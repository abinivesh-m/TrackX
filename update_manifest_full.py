import os, json, cv2, hashlib

base_dir = r'c:\Users\abini\OneDrive\Desktop\sih26127\TrackX'
crops_dir = os.path.join(base_dir, 'data', 'ocr_eval', 'plate_crops_external')
all_files = [f for f in os.listdir(crops_dir) if os.path.isfile(os.path.join(crops_dir, f)) and f.endswith('.jpg')]

print(f'Total plate crop image files: {len(all_files)}')

# Load clean evaluation dataset
eval_path = os.path.join(base_dir, 'data', 'ocr_eval', 'clean_evaluation_dataset.json')
with open(eval_path, 'r', encoding='utf-8') as f:
    eval_data = json.load(f)
eval_entries = eval_data.get('entries', eval_data)

# Load training dataset
train_path = os.path.join(base_dir, 'data', 'ocr_eval', 'training_dataset.json')
with open(train_path, 'r', encoding='utf-8') as f:
    train_data = json.load(f)
train_entries = train_data.get('entries', train_data)

# Load video dataset
video_path = os.path.join(base_dir, 'data', 'ocr_eval', 'video_dataset.json')
video_entries = []
if os.path.exists(video_path):
    with open(video_path, 'r', encoding='utf-8') as f:
        video_entries = json.load(f)

print(f'Eval entries: {len(eval_entries)}')
print(f'Train entries: {len(train_entries)}')
print(f'Video entries: {len(video_entries)}')
print(f'TOTAL GENUINE DATASET ENTRIES: {len(eval_entries) + len(train_entries) + len(video_entries)}')
