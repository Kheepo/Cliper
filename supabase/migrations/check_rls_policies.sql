-- Check and fix RLS policies for user tables

-- First, let's see what RLS policies currently exist
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
AND tablename IN ('users', 'user_settings', 'user_preferences')
ORDER BY tablename, policyname;

-- Check current permissions for anon and authenticated roles
SELECT 
    grantee,
    table_name,
    privilege_type
FROM information_schema.role_table_grants 
WHERE table_schema = 'public' 
AND table_name IN ('users', 'user_settings', 'user_preferences')
AND grantee IN ('anon', 'authenticated')
ORDER BY table_name, grantee;

-- Drop existing policies if they exist (to recreate them properly)
DROP POLICY IF EXISTS "Users can insert their own profile" ON users;
DROP POLICY IF EXISTS "Users can view their own profile" ON users;
DROP POLICY IF EXISTS "Users can update their own profile" ON users;
DROP POLICY IF EXISTS "Allow anon to insert users" ON users;
DROP POLICY IF EXISTS "Allow authenticated to read own user" ON users;
DROP POLICY IF EXISTS "Allow authenticated to update own user" ON users;

-- Create proper RLS policies for users table
-- Allow anonymous users to insert (for registration)
CREATE POLICY "Allow anon to insert users" ON users
    FOR INSERT
    TO anon
    WITH CHECK (true);

-- Allow authenticated users to read their own data
CREATE POLICY "Allow authenticated to read own user" ON users
    FOR SELECT
    TO authenticated
    USING (auth.uid() = auth_id);

-- Allow authenticated users to update their own data
CREATE POLICY "Allow authenticated to update own user" ON users
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = auth_id)
    WITH CHECK (auth.uid() = auth_id);

-- Similar policies for user_settings
DROP POLICY IF EXISTS "Users can manage their own settings" ON user_settings;
DROP POLICY IF EXISTS "Allow authenticated to manage own settings" ON user_settings;

CREATE POLICY "Allow authenticated to manage own settings" ON user_settings
    FOR ALL
    TO authenticated
    USING (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id))
    WITH CHECK (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

-- Similar policies for user_preferences
DROP POLICY IF EXISTS "Users can manage their own preferences" ON user_preferences;
DROP POLICY IF EXISTS "Allow authenticated to manage own preferences" ON user_preferences;

CREATE POLICY "Allow authenticated to manage own preferences" ON user_preferences
    FOR ALL
    TO authenticated
    USING (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id))
    WITH CHECK (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

-- Ensure RLS is enabled on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Grant necessary table-level permissions
GRANT INSERT ON users TO anon;
GRANT SELECT, UPDATE ON users TO authenticated;
GRANT ALL ON user_settings TO authenticated;
GRANT ALL ON user_preferences TO authenticated;

-- Verify the policies were created
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd
FROM pg_policies 
WHERE schemaname = 'public' 
AND tablename IN ('users', 'user_settings', 'user_preferences')
ORDER BY tablename, policyname;

-- Verify permissions
SELECT 
    grantee,
    table_name,
    privilege_type
FROM information_schema.role_table_grants 
WHERE table_schema = 'public' 
AND table_name IN ('users', 'user_settings', 'user_preferences')
AND grantee IN ('anon', 'authenticated')
ORDER BY table_name, grantee;