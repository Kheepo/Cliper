"""Supabase client configuration and utilities."""

import os
from typing import Optional
from supabase import create_client, Client
from functools import lru_cache
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

@lru_cache(maxsize=1)
def get_supabase_client() -> Optional[Client]:
    """Get Supabase client with anon key for frontend operations."""
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.error("Missing Supabase URL or anon key")
            return None
        
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None

@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Optional[Client]:
    """Get Supabase client with service role key for admin operations."""
    try:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            logger.error("Missing Supabase URL or service role key")
            return None
        
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase admin client: {e}")
        return None

def get_supabase_client_with_auth(access_token: str) -> Optional[Client]:
    """Get Supabase client with user access token."""
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.error("Missing Supabase URL or anon key")
            return None
        
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        # Set the auth token for this client instance
        client.auth.set_session(access_token, refresh_token=None)
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase client with auth: {e}")
        return None

def verify_supabase_connection() -> bool:
    """Verify Supabase connection is working."""
    try:
        client = get_supabase_client()
        if not client:
            return False
        
        # Try a simple query to verify connection
        response = client.table('users').select('id').limit(1).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase connection verification failed: {e}")
        return False