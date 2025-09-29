"""Supabase configuration and client setup."""

import os
from supabase import create_client, Client
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration - load from environment variables with fallback
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://stzdywhbdovjojtqxmsd.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0emR5d2hiZG92am9qdHF4bXNkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc1NDA1NjgsImV4cCI6MjA3MzExNjU2OH0.R7GzJ18oGs4JQMBqdoq8h3jH_FQr4W8d0xJ_Wf9Hzm8")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0emR5d2hiZG92am9qdHF4bXNkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzU0MDU2OCwiZXhwIjoyMDczMTE2NTY4fQ.Xg6iDR-YMjID73OzQfJ362B-xYBadJeb6Qh2NxVtAmU")

# Global Supabase clients
_supabase_client: Optional[Client] = None
_supabase_admin_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """Get Supabase client with anon key for frontend operations."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase_client

def get_supabase_admin_client() -> Client:
    """Get Supabase client with service role key for admin operations."""
    global _supabase_admin_client
    if _supabase_admin_client is None:
        _supabase_admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_admin_client

def get_supabase_client_with_auth(access_token: str) -> Client:
    """Get Supabase client with user authentication token."""
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.auth.set_session(access_token, refresh_token=None)
    return client

def test_connection() -> bool:
    """Test Supabase connection."""
    try:
        client = get_supabase_client()
        # Try to query a table to test connection
        result = client.table('users').select('id').limit(1).execute()
        return True
    except Exception as e:
        print(f"Supabase connection test failed: {e}")
        return False