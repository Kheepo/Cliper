#!/usr/bin/env python3
"""
Google Cloud Console OAuth Configuration Verification
This script helps verify and validate Google Cloud Console OAuth settings
for proper integration with Supabase authentication.
"""

import os
import json
import requests
from urllib.parse import urlencode, urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def verify_google_oauth_credentials():
    """Verify Google OAuth credentials format and validity"""
    print("\n=== GOOGLE OAUTH CREDENTIALS VERIFICATION ===")
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {client_secret[:15]}...{client_secret[-5:] if client_secret else 'None'}")
    
    # Validate Client ID format
    if not client_id:
        print("❌ Missing Google Client ID")
        return False
    
    if not client_id.endswith('.apps.googleusercontent.com'):
        print("❌ Invalid Client ID format - should end with .apps.googleusercontent.com")
        return False
    
    # Validate Client Secret format
    if not client_secret:
        print("❌ Missing Google Client Secret")
        return False
    
    if not client_secret.startswith('GOCSPX-'):
        print("❌ Invalid Client Secret format - should start with GOCSPX-")
        return False
    
    print("✅ Google OAuth credentials format is valid")
    return True

def check_required_redirect_uris():
    """Check required redirect URIs for Google Cloud Console"""
    print("\n=== REDIRECT URI REQUIREMENTS ===")
    
    supabase_url = os.getenv('SUPABASE_URL')
    if not supabase_url:
        print("❌ Missing Supabase URL")
        return False
    
    required_uris = [
        f"{supabase_url}/auth/v1/callback",
        "http://localhost:3001/auth/callback",  # Development callback
        "http://localhost:3000/auth/callback",  # Alternative dev port
    ]
    
    print("📋 REQUIRED AUTHORIZED REDIRECT URIs in Google Cloud Console:")
    for i, uri in enumerate(required_uris, 1):
        print(f"   {i}. {uri}")
    
    print("\n📋 REQUIRED AUTHORIZED JAVASCRIPT ORIGINS:")
    origins = [
        "http://localhost:3001",
        "http://localhost:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3000"
    ]
    
    for i, origin in enumerate(origins, 1):
        print(f"   {i}. {origin}")
    
    return True

def test_google_oauth_discovery():
    """Test Google OAuth 2.0 discovery endpoint"""
    print("\n=== GOOGLE OAUTH 2.0 DISCOVERY TEST ===")
    
    try:
        discovery_url = "https://accounts.google.com/.well-known/openid_configuration"
        response = requests.get(discovery_url, timeout=10)
        
        if response.status_code == 200:
            config = response.json()
            print("✅ Google OAuth 2.0 discovery endpoint accessible")
            print(f"   Authorization endpoint: {config.get('authorization_endpoint')}")
            print(f"   Token endpoint: {config.get('token_endpoint')}")
            print(f"   Userinfo endpoint: {config.get('userinfo_endpoint')}")
            print(f"   Supported scopes: {', '.join(config.get('scopes_supported', [])[:5])}...")
            return True
        else:
            print(f"❌ Failed to access discovery endpoint: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error accessing Google OAuth discovery: {e}")
        return False

def validate_oauth_flow_parameters():
    """Validate OAuth flow parameters used by Supabase"""
    print("\n=== OAUTH FLOW PARAMETERS VALIDATION ===")
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    supabase_url = os.getenv('SUPABASE_URL')
    
    if not client_id or not supabase_url:
        print("❌ Missing required configuration")
        return False
    
    # Standard OAuth 2.0 parameters that Supabase uses
    oauth_params = {
        'client_id': client_id,
        'redirect_uri': f"{supabase_url}/auth/v1/callback",
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    
    print("📋 OAuth 2.0 Flow Parameters:")
    for key, value in oauth_params.items():
        print(f"   {key}: {value}")
    
    # Construct authorization URL
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(oauth_params)
    print(f"\n📋 Generated Authorization URL:")
    print(f"   {auth_url[:100]}...")
    
    return True

def check_common_configuration_issues():
    """Check for common Google Cloud Console configuration issues"""
    print("\n=== COMMON CONFIGURATION ISSUES CHECK ===")
    
    issues_found = []
    
    print("🔍 Checking for common issues...")
    
    # Check 1: OAuth consent screen
    print("\n1. OAuth Consent Screen Requirements:")
    print("   ✓ App name must be set")
    print("   ✓ User support email must be provided")
    print("   ✓ Developer contact information must be provided")
    print("   ✓ Scopes: email, profile, openid must be added")
    
    # Check 2: API enablement
    print("\n2. Required APIs (must be enabled):")
    required_apis = [
        "Google+ API (legacy) or People API",
        "Google Identity and Access Management (IAM) API",
        "OAuth 2.0 API"
    ]
    
    for api in required_apis:
        print(f"   ✓ {api}")
    
    # Check 3: Client type
    print("\n3. OAuth Client Configuration:")
    print("   ✓ Application type: Web application")
    print("   ✓ Authorized JavaScript origins configured")
    print("   ✓ Authorized redirect URIs configured")
    
    return len(issues_found) == 0

def generate_google_cloud_setup_guide():
    """Generate step-by-step Google Cloud Console setup guide"""
    print("\n" + "="*70)
    print("GOOGLE CLOUD CONSOLE SETUP GUIDE")
    print("="*70)
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    supabase_url = os.getenv('SUPABASE_URL')
    
    print("\n📋 STEP-BY-STEP CONFIGURATION:")
    
    print("\n1. 🌐 Access Google Cloud Console:")
    print("   - Go to: https://console.cloud.google.com/")
    print("   - Sign in with your Google account")
    
    print("\n2. 🔧 Configure OAuth Consent Screen:")
    print("   - Navigate to: APIs & Services > OAuth consent screen")
    print("   - Choose 'External' user type (for public apps)")
    print("   - Fill in required fields:")
    print("     * App name: Your app name")
    print("     * User support email: Your email")
    print("     * Developer contact: Your email")
    print("   - Add scopes: email, profile, openid")
    print("   - Save and continue")
    
    print("\n3. 🔑 Create OAuth 2.0 Credentials:")
    print("   - Navigate to: APIs & Services > Credentials")
    print("   - Click 'Create Credentials' > 'OAuth 2.0 Client IDs'")
    print("   - Application type: Web application")
    print("   - Name: Your app name")
    
    print("\n4. 🔗 Configure Authorized URIs:")
    print("   Authorized JavaScript origins:")
    print("     - http://localhost:3001")
    print("     - http://localhost:3000")
    print("     - http://127.0.0.1:3001")
    print("     - http://127.0.0.1:3000")
    
    print("\n   Authorized redirect URIs:")
    if supabase_url:
        print(f"     - {supabase_url}/auth/v1/callback")
    print("     - http://localhost:3001/auth/callback")
    print("     - http://localhost:3000/auth/callback")
    
    print("\n5. 📋 Copy Credentials:")
    print("   - Copy Client ID and Client Secret")
    print("   - Add them to your .env file")
    if client_id:
        print(f"   - Your current Client ID: {client_id}")
    
    print("\n6. ✅ Enable Required APIs:")
    print("   - Navigate to: APIs & Services > Library")
    print("   - Search and enable:")
    print("     * Google+ API (or People API)")
    print("     * Google Identity and Access Management (IAM) API")
    
    print("\n7. 🧪 Test Configuration:")
    print("   - Save all changes")
    print("   - Wait 5-10 minutes for changes to propagate")
    print("   - Test OAuth flow in your application")

def main():
    """Main diagnostic function"""
    print("\n" + "="*70)
    print("GOOGLE CLOUD CONSOLE OAUTH CONFIGURATION VERIFICATION")
    print("="*70)
    
    results = {
        'credentials_valid': verify_google_oauth_credentials(),
        'redirect_uris_checked': check_required_redirect_uris(),
        'discovery_accessible': test_google_oauth_discovery(),
        'flow_parameters_valid': validate_oauth_flow_parameters(),
        'common_issues_checked': check_common_configuration_issues()
    }
    
    print("\n=== VERIFICATION SUMMARY ===")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    # Generate setup guide
    generate_google_cloud_setup_guide()
    
    print("\n=== CRITICAL NEXT STEPS ===")
    print("1. 🔧 Complete Google Cloud Console configuration (see guide above)")
    print("2. 🔧 Enable Google provider in Supabase dashboard")
    print("3. 🧪 Test the complete OAuth flow")
    
    return all(results.values())

if __name__ == "__main__":
    main()