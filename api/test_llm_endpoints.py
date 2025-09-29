#!/usr/bin/env python3
"""
Simple test script to verify unified LLM service endpoints
"""

import asyncio
import sys
import os

# Add the api directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_llm_service():
    """Test the unified LLM service directly"""
    try:
        from services.unified_llm_service import unified_llm_service
        
        print("Testing Unified LLM Service...")
        print("=" * 50)
        
        # Test 1: Check service status
        print("\n1. Service Status:")
        print(f"   OpenAI Available: {unified_llm_service.openai_available}")
        print(f"   Gemini Available: {unified_llm_service.gemini_available}")
        
        # Test 2: Test hashtag generation
        print("\n2. Testing Hashtag Generation:")
        try:
            transcript = {"text": "This is a test video about cooking pasta", "segments": []}
            niches = ["cooking", "food"]
            hashtags = await unified_llm_service.generate_hashtags(
                transcript=transcript,
                niches=niches,
                platform="tiktok"
            )
            print(f"   ✅ Generated {len(hashtags)} hashtags")
            for hashtag in hashtags[:3]:  # Show first 3
                print(f"   - {hashtag.tag} (score: {hashtag.relevance_score})")
        except Exception as e:
            print(f"   ❌ Hashtag generation failed: {e}")
        
        # Test 3: Test virality analysis
        print("\n3. Testing Virality Analysis:")
        try:
            transcript = {"text": "Amazing cooking tutorial with secret ingredients"}
            video_features = {"duration": 120.0, "resolution": "1080p"}
            result = await unified_llm_service.analyze_virality(
                transcript=transcript,
                video_features=video_features
            )
            print(f"   ✅ Virality analysis completed")
            print(f"   - Overall score: {result.overall_score}")
            print(f"   - Viral moments: {len(result.viral_moments)}")
        except Exception as e:
            print(f"   ❌ Virality analysis failed: {e}")
        
        print("\n" + "=" * 50)
        print("Test completed!")
        
    except Exception as e:
        print(f"Failed to import or test LLM service: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_service())