#!/usr/bin/env python3
"""
Test script to verify backend authentication endpoints
"""

import requests
import json

# Test backend health
print("Testing backend health...")
try:
    response = requests.get("http://localhost:8000/api/health")
    print(f"Health check: {response.status_code} - {response.json()}")
except Exception as e:
    print(f"Health check failed: {e}")
    exit(1)

# Test auth endpoints without token
print("\nTesting auth endpoints without token...")
try:
    response = requests.post("http://localhost:8000/api/auth/verify")
    print(f"Verify without token: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Verify test failed: {e}")

try:
    response = requests.get("http://localhost:8000/api/auth/me")
    print(f"Get profile without token: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Profile test failed: {e}")

# Test with invalid token
print("\nTesting auth endpoints with invalid token...")
headers = {"Authorization": "Bearer invalid_token"}
try:
    response = requests.post("http://localhost:8000/api/auth/verify", headers=headers)
    print(f"Verify with invalid token: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Invalid token test failed: {e}")

print("\nAuth endpoint tests completed.")