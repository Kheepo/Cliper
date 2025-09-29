#!/usr/bin/env python3
"""
Create a test user and test authentication flow
"""

import requests
import json
import uuid
import time

BASE_URL = "http://localhost:8000"

def create_and_test_user():
    """Create a new test user and test authentication"""
    print("🔧 CREATING TEST USER AND TESTING AUTH")
    print("=" * 50)
    
    # Generate unique email
    unique_id = str(uuid.uuid4())[:8]
    test_email = f"testuser_{unique_id}@example.com"
    test_password = "TestPassword123!"
    
    print(f"\n1. Creating user: {test_email}")
    
    # Register new user
    register_data = {
        "email": test_email,
        "password": test_password,
        "full_name": "Test User"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=register_data,
            timeout=10
        )
        print(f"   Registration Status: {response.status_code}")
        print(f"   Registration Response: {response.text[:500]}")
        
        if response.status_code == 201:
            print(f"   ✅ User created successfully")
            
            # Wait a moment for user to be fully created
            time.sleep(2)
            
            # Now try to login
            print(f"\n2. Testing login with new user...")
            login_data = {
                "email": test_email,
                "password": test_password
            }
            
            try:
                login_response = requests.post(
                    f"{BASE_URL}/api/auth/login",
                    json=login_data,
                    timeout=10
                )
                print(f"   Login Status: {login_response.status_code}")
                print(f"   Login Response: {login_response.text[:500]}")
                
                if login_response.status_code == 200:
                    data = login_response.json()
                    access_token = data.get('tokens', {}).get('access_token')
                    
                    if access_token:
                        print(f"   ✅ Login successful, got token: {access_token[:20]}...")
                        
                        # Test /api/auth/me with valid token
                        print(f"\n3. Testing /api/auth/me with valid token...")
                        headers = {"Authorization": f"Bearer {access_token}"}
                        
                        try:
                            me_response = requests.get(
                                f"{BASE_URL}/api/auth/me",
                                headers=headers,
                                timeout=10
                            )
                            print(f"   Auth/Me Status: {me_response.status_code}")
                            print(f"   Auth/Me Response: {me_response.text}")
                            
                            if me_response.status_code == 200:
                                print(f"   ✅ Authentication flow working!")
                                
                                # Test upload endpoint with auth
                                print(f"\n4. Testing upload endpoint with auth...")
                                test_upload_with_auth(access_token)
                                return True
                            else:
                                print(f"   ❌ Auth/Me failed even with valid token!")
                                analyze_auth_failure(access_token)
                                return False
                                
                        except Exception as e:
                            print(f"   Auth/Me Error: {e}")
                            return False
                    else:
                        print(f"   ❌ No access token in login response")
                        return False
                else:
                    print(f"   ❌ Login failed: {login_response.text}")
                    return False
                    
            except Exception as e:
                print(f"   Login Error: {e}")
                return False
        else:
            print(f"   ❌ Registration failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   Registration Error: {e}")
        return False

def test_upload_with_auth(token):
    """Test upload endpoint with authentication"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test upload endpoint (without file for now)
        response = requests.get(
            f"{BASE_URL}/api/upload",
            headers=headers,
            timeout=10
        )
        print(f"   Upload endpoint status: {response.status_code}")
        print(f"   Upload endpoint response: {response.text[:200]}")
        
        if response.status_code in [200, 405]:  # 405 = Method not allowed (GET on POST endpoint)
            print(f"   ✅ Upload endpoint accessible with auth")
        else:
            print(f"   ❌ Upload endpoint not accessible: {response.status_code}")
            
    except Exception as e:
        print(f"   Upload test error: {e}")

def analyze_auth_failure(token):
    """Analyze why authentication is failing"""
    print(f"\n🔍 ANALYZING AUTH FAILURE")
    print(f"   Token: {token[:50]}...")
    
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))
        
        from api.utils.supabase_client import get_supabase_client_with_auth
        
        # Test token with Supabase directly
        print(f"   Testing token with Supabase...")
        client = get_supabase_client_with_auth(token)
        
        if client:
            print(f"   ✅ Supabase client created")
            
            # Test auth.get_user()
            try:
                user_response = client.auth.get_user()
                if user_response and user_response.user:
                    print(f"   ✅ Token valid, user ID: {user_response.user.id}")
                    print(f"   ✅ User email: {user_response.user.email}")
                else:
                    print(f"   ❌ Token invalid or no user")
            except Exception as auth_error:
                print(f"   ❌ Auth error: {auth_error}")
        else:
            print(f"   ❌ Failed to create Supabase client")
            
    except Exception as e:
        print(f"   Analysis error: {e}")

if __name__ == "__main__":
    success = create_and_test_user()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ AUTHENTICATION WORKING - Upload issue is elsewhere")
    else:
        print("❌ AUTHENTICATION BROKEN - Root cause identified")
        print("\n🔧 NEXT STEPS:")
        print("1. Check backend logs for detailed error messages")
        print("2. Verify Supabase Auth configuration")
        print("3. Check middleware configuration in main.py")