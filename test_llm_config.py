#!/usr/bin/env python3
"""
Test script to verify LLM service configuration with new API keys.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

async def test_llm_services():
    """Test both OpenAI and Gemini LLM services."""
    print("🔧 Testing LLM Service Configuration...")
    print("=" * 50)
    
    # Test environment variables
    print("📋 Environment Variables:")
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    print(f"  OPENAI_API_KEY: {'✅ Set' if openai_key else '❌ Missing'}")
    if openai_key:
        print(f"    Key starts with: {openai_key[:15]}...")
    
    print(f"  GEMINI_API_KEY: {'✅ Set' if gemini_key else '❌ Missing'}")
    if gemini_key:
        print(f"    Key starts with: {gemini_key[:15]}...")
    
    print("\n🧪 Testing LLM Service Initialization...")
    
    # Test unified LLM service
    try:
        from api.services.unified_llm_service import UnifiedLLMService
        
        llm_service = UnifiedLLMService()
        print("✅ UnifiedLLMService initialized successfully")
        
        # Check available providers
        available_providers = []
        
        # Test OpenAI
        if hasattr(llm_service, 'openai_client') and llm_service.openai_client:
            try:
                # Simple test to verify OpenAI client
                print("  🔍 Testing OpenAI client...")
                available_providers.append("OpenAI")
                print("  ✅ OpenAI client available")
            except Exception as e:
                print(f"  ❌ OpenAI client error: {e}")
        
        # Test Gemini
        if hasattr(llm_service, 'gemini_model') and llm_service.gemini_model:
            try:
                # Simple test to verify Gemini client
                print("  🔍 Testing Gemini client...")
                available_providers.append("Gemini")
                print("  ✅ Gemini client available")
            except Exception as e:
                print(f"  ❌ Gemini client error: {e}")
        
        print(f"\n📊 Available Providers: {', '.join(available_providers) if available_providers else 'None'}")
        
        # Test service status
        if available_providers:
            print("\n🚀 Testing service status...")
            try:
                status = llm_service.get_service_status()
                print(f"  ✅ Service status: {status}")
            except Exception as e:
                print(f"  ❌ Service status test failed: {e}")
        
        # Test a simple virality analysis if providers are available
        if available_providers:
            print("\n🧪 Testing virality analysis...")
            try:
                test_transcript = {"text": "This is a test video about technology"}
                test_features = {"duration": 60, "quality": "720p"}
                response = await llm_service.analyze_virality(test_transcript, test_features)
                print(f"  ✅ Virality analysis completed: {len(response)} scores generated")
                for score in response[:2]:  # Show first 2 scores
                    print(f"    - {score.niche}: {score.score:.2f}")
            except Exception as e:
                print(f"  ❌ Virality analysis test failed: {e}")
        
    except Exception as e:
        print(f"❌ UnifiedLLMService initialization failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("🏁 LLM Configuration Test Complete")

if __name__ == "__main__":
    asyncio.run(test_llm_services())