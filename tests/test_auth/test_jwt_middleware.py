import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
import jwt
import json
from api.auth.jwt_middleware import (
    get_current_user,
    get_supabase_token_info,
    require_supabase_token_info,
    require_current_user_from_token_info,
    validate_jwt_structure,
    enrich_user_data,
    user_cache,
    clear_user_cache,
    get_cached_user
)
from api.models.database_models import User

# Test data
SAMPLE_JWT_PAYLOAD = {
    "sub": "12345678-1234-1234-1234-123456789012",
    "email": "test@example.com",
    "aud": "authenticated",
    "role": "authenticated",
    "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    "user_metadata": {
        "full_name": "Test User",
        "username": "testuser"
    },
    "app_metadata": {
        "provider": "email",
        "providers": ["email"]
    }
}

SAMPLE_USER_PROFILE = {
    "id": "12345678-1234-1234-1234-123456789012",
    "email": "test@example.com",
    "username": "testuser",
    "full_name": "Test User",
    "avatar_url": "https://example.com/avatar.jpg",
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
}

SAMPLE_USER_SETTINGS = {
    "user_id": "12345678-1234-1234-1234-123456789012",
    "theme_mode": "dark",
    "language": "en",
    "notifications_enabled": True,
    "email_notifications": True
}

class TestJWTValidation:
    """Test JWT validation functions."""
    
    def test_validate_jwt_structure_valid(self):
        """Test JWT structure validation with valid payload."""
        result = validate_jwt_structure(SAMPLE_JWT_PAYLOAD)
        assert result is True
    
    def test_validate_jwt_structure_missing_sub(self):
        """Test JWT structure validation with missing sub."""
        invalid_payload = SAMPLE_JWT_PAYLOAD.copy()
        del invalid_payload["sub"]
        
        with pytest.raises(HTTPException) as exc_info:
            validate_jwt_structure(invalid_payload)
        
        assert exc_info.value.status_code == 401
        assert "Missing required field: sub" in str(exc_info.value.detail)
    
    def test_validate_jwt_structure_missing_email(self):
        """Test JWT structure validation with missing email."""
        invalid_payload = SAMPLE_JWT_PAYLOAD.copy()
        del invalid_payload["email"]
        
        with pytest.raises(HTTPException) as exc_info:
            validate_jwt_structure(invalid_payload)
        
        assert exc_info.value.status_code == 401
        assert "Missing required field: email" in str(exc_info.value.detail)
    
    def test_validate_jwt_structure_expired_token(self):
        """Test JWT structure validation with expired token."""
        expired_payload = SAMPLE_JWT_PAYLOAD.copy()
        expired_payload["exp"] = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        
        with pytest.raises(HTTPException) as exc_info:
            validate_jwt_structure(expired_payload)
        
        assert exc_info.value.status_code == 401
        assert "Token has expired" in str(exc_info.value.detail)
    
    def test_validate_jwt_structure_invalid_audience(self):
        """Test JWT structure validation with invalid audience."""
        invalid_payload = SAMPLE_JWT_PAYLOAD.copy()
        invalid_payload["aud"] = "invalid"
        invalid_payload["exp"] = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())  # Ensure not expired
        
        with pytest.raises(HTTPException) as exc_info:
            validate_jwt_structure(invalid_payload)
        
        assert exc_info.value.status_code == 401
        assert "Invalid audience" in str(exc_info.value.detail)

class TestUserCache:
    """Test user caching functionality."""
    
    def setup_method(self):
        """Clear cache before each test."""
        clear_user_cache()
    
    def test_user_cache_operations(self):
        """Test basic cache operations."""
        user_id = "test-user-id"
        user_data = {"id": user_id, "email": "test@example.com"}
        
        # Test cache miss
        cached_user = get_cached_user(user_id)
        assert cached_user is None
        
        # Test cache set
        user_cache[user_id] = {
            "data": user_data,
            "timestamp": datetime.now(timezone.utc),
            "ttl": 300
        }
        
        # Test cache hit
        cached_user = get_cached_user(user_id)
        assert cached_user is not None
        assert cached_user["id"] == user_id
        assert cached_user["email"] == "test@example.com"
    
    def test_cache_expiration(self):
        """Test cache expiration logic."""
        user_id = "test-user-id"
        user_data = {"id": user_id, "email": "test@example.com"}
        
        # Set cache with expired timestamp
        user_cache[user_id] = {
            "data": user_data,
            "timestamp": datetime.now(timezone.utc) - timedelta(seconds=400),  # Expired
            "ttl": 300
        }
        
        # Should return None for expired cache
        cached_user = get_cached_user(user_id)
        assert cached_user is None
        
        # Cache entry should be removed
        assert user_id not in user_cache
    
    def test_clear_user_cache(self):
        """Test clearing user cache."""
        # Add some cache entries
        user_cache["user1"] = {"data": {"id": "user1"}, "timestamp": datetime.now(timezone.utc), "ttl": 300}
        user_cache["user2"] = {"data": {"id": "user2"}, "timestamp": datetime.now(timezone.utc), "ttl": 300}
        
        assert len(user_cache) == 2
        
        clear_user_cache()
        assert len(user_cache) == 0

class TestEnrichUserData:
    """Test user data enrichment."""
    
    @patch('api.auth.jwt_middleware.supabase')
    @pytest.mark.asyncio
    async def test_enrich_user_data_success(self, mock_supabase):
        """Test successful user data enrichment."""
        # Mock Supabase responses
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = Mock(
            data=SAMPLE_USER_PROFILE
        )
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = Mock(
            data=SAMPLE_USER_SETTINGS
        )
        
        result = await enrich_user_data(SAMPLE_JWT_PAYLOAD)
        
        assert result["id"] == SAMPLE_JWT_PAYLOAD["sub"]
        assert result["email"] == SAMPLE_JWT_PAYLOAD["email"]
        assert result["profile"] == SAMPLE_USER_PROFILE
        assert result["settings"] == SAMPLE_USER_SETTINGS
        assert "jwt_payload" in result
    
    @patch('api.auth.jwt_middleware.supabase')
    @pytest.mark.asyncio
    async def test_enrich_user_data_no_profile(self, mock_supabase):
        """Test user data enrichment when profile doesn't exist."""
        # Create separate mock objects for profile and settings calls
        profile_mock = Mock()
        profile_mock.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = Exception("No profile found")
        
        settings_mock = Mock()
        settings_mock.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = Mock(data=None)
        
        # Configure the main mock to behave differently for different table calls
        def table_side_effect(table_name):
            if table_name == 'users':
                return profile_mock.table.return_value
            elif table_name == 'user_settings':
                return settings_mock.table.return_value
            return Mock()
        
        mock_supabase.table.side_effect = table_side_effect
        
        result = await enrich_user_data(SAMPLE_JWT_PAYLOAD)
        
        assert result["id"] == SAMPLE_JWT_PAYLOAD["sub"]
        assert result["email"] == SAMPLE_JWT_PAYLOAD["email"]
        assert result["profile"] is None
        assert result["settings"] is None
    
    @patch('api.auth.jwt_middleware.supabase')
    @pytest.mark.asyncio
    async def test_enrich_user_data_caching(self, mock_supabase):
        """Test that enriched user data is cached."""
        clear_user_cache()
        
        # Mock Supabase responses
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = Mock(
            data=SAMPLE_USER_PROFILE
        )
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = Mock(
            data=SAMPLE_USER_SETTINGS
        )
        
        user_id = SAMPLE_JWT_PAYLOAD["sub"]
        
        # First call should fetch from Supabase
        result1 = await enrich_user_data(SAMPLE_JWT_PAYLOAD)
        
        # Second call should use cache
        result2 = await enrich_user_data(SAMPLE_JWT_PAYLOAD)
        
        assert result1 == result2
        
        # Verify data was cached
        cached_user = get_cached_user(user_id)
        assert cached_user is not None
        assert cached_user["id"] == user_id

class TestAuthenticationFunctions:
    """Test main authentication functions."""
    
    def setup_method(self):
        """Clear cache before each test."""
        clear_user_cache()
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self):
        """Test get_current_user with no authorization header."""
        request = Mock()
        request.headers = {}
        
        result = await get_current_user(request)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_header(self):
        """Test get_current_user with invalid authorization header."""
        request = Mock()
        request.headers = {"authorization": "InvalidHeader"}
        
        result = await get_current_user(request)
        assert result is None
    
    @patch('api.auth.jwt_middleware.jwt.decode')
    @patch('api.auth.jwt_middleware.enrich_user_data')
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_enrich, mock_jwt_decode):
        """Test get_current_user with valid token."""
        mock_jwt_decode.return_value = SAMPLE_JWT_PAYLOAD
        mock_enrich.return_value = {
            "id": SAMPLE_JWT_PAYLOAD["sub"],
            "email": SAMPLE_JWT_PAYLOAD["email"],
            "profile": SAMPLE_USER_PROFILE,
            "settings": SAMPLE_USER_SETTINGS
        }
        
        request = Mock()
        request.headers = {"authorization": "Bearer valid_token"}
        
        result = await get_current_user(request)
        
        assert result is not None
        assert result["id"] == SAMPLE_JWT_PAYLOAD["sub"]
        assert result["email"] == SAMPLE_JWT_PAYLOAD["email"]
        assert "profile" in result
        assert "settings" in result
    
    @patch('api.auth.jwt_middleware.jwt.decode')
    @pytest.mark.asyncio
    async def test_get_current_user_jwt_decode_error(self, mock_jwt_decode):
        """Test get_current_user with JWT decode error."""
        mock_jwt_decode.side_effect = jwt.InvalidTokenError("Invalid token")
        
        request = Mock()
        request.headers = {"authorization": "Bearer invalid_token"}
        
        result = await get_current_user(request)
        assert result is None
    
    @patch('api.auth.jwt_middleware.get_current_user')
    @pytest.mark.asyncio
    async def test_require_current_user_from_token_info_success(self, mock_get_current_user):
        """Test require_current_user_from_token_info with valid user."""
        # Mock get_current_user to return valid user data
        mock_get_current_user.return_value = {
            "id": SAMPLE_JWT_PAYLOAD["sub"],
            "email": SAMPLE_JWT_PAYLOAD["email"],
            "profile": SAMPLE_USER_PROFILE,
            "settings": SAMPLE_USER_SETTINGS,
            "jwt_payload": SAMPLE_JWT_PAYLOAD
        }
        
        request = Mock()
        request.headers = {"authorization": "Bearer valid_token"}
        
        result = await require_current_user_from_token_info(request)
        
        assert result is not None
        assert result["id"] == SAMPLE_JWT_PAYLOAD["sub"]
        assert result["email"] == SAMPLE_JWT_PAYLOAD["email"]
        assert "profile" in result
        assert "settings" in result
        
        # Verify get_current_user was called with the request
        mock_get_current_user.assert_called_once_with(request)
    
    @pytest.mark.asyncio
    async def test_require_current_user_from_token_info_no_user(self):
        """Test require_current_user_from_token_info with no user."""
        request = Mock()
        request.headers = {}  # No authorization header
        
        with pytest.raises(HTTPException) as exc_info:
            await require_current_user_from_token_info(request)
        
        assert exc_info.value.status_code == 401
        assert "Authentication required" in str(exc_info.value.detail)
    
    @patch('api.auth.jwt_middleware.validate_jwt_structure')
    @patch('api.auth.jwt_middleware.jwt.decode')
    @pytest.mark.asyncio
    async def test_get_supabase_token_info_success(self, mock_jwt_decode, mock_validate):
        """Test get_supabase_token_info with valid token."""
        mock_jwt_decode.return_value = SAMPLE_JWT_PAYLOAD
        mock_validate.return_value = None  # No exception means valid
        
        request = Mock()
        request.headers = {"authorization": "Bearer valid_token"}
        
        result = await get_supabase_token_info(request)
        
        assert result == SAMPLE_JWT_PAYLOAD
    
    @patch('api.auth.jwt_middleware.get_supabase_token_info')
    @pytest.mark.asyncio
    async def test_require_supabase_token_info_success(self, mock_get_token_info):
        """Test require_supabase_token_info with valid token."""
        mock_get_token_info.return_value = SAMPLE_JWT_PAYLOAD
        
        request = Mock()
        
        result = await require_supabase_token_info(request)
        
        assert result == SAMPLE_JWT_PAYLOAD
    
    @patch('api.auth.jwt_middleware.get_supabase_token_info')
    @pytest.mark.asyncio
    async def test_require_supabase_token_info_no_token(self, mock_get_token_info):
        """Test require_supabase_token_info with no token."""
        mock_get_token_info.return_value = None
        
        request = Mock()
        
        with pytest.raises(HTTPException) as exc_info:
            await require_supabase_token_info(request)
        
        assert exc_info.value.status_code == 401
        assert "Valid Supabase token required" in str(exc_info.value.detail)

class TestIntegration:
    """Integration tests for JWT middleware."""
    
    def setup_method(self):
        """Clear cache before each test."""
        clear_user_cache()
    
    @patch('api.auth.jwt_middleware.jwt.decode')
    @patch('api.auth.jwt_middleware.supabase')
    @pytest.mark.asyncio
    async def test_full_authentication_flow(self, mock_supabase, mock_jwt_decode):
        """Test complete authentication flow from token to enriched user data."""
        # Setup mocks
        mock_jwt_decode.return_value = SAMPLE_JWT_PAYLOAD
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = Mock(
            data=SAMPLE_USER_PROFILE
        )
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = Mock(
            data=SAMPLE_USER_SETTINGS
        )
        
        # Create request with valid token
        request = Mock()
        request.headers = {"authorization": "Bearer valid_token"}
        
        # Test the full flow
        user_data = await get_current_user(request)
        
        assert user_data is not None
        assert user_data["id"] == SAMPLE_JWT_PAYLOAD["sub"]
        assert user_data["email"] == SAMPLE_JWT_PAYLOAD["email"]
        assert user_data["profile"] == SAMPLE_USER_PROFILE
        assert user_data["settings"] == SAMPLE_USER_SETTINGS
        
        # Verify caching worked
        cached_user = get_cached_user(SAMPLE_JWT_PAYLOAD["sub"])
        assert cached_user is not None
        assert cached_user["id"] == SAMPLE_JWT_PAYLOAD["sub"]

if __name__ == "__main__":
    pytest.main([__file__])