#!/usr/bin/env python3
"""
Debug authentication flow step by step
"""

import jwt
import time
from api.utils.supabase_client import get_supabase_client_with_auth
from api.middleware.auth import SupabaseAuthMiddleware
from fastapi.security import HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=== Testing Authentication Flow ===")
print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
print(f"SUPABASE_ANON_KEY: {os.getenv('SUPABASE_ANON_KEY')[:20]}...")
print(f"SUPABASE_SERVICE_ROLE_KEY: {os.getenv('SUPABASE_SERVICE_ROLE_KEY')[:20]}...")

# Create a test JWT token with future expiration (1 year from now)
test_payload = {
    'sub': 'test-user-id-12345',
    'email': 'test@example.com',
    'exp': int(time.time()) + (365 * 24 * 60 * 60),  # 1 year from now
    'iat': int(time.time()),
    'aud': 'authenticated',
    'user_metadata': {
        'name': 'Test User'
    },
    'app_metadata': {
        'role': 'free'
    }
}

# Create token (using a dummy secret for testing)
test_token = jwt.encode(test_payload, 'test-secret', algorithm='HS256')
print(f"✓ Created fresh test token: {test_token[:50]}...")
print(f"Token expires: {time.ctime(test_payload['exp'])}")

# Test 1: Create Supabase client with auth
try:
    client_with_auth = get_supabase_client_with_auth(test_token)
    print(f"✓ Created Supabase client: {type(client_with_auth)}")
    
    # Test auth.get_user() method
    user_response = client_with_auth.auth.get_user()
    print(f"✓ auth.get_user() works: {user_response}")
except Exception as e:
    print(f"✗ Supabase client creation failed: {e}")

# Test 2: Test middleware verify_token
try:
    middleware = SupabaseAuthMiddleware()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=test_token)
    
    import asyncio
    user_info = asyncio.run(middleware.verify_token(credentials))
    print(f"✓ Middleware verify_token works: {user_info['uid']}")
except Exception as e:
    print(f"✗ Middleware verify_token failed: {e}")

print("\n=== Authentication Flow Test Complete ===")
print(f"\nUse this token for API testing:\n{test_token}")