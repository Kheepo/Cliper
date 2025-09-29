import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the api directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import LLM service module directly
import importlib.util
spec = importlib.util.spec_from_file_location("llm_service", "services/llm_service.py")
llm_service_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(llm_service_module)
LLMService = llm_service_module.LLMService

async def test_llm_service():
    """Test the new LLM service."""
    try:
        print("Testing LLM Service...")
        
        # Initialize service
        service = LLMService()
        print("✓ LLM Service initialized successfully")
        
        # Test data
        test_transcript = [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Welcome to this amazing tutorial on viral content creation!"
            },
            {
                "start": 5.0,
                "end": 10.0,
                "text": "Today we're going to learn some incredible techniques that will blow your mind."
            },
            {
                "start": 10.0,
                "end": 15.0,
                "text": "This secret method has helped millions of creators go viral overnight."
            }
        ]
        
        test_metadata = {
            "duration": 15.0,
            "title": "Viral Content Creation Tutorial",
            "description": "Learn the secrets of viral content"
        }
        
        # Test virality analysis
        print("\nTesting virality analysis...")
        scores = await service.analyze_virality(
            test_transcript, 
            test_metadata,
            target_platform="youtube",
            content_type="educational"
        )
        
        print(f"✓ Virality analysis completed")
        print(f"✓ Generated {len(scores)} scores")
        
        # Display results
        for i, score in enumerate(scores):
            print(f"\nScore {i+1}:")
            print(f"  Time: {score.start_time}s - {score.end_time}s")
            print(f"  Score: {score.score}")
            print(f"  Emotion: {score.emotion}")
            print(f"  Keywords: {score.keywords}")
            print(f"  Reasons: {score.reasons}")
            print(f"  Engagement factors: {score.engagement_factors}")
        
        print("\n✓ All tests passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_service())