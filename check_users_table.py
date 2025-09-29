import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')
)

# Check current users in the table
result = supabase.table('users').select('id, email, auth_id').execute()

print(f"Current users count: {len(result.data)}")
print("\nUsers in table:")
for user in result.data:
    print(f"Email: {user['email']}, Auth ID: {user['auth_id']}")

# Clean up any test users
test_emails = [user for user in result.data if '@gmail.com' in user['email'] and ('test_' in user['email'] or 'user_' in user['email'])]
if test_emails:
    print(f"\nFound {len(test_emails)} test users to clean up")
    for user in test_emails:
        try:
            delete_result = supabase.table('users').delete().eq('id', user['id']).execute()
            print(f"Deleted user: {user['email']}")
        except Exception as e:
            print(f"Failed to delete {user['email']}: {e}")
else:
    print("\nNo test users found to clean up")