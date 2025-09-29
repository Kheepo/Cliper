import requests
import json
from fastapi.security import HTTPBearer
from fastapi import Request
from starlette.requests import Request as StarletteRequest
from starlette.datastructures import Headers
import asyncio

# Test HTTPBearer directly
async def test_httpbearer_extraction():
    print("Testing HTTPBearer token extraction...")
    
    # First, register a test user
    register_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "display_name": "Test User"
    }
    
    try:
        print("Registering test user...")
        response = requests.post("http://localhost:8001/api/auth/register", json=register_data)
        print(f"Registration response status: {response.status_code}")
        
        if response.status_code == 201:
            print("Registration successful")
        elif response.status_code == 400 and "already exists" in response.text:
            print("User already exists, proceeding with login")
        else:
            print(f"Registration failed: {response.text}")
        
        # Now try to login
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        print("\nAttempting login...")
        response = requests.post("http://localhost:8001/api/auth/login", json=login_data)
        print(f"Login response status: {response.status_code}")
        print(f"Login response: {response.text}")
        
        if response.status_code == 200:
            login_result = response.json()
            # Check if tokens are nested in the response
            if 'tokens' in login_result:
                access_token = login_result['tokens'].get('access_token')
            else:
                access_token = login_result.get('access_token')
            
            if not access_token:
                print(f"No access token in response: {login_result}")
                return
            print(f"Got access token: {access_token[:50]}...")
            
            # Create a mock request with the token
            headers = Headers({
                "authorization": f"Bearer {access_token}",
                "content-type": "application/json"
            })
            
            # Create a mock request object
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/api/auth/me",
                "headers": [(b"authorization", f"Bearer {access_token}".encode())]
            }
            
            request = StarletteRequest(scope)
            
            # Test HTTPBearer directly
            print("\nTesting HTTPBearer extraction...")
            security = HTTPBearer(auto_error=False)
            credentials = await security(request)
            
            print(f"HTTPBearer extracted credentials: {credentials}")
            if credentials:
                print(f"Token from HTTPBearer: {credentials.credentials[:50]}...")
                print(f"Scheme: {credentials.scheme}")
                
                # Test if the token matches
                if credentials.credentials == access_token:
                    print("✓ Token extraction successful!")
                else:
                    print("✗ Token mismatch!")
            else:
                print("HTTPBearer returned None - token extraction failed!")
                
                # Check the raw headers
                print(f"Raw headers: {dict(request.headers)}")
                auth_header = request.headers.get('authorization')
                print(f"Authorization header: {auth_header}")
                
            # Also test a real API call
            print("\nTesting real API call with token...")
            headers = {"Authorization": f"Bearer {access_token}"}
            me_response = requests.get("http://localhost:8001/api/auth/me", headers=headers)
            print(f"API call status: {me_response.status_code}")
            if me_response.status_code != 200:
                print(f"API call failed: {me_response.text}")
            else:
                print("API call successful!")
                
        else:
            print(f"Login failed: {response.text}")
            
    except Exception as e:
        print(f"Error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_httpbearer_extraction())