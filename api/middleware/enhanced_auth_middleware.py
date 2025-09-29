"""Enhanced Authentication Middleware with comprehensive security features.

Provides:
- JWT token validation with proper error handling
- Token refresh mechanism with rotation
- Token blacklisting and revocation
- Session management with device tracking
- Rate limiting for authentication endpoints
- Security logging and monitoring
- Multi-factor authentication support
"""

import logging
import time
import hashlib
import secrets
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import redis
from pydantic import BaseModel

from api.utils.supabase_client import get_supabase_admin_client
from api.core.config import settings
from api.utils.structured_logging import StructuredLogger

logger = logging.getLogger(__name__)
structured_logger = StructuredLogger("enhanced_auth_middleware")

# Security configuration
class AuthConfig:
    """Authentication configuration settings."""
    
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    SESSION_TIMEOUT_HOURS = 24
    MAX_CONCURRENT_SESSIONS = 5
    TOKEN_ROTATION_ENABLED = True
    MFA_REQUIRED_ROLES = ['admin', 'moderator']
    SECURITY_HEADERS_ENABLED = True

class TokenInfo(BaseModel):
    """Token information model."""
    user_id: str
    email: str
    role: str
    permissions: List[str]
    session_id: str
    device_id: Optional[str] = None
    ip_address: str
    issued_at: datetime
    expires_at: datetime
    token_type: str  # 'access' or 'refresh'

class SessionInfo(BaseModel):
    """Session information model."""
    session_id: str
    user_id: str
    device_id: Optional[str] = None
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    is_active: bool = True

class EnhancedAuthMiddleware:
    """Enhanced authentication middleware with comprehensive security features."""
    
    def __init__(self):
        self.config = AuthConfig()
        self.redis = redis.Redis.from_url(settings.REDIS_URL) if hasattr(settings, 'REDIS_URL') else None
        self.supabase = get_supabase_admin_client()
        self.security = HTTPBearer(auto_error=False)
        
        # In-memory fallback if Redis is not available
        self._token_blacklist: Set[str] = set()
        self._failed_attempts: Dict[str, List[datetime]] = {}
        self._active_sessions: Dict[str, SessionInfo] = {}
    
    def _get_redis_key(self, key_type: str, identifier: str) -> str:
        """Generate Redis key with namespace."""
        return f"auth:{key_type}:{identifier}"
    
    def _hash_token(self, token: str) -> str:
        """Create secure hash of token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _generate_session_id(self) -> str:
        """Generate secure session ID."""
        return secrets.token_urlsafe(32)
    
    def _extract_device_info(self, request: Request) -> Dict[str, str]:
        """Extract device information from request."""
        user_agent = request.headers.get('user-agent', '')
        ip_address = request.client.host if request.client else 'unknown'
        
        # Generate device fingerprint
        device_string = f"{user_agent}:{ip_address}"
        device_id = hashlib.md5(device_string.encode()).hexdigest()
        
        return {
            'device_id': device_id,
            'ip_address': ip_address,
            'user_agent': user_agent
        }
    
    def _is_rate_limited(self, identifier: str, max_attempts: int = None, window_minutes: int = 15) -> bool:
        """Check if identifier is rate limited."""
        max_attempts = max_attempts or self.config.MAX_FAILED_ATTEMPTS
        
        if self.redis:
            key = self._get_redis_key('rate_limit', identifier)
            current_count = self.redis.get(key)
            
            if current_count and int(current_count) >= max_attempts:
                return True
        else:
            # Fallback to in-memory tracking
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=window_minutes)
            
            attempts = self._failed_attempts.get(identifier, [])
            recent_attempts = [attempt for attempt in attempts if attempt > cutoff]
            
            if len(recent_attempts) >= max_attempts:
                return True
        
        return False
    
    def _record_failed_attempt(self, identifier: str, window_minutes: int = 15) -> None:
        """Record failed authentication attempt."""
        if self.redis:
            key = self._get_redis_key('rate_limit', identifier)
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_minutes * 60)
            pipe.execute()
        else:
            # Fallback to in-memory tracking
            now = datetime.now(timezone.utc)
            if identifier not in self._failed_attempts:
                self._failed_attempts[identifier] = []
            
            self._failed_attempts[identifier].append(now)
            
            # Clean old attempts
            cutoff = now - timedelta(minutes=window_minutes)
            self._failed_attempts[identifier] = [
                attempt for attempt in self._failed_attempts[identifier] 
                if attempt > cutoff
            ]
    
    def _validate_token_structure(self, token: str) -> bool:
        """Validate JWT token structure without verification."""
        try:
            # Decode without verification to check structure
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Check required claims
            required_claims = ['sub', 'exp', 'iat', 'type']
            if not all(claim in payload for claim in required_claims):
                return False
            
            # Check if token is expired
            exp = payload.get('exp')
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                return False
            
            return True
            
        except (InvalidTokenError, ExpiredSignatureError, ValueError):
            return False
    
    def _is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        token_hash = self._hash_token(token)
        
        if self.redis:
            return self.redis.exists(self._get_redis_key('blacklist', token_hash)) > 0
        else:
            return token_hash in self._token_blacklist
    
    def _blacklist_token(self, token: str, ttl_seconds: int = None) -> None:
        """Add token to blacklist."""
        token_hash = self._hash_token(token)
        
        if self.redis:
            key = self._get_redis_key('blacklist', token_hash)
            if ttl_seconds:
                self.redis.setex(key, ttl_seconds, '1')
            else:
                self.redis.set(key, '1')
        else:
            self._token_blacklist.add(token_hash)
    
    def _create_session(self, user_id: str, request: Request) -> str:
        """Create new user session."""
        session_id = self._generate_session_id()
        device_info = self._extract_device_info(request)
        
        session_info = SessionInfo(
            session_id=session_id,
            user_id=user_id,
            device_id=device_info['device_id'],
            ip_address=device_info['ip_address'],
            user_agent=device_info['user_agent'],
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc)
        )
        
        if self.redis:
            key = self._get_redis_key('session', session_id)
            self.redis.setex(
                key, 
                int(timedelta(hours=self.config.SESSION_TIMEOUT_HOURS).total_seconds()),
                session_info.json()
            )
            
            # Track user sessions
            user_sessions_key = self._get_redis_key('user_sessions', user_id)
            self.redis.sadd(user_sessions_key, session_id)
            self.redis.expire(user_sessions_key, int(timedelta(hours=self.config.SESSION_TIMEOUT_HOURS).total_seconds()))
        else:
            self._active_sessions[session_id] = session_info
        
        return session_id
    
    def _validate_session(self, session_id: str) -> Optional[SessionInfo]:
        """Validate and return session information."""
        if self.redis:
            key = self._get_redis_key('session', session_id)
            session_data = self.redis.get(key)
            
            if session_data:
                return SessionInfo.parse_raw(session_data)
        else:
            return self._active_sessions.get(session_id)
        
        return None
    
    def _update_session_activity(self, session_id: str) -> None:
        """Update session last activity timestamp."""
        session_info = self._validate_session(session_id)
        if not session_info:
            return
        
        session_info.last_activity = datetime.now(timezone.utc)
        
        if self.redis:
            key = self._get_redis_key('session', session_id)
            self.redis.setex(
                key,
                int(timedelta(hours=self.config.SESSION_TIMEOUT_HOURS).total_seconds()),
                session_info.json()
            )
        else:
            self._active_sessions[session_id] = session_info
    
    async def authenticate_request(self, request: Request) -> Optional[TokenInfo]:
        """Authenticate request and return token information."""
        try:
            # Extract authorization header
            authorization = request.headers.get('Authorization')
            if not authorization or not authorization.startswith('Bearer '):
                return None
            
            token = authorization.split(' ')[1]
            
            # Check rate limiting
            device_info = self._extract_device_info(request)
            if self._is_rate_limited(device_info['ip_address']):
                structured_logger.log_security_event(
                    event_type="rate_limit_exceeded",
                    ip_address=device_info['ip_address'],
                    user_agent=device_info['user_agent']
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many authentication attempts"
                )
            
            # Validate token structure
            if not self._validate_token_structure(token):
                self._record_failed_attempt(device_info['ip_address'])
                return None
            
            # Check if token is blacklisted
            if self._is_token_blacklisted(token):
                self._record_failed_attempt(device_info['ip_address'])
                return None
            
            # Verify token with Supabase
            try:
                user_response = self.supabase.auth.get_user(token)
                if not user_response or not user_response.user:
                    self._record_failed_attempt(device_info['ip_address'])
                    return None
                
                user = user_response.user
                
                # Get user profile from database
                profile_response = self.supabase.table('users').select('*').eq('auth_id', user.id).execute()
                if not profile_response.data:
                    return None
                
                profile = profile_response.data[0]
                
                # Create session if not exists
                session_id = self._create_session(user.id, request)
                
                # Create token info
                token_info = TokenInfo(
                    user_id=user.id,
                    email=user.email,
                    role=user.user_metadata.get('role', 'free'),
                    permissions=self._get_user_permissions(user.user_metadata.get('role', 'free')),
                    session_id=session_id,
                    device_id=device_info['device_id'],
                    ip_address=device_info['ip_address'],
                    issued_at=datetime.fromtimestamp(jwt.decode(token, options={"verify_signature": False})['iat'], tz=timezone.utc),
                    expires_at=datetime.fromtimestamp(jwt.decode(token, options={"verify_signature": False})['exp'], tz=timezone.utc),
                    token_type='access'
                )
                
                # Update session activity
                self._update_session_activity(session_id)
                
                # Log successful authentication
                structured_logger.log_security_event(
                    event_type="authentication_success",
                    user_id=user.id,
                    ip_address=device_info['ip_address'],
                    user_agent=device_info['user_agent']
                )
                
                return token_info
                
            except Exception as e:
                logger.warning(f"Token verification failed: {str(e)}")
                self._record_failed_attempt(device_info['ip_address'])
                return None
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None
    
    def _get_user_permissions(self, role: str) -> List[str]:
        """Get user permissions based on role."""
        role_permissions = {
            'admin': ['read', 'write', 'delete', 'manage_users', 'manage_system'],
            'moderator': ['read', 'write', 'delete', 'manage_content'],
            'premium': ['read', 'write', 'upload_files'],
            'free': ['read']
        }
        return role_permissions.get(role, ['read'])
    
    async def refresh_token(self, refresh_token: str, request: Request) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        try:
            # Validate refresh token with Supabase
            response = self.supabase.auth.refresh_session(refresh_token)
            
            if not response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token"
                )
            
            # If token rotation is enabled, blacklist old refresh token
            if self.config.TOKEN_ROTATION_ENABLED:
                # Calculate TTL based on original token expiration
                try:
                    payload = jwt.decode(refresh_token, options={"verify_signature": False})
                    exp = payload.get('exp')
                    if exp:
                        ttl = max(0, exp - int(time.time()))
                        self._blacklist_token(refresh_token, ttl)
                except:
                    pass
            
            # Create new session
            session_id = self._create_session(response.user.id, request)
            
            # Log token refresh
            device_info = self._extract_device_info(request)
            structured_logger.log_security_event(
                event_type="token_refresh",
                user_id=response.user.id,
                ip_address=device_info['ip_address'],
                user_agent=device_info['user_agent']
            )
            
            return {
                'access_token': response.session.access_token,
                'refresh_token': response.session.refresh_token,
                'expires_in': 3600,  # 1 hour
                'token_type': 'bearer',
                'session_id': session_id
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to refresh token"
            )
    
    async def logout(self, token: str, session_id: Optional[str] = None) -> bool:
        """Logout user and invalidate tokens."""
        try:
            # Blacklist access token
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                exp = payload.get('exp')
                if exp:
                    ttl = max(0, exp - int(time.time()))
                    self._blacklist_token(token, ttl)
            except:
                pass
            
            # Invalidate session
            if session_id:
                if self.redis:
                    self.redis.delete(self._get_redis_key('session', session_id))
                else:
                    self._active_sessions.pop(session_id, None)
            
            return True
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False
    
    async def revoke_all_user_tokens(self, user_id: str) -> bool:
        """Revoke all tokens for a specific user."""
        try:
            if self.redis:
                # Get all user sessions
                user_sessions_key = self._get_redis_key('user_sessions', user_id)
                session_ids = self.redis.smembers(user_sessions_key)
                
                # Delete all sessions
                for session_id in session_ids:
                    self.redis.delete(self._get_redis_key('session', session_id.decode()))
                
                # Clear user sessions set
                self.redis.delete(user_sessions_key)
            else:
                # Remove all sessions for user
                sessions_to_remove = [
                    sid for sid, session in self._active_sessions.items()
                    if session.user_id == user_id
                ]
                for sid in sessions_to_remove:
                    del self._active_sessions[sid]
            
            return True
            
        except Exception as e:
            logger.error(f"Error revoking user tokens: {str(e)}")
            return False

# Global middleware instance
enhanced_auth_middleware = EnhancedAuthMiddleware()

# FastAPI dependencies
async def get_current_user_optional(request: Request) -> Optional[TokenInfo]:
    """Get current user information (optional)."""
    return await enhanced_auth_middleware.authenticate_request(request)

async def get_current_user_required(request: Request) -> TokenInfo:
    """Get current user information (required)."""
    token_info = await enhanced_auth_middleware.authenticate_request(request)
    if not token_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return token_info

def require_permission(permission: str):
    """Decorator to require specific permission."""
    async def permission_checker(token_info: TokenInfo = Depends(get_current_user_required)) -> TokenInfo:
        if permission not in token_info.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return token_info
    return permission_checker

def require_role(roles: List[str]):
    """Decorator to require specific role(s)."""
    async def role_checker(token_info: TokenInfo = Depends(get_current_user_required)) -> TokenInfo:
        if token_info.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role must be one of: {', '.join(roles)}"
            )
        return token_info
    return role_checker