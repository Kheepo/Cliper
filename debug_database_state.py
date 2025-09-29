#!/usr/bin/env python3
"""
Debug script to check the current state of users in both Supabase Auth and our profile table
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_database_state():
    print("🔍 Database State Debug")
    print("=" * 50)
    
    # Get credentials directly
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    print(f"URL: {SUPABASE_URL}")
    print(f"Service Role Key: {'*' * 20 if SUPABASE_SERVICE_ROLE_KEY else 'NOT SET'}")
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("❌ Missing Supabase credentials")
        return
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("✅ Supabase admin client connected")
        
        # Check Supabase Auth users
        print("\n📋 Supabase Auth Users:")
        try:
            auth_users = supabase.auth.admin.list_users()
            print(f"   Total auth users: {len(auth_users)}")
            
            # Look for test emails specifically
            test_emails = []
            for user in auth_users:
                if any(pattern in user.email for pattern in ['@example.com', '@testdomain.com', 'test@', 'fresh_test_']):
                    test_emails.append(user)
            
            if test_emails:
                print(f"\n   🧪 Found {len(test_emails)} test emails in auth:")
                for user in test_emails:
                    print(f"   - {user.email} (ID: {user.id}, Created: {user.created_at})")
            else:
                print("   ✅ No test emails found in auth")
                
            # Show recent users
            if auth_users:
                print(f"\n   📅 Recent auth users (last 5):")
                for user in auth_users[-5:]:
                    print(f"   - {user.email} (ID: {user.id}, Created: {user.created_at})")
                
        except Exception as e:
            print(f"   ❌ Error getting auth users: {e}")
        
        # Check profile table users
        print("\n👤 Profile Table Users:")
        try:
            profile_response = supabase.table('users').select('*').execute()
            profile_users = profile_response.data
            print(f"   Total profile users: {len(profile_users)}")
            
            # Look for test emails in profiles
            test_profiles = []
            for user in profile_users:
                email = user.get('email', '')
                if any(pattern in email for pattern in ['@example.com', '@testdomain.com', 'test@', 'fresh_test_']):
                    test_profiles.append(user)
            
            if test_profiles:
                print(f"\n   🧪 Found {len(test_profiles)} test emails in profiles:")
                for user in test_profiles:
                    print(f"   - {user.get('email')} (ID: {user['id']}, Auth ID: {user.get('auth_id')})")
            else:
                print("   ✅ No test emails found in profiles")
                
            # Show recent profiles
            if profile_users:
                print(f"\n   📅 Recent profile users (last 5):")
                for user in profile_users[-5:]:
                    print(f"   - {user.get('email')} (ID: {user['id']}, Auth ID: {user.get('auth_id')})")
                
        except Exception as e:
            print(f"   ❌ Error getting profile users: {e}")
        
        # Check for orphaned auth users (auth users without profiles)
        print("\n🔗 Checking for orphaned auth users:")
        try:
            auth_users = supabase.auth.admin.list_users()
            profile_response = supabase.table('users').select('auth_id').execute()
            profile_auth_ids = {user['auth_id'] for user in profile_response.data if user.get('auth_id')}
            
            orphaned_users = []
            for auth_user in auth_users:
                if auth_user.id not in profile_auth_ids:
                    orphaned_users.append(auth_user)
            
            if orphaned_users:
                print(f"   ⚠️  Found {len(orphaned_users)} orphaned auth users:")
                for user in orphaned_users[:10]:  # Show first 10
                    print(f"   - {user.email} (ID: {user.id}, Created: {user.created_at})")
                if len(orphaned_users) > 10:
                    print(f"   ... and {len(orphaned_users) - 10} more")
                    
                print("\n   💡 These orphaned users might be causing the 'email already exists' error!")
            else:
                print("   ✅ No orphaned auth users found")
                
        except Exception as e:
            print(f"   ❌ Error checking for orphaned users: {e}")
            
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
    
    print("\n📝 Debug completed!")

if __name__ == "__main__":
    debug_database_state()