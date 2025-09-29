-- Debug and delete the phantom record
-- First, show exactly what's in the table
SELECT 'Current phantom record:' as debug_info;
SELECT id, email, auth_id, display_name, created_at FROM public.users;

-- Also check auth.users
SELECT 'Auth users:' as debug_info;
SELECT id, email, created_at FROM auth.users;

-- Disable RLS temporarily
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;

-- Force delete with explicit WHERE clause to catch everything
DELETE FROM public.users WHERE true;

-- Also clean auth.users
DELETE FROM auth.users WHERE true;

-- Re-enable RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Final verification
SELECT 'After deletion:' as debug_info;
SELECT COUNT(*) as users_count FROM public.users;
SELECT COUNT(*) as auth_users_count FROM auth.users;

SELECT 'Phantom record deletion completed' as result;