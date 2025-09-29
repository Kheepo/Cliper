#!/usr/bin/env python3
"""
Direct test of the videos clips endpoint without middleware interference
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

def test_direct_form_submission(token, video_id):
    """Test direct form submission to the videos clips endpoint"""
    print(f"\n2. Testing direct form submission...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try different ways to send the form data
    print("Trying with files parameter (multipart/form-data)...")
    files = {
        'segment_ids': (None, 'segment1'),
        'segment_ids': (None, 'segment2'),
        'platforms': (None, 'youtube'),
        'platforms': (None, 'tiktok')
    }
    
    response = requests.post(
        f"{BASE_URL}/api/videos/{video_id}/clips",
        files=files,
        headers=headers
    )
    
    print(f"Files method - Status: {response.status_code}")
    print(f"Files method - Response: {response.text}")
    
    if response.status_code not in [200, 201]:
        print("\nTrying with data parameter (application/x-www-form-urlencoded)...")
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
        
        print(f"Data method - Status: {response.status_code}")
        print(f"Data method - Response: {response.text}")
    
    return response.status_code in [200, 201]

def main():
    """Run direct endpoint test"""
    print("=== DIRECT ENDPOINT TEST ===")
    
    # Register user and get token
    token = register_user()
    if not token:
        print("✗ DIRECT ENDPOINT TEST FAILED - No token")
        return
    
    # Test direct form submission
    success = test_direct_form_submission(token, TEST_VIDEO_ID)
    
    # Summary
    print(f"\n=== TEST RESULT ===")
    if success:
        print("✓ DIRECT ENDPOINT TEST PASSED")
    else:
        print("✗ DIRECT ENDPOINT TEST FAILED")

if __name__ == "__main__":
    main()