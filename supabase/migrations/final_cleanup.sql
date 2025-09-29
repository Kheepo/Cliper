-- Final cleanup approach - delete with proper cascade handling
-- First, disable RLS temporarily
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;

-- Delete from dependent tables first to avoid foreign key issues
DELETE FROM public.user_settings;
DELETE FROM public.jobs;
DELETE FROM public.password_reset_tokens;
DELETE FROM public.user_preferences;

-- Now delete from users table
DELETE FROM public.users;

-- Delete from auth.users
DELETE FROM auth.users;

-- Re-enable RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Verify cleanup
SELECT 'Final cleanup verification:' as status;
SELECT 'public.users count' as table_name, COUNT(*) as remaining_rows FROM public.users
UNION ALL
SELECT 'auth.users count' as table_name, COUNT(*) as remaining_rows FROM auth.users
UNION ALL
SELECT 'user_settings count' as table_name, COUNT(*) as remaining_rows FROM public.user_settings
UNION ALL
SELECT 'jobs count' as table_name, COUNT(*) as remaining_rows FROM public.jobs;

SELECT 'Final cleanup completed successfully' as result;