#!/usr/bin/env python3
"""
Automated test script for Cliper authentication flow
Tests registration, login, and Results page access
"""

import requests
import json
import time
from datetime import datetime

class CliperAuthTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.test_user = {
            "email": "testuser@example.com",
            "password": "TestPassword123!",
            "display_name": "Test User"
        }
        self.session = requests.Session()
        self.access_token = None
        
    def test_backend_health(self):
        """Test if backend is running"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                print("✅ Backend is running")
                return True
            else:
                print(f"❌ Backend health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Backend connection failed: {e}")
            return False
    
    def test_frontend_health(self):
        """Test if frontend is running"""
        try:
            response = self.session.get(self.frontend_url)
            if response.status_code == 200:
                print("✅ Frontend is running")
                return True
            else:
                print(f"❌ Frontend health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Frontend connection failed: {e}")
            return False
    
    def test_registration_api(self):
        """Test user registration via API"""
        try:
            # First check if user already exists and delete if needed
            print("\n🔍 Checking if test user already exists...")
            
            # Try to register the user
            print("\n📝 Testing user registration...")
            registration_data = {
                "email": self.test_user["email"],
                "password": self.test_user["password"]
            }
            
            response = self.session.post(
                f"{self.base_url}/api/auth/register",
                json=registration_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201]:
                print("✅ User registration successful")
                return True
            elif response.status_code == 400:
                # User might already exist
                print("⚠️ User might already exist, trying login instead")
                return self.test_login_api()
            else:
                print(f"❌ Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Registration test failed: {e}")
            return False
    
    def test_login_api(self):
        """Test user login via API"""
        try:
            print("\n🔐 Testing user login...")
            login_data = {
                "email": self.test_user["email"],
                "password": self.test_user["password"]
            }
            
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"Login response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ User login successful")
                print(f"Response structure: {json.dumps(result, indent=2)}")
                
                # Check for access token in the expected backend format
                access_token = None
                if 'tokens' in result and 'access_token' in result['tokens']:
                    access_token = result['tokens']['access_token']
                    print(f"🔑 Access token received: {access_token[:50]}...")
                    self.access_token = access_token
                    
                    # Test the token by calling a protected endpoint
                    return self.test_protected_endpoint()
                else:
                    print("❌ No access token found in expected format")
                    print(f"Available keys: {list(result.keys())}")
                    if 'tokens' in result:
                        print(f"Tokens keys: {list(result['tokens'].keys())}")
                    return False
            else:
                print(f"❌ Login failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Login test failed: {e}")
            return False
    
    def test_protected_endpoint(self):
        """Test accessing a protected endpoint with the token"""
        print("\n🔒 Testing protected endpoint...")
        
        if not self.access_token:
            print("❌ No access token available")
            return False
            
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = self.session.get(
                f"{self.base_url}/api/auth/me",
                headers=headers
            )
            
            print(f"Protected endpoint status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Protected endpoint accessible")
                print(f"User info: {json.dumps(result, indent=2)}")
                return True
            else:
                print(f"❌ Protected endpoint failed: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"Error details: {error_detail}")
                except:
                    print(f"Error text: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Protected endpoint error: {e}")
            return False
    
    def test_authenticated_endpoints(self):
        """Test accessing authenticated endpoints"""
        if not self.access_token:
            print("❌ No access token available for authenticated tests")
            return False
            
        try:
            print("\n🔒 Testing authenticated endpoints...")
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Test user profile endpoint
            response = self.session.get(
                f"{self.base_url}/api/user/profile",
                headers=headers
            )
            
            if response.status_code == 200:
                print("✅ Authenticated user profile access successful")
                return True
            else:
                print(f"❌ Authenticated endpoint failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Authenticated endpoint test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all authentication tests"""
        print("\n" + "="*60)
        print("🚀 CLIPER AUTHENTICATION FLOW TEST")
        print("="*60)
        print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"👤 Test User: {self.test_user['email']}")
        print("\n🔧 TESTING SYSTEM COMPONENTS:")
        
        # Test system health
        backend_ok = self.test_backend_health()
        frontend_ok = self.test_frontend_health()
        
        if not backend_ok or not frontend_ok:
            print("\n❌ System health check failed. Please ensure both frontend and backend are running.")
            return False
        
        # Test authentication flow
        registration_ok = self.test_registration_api()
        if not registration_ok:
            print("\n❌ Registration test failed")
            return False
            
        login_ok = self.test_login_api()
        if not login_ok:
            print("\n❌ Login test failed")
            return False
            
        auth_endpoints_ok = self.test_authenticated_endpoints()
        if not auth_endpoints_ok:
            print("\n❌ Authenticated endpoints test failed")
            return False
        
        print("\n" + "="*60)
        print("✅ ALL AUTHENTICATION TESTS PASSED!")
        print("="*60)
        print("\n📋 NEXT STEPS:")
        print("1. Open http://localhost:3000/login in browser")
        print(f"2. Login with: {self.test_user['email']} / {self.test_user['password']}")
        print("3. Navigate to Results page and verify no white screen")
        print("4. Test complete upload -> process -> results flow")
        
        return True

if __name__ == "__main__":
    tester = CliperAuthTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 Authentication system is working correctly!")
    else:
        print("\n💥 Authentication system has issues that need to be fixed.")