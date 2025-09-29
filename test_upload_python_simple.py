#!/usr/bin/env python3
"""
Simple Python test for video upload endpoint
"""

import requests
import io

def test_upload():
    print("=== PYTHON VIDEO UPLOAD TEST ===")
    
    # Step 1: Register user and get token
    print("1. Registering new user...")
    register_data = {
        "email": f"test_user_{hash('test')}@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User"
    }
    
    register_response = requests.post(
        'http://localhost:8000/api/auth/register',
        json=register_data
    )
    
    if register_response.status_code not in [200, 201]:
        print(f"✗ Registration failed: {register_response.status_code}")
        print(f"Response: {register_response.text}")
        return False
    
    response_data = register_response.json()
    # Handle different response formats
    if 'access_token' in response_data:
        token = response_data['access_token']
    elif 'tokens' in response_data and 'access_token' in response_data['tokens']:
        token = response_data['tokens']['access_token']
    else:
        print(f"✗ No access token found in response: {response_data}")
        return False
    print(f"✓ User registered, token: {token[:20]}...")
    
    # Step 2: Create test video content
    print("2. Creating test video content...")
    # Create minimal MP4 content
    mp4_content = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free'
    
    # Step 3: Upload video
    print("3. Uploading video...")
    files = {
        'file': ('test_video.mp4', io.BytesIO(mp4_content), 'video/mp4')
    }
    data = {
        'title': 'Python Test Video',
        'description': 'Test video uploaded via Python'
    }
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    upload_response = requests.post(
        'http://localhost:8000/api/jobs/upload',
        files=files,
        data=data,
        headers=headers
    )
    
    print(f"Upload response status: {upload_response.status_code}")
    
    if upload_response.status_code in [200, 201]:
        upload_data = upload_response.json()
        print("✓ SUCCESS! Upload completed")
        print(f"Job ID: {upload_data.get('id')}")
        print(f"Job Status: {upload_data.get('status')}")
        print(f"Title: {upload_data.get('title')}")
        return True
    else:
        print("✗ Upload failed")
        print(f"Error: {upload_response.text}")
        return False

if __name__ == "__main__":
    try:
        success = test_upload()
        if success:
            print("\n=== TEST RESULT ===")
            print("✓ PYTHON VIDEO UPLOAD TEST PASSED")
        else:
            print("\n=== TEST RESULT ===")
            print("✗ PYTHON VIDEO UPLOAD TEST FAILED")
    except Exception as e:
        print(f"\n=== TEST RESULT ===")
        print(f"✗ PYTHON VIDEO UPLOAD TEST FAILED: {e}")