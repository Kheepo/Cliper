-- Add job_id column to clips table
ALTER TABLE clips ADD COLUMN job_id UUID;

-- Add foreign key constraint to jobs table (if it exists)
-- ALTER TABLE clips ADD CONSTRAINT fk_clips_job_id FOREIGN KEY (job_id) REFERENCES jobs(id);

-- Grant permissions to anon and authenticated roles
GRANT SELECT, INSERT, UPDATE, DELETE ON clips TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON clips TO authenticated;