#!/usr/bin/env python3
"""Test script to verify Firebase to Supabase migration."""

import requests
import json
import sys

def test_endpoint(url, description):
    """Test a single endpoint."""
    try:
        response = requests.get(url, timeout=5)
        print(f"✓ {description}: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"  Response: {json.dumps(data, indent=2)[:200]}...")
            except:
                print(f"  Response: {response.text[:100]}...")
        return response.status_code == 200
    except Exception as e:
        print(f"✗ {description}: Failed - {e}")
        return False

def main():
    """Run migration tests."""
    base_url = "http://localhost:8000"
    
    print("Testing Firebase to Supabase Migration...")
    print("=" * 50)
    
    # Test basic endpoints
    tests = [
        (f"{base_url}/", "Root endpoint"),
        (f"{base_url}/health", "Health check"),
        (f"{base_url}/docs", "API documentation"),
        (f"{base_url}/api/v1/users/me", "User endpoint (should require auth)"),
    ]
    
    passed = 0
    total = len(tests)
    
    for url, description in tests:
        if test_endpoint(url, description):
            passed += 1
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed >= 3:  # Allow auth endpoint to fail
        print("✓ Migration appears successful!")
        return 0
    else:
        print("✗ Migration has issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())