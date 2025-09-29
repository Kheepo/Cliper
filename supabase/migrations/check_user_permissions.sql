-- Check current permissions for users table
SELECT grantee, table_name, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_schema = 'public' 
AND table_name = 'users' 
AND grantee IN ('anon', 'authenticated') 
ORDER BY table_name, grantee;

-- Grant necessary permissions for signup to work
GRANT INSERT ON users TO authenticated;
GRANT SELECT ON users TO authenticated;
GRANT UPDATE ON users TO authenticated;

-- Grant basic read access to anon role for login checks
GRANT SELECT ON users TO anon;

-- Check RLS policies on users table
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies 
WHERE schemaname = 'public' AND tablename = 'users';

-- Create RLS policy to allow users to insert their own profile
CREATE POLICY "Users can insert their own profile" ON users
  FOR INSERT WITH CHECK (auth.uid() = auth_id);

-- Create RLS policy to allow users to read their own profile
CREATE POLICY "Users can read their own profile" ON users
  FOR SELECT USING (auth.uid() = auth_id);

-- Create RLS policy to allow users to update their own profile
CREATE POLICY "Users can update their own profile" ON users
  FOR UPDATE USING (auth.uid() = auth_id);