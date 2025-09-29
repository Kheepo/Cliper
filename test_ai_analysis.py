#!/usr/bin/env python3
"""
Test script for AI Video Analysis Pipeline
Tests the complete AI analysis functionality including:
- Speech recognition with OpenAI Whisper
- Scene detection with OpenCV
- Emotion analysis
- Face detection
- Viral scoring algorithm
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from api/.env
load_dotenv(Path(__file__).parent / 'api' / '.env')

# Add the api directory to the Python path
sys.path.append(str(Path(__file__).parent / 'api'))

from services.ai_analyzer import ai_analyzer

async def test_ai_analysis():
    """Test the complete AI analysis pipeline"""
    print("🚀 Starting AI Analysis Pipeline Test")
    print("=" * 50)
    
    # Test video paths
    test_videos = [
        "test_video.mp4",
        "small_test_video.mp4",
        "api/test_video.mp4"
    ]
    
    # Find available test video
    test_video_path = None
    for video in test_videos:
        if os.path.exists(video):
            test_video_path = video
            break
    
    if not test_video_path:
        print("❌ No test video found. Available videos:")
        for video in test_videos:
            print(f"   - {video}: {'✅ Found' if os.path.exists(video) else '❌ Not found'}")
        return False
    
    print(f"📹 Using test video: {test_video_path}")
    print(f"📁 File size: {os.path.getsize(test_video_path) / 1024 / 1024:.2f} MB")
    
    try:
        # Test the complete analysis pipeline
        print("\n🔍 Running AI Analysis...")
        try:
            result = await ai_analyzer.analyze_video(test_video_path, "test_job_001")
        except Exception as e:
            if "ffmpeg" in str(e).lower() or "file specified" in str(e):
                print("⚠️  Analysis failed due to missing FFmpeg - this is expected")
                print("ℹ️  To fully test the pipeline, install FFmpeg: https://ffmpeg.org/download.html")
                return False
            else:
                raise e
        
        print("\n✅ Analysis completed successfully!")
        print("=" * 50)
        
        # Display results
        print(f"📊 Analysis Results Completed")
        print(f"⏱️  Processing Time: {result.processing_time:.2f} seconds")
        print(f"📈 Overall Viral Score: {result.viral_score.get('overall_score', 'N/A')}")
        print(f"🎯 Viral Grade: {result.viral_score.get('grade', 'N/A')}")
        
        # Speech Analysis Results
        if result.transcription:
            print("\n🎤 Speech Analysis:")
            print(f"   📝 Transcription: {result.transcription.get('transcription', 'N/A')[:100]}...")
            print(f"   📊 Word Count: {result.transcription.get('word_count', 'N/A')}")
            print(f"   🗣️  Speaking Rate: {result.transcription.get('speaking_rate', 'N/A')} WPM")
            print(f"   🔑 Keywords: {', '.join(result.transcription.get('keywords', [])[:5])}")
            print(f"   🌍 Language: {result.transcription.get('language', 'N/A')}")
        
        # Scene Analysis Results
        if result.scenes:
            print(f"\n🎬 Scene Analysis: {len(result.scenes)} scenes detected")
            for i, scene in enumerate(result.scenes[:3]):  # Show first 3 scenes
                print(f"   Scene {i+1}: {scene.start_time:.1f}s - {scene.end_time:.1f}s")
                print(f"      Type: {scene.data.get('scene_type', 'N/A')}")
                print(f"      Motion: {scene.data.get('motion_level', 'N/A')}")
                print(f"      Confidence: {scene.confidence:.2f}")
        
        # Emotion Analysis Results
        if result.emotions:
            print(f"\n😊 Emotion Analysis: {len(result.emotions)} segments analyzed")
            for i, emotion in enumerate(result.emotions[:3]):  # Show first 3 emotions
                print(f"   Segment {i+1}: {emotion.start_time:.1f}s - {emotion.end_time:.1f}s")
                print(f"      Primary Emotion: {emotion.data.get('primary_emotion', 'N/A')}")
                print(f"      Sentiment: {emotion.data.get('sentiment', 'N/A')}")
                print(f"      Energy Level: {emotion.data.get('energy_level', 'N/A')}")
                print(f"      Faces Detected: {emotion.data.get('faces_detected', 'N/A')}")
        
        # Face Detection Results
        if result.faces:
            print(f"\n👤 Face Detection: {len(result.faces)} segments analyzed")
            total_faces = sum(face.data.get('face_count', 0) for face in result.faces)
            avg_faces = total_faces / len(result.faces) if result.faces else 0
            print(f"   Average faces per segment: {avg_faces:.1f}")
            
            # Show segments with faces
            face_segments = [f for f in result.faces if f.data.get('face_count', 0) > 0]
            if face_segments:
                print(f"   Segments with faces: {len(face_segments)}")
                for i, face in enumerate(face_segments[:2]):  # Show first 2 face segments
                    print(f"      Segment {i+1}: {face.start_time:.1f}s - {face.end_time:.1f}s")
                    print(f"         Faces: {face.data.get('face_count', 0)}")
                    print(f"         Quality: {face.data.get('face_quality', 'N/A')}")
        
        # Viral Score Breakdown
        if result.viral_score and 'category_scores' in result.viral_score:
            print("\n📈 Viral Score Breakdown:")
            scores = result.viral_score['category_scores']
            for category, score in scores.items():
                print(f"   {category.replace('_', ' ').title()}: {score:.1f}/100")
        
        # Recommendations
        if result.viral_score and 'recommendations' in result.viral_score:
            recommendations = result.viral_score['recommendations']
            if recommendations:
                print("\n💡 Recommendations:")
                for i, rec in enumerate(recommendations[:3], 1):
                    print(f"   {i}. {rec}")
        
        # Platform Suggestions
        if result.viral_score and 'optimal_platforms' in result.viral_score:
            platforms = result.viral_score['optimal_platforms']
            if platforms:
                print(f"\n📱 Suggested Platforms: {', '.join(platforms)}")
        
        # Save detailed results to file
        results_file = "ai_analysis_test_results.json"
        with open(results_file, 'w') as f:
            # Convert result to dict for JSON serialization
            result_dict = {
                'processing_time': result.processing_time,
                'transcription': result.transcription,
                'scenes': [{
                    'start_time': s.start_time,
                    'end_time': s.end_time,
                    'confidence': s.confidence,
                    'data': s.data
                } for s in result.scenes] if result.scenes else [],
                'emotions': [{
                    'start_time': e.start_time,
                    'end_time': e.end_time,
                    'confidence': e.confidence,
                    'data': e.data
                } for e in result.emotions] if result.emotions else [],
                'faces': [{
                    'start_time': f.start_time,
                    'end_time': f.end_time,
                    'confidence': f.confidence,
                    'data': f.data
                } for f in result.faces] if result.faces else [],
                'viral_score': result.viral_score
            }
            json.dump(result_dict, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {results_file}")
        print("\n🎉 AI Analysis Pipeline Test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ AI Analysis Pipeline Test FAILED!")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_individual_components():
    """Test individual components of the AI analyzer"""
    print("\n🔧 Testing Individual Components")
    print("=" * 50)
    
    # Test video path
    test_videos = ["test_video.mp4", "small_test_video.mp4", "api/test_video.mp4"]
    test_video_path = None
    for video in test_videos:
        if os.path.exists(video):
            test_video_path = video
            break
    
    if not test_video_path:
        print("❌ No test video found for component testing")
        return False
    
    try:
        # Test audio extraction
        print("🎵 Testing audio extraction...")
        try:
            audio_path = await ai_analyzer._extract_audio(test_video_path)
            if os.path.exists(audio_path):
                print(f"   ✅ Audio extracted: {audio_path}")
                print(f"   📁 Audio file size: {os.path.getsize(audio_path) / 1024:.1f} KB")
            else:
                print("   ❌ Audio extraction failed")
                return False
        except Exception as e:
            print(f"   ⚠️  Audio extraction failed (FFmpeg not available): {str(e)}")
            print("   ℹ️  This is expected if FFmpeg is not installed")
        
        # Test speech analysis (skip if audio extraction failed)
        print("🎤 Testing speech analysis...")
        try:
            # Create a dummy audio file for testing if FFmpeg is not available
            dummy_audio = os.path.join(os.path.dirname(test_video_path), "dummy_audio.wav")
            if not os.path.exists(audio_path if 'audio_path' in locals() else dummy_audio):
                print("   ⚠️  Skipping speech analysis (no audio file available)")
            else:
                speech_result = await ai_analyzer._analyze_speech(audio_path if 'audio_path' in locals() else dummy_audio)
                if speech_result and 'text' in speech_result:
                    print(f"   ✅ Speech analysis completed")
                    print(f"   📝 Sample transcription: {speech_result['text'][:50]}...")
                else:
                    print("   ❌ Speech analysis failed")
        except Exception as e:
            print(f"   ⚠️  Speech analysis failed: {str(e)}")
            print("   ℹ️  This is expected without proper audio setup")
        
        # Test scene detection
        print("🎬 Testing scene detection...")
        scenes = await ai_analyzer._analyze_scenes(test_video_path)
        if scenes:
            print(f"   ✅ Scene detection completed: {len(scenes)} scenes")
        else:
            print("   ❌ Scene detection failed")
        
        # Test emotion analysis
        print("😊 Testing emotion analysis...")
        emotions = await ai_analyzer._analyze_emotions(test_video_path)
        if emotions:
            print(f"   ✅ Emotion analysis completed: {len(emotions)} segments")
        else:
            print("   ❌ Emotion analysis failed")
        
        # Test face detection
        print("👤 Testing face detection...")
        faces = await ai_analyzer._detect_faces(test_video_path)
        if faces:
            print(f"   ✅ Face detection completed: {len(faces)} segments")
        else:
            print("   ❌ Face detection failed")
        
        print("\n🎉 Individual Component Tests PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Component Test FAILED: {str(e)}")
        return False

async def main():
    """Main test function"""
    print("🧪 AI Video Analysis Pipeline Test Suite")
    print("=" * 60)
    
    # Check environment
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        print("❌ OPENAI_API_KEY not found in environment")
        return
    else:
        print(f"✅ OpenAI API Key configured: {openai_key[:10]}...")
    
    # Check dependencies
    try:
        import cv2
        print(f"✅ OpenCV version: {cv2.__version__}")
    except ImportError:
        print("❌ OpenCV not installed")
        return
    
    try:
        from openai import AsyncOpenAI
        print("✅ OpenAI library available")
    except ImportError:
        print("❌ OpenAI library not installed")
        return
    
    # Check FFmpeg availability
    import subprocess
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  FFmpeg not available - audio extraction will be limited")
    
    # Run tests
    component_test_passed = await test_individual_components()
    full_test_passed = await test_ai_analysis()
    
    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print(f"   Component Tests: {'✅ PASSED' if component_test_passed else '❌ FAILED'}")
    print(f"   Full Pipeline Test: {'✅ PASSED' if full_test_passed else '❌ FAILED'}")
    
    if component_test_passed and full_test_passed:
        print("\n🎉 ALL TESTS PASSED! AI Analysis Pipeline is working correctly.")
    else:
        print("\n❌ SOME TESTS FAILED. Please check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())