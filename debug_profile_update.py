import requests
import json
import uuid
from datetime import datetime
import os
from supabase import create_client, Client

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

BASE_URL = "http://localhost:8001"

def test_profile_update():
    """Test the profile update operation that's failing during registration"""
    print("🧪 Testing Profile Update Operation")
    print("=" * 50)
    
    # Get Supabase admin client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("❌ Missing Supabase credentials")
        return
    
    supabase: Client = create_client(supabase_url, supabase_service_key)
    
    # First, let's try to create a test auth user
    test_email = f"profile_test_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "TestPassword123!"
    
    print(f"📧 Test email: {test_email}")
    
    try:
        # Step 1: Create auth user
        print("\n🔸 Step 1: Creating auth user...")
        auth_response = supabase.auth.admin.create_user({
            "email": test_email,
            "password": test_password,
            "email_confirm": True
        })
        
        if not auth_response.user:
            print("❌ Failed to create auth user")
            return
            
        auth_user = auth_response.user
        print(f"✅ Auth user created: {auth_user.id}")
        
        # Step 2: Wait for auto-profile creation
        print("\n🔸 Step 2: Waiting for auto-profile creation...")
        import time
        time.sleep(1)
        
        # Step 3: Check if profile was auto-created
        print("\n🔸 Step 3: Checking for auto-created profile...")
        profile_response = supabase.table("users").select("*").eq("auth_id", auth_user.id).execute()
        
        if not profile_response.data:
            print("❌ No auto-created profile found")
            # Cleanup
            supabase.auth.admin.delete_user(auth_user.id)
            return
            
        user_profile = profile_response.data[0]
        print(f"✅ Auto-created profile found: {user_profile['id']}")
        print(f"   Profile data: {json.dumps(user_profile, indent=2, default=str)}")
        
        # Step 4: Try to update the profile (this is where the error occurs)
        print("\n🔸 Step 4: Attempting profile update...")
        update_data = {
            "display_name": "Test User Profile",
            "email_verified": True,
            "last_login": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        print(f"   Update data: {json.dumps(update_data, indent=2)}")
        
        try:
            update_response = supabase.table("users").update(update_data).eq("id", user_profile["id"]).execute()
            
            if update_response.data:
                print(f"✅ Profile updated successfully: {json.dumps(update_response.data[0], indent=2, default=str)}")
            else:
                print(f"⚠️ Update returned no data. Response: {update_response}")
                
        except Exception as update_error:
            print(f"❌ Profile update failed: {update_error}")
            print(f"   Error type: {type(update_error)}")
            print(f"   Error details: {str(update_error)}")
        
        # Cleanup
        print("\n🔸 Step 5: Cleaning up...")
        supabase.auth.admin.delete_user(auth_user.id)
        print("✅ Cleanup completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"   Error type: {type(e)}")

if __name__ == "__main__":
    test_profile_update()