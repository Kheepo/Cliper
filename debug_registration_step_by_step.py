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

def test_registration_steps():
    """Test each step of the registration process individually"""
    print("🧪 Step-by-Step Registration Debug")
    print("=" * 50)
    
    # Get Supabase admin client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not all([supabase_url, supabase_service_key, supabase_anon_key]):
        print("❌ Missing Supabase credentials")
        return
    
    # Create both admin and anon clients
    admin_client: Client = create_client(supabase_url, supabase_service_key)
    anon_client: Client = create_client(supabase_url, supabase_anon_key)
    
    test_email = f"step_test_{uuid.uuid4().hex[:8]}@example.com"
    print(f"📧 Test email: {test_email}")
    
    try:
        # Step 1: Test anon client can check for existing users
        print("\n🔸 Step 1: Testing anon client user existence check...")
        try:
            existing_check = anon_client.table('users').select('id').eq('email', test_email).execute()
            print(f"✅ Anon client can check users table: {len(existing_check.data)} results")
        except Exception as e:
            print(f"❌ Anon client cannot check users table: {e}")
            return
        
        # Step 2: Test admin client can check auth users
        print("\n🔸 Step 2: Testing admin client auth users check...")
        try:
            auth_users = admin_client.auth.admin.list_users()
            existing_auth_user = next((u for u in auth_users if u.email == test_email), None)
            print(f"✅ Admin client can check auth users: {existing_auth_user is None}")
        except Exception as e:
            print(f"❌ Admin client cannot check auth users: {e}")
            return
        
        # Step 3: Test admin client can create auth user
        print("\n🔸 Step 3: Testing admin client auth user creation...")
        try:
            auth_response = admin_client.auth.admin.create_user({
                "email": test_email,
                "password": "TestPassword123!",
                "email_confirm": True
            })
            
            if not auth_response.user:
                print("❌ Auth user creation failed - no user returned")
                return
                
            auth_user = auth_response.user
            print(f"✅ Auth user created: {auth_user.id}")
        except Exception as e:
            print(f"❌ Auth user creation failed: {e}")
            return
        
        # Step 4: Wait and check for auto-created profile
        print("\n🔸 Step 4: Checking for auto-created profile...")
        import time
        time.sleep(1)
        
        try:
            profile_response = admin_client.table("users").select("*").eq("auth_id", auth_user.id).execute()
            
            if not profile_response.data:
                print("❌ No auto-created profile found")
            else:
                user_profile = profile_response.data[0]
                print(f"✅ Auto-created profile found: {user_profile['id']}")
                
                # Step 5: Test profile update with admin client
                print("\n🔸 Step 5: Testing profile update with admin client...")
                try:
                    update_data = {
                        "display_name": "Test User Step",
                        "email_verified": True,
                        "last_login": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    
                    update_response = admin_client.table("users").update(update_data).eq("id", user_profile["id"]).execute()
                    
                    if update_response.data:
                        print(f"✅ Profile updated successfully with admin client")
                    else:
                        print(f"⚠️ Profile update returned no data")
                        
                except Exception as e:
                    print(f"❌ Profile update failed with admin client: {e}")
                
                # Step 6: Test profile update with anon client (this might fail)
                print("\n🔸 Step 6: Testing profile update with anon client...")
                try:
                    update_response = anon_client.table("users").update({"display_name": "Test Anon Update"}).eq("id", user_profile["id"]).execute()
                    
                    if update_response.data:
                        print(f"✅ Profile updated successfully with anon client")
                    else:
                        print(f"⚠️ Profile update with anon client returned no data")
                        
                except Exception as e:
                    print(f"❌ Profile update failed with anon client: {e}")
                    print("   This might be expected - anon users shouldn't update existing profiles")
        
        except Exception as e:
            print(f"❌ Profile check failed: {e}")
        
        # Step 7: Test sign in
        print("\n🔸 Step 7: Testing sign in...")
        try:
            signin_response = admin_client.auth.sign_in_with_password({
                "email": test_email,
                "password": "TestPassword123!"
            })
            
            if signin_response.session:
                print(f"✅ Sign in successful")
            else:
                print(f"❌ Sign in failed - no session")
                
        except Exception as e:
            print(f"❌ Sign in failed: {e}")
        
        # Cleanup
        print("\n🔸 Cleanup: Removing test user...")
        try:
            admin_client.auth.admin.delete_user(auth_user.id)
            print("✅ Test user cleaned up")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_registration_steps()