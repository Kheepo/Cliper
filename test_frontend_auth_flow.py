#!/usr/bin/env python3
"""
Test Frontend Authentication Flow
This script simulates the complete frontend authentication flow including login and Results page access.
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

# Test credentials from previous test
TEST_EMAIL = "testuser_1758806039@example.com"
TEST_PASSWORD = "testpassword123"

def simulate_frontend_login():
    """Simulate frontend login process"""
    print("🔐 Simulating Frontend Login Process...")
    
    # Step 1: Login via API (simulating what frontend does)
    try:
        response = requests.post(f"{BACKEND_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            access_token = data["tokens"]["access_token"]
            user = data["user"]
            
            print(f"   ✅ Login successful")
            print(f"   User: {user['email']} (ID: {user['id']})")
            print(f"   Token: {access_token[:20]}...")
            
            return {
                "success": True,
                "access_token": access_token,
                "user": user
            }
        else:
            print(f"   ❌ Login failed: {response.status_code} - {response.text}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        print(f"   ❌ Login error: {str(e)}")
        return {"success": False, "error": str(e)}

def test_authenticated_api_calls(access_token):
    """Test API calls that the Results page would make"""
    print("\n📡 Testing Authenticated API Calls...")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test 1: Get user profile (auth verification)
    try:
        response = requests.get(f"{BACKEND_URL}/api/auth/me", headers=headers)
        if response.status_code == 200:
            user_data = response.json()
            print(f"   ✅ User profile: {user_data['email']}")
        else:
            print(f"   ❌ User profile failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ User profile error: {str(e)}")
    
    # Test 2: Get jobs list
    try:
        response = requests.get(f"{BACKEND_URL}/api/jobs", headers=headers)
        if response.status_code == 200:
            jobs = response.json()
            print(f"   ✅ Jobs list: {len(jobs)} jobs found")
        else:
            print(f"   ❌ Jobs list failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Jobs list error: {str(e)}")
    
    # Test 3: Try to get a specific job result (this might fail, but should not be auth error)
    try:
        test_job_id = "test-job-id"
        response = requests.get(f"{BACKEND_URL}/api/jobs/{test_job_id}/result", headers=headers)
        if response.status_code == 404:
            print(f"   ✅ Job result endpoint accessible (404 expected for non-existent job)")
        elif response.status_code == 200:
            print(f"   ✅ Job result found")
        elif response.status_code == 401:
            print(f"   ❌ Job result auth failed: 401 Unauthorized")
        else:
            print(f"   ⚠️ Job result unexpected status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Job result error: {str(e)}")

def test_frontend_pages_with_auth():
    """Test frontend pages that require authentication"""
    print("\n🌐 Testing Frontend Pages...")
    
    # Test pages that should be accessible
    pages = {
        "/": "Home page",
        "/login": "Login page",
        "/register": "Register page",
        "/dashboard": "Dashboard page",
        "/results/test-job-id": "Results page"
    }
    
    for path, description in pages.items():
        try:
            response = requests.get(f"{FRONTEND_URL}{path}", timeout=5)
            if response.status_code == 200:
                # Check if it's the React app
                is_react_app = "React App" in response.text
                has_root_div = 'id="root"' in response.text
                
                print(f"   ✅ {description}: Accessible (React: {is_react_app}, Root: {has_root_div})")
            else:
                print(f"   ❌ {description}: Status {response.status_code}")
        except Exception as e:
            print(f"   ❌ {description}: Error - {str(e)}")

def create_test_job(access_token):
    """Create a test job to have real data for Results page"""
    print("\n🎬 Creating Test Job...")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Create a simple test job
    job_data = {
        "video_url": "https://example.com/test-video.mp4",
        "title": "Test Video for Results Page",
        "description": "This is a test video to verify Results page functionality"
    }
    
    try:
        response = requests.post(f"{BACKEND_URL}/api/jobs", json=job_data, headers=headers)
        
        if response.status_code == 200:
            job = response.json()
            job_id = job.get("id") or job.get("job_id")
            print(f"   ✅ Test job created: {job_id}")
            return job_id
        else:
            print(f"   ❌ Job creation failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Job creation error: {str(e)}")
        return None

def test_results_page_data(access_token, job_id):
    """Test if Results page can get data for a real job"""
    if not job_id:
        print("\n⚠️ Skipping Results page data test (no job ID)")
        return
    
    print(f"\n📊 Testing Results Page Data for Job: {job_id}...")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test getting job details
    try:
        response = requests.get(f"{BACKEND_URL}/api/jobs/{job_id}", headers=headers)
        if response.status_code == 200:
            job_data = response.json()
            print(f"   ✅ Job details: {job_data.get('title', 'No title')}")
        else:
            print(f"   ❌ Job details failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Job details error: {str(e)}")
    
    # Test getting job results
    try:
        response = requests.get(f"{BACKEND_URL}/api/jobs/{job_id}/result", headers=headers)
        if response.status_code == 200:
            print(f"   ✅ Job results available")
        elif response.status_code == 404:
            print(f"   ⚠️ Job results not ready yet (404)")
        elif response.status_code == 401:
            print(f"   ❌ Job results auth failed (401)")
        else:
            print(f"   ⚠️ Job results status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Job results error: {str(e)}")

def main():
    print("🧪 Frontend Authentication Flow Test")
    print("=" * 50)
    print(f"Timestamp: {datetime.now()}")
    print(f"Test User: {TEST_EMAIL}")
    print()
    
    # Step 1: Simulate frontend login
    login_result = simulate_frontend_login()
    
    if not login_result["success"]:
        print("\n❌ Login failed. Cannot proceed with authentication tests.")
        return
    
    access_token = login_result["access_token"]
    user = login_result["user"]
    
    # Step 2: Test authenticated API calls
    test_authenticated_api_calls(access_token)
    
    # Step 3: Test frontend pages
    test_frontend_pages_with_auth()
    
    # Step 4: Create a test job
    job_id = create_test_job(access_token)
    
    # Step 5: Test Results page data
    test_results_page_data(access_token, job_id)
    
    # Summary and next steps
    print("\n" + "=" * 50)
    print("🎯 MANUAL TESTING INSTRUCTIONS")
    print("=" * 50)
    print("1. Open browser to: http://localhost:3000/login")
    print(f"2. Login with:")
    print(f"   Email: {TEST_EMAIL}")
    print(f"   Password: {TEST_PASSWORD}")
    print("3. After login, navigate to: /dashboard")
    print("4. Then navigate to: /results/test-job-id")
    if job_id:
        print(f"5. Or try the real job: /results/{job_id}")
    print("6. Check browser console for any errors")
    print("7. Verify that the Results page loads without white screen")
    print()
    print("🔍 What to look for:")
    print("- No white screen on Results page")
    print("- User authentication state is maintained")
    print("- API calls work with proper authorization headers")
    print("- No 401 Unauthorized errors in browser console")

if __name__ == "__main__":
    main()