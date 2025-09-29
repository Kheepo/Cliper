import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')
)

# Check auth users
auth_users_response = supabase.auth.admin.list_users()
auth_users = auth_users_response.users if hasattr(auth_users_response, 'users') else auth_users_response

print(f"Total auth users: {len(auth_users)}")

# Find Gmail users
gmail_users = [u for u in auth_users if 'gmail.com' in u.email]
print(f"Gmail auth users: {len(gmail_users)}")

print("\nGmail auth users:")
for user in gmail_users:
    print(f"Email: {user.email}, ID: {user.id}")

# Check if these auth users have corresponding profile users
print("\nChecking profile matches:")
for auth_user in gmail_users:
    profile_result = supabase.table('users').select('id, email').eq('auth_id', auth_user.id).execute()
    if profile_result.data:
        print(f"✓ {auth_user.email} has profile")
    else:
        print(f"✗ {auth_user.email} has NO profile (orphaned auth user)")
        # Clean up orphaned auth user
        try:
            supabase.auth.admin.delete_user(auth_user.id)
            print(f"  → Deleted orphaned auth user: {auth_user.email}")
        except Exception as e:
            print(f"  → Failed to delete {auth_user.email}: {e}")