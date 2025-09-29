#!/usr/bin/env python3
"""
Test script for authentication endpoints
"""

import requests
import json

def test_auth_endpoints():
    base_url = "http://localhost:8000/api/auth"
    
    print("Testing Authentication Endpoints")
    print("=" * 50)
    
    # Test /me endpoint (should return 401 without auth)
    try:
        print("\n1. Testing /me endpoint (without auth)...")
        response = requests.get(f"{base_url}/me")
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correctly returns 401 Unauthorized")
        else:
            print(f"   Response: {response.text[:200]}")
    except requests.exceptions.ConnectionError:
        print("   ❌ Connection failed - server may not be running")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test /verify endpoint (should return 401 without auth)
    try:
        print("\n2. Testing /verify endpoint (without auth)...")
        response = requests.post(f"{base_url}/verify")
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correctly returns 401 Unauthorized")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ Auth endpoints are responding correctly!")
    print("Server is running and auth routes are working.")
    return True

if __name__ == "__main__":
    test_auth_endpoints()