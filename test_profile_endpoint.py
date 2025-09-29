#!/usr/bin/env python3
"""
Test script to verify the profile endpoint fix.
This script tests:
1. User registration
2. User login
3. Profile endpoint (/api/auth/me) with proper authentication
4. Verifies 200 status instead of previous 500 error
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER = {
    "username": "testuser_profile",
    "email": "testuser_profile@example.com",
    "password": "TestPassword123!"
}

def print_status(message, status="INFO"):
    """Print formatted status message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {status}: {message}")

def test_registration():
    """Test user registration"""
    print_status("Testing user registration...")
    
    url = f"{BASE_URL}/api/auth/register"
    response = requests.post(url, json=TEST_USER)
    
    print_status(f"Registration response status: {response.status_code}")
    
    if response.status_code == 201:
        print_status("✅ Registration successful", "SUCCESS")
        return True
    elif response.status_code == 400:
        try:
            error_data = response.json()
            if "already exists" in str(error_data).lower():
                print_status("User already exists, proceeding with login", "INFO")
                return True
        except:
            pass
        print_status(f"❌ Registration failed: {response.text}", "ERROR")
        return False
    else:
        print_status(f"❌ Registration failed with status {response.status_code}: {response.text}", "ERROR")
        return False

def test_login():
    """Test user login and return access token"""
    print_status("Testing user login...")
    
    url = f"{BASE_URL}/api/auth/login"
    login_data = {
        "username": TEST_USER["username"],
        "password": TEST_USER["password"]
    }
    
    response = requests.post(url, json=login_data)
    
    print_status(f"Login response status: {response.status_code}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            access_token = data.get("access_token")
            if access_token:
                print_status("✅ Login successful, token obtained", "SUCCESS")
                return access_token
            else:
                print_status("❌ Login response missing access_token", "ERROR")
                print_status(f"Response data: {data}")
                return None
        except json.JSONDecodeError:
            print_status(f"❌ Invalid JSON response: {response.text}", "ERROR")
            return None
    else:
        print_status(f"❌ Login failed with status {response.status_code}: {response.text}", "ERROR")
        return None

def test_profile_endpoint(access_token):
    """Test the profile endpoint with authentication"""
    print_status("Testing profile endpoint (/api/auth/me)...")
    
    url = f"{BASE_URL}/api/auth/me"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    print_status(f"Profile endpoint response status: {response.status_code}")
    
    if response.status_code == 200:
        try:
            profile_data = response.json()
            print_status("✅ Profile endpoint working correctly!", "SUCCESS")
            print_status(f"Profile data received: {json.dumps(profile_data, indent=2)}")
            
            # Verify expected fields
            expected_fields = ["id", "username", "email"]
            missing_fields = [field for field in expected_fields if field not in profile_data]
            
            if missing_fields:
                print_status(f"⚠️  Missing expected fields: {missing_fields}", "WARNING")
            else:
                print_status("✅ All expected profile fields present", "SUCCESS")
            
            return True
        except json.JSONDecodeError:
            print_status(f"❌ Invalid JSON response: {response.text}", "ERROR")
            return False
    elif response.status_code == 500:
        print_status("❌ Profile endpoint still returning 500 error - fix not working", "ERROR")
        print_status(f"Error response: {response.text}")
        return False
    else:
        print_status(f"❌ Profile endpoint failed with status {response.status_code}: {response.text}", "ERROR")
        return False

def test_health_endpoint():
    """Test server health endpoint"""
    print_status("Testing server health...")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_status("✅ Server is healthy", "SUCCESS")
            return True
        else:
            print_status(f"❌ Health check failed: {response.status_code}", "ERROR")
            return False
    except requests.exceptions.RequestException as e:
        print_status(f"❌ Cannot connect to server: {e}", "ERROR")
        return False

def main():
    """Main test function"""
    print_status("Starting profile endpoint test suite", "INFO")
    print_status(f"Testing against: {BASE_URL}")
    print("=" * 60)
    
    # Test server health first
    if not test_health_endpoint():
        print_status("Server health check failed, aborting tests", "ERROR")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Test registration
    if not test_registration():
        print_status("Registration test failed, aborting", "ERROR")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Test login
    access_token = test_login()
    if not access_token:
        print_status("Login test failed, aborting", "ERROR")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Test profile endpoint
    if test_profile_endpoint(access_token):
        print("\n" + "=" * 60)
        print_status("🎉 ALL TESTS PASSED! Profile endpoint fix verified", "SUCCESS")
        print_status("The auth_id field fix has resolved the database lookup issue", "SUCCESS")
    else:
        print("\n" + "=" * 60)
        print_status("❌ Profile endpoint test failed", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()