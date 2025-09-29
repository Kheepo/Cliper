import logging
import asyncio
from typing import Optional, Dict, Any, Union
from fastapi import HTTPException, status, Depends, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import os
from datetime import datetime, timezone
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from api.utils.supabase_client import get_supabase_admin_client
from api.models.database_models import User

# Make supabase available for tests
supabase = get_supabase_admin_client()

logger = logging.getLogger(__name__)

# User cache for performance optimization
user_cache: Dict[str, Dict[str, Any]] = {}

def clear_user_cache() -> None:
    """Clear the user cache"""
    global user_cache
    user_cache.clear()

def get_cached_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user from cache if available and not expired"""
    if user_id in user_cache:
        cached_data = user_cache[user_id]
        cache_time = cached_data.get('timestamp')
        ttl = cached_data.get('ttl', 300)
        
        if cache_time:
            # Ensure both timestamps are timezone-aware
            if cache_time.tzinfo is None:
                cache_time = cache_time.replace(tzinfo=timezone.utc)
            
            current_time = datetime.now(timezone.utc)
            if (current_time - cache_time).total_seconds() < ttl:
                return cached_data.get('data')
            else:
                # Remove expired cache entry
                del user_cache[user_id]
    return None

def validate_jwt_structure(payload: Dict[str, Any]) -> bool:
    """Validate JWT payload structure and required fields"""
    required_fields = ['sub', 'email', 'aud', 'exp']
    
    for field in required_fields:
        if field not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Missing required field: {field}",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    # Check if token is expired
    exp = payload.get('exp')
    if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check audience
    aud = payload.get('aud')
    if aud not in ['authenticated', 'anon']:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid audience",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return True

async def enrich_user_data(jwt_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich JWT payload with user profile and settings data with caching"""
    try:
        user_id = jwt_payload.get('sub')
        
        # Check cache first
        cached_user = get_cached_user(user_id)
        if cached_user:
            return cached_user
        
        enriched_data = {
            'id': user_id,
            'email': jwt_payload.get('email'),
            'jwt_payload': jwt_payload
        }
        
        # Try to get user profile
        try:
            profile_response = supabase.table('users').select('*').eq('auth_id', user_id).single().execute()
            if profile_response.data:
                enriched_data['profile'] = profile_response.data
            else:
                enriched_data['profile'] = None
        except Exception as e:
            logger.warning(f"Could not fetch user profile: {str(e)}")
            enriched_data['profile'] = None
        
        # Try to get user settings
        try:
            settings_response = supabase.table('user_settings').select('*').eq('user_id', user_id).maybe_single().execute()
            if settings_response.data:
                enriched_data['settings'] = settings_response.data
            else:
                enriched_data['settings'] = None
        except Exception as e:
            logger.warning(f"Could not fetch user settings: {str(e)}")
            enriched_data['settings'] = None
        
        # Cache the enriched data
        user_cache[user_id] = {
            'data': enriched_data,
            'timestamp': datetime.now(timezone.utc)
        }
        
        return enriched_data
        
    except Exception as e:
        logger.error(f"Error enriching user data: {str(e)}")
        return {
            'id': jwt_payload.get('sub'),
            'email': jwt_payload.get('email'),
            'jwt_payload': jwt_payload,
            'profile': None,
            'settings': None
        }

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)

class JWTMiddleware:
    """JWT Middleware for FastAPI authentication"""
    
    def __init__(self):
        self.supabase = get_supabase_admin_client()
        self.jwt_secret = os.getenv('SUPABASE_JWT_SECRET')
        
        # Cache for user data to reduce database calls
        self._user_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
    
    def _validate_jwt_structure(self, token: str) -> bool:
        """Validate JWT token structure and basic claims"""
        try:
            # Decode without verification to check structure
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Check required claims
            required_claims = ['sub', 'exp', 'iat']
            if not all(claim in payload for claim in required_claims):
                return False
            
            # Check if token is expired
            exp = payload.get('exp')
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                return False
            
            return True
            
        except (InvalidTokenError, ExpiredSignatureError, ValueError) as e:
            logger.warning(f"JWT validation failed: {str(e)}")
            return False
    
    def _get_cached_user(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user from cache if available and not expired"""
        if token in self._user_cache:
            cached_data = self._user_cache[token]
            if datetime.now(timezone.utc).timestamp() - cached_data['cached_at'] < self._cache_ttl:
                return cached_data['user_data']
            else:
                # Remove expired cache entry
                del self._user_cache[token]
        return None
    
    def _cache_user(self, token: str, user_data: Dict[str, Any]) -> None:
        """Cache user data with timestamp"""
        self._user_cache[token] = {
            'user_data': user_data,
            'cached_at': datetime.now(timezone.utc).timestamp()
        }
        
        # Clean old cache entries (keep only last 100)
        if len(self._user_cache) > 100:
            oldest_tokens = sorted(self._user_cache.keys(), 
                                 key=lambda k: self._user_cache[k]['cached_at'])[:50]
            for old_token in oldest_tokens:
                del self._user_cache[old_token]

    async def authenticate_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """Authenticate request using Supabase JWT token with enhanced validation"""
        try:
            # Get authorization header
            authorization = request.headers.get('Authorization')
            
            if not authorization:
                return None
            
            # Extract token from Bearer header
            if not authorization.startswith('Bearer '):
                return None
            
            token = authorization.split(' ')[1]
            
            # First validate JWT structure and expiration
            if not self._validate_jwt_structure(token):
                logger.warning("Invalid JWT structure")
                return None
            
            # Check cache first
            cached_user = self._get_cached_user(token)
            if cached_user:
                return cached_user
            
            # Verify token with Supabase
            try:
                user_response = self.supabase.auth.get_user(token)
                if user_response and user_response.user:
                    user_data = {
                        'sub': user_response.user.id,
                        'uid': user_response.user.id,
                        'email': user_response.user.email,
                        'user_metadata': user_response.user.user_metadata,
                        'token': token,
                        'role': user_response.user.user_metadata.get('role', 'free'),
                        'email_verified': user_response.user.email_confirmed_at is not None,
                        'last_sign_in': user_response.user.last_sign_in_at
                    }
                    
                    # Cache the user data
                    self._cache_user(token, user_data)
                    return user_data
            except Exception:
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error during request authentication: {str(e)}")
            return None

    async def get_current_user(self, request: Request) -> Optional[Dict[str, Any]]:
        """Get current authenticated user with enhanced context"""
        user_data = await self.authenticate_request(request)
        if not user_data:
            return None
        
        # Enrich user data with profile information from database
        try:
            profile_response = self.supabase.table('users').select('*').eq('auth_id', user_data['uid']).execute()
            if profile_response.data:
                user_data['profile'] = profile_response.data[0]
                # Add database user ID for relationships
                user_data['db_user_id'] = profile_response.data[0]['id']
        except Exception as e:
            logger.warning(f"Could not fetch user profile: {str(e)}")
        
        return user_data

# Global middleware instance
jwt_middleware = JWTMiddleware()

async def get_supabase_token_info(request: Request) -> Optional[Dict[str, Any]]:
    """Get Supabase token info from request (optional) with caching"""
    try:
        # Extract token from authorization header
        authorization = request.headers.get('Authorization') or request.headers.get('authorization')
        if not authorization or not authorization.startswith('Bearer '):
            return None
        
        token = authorization.split(' ')[1]
        
        # Decode JWT without verification to get payload
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            validate_jwt_structure(payload)
            return payload
        except (InvalidTokenError, ExpiredSignatureError) as e:
            logger.warning(f"JWT validation failed: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting token info: {str(e)}")
        return None

async def require_supabase_token_info(request: Request) -> Dict[str, Any]:
    """Get Supabase token info from request (required) with enhanced validation"""
    token_info = await get_supabase_token_info(request)
    if not token_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid Supabase token required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Additional validation for email verification if required
    if not token_info.get('email_verified', False):
        logger.warning(f"Unverified email access attempt: {token_info.get('email')}")
    
    return token_info

async def require_current_user_from_token_info(request: Request) -> Dict[str, Any]:
    """Get current user from request (required) with enhanced error handling"""
    user_data = await get_current_user(request)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user_data

def get_supabase_token_info_sync(request: Request) -> Optional[Dict[str, Any]]:
    """Synchronous version of get_supabase_token_info for backward compatibility"""
    try:
        return asyncio.run(get_supabase_token_info(request))
    except Exception as e:
        logger.error(f"Error getting token info: {str(e)}")
        return None

def require_supabase_token_info_sync(request: Request) -> Dict[str, Any]:
    """Synchronous version of require_supabase_token_info for backward compatibility"""
    token_info = get_supabase_token_info_sync(request)
    if not token_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Additional validation for email verification if required
    if not token_info.get('email_verified', False):
        logger.warning(f"Unverified email access attempt: {token_info.get('email')}")
    
    return token_info

def require_current_user_from_token_info_sync(token_info: Dict[str, Any]) -> Dict[str, Any]:
    """Get current user from token info (required) with enhanced error handling (sync version)"""
    if not token_info or not token_info.get('uid'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Get user from database with retry logic
    try:
        # User import already available at module level
        
        supabase = get_supabase_admin_client()
        # Query user from Supabase
        response = supabase.table('users').select('*').eq('auth_id', token_info['uid']).execute()
        
        if not response.data:
            user = None
        else:
            user_data = response.data[0]
            # Create a user-like object for compatibility
            class UserObj:
                def __init__(self, data):
                    self.id = data.get('id')
                    self.auth_id = data.get('auth_id')
                    self.email = data.get('email')
                    self.display_name = data.get('display_name')
                    self.created_at = data.get('created_at')
                    self.updated_at = data.get('updated_at')
                    self.is_active = data.get('is_active', True)
            user = UserObj(user_data)
        
        if not user:
            # Log the missing user for debugging
            logger.warning(f"User not found in database: auth_id={token_info['uid']}, email={token_info.get('email')}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found. Please complete registration."
            )
        
        # Return enriched user data
        user_data = {
            'id': user.id,
            'auth_id': user.auth_id,
            'email': user.email,
            'display_name': user.display_name,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'updated_at': user.updated_at.isoformat() if user.updated_at else None,
            'role': token_info.get('role', 'free'),
            'email_verified': token_info.get('email_verified', False),
            'is_active': user.is_active
        }
        
        # Add profile data if available from token
        if 'profile' in token_info:
            user_data['profile'] = token_info['profile']
        
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user from database: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user information"
        )

async def get_current_user(request: Request = None) -> Optional[Dict[str, Any]]:
    """FastAPI dependency to get current user (optional)"""
    if not request:
        return None
    
    try:
        # Extract token from authorization header
        authorization = request.headers.get('Authorization') or request.headers.get('authorization')
        if not authorization or not authorization.startswith('Bearer '):
            return None
        
        token = authorization.split(' ')[1]
        
        # Decode JWT without verification to get payload
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            validate_jwt_structure(payload)
            
            # Check cache first
            user_id = payload.get('sub')
            cached_user = get_cached_user(user_id)
            if cached_user:
                return cached_user
            
            # Enrich user data
            enriched_data = await enrich_user_data(payload)
            
            # Cache the enriched data
            user_cache[user_id] = {
                'data': enriched_data,
                'timestamp': datetime.now(timezone.utc),
                'ttl': 300
            }
            
            return enriched_data
            
        except (InvalidTokenError, ExpiredSignatureError) as e:
            logger.warning(f"JWT validation failed: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None

def get_current_user_sync(request: Request = None) -> Optional[Dict[str, Any]]:
    """Synchronous version of get_current_user for backward compatibility"""
    if not request:
        return None
    
    try:
        return asyncio.run(get_current_user(request))
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None

# Legacy async function - kept for backward compatibility
async def get_current_user_async(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Get current authenticated user from token (async version)"""
    
    if not credentials:
        return None
    
    try:
        supabase = get_supabase_admin_client()
        
        # Verify token with Supabase
        try:
            user_response = supabase.auth.get_user(credentials.credentials)
            if not user_response or not user_response.user:
                return None
        except Exception:
            return None
        
        # Get user from database
        auth_id = user_response.user.id
        response = supabase.table('users').select('*').eq('auth_id', auth_id).execute()
        
        if not response.data:
            user = None
        else:
            user_data = response.data[0]
            # Create a user-like object for compatibility
            class UserObj:
                def __init__(self, data):
                    self.id = data.get('id')
                    self.auth_id = data.get('auth_id')
                    self.email = data.get('email')
                    self.display_name = data.get('display_name')
                    self.created_at = data.get('created_at')
                    self.updated_at = data.get('updated_at')
                    self.is_active = data.get('is_active', True)
            user = UserObj(user_data)
        
        return user
        
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None

def get_current_user_required(request: Request) -> Dict[str, Any]:
    """FastAPI dependency to get current user (required)"""
    try:
        user = asyncio.run(jwt_middleware.get_current_user(request))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        )

# Create global instance for dependency injection
jwt_middleware = JWTMiddleware()

# Supabase token info functions


async def get_supabase_token_info_optional(
    authorization: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[Dict[str, Any]]:
    """Get Supabase token info without requiring authentication"""
    if not authorization:
        return None
    
    try:
        supabase = get_supabase_admin_client()
        token = authorization.credentials
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            return {
                'sub': user_response.user.id,
                'uid': user_response.user.id,
                'email': user_response.user.email,
                'user_metadata': user_response.user.user_metadata
            }
        return None
    except Exception:
        return None

async def get_supabase_token_info_from_credentials(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get Supabase token information without database lookup"""
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        supabase = get_supabase_admin_client()
        
        # Verify token with Supabase
        user_response = supabase.auth.get_user(credentials.credentials)
        
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {
            'sub': user_response.user.id,
            'uid': user_response.user.id,
            'email': user_response.user.email,
            'user_metadata': user_response.user.user_metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting token info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

async def get_current_user_required_async(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info_from_credentials)
) -> User:
    """Get current user from token info (required) - async version"""
    supabase_uid = token_info.get('uid') or token_info.get('sub')
    
    if not supabase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing uid"
        )
    
    # Get user from database
    supabase = get_supabase_admin_client()
    response = supabase.table('users').select('*').eq('auth_id', supabase_uid).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user_data = response.data[0]
    # Create a user-like object for compatibility
    class UserObj:
        def __init__(self, data):
            self.id = data.get('id')
            self.auth_id = data.get('auth_id')
            self.email = data.get('email')
            self.display_name = data.get('display_name')
            self.created_at = data.get('created_at')
            self.updated_at = data.get('updated_at')
            self.is_active = data.get('is_active', True)
    user = UserObj(user_data)
    
    return user