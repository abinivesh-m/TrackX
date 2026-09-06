#!/usr/bin/env python3
"""
Run the REAL TrackX Pipeline on 7 Cameras.

This script:
1. Scans all 7 camera folders for videos
2. Runs REAL YOLO detection on each video
3. Runs REAL plate detection on each vehicle
4. Runs REAL OCR on each plate
5. Writes REAL observations to PostgreSQL
6. Reconstructs REAL trajectories
7. Displays REAL results

Usage:
    python scripts/run_real_pipeline.py
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
# Create logs directory if it doesn't exist
import os
logs_dir = 'logs'
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'{logs_dir}/pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

# Import TrackX components
from database.observation_store import ObservationStore
from database.blacklist_store import BlacklistStore
from detection.vehicle_detector import VehicleDetector
from detection.detect_plates import PlateDetector
from recognition.ocr_reader import try_init_ocr
from recognition.plate_normalizer import normalize_indian_plate
from recognition.plate_matcher import plate_similarity
from intelligence.trajectory import build_trajectories

# Camera configuration (from your sheet)
CAMERAS = {
    "CAM_01": {
        "name": "Gandhipuram Junction",
        "location": "Gandhipuram",
        "lat": 11.0168,
        "lng": 76.9558,
        "direction": "Northbound",
        "road": "100 Feet Road",
        "video_path": "data/cameras/CAM_01/videos/CAM_01_demo.mp4"
    },
    "CAM_02": {
        "name": "Omni Bus Stand / 100 Feet Rd",
        "location": "Omni Bus Stand",
        "lat": 11.0242,
        "lng": 76.9605,
        "direction": "Southbound",
        "road": "100 Feet Road",
        "video_path": "data/cameras/CAM_02/videos/CAM_02_demo.mp4"
    },
    "CAM_03": {
        "name": "Lakshmi Mills Junction",
        "location": "Lakshmi Mills",
        "lat": 11.0123,
        "lng": 76.9641,
        "direction": "Eastbound",
        "road": "Avinashi Road",
        "video_path": "data/cameras/CAM_03/videos/CAM_03_demo.mp4"
    },
    "CAM_04": {
        "name": "Coimbatore Junction Railway Station",
        "location": "Railway Station",
        "lat": 10.9964,
        "lng": 76.9590,
        "direction": "Westbound",
        "road": "Station Road",
        "video_path": "data/cameras/CAM_04/videos/CAM_04_demo.mp4"
    },
    "CAM_05": {
        "name": "Ramanathapuram Junction",
        "location": "Ramanathapuram",
        "lat": 10.9920,
        "lng": 76.9685,
        "direction": "Northbound",
        "road": "Trichy Road",
        "video_path": "data/cameras/CAM_05/videos/CAM_05_demo.mp4"
    },
    "CAM_06": {
        "name": "Podanur Junction",
        "location": "Podanur",
        "lat": 10.9811,
        "lng": 76.9612,
        "direction": "Southbound",
        "road": "Mettupalayam Road",
        "video_path": "data/cameras/CAM_06/videos/CAM_06_demo.mp4"
    },
    "CAM_07": {
        "name": "Singanallur Junction",
        "location": "Singanallur",
        "lat": 11.0012,
        "lng": 76.9845,
        "direction": "Eastbound",
        "road": "Trichy Road",
        "video_path": "data/cameras/CAM_07/videos/CAM_07_demo.mp4"
    }
}


class RealPipeline:
    """Runs the complete real processing pipeline."""
    
    def __init__(self):
        self.vehicle_detector = None
        self.plate_detector = None
        self.ocr = None
        self.observation_store = None
        self.blacklist_store = None
    
    def initialize(self):
        """Initialize all models and stores."""
        logger.info("Initializing TrackX Real Pipeline...")
        
        # Initialize YOLO vehicle detection
        logger.info("Loading vehicle detection model...")
        self.vehicle_detector = VehicleDetector(weights="yolov8n.pt")
        
        # Initialize plate detection (if weights available)
        weights_path = self._find_plate_weights()
        if weights_path:
            logger.info(f"Loading plate detection model: {weights_path}")
            self.plate_detector = PlateDetector(weights=weights_path)
        else:
            logger.warning("No plate detector weights found. Plate detection will be skipped.")
            self.plate_detector = None
        
        # Initialize OCR
        logger.info("Initializing OCR engine...")
        self.ocr = try_init_ocr()
        if self.ocr is None:
            logger.warning("OCR initialization failed. Plate text will be unavailable.")
        
        # Initialize database stores
        self.observation_store = ObservationStore()
        self.blacklist_store = BlacklistStore()
        
        logger.info("Pipeline initialization complete!")
    
    def _find_plate_weights(self) -> Optional[str]:
        """Find plate detector weights."""
        candidates = [
            "models/best.pt",
            "models/plate_detector.pt",
            "detection/runs/detect/plate_train/weights/best.pt"
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None
    
    def process_camera(self, camera_id: str, camera_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process a single camera's video with real detection.
        
        Returns:
            List of observations found in this camera.
        """
        video_path = camera_config.get("video_path")
        if not os.path.exists(video_path):
            logger.error(f"Video not found for {camera_id}: {video_path}")
            return []
        
        logger.info(f"Processing camera {camera_id}: {video_path}")
        
        import cv2
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video: {video_path}")
            return []
        
        # Process frames
        observations = []
        frame_index = 0
        processed_frames = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Process every Nth frame for speed
        frame_sample = 5
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process every Nth frame
            if frame_index % frame_sample == 0:
                # Vehicle detection
                vehicle_dets = self.vehicle_detector.detect(frame)
                
                # For each vehicle, detect plate and OCR
                for vehicle in vehicle_dets:
                    obs = self._process_vehicle(
                        frame=frame,
                        vehicle=vehicle,
                        camera_id=camera_id,
                        camera_config=camera_config,
                        frame_index=frame_index
                    )
                    if obs:
                        observations.append(obs)
                
                processed_frames += 1
            
            frame_index += 1
        
        cap.release()
        logger.info(f"Processed {processed_frames} frames from {camera_id}, found {len(observations)} vehicles")
        
        return observations
    
    def _process_vehicle(
        self,
        frame,
        vehicle: Dict[str, Any],
        camera_id: str,
        camera_config: Dict[str, Any],
        frame_index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single vehicle detection: crop, detect plate, OCR.
        """
        # Get vehicle bbox
        x1, y1, x2, y2 = vehicle["bbox"]
        
        # Crop vehicle
        vehicle_crop = frame[y1:y2, x1:x2]
        
        if vehicle_crop.size == 0:
            return None
        
        # Plate detection
        plate_info = None
        if self.plate_detector:
            plate_dets = self.plate_detector.detect_on_array(vehicle_crop)
            if plate_dets:
                # Get best plate detection
                best_plate = max(plate_dets, key=lambda d: d["confidence"])
                plate_info = {
                    "bbox": best_plate["bbox"],
                    "confidence": best_plate["confidence"]
                }
        
        # OCR if plate detected
        plate_text = None
        ocr_confidence = None
        normalized_plate = None
        
        if plate_info and self.ocr:
            # Crop plate region from vehicle crop
            px1, py1, px2, py2 = plate_info["bbox"]
            plate_crop = vehicle_crop[py1:py2, px1:px2]
            
            if plate_crop.size > 0:
                # Run OCR
                raw_text, ocr_conf = self.ocr.read(plate_crop)
                
                if raw_text:
                    plate_text = raw_text
                    ocr_confidence = ocr_conf
                    
                    # Normalize
                    normalized, pattern_matched = normalize_indian_plate(raw_text)
                    normalized_plate = normalized
        
        # Create observation
        observation = {
            "camera_id": camera_id,
            "timestamp": datetime.utcnow().isoformat(),
            "plate_text": plate_text,
            "normalized_plate": normalized_plate,
            "confidence": vehicle["confidence"],
            "vehicle_type": vehicle["vehicle_type"],
            "vehicle_bbox": vehicle["bbox"],
            "plate_bbox": plate_info["bbox"] if plate_info else None,
            "ocr_confidence": ocr_confidence,
            "source_file": f"data/cameras/{camera_id}/videos/{camera_id}_demo.mp4",
            "frame_index": frame_index,
            "source_type": "video",
            "data_source": "REAL_INFERENCE",
            "lat": camera_config.get("lat"),
            "long": camera_config.get("lng"),
        }
        
        return observation
    
    def write_observations(self, observations: List[Dict[str, Any]]) -> int:
        """Write observations to database."""
        if not observations:
            return 0
        
        count = 0
        for obs in observations:
            try:
                self.observation_store.add(obs)
                count += 1
            except Exception as e:
                logger.error(f"Failed to write observation: {e}")
        
        logger.info(f"Wrote {count} observations to database")
        return count
    
    def generate_alerts(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate alerts from observations."""
        alerts = []
        
        # Check blacklist
        for obs in observations:
            plate = obs.get("normalized_plate") or obs.get("plate_text")
            if plate:
                # Check against blacklist
                from intelligence.alerts import check_blacklist
                is_flagged, matched_plate, similarity = check_blacklist(plate, self.blacklist_store)
                
                if is_flagged:
                    alerts.append({
                        "type": "BLACKLIST_MATCH",
                        "plate_text": plate,
                        "matched_against": matched_plate,
                        "similarity": similarity,
                        "camera_id": obs["camera_id"],
                        "timestamp": obs["timestamp"],
                        "severity": "HIGH"
                    })
        
        return alerts
    
    def process_all_cameras(self) -> Dict[str, Any]:
        """Process all 7 cameras and generate results."""
        logger.info("=" * 60)
        logger.info("STARTING REAL TRACKX PIPELINE")
        logger.info("=" * 60)
        
        all_observations = []
        results = {}
        
        for camera_id, camera_config in CAMERAS.items():
            logger.info(f"\n--- Processing {camera_id} ({camera_config['name']}) ---")
            
            # Process camera
            camera_observations = self.process_camera(camera_id, camera_config)
            
            # Write to database
            self.write_observations(camera_observations)
            
            # Store results
            results[camera_id] = {
                "name": camera_config["name"],
                "location": camera_config["location"],
                "lat": camera_config["lat"],
                "lng": camera_config["lng"],
                "observations": camera_observations,
                "count": len(camera_observations)
            }
            
            all_observations.extend(camera_observations)
        
        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        
        # Build trajectory
        logger.info("Building trajectories...")
        trajectories = build_trajectories(all_observations)
        
        # Generate alerts
        logger.info("Generating alerts...")
        alerts = self.generate_alerts(all_observations)
        
        # Save results
        self._save_results(results, trajectories, alerts)
        
        return {
            "observations": all_observations,
            "trajectories": trajectories,
            "alerts": alerts,
            "results": results
        }
    
    def _save_results(
        self,
        results: Dict[str, Any],
        trajectories: List[Dict[str, Any]],
        alerts: List[Dict[str, Any]]
    ):
        """Save results to JSON files."""
        output_dir = "outputs/results"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save per-camera results
        with open(f"{output_dir}/pipeline_results.json", "w") as f:
            # Convert observations to serializable format
            serializable_results = {}
            for cam_id, result in results.items():
                serializable_results[cam_id] = {
                    "name": result["name"],
                    "location": result["location"],
                    "lat": result["lat"],
                    "lng": result["lng"],
                    "count": result["count"],
                    "observations": [
                        {k: v for k, v in obs.items() if k != "appearance_vector"}
                        for obs in result["observations"]
                    ]
                }
            json.dump(serializable_results, f, indent=2, default=str)
        
        # Save trajectories
        with open(f"{output_dir}/trajectories.json", "w") as f:
            serializable_trajs = []
            for traj in trajectories:
                serializable_trajs.append({
                    "global_id": traj["global_id"],
                    "observation_count": len(traj["observations"]),
                    "camera_sequence": [o["camera_id"] for o in traj["observations"]],
                    "plates": list(set(o.get("normalized_plate") or o.get("plate_text", "") for o in traj["observations"])),
                    "first_seen": traj["observations"][0]["timestamp"] if traj["observations"] else None,
                    "last_seen": traj["observations"][-1]["timestamp"] if traj["observations"] else None
                })
            json.dump(serializable_trajs, f, indent=2, default=str)
        
        # Save alerts
        with open(f"{output_dir}/alerts.json", "w") as f:
            json.dump(alerts, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "=" * 60)
        print("PIPELINE SUMMARY")
        print("=" * 60)
        print(f"Total Observations: {sum(r['count'] for r in results.values())}")
        print(f"Total Trajectories: {len(trajectories)}")
        print(f"Total Alerts: {len(alerts)}")
        print()
        
        print("--- Per-Camera Summary ---")
        for cam_id, result in results.items():
            print(f"  {cam_id}: {result['count']} observations")
        
        if trajectories:
            print("\n--- Reconstructed Trajectories ---")
            for traj in trajectories:
                if len(traj["observations"]) > 1:
                    cams = [o["camera_id"] for o in traj["observations"]]
                    plates = list(set(o.get("normalized_plate") or o.get("plate_text", "?") for o in traj["observations"]))
                    print(f"  Vehicle: {plates}")
                    print(f"    Route: {' → '.join(cams)}")
                    print(f"    Observations: {len(traj['observations'])}")
        
        if alerts:
            print("\n--- Generated Alerts ---")
            for alert in alerts:
                print(f"  [{alert['severity']}] {alert['type']}: {alert['plate_text']} (camera: {alert['camera_id']})")
        
        print("\nResults saved to:")
        print(f"  {output_dir}/pipeline_results.json")
        print(f"  {output_dir}/trajectories.json")
        print(f"  {output_dir}/alerts.json")
        print("\n✅ REAL PIPELINE COMPLETE!")


def main():
    """Main entry point."""
    logger.info("TrackX Real Pipeline starting...")
    
    pipeline = RealPipeline()
    pipeline.initialize()
    
    results = pipeline.process_all_cameras()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
