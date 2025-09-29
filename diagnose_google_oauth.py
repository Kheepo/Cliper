#!/usr/bin/env python3
"""
Google OAuth Configuration Diagnostic Script
Diagnoses and tests Supabase Google OAuth provider configuration
"""

import requests
import json
import os
from typing import Dict, Any

# Supabase configuration
SUPABASE_URL = "https://stzdywhbdovjojtqxmsd.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0emR5d2hiZG92am9qdHF4bXNkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc1NDA1NjgsImV4cCI6MjA3MzExNjU2OH0.R7GzJ18oGs4JQMBqdoq8h3jH_FQr4W8d0xJ_Wf9Hzm8"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0emR5d2hiZG92am9qdHF4bXNkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzU0MDU2OCwiZXhwIjoyMDczMTE2NTY4fQ.Xg6iDR-YMjID73OzQfJ362B-xYBadJeb6Qh2NxVtAmU"

def check_auth_providers() -> Dict[str, Any]:
    """
    Check which authentication providers are enabled in Supabase
    """
    print("🔍 Checking Supabase authentication providers...")
    
    # Check auth settings endpoint
    url = f"{SUPABASE_URL}/auth/v1/settings"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Auth settings response status: {response.status_code}")
        
        if response.status_code == 200:
            settings = response.json()
            print("✅ Successfully retrieved auth settings")
            
            # Check for external providers
            external_providers = settings.get('external', {})
            print(f"\n📋 External providers configuration:")
            
            for provider, config in external_providers.items():
                enabled = config.get('enabled', False)
                status = "✅ ENABLED" if enabled else "❌ DISABLED"
                print(f"  {provider}: {status}")
                
                if provider == 'google' and enabled:
                    print(f"    - Client ID: {config.get('client_id', 'Not set')}")
                    print(f"    - Redirect URL: {config.get('redirect_url', 'Not set')}")
            
            return settings
        else:
            print(f"❌ Failed to get auth settings: {response.status_code}")
            print(f"Response: {response.text}")
            return {}
            
    except Exception as e:
        print(f"❌ Error checking auth providers: {str(e)}")
        return {}

def test_google_oauth_endpoint() -> bool:
    """
    Test if Google OAuth endpoint is accessible
    """
    print("\n🔍 Testing Google OAuth endpoint...")
    
    # Test the Google OAuth URL
    oauth_url = f"{SUPABASE_URL}/auth/v1/authorize"
    params = {
        "provider": "google",
        "redirect_to": "http://localhost:3000/auth/callback"
    }
    
    headers = {
        "apikey": SUPABASE_ANON_KEY
    }
    
    try:
        response = requests.get(oauth_url, params=params, headers=headers, allow_redirects=False)
        print(f"OAuth endpoint response status: {response.status_code}")
        
        if response.status_code == 302:
            print("✅ OAuth endpoint is working (redirect response)")
            redirect_url = response.headers.get('Location', '')
            if 'google' in redirect_url.lower():
                print("✅ Redirecting to Google OAuth")
                return True
            else:
                print(f"⚠️  Unexpected redirect URL: {redirect_url}")
                return False
        elif response.status_code == 400:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get('msg', 'Unknown error')
            print(f"❌ OAuth endpoint error: {error_msg}")
            return False
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing OAuth endpoint: {str(e)}")
        return False

def check_frontend_config() -> Dict[str, Any]:
    """
    Check frontend Supabase configuration
    """
    print("\n🔍 Checking frontend Supabase configuration...")
    
    config_file = "src/lib/supabase.ts"
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            content = f.read()
            print("✅ Found Supabase config file")
            
            # Check if URL and key are properly set
            if SUPABASE_URL in content:
                print("✅ Supabase URL is correctly configured")
            else:
                print("❌ Supabase URL mismatch in config")
                
            if SUPABASE_ANON_KEY[:20] in content:
                print("✅ Supabase anon key is correctly configured")
            else:
                print("❌ Supabase anon key mismatch in config")
                
            return {"config_found": True, "content": content}
    else:
        print("❌ Supabase config file not found")
        return {"config_found": False}

def generate_setup_instructions() -> str:
    """
    Generate step-by-step setup instructions for Google OAuth
    """
    instructions = """
🚀 GOOGLE OAUTH SETUP INSTRUCTIONS

📋 STEP 1: Google Cloud Console Setup
1. Go to https://console.cloud.google.com/
2. Create a new project or select existing project
3. Enable Google+ API and Google Identity API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
5. Set Application type to "Web application"
6. Add Authorized JavaScript origins:
   - http://localhost:3000 (for development)
   - https://your-domain.com (for production)
7. Add Authorized redirect URIs:
   - https://stzdywhbdovjojtqxmsd.supabase.co/auth/v1/callback
8. Copy the Client ID and Client Secret

📋 STEP 2: Supabase Dashboard Setup
1. Go to https://supabase.com/dashboard/project/stzdywhbdovjojtqxmsd
2. Navigate to Authentication → Providers
3. Find "Google" provider and click to configure
4. Toggle "Enable sign in with Google" to ON
5. Enter your Google Client ID
6. Enter your Google Client Secret
7. Click "Save"

📋 STEP 3: Verification
1. Run this diagnostic script again
2. Test Google OAuth in your application
3. Check browser network tab for any errors

⚠️  IMPORTANT NOTES:
- Make sure redirect URI in Google Console matches Supabase exactly
- Client ID and Secret must be from the same Google Cloud project
- Changes may take a few minutes to propagate
"""
    return instructions

def main():
    """
    Main diagnostic function
    """
    print("🔧 GOOGLE OAUTH DIAGNOSTIC TOOL")
    print("=" * 50)
    
    # Check auth providers
    settings = check_auth_providers()
    
    # Test OAuth endpoint
    oauth_working = test_google_oauth_endpoint()
    
    # Check frontend config
    frontend_config = check_frontend_config()
    
    # Generate report
    print("\n" + "=" * 50)
    print("📊 DIAGNOSTIC REPORT")
    print("=" * 50)
    
    google_enabled = False
    if settings:
        google_config = settings.get('external', {}).get('google', {})
        google_enabled = google_config.get('enabled', False)
    
    print(f"Google Provider Enabled: {'✅ YES' if google_enabled else '❌ NO'}")
    print(f"OAuth Endpoint Working: {'✅ YES' if oauth_working else '❌ NO'}")
    print(f"Frontend Config Found: {'✅ YES' if frontend_config.get('config_found') else '❌ NO'}")
    
    if not google_enabled:
        print("\n🚨 ROOT CAUSE IDENTIFIED:")
        print("Google OAuth provider is NOT ENABLED in Supabase")
        print("\n📋 SOLUTION:")
        print(generate_setup_instructions())
    elif not oauth_working:
        print("\n🚨 ISSUE IDENTIFIED:")
        print("Google provider is enabled but OAuth endpoint is not working")
        print("This might be due to incorrect Google Cloud Console configuration")
    else:
        print("\n✅ All checks passed! Google OAuth should be working.")
    
    # Save detailed report
    report = {
        "timestamp": "2025-01-22",
        "supabase_url": SUPABASE_URL,
        "google_enabled": google_enabled,
        "oauth_endpoint_working": oauth_working,
        "frontend_config_found": frontend_config.get('config_found', False),
        "auth_settings": settings,
        "recommendations": [
            "Enable Google OAuth in Supabase Dashboard" if not google_enabled else "Google OAuth is enabled",
            "Configure Google Cloud Console properly" if not oauth_working else "OAuth endpoint is working",
            "Verify frontend configuration" if not frontend_config.get('config_found') else "Frontend config is present"
        ]
    }
    
    with open('google_oauth_diagnostic_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: google_oauth_diagnostic_report.json")

if __name__ == "__main__":
    main()