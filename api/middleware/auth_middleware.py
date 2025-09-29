from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Callable, Any
from functools import wraps
import logging
from datetime import datetime, timezone
from ..utils.supabase_client import get_supabase_admin_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBearer()

class AuthMiddleware:
    """
    Supabase Authentication Middleware for FastAPI
    """
    
    def __init__(self):
        self.security = HTTPBearer()
        self.supabase_client = get_supabase_admin_client()
    
    async def verify_token(self, credentials: HTTPAuthorizationCredentials) -> dict:
        """
        Verify Supabase JWT token and return user information
        """
        try:
            # Get user from Supabase using the JWT token
            response = self.supabase_client.auth.get_user(credentials.credentials)
            
            if response.user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            user = response.user
            
            # Get user profile from database
            profile_response = self.supabase_client.table('user_profiles').select('*').eq('id', user.id).execute()
            user_profile = profile_response.data[0] if profile_response.data else None
            
            return {
                'uid': user.id,
                'id': user.id,
                'email': user.email,
                'email_verified': user.email_confirmed_at is not None,
                'display_name': user_profile.get('full_name') if user_profile else None,
                'photo_url': user_profile.get('avatar_url') if user_profile else None,
                'profile': user_profile,
                'role': user_profile.get('role', 'free') if user_profile else 'free',
                'subscription': user_profile.get('subscription', {}) if user_profile else {}
            }
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            if "Invalid JWT" in str(e) or "JWT expired" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    async def require_auth(self, credentials: HTTPAuthorizationCredentials) -> dict:
        """
        Require authentication - verify token and return user info
        """
        return await self.verify_token(credentials)
    
    async def require_roles(self, credentials: HTTPAuthorizationCredentials, allowed_roles: List[str]) -> dict:
        """
        Require specific roles - verify token and check user role
        """
        user_info = await self.verify_token(credentials)
        user_role = user_info.get('role', 'free')
        
        if user_role not in allowed_roles:
            logger.warning(f"Access denied for user {user_info['uid']} with role {user_role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        
        return user_info
    
    async def require_premium(self, credentials: HTTPAuthorizationCredentials) -> dict:
        """
        Require premium subscription - verify token and check subscription status
        """
        user_info = await self.verify_token(credentials)
        subscription = user_info.get('subscription', {})
        
        # Check if user has active premium subscription
        is_premium = (
            user_info.get('role') == 'premium' and
            subscription.get('status') == 'active' and
            subscription.get('plan') in ['premium', 'pro']
        )
        
        if not is_premium:
            # Check if subscription is expired
            expires_at = subscription.get('expires_at')
            if expires_at and isinstance(expires_at, datetime):
                if expires_at < datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail="Premium subscription has expired"
                    )
            
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Premium subscription required"
            )
        
        return user_info
    
    async def require_email_verified(self, credentials: HTTPAuthorizationCredentials) -> dict:
        """
        Require email verification - verify token and check email verification status
        """
        user_info = await self.verify_token(credentials)
        
        if not user_info.get('email_verified', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email verification required"
            )
        
        return user_info
    
    async def optional_auth(self, request: Request) -> Optional[dict]:
        """
        Optional authentication - return user info if token is provided and valid, None otherwise
        """
        try:
            authorization = request.headers.get('Authorization')
            if not authorization or not authorization.startswith('Bearer '):
                return None
            
            token = authorization.split(' ')[1]
            credentials = HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)
            return await self.verify_token(credentials)
        except:
            return None

# Create security instance
security = HTTPBearer()

# Create middleware instance
auth_middleware = AuthMiddleware()

# Dependency functions for FastAPI
async def require_auth(credentials: HTTPAuthorizationCredentials = security) -> dict:
    """
    FastAPI dependency to require authentication
    """
    return await auth_middleware.require_auth(credentials)

async def require_admin(credentials: HTTPAuthorizationCredentials = security) -> dict:
    """
    FastAPI dependency to require admin role
    """
    return await auth_middleware.require_roles(credentials, ['admin'])

async def require_premium(credentials: HTTPAuthorizationCredentials = security) -> dict:
    """
    FastAPI dependency to require premium subscription
    """
    return await auth_middleware.require_premium(credentials)

async def require_email_verified(credentials: HTTPAuthorizationCredentials = security) -> dict:
    """
    FastAPI dependency to require email verification
    """
    return await auth_middleware.require_email_verified(credentials)

async def optional_auth(request: Request) -> Optional[dict]:
    """
    FastAPI dependency for optional authentication
    """
    return await auth_middleware.optional_auth(request)

# Decorator functions for additional flexibility
def require_roles(*roles: str):
    """
    Decorator to require specific roles
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract credentials from kwargs or args
            credentials = None
            for arg in args:
                if isinstance(arg, HTTPAuthorizationCredentials):
                    credentials = arg
                    break
            
            if not credentials:
                for value in kwargs.values():
                    if isinstance(value, HTTPAuthorizationCredentials):
                        credentials = value
                        break
            
            if not credentials:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_info = await auth_middleware.require_roles(credentials, list(roles))
            
            # Add user_info to kwargs if not already present
            if 'current_user' not in kwargs:
                kwargs['current_user'] = user_info
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def rate_limit_by_user(max_requests: int = 100, window_seconds: int = 3600):
    """
    Decorator to implement rate limiting per user
    """
    user_requests = {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user info from kwargs
            current_user = kwargs.get('current_user')
            if not current_user:
                # Try to get from args
                for arg in args:
                    if isinstance(arg, dict) and 'uid' in arg:
                        current_user = arg
                        break
            
            if current_user:
                uid = current_user['uid']
                current_time = datetime.now(timezone.utc)
                
                # Clean old entries
                if uid in user_requests:
                    user_requests[uid] = [
                        req_time for req_time in user_requests[uid]
                        if (current_time - req_time).total_seconds() < window_seconds
                    ]
                else:
                    user_requests[uid] = []
                
                # Check rate limit
                if len(user_requests[uid]) >= max_requests:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds"
                    )
                
                # Add current request
                user_requests[uid].append(current_time)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Middleware class for FastAPI application
class SupabaseAuthMiddleware:
    """
    ASGI Middleware for Supabase Authentication
    """
    
    def __init__(self, app, excluded_paths: List[str] = None):
        self.app = app
        self.excluded_paths = excluded_paths or [
            '/docs', '/redoc', '/openapi.json', '/health',
            '/api/auth/register', '/api/auth/login'
        ]
        self.supabase_client = get_supabase_admin_client()
    
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        
        path = scope['path']
        
        # Skip authentication for excluded paths
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            await self.app(scope, receive, send)
            return
        
        # Check for Authorization header
        headers = dict(scope['headers'])
        auth_header = headers.get(b'authorization', b'').decode('utf-8')
        
        if not auth_header.startswith('Bearer '):
            # No auth header, let the endpoint handle it
            await self.app(scope, receive, send)
            return
        
        try:
            token = auth_header.split(' ')[1]
            response = self.supabase_client.auth.get_user(token)
            
            if response.user:
                # Add user info to scope
                scope['user'] = {
                    'uid': response.user.id,
                    'id': response.user.id,
                    'email': response.user.email,
                    'email_verified': response.user.email_confirmed_at is not None
                }
        except Exception as e:
            logger.error(f"Token verification failed in middleware: {str(e)}")
            # Let the endpoint handle the invalid token
        
        await self.app(scope, receive, send)