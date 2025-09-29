-- Fix Security Definer View Issue
-- This migration addresses the Supabase Security Advisor warning about
-- the 'recent_processing_activity' view potentially using SECURITY DEFINER

-- Drop the existing view if it exists
DROP VIEW IF EXISTS recent_processing_activity;

-- Recreate the view with explicit SECURITY INVOKER (default, but explicit for clarity)
-- SECURITY INVOKER means the view executes with the privileges of the user calling it,
-- not the privileges of the view owner, which is more secure
CREATE VIEW recent_processing_activity
WITH (security_invoker = true)
AS
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

-- Grant appropriate permissions
-- Users can only see their own processing activity due to RLS on processing_logs table
GRANT SELECT ON recent_processing_activity TO authenticated;
GRANT SELECT ON recent_processing_activity TO anon;

-- Add a comment explaining the security model
COMMENT ON VIEW recent_processing_activity IS 
'View showing recent processing activity from the last 24 hours. '
'Uses SECURITY INVOKER to ensure users only see data they have permission to access '
'based on the underlying processing_logs table RLS policies.';

-- Verify the view is created correctly
-- This query can be used to check the view properties
-- SELECT 
--     schemaname,
--     viewname,
--     viewowner,
--     pg_get_viewdef(schemaname||'.'||viewname) as definition
-- FROM pg_views 
-- WHERE viewname = 'recent_processing_activity'
-- AND schemaname = 'public';