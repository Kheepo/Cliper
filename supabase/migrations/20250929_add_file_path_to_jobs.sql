-- Add file_path column to jobs table
-- This column will store the storage path for uploaded video files

ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS file_path TEXT;

-- Add comment to document the column purpose
COMMENT ON COLUMN jobs.file_path IS 'Storage path for uploaded video files in Supabase Storage';

-- Create index for better query performance on file_path
CREATE INDEX IF NOT EXISTS idx_jobs_file_path ON jobs(file_path);