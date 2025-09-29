-- Grant permissions to authenticated role for users table
GRANT ALL PRIVILEGES ON public.users TO authenticated;
GRANT SELECT ON public.users TO anon;

-- Check current permissions after granting
SELECT grantee, table_name, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_schema = 'public' 
  AND table_name = 'users'
  AND grantee IN ('anon', 'authenticated') 
ORDER BY table_name, grantee;