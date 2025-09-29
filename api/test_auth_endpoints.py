#!/usr/bin/env python3
"""
Comprehensive test script for authentication endpoints.
Tests user registration, login, and profile endpoint to verify the auth_id field fix.
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER = {
    "email": f"test_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
    "password": "TestPassword123!",
    "full_name": "Test User"
}

def print_test_result(test_name, success, details=None):
    """Print formatted test result."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {test_name}")
    if details:
        print(f"   Details: {details}")
    print()

def test_user_registration():
    """Test user registration endpoint."""
    print("🔍 Testing User Registration...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=TEST_USER,
            headers={"Content-Type": "application/json"}
        )
        
        success = response.status_code == 201
        details = f"Status: {response.status_code}"
        
        if success:
            data = response.json()
            details += f", User ID: {data.get('user', {}).get('id', 'N/A')}"
            return True, data
        else:
            details += f", Error: {response.text}"
            return False, None
            
    except Exception as e:
        print_test_result("User Registration", False, f"Exception: {str(e)}")
        return False, None
    
    finally:
        print_test_result("User Registration", success, details)

def test_user_login():
    """Test user login endpoint."""
    print("🔍 Testing User Login...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            },
            headers={"Content-Type": "application/json"}
        )
        
        success = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if success:
            data = response.json()
            access_token = data.get('access_token')
            details += f", Token received: {'Yes' if access_token else 'No'}"
            return True, access_token
        else:
            details += f", Error: {response.text}"
            return False, None
            
    except Exception as e:
        print_test_result("User Login", False, f"Exception: {str(e)}")
        return False, None
    
    finally:
        print_test_result("User Login", success, details)

def test_profile_endpoint(access_token):
    """Test /api/auth/me endpoint with authentication."""
    print("🔍 Testing Profile Endpoint (/api/auth/me)...")
    
    if not access_token:
        print_test_result("Profile Endpoint", False, "No access token available")
        return False
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        
        success = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if success:
            data = response.json()
            user_email = data.get('email')
            user_id = data.get('id')
            details += f", Email: {user_email}, User ID: {user_id}"
            
            # Verify the response contains expected fields
            expected_fields = ['id', 'email', 'created_at']
            missing_fields = [field for field in expected_fields if field not in data]
            
            if missing_fields:
                details += f", Missing fields: {missing_fields}"
                success = False
            else:
                details += ", All expected fields present"
                
        else:
            details += f", Error: {response.text}"
            
        print_test_result("Profile Endpoint", success, details)
        return success
        
    except Exception as e:
        print_test_result("Profile Endpoint", False, f"Exception: {str(e)}")
        return False

def test_profile_without_auth():
    """Test /api/auth/me endpoint without authentication (should fail)."""
    print("🔍 Testing Profile Endpoint without Authentication...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 Unauthorized
        success = response.status_code == 401
        details = f"Status: {response.status_code} (Expected: 401)"
        
        if not success:
            details += f", Unexpected response: {response.text}"
            
        print_test_result("Profile Endpoint (No Auth)", success, details)
        return success
        
    except Exception as e:
        print_test_result("Profile Endpoint (No Auth)", False, f"Exception: {str(e)}")
        return False

def test_server_health():
    """Test if the server is running and accessible."""
    print("🔍 Testing Server Health...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        success = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if success:
            data = response.json()
            details += f", Server status: {data.get('status', 'unknown')}"
        else:
            details += f", Error: {response.text}"
            
        print_test_result("Server Health", success, details)
        return success
        
    except Exception as e:
        print_test_result("Server Health", False, f"Exception: {str(e)}")
        return False

def main():
    """Run all authentication tests."""
    print("🚀 Starting Authentication Endpoint Tests")
    print(f"📍 Base URL: {BASE_URL}")
    print(f"👤 Test User: {TEST_USER['email']}")
    print("=" * 60)
    
    # Test server health first
    if not test_server_health():
        print("❌ Server is not accessible. Exiting tests.")
        sys.exit(1)
    
    # Test registration
    reg_success, reg_data = test_user_registration()
    if not reg_success:
        print("❌ Registration failed. Cannot proceed with login tests.")
        sys.exit(1)
    
    # Test login
    login_success, access_token = test_user_login()
    if not login_success:
        print("❌ Login failed. Cannot proceed with profile tests.")
        sys.exit(1)
    
    # Test profile endpoint with authentication
    profile_success = test_profile_endpoint(access_token)
    
    # Test profile endpoint without authentication
    no_auth_success = test_profile_without_auth()
    
    # Summary
    print("=" * 60)
    print("📊 Test Summary:")
    print(f"   Registration: {'✅' if reg_success else '❌'}")
    print(f"   Login: {'✅' if login_success else '❌'}")
    print(f"   Profile (with auth): {'✅' if profile_success else '❌'}")
    print(f"   Profile (no auth): {'✅' if no_auth_success else '❌'}")
    
    all_passed = all([reg_success, login_success, profile_success, no_auth_success])
    
    if all_passed:
        print("\n🎉 All tests passed! The auth_id field fix has resolved the database lookup issue.")
        print("✅ The /api/auth/me endpoint now returns 200 status instead of 500 error.")
    else:
        print("\n⚠️  Some tests failed. Please check the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()