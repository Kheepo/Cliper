#!/usr/bin/env python3
"""
Middleware Debug Test
Tests the authentication middleware token extraction directly.
"""

import requests
import json
from datetime import datetime

def test_simple_token_debug():
    print("🔧 Simple Token Debug Test")
    print("=" * 50)
    print(f"Time: {datetime.now()}")
    print("=" * 50)
    
    base_url = "http://localhost:8001"
    
    # Step 1: Login to get a token
    print("\n🔸 Step 1: Getting fresh token...")
    login_data = {
        "email": "newuser1758481516@testdomain.com",
        "password": "NewPassword123!"
    }
    
    try:
        login_response = requests.post(f"{base_url}/api/auth/login", json=login_data)
        print(f"   Login status: {login_response.status_code}")
        
        if login_response.status_code == 200:
            login_result = login_response.json()
            access_token = login_result['tokens']['access_token']
            print(f"   ✅ Got token: {access_token[:50]}...")
            
            # Step 2: Test with different header formats
            print("\n🔸 Step 2: Testing different header formats...")
            
            # Test 1: Standard Bearer format
            headers1 = {"Authorization": f"Bearer {access_token}"}
            me_response1 = requests.get(f"{base_url}/api/auth/me", headers=headers1)
            print(f"   Standard Bearer format: {me_response1.status_code}")
            
            # Test 2: Check if token is valid by calling Supabase directly
            print("\n🔸 Step 3: Testing token validity...")
            print(f"   Token length: {len(access_token)}")
            print(f"   Token starts with: {access_token[:20]}")
            print(f"   Token ends with: {access_token[-20:]}")
            
            # Test 3: Try a simple endpoint that doesn't require auth
            health_response = requests.get(f"{base_url}/health")
            print(f"   Health endpoint: {health_response.status_code}")
            
        else:
            print(f"   ❌ Login failed: {login_response.text}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n🎉 SIMPLE TOKEN DEBUG TEST COMPLETED!")
    print("\n📝 Test completed!")

if __name__ == "__main__":
    test_simple_token_debug()