#!/usr/bin/env python3
"""
Test script to verify the upload functionality after fixing the user ID mapping issue.
"""

import requests
import json
import os
from io import BytesIO

# Configuration
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api"

# Test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def test_api_health():
    """Test API health endpoint"""
    print("\n=== Testing API Health ===")
    try:
        response = requests.get(f"{API_URL}/health", timeout=10)
        print(f"Health check status: {response.status_code}")
        if response.status_code == 200:
            print(f"Health check response: {response.json()}")
            return True
        else:
            print(f"Health check failed: {response.text}")
            return False
    except Exception as e:
        print(f"Health check error: {e}")
        return False

def test_unauthenticated_upload():
    """Test upload without authentication (should fail)"""
    print("\n=== Testing Unauthenticated Upload ===")
    try:
        # Create a small test file
        test_content = b"fake video content for testing"
        files = {'file': ('test.mp4', BytesIO(test_content), 'video/mp4')}
        
        response = requests.post(f"{API_URL}/videos/upload", files=files, timeout=30)
        print(f"Unauthenticated upload status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 403:
            print("✓ Correctly rejected unauthenticated upload")
            return True
        else:
            print("✗ Unexpected response for unauthenticated upload")
            return False
    except Exception as e:
        print(f"Unauthenticated upload error: {e}")
        return False

def login_and_get_token():
    """Login and extract token from response"""
    print("\n=== Logging In ===")
    try:
        login_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        response = requests.post(f"{API_URL}/auth/login", json=login_data, timeout=10)
        print(f"Login status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            if token:
                print(f"✓ Login successful, token extracted: {token[:20]}...")
                return token
            else:
                print("✗ No token in login response")
                print(f"Response: {data}")
                return None
        else:
            print(f"✗ Login failed: {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def test_authenticated_upload(token):
    """Test upload with authentication"""
    print("\n=== Testing Authenticated Upload ===")
    try:
        # Create a small test file
        test_content = b"fake video content for testing upload with proper user mapping"
        files = {'file': ('test_fixed.mp4', BytesIO(test_content), 'video/mp4')}
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        print("Sending authenticated upload request...")
        response = requests.post(
            f"{API_URL}/videos/upload", 
            files=files, 
            headers=headers, 
            timeout=60
        )
        
        print(f"Authenticated upload status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Upload successful!")
            print(f"Job ID: {data.get('job_id')}")
            print(f"File URL: {data.get('file_url')}")
            print(f"Task ID: {data.get('task_id')}")
            return True
        else:
            print(f"✗ Upload failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
            except:
                print(f"Raw error response: {response.text}")
            return False
            
    except Exception as e:
        print(f"Authenticated upload error: {e}")
        return False

def main():
    """Main test function"""
    print("Starting upload functionality test after user ID mapping fix...")
    
    # Test 1: API Health
    if not test_api_health():
        print("\n❌ API health check failed. Stopping tests.")
        return
    
    # Test 2: Unauthenticated upload (should fail)
    test_unauthenticated_upload()
    
    # Test 3: Login
    token = login_and_get_token()
    if not token:
        print("\n❌ Login failed. Cannot test authenticated upload.")
        return
    
    # Test 4: Authenticated upload (should now work)
    if test_authenticated_upload(token):
        print("\n✅ All tests passed! Upload functionality is working correctly.")
    else:
        print("\n❌ Authenticated upload still failing. Need further investigation.")

if __name__ == "__main__":
    main()