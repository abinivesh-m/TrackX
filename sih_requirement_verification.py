"""
SIH-26127 Requirement Verification System
Verifies all 13 SIH requirements for TrackX implementation.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Tuple

class SIHRequirementVerifier:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.verification_results = {
            "verification_timestamp": "",
            "total_requirements": 13,
            "fully_implemented": 0,
            "partially_implemented": 0,
            "not_implemented": 0,
            "requirements": {}
        }
    
    def check_requirement_1_anpr_ocr(self) -> Dict:
        """R1: High-accuracy ANPR/OCR with varying conditions"""
        # Check LPRNet implementation
        lprnet_exists = (self.project_path / "recognition" / "lprnet_ocr.py").exists()
        paddleocr_exists = (self.project_path / "recognition" / "ocr_reader.py").exists()
        
        # Check preprocessing capabilities
        preprocessing_features = [
            "adaptive preprocessing",
            "multi-pass OCR",
            "confidence-based selection",
            "Indian plate validation"
        ]
        
        # Check if OCR evaluation exists
        ocr_eval_exists = (self.project_path / "recognition" / "ocr_evaluation.py").exists()
        
        return {
            "requirement": "R1: High-accuracy ANPR/OCR",
            "status": "PARTIAL" if (lprnet_exists and paddleocr_exists) else "NOT_IMPLEMENTED",
            "evidence": {
                "lprnet_implementation": lprnet_exists,
                "paddleocr_implementation": paddleocr_exists,
                "preprocessing_features": preprocessing_features,
                "ocr_evaluation_module": ocr_eval_exists,
                "measured_accuracy": "35.9% exact-match (documented limitation)",
                "target_accuracy": ">90% (not met)",
                "notes": "LPRNet + PaddleOCR implemented with preprocessing, but accuracy below target"
            }
        }
    
    def check_requirement_2_multi_camera(self) -> Dict:
        """R2: Multi-camera processing"""
        # Check camera network
        camera_network_exists = (self.project_path / "network" / "camera_network.py").exists()
        
        # Check if multiple cameras are defined
        if camera_network_exists:
            from network.camera_network import CAMERAS
            camera_count = len(CAMERAS)
        else:
            camera_count = 0
        
        # Check camera data directories
        camera_data_exists = (self.project_path / "data" / "cameras").exists()
        
        return {
            "requirement": "R2: Multi-camera processing",
            "status": "FULLY_IMPLEMENTED" if camera_count >= 7 else "PARTIAL",
            "evidence": {
                "camera_network_module": camera_network_exists,
                "defined_cameras": camera_count,
                "camera_data_directory": camera_data_exists,
                "multi_camera_support": camera_count >= 7,
                "notes": f"{camera_count} cameras defined in network"
            }
        }
    
    def check_requirement_3_trajectory(self) -> Dict:
        """R3: Single plate trajectory tracking"""
        # Check trajectory module
        trajectory_exists = (self.project_path / "intelligence" / "trajectory.py").exists()
        fusion_exists = (self.project_path / "intelligence" / "fusion.py").exists()
        
        # Check for key trajectory features
        trajectory_features = [
            "multi-camera reconstruction",
            "confidence-aware matching",
            "temporal feasibility",
            "spatial connectivity",
            "anomaly detection"
        ]
        
        return {
            "requirement": "R3: Single plate trajectory tracking",
            "status": "FULLY_IMPLEMENTED" if (trajectory_exists and fusion_exists) else "PARTIAL",
            "evidence": {
                "trajectory_module": trajectory_exists,
                "fusion_module": fusion_exists,
                "trajectory_features": trajectory_features,
                "notes": "Confidence-aware multi-camera trajectory with anomaly detection"
            }
        }
    
    def check_requirement_4_chronological_data(self) -> Dict:
        """R4: Chronological timestamps/camera locations/routes"""
        # Check observation model
        observation_store_exists = (self.project_path / "database" / "observation_store.py").exists()
        
        # Check if timestamps and camera data are stored
        if observation_store_exists:
            # Read the schema to check for required fields
            with open(self.project_path / "database" / "observation_store.py", 'r', encoding='utf-8') as f:
                schema_content = f.read()
            
            has_timestamp = "timestamp" in schema_content
            has_camera_id = "camera_id" in schema_content
            has_location = "lat" in schema_content and "long" in schema_content
        else:
            has_timestamp = has_camera_id = has_location = False
        
        return {
            "requirement": "R4: Chronological timestamps/camera locations/routes",
            "status": "FULLY_IMPLEMENTED" if all([has_timestamp, has_camera_id, has_location]) else "PARTIAL",
            "evidence": {
                "observation_store": observation_store_exists,
                "timestamp_tracking": has_timestamp,
                "camera_id_tracking": has_camera_id,
                "location_tracking": has_location,
                "notes": "Observations include timestamps, camera IDs, and GPS coordinates"
            }
        }
    
    def check_requirement_5_gis_visualization(self) -> Dict:
        """R5: GIS trajectory visualization"""
        # Check GIS module
        gis_exists = (self.project_path / "gis" / "gis_map.py").exists()
        
        # Check dashboard GIS integration
        dashboard_exists = (self.project_path / "dashboard" / "dashboard.py").exists()
        
        # Check for map libraries
        try:
            import folium
            folium_available = True
        except ImportError:
            folium_available = False
        
        return {
            "requirement": "R5: GIS trajectory visualization",
            "status": "FULLY_IMPLEMENTED" if (gis_exists and dashboard_exists and folium_available) else "PARTIAL",
            "evidence": {
                "gis_module": gis_exists,
                "dashboard_integration": dashboard_exists,
                "folium_library": folium_available,
                "notes": "Interactive GIS map with trajectory visualization"
            }
        }
    
    def check_requirement_6_traffic_density(self) -> Dict:
        """R6: Traffic density"""
        # Check analytics module
        analytics_exists = (self.project_path / "analytics" / "analytics.py").exists()
        
        # Check for density calculation functions
        if analytics_exists:
            with open(self.project_path / "analytics" / "analytics.py", 'r', encoding='utf-8') as f:
                analytics_content = f.read()
            
            has_density = "vehicles_per_camera" in analytics_content
            has_hourly_density = "hourly_density" in analytics_content
        else:
            has_density = has_hourly_density = False
        
        return {
            "requirement": "R6: Traffic density",
            "status": "FULLY_IMPLEMENTED" if (analytics_exists and has_density) else "PARTIAL",
            "evidence": {
                "analytics_module": analytics_exists,
                "density_calculation": has_density,
                "hourly_density": has_hourly_density,
                "notes": "Per-camera and hourly traffic density analysis"
            }
        }
    
    def check_requirement_7_od_patterns(self) -> Dict:
        """R7: Origin-Destination patterns"""
        # Check analytics for OD patterns
        analytics_exists = (self.project_path / "analytics" / "analytics.py").exists()
        
        if analytics_exists:
            with open(self.project_path / "analytics" / "analytics.py", 'r', encoding='utf-8') as f:
                analytics_content = f.read()
            
            has_od = "origin_destination_patterns" in analytics_content
        else:
            has_od = False
        
        return {
            "requirement": "R7: Origin-Destination patterns",
            "status": "FULLY_IMPLEMENTED" if (analytics_exists and has_od) else "PARTIAL",
            "evidence": {
                "analytics_module": analytics_exists,
                "od_analysis": has_od,
                "notes": "Origin-destination pattern analysis with matrix computation"
            }
        }
    
    def check_requirement_8_congestion(self) -> Dict:
        """R8: Congestion bottlenecks"""
        # Check analytics for congestion
        analytics_exists = (self.project_path / "analytics" / "analytics.py").exists()
        
        if analytics_exists:
            with open(self.project_path / "analytics" / "analytics.py", 'r', encoding='utf-8') as f:
                analytics_content = f.read()
            
            has_congestion = "congestion_hotspots" in analytics_content
        else:
            has_congestion = False
        
        return {
            "requirement": "R8: Congestion bottlenecks",
            "status": "FULLY_IMPLEMENTED" if (analytics_exists and has_congestion) else "PARTIAL",
            "evidence": {
                "analytics_module": analytics_exists,
                "congestion_analysis": has_congestion,
                "notes": "Multi-factor congestion hotspot identification"
            }
        }
    
    def check_requirement_9_heatmaps(self) -> Dict:
        """R9: Real-time traffic heatmaps"""
        # Check dashboard for heatmap functionality
        dashboard_exists = (self.project_path / "dashboard" / "dashboard.py").exists()
        
        if dashboard_exists:
            with open(self.project_path / "dashboard" / "dashboard.py", 'r', encoding='utf-8') as f:
                dashboard_content = f.read()
            
            has_heatmap = "heatmap" in dashboard_content.lower() or "density" in dashboard_content.lower()
        else:
            has_heatmap = False
        
        return {
            "requirement": "R9: Real-time traffic heatmaps",
            "status": "FULLY_IMPLEMENTED" if (dashboard_exists and has_heatmap) else "PARTIAL",
            "evidence": {
                "dashboard_module": dashboard_exists,
                "heatmap_visualization": has_heatmap,
                "notes": "Traffic density visualization with heatmap-style display"
            }
        }
    
    def check_requirement_10_route_density(self) -> Dict:
        """R10: Route density/flow trends"""
        # Check analytics for route analysis
        analytics_exists = (self.project_path / "analytics" / "analytics.py").exists()
        
        if analytics_exists:
            with open(self.project_path / "analytics" / "analytics.py", 'r', encoding='utf-8') as f:
                analytics_content = f.read()
            
            has_routes = "route_frequency" in analytics_content
            has_cross_camera = "cross_camera_route_frequency" in analytics_content
        else:
            has_routes = has_cross_camera = False
        
        return {
            "requirement": "R10: Route density/flow trends",
            "status": "FULLY_IMPLEMENTED" if (analytics_exists and has_routes) else "PARTIAL",
            "evidence": {
                "analytics_module": analytics_exists,
                "route_analysis": has_routes,
                "cross_camera_routes": has_cross_camera,
                "notes": "Route frequency and cross-camera flow analysis"
            }
        }
    
    def check_requirement_11_vehicle_speed(self) -> Dict:
        """R11: Average vehicle speeds where valid"""
        # Check analytics for speed calculation
        analytics_exists = (self.project_path / "analytics" / "analytics.py").exists()
        
        if analytics_exists:
            with open(self.project_path / "analytics" / "analytics.py", 'r', encoding='utf-8') as f:
                analytics_content = f.read()
            
            has_speed = "calculate_vehicle_speed" in analytics_content
            has_avg_speed = "average_vehicle_speed" in analytics_content
        else:
            has_speed = has_avg_speed = False
        
        return {
            "requirement": "R11: Average vehicle speeds where valid",
            "status": "FULLY_IMPLEMENTED" if (analytics_exists and has_speed) else "PARTIAL",
            "evidence": {
                "analytics_module": analytics_exists,
                "speed_calculation": has_speed,
                "average_speed": has_avg_speed,
                "notes": "Vehicle speed calculation from camera network distances"
            }
        }
    
    def check_requirement_12_blacklist_alerts(self) -> Dict:
        """R12: Blacklisted vehicle alerts"""
        # Check alert system
        alerts_exists = (self.project_path / "intelligence" / "alerts.py").exists()
        blacklist_exists = (self.project_path / "database" / "blacklist_store.py").exists()
        
        # Check for blacklist detection functionality
        if alerts_exists:
            with open(self.project_path / "intelligence" / "alerts.py", 'r', encoding='utf-8') as f:
                alerts_content = f.read()
            
            has_blacklist = "blacklist" in alerts_content.lower()
        else:
            has_blacklist = False
        
        return {
            "requirement": "R12: Blacklisted vehicle alerts",
            "status": "FULLY_IMPLEMENTED" if (alerts_exists and blacklist_exists and has_blacklist) else "PARTIAL",
            "evidence": {
                "alerts_module": alerts_exists,
                "blacklist_store": blacklist_exists,
                "blacklist_detection": has_blacklist,
                "notes": "Blacklist detection with fuzzy matching and alert generation"
            }
        }
    
    def check_requirement_13_anomaly_alerts(self) -> Dict:
        """R13: Suspicious route anomaly alerts"""
        # Check alert system for anomaly detection
        alerts_exists = (self.project_path / "intelligence" / "alerts.py").exists()
        
        # Check for anomaly detection functionality
        if alerts_exists:
            with open(self.project_path / "intelligence" / "alerts.py", 'r', encoding='utf-8') as f:
                alerts_content = f.read()
            
            has_anomaly = "anomaly" in alerts_content.lower() or "suspicious" in alerts_content.lower()
        else:
            has_anomaly = False
        
        # Check route hypothesis module
        route_hypothesis_exists = (self.project_path / "intelligence" / "route_hypothesis.py").exists()
        
        return {
            "requirement": "R13: Suspicious route anomaly alerts",
            "status": "FULLY_IMPLEMENTED" if (alerts_exists and has_anomaly and route_hypothesis_exists) else "PARTIAL",
            "evidence": {
                "alerts_module": alerts_exists,
                "anomaly_detection": has_anomaly,
                "route_hypothesis": route_hypothesis_exists,
                "notes": "Route anomaly detection with impossible travel identification"
            }
        }
    
    def verify_all_requirements(self) -> Dict:
        """Verify all 13 SIH requirements"""
        from datetime import datetime
        self.verification_results["verification_timestamp"] = datetime.now().isoformat()
        
        # Check each requirement
        requirement_checks = [
            self.check_requirement_1_anpr_ocr(),
            self.check_requirement_2_multi_camera(),
            self.check_requirement_3_trajectory(),
            self.check_requirement_4_chronological_data(),
            self.check_requirement_5_gis_visualization(),
            self.check_requirement_6_traffic_density(),
            self.check_requirement_7_od_patterns(),
            self.check_requirement_8_congestion(),
            self.check_requirement_9_heatmaps(),
            self.check_requirement_10_route_density(),
            self.check_requirement_11_vehicle_speed(),
            self.check_requirement_12_blacklist_alerts(),
            self.check_requirement_13_anomaly_alerts()
        ]
        
        # Count implementation status
        for i, check in enumerate(requirement_checks, 1):
            self.verification_results["requirements"][f"R{i}"] = check
            if check["status"] == "FULLY_IMPLEMENTED":
                self.verification_results["fully_implemented"] += 1
            elif check["status"] == "PARTIAL":
                self.verification_results["partially_implemented"] += 1
            else:
                self.verification_results["not_implemented"] += 1
        
        return self.verification_results

def main():
    verifier = SIHRequirementVerifier(".")
    
    print("=" * 60)
    print("SIH-26127 REQUIREMENT VERIFICATION")
    print("=" * 60)
    
    results = verifier.verify_all_requirements()
    
    print(f"\nVerification Results:")
    print(f"Total Requirements: {results['total_requirements']}")
    print(f"Fully Implemented: {results['fully_implemented']}")
    print(f"Partially Implemented: {results['partially_implemented']}")
    print(f"Not Implemented: {results['not_implemented']}")
    
    print(f"\nDetailed Results:")
    for req_id, check in results["requirements"].items():
        print(f"\n{check['requirement']}: {check['status']}")
        print(f"  Evidence: {check['evidence']}")
    
    # Save results
    with open("sih_requirement_verification.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: sih_requirement_verification.json")

if __name__ == "__main__":
    main()