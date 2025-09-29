#!/usr/bin/env python3
"""
Simple test script for clip generation endpoint
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8001"
TEST_VIDEO_ID = "d7f443ef-d227-4a73-803f-e603f63bf242"  # From database query - completed video

def register_user():
    """Register a test user and get token"""
    print("1. Getting user token...")
    
    import time
    unique_email = f"cliptest{int(time.time())}@example.com"
    
    user_data = {
        "email": unique_email,
        "password": "testpass123",
        "full_name": "Clip Test User"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
    
    if response.status_code in [200, 201]:
        data = response.json()
        token = data.get('tokens', {}).get('access_token')
        print(f"✓ User registered, token: {token[:20]}...")
        return token
    elif response.status_code == 400 and "already registered" in response.text:
        # Try to login instead
        print("User already exists, trying to login...")
        login_data = {
            "email": "cliptest@example.com",
            "password": "testpass123"
        }
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        if login_response.status_code in [200, 201]:
            data = login_response.json()
            token = data.get('tokens', {}).get('access_token')
            print(f"✓ User logged in, token: {token[:20]}...")
            return token
    
    print(f"✗ Authentication failed: {response.status_code}")
    print(f"Response: {response.text}")
    return None

def test_clip_generation_videos_endpoint(token, video_id):
    """Test the /api/videos/{video_id}/clips endpoint"""
    print(f"\n2. Testing videos clip generation endpoint...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test data for form submission - send lists properly for FastAPI
    data = [
        ("segment_ids", "segment1"),
        ("segment_ids", "segment2"),
        ("platforms", "youtube"),
        ("platforms", "tiktok")
    ]
    
    response = requests.post(
        f"{BASE_URL}/api/videos/{video_id}/clips",
        data=data,
        headers=headers
    )
    
    print(f"Videos endpoint response status: {response.status_code}")
    print(f"Videos endpoint response: {response.text}")
    
    return response.status_code in [200, 201]

def test_clip_generation_clips_endpoint(token, video_id):
    """Test the clips generation endpoint"""
    print("3. Testing clips generation endpoint...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Use the actual video UUID from the database
    clip_data = {
        "video_id": video_id,  # Using UUID as expected by the database
        "clip_type": "highlight",
        "target_duration": 30.0,
        "custom_parameters": {}
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clips/generate", json=clip_data, headers=headers)
    
    print(f"Clips endpoint response status: {response.status_code}")
    print(f"Clips endpoint response: {response.text}")
    
    return response.status_code in [200, 201]

def main():
    """Run clip generation tests"""
    print("=== CLIP GENERATION TEST ===")
    
    # Register user and get token
    token = register_user()
    if not token:
        print("✗ CLIP GENERATION TEST FAILED - No token")
        return
    
    # Test videos endpoint
    videos_success = test_clip_generation_videos_endpoint(token, TEST_VIDEO_ID)
    
    # Test clips endpoint
    clips_success = test_clip_generation_clips_endpoint(token, TEST_VIDEO_ID)
    
    # Summary
    print(f"\n=== TEST RESULT ===")
    if videos_success or clips_success:
        print("✓ CLIP GENERATION TEST PASSED")
        if videos_success:
            print("  ✓ Videos endpoint working")
        if clips_success:
            print("  ✓ Clips endpoint working")
    else:
        print("✗ CLIP GENERATION TEST FAILED")
        print("  ✗ Both endpoints failed")

if __name__ == "__main__":
    main()