#!/usr/bin/env python3
"""
Simple registration debug script to isolate the "User not allowed" issue
"""

import requests
import json
import uuid
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"

def test_registration():
    """Test user registration with detailed error logging"""
    
    # Generate unique test user
    test_id = str(uuid.uuid4())[:8]
    test_email = f"debug_{test_id}@example.com"
    test_password = "TestPassword123!"
    
    print(f"🧪 Testing registration for: {test_email}")
    
    # Registration payload
    registration_data = {
        "email": test_email,
        "password": test_password,
        "display_name": f"Debug User {test_id}"
    }
    
    try:
        print("📤 Sending registration request...")
        response = requests.post(
            f"{API_BASE}/auth/register",
            json=registration_data,
            timeout=30
        )
        
        print(f"📥 Response Status: {response.status_code}")
        print(f"📥 Response Headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"📥 Response Body: {json.dumps(response_data, indent=2)}")
        except:
            print(f"📥 Response Text: {response.text}")
            
        if response.status_code == 200:
            print("✅ Registration successful!")
            return True
        else:
            print(f"❌ Registration failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"🚨 Request failed: {e}")
        return False
    except Exception as e:
        print(f"🚨 Unexpected error: {e}")
        return False

def test_server_health():
    """Test if server is responding"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"🏥 Health check: {response.status_code}")
        return response.status_code == 200
    except:
        print("🏥 Health check failed - server not responding")
        return False

if __name__ == "__main__":
    print("🔍 Starting Registration Debug Session")
    print(f"⏰ Time: {datetime.now()}")
    print(f"🌐 API Base: {API_BASE}")
    print("-" * 50)
    
    # Test server health first
    if not test_server_health():
        print("❌ Server is not responding. Please start the server first.")
        exit(1)
    
    # Test registration
    success = test_registration()
    
    print("-" * 50)
    if success:
        print("🎉 Registration debug completed successfully!")
    else:
        print("💥 Registration debug failed - investigate server logs")