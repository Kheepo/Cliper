#!/usr/bin/env python3
"""
FFmpeg Processing Test
Tests video processing capabilities using FFmpeg
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

def create_test_video():
    """Create a simple test video using FFmpeg"""
    test_video_path = "test_ffmpeg_video.mp4"
    
    # Create a simple 5-second test video with FFmpeg
    ffmpeg_path = Path("ffmpeg-8.0-essentials_build/bin/ffmpeg.exe")
    
    if not ffmpeg_path.exists():
        print("❌ FFmpeg not found at expected location")
        return None
    
    cmd = [
        str(ffmpeg_path),
        "-f", "lavfi",
        "-i", "testsrc=duration=5:size=320x240:rate=30",
        "-f", "lavfi", 
        "-i", "sine=frequency=1000:duration=5",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-y",  # Overwrite output file
        test_video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ Test video created: {test_video_path}")
            return test_video_path
        else:
            print(f"❌ Failed to create test video: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg command timed out")
        return None
    except Exception as e:
        print(f"❌ Error creating test video: {e}")
        return None

def test_video_info(video_path):
    """Test getting video information using FFprobe"""
    ffprobe_path = Path("ffmpeg-8.0-essentials_build/bin/ffprobe.exe")
    
    if not ffprobe_path.exists():
        print("❌ FFprobe not found")
        return False
    
    cmd = [
        str(ffprobe_path),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            streams = len(info['streams'])
            print(f"✅ Video info retrieved: {duration:.1f}s duration, {streams} streams")
            return True
        else:
            print(f"❌ Failed to get video info: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error getting video info: {e}")
        return False

def test_video_segment(video_path):
    """Test creating a video segment using FFmpeg"""
    ffmpeg_path = Path("ffmpeg-8.0-essentials_build/bin/ffmpeg.exe")
    output_path = "test_segment.mp4"
    
    cmd = [
        str(ffmpeg_path),
        "-i", video_path,
        "-ss", "1",  # Start at 1 second
        "-t", "2",   # Duration of 2 seconds
        "-c", "copy",  # Copy streams without re-encoding
        "-y",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ Video segment created: {output_path} ({file_size} bytes)")
            os.remove(output_path)  # Clean up
            return True
        else:
            print(f"❌ Failed to create segment: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error creating segment: {e}")
        return False

def test_video_thumbnail(video_path):
    """Test creating a thumbnail using FFmpeg"""
    ffmpeg_path = Path("ffmpeg-8.0-essentials_build/bin/ffmpeg.exe")
    thumbnail_path = "test_thumbnail.jpg"
    
    cmd = [
        str(ffmpeg_path),
        "-i", video_path,
        "-ss", "2.5",  # Extract frame at 2.5 seconds
        "-vframes", "1",  # Extract only 1 frame
        "-y",
        thumbnail_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and os.path.exists(thumbnail_path):
            file_size = os.path.getsize(thumbnail_path)
            print(f"✅ Thumbnail created: {thumbnail_path} ({file_size} bytes)")
            os.remove(thumbnail_path)  # Clean up
            return True
        else:
            print(f"❌ Failed to create thumbnail: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error creating thumbnail: {e}")
        return False

def test_audio_extraction(video_path):
    """Test extracting audio using FFmpeg"""
    ffmpeg_path = Path("ffmpeg-8.0-essentials_build/bin/ffmpeg.exe")
    audio_path = "test_audio.wav"
    
    cmd = [
        str(ffmpeg_path),
        "-i", video_path,
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # PCM audio codec
        "-y",
        audio_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            print(f"✅ Audio extracted: {audio_path} ({file_size} bytes)")
            os.remove(audio_path)  # Clean up
            return True
        else:
            print(f"❌ Failed to extract audio: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error extracting audio: {e}")
        return False

def main():
    print("=== FFMPEG PROCESSING TEST ===")
    print(f"Test started at: {datetime.now().isoformat()}")
    
    # Test 1: Create test video
    print("\n1. Creating test video...")
    video_path = create_test_video()
    if not video_path:
        print("❌ Cannot proceed without test video")
        return
    
    tests_passed = 0
    total_tests = 5
    
    # Test 2: Get video information
    print("\n2. Testing video information extraction...")
    if test_video_info(video_path):
        tests_passed += 1
    
    # Test 3: Create video segment
    print("\n3. Testing video segmentation...")
    if test_video_segment(video_path):
        tests_passed += 1
    
    # Test 4: Create thumbnail
    print("\n4. Testing thumbnail generation...")
    if test_video_thumbnail(video_path):
        tests_passed += 1
    
    # Test 5: Extract audio
    print("\n5. Testing audio extraction...")
    if test_audio_extraction(video_path):
        tests_passed += 1
    
    # Clean up test video
    if os.path.exists(video_path):
        os.remove(video_path)
        print(f"\n🧹 Cleaned up test video: {video_path}")
    
    # Results
    print("\n" + "="*50)
    print("FFMPEG PROCESSING TEST RESULTS")
    print("="*50)
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    print(f"Success Rate: {(tests_passed/total_tests)*100:.1f}%")
    
    if tests_passed == total_tests:
        print("🎉 ALL TESTS PASSED - FFmpeg processing is working correctly!")
        print("✅ Video processing pipeline is ready for production")
    elif tests_passed >= total_tests * 0.8:
        print("⚠️  MOSTLY WORKING - Some minor issues detected")
        print("✅ Core video processing functionality is available")
    else:
        print("❌ SIGNIFICANT ISSUES - Video processing may not work properly")
        print("🔧 FFmpeg configuration needs attention")
    
    print(f"\nTest completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()