-- Create a test user for debugging authentication flow
-- This will create a user in both auth.users and public.users tables

INSERT INTO auth.users (
  id,
  email,
  encrypted_password,
  email_confirmed_at,
  created_at,
  updated_at,
  confirmation_token,
  email_change,
  email_change_token_new,
  recovery_token
) VALUES (
  gen_random_uuid(),
  'test@example.com',
  crypt('testpassword123', gen_salt('bf')),
  now(),
  now(),
  now(),
  '',
  '',
  '',
  ''
);

-- Create corresponding user profile in public.users
INSERT INTO public.users (
  id,
  auth_id,
  email,
  display_name,
  is_active,
  email_verified,
  role,
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  (SELECT id FROM auth.users WHERE email = 'test@example.com'),
  'test@example.com',
  'Test User',
  true,
  true,
  'user',
  now(),
  now()
);

-- Create default user settings
INSERT INTO public.user_settings (
  user_id
) VALUES (
  (SELECT id FROM public.users WHERE email = 'test@example.com')
);

-- Create default user preferences
INSERT INTO public.user_preferences (
  user_id
) VALUES (
  (SELECT id FROM public.users WHERE email = 'test@example.com')
);