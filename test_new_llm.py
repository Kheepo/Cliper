#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.services.llm_service import LLMService

async def test_llm_service():
    """Test the new LLM service functionality."""
    try:
        print("Testing new LLM Service...")
        
        # Initialize service
        service = LLMService()
        print("✓ LLM Service initialized successfully")
        
        # Test virality analysis
        print("\nTesting virality analysis...")
        test_transcript = [
            {"start": 0.0, "end": 5.0, "text": "Welcome to this amazing tutorial about AI!"},
            {"start": 5.0, "end": 10.0, "text": "Today we'll learn something incredible that will blow your mind."},
            {"start": 10.0, "end": 15.0, "text": "This technique has helped thousands of people achieve success."}
        ]
        
        test_metadata = {
            "duration": 15.0,
            "title": "Amazing AI Tutorial",
            "description": "Learn AI techniques"
        }
        
        try:
            result = await service.analyze_virality(test_transcript, test_metadata)
            print(f"✓ Virality analysis successful: {len(result)} scores generated")
            for score in result:
                print(f"  - {score.start_time:.1f}s-{score.end_time:.1f}s: Score {score.score:.2f} ({score.content_type})")
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n🎉 All tests passed! New LLM service is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_llm_service())
    sys.exit(0 if success else 1)