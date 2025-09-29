from typing import Optional, Dict, Any
from fastapi import Depends

from api.utils.supabase_client import get_supabase_admin_client
from api.models.database_models import User
from .jwt_middleware import get_current_user, get_current_user_required

# Authentication dependencies for route handlers

def require_auth(user: Dict[str, Any] = Depends(get_current_user_required)) -> Dict[str, Any]:
    """Dependency that requires authentication - raises 401 if not authenticated"""
    return user

def optional_auth(user: Optional[Dict[str, Any]] = Depends(get_current_user)) -> Optional[Dict[str, Any]]:
    """Dependency for optional authentication - returns None if not authenticated"""
    return user

def get_supabase_client():
    """Get Supabase client for database operations"""
    return get_supabase_admin_client()