from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging
from pydantic import BaseModel, EmailStr

from ..services.email_service import EmailService
from ..middleware.auth import get_supabase_token_info_from_auth_middleware as get_supabase_token_info
from ..utils.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["email"])

class EmailTestRequest(BaseModel):
    """Request model for testing email functionality"""
    to_email: EmailStr
    test_type: str = "welcome"  # welcome, password_reset
    
    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "user@example.com",
                "test_type": "welcome"
            }
        }

class EmailConfigResponse(BaseModel):
    """Response model for email configuration status"""
    configured: bool
    smtp_server: str
    smtp_port: int
    from_email: str
    from_name: str
    username_configured: bool
    password_configured: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "configured": True,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "from_email": "noreply@cliper.com",
                "from_name": "Cliper",
                "username_configured": True,
                "password_configured": True
            }
        }

class EmailTestResponse(BaseModel):
    """Response model for email test results"""
    success: bool
    message: str
    email_sent: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Test email sent successfully",
                "email_sent": True
            }
        }

@router.get("/config", response_model=EmailConfigResponse)
async def get_email_config(
    token_info: dict = Depends(get_supabase_token_info)
):
    """Get email service configuration status
    
    Requires authentication. Returns the current email service configuration
    without exposing sensitive credentials.
    """
    try:
        # Check if user has admin role (optional - you can remove this check)
        supabase = get_supabase_client()
        user_response = supabase.table("users").select("role").eq("auth_id", token_info["sub"]).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_role = user_response.data[0].get("role")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        email_service = EmailService()
        config = email_service.get_configuration_status()
        return EmailConfigResponse(**config)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get email configuration")

@router.post("/test", response_model=EmailTestResponse)
async def test_email(
    request: EmailTestRequest,
    token_info: dict = Depends(get_supabase_token_info)
):
    """Test email functionality by sending a test email
    
    Requires authentication. Sends a test email to verify email service is working.
    """
    try:
        # Check if user has admin role (optional)
        supabase = get_supabase_client()
        user_response = supabase.table("users").select("role, display_name").eq("auth_id", token_info["sub"]).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_response.data[0]
        user_role = user_data.get("role")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        email_service = EmailService()
        if not email_service.configured:
            return EmailTestResponse(
                success=False,
                message="Email service not configured. Please set SMTP credentials.",
                email_sent=False
            )
        
        # Send test email based on type
        email_sent = False
        user_name = user_data.get("display_name") or "Test User"
        
        if request.test_type == "welcome":
            email_sent = email_service.send_welcome_email(
                to_email=request.to_email,
                user_name=user_name
            )
        elif request.test_type == "password_reset":
            # Send test password reset email with dummy token
            email_sent = email_service.send_password_reset_email(
                to_email=request.to_email,
                reset_token="test-token-123",
                user_name=user_name
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid test_type. Use 'welcome' or 'password_reset'")
        
        if email_sent:
            return EmailTestResponse(
                success=True,
                message=f"Test {request.test_type} email sent successfully to {request.to_email}",
                email_sent=True
            )
        else:
            return EmailTestResponse(
                success=False,
                message="Failed to send test email. Check SMTP configuration and logs.",
                email_sent=False
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing email: {e}")
        raise HTTPException(status_code=500, detail="Failed to test email functionality")

@router.get("/health")
async def email_health_check():
    """Public endpoint to check email service health
    
    Returns basic health status without exposing configuration details.
    """
    try:
        email_service = EmailService()
        return {
            "status": "healthy" if email_service.configured else "not_configured",
            "service": "email",
            "configured": email_service.configured,
            "timestamp": "2024-01-01T00:00:00Z"  # You can use datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Email health check failed: {e}")
        return {
            "status": "error",
            "service": "email",
            "configured": False,
            "error": str(e)
        }