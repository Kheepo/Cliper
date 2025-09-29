#!/usr/bin/env python3
"""
Final test to verify API key configuration.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api_keys():
    """Test API key configuration."""
    print("🔧 Final API Key Configuration Test")
    print("=" * 50)
    
    # Check environment variables
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    print("📋 Environment Variables:")
    print(f"  OPENAI_API_KEY: {'✅ Set' if openai_key else '❌ Missing'}")
    if openai_key:
        print(f"    Length: {len(openai_key)}")
        print(f"    Starts with: {openai_key[:15]}...")
    
    print(f"  GEMINI_API_KEY: {'✅ Set' if gemini_key else '❌ Missing'}")
    if gemini_key:
        print(f"    Length: {len(gemini_key)}")
        print(f"    Starts with: {gemini_key[:15]}...")
    
    # Test OpenAI
    print("\n🤖 Testing OpenAI:")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        print("  ✅ OpenAI client initialized")
        
        # Simple test
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'OpenAI working' in 2 words"}],
            max_tokens=10
        )
        print(f"  ✅ OpenAI test successful: {response.choices[0].message.content}")
    except Exception as e:
        print(f"  ❌ OpenAI test failed: {e}")
    
    # Test Gemini
    print("\n🧠 Testing Gemini:")
    try:
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-1.5-pro')
        print("  ✅ Gemini client initialized")
        
        # Simple test
        response = model.generate_content("Say 'Gemini working' in 2 words")
        print(f"  ✅ Gemini test successful: {response.text}")
    except Exception as e:
        print(f"  ❌ Gemini test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 API Key Configuration Test Complete")

if __name__ == "__main__":
    test_api_keys()