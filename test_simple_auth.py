import requests
import json

def test_health():
    """Test the server health endpoint"""
    try:
        print("\n=== Testing Server Health ===")
        url = "http://localhost:8000/api/health"
        print(f"Testing: {url}")
        
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Health check passed!")
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Health check timed out")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_registration():
    """Test user registration"""
    try:
        print("\n=== Testing User Registration ===")
        url = "http://localhost:8000/api/auth/register"
        
        registration_data = {
            "email": "testuser@example.com",
            "password": "TestPassword123!",
            "display_name": "Test User",
            "photo_url": ""
        }
        
        print(f"Registering user: {registration_data['email']}")
        response = requests.post(url, json=registration_data, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Registration successful!")
            return True, response.json()
        else:
            print(f"❌ Registration failed")
            return False, None
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False, None

def test_login():
    """Test user login"""
    try:
        print("\n=== Testing User Login ===")
        url = "http://localhost:8000/api/auth/login"
        
        login_data = {
            "email": "testuser@example.com",
            "password": "TestPassword123!"
        }
        
        print(f"Logging in user: {login_data['email']}")
        response = requests.post(url, json=login_data, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Login successful!")
            return True, response.json()
        else:
            print(f"❌ Login failed")
            return False, None
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False, None

if __name__ == "__main__":
    print("Starting authentication tests...")
    
    # Test health first
    health_ok = test_health()
    
    if not health_ok:
        print("\n❌ Server health check failed. Cannot proceed with auth tests.")
        exit(1)
    
    # Test registration
    reg_success, reg_data = test_registration()
    
    # Test login
    login_success, login_data = test_login()
    
    # Summary
    print("\n=== Test Summary ===")
    print(f"Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"Registration: {'✅ PASS' if reg_success else '❌ FAIL'}")
    print(f"Login: {'✅ PASS' if login_success else '❌ FAIL'}")
    
    if health_ok and reg_success and login_success:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed. Check the logs above.")