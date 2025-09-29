#!/usr/bin/env python3
"""
Simple upload test to isolate connection reset issues
"""

import requests
import os
import time

def test_simple_upload():
    print("🧪 Testing simple video upload...")
    print("=" * 50)
    
    # Server URL
    server_url = "http://localhost:8000"
    
    # Check if test video exists
    video_file = "test_video_fallback.mp4"
    if not os.path.exists(video_file):
        print(f"❌ Test video {video_file} not found")
        return False
    
    print(f"📁 Using test video: {video_file} ({os.path.getsize(video_file)} bytes)")
    
    try:
        # Test server health first
        print("🔍 Checking server health...")
        health_response = requests.get(f"{server_url}/api/health", timeout=30)
        print(f"✅ Server health: {health_response.status_code}")
        
        # Prepare upload data
        files = {
            'file': ('test_video.mp4', open(video_file, 'rb'), 'video/mp4')
        }
        
        data = {
            'user_id': '550e8400-e29b-41d4-a716-446655440000',
            'title': 'Simple Test Video',
            'description': 'Testing upload functionality'
        }
        
        print("📤 Starting upload...")
        
        # Use a longer timeout and smaller chunk size
        response = requests.post(
            f"{server_url}/api/videos/upload",
            files=files,
            data=data,
            timeout=120,  # Longer timeout
            stream=True  # Stream the response
        )
        
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload successful!")
            print(f"📋 Response: {result}")
            return True
        else:
            print(f"❌ Upload failed with status {response.status_code}")
            print(f"📋 Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        return False
    except requests.exceptions.Timeout as e:
        print(f"❌ Timeout error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        # Close file if it was opened
        try:
            files['video'][1].close()
        except:
            pass

if __name__ == "__main__":
    success = test_simple_upload()
    print("=" * 50)
    if success:
        print("🎉 Test completed successfully!")
    else:
        print("❌ Test failed - but this helps us identify the issue!")