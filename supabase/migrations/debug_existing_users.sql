-- Debug existing users to understand the duplicate key issue

-- Check existing users in public.users table
SELECT 'PUBLIC USERS:' as table_name, email, auth_id, created_at 
FROM public.users 
ORDER BY created_at DESC;

-- Check existing users in auth.users table
SELECT 'AUTH USERS:' as table_name, email, id, created_at 
FROM auth.users 
ORDER BY created_at DESC;

-- Delete ALL existing users from both tables to start fresh
DELETE FROM public.users;
DELETE FROM auth.users;

-- Verify cleanup
SELECT 'AFTER CLEANUP - PUBLIC:' as status, COUNT(*) as count FROM public.users;
SELECT 'AFTER CLEANUP - AUTH:' as status, COUNT(*) as count FROM auth.users;