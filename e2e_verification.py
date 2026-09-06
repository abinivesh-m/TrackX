"""
End-to-end verification script for TrackX performance improvements.
Tests the trajectory system, dashboard imports, and map components.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_trajectory_system():
    """Test the trajectory building system"""
    print("Testing trajectory system...")
    try:
        from database.observation_store import ObservationStore
        from intelligence.trajectory import build_trajectories
        from config import DB_PATH_STR
        
        store = ObservationStore(db_path=DB_PATH_STR)
        obs = store.by_plate('TN09CX7134')
        print(f"[PASS] Found {len(obs)} observations for TN09CX7134")
        
        trajectories = build_trajectories(obs)
        print(f"[PASS] Built {len(trajectories)} trajectories")
        
        for t in trajectories:
            print(f"  Global Vehicle #{t['global_id']}: {len(t['observations'])} observations")
            # Verify match breakdowns have required fields
            for i, breakdown in enumerate(t['match_breakdowns']):
                assert 'total' in breakdown, f"Missing 'total' in breakdown {i}"
                assert 'confidence_label' in breakdown, f"Missing 'confidence_label' in breakdown {i}"
        
        store.close()
        print("[PASS] Trajectory system tests passed")
        return True
    except Exception as e:
        print(f"[FAIL] Trajectory system test failed: {e}")
        return False

def test_dashboard_imports():
    """Test dashboard module imports"""
    print("Testing dashboard imports...")
    try:
        from dashboard.theme import inject_base_css, kpi_row, status_badge
        print("[PASS] Dashboard theme imports successful")
        
        # Test theme functions work
        badge = status_badge("OPERATIONAL")
        assert "OPERATIONAL" in badge
        print("[PASS] Theme functions work correctly")
        
        return True
    except Exception as e:
        print(f"[FAIL] Dashboard import test failed: {e}")
        return False

def test_map_performance():
    """Test map performance optimizations"""
    print("Testing map performance configurations...")
    try:
        # Check if Folium is available
        import folium
        print("[PASS] Folium library available")
        
        # Test creating a basic map with performance settings
        m = folium.Map(
            location=[11.0168, 76.9558],
            zoom_start=13,
            prefer_canvas=True
        )
        print("[PASS] Map with canvas renderer created successfully")
        
        return True
    except Exception as e:
        print(f"[FAIL] Map performance test failed: {e}")
        return False

def test_frontend_files():
    """Test frontend TypeScript files syntax"""
    print("Testing frontend file structure...")
    try:
        frontend_dir = project_root / "frontend" / "src"
        
        # Check if key files exist
        trajectory_map = frontend_dir / "components" / "maps" / "TrajectoryMap.tsx"
        camera_map = frontend_dir / "components" / "maps" / "CameraMap.tsx"
        index_css = frontend_dir / "index.css"
        
        assert trajectory_map.exists(), "TrajectoryMap.tsx not found"
        assert camera_map.exists(), "CameraMap.tsx not found"
        assert index_css.exists(), "index.css not found"
        
        print("[PASS] Frontend files exist")
        
        # Check if performance optimizations are present in CSS
        css_content = index_css.read_text()
        assert "will-change" in css_content, "Performance optimizations missing in CSS"
        assert "backface-visibility" in css_content, "Backface visibility optimization missing"
        
        print("[PASS] Frontend CSS has performance optimizations")
        
        return True
    except Exception as e:
        print(f"[FAIL] Frontend test failed: {e}")
        return False

def main():
    """Run all verification tests"""
    print("=" * 60)
    print("TRACKX END-TO-END VERIFICATION")
    print("=" * 60)
    print()
    
    results = {
        "Trajectory System": test_trajectory_system(),
        "Dashboard Imports": test_dashboard_imports(),
        "Map Performance": test_map_performance(),
        "Frontend Files": test_frontend_files()
    }
    
    print()
    print("=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name}: {status}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print()
    print(f"Overall: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("[PASS] All verification tests passed!")
        return 0
    else:
        print("[FAIL] Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())