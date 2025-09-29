-- Fix permissions for users table to allow registration
-- This addresses the "User not allowed" error during registration

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Allow anon users to insert during registration" ON users;
DROP POLICY IF EXISTS "Users can view own profile" ON users;
DROP POLICY IF EXISTS "Users can update own profile" ON users;
DROP POLICY IF EXISTS "Users can delete own profile" ON users;

-- Grant basic permissions to anon role (for registration)
GRANT SELECT, INSERT ON users TO anon;

-- Grant full permissions to authenticated role (for logged-in users)
GRANT ALL PRIVILEGES ON users TO authenticated;

-- Create RLS policies for the users table

-- Policy for anon users to insert during registration
CREATE POLICY "Allow anon users to insert during registration" ON users
    FOR INSERT
    TO anon
    WITH CHECK (true);

-- Policy for authenticated users to view their own profile
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT
    TO authenticated
    USING (auth.uid() = auth_id);

-- Policy for authenticated users to update their own profile
CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = auth_id)
    WITH CHECK (auth.uid() = auth_id);

-- Policy for authenticated users to delete their own profile
CREATE POLICY "Users can delete own profile" ON users
    FOR DELETE
    TO authenticated
    USING (auth.uid() = auth_id);

-- Grant usage on the uuid extension (needed for ID generation)
GRANT USAGE ON SCHEMA extensions TO anon, authenticated;
GRANT EXECUTE ON FUNCTION extensions.uuid_generate_v4() TO anon, authenticated;