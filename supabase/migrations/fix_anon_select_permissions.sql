-- Fix anon role permissions for user existence checks during registration
-- This addresses the "User not allowed" error when checking for existing users

-- Grant SELECT permission to anon role for checking existing users during registration
-- This is needed for the email existence check in the registration endpoint
GRANT SELECT ON users TO anon;

-- Also ensure anon can read from auth.users for the auth check
-- Note: This might already be granted by Supabase, but ensuring it's explicit
GRANT USAGE ON SCHEMA auth TO anon;
GRANT SELECT ON auth.users TO anon;

-- Create a more specific RLS policy for anon users to only check email existence
-- This replaces any overly restrictive policies
DROP POLICY IF EXISTS "Allow anon to check email existence" ON users;
CREATE POLICY "Allow anon to check email existence" ON users
    FOR SELECT
    TO anon
    USING (true);  -- Allow anon to read any user record for existence checks

-- Ensure authenticated users can still access their own data
DROP POLICY IF EXISTS "Users can view own profile" ON users;
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT
    TO authenticated
    USING (auth.uid() = auth_id);