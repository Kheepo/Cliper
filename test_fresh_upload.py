#!/usr/bin/env python3
"""
Test upload functionality with fresh authentication
"""

import requests
import json
import time
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:8000"

def register_and_login():
    """Register a new user and get fresh tokens"""
    print("=== REGISTERING NEW USER ===")
    
    # Generate unique email
    timestamp = int(time.time())
    email = f"test{timestamp}@example.com"
    password = "testpassword123"
    
    # Register user
    register_data = {
        "email": email,
        "password": password
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=register_data,
            timeout=10
        )
        
        print(f"Registration Status: {response.status_code}")
        print(f"Registration Response: {response.text[:300]}")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"Registration response keys: {list(response_data.keys())}")
            
            # Check for tokens object with access_token
            if 'tokens' in response_data and 'access_token' in response_data['tokens']:
                token = response_data['tokens']['access_token']
                print(f"✅ Successfully obtained token: {token[:20]}...")
                return token
            
            # Fallback: try direct access_token field
            if 'access_token' in response_data:
                token = response_data['access_token']
                print(f"✅ Successfully obtained token: {token[:20]}...")
                return token
            
            print(f"Full registration response: {response_data}")
            print("❌ No token found in registration response")
            return None
        
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Registration error: {e}")
        return None

def test_auth_endpoints(token):
    """Test authentication endpoints"""
    print("\n=== TESTING AUTH ENDPOINTS ===")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Test /api/auth/me
    try:
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=10)
        print(f"Auth/me Status: {response.status_code}")
        print(f"Auth/me Response: {response.text[:200]}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Auth test error: {e}")
        return False

def test_video_upload_endpoints(token):
    """Test video upload endpoints with proper data"""
    print("\n=== TESTING VIDEO UPLOAD ENDPOINTS ===")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Create test file content
    test_content = b"This is a test video file for upload testing. " * 100  # Make it a bit larger
    
    # Test /api/videos/upload with proper multipart data
    print("\nTesting /api/videos/upload with multipart data:")
    
    files = {
        'file': ('test_video.mp4', test_content, 'video/mp4')
    }
    
    data = {
        'target_niche': 'technology',
        'totalChunks': '1',
        'sessionId': f'session-{int(time.time())}',
        'fileName': 'test_video.mp4'
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/videos/upload",
            headers=headers,
            files=files,
            data=data,
            timeout=30
        )
        
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:500]}")
        
        if response.status_code == 200:
            print("  ✅ Upload successful!")
            return True
        else:
            print(f"  ❌ Upload failed with status {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"  Error: {e}")
    
    return False

def test_chunked_upload(token):
    """Test chunked upload endpoint"""
    print("\n=== TESTING CHUNKED UPLOAD ===")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    
    # Test chunk upload
    chunk_data = {
        "sessionId": f"chunk-session-{int(time.time())}",
        "chunkIndex": 0,
        "totalChunks": 1,
        "fileName": "test_video.mp4",
        "fileSize": 1024,
        "chunkData": "dGVzdCBjaHVuayBkYXRh"  # base64 encoded "test chunk data"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/videos/upload-chunk",
            headers=headers,
            json=chunk_data,
            timeout=30
        )
        
        print(f"Chunk upload Status: {response.status_code}")
        print(f"Chunk upload Response: {response.text[:300]}")
        
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"Chunk upload error: {e}")
        return False

def test_frontend_simulation(token):
    """Simulate exactly what the frontend does"""
    print("\n=== SIMULATING FRONTEND UPLOAD ===")
    
    # Simulate XMLHttpRequest from frontend
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Create FormData equivalent
    test_content = b"Mock video content for frontend simulation test"
    
    files = {
        'file': ('test_video.mp4', test_content, 'video/mp4')
    }
    
    data = {
        'target_niche': 'technology'
    }
    
    print("Simulating frontend POST to /api/videos/upload...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/videos/upload",
            headers=headers,
            files=files,
            data=data,
            timeout=30
        )
        
        print(f"Frontend simulation Status: {response.status_code}")
        print(f"Frontend simulation Response: {response.text[:400]}")
        
        if response.status_code == 200:
            print("✅ Frontend simulation successful!")
            return True
        elif response.status_code == 400:
            print("❌ Frontend simulation failed - likely validation issue")
        elif response.status_code == 401:
            print("❌ Frontend simulation failed - authentication issue")
        else:
            print(f"❌ Frontend simulation failed - unexpected status {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"Frontend simulation error: {e}")
    
    return False

def main():
    """Main test function"""
    print("Fresh Upload Test with Authentication")
    print("=" * 50)
    
    # Get fresh token
    token = register_and_login()
    if not token:
        print("❌ Failed to get authentication token")
        return
    
    # Test authentication
    if not test_auth_endpoints(token):
        print("❌ Authentication test failed")
        return
    
    print("✅ Authentication working")
    
    # Test upload endpoints
    upload_success = test_video_upload_endpoints(token)
    chunk_success = test_chunked_upload(token)
    frontend_success = test_frontend_simulation(token)
    
    print("\n=== FINAL RESULTS ===")
    print(f"Video Upload: {'✅ SUCCESS' if upload_success else '❌ FAILED'}")
    print(f"Chunked Upload: {'✅ SUCCESS' if chunk_success else '❌ FAILED'}")
    print(f"Frontend Simulation: {'✅ SUCCESS' if frontend_success else '❌ FAILED'}")
    
    if not any([upload_success, chunk_success, frontend_success]):
        print("\n🔍 DIAGNOSIS: All upload methods failed")
        print("Next steps:")
        print("1. Check backend logs for detailed error messages")
        print("2. Verify ValidationMiddleware content-type allowlist")
        print("3. Check if multipart/form-data is properly handled")
        print("4. Verify upload endpoint implementations")
    else:
        print("\n✅ At least one upload method is working!")

if __name__ == "__main__":
    main()