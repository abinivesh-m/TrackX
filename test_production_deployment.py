"""
Production Deployment Test Script
Tests all TrackX endpoints on Render deployment
"""

import requests
import json
from datetime import datetime

BACKEND_URL = "https://trackx-2.onrender.com"
FRONTEND_URL = "https://trackx-1.onrender.com"

def test_endpoint(name, url):
    """Test a single endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=30)
        print(f"✅ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ Response Type: JSON")
                print(f"✅ Response Keys: {list(data.keys()) if isinstance(data, dict) else 'List/Other'}")
                print(f"📊 Sample Data:")
                print(json.dumps(data, indent=2)[:500])  # First 500 chars
                return True
            except:
                print(f"⚠️  Response Type: Non-JSON (HTML/Text)")
                print(f"📄 Response Preview: {response.text[:200]}")
                return True
        else:
            print(f"❌ Failed: Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏱️  TIMEOUT - Service may be sleeping (Render free tier)")
        print(f"   Tip: Visit {url} in browser to wake it up, then re-run this test")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def main():
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║            TrackX Production Deployment Test Suite               ║
║                  SIH Problem Statement 26127                     ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    
    results = []
    
    # Test Frontend
    print("\n" + "="*60)
    print("FRONTEND TESTS (React App)")
    print("="*60)
    results.append(("Frontend Homepage", test_endpoint("Frontend Homepage", FRONTEND_URL)))
    
    # Test Backend Endpoints
    print("\n" + "="*60)
    print("BACKEND API TESTS")
    print("="*60)
    
    endpoints = [
        ("Root Endpoint", f"{BACKEND_URL}/"),
        ("Health Check", f"{BACKEND_URL}/health"),
        ("Health Check (v1)", f"{BACKEND_URL}/api/v1/health"),
        ("Analytics Stats", f"{BACKEND_URL}/api/v1/analytics/stats"),
        ("Vehicles List", f"{BACKEND_URL}/api/v1/vehicles"),
        ("TN09CX7134 Trajectory", f"{BACKEND_URL}/api/v1/vehicles/TN09CX7134/trajectory"),
        ("Cameras List", f"{BACKEND_URL}/api/v1/cameras"),
        ("Alerts List", f"{BACKEND_URL}/api/v1/alerts"),
        ("Hourly Analytics", f"{BACKEND_URL}/api/v1/analytics/hourly"),
    ]
    
    for name, url in endpoints:
        results.append((name, test_endpoint(name, url)))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} | {name}")
    
    print(f"\n{'='*60}")
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"{'='*60}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! TrackX is fully operational!")
        print("\n📱 Access Your App:")
        print(f"   Frontend: {FRONTEND_URL}")
        print(f"   API Docs: {BACKEND_URL}/docs")
        print("\n🔍 Try These Features:")
        print("   1. Go to Vehicle Tracking page")
        print("   2. Search for 'TN09CX7134'")
        print("   3. Click on the vehicle row")
        print("   4. Watch the trajectory appear on map (5 cameras)")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\n🔧 Troubleshooting:")
        print("   1. Check if Render deployments are still building")
        print("   2. Visit URLs in browser to wake up sleeping services")
        print("   3. Check Render logs for errors")
        print("   4. Verify environment variables (VITE_API_URL)")

if __name__ == "__main__":
    main()
