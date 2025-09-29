#!/usr/bin/env python3
"""
Test the extracted token directly
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Token from the registration response
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6InZMNGovQS9jZXNQdkRrZDgiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3N0emR5d2hiZG92am9qdHF4bXNkLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiIxMWJjOThjNi1jZjNkLTRjN2ItOTM5YS1mZmY0YjlmYzgwOGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU4NzU2NzQ2LCJpYXQiOjE3NTg3NTMxNDYsImVtYWlsIjoidGVzdHVzZXJfY2EzMDI1MzBAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc1ODc1MzE0Nn1dLCJzZXNzaW9uX2lkIjoiODNkNWI5ZTQtMmY2Yi00N2NhLTgyNGEtZTg1MTU2NmNiMTM5IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Zrzu8iKkIVikDBERpKBvsUDWbQCbD1SZ62bOd0gIOTw"

def test_with_valid_token():
    """Test endpoints with the valid token"""
    print("🔧 TESTING WITH VALID TOKEN")
    print("=" * 50)
    
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    
    print(f"\n1. Testing /api/auth/me with valid token...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=headers,
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 200:
            print(f"   ✅ Auth/Me working!")
        else:
            print(f"   ❌ Auth/Me failed with valid token")
            
            # Let's test the token with Supabase directly
            print(f"\n2. Testing token with Supabase directly...")
            test_supabase_direct()
            
    except Exception as e:
        print(f"   Error: {e}")
    
    print(f"\n3. Testing upload endpoint...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/upload",
            headers=headers,
            timeout=10
        )
        print(f"   Upload Status: {response.status_code}")
        print(f"   Upload Response: {response.text[:200]}")
        
    except Exception as e:
        print(f"   Upload Error: {e}")
    
    print(f"\n4. Testing file upload endpoint...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/upload",
            headers=headers,
            timeout=10
        )
        print(f"   File Upload Status: {response.status_code}")
        print(f"   File Upload Response: {response.text[:200]}")
        
    except Exception as e:
        print(f"   File Upload Error: {e}")

def test_supabase_direct():
    """Test token with Supabase client directly"""
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))
        
        from api.utils.supabase_client import get_supabase_client_with_auth
        
        print(f"   Creating Supabase client with token...")
        client = get_supabase_client_with_auth(ACCESS_TOKEN)
        
        if client:
            print(f"   ✅ Supabase client created")
            
            # Test auth.get_user()
            try:
                user_response = client.auth.get_user()
                if user_response and user_response.user:
                    print(f"   ✅ Token valid, user: {user_response.user.email}")
                    print(f"   ✅ User ID: {user_response.user.id}")
                    
                    # Test database query
                    try:
                        profile_response = client.table('users').select('*').eq('auth_id', user_response.user.id).execute()
                        if profile_response.data:
                            print(f"   ✅ User profile found: {len(profile_response.data)} records")
                        else:
                            print(f"   ⚠️  User profile not found in database")
                    except Exception as db_error:
                        print(f"   ❌ Database query failed: {db_error}")
                        
                else:
                    print(f"   ❌ Token invalid or no user returned")
                    
            except Exception as auth_error:
                print(f"   ❌ Auth verification failed: {auth_error}")
        else:
            print(f"   ❌ Failed to create Supabase client")
            
    except Exception as e:
        print(f"   Supabase test error: {e}")
        import traceback
        traceback.print_exc()

def decode_jwt_payload():
    """Decode JWT payload to see what's inside"""
    try:
        import base64
        import json
        
        # Split JWT and decode payload
        parts = ACCESS_TOKEN.split('.')
        if len(parts) >= 2:
            # Add padding if needed
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            
            decoded = base64.b64decode(payload)
            payload_data = json.loads(decoded)
            
            print(f"\n🔍 JWT PAYLOAD:")
            print(json.dumps(payload_data, indent=2))
            
            return payload_data
    except Exception as e:
        print(f"   JWT decode error: {e}")
        return None

if __name__ == "__main__":
    decode_jwt_payload()
    test_with_valid_token()