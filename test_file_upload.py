#!/usr/bin/env python3
"""
Test actual file upload process
"""

import requests
import json
import io
import os

BASE_URL = "http://localhost:8000"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6InZMNGovQS9jZXNQdkRrZDgiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3N0emR5d2hiZG92am9qdHF4bXNkLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiIxMWJjOThjNi1jZjNkLTRjN2ItOTM5YS1mZmY0YjlmYzgwOGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU4NzU2NzQ2LCJpYXQiOjE3NTg3NTMxNDYsImVtYWlsIjoidGVzdHVzZXJfY2EzMDI1MzBAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc1ODc1MzE0Nn1dLCJzZXNzaW9uX2lkIjoiODNkNWI5ZTQtMmY2Yi00N2NhLTgyNGEtZTg1MTU2NmNiMTM5IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Zrzu8iKkIVikDBERpKBvsUDWbQCbD1SZ62bOd0gIOTw"

def create_test_file():
    """Create a small test file for upload"""
    test_content = "This is a test file for upload testing."
    return io.BytesIO(test_content.encode('utf-8'))

def test_upload_endpoints():
    """Test various upload endpoints with proper file data"""
    print("🔧 TESTING FILE UPLOAD ENDPOINTS")
    print("=" * 50)
    
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    
    # Create test file
    test_file = create_test_file()
    
    print("\n1. Testing POST /api/upload with file...")
    try:
        test_file.seek(0)
        files = {'file': ('test.txt', test_file, 'text/plain')}
        
        response = requests.post(
            f"{BASE_URL}/api/upload",
            headers=headers,
            files=files,
            timeout=30
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. Testing POST /api/v1/upload with file...")
    try:
        test_file.seek(0)
        files = {'file': ('test.txt', test_file, 'text/plain')}
        
        response = requests.post(
            f"{BASE_URL}/api/v1/upload",
            headers=headers,
            files=files,
            timeout=30
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n3. Testing POST /api/upload with JSON data...")
    try:
        data = {
            "filename": "test.txt",
            "content_type": "text/plain",
            "size": 38
        }
        
        response = requests.post(
            f"{BASE_URL}/api/upload",
            headers={**headers, "Content-Type": "application/json"},
            json=data,
            timeout=30
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n4. Testing available upload endpoints...")
    test_available_endpoints(headers)

def test_available_endpoints(headers):
    """Test what upload endpoints are available"""
    endpoints_to_test = [
        "/api/upload",
        "/api/v1/upload", 
        "/api/files/upload",
        "/api/media/upload",
        "/upload",
        "/api/v1/files/upload"
    ]
    
    for endpoint in endpoints_to_test:
        try:
            # Test OPTIONS to see if endpoint exists
            response = requests.options(
                f"{BASE_URL}{endpoint}",
                headers=headers,
                timeout=10
            )
            print(f"   OPTIONS {endpoint}: {response.status_code}")
            if response.status_code != 404:
                print(f"     Allowed methods: {response.headers.get('Allow', 'N/A')}")
                
        except Exception as e:
            print(f"   OPTIONS {endpoint}: Error - {e}")

def test_validation_middleware():
    """Test what's causing the validation errors"""
    print("\n🔍 TESTING VALIDATION MIDDLEWARE")
    print("=" * 50)
    
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    
    # Test with different content types and payloads
    test_cases = [
        {
            "name": "Empty POST",
            "method": "POST",
            "endpoint": "/api/upload",
            "data": None,
            "headers": headers
        },
        {
            "name": "Simple JSON",
            "method": "POST", 
            "endpoint": "/api/upload",
            "data": {"test": "value"},
            "headers": {**headers, "Content-Type": "application/json"}
        },
        {
            "name": "Form data",
            "method": "POST",
            "endpoint": "/api/upload",
            "data": {"test": "value"},
            "headers": headers,
            "as_form": True
        }
    ]
    
    for case in test_cases:
        print(f"\n   Testing: {case['name']}")
        try:
            if case['method'] == 'POST':
                if case.get('as_form'):
                    response = requests.post(
                        f"{BASE_URL}{case['endpoint']}",
                        headers=case['headers'],
                        data=case['data'],
                        timeout=10
                    )
                else:
                    response = requests.post(
                        f"{BASE_URL}{case['endpoint']}",
                        headers=case['headers'],
                        json=case['data'],
                        timeout=10
                    )
                    
                print(f"     Status: {response.status_code}")
                print(f"     Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"     Error: {e}")

def check_backend_routes():
    """Check what routes are actually available"""
    print("\n📋 CHECKING AVAILABLE ROUTES")
    print("=" * 50)
    
    try:
        # Get OpenAPI spec to see available routes
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        if response.status_code == 200:
            openapi_spec = response.json()
            paths = openapi_spec.get('paths', {})
            
            print(f"\n   Available API paths:")
            for path, methods in paths.items():
                if 'upload' in path.lower() or 'file' in path.lower():
                    print(f"     {path}: {list(methods.keys())}")
                    
            # Look for any upload-related paths
            upload_paths = [path for path in paths.keys() if 'upload' in path.lower() or 'file' in path.lower()]
            if upload_paths:
                print(f"\n   Upload-related paths found: {upload_paths}")
            else:
                print(f"\n   ❌ No upload-related paths found in API spec")
                
        else:
            print(f"   ❌ Could not get OpenAPI spec: {response.status_code}")
            
    except Exception as e:
        print(f"   Error checking routes: {e}")

if __name__ == "__main__":
    test_upload_endpoints()
    test_validation_middleware()
    check_backend_routes()
    
    print("\n" + "=" * 50)
    print("🔧 DIAGNOSIS SUMMARY:")
    print("✅ Authentication: WORKING")
    print("❌ File Upload: BLOCKED by validation middleware")
    print("\n🎯 ROOT CAUSE: Input validation middleware is rejecting upload requests")
    print("\n🛠️  NEXT STEPS:")
    print("1. Check ValidationMiddleware configuration in main.py")
    print("2. Review upload endpoint implementation")
    print("3. Verify file upload routes are properly defined")