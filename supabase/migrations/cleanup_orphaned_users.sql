-- Clean up orphaned user records that might be causing duplicate key issues
-- This removes users from public.users table that don't have corresponding auth.users

-- First, let's see what we have
SELECT 
    u.email,
    u.auth_id,
    u.created_at,
    CASE 
        WHEN au.id IS NULL THEN 'ORPHANED - NO AUTH USER'
        ELSE 'HAS AUTH USER'
    END as status
FROM public.users u
LEFT JOIN auth.users au ON u.auth_id = au.id
ORDER BY u.created_at DESC
LIMIT 20;

-- Delete orphaned users (users in public.users without corresponding auth.users)
DELETE FROM public.users 
WHERE auth_id NOT IN (
    SELECT id FROM auth.users
);

-- Also clean up any users with email patterns from our tests
DELETE FROM public.users 
WHERE email LIKE '%@example.com' 
AND (email LIKE 'test%' OR email LIKE 'unique%' OR email LIKE 'fresh%');

-- Show remaining users after cleanup
SELECT 
    u.email,
    u.auth_id,
    u.created_at
FROM public.users u
ORDER BY u.created_at DESC
LIMIT 10;