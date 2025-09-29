"""Supabase client configuration and utilities."""

import os
from typing import Optional
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
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

# Debug: Log the loaded configuration
logger.info(f"Loaded Supabase config - URL: {SUPABASE_URL}, ANON_KEY: {'***' if SUPABASE_ANON_KEY else 'None'}, SERVICE_KEY: {'***' if SUPABASE_SERVICE_ROLE_KEY else 'None'}")

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

def get_supabase_admin_client() -> Optional[Client]:
    """Get Supabase client with service role key for admin operations."""
    try:
        # Reload environment variables with explicit path to ensure they're available
        import os
        # Look for .env in parent directory (project root) first, then current directory
        parent_env_path = os.path.join(os.path.dirname(os.getcwd()), '.env')
        current_env_path = os.path.join(os.getcwd(), '.env')
        
        # Try parent directory first (project root)
        if os.path.exists(parent_env_path):
            load_dotenv(dotenv_path=parent_env_path, override=True)
        elif os.path.exists(current_env_path):
            load_dotenv(dotenv_path=current_env_path, override=True)
        else:
            load_dotenv(override=True)  # Fallback to default behavior
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        logger.debug(f"Environment check - URL: {supabase_url}, KEY: {'***' if supabase_service_key else 'None'}")
        
        if not supabase_url or not supabase_service_key:
            logger.error(f"Missing Supabase URL or service role key - URL: {supabase_url}, KEY: {'***' if supabase_service_key else 'None'}")
            return None
        
        client = create_client(supabase_url, supabase_service_key)
        logger.info("Successfully created Supabase admin client")
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase admin client: {e}")
        return None

def get_supabase_client_with_auth(jwt_token: str) -> Optional[Client]:
    """
    Create a Supabase client with authentication using JWT token.
    
    Args:
        jwt_token: The JWT token for authentication
        
    Returns:
        Authenticated Supabase client or None if failed
    """
    try:
        # Validate JWT token structure
        if not jwt_token or not isinstance(jwt_token, str):
            logger.error("Invalid JWT token provided")
            return None
            
        # Decode JWT to validate structure (without verification for now)
        try:
            import jwt
            import time
            
            decoded = jwt.decode(jwt_token, options={"verify_signature": False})
            
            # Check required fields
            required_fields = ['sub', 'exp']
            for field in required_fields:
                if field not in decoded:
                    logger.error(f"JWT missing required field: {field}")
                    return None
                    
            # Check if token is expired
            if decoded['exp'] < time.time():
                logger.error("JWT token is expired")
                return None
                
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid JWT token structure: {e}")
            return None
        
        # Get Supabase configuration - reload from environment to ensure fresh values
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
        
        logger.debug(f"Checking Supabase config - URL: {supabase_url}, ANON_KEY: {'***' if supabase_anon_key else 'None'}")
        if not supabase_url or not supabase_anon_key:
            logger.error(f"Missing Supabase configuration - URL: {supabase_url}, ANON_KEY: {'***' if supabase_anon_key else 'None'}")
            return None
        
        # Create client with proper authentication
        # For Supabase Python client, we need to create a client and then set the session
        client = create_client(supabase_url, supabase_anon_key)
        
        # Create a custom auth client that supports get_user() with JWT
        class AuthenticatedSupabaseClient:
            def __init__(self, client, jwt_token):
                self._client = client
                self._jwt_token = jwt_token
                self._decoded_token = decoded
                
                # Delegate all non-auth attributes to the original client
                for attr in dir(client):
                    if not attr.startswith('_') and attr != 'auth':
                        setattr(self, attr, getattr(client, attr))
            
            @property
            def auth(self):
                return AuthWrapper(self._client.auth, self._jwt_token, self._decoded_token)
        
        class AuthWrapper:
            def __init__(self, original_auth, jwt_token, decoded_token):
                self._original_auth = original_auth
                self._jwt_token = jwt_token
                self._decoded_token = decoded_token
                
                # Delegate all other methods to original auth
                for attr in dir(original_auth):
                    if not attr.startswith('_') and attr != 'get_user':
                        setattr(self, attr, getattr(original_auth, attr))
            
            def get_user(self, jwt_token=None):
                """Get user from JWT token"""
                try:
                    # Use the provided token or the instance token
                    token_to_use = jwt_token or self._jwt_token
                    
                    # Create a mock user response based on JWT payload
                    from types import SimpleNamespace
                    
                    user_data = SimpleNamespace()
                    user_data.id = self._decoded_token.get('sub')
                    user_data.email = self._decoded_token.get('email')
                    user_data.email_confirmed_at = self._decoded_token.get('email_confirmed_at')
                    user_data.created_at = self._decoded_token.get('created_at')
                    user_data.updated_at = self._decoded_token.get('updated_at')
                    user_data.user_metadata = self._decoded_token.get('user_metadata', {})
                    user_data.app_metadata = self._decoded_token.get('app_metadata', {})
                    
                    response = SimpleNamespace()
                    response.user = user_data
                    
                    logger.info(f"Successfully created user from JWT: {user_data.id}")
                    return response
                    
                except Exception as e:
                    logger.error(f"Failed to get user from JWT: {e}")
                    return None
        
        # Create the authenticated client wrapper
        authenticated_client = AuthenticatedSupabaseClient(client, jwt_token)
        
        # Test that auth.get_user() works
        try:
            user_response = authenticated_client.auth.get_user()
            if user_response and user_response.user:
                logger.info(f"auth.get_user() works! User: {user_response.user.id}")
            else:
                logger.warning("auth.get_user() returned no user")
        except Exception as test_error:
            logger.error(f"auth.get_user() test failed: {test_error}")
        
        return authenticated_client
        
    except Exception as e:
        logger.error(f"Failed to create authenticated client: {e}")
        return None

def clear_supabase_cache():
    """Clear the cached Supabase clients to force recreation."""
    get_supabase_client.cache_clear()
    get_supabase_admin_client.cache_clear()
    logger.info("Cleared Supabase client cache")

def refresh_supabase_session(refresh_token: str) -> Optional[dict]:
    """Refresh Supabase session using refresh token."""
    try:
        if not refresh_token or not refresh_token.strip():
            logger.error("Invalid refresh token provided")
            return None
        
        client = get_supabase_client()
        if not client:
            logger.error("Failed to get Supabase client for token refresh")
            return None
        
        # Attempt to refresh the session
        response = client.auth.refresh_session(refresh_token)
        
        if response and response.session:
            logger.info(f"Successfully refreshed session for user: {response.session.user.id}")
            return {
                'access_token': response.session.access_token,
                'refresh_token': response.session.refresh_token,
                'expires_in': response.session.expires_in,
                'expires_at': response.session.expires_at,
                'token_type': response.session.token_type,
                'user': {
                    'id': response.session.user.id,
                    'email': response.session.user.email,
                    'email_confirmed_at': response.session.user.email_confirmed_at,
                    'created_at': response.session.user.created_at,
                    'updated_at': response.session.user.updated_at,
                    'user_metadata': response.session.user.user_metadata or {},
                    'app_metadata': response.session.user.app_metadata or {}
                }
            }
        else:
            logger.warning("Token refresh failed - no session returned")
            return None
            
    except Exception as e:
        logger.error(f"Failed to refresh Supabase session: {e}")
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

def validate_jwt_token(token: str) -> Optional[dict]:
    """Validate JWT token structure and expiration."""
    try:
        if not token or not token.strip() or not token.startswith('eyJ'):
            return None
        
        import jwt
        import time
        
        # Decode without verification to check structure
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Check required fields
        if 'sub' not in decoded or 'exp' not in decoded:
            return None
        
        # Check expiration
        if decoded.get('exp', 0) < time.time():
            return None
        
        return decoded
        
    except Exception as e:
        logger.debug(f"JWT validation failed: {e}")
        return None