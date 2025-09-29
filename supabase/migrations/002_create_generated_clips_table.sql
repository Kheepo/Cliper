-- Create generated_clips table
CREATE TABLE IF NOT EXISTS generated_clips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_video_id UUID NOT NULL,
    user_id UUID NOT NULL,
    clip_name VARCHAR(255) NOT NULL,
    clip_url TEXT,
    local_path TEXT,
    start_time DECIMAL(10,3) NOT NULL,
    end_time DECIMAL(10,3) NOT NULL,
    duration DECIMAL(10,3) GENERATED ALWAYS AS (end_time - start_time) STORED,
    file_size BIGINT,
    format VARCHAR(10) DEFAULT 'mp4',
    resolution VARCHAR(20), -- e.g., '1920x1080'
    viral_score DECIMAL(5,3),
    generation_settings JSONB, -- stores clip generation parameters
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_generated_clips_original_video ON generated_clips(original_video_id);
CREATE INDEX IF NOT EXISTS idx_generated_clips_user_id ON generated_clips(user_id);
CREATE INDEX IF NOT EXISTS idx_generated_clips_status ON generated_clips(status);
CREATE INDEX IF NOT EXISTS idx_generated_clips_created_at ON generated_clips(created_at);
CREATE INDEX IF NOT EXISTS idx_generated_clips_viral_score ON generated_clips(viral_score DESC);
CREATE INDEX IF NOT EXISTS idx_generated_clips_duration ON generated_clips(duration);

-- Create composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_generated_clips_user_status ON generated_clips(user_id, status);
CREATE INDEX IF NOT EXISTS idx_generated_clips_video_status ON generated_clips(original_video_id, status);

-- Enable Row Level Security
ALTER TABLE generated_clips ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own generated clips" ON generated_clips
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own generated clips" ON generated_clips
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own generated clips" ON generated_clips
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own generated clips" ON generated_clips
    FOR DELETE USING (auth.uid() = user_id);

-- Grant permissions to authenticated users
GRANT ALL PRIVILEGES ON generated_clips TO authenticated;
GRANT SELECT ON generated_clips TO anon;

-- Add trigger for updated_at
CREATE TRIGGER update_generated_clips_updated_at
    BEFORE UPDATE ON generated_clips
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add constraint to ensure valid time range
ALTER TABLE generated_clips ADD CONSTRAINT check_valid_time_range 
    CHECK (start_time >= 0 AND end_time > start_time);

-- Add constraint for valid status values
ALTER TABLE generated_clips ADD CONSTRAINT check_valid_status 
    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled'));

-- Add constraint for valid format values
ALTER TABLE generated_clips ADD CONSTRAINT check_valid_format 
    CHECK (format IN ('mp4', 'mov', 'avi', 'webm', 'mkv'));