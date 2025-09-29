import os
from dotenv import load_dotenv
from supabase import create_client, Client
import time
import uuid

# Load environment variables
load_dotenv()

def get_supabase_admin_client():
    """Get Supabase admin client"""
    url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not service_role_key:
        raise Exception("Missing Supabase URL or service role key")
    
    return create_client(url, service_role_key)

def test_registration_steps():
    """Test each step of the registration process separately"""
    
    print("🔍 Testing Registration Steps Separately")
    print("========================================")
    
    try:
        supabase = get_supabase_admin_client()
        print("✅ Supabase admin client created")
        
        # Step 1: Create auth user
        test_email = f"steptest_{uuid.uuid4().hex[:8]}@example.com"
        test_password = "testpassword123"
        
        print(f"\n🔸 Step 1: Creating auth user with email: {test_email}")
        
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
        
        # Step 2: Wait for trigger and check profile creation
        print("\n🔸 Step 2: Waiting for trigger to create profile...")
        time.sleep(1.0)  # Wait longer
        
        profile_response = supabase.table("users").select("*").eq("auth_id", auth_user.id).execute()
        
        if not profile_response.data:
            print("❌ Auto-created profile not found")
            print("   Trigger might not be working or needs more time")
            
            # Try manual profile creation
            print("\n🔸 Step 2b: Trying manual profile creation...")
            manual_profile_data = {
                "auth_id": auth_user.id,
                "email": test_email,
                "display_name": test_email.split('@')[0],
                "is_active": True,
                "email_verified": True
            }
            
            try:
                manual_response = supabase.table("users").insert(manual_profile_data).execute()
                if manual_response.data:
                    print(f"✅ Manual profile created: {manual_response.data[0]['id']}")
                    user_profile = manual_response.data[0]
                else:
                    print("❌ Manual profile creation failed")
                    return
            except Exception as manual_error:
                print(f"❌ Manual profile creation error: {manual_error}")
                return
        else:
            user_profile = profile_response.data[0]
            print(f"✅ Auto-created profile found: {user_profile['id']}")
        
        # Step 3: Try to update the profile (this might be where the error occurs)
        print("\n🔸 Step 3: Updating profile with additional data...")
        
        update_data = {
            "display_name": test_email.split('@')[0],
            "email_verified": True,
            "last_login": "2025-09-21T21:50:00.000Z",
            "updated_at": "2025-09-21T21:50:00.000Z"
        }
        
        try:
            update_response = supabase.table("users").update(update_data).eq("id", user_profile["id"]).execute()
            
            if update_response.data:
                print(f"✅ Profile updated successfully: {update_response.data[0]['id']}")
                user_profile = update_response.data[0]
            else:
                print("⚠️ Profile update returned no data")
                
        except Exception as update_error:
            print(f"❌ Profile update failed: {update_error}")
            print(f"   This might be the source of 'User not allowed' error")
            
            # Check if it's a permissions issue
            if "not allowed" in str(update_error).lower():
                print("   🔍 This appears to be a permissions/RLS issue")
                
                # Try to check current user permissions
                print("\n🔸 Step 3b: Checking table permissions...")
                try:
                    # Try a simple select to see if we can read
                    read_test = supabase.table("users").select("id").eq("id", user_profile["id"]).execute()
                    print(f"   ✅ Can read profile: {len(read_test.data)} records")
                except Exception as read_error:
                    print(f"   ❌ Cannot read profile: {read_error}")
            
            return
        
        # Step 4: Test sign in
        print("\n🔸 Step 4: Testing sign in...")
        
        try:
            signin_response = supabase.auth.sign_in_with_password({
                "email": test_email,
                "password": test_password
            })
            
            if signin_response.session:
                print(f"✅ Sign in successful: {signin_response.user.id}")
            else:
                print("❌ Sign in failed")
                
        except Exception as signin_error:
            print(f"❌ Sign in error: {signin_error}")
        
        print("\n🔸 Step 5: Cleanup - deleting test user...")
        try:
            supabase.auth.admin.delete_user(auth_user.id)
            print("✅ Test user cleaned up")
        except Exception as cleanup_error:
            print(f"⚠️ Cleanup warning: {cleanup_error}")
        
    except Exception as e:
        print(f"❌ Test setup error: {e}")

if __name__ == "__main__":
    test_registration_steps()
    print("\n📝 Registration steps test completed!")