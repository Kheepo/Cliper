#!/usr/bin/env python3
"""
Test sync video processing functionality
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from api.tasks import process_video_sync
from loguru import logger

async def test_sync_processing():
    """Test the sync processing function"""
    print("🧪 Testing Sync Video Processing")
    print("=" * 50)
    
    # Test parameters
    job_id = "test-job-123"
    video_path = "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4"
    original_filename = "test_video.mp4"
    file_size = 1024
    
    try:
        print(f"📹 Testing sync processing with:")
        print(f"   Job ID: {job_id}")
        print(f"   Video Path: {video_path}")
        print(f"   Filename: {original_filename}")
        print(f"   Size: {file_size} bytes")
        
        # Call the sync processing function
        result = await process_video_sync(
            job_id=job_id,
            video_path=video_path,
            original_filename=original_filename,
            file_size=file_size
        )
        
        print(f"✅ Sync processing completed successfully")
        print(f"   Result: {result}")
        
    except Exception as e:
        print(f"❌ Sync processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_sync_processing())
    if success:
        print("\n🎉 Sync processing test completed successfully!")
    else:
        print("\n💥 Sync processing test failed!")
        sys.exit(1)