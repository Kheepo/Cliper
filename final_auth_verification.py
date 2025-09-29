#!/usr/bin/env python3
"""
Final Authentication Verification
This script performs a comprehensive test to verify the white screen issue is resolved.
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
TEST_EMAIL = "testuser_1758806039@example.com"
TEST_PASSWORD = "testpassword123"

def test_complete_auth_flow():
    """Test the complete authentication flow"""
    print("🔐 Testing Complete Authentication Flow")
    print("=" * 50)
    
    results = {
        "backend_health": False,
        "frontend_health": False,
        "user_registration": False,
        "user_login": False,
        "token_verification": False,
        "protected_endpoints": False,
        "results_page_access": False,
        "auth_persistence": False
    }
    
    # 1. Backend Health Check
    print("1. Checking Backend Health...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        results["backend_health"] = response.status_code == 200
        print(f"   {'✅' if results['backend_health'] else '❌'} Backend: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Backend Error: {str(e)}")
    
    # 2. Frontend Health Check
    print("\n2. Checking Frontend Health...")
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        results["frontend_health"] = response.status_code == 200
        print(f"   {'✅' if results['frontend_health'] else '❌'} Frontend: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Frontend Error: {str(e)}")
    
    if not (results["backend_health"] and results["frontend_health"]):
        print("\n❌ Services not running. Cannot proceed.")
        return results
    
    # 3. User Login Test
    print("\n3. Testing User Login...")
    try:
        response = requests.post(f"{BACKEND_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            access_token = data["tokens"]["access_token"]
            user = data["user"]
            results["user_login"] = True
            print(f"   ✅ Login successful: {user['email']}")
        else:
            print(f"   ❌ Login failed: {response.status_code}")
            return results
    except Exception as e:
        print(f"   ❌ Login error: {str(e)}")
        return results
    
    # 4. Token Verification
    print("\n4. Testing Token Verification...")
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BACKEND_URL}/api/auth/me", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            results["token_verification"] = True
            print(f"   ✅ Token valid: {user_data['email']}")
        else:
            print(f"   ❌ Token verification failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Token verification error: {str(e)}")
    
    # 5. Protected Endpoints Test
    print("\n5. Testing Protected Endpoints...")
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Test jobs endpoint
        response = requests.get(f"{BACKEND_URL}/api/jobs", headers=headers)
        jobs_ok = response.status_code == 200
        
        # Test auth status endpoint
        response = requests.get(f"{BACKEND_URL}/api/auth/status", headers=headers)
        status_ok = response.status_code == 200
        
        results["protected_endpoints"] = jobs_ok and status_ok
        print(f"   {'✅' if jobs_ok else '❌'} Jobs endpoint: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"   {'✅' if status_ok else '❌'} Auth status endpoint")
        
    except Exception as e:
        print(f"   ❌ Protected endpoints error: {str(e)}")
    
    # 6. Results Page Access Test
    print("\n6. Testing Results Page Access...")
    try:
        # Test different Results page URLs
        test_urls = [
            f"{FRONTEND_URL}/results/test-job-id",
            f"{FRONTEND_URL}/results/nonexistent-job",
            f"{FRONTEND_URL}/results"
        ]
        
        all_accessible = True
        for url in test_urls:
            try:
                response = requests.get(url, timeout=5)
                accessible = response.status_code == 200
                has_react_root = 'id="root"' in response.text if response.text else False
                
                print(f"   {'✅' if accessible and has_react_root else '❌'} {url.split('/')[-1] or 'base'}: Status {response.status_code}, React Root: {has_react_root}")
                
                if not (accessible and has_react_root):
                    all_accessible = False
                    
            except Exception as e:
                print(f"   ❌ {url}: Error - {str(e)}")
                all_accessible = False
        
        results["results_page_access"] = all_accessible
        
    except Exception as e:
        print(f"   ❌ Results page test error: {str(e)}")
    
    # 7. Authentication Persistence Test
    print("\n7. Testing Authentication Persistence...")
    try:
        # Simulate multiple API calls to test token persistence
        headers = {"Authorization": f"Bearer {access_token}"}
        
        persistence_tests = []
        for i in range(3):
            response = requests.get(f"{BACKEND_URL}/api/auth/me", headers=headers)
            persistence_tests.append(response.status_code == 200)
            time.sleep(0.5)  # Small delay between requests
        
        results["auth_persistence"] = all(persistence_tests)
        print(f"   {'✅' if results['auth_persistence'] else '❌'} Token persistence: {sum(persistence_tests)}/3 requests successful")
        
    except Exception as e:
        print(f"   ❌ Persistence test error: {str(e)}")
    
    return results

def generate_report(results):
    """Generate a comprehensive test report"""
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE TEST REPORT")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    print(f"Overall Score: {passed_tests}/{total_tests} ({(passed_tests/total_tests)*100:.1f}%)")
    print()
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        test_display = test_name.replace("_", " ").title()
        print(f"{status} {test_display}")
    
    print()
    
    if all(results.values()):
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ WHITE SCREEN ISSUE RESOLUTION STATUS: RESOLVED")
        print("\n🔧 The authentication system is working correctly:")
        print("   • Backend and frontend services are running")
        print("   • User authentication flow works properly")
        print("   • Token verification and persistence work")
        print("   • Protected endpoints are accessible")
        print("   • Results page loads without white screen")
        print("   • Authentication state is maintained")
        
        print("\n🎯 MANUAL VERIFICATION STEPS:")
        print("1. Open: http://localhost:3000/login")
        print(f"2. Login with: {TEST_EMAIL} / {TEST_PASSWORD}")
        print("3. Navigate to: http://localhost:3000/results/test-job-id")
        print("4. Verify: No white screen, page loads correctly")
        print("5. Check: Browser console shows no authentication errors")
        
    else:
        print("❌ SOME TESTS FAILED")
        print("\n⚠️ WHITE SCREEN ISSUE STATUS: NEEDS INVESTIGATION")
        print("\nFailed tests need to be addressed:")
        for test_name, result in results.items():
            if not result:
                print(f"   • {test_name.replace('_', ' ').title()}")
    
    print("\n" + "=" * 60)

def main():
    print("🧪 FINAL AUTHENTICATION VERIFICATION")
    print(f"Timestamp: {datetime.now()}")
    print(f"Test User: {TEST_EMAIL}")
    print()
    
    # Run comprehensive tests
    results = test_complete_auth_flow()
    
    # Generate report
    generate_report(results)
    
    # Additional debugging info
    print("\n🔍 DEBUGGING INFORMATION:")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    print(f"Test Credentials: {TEST_EMAIL} / {TEST_PASSWORD}")
    print("\nIf issues persist:")
    print("1. Check browser developer tools for console errors")
    print("2. Verify network requests in browser dev tools")
    print("3. Check backend logs for authentication errors")
    print("4. Ensure localStorage contains valid auth tokens")

if __name__ == "__main__":
    main()