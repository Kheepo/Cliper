#!/usr/bin/env python3
"""
Test script to verify frontend registration functionality
"""

import requests
import json
import time

def test_frontend_registration():
    """Test user registration through the backend API"""
    
    # Test user credentials - using timestamp to ensure uniqueness
    import time
    timestamp = int(time.time())
    test_user = {
        "email": f"testuser{timestamp}@example.com",
        "password": "TestPassword123!",
        "display_name": "Test User"
    }
    
    print("🧪 Testing Frontend Registration Flow")
    print("=" * 50)
    
    # Test backend health
    try:
        backend_response = requests.get("http://localhost:8000/health", timeout=5)
        if backend_response.status_code == 200:
            print("✅ Backend is running")
        else:
            print(f"❌ Backend health check failed: {backend_response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend is not accessible: {e}")
        return False
    
    # Test frontend health
    try:
        frontend_response = requests.get("http://localhost:3000", timeout=5)
        if frontend_response.status_code == 200:
            print("✅ Frontend is running")
        else:
            print(f"❌ Frontend health check failed: {frontend_response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend is not accessible: {e}")
        return False
    
    # Test user registration via backend API
    try:
        print(f"\n📝 Registering user: {test_user['email']}")
        
        registration_data = {
            "email": test_user["email"],
            "password": test_user["password"],
            "display_name": test_user["display_name"]
        }
        
        response = requests.post(
            "http://localhost:8000/api/auth/register",
            json=registration_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ User registration successful!")
            print(f"   User ID: {result.get('user', {}).get('id', 'N/A')}")
            print(f"   Email: {result.get('user', {}).get('email', 'N/A')}")
            print(f"   Display Name: {result.get('user', {}).get('display_name', 'N/A')}")
            
            # Check if tokens are present
            tokens = result.get('tokens', {})
            if tokens.get('access_token'):
                print("✅ Access token received")
                return True, test_user, tokens['access_token']
            else:
                print("❌ No access token in response")
                return False, None, None
        else:
            print(f"❌ Registration failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False, None, None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Registration request failed: {e}")
        return False, None, None

def test_login_flow(test_user, expected_token=None):
    """Test user login through the backend API"""
    
    print(f"\n🔐 Testing login for: {test_user['email']}")
    
    try:
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        
        response = requests.post(
            "http://localhost:8000/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Login successful!")
            
            # Check if tokens are present
            tokens = result.get('tokens', {})
            access_token = tokens.get('access_token')
            
            if access_token:
                print("✅ Access token received")
                return True, access_token
            else:
                print("❌ No access token in login response")
                return False, None
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Login request failed: {e}")
        return False, None

def test_protected_endpoint(access_token):
    """Test access to protected endpoint with token"""
    
    print(f"\n🔒 Testing protected endpoint access")
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            "http://localhost:8000/api/auth/me",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Protected endpoint access successful!")
            print(f"   User: {result.get('email', 'N/A')}")
            return True
        else:
            print(f"❌ Protected endpoint access failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Protected endpoint request failed: {e}")
        return False

if __name__ == "__main__":
    # Test registration
    reg_success, test_user, access_token = test_frontend_registration()
    
    if reg_success and test_user:
        # Test login
        login_success, login_token = test_login_flow(test_user)
        
        if login_success and login_token:
            # Test protected endpoint
            protected_success = test_protected_endpoint(login_token)
            
            if protected_success:
                print("\n🎉 All authentication tests passed!")
                print("\n📋 Test Summary:")
                print("   ✅ Backend is running")
                print("   ✅ Frontend is running")
                print("   ✅ User registration works")
                print("   ✅ User login works")
                print("   ✅ Protected endpoint access works")
                print("\n🔑 Test User Credentials:")
                print(f"   Email: {test_user['email']}")
                print(f"   Password: {test_user['password']}")
                print(f"   Display Name: {test_user['display_name']}")
            else:
                print("\n❌ Protected endpoint test failed")
        else:
            print("\n❌ Login test failed")
    else:
        print("\n❌ Registration test failed")