import requests
import json

def test_user_registration():
    print("Testing user registration...")
    
    # Test registration
    registration_data = {
        'email': 'test@example.com',
        'password': 'password123',
        'display_name': 'Test User'
    }
    
    try:
        register_response = requests.post('http://localhost:8000/api/auth/register', 
                                        json=registration_data, timeout=10)
        
        print(f"Registration response: {register_response.status_code}")
        print(f"Registration response body: {register_response.text}")
        
        if register_response.status_code == 200:
            print("\n✅ Registration successful!")
            return True
        else:
            print("\n❌ Registration failed")
            return False
    except Exception as e:
        print(f"Registration error: {e}")
        return False

def test_login():
    print("\nTesting login...")
    try:
        login_response = requests.post('http://localhost:8000/api/auth/login', 
                                     json={'email': 'test@example.com', 'password': 'password123'},
                                     timeout=10)
        
        print(f"Login response: {login_response.status_code}")
        print(f"Login response body: {login_response.text}")
        
        if login_response.status_code == 200:
            print("\n✅ Login successful!")
            return login_response.json()
        else:
            print("\n❌ Login failed")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

if __name__ == "__main__":
    # First try to register
    registration_success = test_user_registration()
    
    # Then try to login
    login_result = test_login()
    
    if login_result:
        session = login_result.get('session', {})
        token = session.get('access_token', 'N/A')
        print(f"\nAccess token obtained: {token[:50] if token != 'N/A' else 'N/A'}...")
    
    print(f"\nSummary:")
    print(f"Registration: {'✅ Success' if registration_success else '❌ Failed'}")
    print(f"Login: {'✅ Success' if login_result else '❌ Failed'}")