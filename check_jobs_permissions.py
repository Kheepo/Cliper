import json
from supabase import create_client

# Load Supabase configuration
with open('supabase_config.json', 'r') as f:
    config = json.load(f)

client = create_client(config['url'], config['service_role_key'])

# Check permissions for jobs table
try:
    result = client.rpc('exec_sql', {
        'sql': "SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants WHERE table_schema = 'public' AND table_name = 'jobs' AND grantee IN ('anon', 'authenticated') ORDER BY table_name, grantee;"
    }).execute()
    
    print("Jobs table permissions:")
    if result.data:
        for perm in result.data:
            print(f"  {perm['grantee']}: {perm['privilege_type']}")
    else:
        print("  No permissions found for anon/authenticated roles")
        
except Exception as e:
    print(f"Error checking permissions: {e}")
    
    # Try alternative approach - check if we can insert directly
    print("\nTrying direct insert test...")
    try:
        # Test with service role (should work)
        test_result = client.table('jobs').select('id').limit(1).execute()
        print(f"Service role can read jobs table: {len(test_result.data) >= 0}")
    except Exception as read_error:
        print(f"Service role cannot read jobs table: {read_error}")