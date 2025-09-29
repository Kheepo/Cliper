-- Comprehensive cleanup of both database and auth system
-- This will help us understand what's causing the persistent duplicates

-- First, let's see what's currently in our tables
SELECT 'Current public.users records:' as debug_info;
SELECT id, email, auth_id, created_at FROM public.users ORDER BY created_at DESC LIMIT 10;

-- Check auth.users as well
SELECT 'Current auth.users records:' as debug_info;
SELECT id, email, created_at FROM auth.users ORDER BY created_at DESC LIMIT 10;

-- Disable RLS for cleanup
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;

-- Delete all users from public.users
DELETE FROM public.users;

-- Delete all users from auth.users
DELETE FROM auth.users;

-- Reset sequences
SELECT setval(pg_get_serial_sequence('public.users', 'id'), 1, false) WHERE pg_get_serial_sequence('public.users', 'id') IS NOT NULL;

-- Re-enable RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Final verification
SELECT 'After comprehensive cleanup:' as debug_info;
SELECT 'public.users' as table_name, COUNT(*) as count FROM public.users
UNION ALL
SELECT 'auth.users' as table_name, COUNT(*) as count FROM auth.users;

SELECT 'Comprehensive cleanup completed - both tables should be empty' as result;