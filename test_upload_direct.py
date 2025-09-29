#!/usr/bin/env python3
"""
Direct API upload test to diagnose the exact error
"""

import requests
import json
import os
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

def test_health():
    """Test API health endpoint"""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=30)
        print(f"Health check: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def register_test_user():
    """Register a test user and get auth token"""
    try:
        # Try to login first (user might already exist)
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        response = requests.post(f"{API_BASE}/auth/login", json=login_data, timeout=30)
        print(f"Login attempt: {response.status_code}")
        print(f"Login response: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            # Try different token locations
            token = (response_data.get('access_token') or 
                    response_data.get('token') or 
                    (response_data.get('tokens', {}).get('access_token')))
            if token:
                print(f"Got auth token: {token[:20]}...")
                return token
            else:
                print(f"No token in response: {response_data}")
                return None
        
        # If login failed, try to register
        print("Login failed, attempting registration...")
        register_data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "full_name": "Test User"
        }
        
        response = requests.post(f"{API_BASE}/auth/register", json=register_data, timeout=30)
        print(f"Registration: {response.status_code}")
        
        if response.status_code in [200, 201]:
             # Try login again after registration
             response = requests.post(f"{API_BASE}/auth/login", json=login_data, timeout=30)
             if response.status_code == 200:
                 response_data = response.json()
                 # Try different token locations
                 token = (response_data.get('access_token') or 
                         response_data.get('token') or 
                         (response_data.get('tokens', {}).get('access_token')))
                 if token:
                     print(f"Got auth token after registration: {token[:20]}...")
                     return token
                 else:
                     print(f"No token in login response: {response_data}")
                     return None
        
        print(f"Auth process failed: {response.text}")
        return None
            
    except Exception as e:
        print(f"Auth failed: {e}")
        return None

def create_test_video_file():
    """Create a small test video file"""
    test_file = Path("test_video.mp4")
    
    # Create a minimal MP4 file (just header bytes)
    mp4_header = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free'
    
    with open(test_file, 'wb') as f:
        f.write(mp4_header)
        f.write(b'\x00' * 1000)  # Add some padding
    
    return test_file

def test_upload_with_token(token):
    """Test file upload with authentication"""
    test_file = None
    try:
        # Create test file
        test_file = create_test_video_file()
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # Test multipart upload
        with open(test_file, 'rb') as f:
            files = {
                'file': ('test_video.mp4', f, 'video/mp4')
            }
            data = {
                'title': 'Test Video',
                'description': 'Test upload'
            }
            
            print("Attempting upload...")
            response = requests.post(
                f"{API_BASE}/videos/upload",
                files=files,
                data=data,
                headers=headers,
                timeout=60
            )
            
            print(f"Upload response: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response body: {response.text}")
            
        # Clean up after closing file
        if test_file and test_file.exists():
            test_file.unlink()
            
        return response.status_code, response.text
            
    except Exception as e:
        print(f"Upload test failed: {e}")
        if test_file and test_file.exists():
            try:
                test_file.unlink()
            except:
                pass
        return None, str(e)

def test_upload_without_auth():
    """Test upload without authentication to see the error"""
    test_file = None
    try:
        test_file = create_test_video_file()
        
        with open(test_file, 'rb') as f:
            files = {
                'file': ('test_video.mp4', f, 'video/mp4')
            }
            data = {
                'title': 'Test Video',
                'description': 'Test upload'
            }
            
            print("Testing upload without auth...")
            response = requests.post(
                f"{API_BASE}/videos/upload",
                files=files,
                data=data,
                timeout=60
            )
            
            print(f"No-auth upload: {response.status_code}")
            print(f"Response: {response.text}")
            
        # Clean up after closing file
        if test_file and test_file.exists():
            test_file.unlink()
        return response.status_code, response.text
            
    except Exception as e:
        print(f"No-auth upload failed: {e}")
        if test_file and test_file.exists():
            try:
                test_file.unlink()
            except:
                pass
        return None, str(e)

def main():
    print("=== Direct API Upload Test ===")
    
    # Test 1: Health check
    print("\n1. Testing API health...")
    if not test_health():
        print("API is not responding. Exiting.")
        return
    
    # Test 2: Upload without auth
    print("\n2. Testing upload without authentication...")
    test_upload_without_auth()
    
    # Test 3: Get auth token
    print("\n3. Getting authentication token...")
    token = register_test_user()
    
    if not token:
        print("Could not get auth token. Exiting.")
        return
    
    # Test 4: Upload with auth
    print("\n4. Testing upload with authentication...")
    status, response = test_upload_with_token(token)
    
    print(f"\nFinal result: {status}")
    print(f"Response: {response}")

if __name__ == "__main__":
    main()