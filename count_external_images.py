import os
import xml.etree.ElementTree as ET
from pathlib import Path

def count_annotated_images(folder_path):
    """Count images with XML annotations containing plate numbers."""
    count = 0
    plate_info = []
    
    for file in os.listdir(folder_path):
        if file.endswith('.xml'):
            xml_path = os.path.join(folder_path, file)
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                
                # Look for objects with plate numbers
                for obj in root.findall('object'):
                    name_elem = obj.find('name')
                    if name_elem is not None:
                        plate_text = name_elem.text
                        if plate_text and len(plate_text) >= 4:  # Valid plate format
                            # Check if corresponding image exists
                            img_file = file.replace('.xml', '.jpg')
                            img_path = os.path.join(folder_path, img_file)
                            if os.path.exists(img_path):
                                count += 1
                                plate_info.append({
                                    'image': img_path,
                                    'ground_truth': plate_text,
                                    'source': folder_path
                                })
            except Exception as e:
                print(f"Error parsing {xml_path}: {e}")
    
    return count, plate_info

# Check all state folders
# External annotated-source folders live next to the project (data not committed).
base_path = os.getenv("STATE_WISE_OLX_PATH", str(Path(__file__).resolve().parent.parent / "State-wise_OLX"))
total_count = 0
all_plate_info = []

for state_folder in os.listdir(base_path):
    state_path = os.path.join(base_path, state_folder)
    if os.path.isdir(state_path):
        count, plate_info = count_annotated_images(state_path)
        total_count += count
        all_plate_info.extend(plate_info)
        print(f"{state_folder}: {count} annotated plates")

print(f"\nTotal annotated plates from State-wise_OLX: {total_count}")

# Check google_images
google_path = os.getenv("GOOGLE_IMAGES_PATH", str(Path(__file__).resolve().parent.parent / "google_images"))
google_count = 0
google_plate_info = []

if os.path.exists(google_path):
    for file in os.listdir(google_path):
        if file.endswith('.xml'):
            xml_path = os.path.join(google_path, file)
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                
                for obj in root.findall('object'):
                    name_elem = obj.find('name')
                    if name_elem is not None:
                        plate_text = name_elem.text
                        if plate_text and len(plate_text) >= 4:
                            img_file = file.replace('.xml', '.jpg')
                            img_path = os.path.join(google_path, img_file)
                            if os.path.exists(img_path):
                                google_count += 1
                                google_plate_info.append({
                                    'image': img_path,
                                    'ground_truth': plate_text,
                                    'source': 'google_images'
                                })
            except Exception as e:
                pass

print(f"Total annotated plates from google_images: {google_count}")
print(f"Total external annotated plates: {total_count + google_count}")

# Save the external plate info for later use
import json
with open('external_plates_info.json', 'w') as f:
    json.dump({
        'state_wise_olx': all_plate_info,
        'google_images': google_plate_info,
        'total_external': total_count + google_count
    }, f, indent=2)

print(f"Saved external plate info to external_plates_info.json")
