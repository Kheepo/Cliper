import requests
import json

# Test the login API endpoint
BASE_URL = "http://localhost:8001"

def test_login():
    """Test the login endpoint with the backend API"""
    
    # Use the email from the previous registration test
    test_email = "api_test_31a2fa6d@example.com"
    test_password = "testpassword123"
    
    print(f"🧪 Testing login API with email: {test_email}")
    
    # Login data
    login_data = {
        "email": test_email,
        "password": test_password
    }
    
    try:
        print("\n🔸 Step 1: Testing login endpoint...")
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Login successful!")
            print(f"   User ID: {result['user']['id']}")
            print(f"   Email: {result['user']['email']}")
            print(f"   Display Name: {result['user']['display_name']}")
            print(f"   Token Type: {result['tokens']['token_type']}")
            print(f"   Expires In: {result['tokens']['expires_in']}")
            
            # Test protected endpoint
            print("\n🔸 Step 2: Testing protected endpoint...")
            headers = {
                "Authorization": f"Bearer {result['tokens']['access_token']}"
            }
            
            # Test both profile endpoints
            profile_response = requests.get(f"{BASE_URL}/api/users/profile", headers=headers, timeout=10)
            print(f"   Users profile endpoint status: {profile_response.status_code}")
            
            auth_me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=10)
            print(f"   Auth me endpoint status: {auth_me_response.status_code}")
            
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                print("✅ Users profile endpoint working!")
                print(f"   Profile ID: {profile_data.get('id', 'N/A')}")
                print(f"   Profile Email: {profile_data.get('email', 'N/A')}")
            else:
                print(f"❌ Users profile endpoint failed: {profile_response.text}")
                
            if auth_me_response.status_code == 200:
                me_data = auth_me_response.json()
                print("✅ Auth me endpoint working!")
                print(f"   Me ID: {me_data.get('id', 'N/A')}")
                print(f"   Me Email: {me_data.get('email', 'N/A')}")
            else:
                print(f"❌ Auth me endpoint failed: {auth_me_response.text}")
                
        else:
            print(f"❌ Login failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Login test error: {e}")

if __name__ == "__main__":
    print("🚀 Testing Cliper Login API")
    print("=============================")
    test_login()
    print("\n📝 Test completed!")