#!/usr/bin/env python3
"""
Test script to verify the /api/analytics/user endpoint works with proper JWT
"""

import requests
import jwt
import time
import os
from dotenv import load_dotenv

load_dotenv()

def create_test_jwt():
    """
    Create a properly formatted JWT token for testing
    """
    payload = {
        'sub': 'test-user-id-12345',
        'email': 'test@example.com',
        'exp': int(time.time()) + 3600,  # Expires in 1 hour
        'iat': int(time.time()),
        'aud': 'authenticated',
        'user_metadata': {'name': 'Test User'},
        'app_metadata': {'role': 'free'},
        'email_confirmed_at': '2023-01-01T00:00:00Z'
    }
    
    # Create a JWT token (unsigned for testing)
    token = jwt.encode(payload, 'test-secret', algorithm='HS256')
    return token

def test_analytics_endpoint():
    """
    Test the /api/analytics/user endpoint
    """
    print("=== Testing /api/analytics/user Endpoint ===")
    
    # Create a test JWT
    test_token = create_test_jwt()
    print(f"Created test JWT: {test_token[:50]}...")
    
    # Test the endpoint
    url = "http://localhost:8001/api/analytics/user"
    headers = {
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"\nTesting endpoint: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Endpoint returned 200 OK")
            return True
        elif response.status_code == 401:
            print("⚠️  AUTHENTICATION: Still getting 401, but error message may have changed")
            return False
        elif response.status_code == 422:
            print("⚠️  VALIDATION: Getting 422, likely due to missing request body")
            return False
        else:
            print(f"❌ UNEXPECTED: Got status code {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR: Make sure the server is running on localhost:8001")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_with_request_body():
    """
    Test the endpoint with a proper request body
    """
    print("\n=== Testing with Request Body ===")
    
    test_token = create_test_jwt()
    
    url = "http://localhost:8001/api/analytics/user"
    headers = {
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json"
    }
    
    # Create a proper request body based on the analytics schema
    request_body = {
        "time_range": "last_30_days",
        "metrics": ["total_clips", "total_views"]
    }
    
    try:
        print(f"Testing with request body: {request_body}")
        response = requests.post(url, headers=headers, json=request_body, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Endpoint works with request body!")
            return True
        else:
            print(f"⚠️  Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("Testing Analytics Endpoint Authentication Fix...\n")
    
    # Test GET request
    get_result = test_analytics_endpoint()
    
    # Test POST request with body
    post_result = test_with_request_body()
    
    print("\n=== Final Results ===")
    print(f"GET test: {'✅ PASSED' if get_result else '❌ FAILED'}")
    print(f"POST test: {'✅ PASSED' if post_result else '❌ FAILED'}")
    
    if get_result or post_result:
        print("\n🎉 Authentication fix is working!")
        print("The Supabase client authentication has been successfully fixed.")
    else:
        print("\n❌ Authentication fix needs more investigation.")