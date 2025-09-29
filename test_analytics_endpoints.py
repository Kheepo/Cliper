#!/usr/bin/env python3
"""
Test script to verify analytics endpoints are working properly
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint, description):
    """Test a single endpoint and return results"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*50}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print(f"{'='*50}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response Data: {json.dumps(data, indent=2)}")
                return True, data
            except json.JSONDecodeError:
                print(f"Response Text: {response.text}")
                return False, response.text
        else:
            print(f"Error Response: {response.text}")
            return False, response.text
            
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {e}")
        return False, str(e)
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: {e}")
        return False, str(e)
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return False, str(e)

def main():
    """Main test function"""
    print(f"Analytics Endpoints Test - {datetime.now()}")
    print(f"Testing against: {BASE_URL}")
    
    # Test endpoints that were failing
    endpoints_to_test = [
        ("/api/analytics/jobs", "Analytics Jobs Endpoint"),
        ("/api/analytics/user", "Analytics User Endpoint"),
        ("/api/analytics/dashboard", "Analytics Dashboard Endpoint"),
        ("/health", "Health Check Endpoint"),
        ("/api/health", "API Health Check Endpoint")
    ]
    
    results = {}
    
    for endpoint, description in endpoints_to_test:
        success, data = test_endpoint(endpoint, description)
        results[endpoint] = {
            "success": success,
            "data": data
        }
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    for endpoint, result in results.items():
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"{endpoint}: {status}")
    
    # Check if the problematic endpoints are working
    jobs_working = results.get("/api/analytics/jobs", {}).get("success", False)
    user_working = results.get("/api/analytics/user", {}).get("success", False)
    
    if jobs_working and user_working:
        print("\n🎉 SUCCESS: Both analytics endpoints are working!")
    else:
        print("\n⚠️  ISSUES DETECTED:")
        if not jobs_working:
            print("   - /api/analytics/jobs is not working")
        if not user_working:
            print("   - /api/analytics/user is not working")
    
    return results

if __name__ == "__main__":
    main()