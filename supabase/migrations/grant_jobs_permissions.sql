-- Grant permissions for jobs table to authenticated users
GRANT ALL PRIVILEGES ON jobs TO authenticated;
GRANT SELECT ON jobs TO anon;

-- Also ensure sequence permissions if needed
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon;

-- Note: Verification query removed as it's not needed in migration