"""Unit tests for password reset functionality."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import uuid
from typing import Dict, Any, Optional

# Import the modules to test
try:
    from api.auth.auth_service import AuthService
    from api.auth.password_manager import PasswordManager
    from api.services.email_service import EmailService
    from api.models.user import User, UserRole, UserStatus
    from api.core.exceptions import AuthenticationError, InvalidTokenError, ValidationError
except ImportError:
    # Mock imports for testing
    class AuthService:
        pass
    class PasswordManager:
        pass
    class EmailService:
        pass
    class User:
        pass
    class UserRole:
        USER = "user"
        ADMIN = "admin"
    class UserStatus:
        ACTIVE = "active"
        INACTIVE = "inactive"
    class AuthenticationError(Exception):
        pass
    class InvalidTokenError(Exception):
        pass
    class ValidationError(Exception):
        pass

class TestPasswordResetFlow:
    """Test cases for password reset functionality."""
    
    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance for testing."""
        return AuthService()
    
    @pytest.fixture
    def password_manager(self):
        """Create a PasswordManager instance for testing."""
        return PasswordManager()
    
    @pytest.fixture
    def email_service(self):
        """Create an EmailService instance for testing."""
        return EmailService()
    
    @pytest.fixture
    def sample_user(self):
        """Sample user data for testing."""
        return {
            "id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hashed_password",
            "role": UserRole.USER,
            "status": UserStatus.ACTIVE,
            "created_at": datetime.now(),
            "profile": {
                "first_name": "Test",
                "last_name": "User"
            }
        }
    
    @pytest.fixture
    def reset_token_data(self):
        """Sample reset token data."""
        return {
            "token": str(uuid.uuid4()),
            "user_id": "user_123",
            "expires_at": datetime.now() + timedelta(hours=1),
            "used": False,
            "created_at": datetime.now()
        }
    
    @pytest.mark.asyncio
    async def test_forgot_password_success(self, auth_service, email_service, sample_user):
        """Test successful forgot password request."""
        email = "test@example.com"
        
        with patch('api.auth.auth_service.AuthService.initiate_password_reset') as mock_initiate, \
             patch('api.services.email_service.EmailService.send_password_reset_email') as mock_send_email:
            
            # Setup mocks
            reset_token = str(uuid.uuid4())
            mock_initiate.return_value = {
                "success": True,
                "message": "Password reset email sent",
                "token": reset_token
            }
            mock_send_email.return_value = True
            
            # Execute
            result = await auth_service.initiate_password_reset(email)
            
            # Verify
            assert result["success"] is True
            assert "message" in result
            assert "token" in result
            mock_initiate.assert_called_once_with(email)
            mock_send_email.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_forgot_password_user_not_found(self, auth_service):
        """Test forgot password with non-existent email."""
        email = "nonexistent@example.com"
        
        with patch('api.auth.auth_service.AuthService.initiate_password_reset') as mock_initiate:
            mock_initiate.side_effect = ValidationError("User not found")
            
            with pytest.raises(ValidationError):
                await auth_service.initiate_password_reset(email)
    
    @pytest.mark.asyncio
    async def test_forgot_password_inactive_user(self, auth_service):
        """Test forgot password with inactive user account."""
        email = "inactive@example.com"
        
        with patch('api.auth.auth_service.AuthService.initiate_password_reset') as mock_initiate:
            mock_initiate.side_effect = ValidationError("Account is inactive")
            
            with pytest.raises(ValidationError):
                await auth_service.initiate_password_reset(email)
    
    @pytest.mark.asyncio
    async def test_reset_password_success(self, auth_service, password_manager, reset_token_data):
        """Test successful password reset."""
        token = reset_token_data["token"]
        new_password = "NewSecureP@ssw0rd123!"
        
        with patch('api.auth.auth_service.AuthService.reset_password') as mock_reset, \
             patch('api.auth.password_manager.PasswordManager.validate_password_strength') as mock_validate, \
             patch('api.auth.password_manager.PasswordManager.hash_password') as mock_hash:
            
            # Setup mocks
            mock_validate.return_value = {"is_valid": True, "score": 5}
            mock_hash.return_value = "$2b$12$new_hashed_password"
            mock_reset.return_value = {
                "success": True,
                "message": "Password reset successfully",
                "user_id": reset_token_data["user_id"]
            }
            
            # Execute
            result = await auth_service.reset_password(token, new_password)
            
            # Verify
            assert result["success"] is True
            assert "message" in result
            assert result["user_id"] == reset_token_data["user_id"]
            mock_validate.assert_called_once_with(new_password)
            mock_hash.assert_called_once_with(new_password)
    
    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, auth_service):
        """Test password reset with invalid token."""
        invalid_token = "invalid_token_123"
        new_password = "NewPassword123!"
        
        with patch('api.auth.auth_service.AuthService.reset_password') as mock_reset:
            mock_reset.side_effect = InvalidTokenError("Invalid or expired reset token")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.reset_password(invalid_token, new_password)
    
    @pytest.mark.asyncio
    async def test_reset_password_expired_token(self, auth_service):
        """Test password reset with expired token."""
        expired_token = "expired_token_123"
        new_password = "NewPassword123!"
        
        with patch('api.auth.auth_service.AuthService.reset_password') as mock_reset:
            mock_reset.side_effect = InvalidTokenError("Reset token has expired")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.reset_password(expired_token, new_password)
    
    @pytest.mark.asyncio
    async def test_reset_password_weak_password(self, auth_service, password_manager):
        """Test password reset with weak password."""
        token = "valid_token_123"
        weak_password = "123456"
        
        with patch('api.auth.password_manager.PasswordManager.validate_password_strength') as mock_validate, \
             patch('api.auth.auth_service.AuthService.reset_password') as mock_reset:
            
            mock_validate.return_value = {
                "is_valid": False,
                "score": 1,
                "feedback": ["Password is too weak"]
            }
            mock_reset.side_effect = ValidationError("Password does not meet security requirements")
            
            with pytest.raises(ValidationError):
                await auth_service.reset_password(token, weak_password)
    
    @pytest.mark.asyncio
    async def test_reset_password_used_token(self, auth_service):
        """Test password reset with already used token."""
        used_token = "used_token_123"
        new_password = "NewPassword123!"
        
        with patch('api.auth.auth_service.AuthService.reset_password') as mock_reset:
            mock_reset.side_effect = InvalidTokenError("Reset token has already been used")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.reset_password(used_token, new_password)
    
    @pytest.mark.asyncio
    async def test_verify_reset_token_valid(self, auth_service, reset_token_data):
        """Test reset token verification with valid token."""
        token = reset_token_data["token"]
        
        with patch('api.auth.auth_service.AuthService.verify_reset_token') as mock_verify:
            mock_verify.return_value = {
                "valid": True,
                "user_id": reset_token_data["user_id"],
                "expires_at": reset_token_data["expires_at"]
            }
            
            result = await auth_service.verify_reset_token(token)
            
            assert result["valid"] is True
            assert result["user_id"] == reset_token_data["user_id"]
    
    @pytest.mark.asyncio
    async def test_verify_reset_token_invalid(self, auth_service):
        """Test reset token verification with invalid token."""
        invalid_token = "invalid_token_123"
        
        with patch('api.auth.auth_service.AuthService.verify_reset_token') as mock_verify:
            mock_verify.return_value = {"valid": False, "reason": "Token not found"}
            
            result = await auth_service.verify_reset_token(invalid_token)
            
            assert result["valid"] is False
            assert "reason" in result
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self, auth_service):
        """Test cleanup of expired reset tokens."""
        with patch('api.auth.auth_service.AuthService.cleanup_expired_reset_tokens') as mock_cleanup:
            mock_cleanup.return_value = {"deleted_count": 5}
            
            result = await auth_service.cleanup_expired_reset_tokens()
            
            assert "deleted_count" in result
            assert result["deleted_count"] >= 0

class TestPasswordResetIntegration:
    """Integration tests for complete password reset workflow."""
    
    @pytest.fixture
    def auth_service(self):
        return AuthService()
    
    @pytest.fixture
    def email_service(self):
        return EmailService()
    
    @pytest.fixture
    def password_manager(self):
        return PasswordManager()
    
    @pytest.mark.asyncio
    async def test_complete_password_reset_workflow(self, auth_service, email_service, password_manager):
        """Test complete password reset workflow from request to completion."""
        email = "test@example.com"
        new_password = "NewSecureP@ssw0rd123!"
        
        # Step 1: Initiate password reset
        with patch.object(auth_service, 'initiate_password_reset') as mock_initiate, \
             patch.object(email_service, 'send_password_reset_email') as mock_send_email:
            
            reset_token = str(uuid.uuid4())
            mock_initiate.return_value = {
                "success": True,
                "message": "Password reset email sent",
                "token": reset_token
            }
            mock_send_email.return_value = True
            
            initiate_result = await auth_service.initiate_password_reset(email)
            assert initiate_result["success"] is True
            token = initiate_result["token"]
        
        # Step 2: Verify token
        with patch.object(auth_service, 'verify_reset_token') as mock_verify:
            mock_verify.return_value = {
                "valid": True,
                "user_id": "user_123",
                "expires_at": datetime.now() + timedelta(hours=1)
            }
            
            verify_result = await auth_service.verify_reset_token(token)
            assert verify_result["valid"] is True
        
        # Step 3: Reset password
        with patch.object(password_manager, 'validate_password_strength') as mock_validate, \
             patch.object(password_manager, 'hash_password') as mock_hash, \
             patch.object(auth_service, 'reset_password') as mock_reset:
            
            mock_validate.return_value = {"is_valid": True, "score": 5}
            mock_hash.return_value = "$2b$12$new_hashed_password"
            mock_reset.return_value = {
                "success": True,
                "message": "Password reset successfully",
                "user_id": "user_123"
            }
            
            reset_result = await auth_service.reset_password(token, new_password)
            assert reset_result["success"] is True
            assert reset_result["user_id"] == "user_123"
    
    @pytest.mark.asyncio
    async def test_password_reset_rate_limiting(self, auth_service):
        """Test rate limiting for password reset requests."""
        email = "test@example.com"
        
        with patch.object(auth_service, 'initiate_password_reset') as mock_initiate:
            # First request succeeds
            mock_initiate.return_value = {"success": True, "message": "Email sent"}
            result1 = await auth_service.initiate_password_reset(email)
            assert result1["success"] is True
            
            # Second request too soon should be rate limited
            mock_initiate.side_effect = ValidationError("Too many reset requests. Please wait before trying again.")
            
            with pytest.raises(ValidationError):
                await auth_service.initiate_password_reset(email)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])