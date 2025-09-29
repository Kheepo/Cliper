import json
import requests
from supabase import create_client

# Load configurations
with open('supabase_config.json', 'r') as f:
    config = json.load(f)

with open('test_user_credentials.json', 'r') as f:
    user_data = json.load(f)

# Test direct job creation
print("🔍 Testing direct job creation in Supabase...")

# Create Supabase client with service role
supabase = create_client(config['url'], config['service_role_key'])

# Get user ID from users table
user_id = user_data['user_id']
print(f"Auth ID: {user_id}")

try:
    # Look up user in users table
    user_result = supabase.table("users").select("id").eq("auth_id", user_id).execute()
    if not user_result.data:
        print("❌ User not found in users table")
        exit(1)
    
    db_user_id = user_result.data[0]["id"]
    print(f"✅ Found user in DB with ID: {db_user_id}")
    
    # Test job creation
    job_data = {
        "user_id": db_user_id,
        "job_type": "upload",
        "status": "completed",
        "title": "Test Upload",
        "description": "Debug test upload",
        "video_filename": "test.mp4",
        "video_url": "https://example.com/test.mp4",
        "video_size": 1024
    }
    
    print("📝 Attempting to create job record...")
    print(f"Job data: {json.dumps(job_data, indent=2)}")
    
    result = supabase.table("jobs").insert(job_data).execute()
    
    if result.data:
        job_id = result.data[0]["id"]
        print(f"✅ Job created successfully with ID: {job_id}")
        
        # Clean up - delete the test job
        cleanup_result = supabase.table("jobs").delete().eq("id", job_id).execute()
        print(f"🧹 Cleanup: {len(cleanup_result.data)} job(s) deleted")
    else:
        print("❌ Job creation failed - no data returned")
        print(f"Result: {result}")
        
except Exception as e:
    print(f"❌ Error during job creation: {e}")
    print(f"Error type: {type(e)}")
    
    # Additional debugging
    if hasattr(e, 'details'):
        print(f"Error details: {e.details}")
    if hasattr(e, 'message'):
        print(f"Error message: {e.message}")

print("\n🔍 Testing authenticated API call...")

# Test the actual API endpoint with authentication
headers = {
    'Authorization': f'Bearer {user_data["access_token"]}',
    'Content-Type': 'application/json'
}

try:
    # Test a simple authenticated endpoint first
    response = requests.get('http://localhost:8000/api/health', headers=headers)
    print(f"Health check with auth: {response.status_code} - {response.text}")
except Exception as e:
    print(f"❌ Error testing authenticated health endpoint: {e}")