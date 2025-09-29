-- Force complete cleanup - target the remaining phantom record
-- First, disable RLS
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;

-- Show what's currently in the table
SELECT 'Before cleanup - remaining records:' as status;
SELECT id, email, auth_id, created_at FROM public.users;

-- Force delete everything with CASCADE
DELETE FROM public.users CASCADE;

-- Also clean auth.users completely
DELETE FROM auth.users;

-- Reset any sequences if they exist
SELECT setval(pg_get_serial_sequence('public.users', 'id'), 1, false) WHERE pg_get_serial_sequence('public.users', 'id') IS NOT NULL;

-- Re-enable RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Final verification
SELECT 'After cleanup verification:' as status;
SELECT 'public.users count' as table_name, COUNT(*) as remaining_rows FROM public.users
UNION ALL
SELECT 'auth.users count' as table_name, COUNT(*) as remaining_rows FROM auth.users;

SELECT 'Force cleanup completed - should be completely empty now' as result;