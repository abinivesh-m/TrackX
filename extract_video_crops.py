import os, cv2, json, hashlib
import xml.etree.ElementTree as ET

video_dir = r'c:\Users\abini\OneDrive\Desktop\sih26127\video_images'
crops_dir = r'c:\Users\abini\OneDrive\Desktop\sih26127\TrackX\data\ocr_eval\plate_crops_external'
os.makedirs(crops_dir, exist_ok=True)

xml_files = [f for f in os.listdir(video_dir) if f.endswith('.xml')]
print(f'Found {len(xml_files)} XML files in {video_dir}')

extracted = 0
entries = []

for xf in xml_files:
    xp = os.path.join(video_dir, xf)
    try:
        tree = ET.parse(xp)
        root = tree.getroot()
        name_elem = root.find('.//object/name')
        bndbox = root.find('.//object/bndbox')
        if name_elem is None or bndbox is None:
            continue
        
        gt = name_elem.text.strip().upper() if name_elem.text else ''
        if len(gt) < 5:
            continue

        xmin = int(bndbox.find('xmin').text)
        ymin = int(bndbox.find('ymin').text)
        xmax = int(bndbox.find('xmax').text)
        ymax = int(bndbox.find('ymax').text)

        # Find corresponding image
        base_name = os.path.splitext(xf)[0]
        img_name = None
        for ext in ['.png', '.jpg', '.jpeg']:
            test_p = os.path.join(video_dir, base_name + ext)
            if os.path.exists(test_p):
                img_name = base_name + ext
                break

        if not img_name:
            continue

        img_path = os.path.join(video_dir, img_name)
        img = cv2.imread(img_path)
        if img is None:
            continue

        h, w = img.shape[:2]
        xmin = max(0, xmin)
        ymin = max(0, ymin)
        xmax = min(w, xmax)
        ymax = min(h, ymax)

        if xmax <= xmin or ymax <= ymin:
            continue

        crop = img[ymin:ymax, xmin:xmax]
        if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 20:
            continue

        crop_fname = f'video_{base_name}_crop.jpg'
        crop_path = os.path.join(crops_dir, crop_fname)
        cv2.imwrite(crop_path, crop)

        with open(crop_path, 'rb') as fp:
            imghash = hashlib.sha256(fp.read()).hexdigest()

        entries.append({
            'image_path': crop_path,
            'ground_truth': gt,
            'image_hash': imghash,
            'source': 'video_images_barc',
            'verification_status': 'verified_xml_annotation',
            'bbox': [xmin, ymin, xmax, ymax],
            'original_image': img_path
        })
        extracted += 1
    except Exception as e:
        continue

print(f'Successfully extracted {extracted} plate crops from video_images!')

# Save new entries manifest
with open(r'c:\Users\abini\OneDrive\Desktop\sih26127\TrackX\data\ocr_eval\video_dataset.json', 'w') as f:
    json.dump(entries, f, indent=2)

print('Done!')
