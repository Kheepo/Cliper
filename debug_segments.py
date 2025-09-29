#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from api.video_processor import VideoProcessor
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def test_segment_generation():
    """Test segment generation directly"""
    print("🧪 Testing segment generation...")
    print("=" * 50)
    
    # Initialize processor
    processor = VideoProcessor()
    
    # Test video path
    video_path = "test_video_fallback.mp4"
    
    if not os.path.exists(video_path):
        print(f"❌ Test video not found: {video_path}")
        return
    
    print(f"📁 Using test video: {video_path}")
    
    try:
        # Process video
        print("🔄 Processing video...")
        output_dir = "debug_output"
        os.makedirs(output_dir, exist_ok=True)
        result = processor.process_video(video_path, output_dir)
        
        print(f"✅ Processing result: {result['success']}")
        if result['success']:
            print(f"📊 Clip path: {result.get('clip_path', 'N/A')}")
            print(f"📝 Transcript length: {len(result.get('transcript', ''))}")
            print(f"🎬 Video features: {list(result.get('video_features', {}).keys())}")
            print(f"📈 Segment info: {result.get('segment_info', 'N/A')}")
            print(f"📋 Total segments: {len(result.get('all_segments', []))}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"💥 Exception during processing: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 50)
    print("🏁 Test completed!")

if __name__ == "__main__":
    test_segment_generation()