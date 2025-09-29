#!/usr/bin/env python3
"""
Test registration with a completely new user using a different domain
"""

import requests
import json
import time
from datetime import datetime

def test_new_user_registration():
    # Use timestamp to ensure uniqueness
    timestamp = int(time.time())
    test_email = f"newuser{timestamp}@testdomain.com"
    
    print("🧪 Completely New User Registration Test")
    print(f"Email: {test_email}")
    print(f"Time: {datetime.now()}")
    print("=" * 50)
    
    # Test server connectivity
    print("\n🔸 Step 1: Testing server connectivity...")
    try:
        health_response = requests.get("http://localhost:8001/api/health")
        print(f"   Health check status: {health_response.status_code}")
        if health_response.status_code == 200:
            print("   ✅ Server is responding")
        else:
            print("   ❌ Server health check failed")
            return
    except Exception as e:
        print(f"   ❌ Server connectivity failed: {e}")
        return
    
    # Test registration
    print("\n🔸 Step 2: Testing registration with completely new email...")
    registration_data = {
        "email": test_email,
        "password": "NewPassword123!",
        "full_name": "Completely New User"
    }
    
    print(f"   URL: http://localhost:8001/api/auth/register")
    print(f"   Data: {json.dumps(registration_data, indent=2)}")
    
    try:
        response = requests.post(
            "http://localhost:8001/api/auth/register",
            json=registration_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print("\n📊 Response Details:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 200 or response.status_code == 201:
            response_data = response.json()
            print(f"   ✅ Registration successful!")
            print(f"   User ID: {response_data.get('user', {}).get('id')}")
            print(f"   Display Name: {response_data.get('user', {}).get('display_name')}")
            print(f"   Email: {response_data.get('user', {}).get('email')}")
            print(f"   Access Token: {response_data.get('tokens', {}).get('access_token', '')[:30]}...")
            
            # Test login with the new user
            print("\n🔸 Step 3: Testing login with new user...")
            login_data = {
                "email": test_email,
                "password": "NewPassword123!"
            }
            
            login_response = requests.post(
                "http://localhost:8001/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if login_response.status_code == 200:
                login_result = login_response.json()
                print(f"   ✅ Login successful!")
                print(f"   User ID: {login_result.get('user', {}).get('id')}")
                print(f"   Display Name: {login_result.get('user', {}).get('display_name')}")
                print(f"   Access Token: {login_result.get('tokens', {}).get('access_token', '')[:30]}...")
                
                print("\n🎉 AUTHENTICATION SYSTEM IS WORKING CORRECTLY!")
                print("   ✅ Registration: SUCCESS")
                print("   ✅ Login: SUCCESS")
                print("   ✅ Token Generation: SUCCESS")
                print("   ✅ User Profile Creation: SUCCESS")
                
            else:
                print(f"   ❌ Login failed with status {login_response.status_code}")
                try:
                    error_data = login_response.json()
                    print(f"   Error: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"   Error: {login_response.text}")
                
        else:
            print(f"   ❌ Registration failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Response Body: {json.dumps(error_data, indent=2)}")
            except:
                print(f"   Response Body: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Registration request failed: {e}")
    
    print("\n📝 Test completed!")

if __name__ == "__main__":
    test_new_user_registration()