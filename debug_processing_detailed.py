#!/usr/bin/env python3
"""
Detailed debug script for video processing functionality
"""

import asyncio
import sys
import os
import tempfile
import traceback
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

async def test_video_processing_function():
    """Test the video processing function directly"""
    print("🔧 Testing Video Processing Function Directly")
    print("=" * 50)
    
    try:
        # Import the processing function
        from api.tasks import _process_video_core
        print("✅ Successfully imported _process_video_core")
        
        # Create a simple test video file
        test_content = b'\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41isom\x00\x00\x00\x08free'
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(test_content)
            temp_video_path = temp_file.name
        
        print(f"📁 Created test video: {temp_video_path}")
        
        # Test the function with a mock job ID
        test_job_id = "test-job-123"
        test_filename = "test_video.mp4"
        test_file_size = len(test_content)
        
        print(f"🎬 Testing video processing with:")
        print(f"   Job ID: {test_job_id}")
        print(f"   Video Path: {temp_video_path}")
        print(f"   Filename: {test_filename}")
        print(f"   File Size: {test_file_size}")
        
        # Call the processing function
        try:
            result = await _process_video_core(
                job_id=test_job_id,
                video_path=temp_video_path,
                original_filename=test_filename,
                file_size=test_file_size
            )
            print(f"✅ Processing completed successfully: {result}")
            
        except Exception as processing_error:
            print(f"❌ Processing failed: {str(processing_error)}")
            print(f"📋 Error details:")
            traceback.print_exc()
        
        # Clean up
        try:
            os.unlink(temp_video_path)
            print(f"🧹 Cleaned up test file")
        except:
            pass
            
    except ImportError as import_error:
        print(f"❌ Failed to import processing function: {import_error}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        traceback.print_exc()

async def test_url_processing():
    """Test URL processing functionality"""
    print("\n🌐 Testing URL Processing")
    print("=" * 30)
    
    try:
        from api.tasks import _process_video_core
        
        # Test with a URL (this should trigger the download logic)
        test_url = "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4"
        test_job_id = "test-url-job-456"
        test_filename = "sample_video.mp4"
        test_file_size = 1024 * 1024  # 1MB estimate
        
        print(f"🔗 Testing URL processing with:")
        print(f"   Job ID: {test_job_id}")
        print(f"   Video URL: {test_url}")
        print(f"   Filename: {test_filename}")
        
        try:
            result = await _process_video_core(
                job_id=test_job_id,
                video_path=test_url,
                original_filename=test_filename,
                file_size=test_file_size
            )
            print(f"✅ URL processing completed: {result}")
            
        except Exception as url_error:
            print(f"❌ URL processing failed: {str(url_error)}")
            print(f"📋 Error details:")
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ URL test error: {str(e)}")
        traceback.print_exc()

async def main():
    """Main test function"""
    print("🧪 Video Processing Debug Tests")
    print("=" * 40)
    
    # Test 1: Direct function call
    await test_video_processing_function()
    
    # Test 2: URL processing
    await test_url_processing()
    
    print("\n📊 Debug Tests Complete")
    print("=" * 25)

if __name__ == "__main__":
    asyncio.run(main())