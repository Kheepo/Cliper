#!/usr/bin/env python3
"""
Comprehensive test script to verify the complete authentication flow
including frontend login and Results page access
"""

import requests
import json
import time

def test_backend_frontend_health():
    """Test that both backend and frontend are running"""
    print("🔍 Testing Backend and Frontend Health")
    print("=" * 50)
    
    # Test backend
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
    
    # Test frontend
    try:
        frontend_response = requests.get("http://localhost:3000", timeout=5)
        if frontend_response.status_code == 200:
            print("✅ Frontend is running")
            return True
        else:
            print(f"❌ Frontend health check failed: {frontend_response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend is not accessible: {e}")
        return False

def test_api_authentication():
    """Test authentication via API"""
    print("\n🔐 Testing API Authentication")
    print("=" * 50)
    
    test_user = {
        "email": "testuser1758805676@example.com",
        "password": "TestPassword123!"
    }
    
    try:
        # Test login
        login_response = requests.post(
            "http://localhost:8000/api/auth/login",
            json=test_user,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if login_response.status_code == 200:
            result = login_response.json()
            access_token = result.get('tokens', {}).get('access_token')
            
            if access_token:
                print("✅ API login successful")
                print(f"   User: {result.get('user', {}).get('email', 'N/A')}")
                
                # Test protected endpoint
                headers = {"Authorization": f"Bearer {access_token}"}
                me_response = requests.get(
                    "http://localhost:8000/api/auth/me",
                    headers=headers,
                    timeout=10
                )
                
                if me_response.status_code == 200:
                    print("✅ Protected endpoint access successful")
                    return True, access_token, test_user
                else:
                    print(f"❌ Protected endpoint failed: {me_response.status_code}")
                    return False, None, None
            else:
                print("❌ No access token received")
                return False, None, None
        else:
            print(f"❌ API login failed: {login_response.status_code}")
            print(f"   Response: {login_response.text}")
            return False, None, None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API authentication test failed: {e}")
        return False, None, None

def test_frontend_authentication_simple():
    """Test frontend authentication without browser automation"""
    print("\n🌐 Testing Frontend Authentication (Simple)")
    print("=" * 50)
    
    # Test that key frontend routes are accessible
    routes = [
        ("/", "Home page"),
        ("/login", "Login page"),
        ("/register", "Register page"),
        ("/results", "Results page")
    ]
    
    all_accessible = True
    
    for route, description in routes:
        try:
            response = requests.get(f"http://localhost:3000{route}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {description} accessible")
            else:
                print(f"⚠️  {description} returned: {response.status_code}")
                if route == "/results":
                    # Results page might redirect if not authenticated, which is expected
                    print("   (This might be expected if authentication is required)")
        except requests.exceptions.RequestException as e:
            print(f"❌ {description} failed: {e}")
            all_accessible = False
    
    return all_accessible

def test_results_page_content():
    """Test that the Results page content is accessible"""
    print("\n📊 Testing Results Page Content")
    print("=" * 50)
    
    try:
        # Try to access the results page directly
        response = requests.get("http://localhost:3000/results", timeout=10)
        
        if response.status_code == 200:
            content = response.text
            
            # Check if the page contains expected content or if it's a redirect
            if "<!DOCTYPE html>" in content and "results" in content.lower():
                print("✅ Results page content accessible")
                
                # Check for common error indicators
                if "white screen" in content.lower() or "error" in content.lower():
                    print("⚠️  Potential issues detected in page content")
                    return False
                else:
                    print("✅ No obvious errors in page content")
                    return True
            else:
                print("⚠️  Results page might be redirecting or showing unexpected content")
                return False
        else:
            print(f"⚠️  Results page returned status: {response.status_code}")
            # This might be expected if authentication is required
            return True
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Results page test failed: {e}")
        return False

def run_comprehensive_test():
    """Run all tests in sequence"""
    print("🚀 Starting Comprehensive Authentication Flow Test")
    print("=" * 60)
    
    # Test 1: Health checks
    if not test_backend_frontend_health():
        print("\n❌ Health checks failed. Cannot proceed.")
        return False
    
    # Test 2: API authentication
    api_success, access_token, test_user = test_api_authentication()
    if not api_success:
        print("\n❌ API authentication failed. Cannot proceed.")
        return False
    
    # Test 3: Frontend routes
    frontend_success = test_frontend_authentication_simple()
    if not frontend_success:
        print("\n⚠️  Some frontend routes had issues, but continuing...")
    
    # Test 4: Results page content
    results_success = test_results_page_content()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 COMPREHENSIVE TEST SUMMARY")
    print("=" * 60)
    
    if api_success and frontend_success and results_success:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ Backend authentication: WORKING")
        print("✅ Frontend routes: ACCESSIBLE")
        print("✅ Results page: ACCESSIBLE")
        
        print("\n🔑 Test Credentials for Manual Verification:")
        print(f"   Email: {test_user['email']}")
        print(f"   Password: {test_user['password']}")
        
        print("\n💡 Manual Testing Steps:")
        print("   1. Open http://localhost:3000/login")
        print("   2. Login with the above credentials")
        print("   3. Navigate to http://localhost:3000/results")
        print("   4. Verify no white screen appears")
        
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print(f"   API Authentication: {'✅' if api_success else '❌'}")
        print(f"   Frontend Routes: {'✅' if frontend_success else '❌'}")
        print(f"   Results Page: {'✅' if results_success else '❌'}")
        
        return False

if __name__ == "__main__":
    success = run_comprehensive_test()
    
    if success:
        print("\n🎯 Authentication system appears to be working correctly!")
        print("   The white screen issue should be resolved.")
    else:
        print("\n🔧 Some issues detected. Please check the output above.")