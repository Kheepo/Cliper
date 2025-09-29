-- Create authentication and application schema
-- Based on virality_clipper_architecture.md

-- Enable Row Level Security
ALTER DATABASE postgres SET row_security = on;

-- Create USERS table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'free' CHECK (role IN ('free', 'premium', 'admin')),
    subscription_status VARCHAR(50) DEFAULT 'active' CHECK (subscription_status IN ('active', 'inactive', 'cancelled')),
    subscription_end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    profile_picture_url TEXT
);

-- Create JOBS table
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN ('video_upload', 'url_processing')),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    current_step VARCHAR(255),
    estimated_remaining FLOAT DEFAULT 0,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create VIDEOS table
CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    original_filename VARCHAR(255),
    file_path TEXT NOT NULL,
    file_size BIGINT,
    duration FLOAT,
    format VARCHAR(50),
    resolution VARCHAR(20),
    fps FLOAT,
    source_url TEXT,
    thumbnail_path TEXT,
    transcript TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create CLIPS table
CREATE TABLE IF NOT EXISTS clips (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    start_time INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    overall_virality_score FLOAT DEFAULT 0,
    transcript TEXT,
    thumbnail_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create VIRALITY_SCORES table
CREATE TABLE IF NOT EXISTS virality_scores (
    id SERIAL PRIMARY KEY,
    clip_id INTEGER REFERENCES clips(id) ON DELETE CASCADE,
    niche VARCHAR(100) NOT NULL,
    score FLOAT NOT NULL CHECK (score >= 0 AND score <= 100),
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create HASHTAGS table
CREATE TABLE IF NOT EXISTS hashtags (
    id SERIAL PRIMARY KEY,
    clip_id INTEGER REFERENCES clips(id) ON DELETE CASCADE,
    tag VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('tiktok', 'instagram', 'youtube', 'twitter', 'linkedin')),
    relevance_score FLOAT DEFAULT 0 CHECK (relevance_score >= 0 AND relevance_score <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create POSTING_RECOMMENDATIONS table
CREATE TABLE IF NOT EXISTS posting_recommendations (
    id SERIAL PRIMARY KEY,
    clip_id INTEGER REFERENCES clips(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('tiktok', 'instagram', 'youtube', 'twitter', 'linkedin')),
    optimal_times JSONB DEFAULT '[]',
    format_suggestions JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_job_id ON videos(job_id);
CREATE INDEX IF NOT EXISTS idx_clips_video_id ON clips(video_id);
CREATE INDEX IF NOT EXISTS idx_clips_user_id ON clips(user_id);
CREATE INDEX IF NOT EXISTS idx_virality_scores_clip_id ON virality_scores(clip_id);
CREATE INDEX IF NOT EXISTS idx_hashtags_clip_id ON hashtags(clip_id);
CREATE INDEX IF NOT EXISTS idx_posting_recommendations_clip_id ON posting_recommendations(clip_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_clips_updated_at BEFORE UPDATE ON clips FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE clips ENABLE ROW LEVEL SECURITY;
ALTER TABLE virality_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE hashtags ENABLE ROW LEVEL SECURITY;
ALTER TABLE posting_recommendations ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
-- Users can only see their own data
CREATE POLICY "Users can view own profile" ON users FOR SELECT USING (auth.uid()::text = id::text);
CREATE POLICY "Users can update own profile" ON users FOR UPDATE USING (auth.uid()::text = id::text);

-- Jobs policies
CREATE POLICY "Users can view own jobs" ON jobs FOR SELECT USING (auth.uid()::text = user_id::text);
CREATE POLICY "Users can insert own jobs" ON jobs FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY "Users can update own jobs" ON jobs FOR UPDATE USING (auth.uid()::text = user_id::text);

-- Videos policies
CREATE POLICY "Users can view own videos" ON videos FOR SELECT USING (auth.uid()::text = user_id::text);
CREATE POLICY "Users can insert own videos" ON videos FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY "Users can update own videos" ON videos FOR UPDATE USING (auth.uid()::text = user_id::text);

-- Clips policies
CREATE POLICY "Users can view own clips" ON clips FOR SELECT USING (auth.uid()::text = user_id::text);
CREATE POLICY "Users can insert own clips" ON clips FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY "Users can update own clips" ON clips FOR UPDATE USING (auth.uid()::text = user_id::text);

-- Virality scores policies
CREATE POLICY "Users can view virality scores for own clips" ON virality_scores FOR SELECT USING (
    EXISTS (SELECT 1 FROM clips WHERE clips.id = virality_scores.clip_id AND auth.uid()::text = clips.user_id::text)
);
CREATE POLICY "Users can insert virality scores for own clips" ON virality_scores FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM clips WHERE clips.id = virality_scores.clip_id AND auth.uid()::text = clips.user_id::text)
);

-- Hashtags policies
CREATE POLICY "Users can view hashtags for own clips" ON hashtags FOR SELECT USING (
    EXISTS (SELECT 1 FROM clips WHERE clips.id = hashtags.clip_id AND auth.uid()::text = clips.user_id::text)
);
CREATE POLICY "Users can insert hashtags for own clips" ON hashtags FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM clips WHERE clips.id = hashtags.clip_id AND auth.uid()::text = clips.user_id::text)
);

-- Posting recommendations policies
CREATE POLICY "Users can view posting recommendations for own clips" ON posting_recommendations FOR SELECT USING (
    EXISTS (SELECT 1 FROM clips WHERE clips.id = posting_recommendations.clip_id AND auth.uid()::text = clips.user_id::text)
);
CREATE POLICY "Users can insert posting recommendations for own clips" ON posting_recommendations FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM clips WHERE clips.id = posting_recommendations.clip_id AND auth.uid()::text = clips.user_id::text)
);

-- Grant permissions to anon and authenticated roles
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated, anon;

-- Insert sample data for virality scores niches
INSERT INTO virality_scores (clip_id, niche, score, explanation) VALUES 
(1, 'Gaming', 85.5, 'High engagement potential in gaming community'),
(1, 'Tech Reviews', 78.2, 'Strong appeal for tech enthusiasts'),
(1, 'Entertainment', 92.1, 'Excellent viral potential for general entertainment')
ON CONFLICT DO NOTHING;

-- Create function to handle user registration
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, email, full_name, created_at, updated_at)
    VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name', NOW(), NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger for new user registration
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

COMMIT;