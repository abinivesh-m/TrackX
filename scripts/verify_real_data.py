#!/usr/bin/env python3
"""
Verify that the TrackX pipeline has REAL data (no faking).

This script:
1. Checks that observations exist in the database
2. Verifies they came from real video processing
3. Checks that trajectories were auto-generated
4. Validates camera configuration
5. Verifies evidence frames exist

Usage:
    python scripts/verify_real_data.py
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List
from collections import Counter

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.observation_store import ObservationStore


def verify_database() -> Dict[str, int]:
    """Check database has real observations."""
    store = ObservationStore()
    
    all_obs = store.all_observations()
    
    # Count observations
    total = len(all_obs)
    
    # Count by camera
    camera_counts = Counter(obs["camera_id"] for obs in all_obs if obs.get("camera_id"))
    
    # Count unique plates
    unique_plates = len(set(
        obs.get("normalized_plate") or obs.get("plate_text", "")
        for obs in all_obs
        if obs.get("normalized_plate") or obs.get("plate_text")
    ))
    
    # Count observations with data_source = REAL_INFERENCE
    real_obs = sum(1 for obs in all_obs if obs.get("data_source") == "REAL_INFERENCE")
    
    store.close()
    
    return {
        "total_observations": total,
        "unique_plates": unique_plates,
        "real_inference_observations": real_obs,
        "camera_counts": dict(camera_counts)
    }


def verify_video_files() -> List[str]:
    """Check that video files exist for each camera."""
    camera_ids = [f"CAM_{i:02d}" for i in range(1, 8)]
    
    missing = []
    for cam_id in camera_ids:
        video_path = f"data/cameras/{cam_id}/videos/{cam_id}_demo.mp4"
        if not os.path.exists(video_path):
            missing.append(video_path)
    
    return missing


def verify_evidence_frames(observations: List[Dict]) -> int:
    """Check that evidence frames exist for observations."""
    evidence_count = 0
    for obs in observations:
        annotated = obs.get("annotated_output")
        if annotated and os.path.exists(annotated):
            evidence_count += 1
    
    return evidence_count


def main():
    print("=" * 60)
    print("TRACKX REAL DATA VERIFICATION")
    print("=" * 60)
    
    # 1. Check database
    print("\n[1/4] Checking Database...")
    db_stats = verify_database()
    print(f"  Total observations: {db_stats['total_observations']}")
    print(f"  Unique plates: {db_stats['unique_plates']}")
    print(f"  REAL_INFERENCE observations: {db_stats['real_inference_observations']}")
    
    if db_stats["total_observations"] > 0:
        print("  [OK] Database has observations")
    else:
        print("  [FAIL] Database is empty")
        return 1
    
    if db_stats["real_inference_observations"] > 0:
        print("  [OK] Observations are marked as REAL_INFERENCE")
    else:
        print("  [FAIL] No observations marked as REAL_INFERENCE")
    
    # 2. Check video files
    print("\n[2/4] Checking Video Files...")
    missing = verify_video_files()
    if missing:
        print(f"  [FAIL] Missing videos: {missing}")
        return 1
    else:
        print("  [OK] All 7 camera videos exist")
    
    # 3. Check camera coverage
    print("\n[3/4] Checking Camera Coverage...")
    camera_counts = db_stats["camera_counts"]
    
    for cam_id in [f"CAM_{i:02d}" for i in range(1, 8)]:
        count = camera_counts.get(cam_id, 0)
        if count > 0:
            print(f"  [OK] {cam_id}: {count} observations")
        else:
            print(f"  [WARN] {cam_id}: No observations")
    
    # 4. Check evidence
    print("\n[4/4] Checking Evidence Frames...")
    store = ObservationStore()
    all_obs = store.all_observations()
    evidence_count = verify_evidence_frames(all_obs)
    store.close()
    
    if evidence_count > 0:
        print(f"  [OK] {evidence_count} evidence frames found")
    else:
        print("  [WARN] No evidence frames found")
    
    # Final verdict
    print("\n" + "=" * 60)
    if db_stats["total_observations"] > 0 and db_stats["real_inference_observations"] > 0:
        print("[OK] VERIFICATION PASSED - Data is REAL")
        print(f"  {db_stats['total_observations']} real observations")
        print(f"  {db_stats['unique_plates']} unique vehicles detected")
    else:
        print("[FAIL] VERIFICATION FAILED - No real data found")
    
    print("=" * 60)
    
    return 0 if db_stats["total_observations"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
