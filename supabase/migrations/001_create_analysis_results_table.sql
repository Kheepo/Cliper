-- Create analysis_results table
CREATE TABLE IF NOT EXISTS analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    user_id UUID NOT NULL,
    analysis_type VARCHAR(50) NOT NULL, -- 'speech', 'scene', 'emotion', 'face', 'viral_score'
    analysis_data JSONB NOT NULL,
    confidence_score DECIMAL(5,3),
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_analysis_results_video_id ON analysis_results(video_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_user_id ON analysis_results(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_type ON analysis_results(analysis_type);
CREATE INDEX IF NOT EXISTS idx_analysis_results_created_at ON analysis_results(created_at);
CREATE INDEX IF NOT EXISTS idx_analysis_results_confidence ON analysis_results(confidence_score);

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_analysis_results_video_type ON analysis_results(video_id, analysis_type);

-- Enable Row Level Security
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own analysis results" ON analysis_results
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own analysis results" ON analysis_results
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own analysis results" ON analysis_results
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own analysis results" ON analysis_results
    FOR DELETE USING (auth.uid() = user_id);

-- Grant permissions to authenticated users
GRANT ALL PRIVILEGES ON analysis_results TO authenticated;
GRANT SELECT ON analysis_results TO anon;

-- Add trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_analysis_results_updated_at
    BEFORE UPDATE ON analysis_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();