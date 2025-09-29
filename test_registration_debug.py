import requests
import json
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import uuid

# Load environment variables
load_dotenv()

# Test registration with a completely new email
test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
test_password = "TestPassword123!"

print(f"Testing registration with email: {test_email}")

# Test the registration endpoint
registration_data = {
    "email": test_email,
    "password": test_password
}

try:
    response = requests.post(
        "http://localhost:8001/api/auth/register",
        json=registration_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    
    if response.text:
        try:
            response_json = response.json()
            print(f"Response JSON: {json.dumps(response_json, indent=2)}")
        except:
            print(f"Response Text: {response.text}")
    else:
        print("Empty response body")
        
except Exception as e:
    print(f"Request failed: {e}")

# Also test if we can connect to Supabase directly
print("\n--- Testing Supabase Connection ---")
try:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("Missing Supabase credentials")
    else:
        supabase: Client = create_client(supabase_url, supabase_service_key)
        
        # Test creating a user in auth
        print("Testing auth user creation...")
        auth_response = supabase.auth.admin.create_user({
            "email": f"direct_test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestPassword123!",
            "email_confirm": True
        })
        
        if auth_response.user:
            print(f"Auth user created successfully: {auth_response.user.id}")
            print(f"Auth user ID type: {type(auth_response.user.id)}")
            print(f"Auth user ID value: {repr(auth_response.user.id)}")
            
            # Test inserting into users table
            print("Testing users table insert...")
            user_data = {
                "auth_id": auth_response.user.id,
                "email": auth_response.user.email,
                "display_name": "Test User",
                "is_active": True,
                "email_verified": True,
                "role": "user"
            }
            
            try:
                profile_response = supabase.table("users").insert(user_data).execute()
                print(f"Profile created successfully: {profile_response.data}")
                
                # Cleanup
                supabase.auth.admin.delete_user(auth_response.user.id)
                print("Cleanup completed")
                
            except Exception as profile_error:
                print(f"Profile creation failed: {profile_error}")
                # Still try to cleanup auth user
                try:
                    supabase.auth.admin.delete_user(auth_response.user.id)
                except:
                    pass
        else:
            print("Failed to create auth user")
            
except Exception as e:
    print(f"Supabase test failed: {e}")