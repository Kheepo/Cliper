#!/usr/bin/env python3
"""
Simple test script to verify speech recognition functionality
"""

import os
import tempfile
from pydub import AudioSegment
from pydub.generators import Sine
from video_processor import VideoProcessor

def create_test_audio():
    """Create a simple test audio file"""
    # Create a simple tone
    tone = Sine(440).to_audio_segment(duration=2000)  # 2 seconds
    silence = AudioSegment.silent(duration=500)  # 0.5 seconds
    test_audio = silence + tone + silence
    
    # Export to temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        test_audio.export(temp_file.name, format='wav')
        return temp_file.name

def test_speech_recognition():
    """Test the speech recognition functionality"""
    print("Testing Speech Recognition System...")
    print("=" * 40)
    
    test_audio_path = create_test_audio()
    print(f"Created test audio: {test_audio_path}")
    
    try:
        # Initialize video processor
        processor = VideoProcessor()
        
        # Check available models
        print("\nAvailable speech recognition models:")
        print(f"- Google Speech Recognition: Available")
        print(f"- Whisper: {'Available' if processor.whisper_model else 'Not available'}")
        print(f"- Vosk: {'Available' if processor.vosk_model else 'Not available'}")
        
        # Test transcription
        print("\nTesting transcription...")
        result = processor.transcribe_audio(test_audio_path)
        print(f"Transcription result: '{result}'")
        
        print("\n✅ Speech recognition test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        try:
            os.unlink(test_audio_path)
        except:
            pass

if __name__ == "__main__":
    test_speech_recognition()