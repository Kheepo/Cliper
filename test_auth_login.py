#!/usr/bin/env python3
"""
Test authentication with login instead of registration
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_login_and_auth():
    """Test login and then auth/me endpoint"""
    print("🔧 TESTING LOGIN AND AUTH/ME")
    print("=" * 50)
    
    # Try to login with the test user
    login_data = {
        "email": "test@example.com",
        "password": "TestPassword123!"
    }
    
    print("\n1. Testing login...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=login_data,
            timeout=10
        )
        print(f"   Login Status: {response.status_code}")
        print(f"   Login Response: {response.text[:500]}...")
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get('tokens', {}).get('access_token')
            
            if access_token:
                print(f"   ✅ Got access token: {access_token[:20]}...")
                
                # Test /api/auth/me with valid token
                print("\n2. Testing /api/auth/me with valid token...")
                headers = {"Authorization": f"Bearer {access_token}"}
                
                try:
                    response = requests.get(
                        f"{BASE_URL}/api/auth/me",
                        headers=headers,
                        timeout=10
                    )
                    print(f"   Auth Status: {response.status_code}")
                    print(f"   Auth Response: {response.text}")
                    
                    if response.status_code == 200:
                        print(f"   ✅ Authentication successful!")
                        return True
                    else:
                        print(f"   ❌ Authentication failed with valid token!")
                        
                        # Let's also test the token directly with Supabase
                        print("\n3. Testing token with Supabase directly...")
                        test_token_with_supabase(access_token)
                        return False
                        
                except Exception as e:
                    print(f"   Auth Error: {e}")
                    return False
            else:
                print(f"   ❌ No access token in login response")
                return False
        else:
            print(f"   ❌ Login failed")
            return False
            
    except Exception as e:
        print(f"   Login Error: {e}")
        return False

def test_token_with_supabase(token):
    """Test token directly with Supabase client"""
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))
        
        from api.utils.supabase_client import get_supabase_client_with_auth
        
        print(f"   Testing token: {token[:20]}...")
        
        # Create authenticated client
        client = get_supabase_client_with_auth(token)
        if client:
            print("   ✅ Created authenticated Supabase client")
            
            # Test getting user
            try:
                user_response = client.auth.get_user()
                if user_response and user_response.user:
                    print(f"   ✅ Token valid, user: {user_response.user.email}")
                    
                    # Test database query
                    try:
                        profile_response = client.table('users').select('*').eq('auth_id', user_response.user.id).execute()
                        if profile_response.data:
                            print(f"   ✅ User profile found in database")
                        else:
                            print(f"   ❌ User profile NOT found in database")
                    except Exception as db_error:
                        print(f"   ❌ Database query failed: {db_error}")
                        
                else:
                    print(f"   ❌ Token invalid or expired")
            except Exception as auth_error:
                print(f"   ❌ Auth verification failed: {auth_error}")
        else:
            print("   ❌ Failed to create authenticated client")
            
    except Exception as e:
        print(f"   ❌ Supabase token test error: {e}")

if __name__ == "__main__":
    success = test_login_and_auth()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ AUTHENTICATION WORKING - Issue is elsewhere")
    else:
        print("❌ AUTHENTICATION BROKEN - This is the root cause")