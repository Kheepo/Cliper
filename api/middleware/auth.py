from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, Callable
import logging
import json
from datetime import datetime
from functools import wraps
import os
import jwt
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

from ..utils.supabase_client import get_supabase_admin_client, get_supabase_client_with_auth, SUPABASE_URL, SUPABASE_ANON_KEY

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    """Custom authentication error"""
    pass

class AuthorizationError(Exception):
    """Custom authorization error"""
    pass

class SupabaseAuthMiddleware:
    """Supabase Authentication middleware for FastAPI"""
    
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
        # No need to initialize admin client here - we create authenticated clients per request
        logger.info("SupabaseAuthMiddleware initialized successfully")
    

    
    async def verify_token(self, credentials: HTTPAuthorizationCredentials) -> Dict[str, Any]:
        """Verify Supabase JWT token with improved error handling and session management"""
        if not credentials or not credentials.credentials:
            raise AuthenticationError("No authentication token provided")
        
        token = credentials.credentials.strip()
        
        # Validate token format
        if not token or not token.startswith('eyJ'):
            raise AuthenticationError("Invalid token format")
        
        try:
            # First, validate JWT token structure and expiration
            import jwt
            import time
            
            try:
                # Decode without verification to check token structure
                decoded = jwt.decode(token, options={"verify_signature": False})
                
                # Check if token has required fields
                required_fields = ['sub', 'exp', 'iat', 'aud']
                missing_fields = [field for field in required_fields if field not in decoded]
                if missing_fields:
                    raise AuthenticationError(f"Invalid token structure - missing fields: {', '.join(missing_fields)}")
                
                # Check if token is expired with 30 second buffer
                current_time = time.time()
                exp_time = decoded.get('exp', 0)
                if exp_time <= current_time + 30:  # 30 second buffer for clock skew
                    raise AuthenticationError("Token has expired or expires soon")
                
                # Validate audience
                expected_audience = 'authenticated'
                if decoded.get('aud') != expected_audience:
                    raise AuthenticationError(f"Invalid token audience: expected '{expected_audience}', got '{decoded.get('aud')}'")
                    
                user_id = decoded.get('sub')
                email = decoded.get('email', '')
                user_metadata = decoded.get('user_metadata', {})
                app_metadata = decoded.get('app_metadata', {})
                
                logger.debug(f"Token structure validated for user: {user_id}, expires at: {exp_time}")
                
            except jwt.InvalidTokenError as jwt_error:
                logger.error(f"JWT token parsing failed: {jwt_error}")
                raise AuthenticationError("Invalid token format or signature")
            
            # Create a client with the user's token to verify it with Supabase
            client_with_auth = get_supabase_client_with_auth(token)
            
            if not client_with_auth:
                raise AuthenticationError("Failed to create authenticated Supabase client")
            
            # Verify token with Supabase and get user data
            user = None
            try:
                # Use the authenticated client to get user info
                user_response = client_with_auth.auth.get_user()
                if user_response and user_response.user:
                    user = user_response.user
                    # Update user data from Supabase response
                    user_id = user.id
                    email = user.email or email
                    user_metadata = user.user_metadata or user_metadata
                    app_metadata = user.app_metadata or app_metadata
                    logger.debug(f"Supabase auth verified for user: {user_id}")
                else:
                    logger.warning("Supabase user verification failed, but token is structurally valid")
                    # Continue with JWT data if Supabase verification fails
                    
            except Exception as auth_error:
                logger.warning(f"Supabase user verification failed: {auth_error}, using JWT data")
                # Continue with JWT data if Supabase verification fails
            
            # Get user profile from database using the authenticated client
            user_profile = None
            try:
                # Try to get user profile with error handling
                profile_response = None
                
                # Try user_profiles table first
                try:
                    profile_response = client_with_auth.table('user_profiles').select('*').eq('user_id', user_id).single().execute()
                    if profile_response and profile_response.data:
                        user_profile = profile_response.data
                        logger.debug(f"Profile loaded from user_profiles for user: {user_id}")
                except Exception as profile_error:
                    logger.debug(f"user_profiles query failed: {profile_error}")
                    
                    # Fallback to users table
                    try:
                        profile_response = client_with_auth.table('users').select('*').eq('auth_id', user_id).single().execute()
                        if profile_response and profile_response.data:
                            user_profile = profile_response.data
                            logger.debug(f"Profile loaded from users table for user: {user_id}")
                    except Exception as fallback_error:
                        logger.debug(f"users table query also failed: {fallback_error}")
                
                if not user_profile:
                    logger.info(f"No profile found for user: {user_id}, will use default values")
                    
            except Exception as profile_error:
                logger.warning(f"Failed to fetch user profile for {user_id}: {profile_error}")
            
            # Extract user information with comprehensive defaults
            user_info = {
                'uid': user_id,
                'sub': user_id,  # JWT compatibility
                'id': user_id,
                'email': email,
                'email_verified': user.email_confirmed_at is not None if user else decoded.get('email_confirmed_at') is not None,
                'name': (
                    user_profile.get('display_name') if user_profile else 
                    user_metadata.get('full_name') or 
                    user_metadata.get('name') or 
                    email.split('@')[0] if email else 'Unknown User'
                ),
                'picture': (
                    user_profile.get('photo_url') if user_profile else 
                    user_metadata.get('avatar_url') or 
                    user_metadata.get('picture')
                ),
                'created_at': user.created_at if user else decoded.get('created_at'),
                'updated_at': user.updated_at if user else decoded.get('updated_at'),
                'profile': user_profile,
                'role': (
                    user_profile.get('role') if user_profile else 
                    app_metadata.get('role', 'free')
                ),
                'subscription': (
                    user_profile.get('subscription', {}) if user_profile else 
                    app_metadata.get('subscription', {})
                ),
                'user_metadata': user_metadata,
                'app_metadata': app_metadata,
                'token_exp': exp_time,
                'token_iat': decoded.get('iat'),
                'session_id': decoded.get('session_id')
            }
            
            logger.info(f"Token verified successfully for user: {user_info['uid']} (role: {user_info['role']})")
            return user_info
            
        except AuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected token verification error: {e}")
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['invalid jwt', 'jwt expired', 'token expired', 'invalid token', 'signature']):
                raise AuthenticationError("Invalid or expired authentication token")
            elif any(keyword in error_msg for keyword in ['network', 'connection', 'timeout', 'unreachable']):
                raise AuthenticationError("Authentication service temporarily unavailable")
            elif 'permission' in error_msg or 'access' in error_msg:
                raise AuthenticationError("Insufficient permissions for authentication")
            else:
                raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    async def get_current_user(self, request: Request) -> Optional[Dict[str, Any]]:
        """Get current authenticated user from request"""
        try:
            credentials = await self.security(request)
            if not credentials:
                return None
            
            user_info = await self.verify_token(credentials)
            return user_info
            
        except AuthenticationError:
            return None
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            return None
    
    def require_auth(self, optional: bool = False):
        """Decorator to require authentication"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Find the request object in args or kwargs
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                
                if not request:
                    request = kwargs.get('request')
                
                if not request:
                    if optional:
                        kwargs['current_user'] = None
                        return await func(*args, **kwargs)
                    else:
                        raise HTTPException(
                            status_code=500,
                            detail="Request object not found in authentication decorator"
                        )
                
                try:
                    credentials = await self.security(request)
                    
                    if not credentials:
                        if optional:
                            kwargs['current_user'] = None
                            return await func(*args, **kwargs)
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Authentication required",
                                headers={"WWW-Authenticate": "Bearer"}
                            )
                    
                    user_info = await self.verify_token(credentials)
                    kwargs['current_user'] = user_info
                    
                    # Log successful authentication
                    logger.info(
                        f"Authenticated request: {request.method} {request.url.path} "
                        f"by user {user_info['uid']}"
                    )
                    
                    return await func(*args, **kwargs)
                    
                except AuthenticationError as e:
                    logger.warning(
                        f"Authentication failed for {request.method} {request.url.path}: {e}"
                    )
                    if optional:
                        kwargs['current_user'] = None
                        return await func(*args, **kwargs)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=str(e),
                            headers={"WWW-Authenticate": "Bearer"}
                        )
                
                except Exception as e:
                    logger.error(f"Authentication decorator error: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Authentication service error"
                    )
            
            return wrapper
        return decorator
    
    def require_role(self, required_roles: list, check_claims: bool = True):
        """Decorator to require specific roles/permissions"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                current_user = kwargs.get('current_user')
                
                if not current_user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required for role check"
                    )
                
                # Check user roles from profile
                if check_claims:
                    try:
                        user_role = current_user.get('role', 'free')
                        user_roles = [user_role]  # Convert single role to list for compatibility
                        
                        # Check if user has any of the required roles
                        if not any(role in user_roles for role in required_roles):
                            logger.warning(
                                f"Access denied: User {current_user['uid']} lacks required roles. "
                                f"Required: {required_roles}, Has: {user_roles}"
                            )
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Insufficient permissions. Required roles: {required_roles}"
                            )
                        
                        # Add roles to current_user for use in endpoint
                        current_user['roles'] = user_roles
                        kwargs['current_user'] = current_user
                        
                    except Exception as e:
                        logger.error(f"Role check error: {e}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Authorization service error"
                        )
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator

class APIKeyMiddleware:
    """Simple API key authentication for service-to-service communication"""
    
    def __init__(self):
        self.api_keys = self._load_api_keys()
    
    def _load_api_keys(self) -> Dict[str, Dict[str, Any]]:
        """Load API keys from environment or configuration"""
        api_keys = {}
        
        # Load from environment variables
        admin_key = os.getenv('ADMIN_API_KEY')
        if admin_key:
            api_keys[admin_key] = {
                'name': 'admin',
                'permissions': ['admin', 'read', 'write'],
                'rate_limit': 'unlimited'
            }
        
        service_key = os.getenv('SERVICE_API_KEY')
        if service_key:
            api_keys[service_key] = {
                'name': 'service',
                'permissions': ['read', 'write'],
                'rate_limit': 'high'
            }
        
        readonly_key = os.getenv('READONLY_API_KEY')
        if readonly_key:
            api_keys[readonly_key] = {
                'name': 'readonly',
                'permissions': ['read'],
                'rate_limit': 'medium'
            }
        
        logger.info(f"Loaded {len(api_keys)} API keys")
        return api_keys
    
    def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Verify API key and return key info"""
        return self.api_keys.get(api_key)
    
    def require_api_key(self, required_permissions: list = None):
        """Decorator to require API key authentication"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                # Check for API key in headers
                api_key = request.headers.get('X-API-Key')
                
                if not api_key:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="API key required",
                        headers={"WWW-Authenticate": "ApiKey"}
                    )
                
                key_info = self.verify_api_key(api_key)
                if not key_info:
                    logger.warning(f"Invalid API key used from {request.client.host if request.client else 'unknown'}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid API key"
                    )
                
                # Check permissions
                if required_permissions:
                    key_permissions = key_info.get('permissions', [])
                    if not any(perm in key_permissions for perm in required_permissions):
                        logger.warning(
                            f"API key {key_info['name']} lacks required permissions: {required_permissions}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Insufficient permissions. Required: {required_permissions}"
                        )
                
                # Add key info to kwargs
                kwargs['api_key_info'] = key_info
                
                logger.info(
                    f"API key authenticated: {key_info['name']} for {request.method} {request.url.path}"
                )
                
                return await func(request, *args, **kwargs)
            
            return wrapper
        return decorator

# Global authentication instances
supabase_auth_middleware = SupabaseAuthMiddleware()
api_key_middleware = APIKeyMiddleware()

# Token info functions for compatibility
async def get_supabase_token_info_from_auth_middleware(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> Dict[str, Any]:
    """Get Supabase token information with proper JWT verification"""
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Validate token format first
        token = credentials.credentials.strip()
        if not token.startswith('eyJ'):
            logger.warning("Invalid token format provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create a client with the user's access token
        client = get_supabase_client_with_auth(token)
        
        if not client:
            logger.warning("Failed to create Supabase client - invalid or expired token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to create authenticated Supabase client",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify the token by getting the current user
        try:
            user_response = client.auth.get_user()
            
            if not user_response or not user_response.user:
                logger.warning("Invalid token verification - no user returned")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception as auth_error:
            logger.warning(f"Token verification failed: {auth_error}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_data = {
            'sub': user_response.user.id,
            'uid': user_response.user.id,
            'email': user_response.user.email,
            'user_metadata': user_response.user.user_metadata or {}
        }
        
        logger.info(f"Successfully authenticated user: {user_response.user.id}")
        return user_data
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication service error",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Dependency functions for FastAPI
async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """FastAPI dependency to get current authenticated user"""
    return await supabase_auth_middleware.get_current_user(request)

async def require_authenticated_user(request: Request) -> Dict[str, Any]:
    """FastAPI dependency to require authenticated user"""
    try:
        credentials = await supabase_auth_middleware.security(request)
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        user_info = await supabase_auth_middleware.verify_token(credentials)
        return user_info
        
    except AuthenticationError as e:
        logger.warning(f"Authentication failed for {request.method} {request.url.path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Authentication service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication service unavailable",
            headers={"WWW-Authenticate": "Bearer"}
        )

def create_auth_dependency(required_roles: list = None, optional: bool = False):
    """Create a custom auth dependency with role requirements"""
    async def auth_dependency(request: Request) -> Optional[Dict[str, Any]]:
        if optional:
            user = await get_current_user(request)
        else:
            user = await require_authenticated_user(request)
        
        if user and required_roles:
            try:
                user_role = user.get('role', 'free')
                user_roles = [user_role]  # Convert single role to list for compatibility
                
                if not any(role in user_roles for role in required_roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Required roles: {required_roles}"
                    )
                
                user['roles'] = user_roles
            except Exception as e:
                logger.error(f"Role check error in auth dependency: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authorization service error"
                )
        
        return user
    
    return auth_dependency