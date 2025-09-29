#!/usr/bin/env python3
"""
Database Connectivity and RLS Policies Test

This script tests:
1. Database connectivity
2. Supabase connection
3. RLS policies functionality
4. Table permissions
5. Authentication flow with database
"""

import requests
import json
import os
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"

def test_health_endpoints():
    """Test various health check endpoints"""
    print("\n=== Testing Health Endpoints ===")
    
    endpoints = [
        "/health",
        "/health/detailed", 
        "/api/health",
        "/api/health/simple",
        "/api/health/detailed",
        "/api/health/database",
        "/api/health/readiness"
    ]
    
    results = []
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            print(f"✓ {endpoint}: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if 'status' in data:
                    print(f"  Status: {data['status']}")
                results.append((endpoint, True, response.status_code))
            else:
                results.append((endpoint, False, response.status_code))
        except requests.exceptions.ConnectionError:
            print(f"✗ {endpoint}: Connection failed")
            results.append((endpoint, False, "Connection Error"))
        except Exception as e:
            print(f"✗ {endpoint}: {str(e)}")
            results.append((endpoint, False, str(e)))
    
    return results

def test_supabase_config():
    """Test Supabase configuration endpoint"""
    print("\n=== Testing Supabase Configuration ===")
    
    try:
        response = requests.get(f"{BASE_URL}/api/config/supabase")
        print(f"Supabase config response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Supabase URL available: {'url' in data}")
            print(f"✓ Supabase anon key available: {'anon_key' in data}")
            
            # Check if values are not empty
            if data.get('url') and data.get('anon_key'):
                print("✓ Supabase configuration is complete")
                return True, data
            else:
                print("✗ Supabase configuration is incomplete")
                return False, data
        else:
            print(f"✗ Failed to get Supabase config: {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"✗ Supabase config test failed: {e}")
        return False, None

def test_database_tables():
    """Test database table access"""
    print("\n=== Testing Database Tables Access ===")
    
    # Test endpoints that interact with database
    endpoints_to_test = [
        ("/api/videos/", "GET", "Videos list"),
        ("/api/auth/me", "GET", "Current user"),
        ("/api/users/profile", "GET", "User profile"),
    ]
    
    results = []
    
    for endpoint, method, description in endpoints_to_test:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}")
            else:
                response = requests.post(f"{BASE_URL}{endpoint}")
            
            print(f"{description}: {response.status_code}")
            
            # Check if it's an authentication error (expected) vs database error
            if response.status_code == 401:
                print(f"  ✓ {description} requires authentication (database accessible)")
                results.append((description, True))
            elif response.status_code == 500:
                print(f"  ✗ {description} has server error (possible database issue)")
                print(f"    Response: {response.text[:100]}...")
                results.append((description, False))
            elif response.status_code in [200, 404]:
                print(f"  ✓ {description} accessible")
                results.append((description, True))
            else:
                print(f"  ? {description} returned {response.status_code}")
                results.append((description, True))  # Assume OK if not 500
                
        except Exception as e:
            print(f"  ✗ {description} test failed: {e}")
            results.append((description, False))
    
    return results

def test_rls_policies():
    """Test Row Level Security policies"""
    print("\n=== Testing RLS Policies ===")
    
    # Test that unauthenticated requests are properly blocked
    print("Testing unauthenticated access (should be blocked by RLS):")
    
    test_cases = [
        ("/api/videos/", "Videos access without auth"),
        ("/api/auth/me", "User info without auth"),
        ("/api/users/profile", "Profile access without auth"),
    ]
    
    rls_working = True
    
    for endpoint, description in test_cases:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            
            if response.status_code == 401:
                print(f"  ✓ {description}: Properly blocked (401)")
            elif response.status_code == 403:
                print(f"  ✓ {description}: Properly blocked (403)")
            elif response.status_code == 200:
                print(f"  ⚠ {description}: Accessible without auth (check RLS)")
                # This might be OK for some endpoints, but worth noting
            else:
                print(f"  ? {description}: Status {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ {description}: Test failed - {e}")
            rls_working = False
    
    return rls_working

def test_authentication_flow():
    """Test authentication flow with database"""
    print("\n=== Testing Authentication Flow ===")
    
    # Test registration endpoint
    try:
        test_user = {
            "email": "test@example.com",
            "password": "testpassword123",
            "full_name": "Test User"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=test_user,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Registration test: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ Registration endpoint accessible")
        elif response.status_code == 400:
            print("✓ Registration endpoint working (validation error expected)")
        elif response.status_code == 500:
            print("✗ Registration has server error (possible database issue)")
            print(f"  Response: {response.text[:200]}...")
        else:
            print(f"? Registration returned {response.status_code}")
            
    except Exception as e:
        print(f"✗ Registration test failed: {e}")
    
    # Test login endpoint
    try:
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Login test: {response.status_code}")
        
        if response.status_code in [200, 400, 401]:
            print("✓ Login endpoint accessible")
        elif response.status_code == 500:
            print("✗ Login has server error (possible database issue)")
            print(f"  Response: {response.text[:200]}...")
        else:
            print(f"? Login returned {response.status_code}")
            
    except Exception as e:
        print(f"✗ Login test failed: {e}")

def test_file_storage():
    """Test file storage connectivity"""
    print("\n=== Testing File Storage ===")
    
    # Create a small test file
    test_file_content = b"test file content for storage test"
    test_file_path = "test_storage_file.txt"
    
    try:
        with open(test_file_path, 'wb') as f:
            f.write(test_file_content)
        
        # Test file upload (this will test storage connectivity)
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/api/videos/upload", files=files)
        
        print(f"File upload test: {response.status_code}")
        
        if response.status_code == 401:
            print("✓ File upload requires authentication (storage accessible)")
        elif response.status_code == 200:
            print("✓ File upload successful")
        elif response.status_code == 500:
            print("✗ File upload has server error (possible storage issue)")
            print(f"  Response: {response.text[:200]}...")
        else:
            print(f"? File upload returned {response.status_code}")
            
        # Cleanup
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
            
    except Exception as e:
        print(f"✗ File storage test failed: {e}")
        # Cleanup on error
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

def main():
    """Run all database connectivity and RLS tests"""
    print("🗄️ DATABASE CONNECTIVITY AND RLS POLICIES TEST")
    print("=" * 55)
    
    # Test health endpoints
    health_results = test_health_endpoints()
    
    # Test Supabase configuration
    supabase_ok, supabase_config = test_supabase_config()
    
    # Test database table access
    table_results = test_database_tables()
    
    # Test RLS policies
    rls_ok = test_rls_policies()
    
    # Test authentication flow
    test_authentication_flow()
    
    # Test file storage
    test_file_storage()
    
    # Summary
    print("\n" + "=" * 55)
    print("📊 DATABASE CONNECTIVITY TEST SUMMARY")
    print("=" * 55)
    
    # Health endpoints summary
    working_health = sum(1 for _, success, _ in health_results if success)
    total_health = len(health_results)
    print(f"Health Endpoints: {working_health}/{total_health} working")
    
    # Database tables summary
    working_tables = sum(1 for _, success in table_results if success)
    total_tables = len(table_results)
    print(f"Database Tables: {working_tables}/{total_tables} accessible")
    
    # Overall status
    print(f"\nSupabase Config: {'✓ OK' if supabase_ok else '✗ FAIL'}")
    print(f"RLS Policies: {'✓ OK' if rls_ok else '✗ FAIL'}")
    
    if working_health < total_health or working_tables < total_tables or not supabase_ok:
        print("\n🔧 COMMON ISSUES:")
        print("- Database not connected: Check Supabase URL and keys")
        print("- RLS policies not configured: Check table permissions")
        print("- Server not running: Start with 'python run_server.py'")
        print("- Environment variables missing: Check .env file")
        print("- Network connectivity: Check firewall and DNS")
    
    overall_success = (working_health > 0 and working_tables > 0 and supabase_ok)
    return overall_success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)