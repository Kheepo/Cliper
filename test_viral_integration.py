#!/usr/bin/env python3
"""
Integration test for viral scoring system
Tests the complete viral scoring pipeline from video analysis to API response
"""

import asyncio
import json
import sys
import os
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.services.viral_scoring import ViralScoringService, ViralFactorType
from api.models.pydantic_models import PlatformEnum, ViralityScore
from api.services.unified_llm_service import UnifiedLLMService

async def test_viral_scoring_service():
    """Test the viral scoring service directly"""
    print("🧪 Testing Viral Scoring Service...")
    
    try:
        # Initialize service
        viral_service = ViralScoringService()
        print("✅ ViralScoringService initialized successfully")
        
        # Test data
        sample_transcription = {
            "text": "This is an amazing breakthrough in AI technology that will change everything! The results are incredible and everyone needs to see this.",
            "segments": [
                {"start": 0, "end": 15, "text": "This is an amazing breakthrough in AI technology"},
                {"start": 15, "end": 30, "text": "that will change everything! The results are incredible"},
                {"start": 30, "end": 45, "text": "and everyone needs to see this."}
            ]
        }
        
        sample_scenes = [
            {"timestamp": 5, "scene_type": "talking_head", "complexity": 0.7},
            {"timestamp": 20, "scene_type": "demonstration", "complexity": 0.9},
            {"timestamp": 35, "scene_type": "results", "complexity": 0.8}
        ]
        
        sample_emotions = [
            {"timestamp": 10, "dominant_emotion": "excitement", "confidence": 0.9},
            {"timestamp": 25, "dominant_emotion": "amazement", "confidence": 0.8},
            {"timestamp": 40, "dominant_emotion": "enthusiasm", "confidence": 0.85}
        ]
        
        sample_metadata = {
            "duration": 45,
            "file_size": 10000000,
            "resolution": "1920x1080",
            "fps": 30
        }
        
        # Test analyze_viral_potential
        print("🔍 Testing analyze_viral_potential...")
        start_time = time.time()
        
        analysis = await viral_service.analyze_viral_potential(
            transcription=sample_transcription,
            scenes=sample_scenes,
            emotions=sample_emotions,
            video_metadata=sample_metadata,
            target_platforms=[PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM, PlatformEnum.YOUTUBE]
        )
        
        processing_time = time.time() - start_time
        print(f"✅ Analysis completed in {processing_time:.2f}s")
        
        # Verify results
        print(f"📊 Overall viral score: {analysis.overall_viral_score:.3f}")
        print(f"🎯 Confidence: {analysis.confidence:.3f}")
        print(f"🏆 Platform scores: {len(analysis.platform_scores)} platforms")
        print(f"⚡ Viral moments: {len(analysis.viral_moments)} moments")
        print(f"🔥 Viral factors: {len(analysis.viral_factors)} factors")
        
        # Check platform scores
        for platform, score in analysis.platform_scores.items():
            print(f"  📱 {platform}: {score.score:.3f} (confidence: {score.confidence:.3f})")
        
        # Check viral factors
        print("🎭 Top viral factors:")
        for i, factor in enumerate(analysis.viral_factors[:3]):
            print(f"  {i+1}. {factor.factor_type.value}: {factor.score:.3f} - {factor.reasoning[:50]}...")
        
        # Check viral moments
        print("⚡ Viral moments:")
        for i, moment in enumerate(analysis.viral_moments[:3]):
            print(f"  {i+1}. {moment.start_time:.1f}s-{moment.end_time:.1f}s: {moment.viral_score:.3f} - {moment.description[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Viral scoring service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_comprehensive_viral_analysis():
    """Test the comprehensive viral analysis method"""
    print("\n🧪 Testing Comprehensive Viral Analysis...")
    
    try:
        viral_service = ViralScoringService()
        
        # Test comprehensive analysis
        result = await viral_service.analyze_comprehensive_viral_potential(
            video_url="test_video.mp4",
            clip_segments=[
                {"start_time": 0, "end_time": 30, "text": "Amazing AI breakthrough"},
                {"start_time": 30, "end_time": 60, "text": "Incredible results revealed"}
            ],
            platforms=["tiktok", "instagram"],
            include_insights=True
        )
        
        print(f"✅ Comprehensive analysis completed")
        print(f"📊 Overall score: {result.overall_score:.3f}")
        print(f"🎯 Confidence: {result.confidence:.3f}")
        print(f"📱 Platform scores: {len(result.platform_scores)} platforms")
        print(f"⚡ Viral moments: {len(result.viral_moments)} moments")
        print(f"#️⃣ Hashtags: {len(result.hashtags)} hashtags")
        print(f"📝 Posting recommendations: {len(result.posting_recommendations)} recommendations")
        print(f"💡 Insights: {len(result.insights)} insights")
        
        # Show some results
        if result.hashtags:
            print("🏷️ Sample hashtags:")
            for hashtag in result.hashtags[:3]:
                print(f"  {hashtag.tag} (relevance: {hashtag.relevance_score:.3f})")
        
        if result.posting_recommendations:
            print("📅 Sample posting recommendations:")
            for rec in result.posting_recommendations[:2]:
                print(f"  {rec.platform}: {rec.optimal_time} - {rec.caption[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Comprehensive viral analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_llm_service_integration():
    """Test LLM service integration"""
    print("\n🧪 Testing LLM Service Integration...")
    
    try:
        llm_service = UnifiedLLMService()
        
        # Test LLM response
        test_prompt = """
        Analyze this video content for viral potential:
        Text: "Amazing AI breakthrough that changes everything!"
        Duration: 30 seconds
        Platform: TikTok
        
        Provide viral factors analysis.
        """
        
        response = await llm_service.generate_response(
            prompt=test_prompt,
            task_type="viral_analysis"
        )
        
        print(f"✅ LLM service responded successfully")
        print(f"📝 Response length: {len(response.content)} characters")
        print(f"🎯 Confidence: {response.confidence:.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM service integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_platform_specific_scoring():
    """Test platform-specific scoring algorithms"""
    print("\n🧪 Testing Platform-Specific Scoring...")
    
    try:
        viral_service = ViralScoringService()
        
        # Test each platform
        platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM, PlatformEnum.YOUTUBE]
        
        sample_transcription = {
            "text": "Check out this incredible dance move that's going viral!",
            "segments": [{"start": 0, "end": 15, "text": "Check out this incredible dance move that's going viral!"}]
        }
        
        for platform in platforms:
            print(f"🎯 Testing {platform.value} scoring...")
            
            analysis = await viral_service.analyze_viral_potential(
                transcription=sample_transcription,
                target_platforms=[platform]
            )
            
            platform_score = analysis.platform_scores.get(platform.value)
            if platform_score:
                print(f"  📊 Score: {platform_score.score:.3f}")
                print(f"  🎯 Confidence: {platform_score.confidence:.3f}")
                print(f"  ⏱️ Ideal duration: {platform_score.ideal_duration[0]}-{platform_score.ideal_duration[1]}s")
                print(f"  💡 Suggestions: {len(platform_score.optimization_suggestions)} suggestions")
            else:
                print(f"  ❌ No score found for {platform.value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Platform-specific scoring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all integration tests"""
    print("🚀 Starting Viral Scoring Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Viral Scoring Service", test_viral_scoring_service),
        ("Comprehensive Analysis", test_comprehensive_viral_analysis),
        ("LLM Service Integration", test_llm_service_integration),
        ("Platform-Specific Scoring", test_platform_specific_scoring)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All viral scoring integration tests PASSED!")
        return True
    else:
        print("⚠️ Some viral scoring integration tests FAILED!")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)