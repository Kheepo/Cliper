import json
import requests
from supabase import create_client, Client

# Load Supabase configuration
with open('supabase_config.json', 'r') as f:
    config = json.load(f)

url = config['url']
service_role_key = config['service_role_key']

# Create Supabase client with service role key for admin operations
supabase: Client = create_client(url, service_role_key)

# Load test user credentials
with open('test_user_credentials.json', 'r') as f:
    user_data = json.load(f)

user_id = user_data['user_id']
email = user_data['email']

print(f"Creating user record for {email} with auth_id {user_id}")

try:
    # Insert user into public.users table
    result = supabase.table('users').insert({
        'auth_id': user_id,
        'email': email,
        'display_name': 'Test User',
        'is_active': True,
        'email_verified': True,
        'role': 'user'
    }).execute()
    
    print("User record created successfully:")
    print(json.dumps(result.data, indent=2))
    
except Exception as e:
    print(f"Error creating user record: {e}")
    # Check if user already exists
    try:
        existing_user = supabase.table('users').select('*').eq('auth_id', user_id).execute()
        if existing_user.data:
            print("User already exists in users table:")
            print(json.dumps(existing_user.data, indent=2))
        else:
            print("User does not exist in users table")
    except Exception as check_error:
        print(f"Error checking existing user: {check_error}")