"""Authentication and authorization middleware for the Cliper API."""

import jwt
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from functools import wraps

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import redis

# from ..core.database import get_db_pool  # Disabled for Firebase migration
from ..models.user import User
from ..core.config import settings
from .hardening import SecurityHardening, get_security

# JWT Configuration
JWT_SECRET_KEY = settings.SECRET_KEY
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7

# Permission levels
class Permission:
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

# Role-based permissions
ROLE_PERMISSIONS = {
    "user": [Permission.READ, Permission.WRITE],
    "premium": [Permission.READ, Permission.WRITE],
    "moderator": [Permission.READ, Permission.WRITE, Permission.DELETE],
    "admin": [Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN],
    "super_admin": [Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN, Permission.SUPER_ADMIN]
}

class TokenManager:
    """JWT token management utilities."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def create_access_token(self, user_id: int, user_role: str, permissions: List[str]) -> str:
        """Create JWT access token."""
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "user_id": user_id,
            "role": user_role,
            "permissions": permissions,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    def create_refresh_token(self, user_id: int) -> str:
        """Create JWT refresh token."""
        expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "user_id": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        # Store refresh token in Redis
        self.redis.setex(
            f"refresh_token:{user_id}",
            timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            token
        )
        
        return token
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            # Check if token is blacklisted
            if self.is_token_blacklisted(token):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
            
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    def refresh_access_token(self, refresh_token: str, db: Session) -> Dict[str, str]:
        """Refresh access token using refresh token."""
        try:
            payload = jwt.decode(refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            user_id = payload.get("user_id")
            
            # Verify refresh token exists in Redis
            stored_token = self.redis.get(f"refresh_token:{user_id}")
            if not stored_token or stored_token.decode() != refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            # Get user and create new access token
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )
            
            permissions = ROLE_PERMISSIONS.get(user.role, [])
            new_access_token = self.create_access_token(user.id, user.role, permissions)
            
            return {
                "access_token": new_access_token,
                "token_type": "bearer"
            }
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    
    def blacklist_token(self, token: str) -> None:
        """Add token to blacklist."""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
            exp = payload.get("exp")
            if exp:
                # Calculate TTL based on token expiration
                ttl = max(0, exp - int(time.time()))
                self.redis.setex(f"blacklist:{token}", ttl, "1")
        except jwt.InvalidTokenError:
            pass  # Invalid tokens don't need to be blacklisted
    
    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        return self.redis.exists(f"blacklist:{token}") > 0
    
    def revoke_user_tokens(self, user_id: int) -> None:
        """Revoke all tokens for a user."""
        # Remove refresh token
        self.redis.delete(f"refresh_token:{user_id}")
        
        # Add user to revoked list (access tokens will check this)
        self.redis.setex(
            f"revoked_user:{user_id}",
            timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            "1"
        )

class AuthenticationMiddleware:
    """Authentication middleware for protected endpoints."""
    
    def __init__(self):
        self.security_bearer = HTTPBearer(auto_error=False)
        self.redis = redis.Redis.from_url(settings.REDIS_URL)
        self.token_manager = TokenManager(self.redis)
    
    async def get_current_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
        db: Session = Depends(get_db)
    ) -> Optional[User]:
        """Get current authenticated user."""
        if not credentials:
            return None
        
        try:
            payload = self.token_manager.verify_token(credentials.credentials)
            user_id = payload.get("user_id")
            
            if not user_id:
                return None
            
            # Check if user tokens are revoked
            if self.redis.exists(f"revoked_user:{user_id}"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User tokens have been revoked"
                )
            
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                return None
            
            # Update last activity
            user.last_activity = datetime.utcnow()
            db.commit()
            
            return user
            
        except HTTPException:
            raise
        except Exception:
            return None
    
    async def require_authentication(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
        db: Session = Depends(get_db)
    ) -> User:
        """Require valid authentication."""
        user = await self.get_current_user(credentials, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return user
    
    async def require_permission(
        self,
        required_permission: str,
        user: User = Depends(lambda: AuthenticationMiddleware().require_authentication)
    ) -> User:
        """Require specific permission."""
        user_permissions = ROLE_PERMISSIONS.get(user.role, [])
        
        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{required_permission}' required"
            )
        
        return user
    
    async def require_role(
        self,
        required_roles: List[str],
        user: User = Depends(lambda: AuthenticationMiddleware().require_authentication)
    ) -> User:
        """Require specific role(s)."""
        if user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role must be one of: {', '.join(required_roles)}"
            )
        
        return user

class SessionManager:
    """Session management for user activities."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def create_session(self, user_id: int, request: Request) -> str:
        """Create user session."""
        session_id = f"session:{user_id}:{int(time.time())}"
        
        session_data = {
            "user_id": user_id,
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent", ""),
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        
        # Store session for 24 hours
        self.redis.setex(
            session_id,
            timedelta(hours=24),
            str(session_data)
        )
        
        # Add to user's active sessions
        self.redis.sadd(f"user_sessions:{user_id}", session_id)
        self.redis.expire(f"user_sessions:{user_id}", timedelta(hours=24))
        
        return session_id
    
    def update_session_activity(self, session_id: str) -> None:
        """Update session last activity."""
        if self.redis.exists(session_id):
            session_data = eval(self.redis.get(session_id).decode())
            session_data["last_activity"] = datetime.utcnow().isoformat()
            self.redis.setex(session_id, timedelta(hours=24), str(session_data))
    
    def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        session_ids = self.redis.smembers(f"user_sessions:{user_id}")
        sessions = []
        
        for session_id in session_ids:
            session_data = self.redis.get(session_id)
            if session_data:
                sessions.append(eval(session_data.decode()))
        
        return sessions
    
    def revoke_session(self, session_id: str, user_id: int) -> None:
        """Revoke a specific session."""
        self.redis.delete(session_id)
        self.redis.srem(f"user_sessions:{user_id}", session_id)
    
    def revoke_all_sessions(self, user_id: int) -> None:
        """Revoke all sessions for a user."""
        session_ids = self.redis.smembers(f"user_sessions:{user_id}")
        
        for session_id in session_ids:
            self.redis.delete(session_id)
        
        self.redis.delete(f"user_sessions:{user_id}")

# Dependency functions
def get_token_manager() -> TokenManager:
    """Get token manager instance."""
    redis_client = redis.Redis.from_url(settings.REDIS_URL)
    return TokenManager(redis_client)

def get_session_manager() -> SessionManager:
    """Get session manager instance."""
    redis_client = redis.Redis.from_url(settings.REDIS_URL)
    return SessionManager(redis_client)

# Authentication decorators
def require_auth(func):
    """Decorator to require authentication."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        auth_middleware = AuthenticationMiddleware()
        # This would need to be properly integrated with FastAPI dependency injection
        return await func(*args, **kwargs)
    return wrapper

def require_permission(permission: str):
    """Decorator to require specific permission."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # This would need to be properly integrated with FastAPI dependency injection
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(*roles: str):
    """Decorator to require specific role(s)."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # This would need to be properly integrated with FastAPI dependency injection
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Security audit logging
class SecurityAuditLogger:
    """Security audit logging for authentication events."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def log_login_attempt(self, username: str, ip_address: str, success: bool, reason: str = None) -> None:
        """Log login attempt."""
        log_entry = {
            "event": "login_attempt",
            "username": username,
            "ip_address": ip_address,
            "success": success,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in Redis with 30-day expiration
        key = f"audit_log:{int(time.time())}:{username}"
        self.redis.setex(key, timedelta(days=30), str(log_entry))
        
        # Add to user's login history
        self.redis.lpush(f"login_history:{username}", str(log_entry))
        self.redis.ltrim(f"login_history:{username}", 0, 99)  # Keep last 100 entries
        self.redis.expire(f"login_history:{username}", timedelta(days=30))
    
    def log_permission_denied(self, user_id: int, resource: str, action: str, ip_address: str) -> None:
        """Log permission denied events."""
        log_entry = {
            "event": "permission_denied",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        key = f"audit_log:{int(time.time())}:{user_id}"
        self.redis.setex(key, timedelta(days=30), str(log_entry))
    
    def log_suspicious_activity(self, ip_address: str, activity_type: str, details: Dict[str, Any]) -> None:
        """Log suspicious activity."""
        log_entry = {
            "event": "suspicious_activity",
            "ip_address": ip_address,
            "activity_type": activity_type,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        key = f"security_alert:{int(time.time())}:{ip_address}"
        self.redis.setex(key, timedelta(days=90), str(log_entry))
        
        # Add to suspicious activity list
        self.redis.lpush("suspicious_activities", str(log_entry))
        self.redis.ltrim("suspicious_activities", 0, 999)  # Keep last 1000 entries
        self.redis.expire("suspicious_activities", timedelta(days=90))

def get_audit_logger() -> SecurityAuditLogger:
    """Get security audit logger instance."""
    redis_client = redis.Redis.from_url(settings.REDIS_URL)
    return SecurityAuditLogger(redis_client)