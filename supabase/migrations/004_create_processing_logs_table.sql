-- Create processing_logs table
CREATE TABLE IF NOT EXISTS processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL,
    video_id UUID,
    user_id UUID NOT NULL,
    operation_type VARCHAR(50) NOT NULL, -- 'upload', 'analysis', 'clip_generation', 'export'
    operation_subtype VARCHAR(50), -- 'speech_analysis', 'scene_detection', 'emotion_analysis', etc.
    status VARCHAR(20) NOT NULL DEFAULT 'started', -- 'started', 'in_progress', 'completed', 'failed', 'cancelled'
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    message TEXT,
    error_details JSONB,
    metadata JSONB, -- stores operation-specific data
    processing_time_ms INTEGER,
    memory_usage_mb INTEGER,
    cpu_usage_percentage DECIMAL(5,2),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_processing_logs_job_id ON processing_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_video_id ON processing_logs(video_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_user_id ON processing_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_operation_type ON processing_logs(operation_type);
CREATE INDEX IF NOT EXISTS idx_processing_logs_status ON processing_logs(status);
CREATE INDEX IF NOT EXISTS idx_processing_logs_started_at ON processing_logs(started_at);
CREATE INDEX IF NOT EXISTS idx_processing_logs_created_at ON processing_logs(created_at);

-- Create composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_processing_logs_user_status ON processing_logs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_processing_logs_job_status ON processing_logs(job_id, status);
CREATE INDEX IF NOT EXISTS idx_processing_logs_operation_status ON processing_logs(operation_type, status);
CREATE INDEX IF NOT EXISTS idx_processing_logs_video_operation ON processing_logs(video_id, operation_type);

-- Enable Row Level Security
ALTER TABLE processing_logs ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own processing logs" ON processing_logs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "System can insert processing logs" ON processing_logs
    FOR INSERT WITH CHECK (true); -- Allow system to insert logs

CREATE POLICY "System can update processing logs" ON processing_logs
    FOR UPDATE USING (true); -- Allow system to update logs

-- Grant permissions
GRANT ALL PRIVILEGES ON processing_logs TO authenticated;
GRANT SELECT ON processing_logs TO anon;

-- Add constraint for valid status values
ALTER TABLE processing_logs ADD CONSTRAINT check_valid_status 
    CHECK (status IN ('started', 'in_progress', 'completed', 'failed', 'cancelled', 'paused'));

-- Add constraint for valid operation types
ALTER TABLE processing_logs ADD CONSTRAINT check_valid_operation_type 
    CHECK (operation_type IN ('upload', 'analysis', 'clip_generation', 'export', 'transcoding', 'validation'));

-- Function to update processing log status
CREATE OR REPLACE FUNCTION update_processing_log(
    p_job_id UUID,
    p_status VARCHAR(20),
    p_progress INTEGER DEFAULT NULL,
    p_message TEXT DEFAULT NULL,
    p_error_details JSONB DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    UPDATE processing_logs 
    SET 
        status = p_status,
        progress_percentage = COALESCE(p_progress, progress_percentage),
        message = COALESCE(p_message, message),
        error_details = COALESCE(p_error_details, error_details),
        metadata = CASE 
            WHEN p_metadata IS NOT NULL THEN 
                COALESCE(metadata, '{}'::jsonb) || p_metadata
            ELSE metadata
        END,
        completed_at = CASE 
            WHEN p_status IN ('completed', 'failed', 'cancelled') THEN NOW()
            ELSE completed_at
        END
    WHERE job_id = p_job_id
    AND status NOT IN ('completed', 'failed', 'cancelled'); -- Don't update already finished jobs
END;
$$ LANGUAGE plpgsql;

-- Function to create a new processing log entry
CREATE OR REPLACE FUNCTION create_processing_log(
    p_job_id UUID,
    p_video_id UUID,
    p_user_id UUID,
    p_operation_type VARCHAR(50),
    p_operation_subtype VARCHAR(50) DEFAULT NULL,
    p_message TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    log_id UUID;
BEGIN
    INSERT INTO processing_logs (
        job_id,
        video_id,
        user_id,
        operation_type,
        operation_subtype,
        message,
        metadata
    ) VALUES (
        p_job_id,
        p_video_id,
        p_user_id,
        p_operation_type,
        p_operation_subtype,
        p_message,
        p_metadata
    ) RETURNING id INTO log_id;
    
    RETURN log_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get processing statistics
CREATE OR REPLACE FUNCTION get_processing_stats(
    p_user_id UUID DEFAULT NULL,
    p_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    operation_type VARCHAR(50),
    total_operations BIGINT,
    successful_operations BIGINT,
    failed_operations BIGINT,
    avg_processing_time_ms NUMERIC,
    success_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pl.operation_type,
        COUNT(*) as total_operations,
        COUNT(*) FILTER (WHERE pl.status = 'completed') as successful_operations,
        COUNT(*) FILTER (WHERE pl.status = 'failed') as failed_operations,
        AVG(pl.processing_time_ms) as avg_processing_time_ms,
        ROUND(
            (COUNT(*) FILTER (WHERE pl.status = 'completed')::NUMERIC / COUNT(*)::NUMERIC) * 100, 
            2
        ) as success_rate
    FROM processing_logs pl
    WHERE 
        (p_user_id IS NULL OR pl.user_id = p_user_id)
        AND pl.created_at >= NOW() - INTERVAL '1 day' * p_days
        AND pl.status IN ('completed', 'failed')
    GROUP BY pl.operation_type
    ORDER BY total_operations DESC;
END;
$$ LANGUAGE plpgsql;

-- Create a view for recent processing activity
CREATE OR REPLACE VIEW recent_processing_activity AS
SELECT 
    id,
    job_id,
    video_id,
    user_id,
    operation_type,
    operation_subtype,
    status,
    progress_percentage,
    message,
    processing_time_ms,
    started_at,
    completed_at,
    created_at
FROM processing_logs
WHERE created_at >= NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;