-- Add role column to users table
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'user';

-- Add check constraint for valid roles
ALTER TABLE public.users ADD CONSTRAINT users_role_check 
  CHECK (role IN ('user', 'admin', 'moderator'));

-- Update existing users to have 'user' role
UPDATE public.users SET role = 'user' WHERE role IS NULL;

-- Grant permissions for the role column
GRANT SELECT, UPDATE ON public.users TO authenticated;
GRANT SELECT ON public.users TO anon;

-- Check current permissions
SELECT grantee, table_name, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_schema = 'public' AND table_name = 'users' 
AND grantee IN ('anon', 'authenticated') 
ORDER BY table_name, grantee;