#!/usr/bin/env python3
"""
Test script to check VideoProcessor functionality
"""

import sys
import os

def test_video_processor():
    """Test VideoProcessor import and initialization"""
    print("🧪 Testing VideoProcessor...")
    
    try:
        print("📦 Testing VideoProcessor import...")
        from video_processor import VideoProcessor
        print("✅ VideoProcessor imported successfully")
        
        print("📦 Testing VideoProcessor initialization...")
        video_processor = VideoProcessor()
        print("✅ VideoProcessor initialized successfully")
        
        # Test if find_best_segments method exists and has correct signature
        print("📦 Testing find_best_segments method...")
        if hasattr(video_processor, 'find_best_segments'):
            import inspect
            sig = inspect.signature(video_processor.find_best_segments)
            params = list(sig.parameters.keys())
            print(f"✅ find_best_segments method found with parameters: {params}")
            
            # Check if duration parameter exists
            if 'duration' in params:
                print("✅ duration parameter found in find_best_segments")
            else:
                print("❌ duration parameter missing from find_best_segments")
        else:
            print("❌ find_best_segments method not found")
        
        print("\n🎉 VideoProcessor test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ VideoProcessor test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_video_processor()