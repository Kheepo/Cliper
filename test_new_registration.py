import requests
import json
import time
import random
import string

def generate_test_email():
    """Generate a unique test email"""
    timestamp = str(int(time.time()))
    random_suffix = ''.join(random.choices(string.ascii_lowercase, k=5))
    return f"test_{timestamp}_{random_suffix}@example.com"

def test_new_user_registration():
    """Test registration with a completely new user"""
    try:
        print("\n=== Testing New User Registration ===")
        
        # Generate unique email
        test_email = generate_test_email()
        print(f"Generated test email: {test_email}")
        
        url = "http://localhost:8000/api/auth/register"
        registration_data = {
            "email": test_email,
            "password": "TestPassword123!",
            "display_name": "New Test User",
            "photo_url": ""
        }
        
        print(f"Registering new user: {registration_data['email']}")
        response = requests.post(url, json=registration_data, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Registration successful!")
            result = response.json()
            return True, test_email, result
        else:
            print(f"❌ Registration failed")
            try:
                error_detail = response.json()
                print(f"Error details: {error_detail}")
            except:
                pass
            return False, test_email, None
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False, None, None

def test_login_new_user(email, password="TestPassword123!"):
    """Test login with the newly registered user"""
    try:
        print(f"\n=== Testing Login for New User: {email} ===")
        url = "http://localhost:8000/api/auth/login"
        
        login_data = {
            "email": email,
            "password": password
        }
        
        print(f"Logging in user: {login_data['email']}")
        response = requests.post(url, json=login_data, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Login successful!")
            result = response.json()
            return True, result
        else:
            print(f"❌ Login failed")
            try:
                error_detail = response.json()
                print(f"Error details: {error_detail}")
            except:
                pass
            return False, None
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False, None

def test_user_profile_access(access_token):
    """Test accessing user profile with the token"""
    try:
        print("\n=== Testing User Profile Access ===")
        url = "http://localhost:8000/api/auth/me"
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        print("Accessing user profile...")
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Profile access successful!")
            return True, response.json()
        else:
            print(f"❌ Profile access failed")
            return False, None
            
    except Exception as e:
        print(f"❌ Profile access error: {e}")
        return False, None

if __name__ == "__main__":
    print("Starting comprehensive registration and authentication test...")
    
    # Test new user registration
    reg_success, test_email, reg_data = test_new_user_registration()
    
    if not reg_success:
        print("\n❌ Registration failed. Cannot proceed with login test.")
        exit(1)
    
    # Test login with new user
    login_success, login_data = test_login_new_user(test_email)
    
    access_token = None
    if login_success and login_data:
        access_token = login_data.get('session', {}).get('access_token')
    
    # Test profile access if we have a token
    profile_success = False
    if access_token:
        profile_success, profile_data = test_user_profile_access(access_token)
    
    # Summary
    print("\n=== Comprehensive Test Summary ===")
    print(f"New User Registration: {'✅ PASS' if reg_success else '❌ FAIL'}")
    print(f"New User Login: {'✅ PASS' if login_success else '❌ FAIL'}")
    print(f"Profile Access: {'✅ PASS' if profile_success else '❌ FAIL'}")
    
    if reg_success and login_success and profile_success:
        print("\n🎉 All authentication tests passed!")
        print(f"Test user email: {test_email}")
        if access_token:
            print(f"Access token (first 50 chars): {access_token[:50]}...")
    else:
        print("\n⚠️ Some authentication tests failed. Check the logs above.")
        exit(1)