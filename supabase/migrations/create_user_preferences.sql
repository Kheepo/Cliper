-- Create user_preferences table for storing user-specific preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT extensions.uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'light' CHECK (theme IN ('light', 'dark', 'auto')),
    language VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_notifications BOOLEAN DEFAULT true,
    push_notifications BOOLEAN DEFAULT true,
    marketing_emails BOOLEAN DEFAULT false,
    auto_save BOOLEAN DEFAULT true,
    default_privacy VARCHAR(20) DEFAULT 'private' CHECK (default_privacy IN ('public', 'private', 'unlisted')),
    analytics_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

-- Enable Row Level Security
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
-- Users can only access their own preferences
CREATE POLICY "Users can view their own preferences" ON user_preferences
    FOR SELECT USING (
        user_id IN (
            SELECT id FROM users WHERE auth_id = auth.uid()
        )
    );

CREATE POLICY "Users can update their own preferences" ON user_preferences
    FOR UPDATE USING (
        user_id IN (
            SELECT id FROM users WHERE auth_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert their own preferences" ON user_preferences
    FOR INSERT WITH CHECK (
        user_id IN (
            SELECT id FROM users WHERE auth_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete their own preferences" ON user_preferences
    FOR DELETE USING (
        user_id IN (
            SELECT id FROM users WHERE auth_id = auth.uid()
        )
    );

-- Grant permissions to authenticated users
GRANT SELECT, INSERT, UPDATE, DELETE ON user_preferences TO authenticated;

-- Grant read access to anon role for public data (if needed)
GRANT SELECT ON user_preferences TO anon;

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_preferences_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
CREATE TRIGGER trigger_update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_user_preferences_updated_at();

-- Add comments for documentation
COMMENT ON TABLE user_preferences IS 'Stores user-specific preferences and settings';
COMMENT ON COLUMN user_preferences.theme IS 'UI theme preference: light, dark, or auto';
COMMENT ON COLUMN user_preferences.language IS 'User interface language preference';
COMMENT ON COLUMN user_preferences.timezone IS 'User timezone for date/time display';
COMMENT ON COLUMN user_preferences.email_notifications IS 'Whether to send email notifications';
COMMENT ON COLUMN user_preferences.push_notifications IS 'Whether to send push notifications';
COMMENT ON COLUMN user_preferences.marketing_emails IS 'Whether to send marketing emails';
COMMENT ON COLUMN user_preferences.auto_save IS 'Whether to automatically save work';
COMMENT ON COLUMN user_preferences.default_privacy IS 'Default privacy setting for new content';
COMMENT ON COLUMN user_preferences.analytics_enabled IS 'Whether to enable analytics tracking';