#!/usr/bin/env python3
"""
Test script to verify speech recognition functionality with fallback mechanisms
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the api directory to the path and set up module path
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.join(os.path.dirname(__file__), 'api'))
sys.path.insert(0, '.')

# Import with proper module structure
try:
    from api.video_processor import VideoProcessor
except ImportError:
    # Fallback import method
    import importlib.util
    spec = importlib.util.spec_from_file_location("video_processor", "api/video_processor.py")
    video_processor_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(video_processor_module)
    VideoProcessor = video_processor_module.VideoProcessor
from moviepy.editor import AudioFileClip
from pydub import AudioSegment
from pydub.generators import Sine

def create_test_audio():
    """Create a simple test audio file with speech-like content"""
    # Create a simple tone that can be processed
    tone = Sine(440).to_audio_segment(duration=3000)  # 3 seconds of 440Hz tone
    
    # Add some silence
    silence = AudioSegment.silent(duration=1000)  # 1 second silence
    
    # Combine them
    test_audio = silence + tone + silence
    
    # Export to temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        test_audio.export(temp_file.name, format='wav')
        return temp_file.name

def test_speech_recognition():
    """Test the speech recognition functionality"""
    print("Testing Speech Recognition Fallback System...")
    print("=" * 50)
    
    # Create test audio
    test_audio_path = create_test_audio()
    print(f"Created test audio: {test_audio_path}")
    
    try:
        # Initialize video processor
        processor = VideoProcessor()
        
        # Test transcription
        print("\nTesting transcription with fallback mechanisms...")
        
        def progress_callback(message):
            print(f"Progress: {message}")
        
        result = processor.transcribe_audio(test_audio_path, progress_callback)
        
        print(f"\nTranscription result: '{result}'")
        
        # Check which models are available
        print("\nAvailable speech recognition models:")
        print(f"- Google Speech Recognition: Available")
        print(f"- Whisper: {'Available' if processor.whisper_model else 'Not available'}")
        print(f"- Vosk: {'Available' if processor.vosk_model else 'Not available'}")
        
        # Test individual methods if available
        if processor.whisper_model:
            print("\nTesting Whisper directly...")
            whisper_result = processor._transcribe_with_whisper(test_audio_path, 0)
            print(f"Whisper result: '{whisper_result}'")
        
        print("\n✅ Speech recognition test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during speech recognition test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up test file
        try:
            os.unlink(test_audio_path)
            print(f"\nCleaned up test file: {test_audio_path}")
        except:
            pass

if __name__ == "__main__":
    test_speech_recognition()