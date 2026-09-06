"""
test_analytics_enhancements.py

Tests for enhanced analytics features: speed calculation, OD patterns, congestion detection.
"""

import unittest
from datetime import datetime, timedelta
from analytics.analytics import (
    calculate_vehicle_speed, average_vehicle_speed, 
    origin_destination_patterns, congestion_hotspots
)


class TestVehicleSpeedCalculation(unittest.TestCase):
    """Test vehicle speed calculation functionality."""
    
    def test_speed_calculation_valid(self):
        """Test speed calculation with valid data."""
        obs_a = {
            "camera_id": "CAM_01",
            "timestamp": "2026-08-26T09:00:00",
            "lat": 13.0827,
            "long": 80.2707
        }
        obs_b = {
            "camera_id": "CAM_02",
            "timestamp": "2026-08-26T09:02:48",  # ~2.8 minutes later
            "lat": 13.0850,
            "long": 80.2750
        }
        
        speed = calculate_vehicle_speed(obs_a, obs_b)
        
        # Should return a reasonable speed (not None, not extreme)
        self.assertIsNotNone(speed)
        self.assertGreater(speed, 0)
        self.assertLess(speed, 200)  # Should be realistic
    
    def test_speed_calculation_same_camera(self):
        """Test speed calculation returns None for same camera."""
        obs_a = {
            "camera_id": "CAM_01",
            "timestamp": "2026-08-26T09:00:00",
            "lat": 13.0827,
            "long": 80.2707
        }
        obs_b = {
            "camera_id": "CAM_01",  # Same camera
            "timestamp": "2026-08-26T09:01:00",
            "lat": 13.0827,
            "long": 80.2707
        }
        
        speed = calculate_vehicle_speed(obs_a, obs_b)
        self.assertIsNone(speed)
    
    def test_speed_calculation_invalid_time(self):
        """Test speed calculation with invalid time sequence."""
        obs_a = {
            "camera_id": "CAM_01",
            "timestamp": "2026-08-26T09:05:00",
            "lat": 13.0827,
            "long": 80.2707
        }
        obs_b = {
            "camera_id": "CAM_02",
            "timestamp": "2026-08-26T09:00:00",  # Earlier time
            "lat": 13.0850,
            "long": 80.2750
        }
        
        speed = calculate_vehicle_speed(obs_a, obs_b)
        self.assertIsNone(speed)
    
    def test_average_speed_calculation(self):
        """Test average speed calculation across trajectories."""
        # Create mock trajectory
        trajectory = {
            "global_id": 1,
            "observations": [
                {
                    "camera_id": "CAM_01",
                    "timestamp": "2026-08-26T09:00:00",
                    "lat": 13.0827,
                    "long": 80.2707
                },
                {
                    "camera_id": "CAM_02",
                    "timestamp": "2026-08-26T09:02:48",
                    "lat": 13.0850,
                    "long": 80.2750
                },
                {
                    "camera_id": "CAM_03",
                    "timestamp": "2026-08-26T09:06:24",
                    "lat": 13.0900,
                    "long": 80.2800
                }
            ]
        }
        
        result = average_vehicle_speed([trajectory])
        
        self.assertEqual(result["status"], "calculated")
        self.assertIsNotNone(result["overall_avg_speed"])
        self.assertGreater(result["overall_avg_speed"], 0)
        self.assertGreater(result["num_valid_speeds"], 0)
    
    def test_average_speed_insufficient_data(self):
        """Test average speed with insufficient data."""
        trajectory = {
            "global_id": 1,
            "observations": [
                {
                    "camera_id": "CAM_01",
                    "timestamp": "2026-08-26T09:00:00",
                    "lat": 13.0827,
                    "long": 80.2707
                }
            ]
        }
        
        result = average_vehicle_speed([trajectory])
        
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIsNone(result["overall_avg_speed"])


class TestOriginDestinationPatterns(unittest.TestCase):
    """Test origin-destination pattern analysis."""
    
    def test_od_pattern_calculation(self):
        """Test OD pattern calculation with valid trajectories."""
        trajectories = [
            {
                "global_id": 1,
                "observations": [
                    {"camera_id": "CAM_01", "timestamp": "2026-08-26T09:00:00"},
                    {"camera_id": "CAM_02", "timestamp": "2026-08-26T09:02:48"},
                    {"camera_id": "CAM_03", "timestamp": "2026-08-26T09:06:24"}
                ]
            },
            {
                "global_id": 2,
                "observations": [
                    {"camera_id": "CAM_01", "timestamp": "2026-08-26T09:10:00"},
                    {"camera_id": "CAM_04", "timestamp": "2026-08-26T09:15:00"}
                ]
            }
        ]
        
        result = origin_destination_patterns(trajectories)
        
        self.assertIn("od_pairs", result)
        self.assertIn("top_origins", result)
        self.assertIn("top_destinations", result)
        self.assertIn("top_od_pairs", result)
        
        # Should have CAM_01 as a top origin
        origin_cams = [cam for cam, count in result["top_origins"]]
        self.assertIn("CAM_01", origin_cams)
    
    def test_od_pattern_single_observation(self):
        """Test OD pattern with single observation trajectories."""
        trajectories = [
            {
                "global_id": 1,
                "observations": [
                    {"camera_id": "CAM_01", "timestamp": "2026-08-26T09:00:00"}
                ]
            }
        ]
        
        result = origin_destination_patterns(trajectories)
        
        # Single observation should not create OD pair
        self.assertEqual(len(result["od_pairs"]), 0)


class TestCongestionDetection(unittest.TestCase):
    """Test congestion hotspot detection."""
    
    def test_congestion_detection(self):
        """Test congestion detection with realistic data."""
        observations = []
        
        # Create observations with varying density
        for i in range(10):
            observations.append({"camera_id": "CAM_01", "timestamp": "2026-08-26T09:00:00"})
        for i in range(5):
            observations.append({"camera_id": "CAM_02", "timestamp": "2026-08-26T09:00:00"})
        for i in range(3):
            observations.append({"camera_id": "CAM_03", "timestamp": "2026-08-26T09:00:00"})
        
        result = congestion_hotspots(observations, threshold_percentile=50)
        
        self.assertEqual(result["status"], "calculated")
        self.assertIn("congested_cameras", result)
        self.assertIn("density_by_camera", result)
        self.assertIn("threshold", result)
        
        # CAM_01 should be congested (highest density)
        congested_cams = [cam for cam, count in result["congested_cameras"]]
        self.assertIn("CAM_01", congested_cams)
    
    def test_congestion_detection_insufficient_data(self):
        """Test congestion detection with insufficient data."""
        result = congestion_hotspots([])
        
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["congested_cameras"], [])


if __name__ == "__main__":
    unittest.main()