#!/usr/bin/env python3
"""
Test script to verify Celery task calling works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.tasks import generate_clips_task

def test_task_call():
    """Test calling the generate_clips_task directly"""
    
    print("Testing generate_clips_task call...")
    
    try:
        # Test with keyword arguments (how it's called in main.py)
        print("Testing with keyword arguments...")
        task = generate_clips_task.delay(
            clip_id="test-clip-123",
            video_id="test-video-123", 
            user_id="test-user-123",
            generation_options={
                "clip_type": "highlight",
                "target_duration": 30,
                "platform": "tiktok"
            }
        )
        print(f"✓ Task queued successfully with ID: {task.id}")
        return True
        
    except Exception as e:
        print(f"✗ Error calling task: {e}")
        return False

if __name__ == "__main__":
    success = test_task_call()
    sys.exit(0 if success else 1)