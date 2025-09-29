import requests
import json
import uuid

# Test the fixed registration API endpoint
BASE_URL = "http://localhost:8001"

def test_registration():
    """Test the registration endpoint with the backend API"""
    
    # Generate a unique test email
    test_email = f"api_test_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "testpassword123"
    
    print(f"🧪 Testing registration API with email: {test_email}")
    
    # Registration data
    registration_data = {
        "email": test_email,
        "password": test_password,
        "full_name": "API Test User"
    }
    
    try:
        # Test registration endpoint
        print("\n🔸 Step 1: Testing registration endpoint...")
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=registration_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print("✅ Registration successful!")
            print(f"   User ID: {result['user']['id']}")
            print(f"   Email: {result['user']['email']}")
            print(f"   Display Name: {result['user']['display_name']}")
            print(f"   Access Token: {result['tokens']['access_token'][:20]}...")
            
            # Test login with the same credentials
            print("\n🔸 Step 2: Testing login endpoint...")
            login_data = {
                "email": test_email,
                "password": test_password
            }
            
            login_response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            print(f"   Login Status Code: {login_response.status_code}")
            
            if login_response.status_code == 200:
                login_result = login_response.json()
                print("✅ Login successful!")
                print(f"   User ID: {login_result['user']['id']}")
                print(f"   Last Login: {login_result['user']['last_login']}")
                print(f"   Access Token: {login_result['tokens']['access_token'][:20]}...")
                
                # Test token verification
                print("\n🔸 Step 3: Testing token verification...")
                verify_response = requests.post(
                    f"{BASE_URL}/auth/verify",
                    headers={
                        "Authorization": f"Bearer {login_result['tokens']['access_token']}",
                        "Content-Type": "application/json"
                    },
                    timeout=30
                )
                
                print(f"   Verify Status Code: {verify_response.status_code}")
                
                if verify_response.status_code == 200:
                    verify_result = verify_response.json()
                    print("✅ Token verification successful!")
                    print(f"   Verified User ID: {verify_result['user']['id']}")
                    print(f"   Verified Email: {verify_result['user']['email']}")
                else:
                    print(f"❌ Token verification failed: {verify_response.text}")
                    
            else:
                print(f"❌ Login failed: {login_response.text}")
                
        else:
            print(f"❌ Registration failed: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - is the backend server running on port 8001?")
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    print("🚀 Testing Cliper Authentication API")
    print("=====================================\n")
    test_registration()
    print("\n📝 Test completed!")