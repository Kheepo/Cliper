#!/usr/bin/env python3
"""
Test script to check if all imports work correctly
"""

import sys
import os

# Change to api directory to handle relative imports
os.chdir('api')
sys.path.insert(0, os.getcwd())

def test_imports():
    """Test importing all the modules used in video processing"""
    print("🧪 Testing imports...")
    
    try:
        print("📦 Testing basic imports...")
        import cv2
        print("✅ cv2 imported successfully")
        
        import whisper
        print("✅ whisper imported successfully")
        
        import torch
        print("✅ torch imported successfully")
        
        print("📦 Testing API imports...")
        from video_processor import VideoProcessor
        print("✅ VideoProcessor imported successfully")
        
        from services.unified_llm_service import unified_llm_service
        print("✅ Unified LLM Service imported successfully")
        
        from services import DatabaseService
        print("✅ DatabaseService imported successfully")
        
        print("📦 Testing VideoProcessor initialization...")
        video_processor = VideoProcessor()
        print("✅ VideoProcessor initialized successfully")
        
        print("📦 Testing Unified LLM Service status...")
        status = unified_llm_service.get_service_status()
        print(f"✅ Unified LLM Service status: {status}")
        
        print("\n🎉 All imports and initializations successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import/initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()