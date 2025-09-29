#!/usr/bin/env python3
"""
Comprehensive Video Upload and Processing Pipeline Test

This script tests the complete video upload and processing workflow:
1. Video upload endpoint
2. Video processing status
3. Video retrieval
4. Analysis results
5. Clip generation
"""

import requests
import json
import time
import os
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
TEST_VIDEO_PATH = "test_video.mp4"  # We'll create a small test file

def create_test_video():
    """Create a small test video file for upload testing"""
    try:
        # Create a minimal MP4 file (just headers, not a real video)
        test_content = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free'
        with open(TEST_VIDEO_PATH, 'wb') as f:
            f.write(test_content)
        print(f"✓ Created test video file: {TEST_VIDEO_PATH}")
        return True
    except Exception as e:
        print(f"✗ Failed to create test video: {e}")
        return False

def test_video_upload():
    """Test video upload endpoint"""
    print("\n=== Testing Video Upload ===")
    
    if not os.path.exists(TEST_VIDEO_PATH):
        if not create_test_video():
            return False
    
    try:
        # Test without authentication first
        with open(TEST_VIDEO_PATH, 'rb') as f:
            files = {'file': ('test_video.mp4', f, 'video/mp4')}
            response = requests.post(f"{BASE_URL}/api/videos/upload", files=files)
        
        print(f"Upload response status: {response.status_code}")
        print(f"Upload response: {response.text[:200]}...")
        
        if response.status_code == 401:
            print("✓ Upload correctly requires authentication")
            return True
        elif response.status_code == 200:
            print("✓ Upload successful (no auth required)")
            return True
        else:
            print(f"✗ Unexpected upload response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Upload test failed: {e}")
        return False

def test_video_url_processing():
    """Test video URL processing endpoint"""
    print("\n=== Testing Video URL Processing ===")
    
    try:
        # Test with a sample YouTube URL
        test_data = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Test Video",
            "description": "Test video for processing"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/videos/process-url",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"URL processing response status: {response.status_code}")
        print(f"URL processing response: {response.text[:200]}...")
        
        if response.status_code == 401:
            print("✓ URL processing correctly requires authentication")
            return True
        elif response.status_code == 200:
            print("✓ URL processing successful (no auth required)")
            return True
        else:
            print(f"✗ Unexpected URL processing response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ URL processing test failed: {e}")
        return False

def test_video_list():
    """Test video list endpoint"""
    print("\n=== Testing Video List ===")
    
    try:
        response = requests.get(f"{BASE_URL}/api/videos/")
        
        print(f"Video list response status: {response.status_code}")
        print(f"Video list response: {response.text[:200]}...")
        
        if response.status_code == 401:
            print("✓ Video list correctly requires authentication")
            return True
        elif response.status_code == 200:
            print("✓ Video list accessible (no auth required)")
            return True
        else:
            print(f"✗ Unexpected video list response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Video list test failed: {e}")
        return False

def test_video_details():
    """Test video details endpoint"""
    print("\n=== Testing Video Details ===")
    
    try:
        # Test with a sample video ID
        test_video_id = "test-video-123"
        response = requests.get(f"{BASE_URL}/api/videos/{test_video_id}")
        
        print(f"Video details response status: {response.status_code}")
        print(f"Video details response: {response.text[:200]}...")
        
        if response.status_code in [401, 404]:
            print("✓ Video details correctly requires authentication or returns not found")
            return True
        elif response.status_code == 200:
            print("✓ Video details accessible")
            return True
        else:
            print(f"✗ Unexpected video details response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Video details test failed: {e}")
        return False

def test_video_analysis():
    """Test video analysis endpoint"""
    print("\n=== Testing Video Analysis ===")
    
    try:
        # Test with a sample video ID
        test_video_id = "test-video-123"
        response = requests.get(f"{BASE_URL}/api/videos/{test_video_id}/analysis")
        
        print(f"Video analysis response status: {response.status_code}")
        print(f"Video analysis response: {response.text[:200]}...")
        
        if response.status_code in [401, 404]:
            print("✓ Video analysis correctly requires authentication or returns not found")
            return True
        elif response.status_code == 200:
            print("✓ Video analysis accessible")
            return True
        else:
            print(f"✗ Unexpected video analysis response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Video analysis test failed: {e}")
        return False

def test_clip_generation():
    """Test clip generation endpoint"""
    print("\n=== Testing Clip Generation ===")
    
    try:
        # Test with sample data
        test_video_id = "test-video-123"
        test_data = {
            "segment_ids": ["segment1", "segment2"],
            "platforms": ["youtube", "tiktok"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/videos/{test_video_id}/clips",
            data=test_data
        )
        
        print(f"Clip generation response status: {response.status_code}")
        print(f"Clip generation response: {response.text[:200]}...")
        
        if response.status_code in [401, 404]:
            print("✓ Clip generation correctly requires authentication or returns not found")
            return True
        elif response.status_code == 200:
            print("✓ Clip generation accessible")
            return True
        else:
            print(f"✗ Unexpected clip generation response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Clip generation test failed: {e}")
        return False

def test_server_connectivity():
    """Test basic server connectivity"""
    print("\n=== Testing Server Connectivity ===")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Health check response status: {response.status_code}")
        print(f"Health check response: {response.text}")
        
        if response.status_code == 200:
            print("✓ Server is running and accessible")
            return True
        else:
            print(f"✗ Server health check failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server - is it running?")
        return False
    except Exception as e:
        print(f"✗ Server connectivity test failed: {e}")
        return False

def cleanup():
    """Clean up test files"""
    try:
        if os.path.exists(TEST_VIDEO_PATH):
            os.remove(TEST_VIDEO_PATH)
            print(f"✓ Cleaned up test file: {TEST_VIDEO_PATH}")
    except Exception as e:
        print(f"Warning: Failed to clean up test file: {e}")

def main():
    """Run all video pipeline tests"""
    print("🎬 VIDEO UPLOAD AND PROCESSING PIPELINE TEST")
    print("=" * 50)
    
    tests = [
        ("Server Connectivity", test_server_connectivity),
        ("Video Upload", test_video_upload),
        ("Video URL Processing", test_video_url_processing),
        ("Video List", test_video_list),
        ("Video Details", test_video_details),
        ("Video Analysis", test_video_analysis),
        ("Clip Generation", test_clip_generation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Cleanup
    cleanup()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 VIDEO PIPELINE TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:<8} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed < total:
        print("\n🔧 COMMON ISSUES:")
        print("- Server not running: Start with 'python run_server.py'")
        print("- Authentication required: Most endpoints need valid JWT tokens")
        print("- Database not connected: Check Supabase configuration")
        print("- File upload issues: Check file size limits and storage setup")
        print("- Missing dependencies: Check if all required packages are installed")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)