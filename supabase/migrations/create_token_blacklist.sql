-- Create token_blacklist table for JWT token invalidation
CREATE TABLE IF NOT EXISTS token_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    user_id UUID NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key constraint (logical, not physical)
    CONSTRAINT fk_token_blacklist_user_id 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create index for faster token lookup
CREATE INDEX IF NOT EXISTS idx_token_blacklist_token_hash ON token_blacklist(token_hash);
CREATE INDEX IF NOT EXISTS idx_token_blacklist_user_id ON token_blacklist(user_id);
CREATE INDEX IF NOT EXISTS idx_token_blacklist_expires_at ON token_blacklist(expires_at);

-- Enable RLS
ALTER TABLE token_blacklist ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Users can only see their own blacklisted tokens
CREATE POLICY "Users can view own blacklisted tokens" ON token_blacklist
    FOR SELECT USING (auth.uid()::text = user_id::text);

-- Only authenticated users can insert blacklist entries
CREATE POLICY "Authenticated users can blacklist tokens" ON token_blacklist
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- Users can only delete their own blacklisted tokens (for cleanup)
CREATE POLICY "Users can delete own blacklisted tokens" ON token_blacklist
    FOR DELETE USING (auth.uid()::text = user_id::text);

-- Grant permissions to roles
GRANT SELECT, INSERT, DELETE ON token_blacklist TO authenticated;
GRANT SELECT ON token_blacklist TO anon;

-- Create function to clean up expired tokens
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM token_blacklist 
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission on cleanup function
GRANT EXECUTE ON FUNCTION cleanup_expired_tokens() TO authenticated;

-- Add comment for documentation
COMMENT ON TABLE token_blacklist IS 'Stores invalidated JWT tokens to prevent reuse after logout';
COMMENT ON COLUMN token_blacklist.token_hash IS 'SHA256 hash of the JWT token for security';
COMMENT ON COLUMN token_blacklist.expires_at IS 'When the token naturally expires (from JWT exp claim)';
COMMENT ON FUNCTION cleanup_expired_tokens() IS 'Removes expired tokens from blacklist to keep table size manageable';