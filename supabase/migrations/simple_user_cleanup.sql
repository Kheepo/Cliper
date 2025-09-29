-- Simple cleanup of all user data
-- First, disable RLS temporarily to ensure we can delete everything
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;

-- Delete all data from public.users
DELETE FROM public.users;

-- Delete all data from auth.users (this will cascade to related tables)
DELETE FROM auth.users;

-- Re-enable RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Verify cleanup
SELECT 'Cleanup verification:' as status;
SELECT 'public.users count' as table_name, COUNT(*) as remaining_rows FROM public.users
UNION ALL
SELECT 'auth.users count' as table_name, COUNT(*) as remaining_rows FROM auth.users;

SELECT 'Cleanup completed successfully'