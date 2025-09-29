-- Check current permissions for users table
SELECT grantee, table_name, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_schema = 'public' 
  AND table_name = 'users' 
  AND grantee IN ('anon', 'authenticated') 
ORDER BY table_name, grantee;

-- Grant necessary permissions to anon role (for registration)
GRANT INSERT ON public.users TO anon;
GRANT SELECT ON public.users TO anon;

-- Grant full access to authenticated role
GRANT ALL PRIVILEGES ON public.users TO authenticated;

-- Also grant permissions for user_settings table
GRANT INSERT ON public.user_settings TO anon;
GRANT SELECT ON public.user_settings TO anon;
GRANT ALL PRIVILEGES ON public.user_settings TO authenticated;

-- Grant permissions for user_preferences table
GRANT INSERT ON public.user_preferences TO anon;
GRANT SELECT ON public.user_preferences TO anon;
GRANT ALL PRIVILEGES ON public.user_preferences TO authenticated;

-- Verify permissions after granting
SELECT grantee, table_name, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_schema = 'public' 
  AND table_name IN ('users', 'user_settings', 'user_preferences')
  AND grantee IN ('anon', 'authenticated') 
ORDER BY table_name, grantee;