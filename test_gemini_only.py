#!/usr/bin/env python3
"""
Test script specifically for Gemini API configuration.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_gemini_api():
    """Test Gemini API directly."""
    print("🔧 Testing Gemini API Configuration...")
    print("=" * 50)
    
    # Check environment variable
    gemini_key = os.getenv("GEMINI_API_KEY")
    print(f"GEMINI_API_KEY: {'✅ Set' if gemini_key else '❌ Missing'}")
    if gemini_key:
        print(f"Key: {gemini_key}")
        print(f"Key length: {len(gemini_key)}")
        print(f"Starts with 'your-': {gemini_key.startswith('your-')}")
    
    # Test Gemini import and initialization
    try:
        import google.generativeai as genai
        print("✅ google.generativeai imported successfully")
        
        if gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                
                # List available models
                try:
                    models = genai.list_models()
                    print("📋 Available models:")
                    for model in models:
                        if 'generateContent' in model.supported_generation_methods:
                            print(f"  - {model.name}")
                except Exception as e:
                    print(f"⚠️ Could not list models: {e}")
                
                # Try different model names (using the full model names from the list)
                model_names = ['models/gemini-1.5-pro', 'models/gemini-pro', 'models/gemini-flash-latest']
                for model_name in model_names:
                    try:
                        model = genai.GenerativeModel(model_name)
                        print(f"✅ Gemini model '{model_name}' initialized successfully")
                        
                        # Test a simple generation
                        response = model.generate_content("Say hello in 3 words")
                        print(f"✅ Test generation successful: {response.text}")
                        break
                    except Exception as e:
                        print(f"❌ Model '{model_name}' failed: {e}")
                        continue
                    
            except Exception as e:
                print(f"❌ Gemini configuration failed: {e}")
        else:
            print("❌ No API key to test")
            
    except ImportError as e:
        print(f"❌ Failed to import google.generativeai: {e}")
    
    print("=" * 50)

if __name__ == "__main__":
    test_gemini_api()