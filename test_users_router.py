import requests
import json

# Test if the users router is properly loaded
BASE_URL = "http://localhost:8001"

def test_users_router():
    """Test if the users router endpoints are accessible"""
    
    print("🧪 Testing Users Router Endpoints")
    print("=================================")
    
    # Test endpoints without authentication first
    endpoints_to_test = [
        "/api/users",
        "/api/users/profile",
        "/api/auth",
        "/api/auth/me"
    ]
    
    for endpoint in endpoints_to_test:
        try:
            print(f"\n🔸 Testing {endpoint}...")
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 404:
                print(f"   ❌ Endpoint not found: {endpoint}")
            elif response.status_code == 401 or response.status_code == 403:
                print(f"   ✅ Endpoint exists but requires authentication: {endpoint}")
            elif response.status_code == 422:
                print(f"   ✅ Endpoint exists but has validation errors: {endpoint}")
            else:
                print(f"   ✅ Endpoint accessible: {endpoint}")
                
        except Exception as e:
            print(f"   ❌ Error testing {endpoint}: {e}")
    
    # Test with authentication
    print("\n🔸 Testing with authentication...")
    
    # Login first
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
            
            # Test authenticated endpoints
            auth_endpoints = [
                "/api/users/profile",
                "/api/auth/me"
            ]
            
            for endpoint in auth_endpoints:
                try:
                    print(f"\n🔸 Testing authenticated {endpoint}...")
                    response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=5)
                    print(f"   Status Code: {response.status_code}")
                    
                    if response.status_code == 200:
                        print(f"   ✅ Authenticated endpoint working: {endpoint}")
                    else:
                        print(f"   ❌ Authenticated endpoint failed: {endpoint}")
                        print(f"   Response: {response.text[:200]}")
                        
                except Exception as e:
                    print(f"   ❌ Error testing authenticated {endpoint}: {e}")
        else:
            print(f"❌ Login failed: {login_response.text}")
            
    except Exception as e:
        print(f"❌ Authentication test error: {e}")

if __name__ == "__main__":
    test_users_router()
    print("\n📝 Router test completed!")