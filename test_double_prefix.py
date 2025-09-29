import requests
import json

# Test the double prefix issue
BASE_URL = "http://localhost:8001"

def test_double_prefix():
    """Test if the users router has a double prefix issue"""
    
    print("🧪 Testing Double Prefix Issue")
    print("==============================")
    
    # Login first to get token
    login_data = {
        "email": "api_test_31a2fa6d@example.com",
        "password": "testpassword123"
    }
    
    try:
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data, timeout=10)
        
        if login_response.status_code == 200:
            result = login_response.json()
            access_token = result['tokens']['access_token']
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Test different possible endpoints
            endpoints_to_test = [
                "/api/users/profile",           # Expected endpoint
                "/api/users/users/profile",     # Double prefix
                "/users/profile",               # Without api prefix
                "/api/profile",                 # Without users prefix
            ]
            
            for endpoint in endpoints_to_test:
                try:
                    print(f"\n🔸 Testing {endpoint}...")
                    response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)
                    print(f"   Status Code: {response.status_code}")
                    
                    if response.status_code == 200:
                        print(f"   ✅ Working endpoint: {endpoint}")
                        data = response.json()
                        print(f"   User ID: {data.get('id', 'N/A')}")
                        print(f"   Email: {data.get('email', 'N/A')}")
                    elif response.status_code == 404:
                        print(f"   ❌ Not found: {endpoint}")
                    else:
                        print(f"   ⚠️  Other status: {endpoint} - {response.text[:100]}")
                        
                except Exception as e:
                    print(f"   ❌ Error testing {endpoint}: {e}")
        else:
            print(f"❌ Login failed: {login_response.text}")
            
    except Exception as e:
        print(f"❌ Test error: {e}")

if __name__ == "__main__":
    test_double_prefix()
    print("\n📝 Double prefix test completed!")