-- Create a test user for authentication testing
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
  crypt('password123', gen_salt('bf')),
  now(),
  now(),
  now(),
  '',
  '',
  '',
  ''
);

-- Create corresponding user in public.users table
INSERT INTO public.users (
  id,
  email,
  display_name,
  is_active,
  created_at,
  updated_at,
  auth_id,
  email_verified,
  role
) VALUES (
  gen_random_uuid(),
  'test@example.com',
  'Test User',
  true,
  now(),
  now(),
  (SELECT id FROM auth.users WHERE email = 'test@example.com'),
  true,
  'user'
);