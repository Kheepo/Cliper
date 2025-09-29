#!/usr/bin/env python3
"""
Debug Authentication State for Results Page
This script tests the complete authentication flow and Results page access.
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

def check_backend_health():
    """Check if backend is running"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def check_frontend_health():
    """Check if frontend is running"""
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        return response.status_code == 200
    except:
        return False

def test_user_registration():
    """Test user registration"""
    timestamp = int(time.time())
    email = f"testuser_{timestamp}@example.com"
    password = "testpassword123"
    
    try:
        response = requests.post(f"{BACKEND_URL}/api/auth/register", json={
            "email": email,
            "password": password,
            "full_name": "Test User"
        })
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "email": email,
                "password": password,
                "access_token": data["tokens"]["access_token"],
                "user": data["user"]
            }
        else:
            return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_user_login(email, password):
    """Test user login"""
    try:
        response = requests.post(f"{BACKEND_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "access_token": data["tokens"]["access_token"],
                "user": data["user"]
            }
        else:
            return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_token_verification(access_token):
    """Test token verification"""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BACKEND_URL}/api/auth/me", headers=headers)
        
        if response.status_code == 200:
            return {"success": True, "user": response.json()}
        else:
            return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_auth_status(access_token):
    """Test auth status endpoint"""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BACKEND_URL}/api/auth/status", headers=headers)
        
        if response.status_code == 200:
            return {"success": True, "status": response.json()}
        else:
            return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_protected_endpoint(access_token):
    """Test a protected endpoint"""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BACKEND_URL}/api/jobs", headers=headers)
        
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response": response.text[:200] if response.text else "No content"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_results_endpoint(access_token, job_id="test-job-id"):
    """Test results endpoint"""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BACKEND_URL}/api/jobs/{job_id}/result", headers=headers)
        
        return {
            "success": response.status_code in [200, 404],  # 404 is expected for non-existent job
            "status_code": response.status_code,
            "response": response.text[:200] if response.text else "No content"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_frontend_routes():
    """Test frontend route accessibility"""
    routes = ["/", "/login", "/register", "/dashboard", "/results/test-job-id"]
    results = {}
    
    for route in routes:
        try:
            response = requests.get(f"{FRONTEND_URL}{route}", timeout=5)
            results[route] = {
                "status_code": response.status_code,
                "accessible": response.status_code == 200,
                "title": "React App" in response.text if response.text else False
            }
        except Exception as e:
            results[route] = {"error": str(e), "accessible": False}
    
    return results

def main():
    print("🔍 Authentication & Results Page Debug Test")
    print("=" * 50)
    print(f"Timestamp: {datetime.now()}")
    print()
    
    # 1. Check services
    print("1. Checking Services...")
    backend_ok = check_backend_health()
    frontend_ok = check_frontend_health()
    
    print(f"   Backend (8000): {'✅ Running' if backend_ok else '❌ Not accessible'}")
    print(f"   Frontend (3000): {'✅ Running' if frontend_ok else '❌ Not accessible'}")
    
    if not backend_ok:
        print("\n❌ Backend not running. Please start the backend server.")
        return
    
    if not frontend_ok:
        print("\n❌ Frontend not running. Please start the frontend server.")
        return
    
    print()
    
    # 2. Test user registration
    print("2. Testing User Registration...")
    reg_result = test_user_registration()
    
    if not reg_result["success"]:
        print(f"   ❌ Registration failed: {reg_result['error']}")
        return
    
    print(f"   ✅ User registered: {reg_result['email']}")
    access_token = reg_result["access_token"]
    user_email = reg_result["email"]
    user_password = reg_result["password"]
    print()
    
    # 3. Test token verification
    print("3. Testing Token Verification...")
    verify_result = test_token_verification(access_token)
    
    if verify_result["success"]:
        print(f"   ✅ Token valid, user: {verify_result['user']['email']}")
    else:
        print(f"   ❌ Token verification failed: {verify_result['error']}")
    print()
    
    # 4. Test auth status
    print("4. Testing Auth Status...")
    status_result = test_auth_status(access_token)
    
    if status_result["success"]:
        print(f"   ✅ Auth status OK")
        print(f"   User ID: {status_result['status'].get('user_id', 'N/A')}")
    else:
        print(f"   ❌ Auth status failed: {status_result['error']}")
    print()
    
    # 5. Test protected endpoints
    print("5. Testing Protected Endpoints...")
    
    # Test jobs endpoint
    jobs_result = test_protected_endpoint(access_token)
    print(f"   Jobs endpoint: {'✅' if jobs_result['success'] else '❌'} (Status: {jobs_result.get('status_code', 'N/A')})")
    
    # Test results endpoint
    results_result = test_results_endpoint(access_token)
    print(f"   Results endpoint: {'✅' if results_result['success'] else '❌'} (Status: {results_result.get('status_code', 'N/A')})")
    print()
    
    # 6. Test frontend routes
    print("6. Testing Frontend Routes...")
    frontend_results = test_frontend_routes()
    
    for route, result in frontend_results.items():
        if "error" in result:
            print(f"   {route}: ❌ Error - {result['error']}")
        else:
            status = "✅" if result["accessible"] else "❌"
            print(f"   {route}: {status} (Status: {result['status_code']})")
    print()
    
    # 7. Test login flow
    print("7. Testing Login Flow...")
    login_result = test_user_login(user_email, user_password)
    
    if login_result["success"]:
        print(f"   ✅ Login successful")
        new_token = login_result["access_token"]
        
        # Verify new token
        verify_new = test_token_verification(new_token)
        if verify_new["success"]:
            print(f"   ✅ New token verified")
        else:
            print(f"   ❌ New token verification failed")
    else:
        print(f"   ❌ Login failed: {login_result['error']}")
    print()
    
    # Summary
    print("📋 SUMMARY")
    print("=" * 20)
    print(f"✅ Backend Health: {backend_ok}")
    print(f"✅ Frontend Health: {frontend_ok}")
    print(f"✅ User Registration: {reg_result['success']}")
    print(f"✅ Token Verification: {verify_result['success']}")
    print(f"✅ Auth Status: {status_result['success']}")
    print(f"✅ Protected Endpoints: {jobs_result['success']}")
    print(f"✅ Login Flow: {login_result['success']}")
    print()
    
    if all([backend_ok, frontend_ok, reg_result['success'], verify_result['success'], 
            status_result['success'], jobs_result['success'], login_result['success']]):
        print("🎉 All authentication tests passed!")
        print("\n🔧 NEXT STEPS:")
        print("1. Open browser to http://localhost:3000/login")
        print(f"2. Login with: {user_email} / {user_password}")
        print("3. Navigate to /results/test-job-id to test Results page")
        print("4. Check browser console for any authentication errors")
    else:
        print("❌ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    main()