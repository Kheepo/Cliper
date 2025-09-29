-- Debug users table to see current state
SELECT 'public.users table:' as info;
SELECT id, email, auth_id, created_at FROM public.users ORDER BY created_at DESC LIMIT 10;

SELECT 'auth.users table:' as info;
SELECT id, email, created_at FROM auth.users ORDER BY created_at DESC LIMIT 10;

SELECT 'Table counts:' as info;
SELECT 'public.users' as table_name, COUNT(*) as count FROM public.users
UNION ALL
SELECT 'auth.users' as table_name, COUNT(*) as count FROM auth.users;