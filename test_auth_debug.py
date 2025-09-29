#!/usr/bin/env python3
"""
Debug script to test authentication flow and identify the exact error
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_auth_flow():
    """Test the complete authentication flow to identify issues"""
    print("🔧 DEBUGGING AUTHENTICATION FLOW")
    print("=" * 50)
    
    # Step 1: Test health endpoint
    print("\n1. Testing backend health...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"   Health Status: {response.status_code}")
        print(f"   Health Response: {response.text}")
    except Exception as e:
        print(f"   Health Error: {e}")
        return False
    
    # Step 2: Test auth/me without token (should return 401)
    print("\n2. Testing /api/auth/me without token...")
    try:
        response = requests.get(f"{BASE_URL}/api/auth/me", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Step 3: Try to register a test user
    print("\n3. Testing user registration...")
    test_user = {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
            timeout=10
        )
        print(f"   Registration Status: {response.status_code}")
        print(f"   Registration Response: {response.text[:500]}...")
        
        if response.status_code == 201:
            data = response.json()
            access_token = data.get('tokens', {}).get('access_token')
            
            if access_token:
                print(f"   ✅ Got access token: {access_token[:20]}...")
                
                # Step 4: Test /api/auth/me with valid token
                print("\n4. Testing /api/auth/me with valid token...")
                headers = {"Authorization": f"Bearer {access_token}"}
                
                try:
                    response = requests.get(
                        f"{BASE_URL}/api/auth/me",
                        headers=headers,
                        timeout=10
                    )
                    print(f"   Auth Status: {response.status_code}")
                    print(f"   Auth Response: {response.text}")
                    
                    if response.status_code != 200:
                        print(f"   ❌ Authentication failed with valid token!")
                        return False
                    else:
                        print(f"   ✅ Authentication successful!")
                        return True
                        
                except Exception as e:
                    print(f"   Auth Error: {e}")
                    return False
            else:
                print(f"   ❌ No access token in registration response")
                return False
        else:
            print(f"   ❌ Registration failed")
            return False
            
    except Exception as e:
        print(f"   Registration Error: {e}")
        return False

def test_supabase_connection():
    """Test direct Supabase connection"""
    print("\n🔧 TESTING SUPABASE CONNECTION")
    print("=" * 50)
    
    try:
        # Import the Supabase client
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))
        
        from api.utils.supabase_client import get_supabase_admin_client
        
        client = get_supabase_admin_client()
        if client:
            print("   ✅ Supabase admin client created successfully")
            
            # Test a simple query
            try:
                result = client.table('users').select('count').execute()
                print(f"   ✅ Database query successful")
                return True
            except Exception as query_error:
                print(f"   ❌ Database query failed: {query_error}")
                return False
        else:
            print("   ❌ Failed to create Supabase admin client")
            return False
            
    except Exception as e:
        print(f"   ❌ Supabase connection error: {e}")
        return False

if __name__ == "__main__":
    print("Starting authentication debug...")
    
    # Test Supabase connection first
    supabase_ok = test_supabase_connection()
    
    # Test auth flow
    auth_ok = test_auth_flow()
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Supabase Connection: {'✅ OK' if supabase_ok else '❌ FAILED'}")
    print(f"Authentication Flow: {'✅ OK' if auth_ok else '❌ FAILED'}")
    
    if not auth_ok:
        print("\n🚨 AUTHENTICATION ISSUE DETECTED")
        print("The white screen during upload is likely caused by authentication failures.")
        print("Check the backend logs for more detailed error messages.")
    else:
        print("\n✅ AUTHENTICATION WORKING")
        print("The white screen issue may be caused by other factors.")