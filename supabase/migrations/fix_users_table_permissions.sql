-- Grant permissions for users table to anon and authenticated roles
-- This fixes the registration functionality

-- Grant SELECT, INSERT, UPDATE permissions to authenticated users
GRANT SELECT, INSERT, UPDATE ON public.users TO authenticated;

-- Grant SELECT permission to anon users (for public profiles)
GRANT SELECT ON public.users TO anon;

-- Create RLS policies for users table

-- Policy: Users can view their own profile
CREATE POLICY "Users can view own profile" ON public.users
    FOR SELECT
    TO authenticated
    USING (auth.uid() = auth_id);

-- Policy: Users can insert their own profile during registration
CREATE POLICY "Users can insert own profile" ON public.users
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = auth_id);

-- Policy: Users can update their own profile
CREATE POLICY "Users can update own profile" ON public.users
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = auth_id)
    WITH CHECK (auth.uid() = auth_id);

-- Policy: Allow service role to manage all users (for admin operations)
CREATE POLICY "Service role can manage all users" ON public.users
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Grant permissions for user_settings table as well
GRANT SELECT, INSERT, UPDATE ON public.user_settings TO authenticated;
GRANT SELECT ON public.user_settings TO anon;

-- RLS policies for user_settings
CREATE POLICY "Users can manage own settings" ON public.user_settings
    FOR ALL
    TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.users 
        WHERE users.id = user_settings.user_id 
        AND users.auth_id = auth.uid()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.users 
        WHERE users.id = user_settings.user_id 
        AND users.auth_id = auth.uid()
    ));

-- Service role policy for user_settings
CREATE POLICY "Service role can manage all user settings" ON public.user_settings
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);