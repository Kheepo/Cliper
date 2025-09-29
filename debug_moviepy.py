#!/usr/bin/env python3

import os
import sys
from moviepy.editor import VideoFileClip

def test_moviepy_extraction():
    """Test MoviePy extraction with the test video"""
    video_path = "test_video_fallback.mp4"
    output_path = "debug_clip.mp4"
    
    print(f"Testing MoviePy extraction...")
    print(f"Video path: {video_path}")
    print(f"Video exists: {os.path.exists(video_path)}")
    
    if not os.path.exists(video_path):
        print("❌ Test video not found!")
        return False
    
    try:
        print("📹 Loading video...")
        video = VideoFileClip(video_path)
        print(f"✅ Video loaded successfully")
        print(f"Duration: {video.duration} seconds")
        print(f"FPS: {video.fps}")
        print(f"Size: {video.size}")
        
        # Try to extract a small clip
        print("✂️ Extracting clip (0-5 seconds)...")
        clip = video.subclip(0, min(5, video.duration))
        print(f"✅ Clip created successfully")
        
        print(f"📝 Writing clip to {output_path}...")
        clip.write_videofile(output_path, verbose=False, logger=None)
        print(f"✅ Clip written successfully")
        
        # Clean up
        video.close()
        clip.close()
        
        # Check output file
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"✅ Output file created: {output_path} ({size} bytes)")
            return True
        else:
            print(f"❌ Output file not created")
            return False
            
    except Exception as e:
        print(f"❌ MoviePy extraction failed: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_moviepy_extraction()
    if success:
        print("\n🎉 MoviePy extraction test PASSED!")
    else:
        print("\n💥 MoviePy extraction test FAILED!")
    
    sys.exit(0 if success else 1)