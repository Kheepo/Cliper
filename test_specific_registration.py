import requests
import json

def test_specific_registration():
    """Test registration with a specific email that worked before"""
    
    print("🚀 Testing Specific Registration")
    print("================================")
    
    base_url = "http://localhost:8001"
    
    # Use a simple email format that worked before
    test_email = "simple_test@example.com"
    test_password = "testpassword123"
    
    print(f"🔸 Testing with email: {test_email}")
    
    registration_data = {
        "email": test_email,
        "password": test_password
    }
    
    try:
        print("\n🔸 Sending registration request...")
        response = requests.post(
            f"{base_url}/api/auth/register",
            json=registration_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text[:500]}...")
        
        if response.status_code == 200:
            data = response.json()
            user_data = data.get('user', {})
            tokens = data.get('tokens', {})
            
            print("✅ Registration successful!")
            print(f"   User ID: {user_data.get('id')}")
            print(f"   Email: {user_data.get('email')}")
            print(f"   Display Name: {user_data.get('display_name')}")
            
            # Test login immediately
            print("\n🔸 Testing immediate login...")
            login_response = requests.post(
                f"{base_url}/api/auth/login",
                json={"email": test_email, "password": test_password},
                headers={"Content-Type": "application/json"}
            )
            
            print(f"   Login Status Code: {login_response.status_code}")
            if login_response.status_code == 200:
                print("✅ Login also successful!")
            else:
                print(f"❌ Login failed: {login_response.text}")
            
        else:
            print(f"❌ Registration failed")
            print(f"   Error details: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out - server might be overloaded")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - server might be down")
    except Exception as e:
        print(f"❌ Registration error: {e}")

if __name__ == "__main__":
    test_specific_registration()
    print("\n📝 Specific registration test completed!")