-- Create missing tables for Cliper application
-- Migration: 20240101000000_create_missing_tables.sql

-- Analysis Results Table
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    viral_score FLOAT CHECK (viral_score >= 0 AND viral_score <= 100),
    speech_analysis JSONB DEFAULT '{}',
    scene_analysis JSONB DEFAULT '{}',
    emotion_analysis JSONB DEFAULT '{}',
    recommendations JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for analysis_results
CREATE INDEX idx_analysis_results_job_id ON analysis_results(job_id);
CREATE INDEX idx_analysis_results_viral_score ON analysis_results(viral_score DESC);

-- Grant permissions for analysis_results
GRANT SELECT ON analysis_results TO anon;
GRANT ALL PRIVILEGES ON analysis_results TO authenticated;

-- Analysis Segments Table
CREATE TABLE analysis_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID REFERENCES analysis_results(id) ON DELETE CASCADE,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    engagement_score FLOAT CHECK (engagement_score >= 0 AND engagement_score <= 100),
    segment_type VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for analysis_segments
CREATE INDEX idx_analysis_segments_analysis_id ON analysis_segments(analysis_id);
CREATE INDEX idx_analysis_segments_engagement_score ON analysis_segments(engagement_score DESC);

-- Grant permissions for analysis_segments
GRANT SELECT ON analysis_segments TO anon;
GRANT ALL PRIVILEGES ON analysis_segments TO authenticated;

-- Generated Clips Table
CREATE TABLE generated_clips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    segment_id UUID REFERENCES analysis_segments(id) ON DELETE SET NULL,
    platform VARCHAR(20) CHECK (platform IN ('tiktok', 'instagram', 'youtube', 'twitter')),
    file_path VARCHAR(500),
    thumbnail_path VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for generated_clips
CREATE INDEX idx_generated_clips_job_id ON generated_clips(job_id);
CREATE INDEX idx_generated_clips_platform ON generated_clips(platform);

-- Grant permissions for generated_clips
GRANT SELECT ON generated_clips TO anon;
GRANT ALL PRIVILEGES ON generated_clips TO authenticated;

-- Processing Logs Table
CREATE TABLE processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    stage VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    message TEXT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for processing_logs
CREATE INDEX idx_processing_logs_job_id ON processing_logs(job_id);
CREATE INDEX idx_processing_logs_created_at ON processing_logs(created_at DESC);

-- Grant permissions for processing_logs
GRANT SELECT ON processing_logs TO anon;
GRANT ALL PRIVILEGES ON processing_logs TO authenticated;

-- User Settings Table
CREATE TABLE user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    notification_preferences JSONB DEFAULT '{"email": true, "push": false}',
    default_platforms JSONB DEFAULT '["tiktok", "instagram"]',
    quality_preferences JSONB DEFAULT '{"resolution": "1080p", "format": "mp4"}',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for user_settings
CREATE UNIQUE INDEX idx_user_settings_user_id ON user_settings(user_id);

-- Grant permissions for user_settings
GRANT SELECT ON user_settings TO anon;
GRANT ALL PRIVILEGES ON user_settings TO authenticated;

-- Insert sample user settings for existing users
INSERT INTO user_settings (user_id, notification_preferences, default_platforms, quality_preferences)
SELECT 
    id,
    '{"email": true, "push": false, "completion": true}',
    '["tiktok", "instagram", "youtube"]',
    '{"resolution": "1080p", "format": "mp4", "quality": "high"}'
FROM users
WHERE id NOT IN (SELECT user_id FROM user_settings WHERE user_id IS NOT NULL);

-- Add RLS (Row Level Security) policies
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_clips ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- RLS policies for analysis_results
CREATE POLICY "Users can view their own analysis results" ON analysis_results
    FOR SELECT USING (job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid()));

CREATE POLICY "Users can insert their own analysis results" ON analysis_results
    FOR INSERT WITH CHECK (job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid()));

-- RLS policies for analysis_segments
CREATE POLICY "Users can view their own analysis segments" ON analysis_segments
    FOR SELECT USING (analysis_id IN (SELECT id FROM analysis_results WHERE job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid())));

CREATE POLICY "Users can insert their own analysis segments" ON analysis_segments
    FOR INSERT WITH CHECK (analysis_id IN (SELECT id FROM analysis_results WHERE job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid())));

-- RLS policies for generated_clips
CREATE POLICY "Users can view their own generated clips" ON generated_clips
    FOR SELECT USING (job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid()));

CREATE POLICY "Users can insert their own generated clips" ON generated_clips
    FOR INSERT WITH CHECK (job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid()));

-- RLS policies for processing_logs
CREATE POLICY "Users can view their own processing logs" ON processing_logs
    FOR SELECT USING (job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid()));

CREATE POLICY "Users can insert their own processing logs" ON processing_logs
    FOR INSERT WITH CHECK (job_id IN (SELECT id FROM jobs WHERE user_id = auth.uid()));

-- RLS policies for user_settings
CREATE POLICY "Users can view their own settings" ON user_settings
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY "Users can update their own settings" ON user_settings
    FOR ALL USING (user_id = auth.uid());

-- Create triggers for updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE analysis_results IS 'Stores AI analysis results for video jobs';
COMMENT ON TABLE analysis_segments IS 'Stores individual segments from video analysis';
COMMENT ON TABLE generated_clips IS 'Stores information about generated video clips';
COMMENT ON TABLE processing_logs IS 'Stores processing logs and status updates for jobs';
COMMENT ON TABLE user_settings IS 'Stores user preferences and settings';