-- Update generated_clips table schema with missing fields and indexes
-- Add missing fields for production-ready clip generation

-- Add thumbnail_path field if it doesn't exist
ALTER TABLE generated_clips 
ADD COLUMN IF NOT EXISTS thumbnail_path TEXT;

-- Add platform field for platform-specific optimization
ALTER TABLE generated_clips 
ADD COLUMN IF NOT EXISTS platform VARCHAR(50) DEFAULT 'general' 
CHECK (platform IN ('general', 'youtube', 'tiktok', 'instagram', 'twitter', 'facebook'));

-- Add clip_type field for different clip categories
ALTER TABLE generated_clips 
ADD COLUMN IF NOT EXISTS clip_type VARCHAR(50) DEFAULT 'highlight' 
CHECK (clip_type IN ('highlight', 'teaser', 'summary', 'custom'));

-- Add quality field for video quality tracking
ALTER TABLE generated_clips 
ADD COLUMN IF NOT EXISTS quality VARCHAR(20) DEFAULT 'high' 
CHECK (quality IN ('low', 'medium', 'high', 'ultra'));

-- Add retry_count for error recovery
ALTER TABLE generated_clips 
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- Add last_error_at for error tracking
ALTER TABLE generated_clips 
ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMPTZ;

-- Add generation_metadata for storing additional processing info
ALTER TABLE generated_clips 
ADD COLUMN IF NOT EXISTS generation_metadata JSONB DEFAULT '{}'::jsonb;

-- Create indexes for performance optimization

-- Index for user queries (most common)
CREATE INDEX IF NOT EXISTS idx_generated_clips_user_id 
ON generated_clips(user_id);

-- Index for video-based queries
CREATE INDEX IF NOT EXISTS idx_generated_clips_original_video_id 
ON generated_clips(original_video_id);

-- Index for status-based queries (for monitoring)
CREATE INDEX IF NOT EXISTS idx_generated_clips_status 
ON generated_clips(status);

-- Composite index for user + status queries
CREATE INDEX IF NOT EXISTS idx_generated_clips_user_status 
ON generated_clips(user_id, status);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_generated_clips_created_at 
ON generated_clips(created_at DESC);

-- Index for platform-specific queries
CREATE INDEX IF NOT EXISTS idx_generated_clips_platform 
ON generated_clips(platform);

-- Index for clip type queries
CREATE INDEX IF NOT EXISTS idx_generated_clips_type 
ON generated_clips(clip_type);

-- Composite index for video + status (for processing workflows)
CREATE INDEX IF NOT EXISTS idx_generated_clips_video_status 
ON generated_clips(original_video_id, status);

-- Index for viral score queries (for recommendations)
CREATE INDEX IF NOT EXISTS idx_generated_clips_viral_score 
ON generated_clips(viral_score DESC) WHERE viral_score IS NOT NULL;

-- Index for error tracking and retry logic
CREATE INDEX IF NOT EXISTS idx_generated_clips_retry_count 
ON generated_clips(retry_count) WHERE status = 'failed';

-- Add foreign key constraints if they don't exist
-- Note: We're using logical foreign keys instead of physical ones as per guidelines

-- Add RLS policies for security
ALTER TABLE generated_clips ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own clips
CREATE POLICY IF NOT EXISTS "Users can view own clips" ON generated_clips
    FOR SELECT USING (auth.uid()::uuid = user_id);

-- Policy: Users can insert their own clips
CREATE POLICY IF NOT EXISTS "Users can insert own clips" ON generated_clips
    FOR INSERT WITH CHECK (auth.uid()::uuid = user_id);

-- Policy: Users can update their own clips
CREATE POLICY IF NOT EXISTS "Users can update own clips" ON generated_clips
    FOR UPDATE USING (auth.uid()::uuid = user_id);

-- Policy: Users can delete their own clips
CREATE POLICY IF NOT EXISTS "Users can delete own clips" ON generated_clips
    FOR DELETE USING (auth.uid()::uuid = user_id);

-- Grant permissions to anon and authenticated roles
GRANT SELECT, INSERT, UPDATE, DELETE ON generated_clips TO authenticated;
GRANT SELECT ON generated_clips TO anon;

-- Add trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger if it doesn't exist
DROP TRIGGER IF EXISTS update_generated_clips_updated_at ON generated_clips;
CREATE TRIGGER update_generated_clips_updated_at
    BEFORE UPDATE ON generated_clips
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE generated_clips IS 'Stores generated video clips with metadata and processing status';
COMMENT ON COLUMN generated_clips.thumbnail_path IS 'Path to the generated thumbnail image';
COMMENT ON COLUMN generated_clips.platform IS 'Target platform for optimization (youtube, tiktok, etc.)';
COMMENT ON COLUMN generated_clips.clip_type IS 'Type of clip (highlight, teaser, summary, custom)';
COMMENT ON COLUMN generated_clips.quality IS 'Video quality setting used for generation';
COMMENT ON COLUMN generated_clips.retry_count IS 'Number of retry attempts for failed generations';
COMMENT ON COLUMN generated_clips.last_error_at IS 'Timestamp of the last error occurrence';
COMMENT ON COLUMN generated_clips.generation_metadata IS 'Additional metadata about the generation process';
