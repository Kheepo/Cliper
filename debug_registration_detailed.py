import requests
import json
import uuid
from datetime import datetime

def test_registration_detailed():
    """Detailed test of registration endpoint with comprehensive error reporting"""
    
    # Generate unique test email
    test_id = str(uuid.uuid4())[:8]
    test_email = f"detailed_test_{test_id}@example.com"
    
    print(f"🧪 Detailed Registration Test")
    print(f"Email: {test_email}")
    print(f"Time: {datetime.now()}")
    print("=" * 50)
    
    # Test data
    registration_data = {
        "email": test_email,
        "password": "TestPassword123!",
        "full_name": "Test User Detailed"
    }
    
    try:
        # Test server connectivity first
        print("\n🔸 Step 1: Testing server connectivity...")
        health_response = requests.get("http://localhost:8001/health", timeout=5)
        print(f"   Health check status: {health_response.status_code}")
        if health_response.status_code == 200:
            print("   ✅ Server is responding")
        else:
            print(f"   ❌ Server health check failed: {health_response.text}")
            return
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Server connectivity failed: {e}")
        return
    
    try:
        # Test registration endpoint
        print("\n🔸 Step 2: Testing registration endpoint...")
        print(f"   URL: http://localhost:8001/api/auth/register")
        print(f"   Data: {json.dumps(registration_data, indent=2)}")
        
        response = requests.post(
            "http://localhost:8001/api/auth/register",
            json=registration_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"\n📊 Response Details:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        try:
            response_json = response.json()
            print(f"   Response Body: {json.dumps(response_json, indent=2)}")
        except json.JSONDecodeError:
            print(f"   Response Text: {response.text}")
        
        if response.status_code == 200 or response.status_code == 201:
            print("   ✅ Registration successful!")
            
            # Test login if registration succeeded
            print("\n🔸 Step 3: Testing login...")
            login_data = {
                "email": test_email,
                "password": "TestPassword123!"
            }
            
            login_response = requests.post(
                "http://localhost:8001/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            print(f"   Login Status: {login_response.status_code}")
            if login_response.status_code == 200:
                login_json = login_response.json()
                print(f"   ✅ Login successful!")
                print(f"   Token received: {bool(login_json.get('access_token'))}")
            else:
                print(f"   ❌ Login failed: {login_response.text}")
                
        else:
            print(f"   ❌ Registration failed with status {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("   ❌ Request timed out - server may be overloaded")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    print("\n📝 Test completed!")

if __name__ == "__main__":
    test_registration_detailed()