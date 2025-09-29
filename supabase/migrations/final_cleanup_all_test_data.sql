-- Final comprehensive cleanup of all test data
-- This will remove ALL test users from both auth and public tables

-- First, show what we're about to clean up
SELECT 'AUTH USERS TO DELETE' as table_name, email, created_at
FROM auth.users 
WHERE email LIKE '%test%' 
   OR email LIKE '%example.com%' 
   OR email LIKE '%@test.com%'
   OR email LIKE '%@gmail.com%'
ORDER BY created_at DESC;

SELECT 'PUBLIC USERS TO DELETE' as table_name, email, created_at
FROM public.users 
WHERE email LIKE '%test%' 
   OR email LIKE '%example.com%' 
   OR email LIKE '%@test.com%'
   OR email LIKE '%@gmail.com%'
ORDER BY created_at DESC;

-- Delete all test users from public.users first
DELETE FROM public.users 
WHERE email LIKE '%test%' 
   OR email LIKE '%example.com%' 
   OR email LIKE '%@test.com%'
   OR email LIKE '%@gmail.com%';

-- Delete all test users from auth.users
-- Note: This requires service role permissions
DO $$
DECLARE
    user_record RECORD;
    deleted_count INTEGER := 0;
BEGIN
    FOR user_record IN 
        SELECT id, email 
        FROM auth.users 
        WHERE email LIKE '%test%' 
           OR email LIKE '%example.com%' 
           OR email LIKE '%@test.com%'
           OR email LIKE '%@gmail.com%'
    LOOP
        DELETE FROM auth.users WHERE id = user_record.id;
        deleted_count := deleted_count + 1;
        RAISE NOTICE 'Deleted auth user: % (ID: %)', user_record.email, user_record.id;
    END LOOP;
    
    RAISE NOTICE 'Total auth users deleted: %', deleted_count;
END $$;

-- Show final state
SELECT 'REMAINING AUTH USERS' as table_name, COUNT(*) as count
FROM auth.users;

SELECT 'REMAINING PUBLIC USERS' as table_name, COUNT(*) as count
FROM public.users;