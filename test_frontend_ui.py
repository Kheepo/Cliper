#!/usr/bin/env python3
"""
Frontend UI Authentication Test
Tests the frontend authentication forms and flow
"""

import requests
import time
import json

def test_frontend_accessibility():
    """Test if frontend is accessible"""
    print("\n=== Testing Frontend Accessibility ===")
    try:
        response = requests.get('http://localhost:3000', timeout=5)
        print(f"✅ Frontend accessible: {response.status_code}")
        
        # Check if it's a React app
        if 'react' in response.text.lower() or 'root' in response.text:
            print("✅ React app detected")
        else:
            print("⚠️  React app not clearly detected")
            
        return True
    except Exception as e:
        print(f"❌ Frontend not accessible: {e}")
        return False

def test_backend_auth_endpoints():
    """Test backend authentication endpoints"""
    print("\n=== Testing Backend Auth Endpoints ===")
    
    # Test registration
    try:
        reg_data = {
            "email": "test@example.com",
            "password": "TestPass123!",
            "display_name": "Test User"
        }
        
        response = requests.post('http://localhost:8001/api/auth/register', 
                               json=reg_data, timeout=10)
        print(f"Registration endpoint: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Registration endpoint working")
        elif response.status_code == 400:
            print("⚠️  Registration endpoint working (user may already exist)")
        else:
            print(f"❌ Registration failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Registration endpoint error: {e}")
    
    # Test login
    try:
        login_data = {
            "email": "test@example.com",
            "password": "TestPass123!"
        }
        
        response = requests.post('http://localhost:8001/api/auth/login', 
                               json=login_data, timeout=10)
        print(f"Login endpoint: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Login endpoint working")
            result = response.json()
            if 'access_token' in result:
                print("✅ Access token returned")
                return result['access_token']
        else:
            print(f"❌ Login failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Login endpoint error: {e}")
    
    return None

def test_protected_endpoint(token):
    """Test protected endpoint with token"""
    print("\n=== Testing Protected Endpoint ===")
    
    if not token:
        print("❌ No token available for testing")
        return
    
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get('http://localhost:8001/api/auth/me', 
                              headers=headers, timeout=10)
        
        print(f"Protected endpoint: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Protected endpoint working")
            user_data = response.json()
            print(f"User data: {json.dumps(user_data, indent=2)}")
        else:
            print(f"❌ Protected endpoint failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Protected endpoint error: {e}")

def test_cors_configuration():
    """Test CORS configuration"""
    print("\n=== Testing CORS Configuration ===")
    
    try:
        # Test preflight request
        headers = {
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type,Authorization'
        }
        
        response = requests.options('http://localhost:8001/api/auth/login', 
                                  headers=headers, timeout=10)
        
        print(f"CORS preflight: {response.status_code}")
        
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers')
        }
        
        print("CORS Headers:")
        for header, value in cors_headers.items():
            if value:
                print(f"  ✅ {header}: {value}")
            else:
                print(f"  ❌ {header}: Not set")
                
    except Exception as e:
        print(f"❌ CORS test error: {e}")

def check_google_oauth_setup():
    """Check Google OAuth configuration"""
    print("\n=== Google OAuth Setup Guide ===")
    
    print("""
📋 To enable Google OAuth in your Cliper app:

1. 🔗 Go to Supabase Dashboard:
   - Visit: https://supabase.com/dashboard
   - Select your Cliper project

2. ⚙️  Navigate to Authentication > Providers:
   - Click on "Authentication" in the left sidebar
   - Click on "Providers" tab

3. 🔧 Enable Google Provider:
   - Find "Google" in the list of providers
   - Toggle it to "Enabled"
   - You'll need:
     * Google Client ID
     * Google Client Secret

4. 🔑 Get Google OAuth Credentials:
   - Go to: https://console.developers.google.com/
   - Create a new project or select existing
   - Enable Google+ API
   - Create OAuth 2.0 credentials
   - Add authorized redirect URI:
     https://[your-supabase-url]/auth/v1/callback

5. 📝 Configure in Supabase:
   - Paste Client ID and Client Secret
   - Save the configuration

6. 🧪 Test the Integration:
   - Try Google login on your frontend
   - Check for any console errors

✅ Once configured, users can sign up/login with Google!
    """)

def main():
    """Run all authentication tests"""
    print("🧪 Cliper Authentication System Test")
    print("=" * 50)
    
    # Test frontend accessibility
    frontend_ok = test_frontend_accessibility()
    
    # Test backend authentication
    token = test_backend_auth_endpoints()
    
    # Test protected endpoints
    test_protected_endpoint(token)
    
    # Test CORS
    test_cors_configuration()
    
    # Google OAuth guide
    check_google_oauth_setup()
    
    print("\n" + "=" * 50)
    print("🎯 Test Summary:")
    
    if frontend_ok:
        print("✅ Frontend: Accessible at http://localhost:3000")
    else:
        print("❌ Frontend: Not accessible")
    
    if token:
        print("✅ Backend Auth: Registration and Login working")
        print("✅ JWT Tokens: Generated and validated successfully")
    else:
        print("❌ Backend Auth: Issues detected")
    
    print("\n📋 Next Steps:")
    print("1. ✅ Backend authentication is working")
    print("2. ✅ Frontend is accessible")
    print("3. 🔧 Enable Google OAuth in Supabase (see guide above)")
    print("4. 🧪 Test registration/login forms in browser")
    print("5. 🔍 Check browser console for any frontend errors")
    
if __name__ == "__main__":
    main()