-- Comprehensive cleanup of auth and user data
-- This will clean up both auth.users and public.users to resolve conflicts

-- First, let's see what auth users exist with example.com emails
SELECT 
    au.id,
    au.email,
    au.created_at,
    CASE 
        WHEN u.auth_id IS NULL THEN 'NO PROFILE'
        ELSE 'HAS PROFILE'
    END as profile_status
FROM auth.users au
LEFT JOIN public.users u ON au.id = u.auth_id
WHERE au.email LIKE '%@example.com'
ORDER BY au.created_at DESC;

-- Delete auth users with example.com emails that have test patterns
-- Note: This uses the service role which has permission to delete auth users
DO $$
DECLARE
    user_record RECORD;
BEGIN
    FOR user_record IN 
        SELECT id, email 
        FROM auth.users 
        WHERE email LIKE '%@example.com' 
        AND (email LIKE 'test%' OR email LIKE 'unique%' OR email LIKE 'fresh%' OR email LIKE 'clean%')
    LOOP
        -- Delete from public.users first
        DELETE FROM public.users WHERE auth_id = user_record.id;
        
        -- Delete from auth.users
        DELETE FROM auth.users WHERE id = user_record.id;
        
        RAISE NOTICE 'Deleted user: %', user_record.email;
    END LOOP;
END $$;

-- Show remaining auth users with example.com emails
SELECT 
    au.id,
    au.email,
    au.created_at
FROM auth.users au
WHERE au.email LIKE '%@example.com'
ORDER BY au.created_at DESC
LIMIT 10;