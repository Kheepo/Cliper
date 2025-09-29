-- Add current_step column to jobs table
-- This column tracks the current processing step for better user feedback

ALTER TABLE jobs 
ADD COLUMN current_step VARCHAR(200) DEFAULT NULL;

-- Add comment to document the column
COMMENT ON COLUMN jobs.current_step IS 'Current processing step description for user feedback';

-- Create index for better query