from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from ..middleware.enhanced_auth_middleware import (
    get_current_user_required,
    get_current_user_optional,
    require_permission,
    require_role
)
from ..services.api_key_service import APIKeyService, APIKeyScope
from ..utils.structured_logging import log_security_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Enhanced Authentication"])
security = HTTPBearer()

# Request/Response Models
class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    session_id: str

class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    device_info: Dict[str, Any]
    ip_address: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    is_active: bool

class APIKeyCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    scopes: List[APIKeyScope]
    expires_at: Optional[datetime] = None
    ip_restrictions: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = None

class APIKeyResponse(BaseModel):
    key_id: str
    name: str
    description: Optional[str]
    scopes: List[APIKeyScope]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int
    is_active: bool
    # Note: The actual API key is only returned once during creation

class APIKeyCreateResponse(APIKeyResponse):
    api_key: str  # Only included in creation response

class APIKeyUsageStats(BaseModel):
    key_id: str
    total_requests: int
    requests_today: int
    requests_this_month: int
    last_used_at: Optional[datetime]
    rate_limit_hits: int
    error_count: int

# Enhanced Authentication Endpoints

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    refresh_request: TokenRefreshRequest
):
    """Refresh access token using refresh token."""
    try:
        enhanced_auth = request.app.state.enhanced_auth
        
        # Extract device info
        device_info = {
            "user_agent": request.headers.get("user-agent", "unknown"),
            "ip_address": request.client.host if request.client else "unknown"
        }
        
        # Refresh token
        result = await enhanced_auth.refresh_token(
            refresh_request.refresh_token,
            device_info
        )
        
        log_security_event("TOKEN_REFRESH", {
            "user_id": result["user_id"],
            "session_id": result["session_id"],
            "ip_address": device_info["ip_address"]
        })
        
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=result["expires_in"],
            user_id=result["user_id"],
            session_id=result["session_id"]
        )
        
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

@router.post("/logout")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Logout user and invalidate tokens."""
    try:
        enhanced_auth = request.app.state.enhanced_auth
        token = credentials.credentials
        
        # Logout and invalidate tokens
        await enhanced_auth.logout(token)
        
        log_security_event("USER_LOGOUT", {
            "ip_address": request.client.host if request.client else "unknown"
        })
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed"
        )

@router.post("/logout-all")
async def logout_all_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user_required)
):
    """Logout user from all sessions and revoke all tokens."""
    try:
        enhanced_auth = request.app.state.enhanced_auth
        user_id = current_user["id"]
        
        # Revoke all user tokens
        await enhanced_auth.revoke_all_user_tokens(user_id)
        
        log_security_event("USER_LOGOUT_ALL", {
            "user_id": user_id,
            "ip_address": request.client.host if request.client else "unknown"
        })
        
        return {"message": "Successfully logged out from all sessions"}
        
    except Exception as e:
        logger.error(f"Logout all sessions failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to logout from all sessions"
        )

@router.get("/sessions", response_model=List[SessionInfo])
async def get_user_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user_required)
):
    """Get all active sessions for the current user."""
    try:
        enhanced_auth = request.app.state.enhanced_auth
        user_id = current_user["id"]
        
        # Get user sessions
        sessions = await enhanced_auth.get_user_sessions(user_id)
        
        return [
            SessionInfo(
                session_id=session["session_id"],
                user_id=session["user_id"],
                device_info=session["device_info"],
                ip_address=session["ip_address"],
                created_at=session["created_at"],
                last_activity=session["last_activity"],
                expires_at=session["expires_at"],
                is_active=session["is_active"]
            )
            for session in sessions
        ]
        
    except Exception as e:
        logger.error(f"Get user sessions failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve sessions"
        )

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user_required)
):
    """Revoke a specific session."""
    try:
        enhanced_auth = request.app.state.enhanced_auth
        user_id = current_user["id"]
        
        # Revoke specific session
        await enhanced_auth.revoke_session(user_id, session_id)
        
        log_security_event("SESSION_REVOKED", {
            "user_id": user_id,
            "session_id": session_id,
            "ip_address": request.client.host if request.client else "unknown"
        })
        
        return {"message": f"Session {session_id} revoked successfully"}
        
    except Exception as e:
        logger.error(f"Revoke session failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to revoke session"
        )

# API Key Management Endpoints

@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    request: Request,
    key_request: APIKeyCreateRequest,
    current_user: dict = Depends(get_current_user_required)
):
    """Create a new API key for the current user."""
    try:
        api_key_service: APIKeyService = request.app.state.api_key_service
        user_id = current_user["id"]
        
        # Create API key
        result = await api_key_service.create_api_key(
            user_id=user_id,
            name=key_request.name,
            description=key_request.description,
            scopes=key_request.scopes,
            expires_at=key_request.expires_at,
            ip_restrictions=key_request.ip_restrictions,
            rate_limit_per_minute=key_request.rate_limit_per_minute
        )
        
        log_security_event("API_KEY_CREATED", {
            "user_id": user_id,
            "key_id": result["key_id"],
            "scopes": [scope.value for scope in key_request.scopes],
            "ip_address": request.client.host if request.client else "unknown"
        })
        
        return APIKeyCreateResponse(
            key_id=result["key_id"],
            name=result["name"],
            description=result["description"],
            scopes=result["scopes"],
            created_at=result["created_at"],
            expires_at=result["expires_at"],
            last_used_at=None,
            usage_count=0,
            is_active=True,
            api_key=result["api_key"]  # Only returned during creation
        )
        
    except Exception as e:
        logger.error(f"Create API key failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create API key"
        )

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    request: Request,
    current_user: dict = Depends(get_current_user_required)
):
    """List all API keys for the current user."""
    try:
        api_key_service: APIKeyService = request.app.state.api_key_service
        user_id = current_user["id"]
        
        # Get user's API keys
        keys = await api_key_service.list_user_api_keys(user_id)
        
        return [
            APIKeyResponse(
                key_id=key["key_id"],
                name=key["name"],
                description=key["description"],
                scopes=key["scopes"],
                created_at=key["created_at"],
                expires_at=key["expires_at"],
                last_used_at=key["last_used_at"],
                usage_count=key["usage_count"],
                is_active=key["is_active"]
            )
            for key in keys
        ]
        
    except Exception as e:
        logger.error(f"List API keys failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve API keys"
        )

@router.get("/api-keys/{key_id}/usage", response_model=APIKeyUsageStats)
async def get_api_key_usage(
    key_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user_required)
):
    """Get usage statistics for a specific API key."""
    try:
        api_key_service: APIKeyService = request.app.state.api_key_service
        user_id = current_user["id"]
        
        # Get usage stats
        stats = await api_key_service.get_usage_stats(key_id, user_id)
        
        return APIKeyUsageStats(**stats)
        
    except Exception as e:
        logger.error(f"Get API key usage failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve API key usage"
        )

@router.post("/api-keys/{key_id}/rotate")
async def rotate_api_key(
    key_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user_required)
):
    """Rotate an API key (generate new key, invalidate old one)."""
    try:
        api_key_service: APIKeyService = request.app.state.api_key_service
        user_id = current_user["id"]
        
        # Rotate API key
        new_key = await api_key_service.rotate_api_key(key_id, user_id)
        
        log_security_event("API_KEY_ROTATED", {
            "user_id": user_id,
            "old_key_id": key_id,
            "new_key_id": new_key["key_id"],
            "ip_address": request.client.host if request.client else "unknown"
        })
        
        return {
            "message": "API key rotated successfully",
            "new_api_key": new_key["api_key"],
            "key_id": new_key["key_id"]
        }
        
    except Exception as e:
        logger.error(f"Rotate API key failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to rotate API key"
        )

@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user_required)
):
    """Revoke an API key."""
    try:
        api_key_service: APIKeyService = request.app.state.api_key_service
        user_id = current_user["id"]
        
        # Revoke API key
        await api_key_service.revoke_api_key(key_id, user_id)
        
        log_security_event("API_KEY_REVOKED", {
            "user_id": user_id,
            "key_id": key_id,
            "ip_address": request.client.host if request.client else "unknown"
        })
        
        return {"message": f"API key {key_id} revoked successfully"}
        
    except Exception as e:
        logger.error(f"Revoke API key failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to revoke API key"
        )

# Export the router with the expected name
enhanced_auth_router = router

# Admin endpoints (require admin role)

@router.get("/admin/api-keys", response_model=List[APIKeyResponse])
async def admin_list_all_api_keys(
    request: Request,
    current_user: dict = Depends(require_role("admin"))
):
    """Admin endpoint to list all API keys in the system."""
    try:
        api_key_service: APIKeyService = request.app.state.api_key_service
        
        # Get all API keys (admin only)
        keys = await api_key_service.admin_list_all_keys()
        
        return [
            APIKeyResponse(
                key_id=key["key_id"],
                name=key["name"],
                description=key["description"],
                scopes=key["scopes"],
                created_at=key["created_at"],
                expires_at=key["expires_at"],
                last_used_at=key["last_used_at"],
                usage_count=key["usage_count"],
                is_active=key["is_active"]
            )
            for key in keys
        ]
        
    except Exception as e:
        logger.error(f"Admin list API keys failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve API keys"
        )

@router.delete("/admin/api-keys/{key_id}")
async def admin_revoke_api_key(
    key_id: str,
    request: Request,
    current_user: dict = Depends(require_role("admin"))
):
    """Admin endpoint to revoke any API key."""
    try:
        api_key_service: APIKeyService = request.app.state.api_key_service
        
        # Admin revoke API key
        await api_key_service.admin_revoke_key(key_id)
        
        log_security_event("API_KEY_ADMIN_REVOKED", {
            "admin_user_id": current_user["id"],
            "key_id": key_id,
            "ip_address": request.client.host if request.client else "unknown"
        })
        
        return {"message": f"API key {key_id} revoked by admin"}
        
    except Exception as e:
        logger.error(f"Admin revoke API key failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to revoke API key"
        )