-- Check current users in both tables
SELECT 'public.users count:' as info, COUNT(*) as count FROM public.users;
SELECT 'auth.users count:' as info, COUNT(*) as count FROM auth.users;

-- Show actual data in public.users
SELECT 'Current public.users data:' as info;
SELECT id, email, auth_id, created_at FROM public.users ORDER BY created_at DESC;

-- Show actual data in auth.users
SELECT 'Current auth.users data:' as info;
SELECT id, email, created_at FROM auth.users ORDER BY created_at DESC;

-- Delete all users from public.users first (to avoid foreign key constraints)
DELETE FROM public.users;

-- Delete all users from auth.users
DELETE FROM auth.users;

-- Verify cleanup
SELECT 'After cleanup - public.users count:' as info, COUNT(*) as count FROM public.users;
SELECT 'After cleanup - auth.users count:' as info, COUNT(*) as count FROM auth.users;

-- Reset sequences if they exist
SELECT 'Cleanup completed successfully' as status;