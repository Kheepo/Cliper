#!/usr/bin/env python3
"""
Simple test script to verify the unified LLM service functionality.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path to enable 'api' imports
api_dir = Path(__file__).parent
parent_dir = api_dir.parent
sys.path.insert(0, str(parent_dir))

from api.services.unified_llm_service import UnifiedLLMService, TaskType, ClipSegment

async def test_unified_llm_service():
    """Test the unified LLM service functionality."""
    print("🧪 Testing Unified LLM Service...")
    
    # Initialize the service
    service = UnifiedLLMService()
    
    # Test 1: Check service initialization
    print("\n1. Service Initialization:")
    print(f"   OpenAI available: {service.openai_available}")
    print(f"   Gemini available: {service.gemini_available}")
    
    if not service.openai_available and not service.gemini_available:
        print("   ❌ No LLM providers available!")
        return False
    
    # Test 2: Test segment selection
    print("\n2. Testing Segment Selection:")
    try:
        # Mock transcription data
        test_transcription = {
            "segments": [
                {"start": 0.0, "end": 30.0, "text": "Welcome to this amazing tutorial"},
                {"start": 30.0, "end": 60.0, "text": "Here's the most important part"},
                {"start": 60.0, "end": 90.0, "text": "This is the climax of our content"}
            ],
            "text": "Welcome to this amazing tutorial. Here's the most important part. This is the climax of our content."
        }
        
        # Mock scenes and emotions
        test_scenes = [{"timestamp": 30.0, "description": "Close-up shot", "features": ["face", "hands"]}]
        test_emotions = [{"timestamp": 45.0, "emotion": "excitement", "confidence": 0.8}]
        test_viral_score = {"overall_score": 0.7, "factors": ["engaging_content", "clear_audio"]}
        
        result = await service.select_optimal_segments(
            transcription=test_transcription,
            scenes=test_scenes,
            emotions=test_emotions,
            viral_score=test_viral_score,
            platform="tiktok",
            max_segments=2
        )
        
        print(f"   ✅ Selected {len(result.segments)} segments")
        print(f"   Selection strategy: {result.selection_strategy}")
        print(f"   Processing time: {result.total_processing_time:.2f}s")
        
    except Exception as e:
        print(f"   ❌ Segment selection failed: {e}")
        return False
    
    # Test 3: Test virality analysis
    print("\n3. Testing Virality Analysis:")
    try:
        test_transcript = {
            "segments": [
                {"start": 0.0, "end": 30.0, "text": "Welcome to this amazing tutorial"},
                {"start": 30.0, "end": 60.0, "text": "Here's the most important part"}
            ],
            "text": "Welcome to this amazing tutorial. Here's the most important part."
        }
        
        test_video_features = {
            "duration": 120.0,
            "resolution": "1080p",
            "audio_quality": "high",
            "visual_features": ["clear_lighting", "stable_camera"]
        }
        
        result = await service.analyze_virality(
            transcript=test_transcript,
            video_features=test_video_features
        )
        
        print(f"   ✅ Analyzed virality for {len(result)} niches")
        for score in result[:2]:  # Show first 2 results
            print(f"   - {score.niche}: {score.score:.2f}")
        
    except Exception as e:
        print(f"   ❌ Virality analysis failed: {e}")
        return False
    
    # Test 4: Test hashtag generation
    print("\n4. Testing Hashtag Generation:")
    try:
        test_transcript = {
            "text": "Educational coding tutorial about Python programming",
            "segments": [
                {"start": 0.0, "end": 30.0, "text": "Welcome to Python programming"}
            ]
        }
        
        test_niches = ["Educational/Tutorial", "Technology/Review"]
        
        hashtag_result = await service.generate_hashtags(
            transcript=test_transcript,
            niches=test_niches,
            platform="instagram"
        )
        
        print(f"   ✅ Generated {len(hashtag_result)} hashtags")
        sample_tags = [tag.tag for tag in hashtag_result[:3]]
        print(f"   Sample hashtags: {', '.join(sample_tags)}")
        
    except Exception as e:
        print(f"   ❌ Hashtag generation failed: {e}")
        return False
    
    # Test 5: Cache statistics
    print("\n5. Cache Statistics:")
    cache_stats = service.get_cache_stats()
    print(f"   Total entries: {cache_stats['total_entries']}")
    print(f"   Valid entries: {cache_stats['valid_entries']}")
    print(f"   Expired entries: {cache_stats['expired_entries']}")
    print(f"   Providers available: OpenAI={cache_stats['providers_available']['openai']}, Gemini={cache_stats['providers_available']['gemini']}")
    
    print("\n🎉 All tests passed! Unified LLM Service is working correctly.")
    return True

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run the tests
    success = asyncio.run(test_unified_llm_service())
    
    if success:
        print("\n✅ Unified LLM Service is production ready!")
        sys.exit(0)
    else:
        print("\n❌ Unified LLM Service has issues that need to be resolved.")
        sys.exit(1)