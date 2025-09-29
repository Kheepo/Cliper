#!/usr/bin/env python3
"""
Cleanup script to remove orphaned auth users that don't have corresponding profiles
This should fix the 'email already exists' registration error
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def cleanup_orphaned_users():
    print("🧹 Cleaning up orphaned auth users")
    print("=" * 50)
    
    # Get credentials directly
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("❌ Missing Supabase credentials")
        return
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("✅ Supabase admin client connected")
        
        # Get all auth users and profile users
        print("\n📋 Getting current users...")
        auth_users = supabase.auth.admin.list_users()
        profile_response = supabase.table('users').select('auth_id').execute()
        profile_auth_ids = {user['auth_id'] for user in profile_response.data if user.get('auth_id')}
        
        print(f"   Total auth users: {len(auth_users)}")
        print(f"   Total profile users: {len(profile_response.data)}")
        
        # Find orphaned users
        orphaned_users = []
        for auth_user in auth_users:
            if auth_user.id not in profile_auth_ids:
                orphaned_users.append(auth_user)
        
        if not orphaned_users:
            print("\n✅ No orphaned users found!")
            return
        
        print(f"\n⚠️  Found {len(orphaned_users)} orphaned auth users:")
        
        # Show what will be deleted
        test_patterns = ['@example.com', '@testdomain.com', 'test@', 'fresh_test_']
        test_orphaned = []
        production_orphaned = []
        
        for user in orphaned_users:
            if any(pattern in user.email for pattern in test_patterns):
                test_orphaned.append(user)
            else:
                production_orphaned.append(user)
        
        if test_orphaned:
            print(f"\n🧪 Test orphaned users to delete ({len(test_orphaned)}):")
            for user in test_orphaned:
                print(f"   - {user.email} (ID: {user.id})")
        
        if production_orphaned:
            print(f"\n⚠️  Production orphaned users found ({len(production_orphaned)}):")
            for user in production_orphaned:
                print(f"   - {user.email} (ID: {user.id})")
            print("   ⚠️  These will NOT be deleted automatically for safety!")
        
        # Delete test orphaned users only
        if test_orphaned:
            print(f"\n🗑️  Deleting {len(test_orphaned)} test orphaned users...")
            deleted_count = 0
            failed_count = 0
            
            for user in test_orphaned:
                try:
                    supabase.auth.admin.delete_user(user.id)
                    print(f"   ✅ Deleted: {user.email}")
                    deleted_count += 1
                except Exception as e:
                    print(f"   ❌ Failed to delete {user.email}: {e}")
                    failed_count += 1
            
            print(f"\n📊 Cleanup Summary:")
            print(f"   ✅ Successfully deleted: {deleted_count}")
            print(f"   ❌ Failed to delete: {failed_count}")
            
            if production_orphaned:
                print(f"   ⚠️  Production users left untouched: {len(production_orphaned)}")
                print("   💡 Review these manually if needed")
        
        else:
            print("\n✅ No test orphaned users to delete")
            
    except Exception as e:
        print(f"❌ Failed to cleanup orphaned users: {e}")
    
    print("\n🎉 Cleanup completed!")
    print("\n💡 Try registration again - the 'email already exists' error should be fixed!")

if __name__ == "__main__":
    cleanup_orphaned_users()