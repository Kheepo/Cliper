#!/usr/bin/env python3
"""
Debug script to test path matching logic for ValidationMiddleware
"""

import requests
import json
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IjdkYWY4NzBkLWI4YzMtNGJjZC1hNzI5LWNhNzJkNzJkNzJkNyIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzM3NTU5NzI5LCJpYXQiOjE3Mzc1NTYxMjksImlzcyI6Imh0dHBzOi8vdGVzdC5zdXBhYmFzZS5jbyIsInN1YiI6IjEyMzQ1Njc4LTEyMzQtMTIzNC0xMjM0LTEyMzQ1Njc4OTAxMiIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZW1haWwiLCJwcm92aWRlcnMiOlsiZW1haWwiXX0sInVzZXJfbWV0YWRhdGEiOnt9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzM3NTU2MTI5fV0sInNlc3Npb25faWQiOiIxMjM0NTY3OC0xMjM0LTEyMzQtMTIzNC0xMjM0NTY3ODkwMTIifQ.test_signature"

def test_path_matching():
    """Test path matching logic"""
    print("=== PATH MATCHING DEBUG ===")
    
    # Test paths that should be exempt
    exempt_paths = [
        "/api/videos/upload",
        "/api/videos/upload-chunk", 
        "/api/videos/finalize-upload",
        "/api/auth/",
        "/api/health",
        "/docs",
        "/openapi.json",
        "/api/openapi.json"
    ]
    
    test_paths = [
        "/api/videos/upload",
        "/api/videos/upload-chunk",
        "/api/videos/finalize-upload", 
        "/api/auth/me",
        "/api/health",
        "/api/upload",  # This should NOT be exempt
        "/api/files/upload",  # This should NOT be exempt
    ]
    
    print("\nExempt paths configuration:")
    for path in exempt_paths:
        print(f"  - {path}")
    
    print("\nPath matching test:")
    for test_path in test_paths:
        is_exempt = any(test_path.startswith(exempt) for exempt in exempt_paths)
        print(f"  {test_path:<30} -> {'EXEMPT' if is_exempt else 'NOT EXEMPT'}")

def test_actual_requests():
    """Test actual HTTP requests to see validation behavior"""
    print("\n=== ACTUAL REQUEST TESTING ===")
    
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Test endpoints
    test_endpoints = [
        ("/api/health", "GET", None),
        ("/api/auth/me", "GET", None),
        ("/api/videos/upload", "POST", {"data": {"test": "data"}}),
        ("/api/upload", "POST", {"data": {"test": "data"}}),
        ("/api/files/upload", "POST", {"data": {"test": "data"}}),
    ]
    
    for endpoint, method, data in test_endpoints:
        url = f"{BASE_URL}{endpoint}"
        print(f"\nTesting {method} {endpoint}:")
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=10)
            
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}..." if len(response.text) > 200 else f"  Response: {response.text}")
            
        except requests.exceptions.RequestException as e:
            print(f"  Error: {e}")

def test_multipart_upload():
    """Test multipart form data upload"""
    print("\n=== MULTIPART UPLOAD TESTING ===")
    
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Create a small test file
    test_content = b"This is a test video file content for upload testing."
    
    files = {
        'file': ('test_video.mp4', test_content, 'video/mp4')
    }
    
    data = {
        'target_niche': 'test',
        'totalChunks': '1',
        'sessionId': 'test-session-123',
        'fileName': 'test_video.mp4'
    }
    
    test_endpoints = [
        "/api/videos/upload",
        "/api/upload",
        "/api/files/upload"
    ]
    
    for endpoint in test_endpoints:
        url = f"{BASE_URL}{endpoint}"
        print(f"\nTesting multipart upload to {endpoint}:")
        
        try:
            response = requests.post(
                url, 
                headers=headers, 
                files=files, 
                data=data, 
                timeout=30
            )
            
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:300]}..." if len(response.text) > 300 else f"  Response: {response.text}")
            
        except requests.exceptions.RequestException as e:
            print(f"  Error: {e}")

def main():
    """Main test function"""
    print("ValidationMiddleware Path Matching Debug")
    print("=" * 50)
    
    test_path_matching()
    test_actual_requests()
    test_multipart_upload()
    
    print("\n=== SUMMARY ===")
    print("1. Check if /api/videos/upload is properly exempt")
    print("2. Verify multipart/form-data content type is allowed")
    print("3. Check if validation middleware is blocking legitimate requests")
    print("4. Look for specific validation errors in the logs")

if __name__ == "__main__":
    main()