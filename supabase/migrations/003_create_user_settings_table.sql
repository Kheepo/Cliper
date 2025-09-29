-- Create user_settings table
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,
    preferences JSONB NOT NULL DEFAULT '{}',
    ai_analysis_settings JSONB NOT NULL DEFAULT '{
        "enable_speech_analysis": true,
        "enable_scene_detection": true,
        "enable_emotion_analysis": true,
        "enable_face_detection": true,
        "viral_score_threshold": 0.7,
        "auto_generate_clips": false,
        "max_clip_duration": 60,
        "min_clip_duration": 5,
        "preferred_resolution": "1920x1080",
        "preferred_format": "mp4"
    }',
    notification_settings JSONB NOT NULL DEFAULT '{
        "email_notifications": true,
        "processing_complete": true,
        "analysis_ready": true,
        "clip_generated": true,
        "error_alerts": true
    }',
    export_settings JSONB NOT NULL DEFAULT '{
        "default_format": "mp4",
        "default_quality": "high",
        "include_metadata": true,
        "watermark_enabled": false,
        "auto_upload_to_cloud": false
    }',
    privacy_settings JSONB NOT NULL DEFAULT '{
        "data_retention_days": 30,
        "allow_analytics": true,
        "share_usage_data": false,
        "public_profile": false
    }',
    subscription_tier VARCHAR(20) DEFAULT 'free', -- 'free', 'pro', 'enterprise'
    usage_limits JSONB NOT NULL DEFAULT '{
        "monthly_video_minutes": 60,
        "monthly_clips_generated": 10,
        "storage_limit_gb": 1,
        "concurrent_processing": 1
    }',
    current_usage JSONB NOT NULL DEFAULT '{
        "monthly_video_minutes_used": 0,
        "monthly_clips_generated": 0,
        "storage_used_gb": 0,
        "last_reset_date": null
    }',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT check_valid_subscription_tier CHECK (subscription_tier IN ('free', 'pro', 'enterprise'))
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_settings_subscription_tier ON user_settings(subscription_tier);
CREATE INDEX IF NOT EXISTS idx_user_settings_created_at ON user_settings(created_at);

-- Enable Row Level Security
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own settings" ON user_settings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own settings" ON user_settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own settings" ON user_settings
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own settings" ON user_settings
    FOR DELETE USING (auth.uid() = user_id);

-- Grant permissions to authenticated users
GRANT ALL PRIVILEGES ON user_settings TO authenticated;
GRANT SELECT ON user_settings TO anon;

-- Create update_updated_at_column function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger for updated_at
CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();



-- Function to reset monthly usage
CREATE OR REPLACE FUNCTION reset_monthly_usage()
RETURNS void AS $$
BEGIN
    UPDATE user_settings 
    SET current_usage = jsonb_set(
        jsonb_set(
            jsonb_set(
                current_usage,
                '{monthly_video_minutes_used}',
                '0'
            ),
            '{monthly_clips_generated}',
            '0'
        ),
        '{last_reset_date}',
        to_jsonb(CURRENT_DATE::text)
    )
    WHERE (current_usage->>'last_reset_date')::date < DATE_TRUNC('month', CURRENT_DATE)::date
       OR current_usage->>'last_reset_date' IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Function to check usage limits
CREATE OR REPLACE FUNCTION check_usage_limit(
    p_user_id UUID,
    p_limit_type TEXT,
    p_amount NUMERIC DEFAULT 1
)
RETURNS BOOLEAN AS $$
DECLARE
    current_limit NUMERIC;
    current_used NUMERIC;
BEGIN
    SELECT 
        (usage_limits->>p_limit_type)::NUMERIC,
        (current_usage->>p_limit_type||'_used')::NUMERIC
    INTO current_limit, current_used
    FROM user_settings
    WHERE user_id = p_user_id;
    
    RETURN (current_used + p_amount) <= current_limit;
END;
$$ LANGUAGE plpgsql;