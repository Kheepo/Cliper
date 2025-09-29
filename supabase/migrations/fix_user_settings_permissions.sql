-- Grant necessary permissions for user_settings table
GRANT INSERT ON user_settings TO authenticated;
GRANT SELECT ON user_settings TO authenticated;
GRANT UPDATE ON user_settings TO authenticated;

-- Check if RLS policies exist for user_settings
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies 
WHERE schemaname = 'public' AND tablename = 'user_settings';

-- Create RLS policies for user_settings if they don't exist
DROP POLICY IF EXISTS "Users can manage their own settings" ON user_settings;

CREATE POLICY "Users can insert their own settings" ON user_settings
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM users 
      WHERE users.id = user_settings.user_id 
      AND users.auth_id = auth.uid()
    )
  );

CREATE POLICY "Users can read their own settings" ON user_settings
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM users 
      WHERE users.id = user_settings.user_id 
      AND users.auth_id = auth.uid()
    )
  );

CREATE POLICY "Users can update their own settings" ON user_settings
  FOR UPDATE USING (
    EXISTS (
      SELECT 1 FROM users 
      WHERE users.id = user_settings.user_id 
      AND users.auth_id = auth.uid()
    )
  );

-- Check current permissions
SELECT grantee, table_name, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_schema = 'public' 
AND table_name = 'user_settings' 
AND grantee IN ('anon', 'authenticated') 
ORDER BY table_name, grantee;