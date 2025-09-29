#!/usr/bin/env python3
"""
User Profile Management Test
Tests user profile endpoints and functionality
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def test_server_connectivity() -> bool:
    """Test if the server is running"""
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def test_user_profile_endpoints() -> Dict[str, Any]:
    """Test user profile related endpoints"""
    print("\n=== Testing User Profile Endpoints ===")
    
    endpoints_to_test = [
        ("/api/users/profile", "GET"),
        ("/api/users/me", "GET"),
        ("/api/user/profile", "GET"),
        ("/api/profile", "GET"),
        ("/api/users/settings", "GET"),
        ("/api/user/settings", "GET"),
        ("/api/settings", "GET")
    ]
    
    results = {}
    
    for endpoint, method in endpoints_to_test:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", timeout=10)
            
            status = response.status_code
            print(f"{endpoint} ({method}): {status}")
            
            if status in [200, 401, 403]:  # Expected responses
                print(f"  ✓ Endpoint available")
                results[endpoint] = {"status": "available", "code": status}
            elif status == 404:
                print(f"  ✗ Endpoint not found")
                results[endpoint] = {"status": "not_found", "code": status}
            else:
                print(f"  ? Unexpected status: {status}")
                results[endpoint] = {"status": "unexpected", "code": status}
                
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")
            results[endpoint] = {"status": "error", "error": str(e)}
    
    return results

def test_user_update_endpoints() -> Dict[str, Any]:
    """Test user profile update endpoints"""
    print("\n=== Testing User Profile Update Endpoints ===")
    
    endpoints_to_test = [
        ("/api/users/profile", "PUT"),
        ("/api/users/profile", "PATCH"),
        ("/api/users/me", "PUT"),
        ("/api/users/me", "PATCH"),
        ("/api/user/profile", "PUT"),
        ("/api/profile", "PUT"),
        ("/api/users/settings", "PUT"),
        ("/api/user/settings", "PUT")
    ]
    
    results = {}
    test_data = {
        "name": "Test User",
        "email": "test@example.com",
        "preferences": {"theme": "dark"}
    }
    
    for endpoint, method in endpoints_to_test:
        try:
            if method == "PUT":
                response = requests.put(
                    f"{BASE_URL}{endpoint}",
                    json=test_data,
                    timeout=10
                )
            elif method == "PATCH":
                response = requests.patch(
                    f"{BASE_URL}{endpoint}",
                    json=test_data,
                    timeout=10
                )
            
            status = response.status_code
            print(f"{endpoint} ({method}): {status}")
            
            if status in [200, 401, 403, 422]:  # Expected responses
                print(f"  ✓ Endpoint available")
                results[endpoint] = {"status": "available", "code": status}
            elif status == 404:
                print(f"  ✗ Endpoint not found")
                results[endpoint] = {"status": "not_found", "code": status}
            else:
                print(f"  ? Unexpected status: {status}")
                results[endpoint] = {"status": "unexpected", "code": status}
                
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")
            results[endpoint] = {"status": "error", "error": str(e)}
    
    return results

def test_user_management_endpoints() -> Dict[str, Any]:
    """Test user management endpoints"""
    print("\n=== Testing User Management Endpoints ===")
    
    endpoints_to_test = [
        ("/api/users", "GET"),
        ("/api/users/list", "GET"),
        ("/api/admin/users", "GET"),
        ("/api/users/search", "GET"),
        ("/api/users/count", "GET")
    ]
    
    results = {}
    
    for endpoint, method in endpoints_to_test:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            status = response.status_code
            print(f"{endpoint} ({method}): {status}")
            
            if status in [200, 401, 403]:  # Expected responses
                print(f"  ✓ Endpoint available")
                results[endpoint] = {"status": "available", "code": status}
            elif status == 404:
                print(f"  ✗ Endpoint not found")
                results[endpoint] = {"status": "not_found", "code": status}
            else:
                print(f"  ? Unexpected status: {status}")
                results[endpoint] = {"status": "unexpected", "code": status}
                
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")
            results[endpoint] = {"status": "error", "error": str(e)}
    
    return results

def test_user_preferences_endpoints() -> Dict[str, Any]:
    """Test user preferences and settings endpoints"""
    print("\n=== Testing User Preferences Endpoints ===")
    
    endpoints_to_test = [
        ("/api/users/preferences", "GET"),
        ("/api/user/preferences", "GET"),
        ("/api/preferences", "GET"),
        ("/api/users/preferences", "PUT"),
        ("/api/user/preferences", "PUT"),
        ("/api/preferences", "PUT")
    ]
    
    results = {}
    test_preferences = {
        "theme": "dark",
        "language": "en",
        "notifications": True,
        "auto_save": True
    }
    
    for endpoint, method in endpoints_to_test:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            else:
                response = requests.put(
                    f"{BASE_URL}{endpoint}",
                    json=test_preferences,
                    timeout=10
                )
            
            status = response.status_code
            print(f"{endpoint} ({method}): {status}")
            
            if status in [200, 401, 403, 422]:  # Expected responses
                print(f"  ✓ Endpoint available")
                results[endpoint] = {"status": "available", "code": status}
            elif status == 404:
                print(f"  ✗ Endpoint not found")
                results[endpoint] = {"status": "not_found", "code": status}
            else:
                print(f"  ? Unexpected status: {status}")
                results[endpoint] = {"status": "unexpected", "code": status}
                
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")
            results[endpoint] = {"status": "error", "error": str(e)}
    
    return results

def test_existing_user_settings_endpoint() -> Dict[str, Any]:
    """Test the existing user settings endpoint from main.py"""
    print("\n=== Testing Existing User Settings Endpoint ===")
    
    try:
        # Test GET request
        response = requests.get(f"{BASE_URL}/api/user/settings", timeout=10)
        status = response.status_code
        print(f"/api/user/settings (GET): {status}")
        
        if status == 200:
            print(f"  ✓ Settings retrieved successfully")
            try:
                data = response.json()
                print(f"  📄 Response: {json.dumps(data, indent=2)[:200]}...")
            except:
                print(f"  📄 Response: {response.text[:200]}...")
        elif status in [401, 403]:
            print(f"  ⚠ Authentication required")
        else:
            print(f"  ? Unexpected status: {status}")
        
        # Test PUT request
        test_settings = {
            "theme": "dark",
            "notifications": True,
            "language": "en"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/user/settings",
            json=test_settings,
            timeout=10
        )
        status = response.status_code
        print(f"/api/user/settings (PUT): {status}")
        
        if status == 200:
            print(f"  ✓ Settings updated successfully")
        elif status in [401, 403]:
            print(f"  ⚠ Authentication required")
        elif status == 422:
            print(f"  ⚠ Validation error")
        else:
            print(f"  ? Unexpected status: {status}")
            
        return {"get": status, "put": status}
        
    except Exception as e:
        print(f"Error testing user settings: {str(e)}")
        return {"error": str(e)}

def main():
    print("👤 USER PROFILE MANAGEMENT TEST")
    print("=" * 50)
    
    # Test server connectivity
    if not test_server_connectivity():
        print("❌ Server not accessible at", BASE_URL)
        print("\n💡 Common issues:")
        print("   • Server not running (try: python run_server.py)")
        print("   • Wrong port or URL")
        print("   • Firewall blocking connection")
        return
    
    print("✅ Server is running")
    
    # Run tests
    profile_results = test_user_profile_endpoints()
    update_results = test_user_update_endpoints()
    management_results = test_user_management_endpoints()
    preferences_results = test_user_preferences_endpoints()
    settings_results = test_existing_user_settings_endpoint()
    
    # Summary
    print("\n" + "=" * 55)
    print("📊 USER PROFILE MANAGEMENT TEST SUMMARY")
    print("=" * 55)
    
    # Count available endpoints
    total_profile = len(profile_results)
    available_profile = sum(1 for r in profile_results.values() 
                          if r.get('status') == 'available')
    
    total_update = len(update_results)
    available_update = sum(1 for r in update_results.values() 
                         if r.get('status') == 'available')
    
    total_management = len(management_results)
    available_management = sum(1 for r in management_results.values() 
                             if r.get('status') == 'available')
    
    total_preferences = len(preferences_results)
    available_preferences = sum(1 for r in preferences_results.values() 
                              if r.get('status') == 'available')
    
    print(f"Profile Endpoints: {available_profile}/{total_profile} available")
    print(f"Update Endpoints: {available_update}/{total_update} available")
    print(f"Management Endpoints: {available_management}/{total_management} available")
    print(f"Preferences Endpoints: {available_preferences}/{total_preferences} available")
    
    if isinstance(settings_results, dict) and 'get' in settings_results:
        print(f"Existing Settings Endpoint: ✓ Available (GET: {settings_results['get']}, PUT: {settings_results.get('put', 'N/A')})")
    
    print("\n📋 IMPLEMENTATION STATUS:")
    if available_profile > 0:
        print("- User profile retrieval: ✓ Available")
    else:
        print("- User profile retrieval: ✗ Not implemented")
        
    if available_update > 0:
        print("- Profile updates: ✓ Available")
    else:
        print("- Profile updates: ✗ Not implemented")
        
    if available_management > 0:
        print("- User management: ✓ Available")
    else:
        print("- User management: ✗ Not implemented")
        
    if available_preferences > 0:
        print("- User preferences: ✓ Available")
    else:
        print("- User preferences: ✗ Not implemented")
    
    print("\n💡 Common issues:")
    print("   • Most endpoints require authentication")
    print("   • Profile management may need implementation")
    print("   • User preferences system may need setup")
    print("   • Frontend integration may be needed")

if __name__ == "__main__":
    main()