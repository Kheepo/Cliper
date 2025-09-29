-- Update existing user_settings table to add AI analysis columns
-- First, add the new columns
ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS ai_analysis_settings JSONB DEFAULT '{
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
ADD COLUMN IF NOT EXISTS notification_settings JSONB DEFAULT '{
    "email_notifications": true,
    "processing_complete": true,
    "analysis_ready": true,
    "clip_generated": true,
    "error_alerts": true
}',
ADD COLUMN IF NOT EXISTS export_settings JSONB DEFAULT '{
    "default_format": "mp4",
    "default_quality": "high",
    "include_metadata": true,
    "watermark_enabled": false,
    "auto_upload_to_cloud": false
}',
ADD COLUMN IF NOT EXISTS privacy_settings JSONB DEFAULT '{
    "data_retention_days": 30,
    "allow_analytics": true,
    "share_usage_data": false,
    "public_profile": false
}',
ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(20) DEFAULT 'free',
ADD COLUMN IF NOT EXISTS usage_limits JSONB DEFAULT '{
    "monthly_video_minutes": 60,
    "monthly_clips_generated": 10,
    "storage_limit_gb": 1,
    "concurrent_processing": 1
}',
ADD COLUMN IF NOT EXISTS current_usage JSONB DEFAULT '{
    "monthly_video_minutes_used": 0,
    "monthly_clips_generated": 0,
    "storage_used_gb": 0,
    "last_reset_date": null
}';

-- Add constraint for valid subscription tiers
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'check_valid_subscription_tier' 
        AND table_name = 'user_settings'
    ) THEN
        ALTER TABLE user_settings ADD CONSTRAINT check_valid_subscription_tier 
            CHECK (subscription_tier IN ('free', 'pro', 'enterprise'));
    END IF;
END $$;

-- Create additional indexes
CREATE INDEX IF NOT EXISTS idx_user_settings_subscription_tier ON user_settings(subscription_tier);

-- Create update_updated_at_column function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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