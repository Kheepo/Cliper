-- Add email_verified column to users table
ALTER TABLE public.users 
ADD COLUMN email_verified BOOLEAN DEFAULT false;

-- Update existing users to have email_verified = true (since they were created successfully)
UPDATE public.users 
SET email_verified = true 
WHERE email_verified IS NULL;

-- Add comment to the column
COMMENT ON COLUMN public.users.email_verified IS 'Indicates whether the user has verified their email address';