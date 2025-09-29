-- Initial database schema for video analysis application
-- Creates all the core tables with proper relationships and constraints

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (linked to Supabase Auth)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_id VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    photo_url TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- User settings table
CREATE TABLE user_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'light',
    language VARCHAR(10) DEFAULT 'en',
    notifications_enabled BOOLEAN DEFAULT true,
    email_notifications BOOLEAN DEFAULT true,
    auto_save_results BOOLEAN DEFAULT true,
    default_video_quality VARCHAR(20) DEFAULT 'high',
    max_concurrent_jobs INTEGER DEFAULT 3,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Jobs table (video analysis jobs)
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_type VARCHAR(20) NOT NULL CHECK (job_type IN ('upload', 'url')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    title VARCHAR(255),
    description TEXT,
    video_url TEXT,
    video_filename VARCHAR(255),
    video_size BIGINT,
    video_duration FLOAT,
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Job results table
CREATE TABLE job_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    virality_score FLOAT CHECK (virality_score >= 0 AND virality_score <= 100),
    engagement_metrics JSONB,
    hashtags TEXT[],
    suggested_clips JSONB,
    analysis_summary TEXT,
    thumbnail_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(job_id)
);

-- Job logs table
CREATE TABLE job_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    level VARCHAR(20) NOT NULL CHECK (level IN ('debug', 'info', 'warning', 'error', 'critical')),
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_users_auth_id ON users(auth_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
CREATE INDEX idx_job_results_job_id ON job_results(job_id);
CREATE INDEX idx_job_logs_job_id ON job_logs(job_id);
CREATE INDEX idx_job_logs_level ON job_logs(level);
CREATE INDEX idx_job_logs_created_at ON job_logs(created_at);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_job_results_updated_at BEFORE UPDATE ON job_results
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_logs ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
-- Users can only see their own data
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth_id = auth.uid()::text);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth_id = auth.uid()::text);

-- User settings policies
CREATE POLICY "Users can view own settings" ON user_settings
    FOR SELECT USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()::text));

CREATE POLICY "Users can update own settings" ON user_settings
    FOR UPDATE USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()::text));

CREATE POLICY "Users can insert own settings" ON user_settings
    FOR INSERT WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()::text));

-- Jobs policies
CREATE POLICY "Users can view own jobs" ON jobs
    FOR SELECT USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()::text));

CREATE POLICY "Users can create own jobs" ON jobs
    FOR INSERT WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()::text));

CREATE POLICY "Users can update own jobs" ON jobs
    FOR UPDATE USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()::text));

-- Job results policies
CREATE POLICY "Users can view own job results" ON job_results
    FOR SELECT USING (job_id IN (SELECT id FROM jobs WHERE user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()::text)));

CREATE POLICY "Service can insert job results" ON job_results
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Service can update job results" ON job_results
    FOR UPDATE USING (true);

-- Job logs policies
CREATE POLICY "Users can view own job logs" ON job_logs
    FOR SELECT USING (job_id IN (SELECT id FROM jobs WHERE user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()::text)));

CREATE POLICY "Service can insert job logs" ON job_logs
    FOR INSERT WITH CHECK (true);

-- Insert some sample data for testing
INSERT INTO users (auth_id, email, display_name) VALUES
    ('test-user-1', 'test@example.com', 'Test User'),
    ('test-user-2', 'demo@example.com', 'Demo User');

INSERT INTO user_settings (user_id, theme, language) VALUES
    ((SELECT id FROM users WHERE auth_id = 'test-user-1'), 'dark', 'en'),
    ((SELECT id FROM users WHERE auth_id = 'test-user-2'), 'light', 'en');

INSERT INTO jobs (user_id, job_type, status, title, description) VALUES
    ((SELECT id FROM users WHERE auth_id = 'test-user-1'), 'upload', 'completed', 'Sample Video Analysis', 'Test video for analysis'),
    ((SELECT id FROM users WHERE auth_id = 'test-user-1'), 'url', 'processing', 'YouTube Video Analysis', 'Analyzing viral video trends'),
    ((SELECT id FROM users WHERE auth_id = 'test-user-2'), 'upload', 'failed', 'Video analysis that failed');

INSERT INTO job_results (job_id, virality_score, hashtags, analysis_summary) VALUES
    ((SELECT id FROM jobs WHERE title = 'Sample Video Analysis'), 85.5, ARRAY['#viral', '#trending', '#entertainment'], 'High engagement potential with strong visual appeal');

INSERT INTO job_logs (job_id, level, message) VALUES
    ((SELECT id FROM jobs WHERE title = 'Sample Video Analysis'), 'info', 'Analysis started'),
    ((SELECT id FROM jobs WHERE title = 'Sample Video Analysis'), 'info', 'Video processing completed'),
    ((SELECT id FROM jobs WHERE title = 'YouTube Video Analysis'), 'info', 'URL validation successful'),
    ((SELECT id FROM jobs WHERE title = 'Failed Analysis'), 'error', 'Video format not supported');