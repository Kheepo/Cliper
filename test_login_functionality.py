#!/usr/bin/env python3
"""
Comprehensive test for login functionality
"""

import requests
import json
from datetime import datetime

def test_login_functionality():
    print("🔐 Login Functionality Test")
    print("=" * 50)
    
    base_url = "http://localhost:8001"
    
    # Test data
    test_email = "newuser1758481516@testdomain.com"  # From previous successful registration
    test_password = "NewPassword123!"
    
    print(f"Testing login for: {test_email}")
    print(f"Time: {datetime.now()}")
    print("=" * 50)
    
    # Step 1: Test server connectivity
    print("\n🔸 Step 1: Testing server connectivity...")
    try:
        health_response = requests.get(f"{base_url}/health")
        print(f"   Health check status: {health_response.status_code}")
        if health_response.status_code == 200:
            print("   ✅ Server is responding")
        else:
            print("   ❌ Server health check failed")
            return
    except Exception as e:
        print(f"   ❌ Server connectivity failed: {e}")
        return
    
    # Step 2: Test login
    print("\n🔸 Step 2: Testing login...")
    login_url = f"{base_url}/api/auth/login"
    login_data = {
        "email": test_email,
        "password": test_password
    }
    
    print(f"   URL: {login_url}")
    print(f"   Data: {json.dumps(login_data, indent=2)}")
    
    try:
        login_response = requests.post(
            login_url,
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n📊 Response Details:")
        print(f"   Status Code: {login_response.status_code}")
        print(f"   Headers: {dict(login_response.headers)}")
        
        if login_response.status_code == 200:
            response_data = login_response.json()
            print("   ✅ Login successful!")
            print(f"   User ID: {response_data['user']['id']}")
            print(f"   Display Name: {response_data['user']['display_name']}")
            print(f"   Email: {response_data['user']['email']}")
            print(f"   Email Verified: {response_data['user']['email_verified']}")
            print(f"   Is Active: {response_data['user']['is_active']}")
            print(f"   Access Token: {response_data['tokens']['access_token'][:50]}...")
            print(f"   Token Type: {response_data['tokens']['token_type']}")
            print(f"   Expires In: {response_data['tokens']['expires_in']} seconds")
            
            # Step 3: Test token verification
            print("\n🔸 Step 3: Testing token verification...")
            access_token = response_data['tokens']['access_token']
            
            verify_response = requests.post(
                f"{base_url}/api/auth/verify",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if verify_response.status_code == 200:
                verify_data = verify_response.json()
                print("   ✅ Token verification successful!")
                print(f"   Verified User ID: {verify_data['user']['id']}")
                print(f"   Verified Email: {verify_data['user']['email']}")
            else:
                print(f"   ❌ Token verification failed: {verify_response.status_code}")
                print(f"   Error: {verify_response.text}")
            
        else:
            print(f"   ❌ Login failed with status {login_response.status_code}")
            print(f"   Response Body: {json.dumps(login_response.json(), indent=2)}")
            
    except Exception as e:
        print(f"   ❌ Login request failed: {e}")
    
    # Step 4: Test invalid credentials
    print("\n🔸 Step 4: Testing invalid credentials...")
    invalid_login_data = {
        "email": test_email,
        "password": "WrongPassword123!"
    }
    
    try:
        invalid_response = requests.post(
            login_url,
            json=invalid_login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if invalid_response.status_code == 401:
            print("   ✅ Invalid credentials properly rejected")
        else:
            print(f"   ⚠️  Unexpected response for invalid credentials: {invalid_response.status_code}")
            print(f"   Response: {invalid_response.text}")
            
    except Exception as e:
        print(f"   ❌ Invalid credentials test failed: {e}")
    
    # Step 5: Test non-existent user
    print("\n🔸 Step 5: Testing non-existent user...")
    nonexistent_login_data = {
        "email": "nonexistent@example.com",
        "password": "SomePassword123!"
    }
    
    try:
        nonexistent_response = requests.post(
            login_url,
            json=nonexistent_login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if nonexistent_response.status_code == 401:
            print("   ✅ Non-existent user properly rejected")
        else:
            print(f"   ⚠️  Unexpected response for non-existent user: {nonexistent_response.status_code}")
            print(f"   Response: {nonexistent_response.text}")
            
    except Exception as e:
        print(f"   ❌ Non-existent user test failed: {e}")
    
    print("\n🎉 LOGIN FUNCTIONALITY TEST COMPLETED!")
    print("\n📝 Test completed!")

if __name__ == "__main__":
    test_login_functionality()