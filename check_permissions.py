from database.config import get_supabase_admin_client
import json

def check_permissions():
    """Check permissions and RLS policies for the users table"""
    
    supabase = get_supabase_admin_client()
    
    print("🔍 Checking permissions for users table...")
    print("=" * 50)
    
    # Check table permissions
    print("\n📋 Table Permissions:")
    try:
        permissions_query = """
        SELECT 
            grantee, 
            table_name, 
            privilege_type 
        FROM information_schema.role_table_grants 
        WHERE table_schema = 'public' 
            AND table_name = 'users'
            AND grantee IN ('anon', 'authenticated') 
        ORDER BY table_name, grantee;
        """
        
        result = supabase.rpc('exec_sql', {'sql': permissions_query}).execute()
        if result.data:
            for row in result.data:
                print(f"   {row['grantee']}: {row['privilege_type']} on {row['table_name']}")
        else:
            print("   ❌ No permissions found for anon/authenticated roles")
            
    except Exception as e:
        print(f"   ❌ Error checking permissions: {e}")
    
    # Check RLS policies
    print("\n🛡️ RLS Policies:")
    try:
        policies_query = """
        SELECT 
            schemaname,
            tablename,
            policyname,
            permissive,
            roles,
            cmd,
            qual,
            with_check
        FROM pg_policies 
        WHERE schemaname = 'public' 
            AND tablename = 'users';
        """
        
        result = supabase.rpc('exec_sql', {'sql': policies_query}).execute()
        if result.data:
            for policy in result.data:
                print(f"   Policy: {policy['policyname']}")
                print(f"     Command: {policy['cmd']}")
                print(f"     Roles: {policy['roles']}")
                print(f"     Condition: {policy['qual']}")
                print(f"     With Check: {policy['with_check']}")
                print()
        else:
            print("   ❌ No RLS policies found")
            
    except Exception as e:
        print(f"   ❌ Error checking RLS policies: {e}")
    
    # Check if RLS is enabled
    print("\n🔒 RLS Status:")
    try:
        rls_query = """
        SELECT 
            schemaname,
            tablename,
            rowsecurity,
            forcerowsecurity
        FROM pg_tables 
        WHERE schemaname = 'public' 
            AND tablename = 'users';
        """
        
        result = supabase.rpc('exec_sql', {'sql': rls_query}).execute()
        if result.data:
            for table in result.data:
                print(f"   Table: {table['tablename']}")
                print(f"   RLS Enabled: {table['rowsecurity']}")
                print(f"   RLS Forced: {table['forcerowsecurity']}")
        else:
            print("   ❌ Could not check RLS status")
            
    except Exception as e:
        print(f"   ❌ Error checking RLS status: {e}")

if __name__ == "__main__":
    check_permissions()