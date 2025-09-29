import os
import sys
from datetime import datetime
import uuid

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.config import get_supabase_admin_client

# Initialize Supabase admin client (needed for user creation)
supabase = get_supabase_admin_client()

print("🔍 Found the issue! There's an automatic trigger creating user profiles.")
print("Let's test the corrected registration flow...")

# Generate a test email
test_email = f"corrected_test_{uuid.uuid4().hex[:8]}@example.com"
print(f"\n🧪 Using test email: {test_email}")

try:
    # Step 1: Create auth user (this will automatically create the profile)
    print("\n🔸 Step 1: Creating auth user (profile will be auto-created)...")
    auth_response = supabase.auth.admin.create_user({
        "email": test_email,
        "password": "testpassword123",
        "email_confirm": True
    })
    auth_user_id = auth_response.user.id
    print(f"✅ Auth user created: {auth_user_id}")
    
    # Step 2: Check if profile was auto-created
    print("\n🔸 Step 2: Checking if profile was auto-created...")
    profile_check = supabase.table('users').select('*').eq('email', test_email).execute()
    
    if profile_check.data:
        profile = profile_check.data[0]
        print(f"✅ Profile auto-created: {profile['id']}")
        print(f"   Email: {profile['email']}")
        print(f"   Auth ID: {profile['auth_id']}")
        print(f"   Display Name: {profile['display_name']}")
        print(f"   Role: {profile['role']}")
        
        # Step 3: Update profile if needed (instead of creating)
        print("\n🔸 Step 3: Updating profile with additional data...")
        update_data = {
            "display_name": test_email.split('@')[0],
            "email_verified": True,
            "last_login": datetime.now().isoformat()
        }
        
        update_response = supabase.table('users').update(update_data).eq('id', profile['id']).execute()
        print(f"✅ Profile updated: {update_response.data[0]['id']}")
        
        # Step 4: Test sign in
        print("\n🔸 Step 4: Testing sign in...")
        signin_response = supabase.auth.sign_in_with_password({
            "email": test_email,
            "password": "testpassword123"
        })
        
        if signin_response.session:
            print(f"✅ Sign in successful")
            print(f"   Access token: {signin_response.session.access_token[:20]}...")
            print(f"   User ID: {signin_response.user.id}")
        else:
            print("❌ Sign in failed")
        
        print("\n🎉 Corrected registration flow completed successfully!")
        print(f"   Auth ID: {auth_user_id}")
        print(f"   Profile ID: {profile['id']}")
        print(f"   Email: {test_email}")
        
    else:
        print("❌ No profile was auto-created - this is unexpected!")
    
except Exception as e:
    print(f"\n❌ Registration flow failed: {e}")
    print(f"   Error type: {type(e).__name__}")
    
    # Cleanup on failure
    if 'auth_user_id' in locals():
        print(f"\n🧹 Cleaning up auth user {auth_user_id}...")
        try:
            supabase.auth.admin.delete_user(auth_user_id)
            print("✅ Cleanup successful")
        except Exception as cleanup_error:
            print(f"❌ Cleanup failed: {cleanup_error}")

print("\n📝 Summary:")
print("   - Supabase has an automatic trigger that creates user profiles")
print("   - The backend registration endpoint should NOT manually create profiles")
print("   - Instead, it should just create the auth user and optionally update the auto-created profile")
print("   - This explains the 'User not allowed' error in the original registration flow")