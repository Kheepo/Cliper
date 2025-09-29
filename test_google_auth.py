#!/usr/bin/env python3
"""
Test script to reproduce the Google OAuth error
"""

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_supabase_auth_endpoint():
    """Test the Supabase auth endpoint directly"""
    supabase_url = os.getenv('VITE_SUPABASE_URL')
    anon_key = os.getenv('VITE_SUPABASE_ANON_KEY')
    
    if not supabase_url or not anon_key:
        print("❌ Missing Supabase environment variables")
        return False
    
    # Test the auth providers endpoint
    auth_url = f"{supabase_url}/auth/v1/authorize"
    
    headers = {
        'apikey': anon_key,
        'Authorization': f'Bearer {anon_key}',
        'Content-Type': 'application/json'
    }
    
    # Simulate the Google OAuth request
    params = {
        'provider': 'google',
        'redirect_to': 'http://localhost:5173/auth/callback'
    }
    
    print(f"Testing Google OAuth at: {auth_url}")
    print(f"Headers: {headers}")
    print(f"Params: {params}")
    
    try:
        response = requests.get(auth_url, headers=headers, params=params)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 302:
            print("✅ Redirect response received (expected for OAuth)")
            print(f"Location: {response.headers.get('Location', 'No location header')}")
            return True
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error response: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Response text: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {str(e)}")
        return False

def test_supabase_settings():
    """Check Supabase auth settings"""
    supabase_url = os.getenv('VITE_SUPABASE_URL')
    service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not service_role_key:
        print("❌ Missing Supabase service role key")
        return False
    
    settings_url = f"{supabase_url}/auth/v1/settings"
    
    headers = {
        'apikey': service_role_key,
        'Authorization': f'Bearer {service_role_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(settings_url, headers=headers)
        
        if response.status_code == 200:
            settings = response.json()
            external_providers = settings.get('external', {})
            
            print("\n=== Supabase Auth Settings ===")
            print(f"External providers: {list(external_providers.keys())}")
            
            if 'google' in external_providers:
                google_config = external_providers['google']
                print(f"Google config: {google_config}")
                
                if isinstance(google_config, dict):
                    enabled = google_config.get('enabled', False)
                    client_id = google_config.get('client_id', 'Not set')
                    print(f"Google enabled: {enabled}")
                    print(f"Google client ID: {client_id}")
                else:
                    print(f"Google enabled: {google_config}")
            else:
                print("❌ Google provider not found in settings")
                
            return True
        else:
            print(f"❌ Failed to get settings: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Settings request failed: {str(e)}")
        return False

def main():
    print("🔍 Testing Google OAuth Configuration...\n")
    
    # Test 1: Check Supabase settings
    print("1. Checking Supabase auth settings...")
    settings_ok = test_supabase_settings()
    
    print("\n" + "="*60)
    
    # Test 2: Test the actual auth endpoint
    print("2. Testing Google OAuth endpoint...")
    auth_ok = test_supabase_auth_endpoint()
    
    print("\n" + "="*60)
    print("\n📋 SUMMARY:")
    print(f"Settings check: {'✅ PASS' if settings_ok else '❌ FAIL'}")
    print(f"Auth endpoint: {'✅ PASS' if auth_ok else '❌ FAIL'}")
    
    if not settings_ok or not auth_ok:
        print("\n🔧 TROUBLESHOOTING STEPS:")
        print("1. Verify Google provider is enabled in Supabase Dashboard")
        print("2. Check Google OAuth client ID and secret are correctly set")
        print("3. Ensure redirect URI is properly configured in Google Console")
        print("4. Wait a few minutes for changes to propagate")
        print("5. Try restarting your development servers")

if __name__ == "__main__":
    main()