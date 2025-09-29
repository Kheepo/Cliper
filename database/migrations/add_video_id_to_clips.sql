-- Add video_id column to clips table
ALTER TABLE clips ADD COLUMN video_id UUID;

-- Add foreign key constraint to videos table (if it exists)
-- ALTER TABLE clips ADD CONSTRAINT fk_clips_video_id FOREIGN KEY (video_id) REFERENCES videos(id);

-- Grant permissions to anon and authenticated roles
GRANT SELECT, INSERT, UPDATE, DELETE ON clips TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON clips TO authenticated;