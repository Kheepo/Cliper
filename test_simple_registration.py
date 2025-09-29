import requests
import json
import uuid

# Test with a completely unique email
test_email = f"unique_{uuid.uuid4()}@newdomain.test"
test_password = "TestPassword123!"

print(f"Testing registration with unique email: {test_email}")

# Test the registration endpoint
registration_data = {
    "email": test_email,
    "password": test_password
}

try:
    response = requests.post(
        "http://localhost:8001/api/auth/register",
        json=registration_data,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.text:
        try:
            response_json = response.json()
            print(f"Response JSON: {json.dumps(response_json, indent=2)}")
            
            # If registration was successful, test login
            if response.status_code == 200 and 'tokens' in response_json:
                print("\n--- Testing Login ---")
                login_response = requests.post(
                    "http://localhost:8001/api/auth/login",
                    json={"email": test_email, "password": test_password},
                    headers={"Content-Type": "application/json"}
                )
                print(f"Login Status: {login_response.status_code}")
                if login_response.text:
                    try:
                        login_json = login_response.json()
                        print(f"Login Response: {json.dumps(login_json, indent=2)}")
                    except:
                        print(f"Login Response Text: {login_response.text}")
                        
        except Exception as json_error:
            print(f"Response Text: {response.text}")
            print(f"JSON Parse Error: {json_error}")
    else:
        print("Empty response body")
        
except Exception as e:
    print(f"Request failed: {e}")