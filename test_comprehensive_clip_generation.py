#!/usr/bin/env python3
"""
Comprehensive Clip Generation Testing Script
Tests all aspects of the clip generation pipeline
"""

import requests
import json
import time
import os
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8001"
TEST_VIDEO_PATH = "working_test.mp4"  # Use one of our available test videos

def log_test(message, status="INFO"):
    """Log test messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {status}: {message}")

def test_api_health():
    """Test API health endpoint"""
    log_test("Testing API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            log_test("✅ API health check passed", "SUCCESS")
            return True
        else:
            log_test(f"❌ API health check failed: {response.status_code}", "ERROR")
            return False
    except Exception as e:
        log_test(f"❌ API health check failed: {e}", "ERROR")
        return False

def test_video_upload():
    """Test video upload functionality"""
    log_test("Testing video upload...")
    try:
        response = requests.post(f"{API_BASE_URL}/api/videos/upload")
        if response.status_code == 200:
            data = response.json()
            log_test(f"✅ Video upload successful: {data['job_id']}", "SUCCESS")
            return data['job_id']
        else:
            log_test(f"❌ Video upload failed: {response.status_code}", "ERROR")
            return None
    except Exception as e:
        log_test(f"❌ Video upload failed: {e}", "ERROR")
        return None

def test_video_list():
    """Test video listing functionality"""
    log_test("Testing video list...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/videos/")
        if response.status_code == 200:
            videos = response.json()
            log_test(f"✅ Video list retrieved: {len(videos)} videos", "SUCCESS")
            return videos
        else:
            log_test(f"❌ Video list failed: {response.status_code}", "ERROR")
            return []
    except Exception as e:
        log_test(f"❌ Video list failed: {e}", "ERROR")
        return []

def test_clip_generation(video_id, platform="youtube", segments=2):
    """Test clip generation for different platforms"""
    log_test(f"Testing clip generation for {platform}...")
    try:
        payload = {
            "platform": platform,
            "segments": segments,
            "clip_length": 30 if platform == "youtube" else 15
        }
        
        response = requests.post(f"{API_BASE_URL}/api/videos/{video_id}/clips", json=payload)
        if response.status_code == 200:
            data = response.json()
            log_test(f"✅ Clip generation started: {data['clip_id']}", "SUCCESS")
            return data['clip_id']
        else:
            log_test(f"❌ Clip generation failed: {response.status_code} - {response.text}", "ERROR")
            return None
    except Exception as e:
        log_test(f"❌ Clip generation failed: {e}", "ERROR")
        return None

def check_clip_files():
    """Check if clip files are generated and have content"""
    log_test("Checking generated clip files...")
    clips_dir = "uploads/clips"
    
    if not os.path.exists(clips_dir):
        log_test(f"❌ Clips directory not found: {clips_dir}", "ERROR")
        return False
    
    files = os.listdir(clips_dir)
    if not files:
        log_test("❌ No clip files found", "ERROR")
        return False
    
    log_test(f"📁 Found {len(files)} files in clips directory", "INFO")
    
    # Check file sizes
    non_empty_files = 0
    for file in files:
        file_path = os.path.join(clips_dir, file)
        size = os.path.getsize(file_path)
        if size > 100:  # Consider files > 100 bytes as non-empty
            non_empty_files += 1
            log_test(f"✅ {file}: {size} bytes", "SUCCESS")
        else:
            log_test(f"⚠️ {file}: {size} bytes (possibly empty)", "WARNING")
    
    if non_empty_files > 0:
        log_test(f"✅ Found {non_empty_files} non-empty clip files", "SUCCESS")
        return True
    else:
        log_test("❌ All clip files appear to be empty", "ERROR")
        return False

def run_comprehensive_test():
    """Run comprehensive test suite"""
    log_test("🚀 Starting Comprehensive Clip Generation Test", "INFO")
    log_test("=" * 60, "INFO")
    
    results = {
        "api_health": False,
        "video_upload": False,
        "video_list": False,
        "clip_generation": {},
        "clip_files": False,
        "start_time": datetime.now(),
        "end_time": None
    }
    
    # Test 1: API Health
    results["api_health"] = test_api_health()
    if not results["api_health"]:
        log_test("❌ API health check failed, stopping tests", "ERROR")
        return results
    
    # Test 2: Video Upload
    video_id = test_video_upload()
    results["video_upload"] = video_id is not None
    
    # Test 3: Video List
    videos = test_video_list()
    results["video_list"] = len(videos) > 0
    
    if video_id:
        # Test 4: Clip Generation for Different Platforms
        platforms = [
            ("youtube", 2),
            ("tiktok", 3),
            ("instagram", 2)
        ]
        
        for platform, segments in platforms:
            clip_id = test_clip_generation(video_id, platform, segments)
            results["clip_generation"][platform] = clip_id is not None
            
            # Wait a bit between requests
            time.sleep(1)
    
    # Wait for background processing
    log_test("⏳ Waiting 10 seconds for background processing...", "INFO")
    time.sleep(10)
    
    # Test 5: Check Generated Files
    results["clip_files"] = check_clip_files()
    
    results["end_time"] = datetime.now()
    
    # Generate Summary
    log_test("=" * 60, "INFO")
    log_test("📊 TEST SUMMARY", "INFO")
    log_test("=" * 60, "INFO")
    
    total_tests = 4 + len(results["clip_generation"])
    passed_tests = sum([
        results["api_health"],
        results["video_upload"],
        results["video_list"],
        sum(results["clip_generation"].values()),
        results["clip_files"]
    ])
    
    log_test(f"✅ Passed: {passed_tests}/{total_tests} tests", "SUCCESS" if passed_tests == total_tests else "WARNING")
    log_test(f"⏱️ Duration: {results['end_time'] - results['start_time']}", "INFO")
    
    # Detailed Results
    log_test(f"API Health: {'✅' if results['api_health'] else '❌'}", "INFO")
    log_test(f"Video Upload: {'✅' if results['video_upload'] else '❌'}", "INFO")
    log_test(f"Video List: {'✅' if results['video_list'] else '❌'}", "INFO")
    
    for platform, success in results["clip_generation"].items():
        log_test(f"Clip Gen ({platform}): {'✅' if success else '❌'}", "INFO")
    
    log_test(f"Clip Files: {'✅' if results['clip_files'] else '❌'}", "INFO")
    
    return results

if __name__ == "__main__":
    results = run_comprehensive_test()
    
    # Save results to file
    with open("test_results.json", "w") as f:
        # Convert datetime objects to strings for JSON serialization
        results_copy = results.copy()
        results_copy["start_time"] = results["start_time"].isoformat()
        results_copy["end_time"] = results["end_time"].isoformat()
        json.dump(results_copy, f, indent=2)
    
    log_test("📄 Test results saved to test_results.json", "INFO")