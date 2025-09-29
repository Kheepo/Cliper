#!/usr/bin/env python3
"""
Test analytics endpoints with authentication simulation.
"""

import requests
import json
from datetime import datetime

def test_analytics_with_mock_auth():
    """Test analytics endpoints with mock authentication headers."""
    base_url = "http://localhost:8000"
    
    # Mock JWT token (this won't work with real auth, but let's see the response)
    mock_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQiLCJlbWFpbCI6InRlc3RAdGVzdC5jb20iLCJleHAiOjk5OTk5OTk5OTksImlhdCI6MTYwMDAwMDAwMCwiYXVkIjoiYXV0aGVudGljYXRlZCJ9.test"
    
    headers = {
        "Authorization": f"Bearer {mock_token}",
        "Content-Type": "application/json"
    }
    
    endpoints = [
        "/api/health",
        "/api/analytics/jobs", 
        "/api/analytics/user",
        "/analytics/jobs",
        "/analytics/user"
    ]
    
    print("Testing Analytics Endpoints with Mock Auth")
    print("=" * 50)
    
    for endpoint in endpoints:
        try:
            print(f"\nTesting: {base_url}{endpoint}")
            
            if endpoint == "/api/health":
                # Health endpoint doesn't need auth
                response = requests.get(f"{base_url}{endpoint}", timeout=10)
            else:
                # Analytics endpoints need auth
                response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Success: {json.dumps(data, indent=2)[:200]}...")
                except:
                    print(f"Success: {response.text[:200]}...")
            else:
                try:
                    error_data = response.json()
                    print(f"Error: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"Error: {response.text}")
                    
        except requests.exceptions.Timeout:
            print("Timeout Error")
        except requests.exceptions.ConnectionError:
            print("Connection Error")
        except Exception as e:
            print(f"Unexpected Error: {e}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    test_analytics_with_mock_auth()