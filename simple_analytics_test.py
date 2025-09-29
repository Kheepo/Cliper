#!/usr/bin/env python3
"""
Simple test to check analytics endpoints
"""

import requests
import json

def test_simple_endpoint(endpoint):
    """Test a single endpoint with minimal timeout"""
    url = f"http://localhost:8000{endpoint}"
    print(f"Testing: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Success: {json.dumps(data, indent=2)[:200]}...")
            except:
                print(f"Response: {response.text[:200]}...")
        else:
            print(f"Error: {response.text[:200]}...")
        return response.status_code
    except Exception as e:
        print(f"Exception: {e}")
        return None

if __name__ == "__main__":
    print("Simple Analytics Test")
    print("=" * 40)
    
    # Test basic endpoints first
    print("\n1. Testing basic health:")
    test_simple_endpoint("/api/health")
    
    print("\n2. Testing analytics endpoints:")
    test_simple_endpoint("/api/analytics/jobs")
    test_simple_endpoint("/api/analytics/user")
    
    print("\n3. Testing if analytics router is mounted:")
    test_simple_endpoint("/analytics/user")
    test_simple_endpoint("/analytics/jobs")
    
    print("\nTest completed.")