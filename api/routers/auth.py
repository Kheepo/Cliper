import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Request, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..models.pydantic_models import (
    UserLogin, UserCreate, TokenResponse, PasswordResetRequest, PasswordResetConfirm,
    RefreshTokenRequest, LogoutRequest, UserProfileUpdate, ForgotPasswordRequest,
    ResetPasswordRequest, PasswordResetResponse, UserProfileResponse, AuthResponse
)
import secrets
from ..utils.supabase_client import get_supabase_client, get_supabase_admin_client
from ..services.email_service import EmailService
from ..middleware.auth import require_authenticated_user, get_supabase_token_info_from_auth_middleware as get_supabase_token_info, get_current_user
from ..docs.openapi_config import COMMON_RESPONSES, AUTH_EXAMPLES

# Services are initialized as needed to avoid import-time issues
logger = logging.getLogger(__name__)

router = APIRouter(tags=["authentication"])

# Models are imported from pydantic_models module

@router.post(
    "/register",
    response_model=AuthResponse,
    summary="User Registration",
    description="""
    Register a new user account.
    
    This endpoint:
    - Creates a new user in Supabase Auth
    - Creates a corresponding user profile in the database
    - Returns authentication tokens for immediate login
    
    **Security**: Password must meet minimum requirements
    """,
    responses={
        201: {
            "description": "User registered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "email": "user@example.com",
                            "display_name": "John Doe",
                            "is_active": True,
                            "email_verified": True
                        },
                        "tokens": {
                            "access_token": "eyJ...",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                            "refresh_token": "refresh_token_here"
                        }
                    }
                }
            }
        },
         **COMMON_RESPONSES
    }
)
async def register_user(user_data: UserCreate):
    """Register a new user with email and password."""
    try:
        logger.info(f"Registration attempt for email: {user_data.email}")
        
        # Get Supabase admin client for user creation
        supabase = get_supabase_admin_client()
        if not supabase:
            logger.error("Failed to get Supabase admin client")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection failed"
            )
        
        logger.info("Supabase admin client obtained successfully")
        
        # Note: Removed auth user existence check as it was causing false positives
        # Supabase will handle duplicate email prevention during user creation
        
        # Check if user already exists in profile table (lightweight check)
        try:
            logger.info("Checking for existing users in profile table")
            existing_profile = supabase.table('users').select('id').eq('email', user_data.email).execute()
            if existing_profile.data:
                logger.warning(f"Profile user already exists for: {user_data.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email address [{user_data.email}] is already registered"
                )
            
            logger.info("No existing user found in profile table")
        
        except HTTPException:
            # Re-raise HTTPExceptions (like duplicate user errors)
            raise
        except Exception as check_error:
            logger.error(f"Error checking for existing users: {check_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify user registration status"
            )
        
        auth_user = None
        try:
            logger.info("Creating user in Supabase Auth")
            # Create user in Supabase Auth (this will auto-create the profile via database trigger)
            auth_response = supabase.auth.admin.create_user({
                "email": user_data.email,
                "password": user_data.password,
                "email_confirm": True  # Auto-confirm email for development
            })
            
            if not auth_response.user:
                logger.error("Auth response did not contain user data")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account"
                )
            
            auth_user = auth_response.user
            logger.info(f"User created in auth successfully: {auth_user.id}")
            logger.info(f"Created auth user {auth_user.id} for email {user_data.email}")
            
            # Wait a moment for the database trigger to create the profile
            import time
            time.sleep(0.5)
            
            # Get the auto-created user profile
            logger.info("Retrieving auto-created user profile")
            profile_response = supabase.table("users").select("*").eq("auth_id", auth_user.id).execute()
            
            if not profile_response.data:
                logger.error("Auto-created profile not found")
                raise Exception("User profile was not automatically created")
            
            user_profile = profile_response.data[0]
            logger.info(f"Retrieved auto-created profile: {user_profile['id']}")
            
            # Update the profile with additional data if needed
            update_data = {
                "display_name": getattr(user_data, 'full_name', None) or user_data.email.split('@')[0],
                "email_verified": True,  # Auto-verified for development
                "last_login": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Updating profile with additional data: {update_data}")
            logger.info(f"Profile ID to update: {user_profile['id']}")
            logger.info(f"Auth user ID: {auth_user.id}")
            
            try:
                update_response = supabase.table("users").update(update_data).eq("id", user_profile["id"]).execute()
                logger.info(f"Update response: {update_response}")
            except Exception as update_error:
                logger.error(f"Profile update failed with error: {update_error}")
                logger.error(f"Error type: {type(update_error)}")
                raise update_error
            
            if update_response.data:
                user_profile = update_response.data[0]
                logger.info(f"Successfully updated user profile {user_profile['id']}")
            else:
                logger.warning("Profile update returned no data, using original profile")
            
        except Exception as creation_error:
            # Cleanup: delete auth user if it was created but profile setup failed
            if auth_user:
                try:
                    supabase.auth.admin.delete_user(auth_user.id)
                    logger.info(f"Cleaned up auth user {auth_user.id} after profile setup failure")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup auth user {auth_user.id}: {cleanup_error}")
            
            # Re-raise the original error if it's already an HTTPException
            if isinstance(creation_error, HTTPException):
                raise creation_error
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to setup user profile: {str(creation_error)}"
            )
        
        # Sign in the user to get tokens (no need for generate_link)
        signin_response = supabase.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password
        })
        
        if not signin_response.session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user session"
            )
        
        session = signin_response.session
        
        return AuthResponse(
            user=UserProfileResponse(**user_profile),
            tokens=TokenResponse(
                access_token=session.access_token,
                token_type="Bearer",
                expires_in=session.expires_in or 3600,
                refresh_token=session.refresh_token
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post(
    "/login",
    response_model=AuthResponse,
    summary="User Login",
    description="""
    Authenticate user with email and password.
    
    This endpoint:
    - Validates user credentials
    - Returns authentication tokens and user data
    - Updates last login timestamp
    
    **Security**: Requires valid email and password
    """,
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "email": "user@example.com",
                            "display_name": "John Doe",
                            "is_active": True,
                            "email_verified": True
                        },
                        "tokens": {
                            "access_token": "eyJ...",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                            "refresh_token": "refresh_token_here"
                        }
                    }
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def login_user(user_credentials: UserLogin):
    """Authenticate user and return tokens"""
    try:
        supabase = get_supabase_admin_client()
        
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": user_credentials.email,
            "password": user_credentials.password
        })
        
        if not auth_response.session or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        session = auth_response.session
        auth_user = auth_response.user
        
        # Get user profile from database
        profile_response = supabase.table("users").select("*").eq("auth_id", auth_user.id).execute()
        
        if not profile_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        user_profile = profile_response.data[0]
        
        # Check if user is active
        if not user_profile.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Update last login timestamp
        supabase.table("users").update({
            "last_login": datetime.utcnow().isoformat()
        }).eq("id", user_profile["id"]).execute()
        
        # Update user profile with new last_login
        user_profile["last_login"] = datetime.utcnow().isoformat()
        
        return AuthResponse(
            user=UserProfileResponse(**user_profile),
            tokens=TokenResponse(
                access_token=session.access_token,
                token_type="Bearer",
                expires_in=session.expires_in or 3600,
                refresh_token=session.refresh_token
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        error_message = str(e).lower()
        
        # Check if it's an authentication error (invalid credentials)
        if any(phrase in error_message for phrase in ['invalid login credentials', 'invalid email or password', 'authentication failed']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # For other errors, return 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post(
    "/verify", 
    response_model=AuthResponse,
    summary="Verify Authentication Token",
    description="""
    Verify a Supabase JWT token and retrieve or create the user profile.
    
    This endpoint:
    - Validates the provided JWT token
    - Retrieves existing user data or creates a new user profile
    - Updates the last login timestamp
    - Creates default user settings for new users
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Token verified successfully",
            "content": {
                "application/json": {
                    "example": AUTH_EXAMPLES["auth_response"]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def verify_token(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_authenticated_user)
):
    try:
        supabase = get_supabase_admin_client()
        user_uid = current_user.get('sub') or current_user.get('uid')
        email = current_user.get('email')
        
        if not user_uid or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid or email"
            )
        
        # Check if user exists
        existing_user = supabase.table('users').select('*').eq('auth_id', user_uid).execute()
        
        if existing_user.data:
            # Update last login
            user_data = existing_user.data[0]
            supabase.table('users').update({
                'last_login': datetime.utcnow().isoformat()
            }).eq('id', user_data['id']).execute()
            
            user_data['last_login'] = datetime.utcnow().isoformat()
        else:
            # Create new user
            new_user = {
                'auth_id': user_uid,
                'email': email,
                'display_name': current_user.get('user_metadata', {}).get('display_name') or current_user.get('name'),
                'photo_url': current_user.get('user_metadata', {}).get('avatar_url') or current_user.get('picture'),
                'last_login': datetime.utcnow().isoformat()
            }
            
            result = supabase.table('users').insert(new_user).execute()
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )
            user_data = result.data[0]
            
            # Create default user settings
            supabase.table('user_settings').insert({
                'user_id': user_data['id']
            }).execute()
        
        # Extract token from request headers (already validated by middleware)
        authorization = request.headers.get('Authorization', '')
        access_token = authorization.replace('Bearer ', '') if authorization.startswith('Bearer ') else ''
        
        return AuthResponse(
            user=UserProfileResponse(**user_data),
            tokens=TokenResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_in=3600,
                refresh_token=None
            ),
            message="Token verified successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )

@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get Current User Profile",
    description="""
    Retrieve the current authenticated user's profile information.
    
    Returns complete user profile data including:
    - User identification details
    - Profile information (name, photo)
    - Account status and timestamps
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "User profile retrieved successfully",
            "content": {
                "application/json": {
                    "example": AUTH_EXAMPLES["user_response"]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def get_current_user_profile(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_authenticated_user)
):
    try:
        supabase = get_supabase_admin_client()
        user_uid = current_user.get('sub') or current_user.get('uid')
        
        if not user_uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('*').eq('auth_id', user_uid).execute()
        
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserProfileResponse(**user_result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user profile: {str(e)}"
        )

@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Update User Profile",
    description="""
    Update the current authenticated user's profile information.
    
    Allows updating:
    - Display name (1-100 characters)
    - Profile photo URL
    
    Only provided fields will be updated. Omitted fields remain unchanged.
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Profile updated successfully",
            "content": {
                "application/json": {
                    "example": AUTH_EXAMPLES["user_response"]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_authenticated_user)
):
    try:
        supabase = get_supabase_admin_client()
        user_uid = current_user.get('sub') or current_user.get('uid')
        
        if not user_uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Prepare update data
        update_data = {}
        if profile_update.display_name is not None:
            update_data['display_name'] = profile_update.display_name
        if profile_update.photo_url is not None:
            update_data['photo_url'] = profile_update.photo_url
        
        if not update_data:
            # No updates to make, just return current user
            user_result = supabase.table('users').select('*').eq('auth_id', user_uid).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            return UserProfileResponse(**user_result.data[0])
        
        # Update user
        result = supabase.table('users').update(update_data).eq('auth_id', user_uid).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserProfileResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating profile: {str(e)}"
        )

# Logout endpoint is implemented below with token blacklisting

@router.delete("/account")
async def delete_user_account(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_authenticated_user)
):
    """Delete user account (both from Supabase Auth and database)"""
    try:
        supabase = get_supabase_admin_client()
        user_uid = current_user.get('sub') or current_user.get('uid')
        
        if not user_uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Delete from database first (cascade will handle related records)
        result = supabase.table('users').delete().eq('auth_id', user_uid).execute()
        
        # Delete from Supabase Auth
        auth_result = supabase.auth.admin.delete_user(user_uid)
        
        if not auth_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting user from Supabase Auth"
            )
        
        return {"message": "Account deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting account: {str(e)}"
        )

@router.get("/status")
async def auth_status(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Check authentication status"""
    try:
        if current_user:
            supabase = get_supabase_admin_client()
            user_uid = current_user.get('sub') or current_user.get('uid')
            
            if user_uid:
                user_result = supabase.table('users').select('id', 'email').eq('auth_id', user_uid).execute()
                
                if user_result.data:
                    user_data = user_result.data[0]
                    return {
                        "authenticated": True,
                        "user_id": user_data['id'],
                        "email": user_data['email']
                    }
        
        return {"authenticated": False}
        
    except Exception:
        return {"authenticated": False}

@router.post(
    "/forgot-password",
    response_model=PasswordResetResponse,
    summary="Request Password Reset",
    description="""
    Send a password reset email to the user.
    
    This endpoint:
    - Validates the email address
    - Generates a secure reset token
    - Stores the token with expiration
    - Sends reset email (requires email service)
    
    **Rate Limited**: Maximum 3 requests per hour per email
    """,
    responses={
        200: {
            "description": "Password reset email sent successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Password reset email sent successfully",
                        "success": True
                    }
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def forgot_password(request: ForgotPasswordRequest):
    """Send password reset email"""
    try:
        supabase = get_supabase_admin_client()
        
        # Check if user exists
        user_result = supabase.table('users').select('id, email, auth_id').eq('email', request.email).execute()
        
        if not user_result.data:
            # Don't reveal if email exists or not for security
            return PasswordResetResponse(
                message="If an account with this email exists, a password reset link has been sent.",
                success=True
            )
        
        user = user_result.data[0]
        
        # Generate secure reset token
        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        
        # Set expiration (1 hour from now)
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        # Store reset token in database
        supabase.table('password_reset_tokens').insert({
            'user_id': user['id'],
            'token_hash': token_hash,
            'expires_at': expires_at,
            'used': False,
            'created_at': datetime.utcnow().isoformat()
        }).execute()
        
        # Send password reset email
        user_name = user.get('display_name') or request.email.split('@')[0]
        email_service = EmailService()
        email_sent = email_service.send_password_reset_email(
            to_email=request.email,
            reset_token=reset_token,
            user_name=user_name
        )
        
        if not email_sent:
            print(f"Failed to send password reset email to {request.email}")
            # Don't fail the request if email fails, but log it
        
        print(f"Password reset token generated for user {user['id']}, email sent: {email_sent}")
        
        return PasswordResetResponse(
            message="If an account with this email exists, a password reset link has been sent.",
            success=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing password reset request: {str(e)}"
        )

@router.post(
    "/reset-password",
    response_model=PasswordResetResponse,
    summary="Reset Password",
    description="""
    Reset user password using a valid reset token.
    
    This endpoint:
    - Validates the reset token
    - Checks token expiration
    - Updates the user's password
    - Invalidates the reset token
    
    **Security**: Tokens are single-use and expire after 1 hour
    """,
    responses={
        200: {
            "description": "Password reset successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Password reset successfully",
                        "success": True
                    }
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def reset_password(request: ResetPasswordRequest):
    """Reset password with token"""
    try:
        supabase = get_supabase_admin_client()
        
        # Hash the provided token
        token_hash = hashlib.sha256(request.token.encode()).hexdigest()
        
        # Find valid reset token
        token_result = supabase.table('password_reset_tokens').select(
            'id, user_id, expires_at, used'
        ).eq('token_hash', token_hash).eq('used', False).execute()
        
        if not token_result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        token_data = token_result.data[0]
        
        # Check if token is expired
        expires_at = datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired"
            )
        
        # Get user auth_id
        user_result = supabase.table('users').select('auth_id').eq('id', token_data['user_id']).execute()
        
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        auth_id = user_result.data[0]['auth_id']
        
        # Update password in Supabase Auth
        try:
            supabase.auth.admin.update_user_by_id(
                auth_id,
                {"password": request.new_password}
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update password: {str(e)}"
            )
        
        # Mark token as used
        supabase.table('password_reset_tokens').update({
            'used': True,
            'used_at': datetime.utcnow().isoformat()
        }).eq('id', token_data['id']).execute()
        
        return PasswordResetResponse(
            message="Password reset successfully",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resetting password: {str(e)}"
        )

@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refresh Access Token",
    description="""
    Refresh an expired access token using a valid refresh token.
    
    This endpoint:
    - Validates the refresh token
    - Issues a new access token
    - Returns updated user information
    
    **Authentication Required**: Valid refresh token
    """
)
async def refresh_token(
    refresh_token: str = Form(..., description="Valid refresh token")
):
    """Refresh access token using refresh token"""
    try:
        supabase = get_supabase_admin_client()
        
        # Refresh the session using Supabase
        response = supabase.auth.refresh_session(refresh_token)
        
        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid or expired refresh token"
            )
        
        # Get user data
        user_data = response.user
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="User not found"
            )
        
        # Get user from database
        db_user_response = supabase.table("users").select("*").eq("auth_id", user_data.id).execute()
        
        if not db_user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        db_user = db_user_response.data[0]
        
        # Update last login
        supabase.table('users').update({
            'last_login': datetime.utcnow().isoformat()
        }).eq('id', db_user['id']).execute()
        
        return AuthResponse(
            user=UserProfileResponse(**db_user),
            message="Token refreshed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to refresh token"
        )

@router.post(
    "/logout",
    summary="Logout User",
    description="""
    Logout the current authenticated user and invalidate their session.
    
    This endpoint:
    - Invalidates the current JWT token by adding it to a blacklist
    - Updates the user's last logout timestamp
    - Ensures the token cannot be used for future requests
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Logged out successfully",
            "content": {
                "application/json": {
                    "example": {"message": "Logged out successfully"}
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def logout_user(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_authenticated_user)
):
    """Logout user and invalidate session"""
    try:
        # Get the JWT token from the request
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="No token provided"
            )
        
        token = authorization.split(" ")[1]
        
        # Get token info to extract expiration
        token_info = get_supabase_token_info(token)
        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token"
            )
        
        # Add token to blacklist with expiration time
        supabase = get_supabase_admin_client()
        
        # Store blacklisted token
        blacklist_data = {
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "user_id": current_user["id"],
            "expires_at": datetime.fromtimestamp(token_info["exp"]).isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("token_blacklist").insert(blacklist_data).execute()
        
        # Update user's last logout time
        supabase.table("users").update({
            "last_logout": datetime.utcnow().isoformat()
        }).eq("id", current_user["id"]).execute()
        
        return {"message": "Logged out successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Logout failed"
        )

@router.get(
    "/test-supabase",
    summary="Test Supabase Connectivity",
    description="Test endpoint to verify Supabase client creation and connectivity",
    responses={
        200: {
            "description": "Supabase connectivity test results",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Supabase connectivity verified",
                        "details": {
                            "admin_client": True,
                            "regular_client": True,
                            "database_connection": True
                        }
                    }
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def test_supabase_connectivity():
    """Test Supabase client creation and basic connectivity"""
    results = {
        "status": "success",
        "message": "Supabase connectivity verified",
        "details": {
            "admin_client": False,
            "regular_client": False,
            "database_connection": False,
            "errors": []
        }
    }
    
    try:
        # Test admin client creation
        try:
            admin_client = get_supabase_admin_client()
            if admin_client:
                results["details"]["admin_client"] = True
                logger.info("Admin client created successfully")
            else:
                results["details"]["errors"].append("Admin client creation returned None")
        except Exception as e:
            results["details"]["errors"].append(f"Admin client error: {str(e)}")
            logger.error(f"Admin client creation failed: {e}")
        
        # Test regular client creation
        try:
            regular_client = get_supabase_client()
            if regular_client:
                results["details"]["regular_client"] = True
                logger.info("Regular client created successfully")
            else:
                results["details"]["errors"].append("Regular client creation returned None")
        except Exception as e:
            results["details"]["errors"].append(f"Regular client error: {str(e)}")
            logger.error(f"Regular client creation failed: {e}")
        
        # Test database connection with a simple query
        try:
            if admin_client:
                # Try a simple query to test database connectivity
                test_response = admin_client.table('users').select('id').limit(1).execute()
                results["details"]["database_connection"] = True
                logger.info("Database connection test successful")
            else:
                results["details"]["errors"].append("Cannot test database - no admin client")
        except Exception as e:
            results["details"]["errors"].append(f"Database connection error: {str(e)}")
            logger.error(f"Database connection test failed: {e}")
        
        # Determine overall status
        if results["details"]["errors"]:
            results["status"] = "partial" if any([results["details"]["admin_client"], results["details"]["regular_client"]]) else "failed"
            results["message"] = "Supabase connectivity issues detected"
        
        return results
        
    except Exception as e:
        logger.error(f"Supabase connectivity test failed: {e}")
        return {
            "status": "failed",
            "message": "Supabase connectivity test failed",
            "details": {
                "admin_client": False,
                "regular_client": False,
                "database_connection": False,
                "errors": [f"Test execution error: {str(e)}"]
            }
        }

# Export the router with the expected name
auth_router = router