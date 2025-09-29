#!/usr/bin/env python3
"""
Create a test user for video upload testing
"""

import requests
import json
from datetime import datetime

# Supabase configuration
SUPABASE_URL = "https://stzdywhbdovjojtqxmsd.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0emR5d2hiZG92am9qdHF4bXNkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzU0MDU2OCwiZXhwIjoyMDczMTE2NTY4fQ.Xg6iDR-YMjID73OzQfJ362B-xYBadJeb6Qh2NxVtAmU"

def create_test_user():
    """Create a test user account"""
    print("🚀 Creating test user for video upload testing")
    
    # User data
    user_data = {
        "email": "test.upload@example.com",
        "password": "TestUpload123!",
        "email_confirm": True,
        "user_metadata": {
            "full_name": "Upload Test User",
            "role": "user"
        }
    }
    
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "apikey": SUPABASE_SERVICE_KEY
    }
    
    try:
        # Create user via Supabase Auth Admin API
        response = requests.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=headers,
            json=user_data,
            timeout=10
        )
        
        if response.status_code == 200:
            user = response.json()
            print(f"✅ Test user created successfully!")
            print(f"   User ID: {user['id']}")
            print(f"   Email: {user['email']}")
            
            # Now sign in to get access token
            print("\n🔑 Signing in to get access token...")
            signin_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }
            
            signin_response = requests.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers={
                    "Content-Type": "application/json",
                    "apikey": SUPABASE_SERVICE_KEY
                },
                json=signin_data,
                timeout=10
            )
            
            if signin_response.status_code == 200:
                tokens = signin_response.json()
                access_token = tokens['access_token']
                print(f"✅ Sign in successful!")
                print(f"   Access Token: {access_token[:50]}...")
                
                # Save credentials for testing
                test_credentials = {
                    "user_id": user['id'],
                    "email": user['email'],
                    "access_token": access_token,
                    "created_at": datetime.now().isoformat()
                }
                
                with open("test_user_credentials.json", "w") as f:
                    json.dump(test_credentials, f, indent=2)
                
                print("\n📝 Credentials saved to test_user_credentials.json")
                print("\nUse these credentials for upload testing:")
                print(f"   Authorization: Bearer {access_token}")
                
                return access_token
            else:
                print(f"❌ Sign in failed: {signin_response.status_code}")
                print(f"   Response: {signin_response.text}")
                return None
                
        else:
            print(f"❌ User creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        return None

if __name__ == "__main__":
    access_token = create_test_user()
    if access_token:
        print("\n🎉 Test user setup completed successfully!")
        print("You can now use the access token for video upload testing.")
    else:
        print("\n❌ Test user setup failed.")