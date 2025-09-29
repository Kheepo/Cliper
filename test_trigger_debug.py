import requests
import json
import time
import os
from dotenv import load_dotenv
load_dotenv()
from api.utils.supabase_client import get_supabase_admin_client
import uuid

# Debug environment variables
print(f"Debug - SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
print(f"Debug - SUPABASE_SERVICE_ROLE_KEY: {'Present' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else 'Missing'}")
print(f"Debug - Current working directory: {os.getcwd()}")
print(f"Debug - .env file exists: {os.path.exists('.env')}")
print()

def test_trigger_and_profile_creation():
    """Test the database trigger and profile creation process"""
    
    print("🧪 Testing Database Trigger and Profile Creation")
    print("================================================")
    
    supabase = get_supabase_admin_client()
    if not supabase:
        print("❌ Failed to get Supabase admin client")
        return
    
    # Generate unique test email
    test_id = str(uuid.uuid4())[:8]
    test_email = f"trigger_test_{test_id}@example.com"
    test_password = "testpassword123"
    
    print(f"🔸 Testing with email: {test_email}")
    
    auth_user = None
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
        
        # Step 2: Check if profile was auto-created immediately
        print("\n🔸 Step 2: Checking for auto-created profile (immediate)...")
        profile_response = supabase.table("users").select("*").eq("auth_id", auth_user.id).execute()
        
        if profile_response.data:
            print(f"✅ Profile auto-created immediately: {profile_response.data[0]['id']}")
            user_profile = profile_response.data[0]
        else:
            print("⚠️  Profile not created immediately, waiting 1 second...")
            time.sleep(1)
            
            # Step 3: Check again after delay
            print("\n🔸 Step 3: Checking for auto-created profile (after delay)...")
            profile_response = supabase.table("users").select("*").eq("auth_id", auth_user.id).execute()
            
            if profile_response.data:
                print(f"✅ Profile auto-created after delay: {profile_response.data[0]['id']}")
                user_profile = profile_response.data[0]
            else:
                print("❌ Profile was not auto-created by trigger")
                print("🔧 Attempting manual profile creation...")
                
                # Step 4: Try manual profile creation
                manual_profile = {
                    "auth_id": auth_user.id,
                    "email": test_email,
                    "display_name": f"Test User {test_id}",
                    "is_active": True,
                    "email_verified": True,
                    "role": "user"
                }
                
                try:
                    manual_response = supabase.table("users").insert(manual_profile).execute()
                    if manual_response.data:
                        print(f"✅ Manual profile creation successful: {manual_response.data[0]['id']}")
                        user_profile = manual_response.data[0]
                    else:
                        print("❌ Manual profile creation failed - no data returned")
                        return
                except Exception as manual_error:
                    print(f"❌ Manual profile creation failed: {manual_error}")
                    return
        
        # Step 5: Test profile update
        print("\n🔸 Step 5: Testing profile update...")
        update_data = {
            "display_name": f"Updated Test User {test_id}",
            "last_login": "2024-01-01T00:00:00Z"
        }
        
        try:
            update_response = supabase.table("users").update(update_data).eq("id", user_profile["id"]).execute()
            if update_response.data:
                print(f"✅ Profile update successful")
                print(f"   Updated display name: {update_response.data[0]['display_name']}")
            else:
                print("❌ Profile update failed - no data returned")
        except Exception as update_error:
            print(f"❌ Profile update failed: {update_error}")
        
        # Step 6: Test sign in
        print("\n🔸 Step 6: Testing sign in...")
        try:
            signin_response = supabase.auth.sign_in_with_password({
                "email": test_email,
                "password": test_password
            })
            
            if signin_response.session:
                print(f"✅ Sign in successful")
                print(f"   Access token: {signin_response.session.access_token[:20]}...")
            else:
                print("❌ Sign in failed - no session")
        except Exception as signin_error:
            print(f"❌ Sign in failed: {signin_error}")
        
    except Exception as e:
        print(f"❌ Test error: {e}")
    
    finally:
        # Cleanup: delete the test user
        if auth_user:
            try:
                print(f"\n🧹 Cleaning up test user {auth_user.id}...")
                supabase.auth.admin.delete_user(auth_user.id)
                print("✅ Test user cleaned up")
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup failed: {cleanup_error}")

if __name__ == "__main__":
    test_trigger_and_profile_creation()
    print("\n📝 Trigger test completed!")