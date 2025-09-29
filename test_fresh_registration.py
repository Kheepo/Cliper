import requests
import json
import uuid

def test_fresh_registration():
    """Test registration with a completely fresh email"""
    
    print("🚀 Testing Fresh Registration")
    print("==============================")
    
    base_url = "http://localhost:8001"
    
    # Use a completely unique email
    test_email = f"fresh_{uuid.uuid4().hex[:12]}@example.com"
    test_password = "testpassword123"
    
    print(f"🔸 Testing with fresh email: {test_email}")
    
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
            timeout=15
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            user_data = data.get('user', {})
            tokens = data.get('tokens', {})
            
            print("✅ Registration successful!")
            print(f"   User ID: {user_data.get('id')}")
            print(f"   Email: {user_data.get('email')}")
            print(f"   Display Name: {user_data.get('display_name')}")
            print(f"   Access Token: {tokens.get('access_token', 'N/A')[:20]}...")
            
            # Test immediate login
            print("\n🔸 Testing immediate login...")
            login_response = requests.post(
                f"{base_url}/api/auth/login",
                json={"email": test_email, "password": test_password},
                headers={"Content-Type": "application/json"}
            )
            
            print(f"   Login Status Code: {login_response.status_code}")
            if login_response.status_code == 200:
                login_data = login_response.json()
                print("✅ Login successful!")
                print(f"   User ID: {login_data.get('user', {}).get('id')}")
            else:
                print(f"❌ Login failed: {login_response.text}")
            
            # Test protected endpoint
            print("\n🔸 Testing protected endpoint...")
            headers = {
                "Authorization": f"Bearer {tokens.get('access_token')}",
                "Content-Type": "application/json"
            }
            
            profile_response = requests.get(
                f"{base_url}/api/users/profile",
                headers=headers
            )
            
            print(f"   Profile Status Code: {profile_response.status_code}")
            if profile_response.status_code == 200:
                print("✅ Protected endpoint access successful!")
            else:
                print(f"❌ Protected endpoint failed: {profile_response.text}")
            
        elif response.status_code == 500:
            print(f"❌ Registration failed with 500 error")
            try:
                error_data = response.json()
                print(f"   Error details: {error_data.get('detail', 'No details')}")
            except:
                print(f"   Raw error: {response.text}")
        else:
            print(f"❌ Registration failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out - server might be overloaded")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - server might be down")
    except Exception as e:
        print(f"❌ Registration error: {e}")

if __name__ == "__main__":
    test_fresh_registration()
    print("\n📝 Fresh registration test completed!")