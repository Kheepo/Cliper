-- Migration to update users table for Supabase Auth integration
-- Remove firebase_uid and add auth_id to link with Supabase Auth users

-- First, drop all existing RLS policies that depend on firebase_uid
DROP POLICY IF EXISTS "Users can view own profile" ON users;
DROP POLICY IF EXISTS "Users can update own profile" ON users;
DROP POLICY IF EXISTS "Users can insert own profile" ON users;
DROP POLICY IF EXISTS "Users can view own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can update own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can insert own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can view own jobs" ON jobs;
DROP POLICY IF EXISTS "Users can create own jobs" ON jobs;
DROP POLICY IF EXISTS "Users can update own jobs" ON jobs;
DROP POLICY IF EXISTS "Users can view own job results" ON job_results;
DROP POLICY IF EXISTS "Users can view own job logs" ON job_logs;

-- Add the new auth_id column that will reference auth.users
ALTER TABLE users ADD COLUMN auth_id UUID REFERENCES auth.users(id);

-- Create index for better performance
CREATE INDEX idx_users_auth_id ON users(auth_id);

-- Now we can safely remove the firebase_uid column
ALTER TABLE users DROP COLUMN firebase_uid;

-- Add unique constraint on auth_id
ALTER TABLE users ADD CONSTRAINT users_auth_id_unique UNIQUE (auth_id);

-- Create new RLS policies using auth.uid()
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth_id = auth.uid());

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth_id = auth.uid());

CREATE POLICY "Users can insert own profile" ON users
    FOR INSERT WITH CHECK (auth_id = auth.uid());

-- Grant permissions to authenticated users
GRANT SELECT, INSERT, UPDATE ON users TO authenticated;
GRANT SELECT, INSERT, UPDATE ON user_settings TO authenticated;

-- Update user_settings RLS policies
CREATE POLICY "Users can view own settings" ON user_settings
    FOR SELECT USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can update own settings" ON user_settings
    FOR UPDATE USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can insert own settings" ON user_settings
    FOR INSERT WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

-- Update other tables' RLS policies to use the new auth structure
-- Jobs table
CREATE POLICY "Users can view own jobs" ON jobs
    FOR SELECT USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can insert own jobs" ON jobs
    FOR INSERT WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can update own jobs" ON jobs
    FOR UPDATE USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

-- Job results policies
CREATE POLICY "Users can view own job results" ON job_results
    FOR SELECT USING (job_id IN (SELECT id FROM jobs WHERE user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())));

-- Job logs policies
CREATE POLICY "Users can view own job logs" ON job_logs
    FOR SELECT USING (job_id IN (SELECT id FROM jobs WHERE user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())));

GRANT ALL ON jobs TO authenticated;
GRANT ALL ON job_results TO authenticated;
GRANT ALL ON job_logs TO authenticated;
GRANT ALL ON analysis_results TO authenticated;
GRANT ALL ON generated_clips TO authenticated;
GRANT ALL ON processing_logs TO authenticated;

-- Create a function to automatically create user profile when auth user is created
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (auth_id, email, display_name, photo_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'display_name', NEW.email),
        NEW.raw_user_meta_data->>'avatar_url'
    );
    
    -- Create default user settings
    INSERT INTO public.user_settings (user_id)
    VALUES ((SELECT id FROM public.users WHERE auth_id = NEW.id));
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger to automatically create user profile
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_clips ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_logs ENABLE ROW LEVEL SECURITY;