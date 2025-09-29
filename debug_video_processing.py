#!/usr/bin/env python3
"""
Debug script to test video processing with URL download functionality
"""

import os
import sys
import asyncio
import tempfile
import requests
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from api.services.supabase_service import supabase_service
from api.tasks import VideoProcessingTask

async def test_url_download():
    """Test the URL download functionality"""
    print("🔍 Testing URL download functionality...")
    
    # Test URL (a small video file)
    test_url = "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4"
    
    try:
        # Test downloading from URL
        print(f"📥 Downloading from: {test_url}")
        
        # Create temporary file
        temp_fd, local_video_path = tempfile.mkstemp(suffix='.mp4', prefix='test_video_')
        
        # Download the video file
        response = requests.get(test_url, stream=True, timeout=30)
        response.raise_for_status()
        
        with os.fdopen(temp_fd, 'wb') as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
        
        print(f"✅ Downloaded to: {local_video_path}")
        print(f"📊 File size: {os.path.getsize(local_video_path)} bytes")
        print(f"📁 File exists: {os.path.exists(local_video_path)}")
        
        # Clean up
        if os.path.exists(local_video_path):
            os.remove(local_video_path)
            print("🧹 Cleaned up temporary file")
            
        return True
        
    except Exception as e:
        print(f"❌ URL download failed: {e}")
        return False

async def test_video_processing_with_url():
    """Test video processing with a Supabase storage URL"""
    print("\n🎬 Testing video processing with Supabase URL...")
    
    try:
        # Get a test job from the database
        jobs_response = await supabase_service.supabase.table('jobs').select('*').limit(1).execute()
        
        if not jobs_response.data:
            print("❌ No jobs found in database")
            return False
            
        job = jobs_response.data[0]
        job_id = job['id']
        video_url = job['video_url']
        
        print(f"📋 Using job: {job_id}")
        print(f"🔗 Video URL: {video_url}")
        
        # Test if URL is accessible
        try:
            response = requests.head(video_url, timeout=10)
            print(f"📡 URL status: {response.status_code}")
            print(f"📊 Content length: {response.headers.get('content-length', 'unknown')}")
            print(f"📄 Content type: {response.headers.get('content-type', 'unknown')}")
        except Exception as url_error:
            print(f"❌ URL not accessible: {url_error}")
            return False
        
        # Create video processing task instance
        task = VideoProcessingTask()
        
        # Test the core processing function with URL
        print("🔄 Starting video processing...")
        
        try:
            result = await task._process_video_core(
                job_id=job_id,
                video_path=video_url,
                original_filename="test_video.mp4",
                file_size=1024
            )
            print(f"✅ Processing completed: {result}")
            return True
            
        except Exception as processing_error:
            print(f"❌ Processing failed: {processing_error}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("🧪 Video Processing Debug Tests")
    print("=" * 50)
    
    # Test 1: URL download functionality
    url_test_passed = await test_url_download()
    
    # Test 2: Video processing with URL (only if we have jobs)
    processing_test_passed = await test_video_processing_with_url()
    
    print("\n📊 Test Results Summary")
    print("=" * 30)
    print(f"   URL Download Test: {'✅ PASS' if url_test_passed else '❌ FAIL'}")
    print(f"   Video Processing Test: {'✅ PASS' if processing_test_passed else '❌ FAIL'}")
    
    if url_test_passed and processing_test_passed:
        print("\n🎉 All tests passed!")
        return True
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)