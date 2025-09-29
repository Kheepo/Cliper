#!/usr/bin/env python3
"""
Test video upload functionality with proper authentication
"""

import requests
import json
import os
from io import BytesIO

def create_test_video_file():
    """Create a minimal test video file"""
    # Create a simple test file (not a real video, but for upload testing)
    test_content = b"\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41isom\x00\x00\x00\x08free" + b"\x00" * 1000
    
    with open("test_upload_video.mp4", "wb") as f:
        f.write(test_content)
    
    return "test_upload_video.mp4"

def test_video_upload():
    """Test video upload with proper authentication"""
    print("🎬 Testing Video Upload Functionality")
    print("=" * 50)
    
    # Load test user credentials
    try:
        with open("test_user_credentials.json", "r") as f:
            credentials = json.load(f)
        access_token = credentials["access_token"]
        user_id = credentials["user_id"]
        print(f"✅ Loaded credentials for user: {user_id}")
    except Exception as e:
        print(f"❌ Failed to load credentials: {e}")
        return False
    
    # Create test video file
    print("\n📁 Creating test video file...")
    video_file = create_test_video_file()
    file_size = os.path.getsize(video_file)
    print(f"   File: {video_file} ({file_size} bytes)")
    
    # Prepare upload request
    url = "http://localhost:8000/api/videos/upload"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    # Test 1: Check endpoint accessibility
    print("\n🔍 Test 1: Check endpoint accessibility")
    try:
        with open(video_file, "rb") as f:
            files = {
                "file": ("test_upload_video.mp4", f, "video/mp4")
            }
            data = {
                "title": "Test Upload Video",
                "description": "Test video for upload functionality verification"
            }
            
            print(f"   Uploading to: {url}")
            print(f"   File size: {file_size} bytes")
            print(f"   Auth token: {access_token[:50]}...")
            
            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=30
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Upload successful!")
                print(f"   Job ID: {result.get('job_id', 'N/A')}")
                print(f"   Message: {result.get('message', 'N/A')}")
                return True
            elif response.status_code == 401:
                print(f"   ❌ Authentication failed: {response.text}")
                return False
            elif response.status_code == 422:
                print(f"   ❌ Validation error: {response.text}")
                return False
            else:
                print(f"   ❌ Upload failed: {response.text}")
                return False
                
    except requests.exceptions.Timeout:
        print("   ❌ Upload timeout")
        return False
    except Exception as e:
        print(f"   ❌ Upload error: {e}")
        return False
    finally:
        # Cleanup test file
        if os.path.exists(video_file):
            os.remove(video_file)
            print(f"   🧹 Cleaned up test file: {video_file}")

def test_endpoint_without_auth():
    """Test endpoint without authentication to verify it requires auth"""
    print("\n🔒 Test 2: Verify authentication requirement")
    
    url = "http://localhost:8000/api/videos/upload"
    
    try:
        # Create minimal test file
        test_content = b"test video content"
        files = {
            "file": ("test.mp4", BytesIO(test_content), "video/mp4")
        }
        
        response = requests.post(url, files=files, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 401:
            print(f"   ✅ Correctly requires authentication")
            return True
        else:
            print(f"   ❌ Should require authentication but got: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error testing without auth: {e}")
        return False

def main():
    """Run all upload tests"""
    print("🚀 Starting Video Upload Tests")
    print("=" * 60)
    
    # Test authentication requirement
    auth_test = test_endpoint_without_auth()
    
    # Test authenticated upload
    upload_test = test_video_upload()
    
    print("\n📊 Test Results Summary")
    print("=" * 30)
    print(f"   Authentication Test: {'✅ PASS' if auth_test else '❌ FAIL'}")
    print(f"   Upload Test: {'✅ PASS' if upload_test else '❌ FAIL'}")
    
    if auth_test and upload_test:
        print("\n🎉 All video upload tests passed!")
        return True
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)