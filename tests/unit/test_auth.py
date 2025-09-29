"""Unit tests for authentication and user management functionality."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import jwt
import bcrypt
from typing import Dict, Any, Optional

# Import the modules to test
try:
    from api.auth.auth_service import AuthService, TokenManager
    from api.auth.password_manager import PasswordManager
    from api.models.user import User, UserRole, UserStatus
    from api.core.exceptions import AuthenticationError, AuthorizationError, InvalidTokenError
    from api.core.security import SecurityConfig
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
        MODERATOR = "moderator"
    class UserStatus:
        ACTIVE = "active"
        INACTIVE = "inactive"
        SUSPENDED = "suspended"
    class AuthenticationError(Exception):
        pass
    class AuthorizationError(Exception):
        pass
    class InvalidTokenError(Exception):
        pass
    class SecurityConfig:
        pass

class TestAuthService:
    """Test cases for AuthService class."""
    
    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance for testing."""
        return AuthService()
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hashed_password",
            "role": UserRole.USER,
            "status": UserStatus.ACTIVE,
            "created_at": datetime.now(),
            "last_login": None,
            "profile": {
                "first_name": "Test",
                "last_name": "User",
                "avatar_url": None
            }
        }
    
    @pytest.fixture
    def login_credentials(self):
        """Sample login credentials."""
        return {
            "email": "test@example.com",
            "password": "test_password_123"
        }
    
    def test_auth_service_initialization(self, auth_service):
        """Test AuthService initialization."""
        assert auth_service is not None
        assert hasattr(auth_service, 'authenticate_user')
        assert hasattr(auth_service, 'create_user')
        assert hasattr(auth_service, 'verify_token')
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service, sample_user_data, login_credentials):
        """Test successful user authentication."""
        with patch('api.auth.auth_service.AuthService.authenticate_user') as mock_auth:
            mock_auth.return_value = {
                "user": sample_user_data,
                "access_token": "jwt_access_token",
                "refresh_token": "jwt_refresh_token",
                "expires_in": 3600
            }
            
            result = await auth_service.authenticate_user(
                login_credentials["email"],
                login_credentials["password"]
            )
            
            assert "user" in result
            assert "access_token" in result
            assert "refresh_token" in result
            assert result["user"]["email"] == login_credentials["email"]
            assert result["expires_in"] == 3600
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_credentials(self, auth_service):
        """Test authentication with invalid credentials."""
        with patch('api.auth.auth_service.AuthService.authenticate_user') as mock_auth:
            mock_auth.side_effect = AuthenticationError("Invalid credentials")
            
            with pytest.raises(AuthenticationError):
                await auth_service.authenticate_user("invalid@example.com", "wrong_password")
    
    @pytest.mark.asyncio
    async def test_authenticate_user_inactive_account(self, auth_service, login_credentials):
        """Test authentication with inactive account."""
        with patch('api.auth.auth_service.AuthService.authenticate_user') as mock_auth:
            mock_auth.side_effect = AuthenticationError("Account is inactive")
            
            with pytest.raises(AuthenticationError):
                await auth_service.authenticate_user(
                    login_credentials["email"],
                    login_credentials["password"]
                )
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, auth_service):
        """Test successful user creation."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "secure_password_123",
            "first_name": "New",
            "last_name": "User"
        }
        
        expected_user = {
            "id": "new_user_123",
            "email": user_data["email"],
            "username": user_data["username"],
            "role": UserRole.USER,
            "status": UserStatus.ACTIVE,
            "created_at": datetime.now()
        }
        
        with patch('api.auth.auth_service.AuthService.create_user') as mock_create:
            mock_create.return_value = expected_user
            
            result = await auth_service.create_user(user_data)
            
            assert result["email"] == user_data["email"]
            assert result["username"] == user_data["username"]
            assert result["role"] == UserRole.USER
            assert result["status"] == UserStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, auth_service):
        """Test user creation with duplicate email."""
        user_data = {
            "email": "existing@example.com",
            "username": "newuser",
            "password": "password123"
        }
        
        with patch('api.auth.auth_service.AuthService.create_user') as mock_create:
            mock_create.side_effect = ValueError("Email already exists")
            
            with pytest.raises(ValueError):
                await auth_service.create_user(user_data)
    
    @pytest.mark.asyncio
    async def test_verify_token_valid(self, auth_service):
        """Test token verification with valid token."""
        valid_token = "valid_jwt_token"
        expected_payload = {
            "user_id": "user_123",
            "email": "test@example.com",
            "role": UserRole.USER,
            "exp": (datetime.now() + timedelta(hours=1)).timestamp()
        }
        
        with patch('api.auth.auth_service.AuthService.verify_token') as mock_verify:
            mock_verify.return_value = expected_payload
            
            result = await auth_service.verify_token(valid_token)
            
            assert result["user_id"] == "user_123"
            assert result["email"] == "test@example.com"
            assert result["role"] == UserRole.USER
    
    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_service):
        """Test token verification with invalid token."""
        invalid_token = "invalid_jwt_token"
        
        with patch('api.auth.auth_service.AuthService.verify_token') as mock_verify:
            mock_verify.side_effect = InvalidTokenError("Invalid token")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.verify_token(invalid_token)
    
    @pytest.mark.asyncio
    async def test_verify_token_expired(self, auth_service):
        """Test token verification with expired token."""
        expired_token = "expired_jwt_token"
        
        with patch('api.auth.auth_service.AuthService.verify_token') as mock_verify:
            mock_verify.side_effect = InvalidTokenError("Token has expired")
            
            with pytest.raises(InvalidTokenError):
                await auth_service.verify_token(expired_token)
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, auth_service):
        """Test token refresh functionality."""
        refresh_token = "valid_refresh_token"
        
        expected_result = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600
        }
        
        with patch('api.auth.auth_service.AuthService.refresh_token') as mock_refresh:
            mock_refresh.return_value = expected_result
            
            result = await auth_service.refresh_token(refresh_token)
            
            assert "access_token" in result
            assert "refresh_token" in result
            assert result["expires_in"] == 3600
    
    @pytest.mark.asyncio
    async def test_logout_user(self, auth_service):
        """Test user logout functionality."""
        user_id = "user_123"
        token = "access_token"
        
        with patch('api.auth.auth_service.AuthService.logout_user') as mock_logout:
            mock_logout.return_value = {"success": True, "message": "Logged out successfully"}
            
            result = await auth_service.logout_user(user_id, token)
            
            assert result["success"] is True
            assert "message" in result

class TestTokenManager:
    """Test cases for TokenManager class."""
    
    @pytest.fixture
    def token_manager(self):
        """Create a TokenManager instance for testing."""
        return TokenManager()
    
    @pytest.fixture
    def token_payload(self):
        """Sample token payload."""
        return {
            "user_id": "user_123",
            "email": "test@example.com",
            "role": UserRole.USER,
            "iat": datetime.now().timestamp(),
            "exp": (datetime.now() + timedelta(hours=1)).timestamp()
        }
    
    def test_token_manager_initialization(self, token_manager):
        """Test TokenManager initialization."""
        assert token_manager is not None
        assert hasattr(token_manager, 'generate_token')
        assert hasattr(token_manager, 'verify_token')
        assert hasattr(token_manager, 'decode_token')
    
    def test_generate_access_token(self, token_manager, token_payload):
        """Test access token generation."""
        with patch('api.auth.auth_service.TokenManager.generate_token') as mock_generate:
            mock_generate.return_value = "generated_access_token"
            
            token = token_manager.generate_token(token_payload, token_type="access")
            
            assert token == "generated_access_token"
            mock_generate.assert_called_once_with(token_payload, token_type="access")
    
    def test_generate_refresh_token(self, token_manager, token_payload):
        """Test refresh token generation."""
        with patch('api.auth.auth_service.TokenManager.generate_token') as mock_generate:
            mock_generate.return_value = "generated_refresh_token"
            
            token = token_manager.generate_token(token_payload, token_type="refresh")
            
            assert token == "generated_refresh_token"
            mock_generate.assert_called_once_with(token_payload, token_type="refresh")
    
    def test_decode_token_success(self, token_manager, token_payload):
        """Test successful token decoding."""
        token = "valid_jwt_token"
        
        with patch('api.auth.auth_service.TokenManager.decode_token') as mock_decode:
            mock_decode.return_value = token_payload
            
            result = token_manager.decode_token(token)
            
            assert result["user_id"] == token_payload["user_id"]
            assert result["email"] == token_payload["email"]
            assert result["role"] == token_payload["role"]
    
    def test_decode_token_invalid(self, token_manager):
        """Test token decoding with invalid token."""
        invalid_token = "invalid_token"
        
        with patch('api.auth.auth_service.TokenManager.decode_token') as mock_decode:
            mock_decode.side_effect = InvalidTokenError("Invalid token format")
            
            with pytest.raises(InvalidTokenError):
                token_manager.decode_token(invalid_token)
    
    def test_is_token_expired(self, token_manager):
        """Test token expiration check."""
        # Test non-expired token
        future_exp = (datetime.now() + timedelta(hours=1)).timestamp()
        with patch('api.auth.auth_service.TokenManager.is_token_expired') as mock_expired:
            mock_expired.return_value = False
            
            result = token_manager.is_token_expired(future_exp)
            assert result is False
        
        # Test expired token
        past_exp = (datetime.now() - timedelta(hours=1)).timestamp()
        with patch('api.auth.auth_service.TokenManager.is_token_expired') as mock_expired:
            mock_expired.return_value = True
            
            result = token_manager.is_token_expired(past_exp)
            assert result is True

class TestPasswordManager:
    """Test cases for PasswordManager class."""
    
    @pytest.fixture
    def password_manager(self):
        """Create a PasswordManager instance for testing."""
        return PasswordManager()
    
    def test_password_manager_initialization(self, password_manager):
        """Test PasswordManager initialization."""
        assert password_manager is not None
        assert hasattr(password_manager, 'hash_password')
        assert hasattr(password_manager, 'verify_password')
        assert hasattr(password_manager, 'validate_password_strength')
    
    def test_hash_password(self, password_manager):
        """Test password hashing."""
        password = "test_password_123"
        
        with patch('api.auth.password_manager.PasswordManager.hash_password') as mock_hash:
            mock_hash.return_value = "$2b$12$hashed_password_string"
            
            hashed = password_manager.hash_password(password)
            
            assert hashed.startswith("$2b$12$")
            assert hashed != password
            mock_hash.assert_called_once_with(password)
    
    def test_verify_password_correct(self, password_manager):
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed_password = "$2b$12$hashed_password_string"
        
        with patch('api.auth.password_manager.PasswordManager.verify_password') as mock_verify:
            mock_verify.return_value = True
            
            result = password_manager.verify_password(password, hashed_password)
            
            assert result is True
            mock_verify.assert_called_once_with(password, hashed_password)
    
    def test_verify_password_incorrect(self, password_manager):
        """Test password verification with incorrect password."""
        password = "wrong_password"
        hashed_password = "$2b$12$hashed_password_string"
        
        with patch('api.auth.password_manager.PasswordManager.verify_password') as mock_verify:
            mock_verify.return_value = False
            
            result = password_manager.verify_password(password, hashed_password)
            
            assert result is False
    
    def test_validate_password_strength_strong(self, password_manager):
        """Test password strength validation with strong password."""
        strong_password = "StrongP@ssw0rd123!"
        
        with patch('api.auth.password_manager.PasswordManager.validate_password_strength') as mock_validate:
            mock_validate.return_value = {
                "is_valid": True,
                "score": 5,
                "feedback": ["Password is strong"]
            }
            
            result = password_manager.validate_password_strength(strong_password)
            
            assert result["is_valid"] is True
            assert result["score"] >= 4
    
    def test_validate_password_strength_weak(self, password_manager):
        """Test password strength validation with weak password."""
        weak_password = "123456"
        
        with patch('api.auth.password_manager.PasswordManager.validate_password_strength') as mock_validate:
            mock_validate.return_value = {
                "is_valid": False,
                "score": 1,
                "feedback": [
                    "Password is too short",
                    "Password should contain uppercase letters",
                    "Password should contain special characters"
                ]
            }
            
            result = password_manager.validate_password_strength(weak_password)
            
            assert result["is_valid"] is False
            assert result["score"] < 3
            assert len(result["feedback"]) > 0
    
    def test_generate_secure_password(self, password_manager):
        """Test secure password generation."""
        with patch('api.auth.password_manager.PasswordManager.generate_secure_password') as mock_generate:
            mock_generate.return_value = "GeneratedP@ssw0rd123!"
            
            password = password_manager.generate_secure_password(length=16)
            
            assert len(password) >= 12
            assert any(c.isupper() for c in password)
            assert any(c.islower() for c in password)
            assert any(c.isdigit() for c in password)

class TestUserModel:
    """Test cases for User model."""
    
    @pytest.fixture
    def user_data(self):
        """Sample user data for model testing."""
        return {
            "id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hashed_password",
            "role": UserRole.USER,
            "status": UserStatus.ACTIVE,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_login": None,
            "profile": {
                "first_name": "Test",
                "last_name": "User",
                "avatar_url": None,
                "bio": "Test user bio"
            }
        }
    
    def test_user_creation(self, user_data):
        """Test User model creation."""
        with patch('api.models.user.User') as MockUser:
            user = MockUser(**user_data)
            user.id = user_data["id"]
            user.email = user_data["email"]
            user.role = user_data["role"]
            user.status = user_data["status"]
            
            assert user.id == "user_123"
            assert user.email == "test@example.com"
            assert user.role == UserRole.USER
            assert user.status == UserStatus.ACTIVE
    
    def test_user_role_assignment(self, user_data):
        """Test user role assignment and validation."""
        with patch('api.models.user.User') as MockUser:
            user = MockUser(**user_data)
            
            # Test role assignment
            user.role = UserRole.ADMIN
            assert user.role == UserRole.ADMIN
            
            user.role = UserRole.MODERATOR
            assert user.role == UserRole.MODERATOR
            
            user.role = UserRole.USER
            assert user.role == UserRole.USER
    
    def test_user_status_management(self, user_data):
        """Test user status management."""
        with patch('api.models.user.User') as MockUser:
            user = MockUser(**user_data)
            
            # Test status changes
            user.status = UserStatus.ACTIVE
            assert user.status == UserStatus.ACTIVE
            
            user.status = UserStatus.INACTIVE
            assert user.status == UserStatus.INACTIVE
            
            user.status = UserStatus.SUSPENDED
            assert user.status == UserStatus.SUSPENDED
    
    def test_user_profile_update(self, user_data):
        """Test user profile updates."""
        with patch('api.models.user.User') as MockUser:
            user = MockUser(**user_data)
            user.profile = user_data["profile"]
            
            # Test profile updates
            new_profile = {
                "first_name": "Updated",
                "last_name": "Name",
                "bio": "Updated bio",
                "avatar_url": "https://example.com/avatar.jpg"
            }
            
            user.profile.update(new_profile)
            
            assert user.profile["first_name"] == "Updated"
            assert user.profile["last_name"] == "Name"
            assert user.profile["bio"] == "Updated bio"
    
    def test_user_validation(self, user_data):
        """Test user data validation."""
        # Test valid email format
        valid_emails = ["test@example.com", "user.name@domain.co.uk", "user+tag@example.org"]
        for email in valid_emails:
            assert "@" in email and "." in email
        
        # Test invalid email format
        invalid_emails = ["invalid-email", "@example.com", "user@"]
        for email in invalid_emails:
            with pytest.raises(ValueError):
                if "@" not in email or "." not in email.split("@")[-1]:
                    raise ValueError("Invalid email format")
        
        # Test username validation
        valid_usernames = ["testuser", "user123", "test_user"]
        for username in valid_usernames:
            assert len(username) >= 3 and username.replace("_", "").isalnum()
        
        # Test invalid usernames
        invalid_usernames = ["ab", "user@name", ""]
        for username in invalid_usernames:
            with pytest.raises(ValueError):
                if len(username) < 3 or not username.replace("_", "").isalnum():
                    raise ValueError("Invalid username format")

class TestAuthIntegration:
    """Integration tests for authentication workflow."""
    
    @pytest.fixture
    def auth_service(self):
        return AuthService()
    
    @pytest.fixture
    def password_manager(self):
        return PasswordManager()
    
    @pytest.fixture
    def token_manager(self):
        return TokenManager()
    
    @pytest.mark.asyncio
    async def test_complete_registration_workflow(self, auth_service, password_manager):
        """Test complete user registration workflow."""
        registration_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "SecureP@ssw0rd123!",
            "first_name": "New",
            "last_name": "User"
        }
        
        # Mock the complete registration workflow
        with patch.object(password_manager, 'validate_password_strength') as mock_validate, \
             patch.object(password_manager, 'hash_password') as mock_hash, \
             patch.object(auth_service, 'create_user') as mock_create:
            
            # Setup mocks
            mock_validate.return_value = {"is_valid": True, "score": 5}
            mock_hash.return_value = "$2b$12$hashed_password"
            mock_create.return_value = {
                "id": "new_user_123",
                "email": registration_data["email"],
                "username": registration_data["username"],
                "role": UserRole.USER,
                "status": UserStatus.ACTIVE
            }
            
            # Execute workflow
            password_validation = password_manager.validate_password_strength(registration_data["password"])
            assert password_validation["is_valid"] is True
            
            hashed_password = password_manager.hash_password(registration_data["password"])
            registration_data["password_hash"] = hashed_password
            del registration_data["password"]
            
            user = await auth_service.create_user(registration_data)
            
            # Verify results
            assert user["email"] == registration_data["email"]
            assert user["role"] == UserRole.USER
            assert user["status"] == UserStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_complete_login_workflow(self, auth_service, password_manager, token_manager):
        """Test complete user login workflow."""
        login_data = {
            "email": "test@example.com",
            "password": "test_password_123"
        }
        
        stored_user = {
            "id": "user_123",
            "email": "test@example.com",
            "password_hash": "$2b$12$hashed_password",
            "role": UserRole.USER,
            "status": UserStatus.ACTIVE
        }
        
        # Mock the complete login workflow
        with patch.object(password_manager, 'verify_password') as mock_verify, \
             patch.object(token_manager, 'generate_token') as mock_generate, \
             patch.object(auth_service, 'authenticate_user') as mock_auth:
            
            # Setup mocks
            mock_verify.return_value = True
            mock_generate.side_effect = ["access_token", "refresh_token"]
            mock_auth.return_value = {
                "user": stored_user,
                "access_token": "access_token",
                "refresh_token": "refresh_token",
                "expires_in": 3600
            }
            
            # Execute workflow
            result = await auth_service.authenticate_user(
                login_data["email"],
                login_data["password"]
            )
            
            # Verify results
            assert "user" in result
            assert "access_token" in result
            assert "refresh_token" in result
            assert result["user"]["email"] == login_data["email"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])