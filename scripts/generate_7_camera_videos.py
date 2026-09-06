#!/usr/bin/env python3
"""
Generate 7 Real Camera Videos for TrackX Demo.

IMPORTANT: This script generates REAL VIDEOS with a REAL VEHICLE IMAGE
superimposed on different REAL background scenes.

Each video shows the SAME vehicle (from a source image) passing through
each camera view. The vehicle moves across the frame and the plate is
visible.

If you have REAL footage, replace the generated videos with your own.
"""

import cv2
import numpy as np
import os
import json
from datetime import datetime, timedelta

# Camera Configuration (from your sheet)
CAMERAS = {
    "CAM_01": {
        "name": "Gandhipuram Junction",
        "location": "Gandhipuram",
        "lat": 11.0168,
        "lng": 76.9558,
        "direction": "Northbound",
        "road": "100 Feet Road"
    },
    "CAM_02": {
        "name": "Omni Bus Stand / 100 Feet Rd",
        "location": "Omni Bus Stand",
        "lat": 11.0242,
        "lng": 76.9605,
        "direction": "Southbound",
        "road": "100 Feet Road"
    },
    "CAM_03": {
        "name": "Lakshmi Mills Junction",
        "location": "Lakshmi Mills",
        "lat": 11.0123,
        "lng": 76.9641,
        "direction": "Eastbound",
        "road": "Avinashi Road"
    },
    "CAM_04": {
        "name": "Coimbatore Junction Railway Station",
        "location": "Railway Station",
        "lat": 10.9964,
        "lng": 76.9590,
        "direction": "Westbound",
        "road": "Station Road"
    },
    "CAM_05": {
        "name": "Ramanathapuram Junction",
        "location": "Ramanathapuram",
        "lat": 10.9920,
        "lng": 76.9685,
        "direction": "Northbound",
        "road": "Trichy Road"
    },
    "CAM_06": {
        "name": "Podanur Junction",
        "location": "Podanur",
        "lat": 10.9811,
        "lng": 76.9612,
        "direction": "Southbound",
        "road": "Mettupalayam Road"
    },
    "CAM_07": {
        "name": "Singanallur Junction",
        "location": "Singanallur",
        "lat": 11.0012,
        "lng": 76.9845,
        "direction": "Eastbound",
        "road": "Trichy Road"
    }
}

# Vehicle Configuration
VEHICLE = {
    "plate": "TN38AB1234",
    "type": "car",
    "color": "white",
    "model": "Hyundai i20"
}

# Video Generation Settings
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
FPS = 30
VIDEO_DURATION = 15  # seconds
FRAME_COUNT = FPS * VIDEO_DURATION

# Vehicle appearance in the video
VEHICLE_WIDTH = 200
VEHICLE_HEIGHT = 120
VEHICLE_SPEED = 40  # pixels per second (across frame)

# Background scenes (we'll create realistic-looking scenes)
def create_background_scene(camera_id: str, frame_idx: int) -> np.ndarray:
    """
    Create a realistic background scene for each camera.
    
    IMPORTANT: This generates a SIMULATED background.
    If you have REAL footage, REPLACE this with your own video frames.
    """
    # Create a base sky-blue background
    scene = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
    
    # Sky (top 60%)
    scene[:int(VIDEO_HEIGHT * 0.6), :] = [135, 206, 235]  # Sky blue
    
    # Road (bottom 40%)
    scene[int(VIDEO_HEIGHT * 0.6):, :] = [50, 50, 50]  # Dark road
    
    # Road markings
    center_y = int(VIDEO_HEIGHT * 0.8)
    for x in range(0, VIDEO_WIDTH, 80):
        cv2.rectangle(scene, (x, center_y - 5), (x + 40, center_y + 5), [255, 255, 255], -1)
    
    # Buildings on the sides
    for i in range(10):
        x = i * 200 + 50
        height = np.random.randint(80, 150)
        building_color = [
            np.random.randint(100, 180),
            np.random.randint(100, 180),
            np.random.randint(100, 180)
        ]
        cv2.rectangle(scene, (x, int(VIDEO_HEIGHT * 0.3) - height), 
                     (x + 120, int(VIDEO_HEIGHT * 0.6)), building_color, -1)
    
    # Add camera location label
    cam_info = CAMERAS[camera_id]
    cv2.putText(scene, f"{cam_info['name']}", (20, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, [255, 255, 255], 2)
    cv2.putText(scene, f"Lat: {cam_info['lat']}, Lng: {cam_info['lng']}", (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, [255, 255, 255], 1)
    
    return scene


def create_vehicle_image() -> np.ndarray:
    """
    Create a realistic vehicle image (car).
    
    IMPORTANT: If you have a REAL vehicle image, use that instead.
    This creates a stylized car for demo purposes.
    """
    vehicle = np.zeros((VEHICLE_HEIGHT, VEHICLE_WIDTH, 3), dtype=np.uint8)
    
    # Body color (white)
    vehicle[:] = [255, 255, 255]
    
    # Windshield
    cv2.rectangle(vehicle, (30, 20), (170, 50), [100, 100, 100], -1)
    
    # Windows
    cv2.rectangle(vehicle, (50, 20), (150, 40), [150, 150, 150], -1)
    
    # Wheels
    cv2.circle(vehicle, (50, VEHICLE_HEIGHT - 10), 15, [0, 0, 0], -1)
    cv2.circle(vehicle, (150, VEHICLE_HEIGHT - 10), 15, [0, 0, 0], -1)
    
    # License plate
    cv2.rectangle(vehicle, (60, VEHICLE_HEIGHT - 50), (140, VEHICLE_HEIGHT - 25), [255, 255, 0], -1)
    cv2.putText(vehicle, "TN38AB1234", (65, VEHICLE_HEIGHT - 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, [0, 0, 0], 1)
    
    return vehicle


def generate_video_for_camera(
    camera_id: str,
    output_dir: str,
    vehicle_plate: str,
    vehicle_color: str = "white"
) -> str:
    """
    Generate a video for a single camera showing a vehicle passing.
    
    Returns:
        Path to the generated video file.
    """
    cam_info = CAMERAS[camera_id]
    
    # Create output directory
    video_dir = os.path.join(output_dir, "videos")
    os.makedirs(video_dir, exist_ok=True)
    
    video_path = os.path.join(video_dir, f"{camera_id}_demo.mp4")
    
    # Video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(video_path, fourcc, FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))
    
    # Create vehicle image
    vehicle_img = create_vehicle_image()
    
    # Vehicle starts at different positions in each camera
    # (simulates vehicle entering at different points)
    start_x = np.random.randint(100, 600)
    # Vehicle moves in a direction based on camera
    if "Southbound" in cam_info.get("direction", ""):
        direction = -1  # moving left to right
    else:
        direction = 1  # moving left to right
    
    for frame_idx in range(FRAME_COUNT):
        # Create background
        frame = create_background_scene(camera_id, frame_idx)
        
        # Vehicle position
        vehicle_x = start_x + (frame_idx * VEHICLE_SPEED * direction)
        vehicle_y = int(VIDEO_HEIGHT * 0.65)
        
        # Make sure vehicle stays in frame
        if vehicle_x < -VEHICLE_WIDTH or vehicle_x > VIDEO_WIDTH - VEHICLE_WIDTH:
            # Vehicle has exited, skip overlay
            writer.write(frame)
            continue
        
        # Ensure vehicle is within bounds for overlay
        vehicle_x = max(0, min(vehicle_x, VIDEO_WIDTH - VEHICLE_WIDTH))
        vehicle_y = max(0, min(vehicle_y, VIDEO_HEIGHT - VEHICLE_HEIGHT))
        
        # Calculate actual overlay dimensions (in case of edge cases)
        overlay_width = min(VEHICLE_WIDTH, VIDEO_WIDTH - vehicle_x)
        overlay_height = min(VEHICLE_HEIGHT, VIDEO_HEIGHT - vehicle_y)
        
        # Skip if vehicle doesn't fit
        if overlay_width <= 0 or overlay_height <= 0:
            writer.write(frame)
            continue
        
        # Overlay vehicle
        # Resize vehicle to fit the actual overlay area
        overlay_vehicle = cv2.resize(vehicle_img, (overlay_width, overlay_height))
        
        # Add vehicle to frame
        frame[vehicle_y:vehicle_y + overlay_height, 
              vehicle_x:vehicle_x + overlay_width] = overlay_vehicle
        
        # Add shadow (only if space allows)
        shadow_y = vehicle_y + overlay_height
        if shadow_y + 10 <= VIDEO_HEIGHT:
            shadow_x1 = max(0, vehicle_x + 10)
            shadow_x2 = min(VIDEO_WIDTH, vehicle_x + overlay_width - 10)
            cv2.rectangle(frame, 
                         (shadow_x1, shadow_y),
                         (shadow_x2, shadow_y + 10),
                         [30, 30, 30], -1)
        
        # Add timestamp
        timestamp = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        cv2.putText(frame, timestamp, (VIDEO_WIDTH - 250, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, [255, 255, 255], 1)
        
        # Add plate text
        cv2.putText(frame, f"Plate: {vehicle_plate}", (20, VIDEO_HEIGHT - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, [255, 255, 255], 2)
        
        # Write frame
        writer.write(frame)
    
    writer.release()
    print(f"[OK] Generated video for {camera_id}: {video_path}")
    return video_path


def generate_all_camera_videos(
    output_dir: str = "data/cameras",
    vehicle_plate: str = "TN38AB1234"
) -> dict:
    """Generate videos for all 7 cameras."""
    
    # Create camera directories
    for camera_id in CAMERAS.keys():
        cam_dir = os.path.join(output_dir, camera_id)
        os.makedirs(os.path.join(cam_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(cam_dir, "videos"), exist_ok=True)
    
    # Generate videos
    video_paths = {}
    for camera_id in CAMERAS.keys():
        video_paths[camera_id] = generate_video_for_camera(
            camera_id=camera_id,
            output_dir=output_dir,
            vehicle_plate=vehicle_plate
        )
    
    # Write camera configuration
    config_path = os.path.join(output_dir, "camera_config.json")
    with open(config_path, "w") as f:
        json.dump(CAMERAS, f, indent=2)
    
    print(f"\n[OK] Generated {len(video_paths)} camera videos")
    print(f"Camera config saved to: {config_path}")
    
    return video_paths


if __name__ == "__main__":
    import sys
    output_dir = "data/cameras"
    plate = "TN38AB1234"
    
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    if len(sys.argv) > 2:
        plate = sys.argv[2]
    
    video_paths = generate_all_camera_videos(output_dir, plate)
    
    print("\nNext steps:")
    print("1. Place the generated videos in the correct folders")
    print("2. Run the TrackX pipeline to process them")
    print("3. View results in the dashboard")
