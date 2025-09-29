#!/usr/bin/env python3
"""
Comprehensive video upload test
"""

import requests
import io
import time
import json

BASE_URL = "http://localhost:8001"

def create_test_video_file():
    """Create a minimal MP4 file for testing"""
    # MP4 file header (ftyp box)
    mp4_header = bytes([
        0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,  # ftyp box
        0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
        0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
        0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31
    ])
    
    # Add some additional data to make it a bit larger
    additional_data = b"test_video_data" * 100
    return mp4_header + additional_data

def register_user():
    """Register a test user and get token"""
    print("1. Registering test user...")
    
    unique_email = f"test{int(time.time())}@example.com"
    user_data = {
        "email": unique_email,
        "password": "testpass123",
        "full_name": "Test User"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user_data, timeout=10)
        
        if response.status_code in [200, 201]:
            data = response.json()
            token = data.get('tokens', {}).get('access_token')
            print(f"✓ User registered successfully, token: {token[:20]}...")
            return token
        elif response.status_code == 400:
            # Try to login with existing user
            print("User might exist, trying to login...")
            login_data = {
                "email": "test@example.com",
                "password": "testpass123"
            }
            login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data, timeout=10)
            if login_response.status_code in [200, 201]:
                data = login_response.json()
                token = data.get('tokens', {}).get('access_token')
                print(f"✓ User logged in successfully, token: {token[:20]}...")
                return token
        
        print(f"✗ Authentication failed: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    except Exception as e:
        print(f"✗ Authentication error: {e}")
        return None

def upload_video(token):
    """Upload a test video"""
    print("\n2. Testing video upload...")
    
    video_data = create_test_video_file()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    files = {
        'file': ('test_video.mp4', io.BytesIO(video_data), 'video/mp4')
    }
    
    data = {
        'target_niche': 'entertainment'
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/videos/upload",
            files=files,
            data=data,
            headers=headers,
            timeout=30
        )
        
        print(f"Upload response status: {response.status_code}")
        print(f"Upload response: {response.text}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            print("✓ Video uploaded successfully!")
            print(f"  Job ID: {data.get('job_id')}")
            print(f"  File URL: {data.get('file_url')}")
            print(f"  Task ID: {data.get('task_id')}")
            return data.get('job_id')
        else:
            print(f"✗ Upload failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ Upload error: {e}")
        return None

def check_job_status(token, job_id):
    """Check the status of the uploaded video"""
    print("\n3. Checking job status...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/api/videos/", headers=headers, timeout=10)
        
        if response.status_code == 200:
            videos = response.json()
            print(f"✓ Retrieved {len(videos)} videos")
            
            # Find our uploaded video
            uploaded_video = None
            for video in videos:
                if video.get('id') == job_id:
                    uploaded_video = video
                    break
            
            if uploaded_video:
                print(f"  Video Status: {uploaded_video.get('status')}")
                print(f"  Video Title: {uploaded_video.get('title')}")
                print(f"  Video ID: {uploaded_video.get('id')}")
                return uploaded_video
            else:
                print("✗ Uploaded video not found in list")
                print("Available videos:")
                for video in videos[:3]:  # Show first 3
                    print(f"  - {video.get('id')}: {video.get('title')} ({video.get('status')})")
                return None
        else:
            print(f"✗ Failed to get videos: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"✗ Status check error: {e}")
        return None

def test_clip_generation(token, video_id):
    """Test clip generation endpoint"""
    print("\n4. Testing clip generation...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test with form data
    data = [
        ("segment_ids", "segment1"),
        ("segment_ids", "segment2"),
        ("platforms", "youtube"),
        ("platforms", "tiktok")
    ]
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/videos/{video_id}/clips",
            data=data,
            headers=headers,
            timeout=30
        )
        
        print(f"Clip generation status: {response.status_code}")
        print(f"Clip generation response: {response.text}")
        
        if response.status_code in [200, 201]:
            print("✓ Clip generation request successful!")
            return True
        else:
            print(f"✗ Clip generation failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Clip generation error: {e}")
        return False

def main():
    """Run comprehensive upload test"""
    print("=== COMPREHENSIVE VIDEO UPLOAD TEST ===")
    
    # Step 1: Register/login user
    token = register_user()
    if not token:
        print("\n✗ TEST FAILED - No authentication token")
        return False
    
    # Step 2: Upload video
    job_id = upload_video(token)
    if not job_id:
        print("\n✗ TEST FAILED - Upload failed")
        return False
    
    # Step 3: Check job status
    video = check_job_status(token, job_id)
    
    # Step 4: Test clip generation (if video exists)
    clip_success = False
    if video:
        clip_success = test_clip_generation(token, job_id)
    
    # Summary
    print("\n=== TEST RESULTS ===")
    if job_id and video:
        print("✓ VIDEO UPLOAD TEST PASSED")
        print(f"  Job ID: {job_id}")
        print(f"  Video Status: {video.get('status')}")
        if clip_success:
            print("✓ CLIP GENERATION TEST PASSED")
        else:
            print("⚠ CLIP GENERATION TEST FAILED (but upload worked)")
        return True
    else:
        print("✗ VIDEO UPLOAD TEST FAILED")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)