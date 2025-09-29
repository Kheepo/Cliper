from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
import logging
import os
from ..utils.supabase_client import (
    get_supabase_client,
    get_supabase_client_with_auth,
    verify_supabase_connection,
    validate_jwt_token
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["debug"])
security = HTTPBearer()

@router.get("/supabase-connection")
async def test_supabase_connection():
    """Test basic Supabase connection"""
    try:
        # Test basic client creation
        client = get_supabase_client()
        if not client:
            return {
                "status": "error",
                "message": "Failed to create basic Supabase client",
                "details": {
                    "supabase_url": os.getenv('SUPABASE_URL', 'Not set'),
                    "supabase_anon_key": "Set" if os.getenv('SUPABASE_ANON_KEY') else "Not set"
                }
            }
        
        # Test connection verification
        connection_ok = verify_supabase_connection()
        
        return {
            "status": "success" if connection_ok else "warning",
            "message": "Supabase connection test completed",
            "details": {
                "basic_client": "OK",
                "connection_test": "OK" if connection_ok else "Failed",
                "supabase_url": os.getenv('SUPABASE_URL', 'Not set')[:50] + "..." if os.getenv('SUPABASE_URL') else "Not set",
                "supabase_anon_key": "Set" if os.getenv('SUPABASE_ANON_KEY') else "Not set"
            }
        }
    except Exception as e:
        logger.error(f"Supabase connection test failed: {e}")
        return {
            "status": "error",
            "message": f"Supabase connection test failed: {str(e)}",
            "details": {
                "error_type": type(e).__name__,
                "supabase_url": os.getenv('SUPABASE_URL', 'Not set')[:50] + "..." if os.getenv('SUPABASE_URL') else "Not set",
                "supabase_anon_key": "Set" if os.getenv('SUPABASE_ANON_KEY') else "Not set"
            }
        }

@router.post("/auth-client")
async def test_auth_client(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Test authenticated Supabase client creation"""
    try:
        token = credentials.credentials
        
        # Test JWT validation
        jwt_info = validate_jwt_token(token)
        if not jwt_info:
            return {
                "status": "error",
                "message": "Invalid JWT token",
                "details": {
                    "token_format": "Valid" if token.startswith('eyJ') else "Invalid",
                    "token_length": len(token)
                }
            }
        
        # Test authenticated client creation
        auth_client = get_supabase_client_with_auth(token)
        if not auth_client:
            return {
                "status": "error",
                "message": "Failed to create authenticated Supabase client",
                "details": {
                    "jwt_valid": "Yes",
                    "user_id": jwt_info.get('sub'),
                    "token_exp": jwt_info.get('exp'),
                    "token_aud": jwt_info.get('aud')
                }
            }
        
        # Test user verification
        try:
            user_response = auth_client.auth.get_user()
            user_ok = user_response and user_response.user
        except Exception as user_error:
            user_ok = False
            user_error_msg = str(user_error)
        
        return {
            "status": "success" if user_ok else "warning",
            "message": "Authenticated client test completed",
            "details": {
                "jwt_valid": "Yes",
                "auth_client_created": "Yes",
                "user_verification": "OK" if user_ok else f"Failed: {user_error_msg if not user_ok else ''}",
                "user_id": jwt_info.get('sub'),
                "token_aud": jwt_info.get('aud')
            }
        }
        
    except Exception as e:
        logger.error(f"Auth client test failed: {e}")
        return {
            "status": "error",
            "message": f"Auth client test failed: {str(e)}",
            "details": {
                "error_type": type(e).__name__,
                "token_provided": "Yes" if credentials and credentials.credentials else "No"
            }
        }

@router.get("/environment")
async def check_environment():
    """Check environment variables"""
    env_vars = {
        'SUPABASE_URL': os.getenv('SUPABASE_URL'),
        'SUPABASE_ANON_KEY': os.getenv('SUPABASE_ANON_KEY'),
        'SUPABASE_SERVICE_ROLE_KEY': os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    }
    
    return {
        "status": "success",
        "message": "Environment check completed",
        "details": {
            key: "Set" if value else "Not set" 
            for key, value in env_vars.items()
        }
    }