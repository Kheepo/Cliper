-- Aggressive cleanup using TRUNCATE
-- First, disable RLS and foreign key constraints temporarily
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;

-- Disable triggers temporarily to avoid cascading issues
ALTER TABLE public.users DISABLE TRIGGER ALL;

-- Truncate the users table (this removes all data and resets sequences)
TRUNCATE TABLE public.users RESTART IDENTITY CASCADE;

-- Also clean up auth.users table
DELETE FROM auth.users;

-- Re-enable triggers
ALTER TABLE public.users ENABLE TRIGGER ALL;

-- Re-enable RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Verify cleanup
SELECT 'Cleanup verification:' as status;
SELECT 'public.users count' as table_name, COUNT(*) as remaining_rows FROM public.users
UNION ALL
SELECT 'auth.users count' as table_name, COUNT(*) as remaining_rows FROM auth.users;

SELECT 'Aggressive cleanup completed' as result;