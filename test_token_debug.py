#!/usr/bin/env python3
"""
Debug Token Verification Test
Tests the authentication middleware directly to identify token verification issues.
"""

import requests
import json
from datetime import datetime

def test_token_debug():
    print("🔍 Token Verification Debug Test")
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
            
            # Step 2: Test the /me endpoint (simpler than verify)
            print("\n🔸 Step 2: Testing /me endpoint...")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            me_response = requests.get(f"{base_url}/api/auth/me", headers=headers)
            print(f"   /me status: {me_response.status_code}")
            
            if me_response.status_code == 200:
                print("   ✅ /me endpoint works!")
                me_data = me_response.json()
                print(f"   User: {me_data.get('display_name')} ({me_data.get('email')})")
            else:
                print(f"   ❌ /me failed: {me_response.text}")
            
            # Step 3: Test verify endpoint
            print("\n🔸 Step 3: Testing verify endpoint...")
            verify_response = requests.post(f"{base_url}/api/auth/verify", headers=headers)
            print(f"   Verify status: {verify_response.status_code}")
            
            if verify_response.status_code == 200:
                print("   ✅ Verify endpoint works!")
                verify_data = verify_response.json()
                print(f"   Message: {verify_data.get('message')}")
            else:
                print(f"   ❌ Verify failed: {verify_response.text}")
                
        else:
            print(f"   ❌ Login failed: {login_response.text}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n🎉 TOKEN DEBUG TEST COMPLETED!")
    print("\n📝 Test completed!")

if __name__ == "__main__":
    test_token_debug()