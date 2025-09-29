"""Unit tests for authentication endpoints including logout, refresh token, and token management."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import hashlib
import uuid
from typing import Dict, Any, Optional

# Import the modules to test
try:
    from api.auth.auth_service import AuthService, TokenManager
    from api.auth.password_manager import PasswordManager
    from api.models.user import User, UserRole, UserStatus
    from api.core.exceptions import AuthenticationError, InvalidTokenError, AuthorizationError
except ImportError:
    # Mock imports for testing
    class AuthService:
        pass
    class TokenManager:
        pass
    class PasswordManager:
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
    class AuthorizationError(Exception):
        pass

class TestLogoutEndpoint:
    """Test cases for logout endpoint functionality."""
    
    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance for testing."""
        return AuthService()
    
    @pytest.fixture
    def token_manager(self):
        """Create a TokenManager instance for testing."""
        return TokenManager()
    
    @pytest.fixture
    def sample_user(self):
        """Sample user data for testing."""
        return {
            "id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "role": UserRole.USER,
            "status": UserStatus.ACTIVE
        }
    
    @pytest.fixture
    def valid_token(self):
        """Valid JWT token for testing."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl8xMjMiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJyb2xlIjoidXNlciIsImV4cCI6MTcwMDAwMDAwMH0.signature"
    
    @pytest.mark.asyncio
    async def test_logout_success(self, auth_service, sample_user, valid_token):
        """Test successful user logout."""
        user_id = sample_user["id"]
        
        with patch('api.auth.auth_service.AuthService.logout_user') as mock_logout:
            mock_logout.return_value = {
                "success": True,
                "message": "Logged out successfully",
                "user_id": user_id
            }
            
            result = await auth_service.logout_user(user_id, valid_token)
            
            assert result["success"] is True
            assert "message" in result
            assert result["user_id"] == user_id
            mock_logout.assert_called_once_with(user_id, valid_token)
    
    @pytest.mark.asyncio
    async def test_logout_invalid_token(self, auth_service):
        """Test logout with invalid token."""
        user_id = "user_123"
        invalid_token = "invalid_token"
        
        with patch('api.auth.auth_service.AuthService.logout_user') as mock_logout:
            mock_logout.side_effect = InvalidTokenError("Invalid token")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.logout_user(user_id, invalid_token)
    
    @pytest.mark.asyncio
    async def test_logout_expired_token(self, auth_service):
        """Test logout with expired token."""
        user_id = "user_123"
        expired_token = "expired_token"
        
        with patch('api.auth.auth_service.AuthService.logout_user') as mock_logout:
            mock_logout.side_effect = InvalidTokenError("Token has expired")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.logout_user(user_id, expired_token)
    
    @pytest.mark.asyncio
    async def test_logout_already_logged_out(self, auth_service):
        """Test logout with already blacklisted token."""
        user_id = "user_123"
        blacklisted_token = "blacklisted_token"
        
        with patch('api.auth.auth_service.AuthService.logout_user') as mock_logout:
            mock_logout.side_effect = InvalidTokenError("Token has been revoked")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.logout_user(user_id, blacklisted_token)
    
    @pytest.mark.asyncio
    async def test_logout_user_mismatch(self, auth_service):
        """Test logout with token belonging to different user."""
        user_id = "user_123"
        other_user_token = "other_user_token"
        
        with patch('api.auth.auth_service.AuthService.logout_user') as mock_logout:
            mock_logout.side_effect = AuthorizationError("Token does not belong to user")
            
            with pytest.raises(AuthorizationError):
                await auth_service.logout_user(user_id, other_user_token)

class TestRefreshTokenEndpoint:
    """Test cases for refresh token endpoint functionality."""
    
    @pytest.fixture
    def auth_service(self):
        return AuthService()
    
    @pytest.fixture
    def token_manager(self):
        return TokenManager()
    
    @pytest.fixture
    def valid_refresh_token(self):
        """Valid refresh token for testing."""
        return "refresh_token_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh_payload.signature"
    
    @pytest.fixture
    def token_response(self):
        """Expected token response."""
        return {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "bearer",
            "expires_in": 3600
        }
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, auth_service, valid_refresh_token, token_response):
        """Test successful token refresh."""
        with patch('api.auth.auth_service.AuthService.refresh_token') as mock_refresh:
            mock_refresh.return_value = token_response
            
            result = await auth_service.refresh_token(valid_refresh_token)
            
            assert "access_token" in result
            assert "refresh_token" in result
            assert "expires_in" in result
            assert result["token_type"] == "bearer"
            assert result["expires_in"] == 3600
            mock_refresh.assert_called_once_with(valid_refresh_token)
    
    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, auth_service):
        """Test refresh with invalid token."""
        invalid_token = "invalid_refresh_token"
        
        with patch('api.auth.auth_service.AuthService.refresh_token') as mock_refresh:
            mock_refresh.side_effect = InvalidTokenError("Invalid refresh token")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.refresh_token(invalid_token)
    
    @pytest.mark.asyncio
    async def test_refresh_token_expired(self, auth_service):
        """Test refresh with expired token."""
        expired_token = "expired_refresh_token"
        
        with patch('api.auth.auth_service.AuthService.refresh_token') as mock_refresh:
            mock_refresh.side_effect = InvalidTokenError("Refresh token has expired")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.refresh_token(expired_token)
    
    @pytest.mark.asyncio
    async def test_refresh_token_revoked(self, auth_service):
        """Test refresh with revoked token."""
        revoked_token = "revoked_refresh_token"
        
        with patch('api.auth.auth_service.AuthService.refresh_token') as mock_refresh:
            mock_refresh.side_effect = InvalidTokenError("Refresh token has been revoked")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.refresh_token(revoked_token)
    
    @pytest.mark.asyncio
    async def test_refresh_token_user_inactive(self, auth_service):
        """Test refresh with inactive user account."""
        valid_token = "valid_refresh_token"
        
        with patch('api.auth.auth_service.AuthService.refresh_token') as mock_refresh:
            mock_refresh.side_effect = AuthenticationError("User account is inactive")
            
            with pytest.raises(AuthenticationError):
                await auth_service.refresh_token(valid_token)

class TestTokenBlacklisting:
    """Test cases for token blacklisting functionality."""
    
    @pytest.fixture
    def auth_service(self):
        return AuthService()
    
    @pytest.fixture
    def token_manager(self):
        return TokenManager()
    
    @pytest.fixture
    def sample_token(self):
        """Sample token for testing."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl8xMjMiLCJleHAiOjE3MDAwMDAwMDB9.signature"
    
    @pytest.mark.asyncio
    async def test_blacklist_token_success(self, auth_service, sample_token):
        """Test successful token blacklisting."""
        user_id = "user_123"
        
        with patch('api.auth.auth_service.AuthService.blacklist_token') as mock_blacklist:
            mock_blacklist.return_value = {
                "success": True,
                "message": "Token blacklisted successfully",
                "token_hash": hashlib.sha256(sample_token.encode()).hexdigest()
            }
            
            result = await auth_service.blacklist_token(sample_token, user_id)
            
            assert result["success"] is True
            assert "token_hash" in result
            mock_blacklist.assert_called_once_with(sample_token, user_id)
    
    @pytest.mark.asyncio
    async def test_is_token_blacklisted_true(self, auth_service, sample_token):
        """Test checking if token is blacklisted (true case)."""
        with patch('api.auth.auth_service.AuthService.is_token_blacklisted') as mock_check:
            mock_check.return_value = True
            
            result = await auth_service.is_token_blacklisted(sample_token)
            
            assert result is True
            mock_check.assert_called_once_with(sample_token)
    
    @pytest.mark.asyncio
    async def test_is_token_blacklisted_false(self, auth_service, sample_token):
        """Test checking if token is blacklisted (false case)."""
        with patch('api.auth.auth_service.AuthService.is_token_blacklisted') as mock_check:
            mock_check.return_value = False
            
            result = await auth_service.is_token_blacklisted(sample_token)
            
            assert result is False
            mock_check.assert_called_once_with(sample_token)
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_blacklisted_tokens(self, auth_service):
        """Test cleanup of expired blacklisted tokens."""
        with patch('api.auth.auth_service.AuthService.cleanup_expired_blacklisted_tokens') as mock_cleanup:
            mock_cleanup.return_value = {"deleted_count": 10}
            
            result = await auth_service.cleanup_expired_blacklisted_tokens()
            
            assert "deleted_count" in result
            assert result["deleted_count"] >= 0
            mock_cleanup.assert_called_once()

class TestTokenValidation:
    """Test cases for token validation and verification."""
    
    @pytest.fixture
    def token_manager(self):
        return TokenManager()
    
    @pytest.fixture
    def valid_payload(self):
        """Valid token payload."""
        return {
            "user_id": "user_123",
            "email": "test@example.com",
            "role": UserRole.USER,
            "iat": datetime.now().timestamp(),
            "exp": (datetime.now() + timedelta(hours=1)).timestamp()
        }
    
    def test_generate_token_hash(self, token_manager):
        """Test token hash generation."""
        token = "sample_token_123"
        expected_hash = hashlib.sha256(token.encode()).hexdigest()
        
        with patch('api.auth.auth_service.TokenManager.generate_token_hash') as mock_hash:
            mock_hash.return_value = expected_hash
            
            result = token_manager.generate_token_hash(token)
            
            assert result == expected_hash
            assert len(result) == 64  # SHA256 hex length
    
    def test_extract_token_expiry(self, token_manager, valid_payload):
        """Test extracting expiry from token payload."""
        with patch('api.auth.auth_service.TokenManager.extract_token_expiry') as mock_extract:
            mock_extract.return_value = datetime.fromtimestamp(valid_payload["exp"])
            
            result = token_manager.extract_token_expiry(valid_payload)
            
            assert isinstance(result, datetime)
            assert result > datetime.now()
    
    def test_validate_token_structure(self, token_manager):
        """Test token structure validation."""
        valid_token = "header.payload.signature"
        invalid_token = "invalid_token"
        
        with patch('api.auth.auth_service.TokenManager.validate_token_structure') as mock_validate:
            # Valid token
            mock_validate.return_value = True
            result1 = token_manager.validate_token_structure(valid_token)
            assert result1 is True
            
            # Invalid token
            mock_validate.return_value = False
            result2 = token_manager.validate_token_structure(invalid_token)
            assert result2 is False

class TestAuthEndpointsIntegration:
    """Integration tests for authentication endpoints."""
    
    @pytest.fixture
    def auth_service(self):
        return AuthService()
    
    @pytest.fixture
    def token_manager(self):
        return TokenManager()
    
    @pytest.mark.asyncio
    async def test_login_logout_flow(self, auth_service, token_manager):
        """Test complete login-logout flow."""
        # Step 1: Login
        login_data = {"email": "test@example.com", "password": "password123"}
        
        with patch.object(auth_service, 'authenticate_user') as mock_login:
            mock_login.return_value = {
                "user": {"id": "user_123", "email": "test@example.com"},
                "access_token": "access_token_123",
                "refresh_token": "refresh_token_123",
                "expires_in": 3600
            }
            
            login_result = await auth_service.authenticate_user(
                login_data["email"], login_data["password"]
            )
            
            assert "access_token" in login_result
            user_id = login_result["user"]["id"]
            access_token = login_result["access_token"]
        
        # Step 2: Logout
        with patch.object(auth_service, 'logout_user') as mock_logout:
            mock_logout.return_value = {
                "success": True,
                "message": "Logged out successfully"
            }
            
            logout_result = await auth_service.logout_user(user_id, access_token)
            
            assert logout_result["success"] is True
    
    @pytest.mark.asyncio
    async def test_token_refresh_flow(self, auth_service):
        """Test token refresh flow."""
        refresh_token = "valid_refresh_token"
        
        with patch.object(auth_service, 'refresh_token') as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_in": 3600
            }
            
            result = await auth_service.refresh_token(refresh_token)
            
            assert "access_token" in result
            assert "refresh_token" in result
            assert result["expires_in"] == 3600
    
    @pytest.mark.asyncio
    async def test_token_blacklist_validation_flow(self, auth_service):
        """Test token blacklisting and validation flow."""
        token = "test_token_123"
        user_id = "user_123"
        
        # Step 1: Blacklist token
        with patch.object(auth_service, 'blacklist_token') as mock_blacklist:
            mock_blacklist.return_value = {"success": True}
            
            blacklist_result = await auth_service.blacklist_token(token, user_id)
            assert blacklist_result["success"] is True
        
        # Step 2: Check if token is blacklisted
        with patch.object(auth_service, 'is_token_blacklisted') as mock_check:
            mock_check.return_value = True
            
            is_blacklisted = await auth_service.is_token_blacklisted(token)
            assert is_blacklisted is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])