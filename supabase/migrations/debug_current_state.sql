-- Debug current state of all user-related tables
SELECT 'Current state check:' as status;

-- Check public.users table
SELECT 'public.users:' as table_name;
SELECT id, email, auth_id, created_at FROM public.users ORDER BY created_at DESC LIMIT 10;

-- Check auth.users table
SELECT 'auth.users:' as table_name;
SELECT id, email, created_at FROM auth.users ORDER BY created_at DESC LIMIT 10;

-- Check for any email patterns that might be causing issues
SELECT 'Email pattern analysis:' as analysis;
SELECT email, COUNT(*) as count FROM public.users GROUP BY email HAVING COUNT(*) > 1;

SELECT 'Debug completed' as result;