import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from api.middleware.auth import (
    SupabaseAuthMiddleware, get_current_user, require_authenticated_user
)
from api.models.database_models import User
from api.core.config import settings
from supabase import Client

# Mock data
SAMPLE_USER_DATA = {
    "auth_id": "auth-123",
    "email": "test@example.com",
    "display_name": "Test User",
    "avatar_url": "https://example.com/avatar.jpg",
    "is_active": True,
    "last_login": datetime.utcnow(),
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}

VALID_JWT_PAYLOAD = {
    "sub": "user-123",
    "email": "test@example.com",
    "aud": "authenticated",
    "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    "iat": int(datetime.utcnow().timestamp()),
    "iss": "https://your-project.supabase.co/auth/v1"
}

class TestSupabaseAuthMiddleware:
    """Test SupabaseAuthMiddleware class functionality."""
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client."""
        client = Mock(spec=Client)
        return client
    
    @pytest.fixture
    def auth_middleware(self, mock_supabase_client):
        """Create SupabaseAuthMiddleware instance with mocked dependencies."""
        with patch('api.middleware.auth.get_supabase_client', return_value=mock_supabase_client):
            middleware = SupabaseAuthMiddleware()
            return middleware
    
    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request object."""
        request = Mock()
        request.headers = {"authorization": "Bearer valid_token"}
        request.url.path = "/api/test"
        request.method = "GET"
        return request
    
    @pytest.fixture
    def mock_call_next(self):
        """Mock call_next function."""
        async def call_next(request):
            response = Mock()
            response.status_code = 200
            return response
        return call_next
    
    @pytest.mark.asyncio
    async def test_middleware_initialization(self, auth_middleware):
        """Test middleware initialization."""
        assert auth_middleware is not None
        assert hasattr(auth_middleware, 'supabase')
    
    @pytest.mark.asyncio
    async def test_middleware_public_endpoint_bypass(self, auth_middleware, mock_call_next):
        """Test that public endpoints bypass authentication."""
        # Mock request to public endpoint
        request = Mock()
        request.url.path = "/docs"
        request.method = "GET"
        
        # Should bypass authentication
        response = await auth_middleware(request, mock_call_next)
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_middleware_health_endpoint_bypass(self, auth_middleware, mock_call_next):
        """Test that health endpoints bypass authentication."""
        request = Mock()
        request.url.path = "/health"
        request.method = "GET"
        
        response = await auth_middleware(request, mock_call_next)
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_middleware_missing_authorization_header(self, auth_middleware, mock_call_next):
        """Test middleware with missing authorization header."""
        request = Mock()
        request.headers = {}  # No authorization header
        request.url.path = "/api/protected"
        request.method = "GET"
        
        with pytest.raises(HTTPException) as exc_info:
            await auth_middleware(request, mock_call_next)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authorization header missing" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_middleware_invalid_authorization_format(self, auth_middleware, mock_call_next):
        """Test middleware with invalid authorization header format."""
        request = Mock()
        request.headers = {"authorization": "InvalidFormat token"}
        request.url.path = "/api/protected"
        request.method = "GET"
        
        with pytest.raises(HTTPException) as exc_info:
            await auth_middleware(request, mock_call_next)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid authorization header format" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('api.middleware.auth.verify_token')
    async def test_middleware_valid_token(self, mock_verify_token, auth_middleware, mock_request, mock_call_next):
        """Test middleware with valid token."""
        # Mock successful token verification
        mock_user = Mock(spec=User)
        mock_user.id = "user-123"
        mock_user.is_active = True
        mock_verify_token.return_value = mock_user
        
        response = await auth_middleware(mock_request, mock_call_next)
        
        assert response.status_code == 200
        mock_verify_token.assert_called_once_with("valid_token")
    
    @pytest.mark.asyncio
    @patch('api.middleware.auth.verify_token')
    async def test_middleware_invalid_token(self, mock_verify_token, auth_middleware, mock_request, mock_call_next):
        """Test middleware with invalid token."""
        # Mock token verification failure
        mock_verify_token.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await auth_middleware(mock_request, mock_call_next)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('api.middleware.auth.verify_token')
    async def test_middleware_inactive_user(self, mock_verify_token, auth_middleware, mock_request, mock_call_next):
        """Test middleware with inactive user."""
        # Mock user that is inactive
        mock_user = Mock(spec=User)
        mock_user.id = "user-123"
        mock_user.is_active = False
        mock_verify_token.return_value = mock_user
        
        with pytest.raises(HTTPException) as exc_info:
            await auth_middleware(mock_request, mock_call_next)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "User account is inactive" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_middleware_exception_handling(self, auth_middleware, mock_request, mock_call_next):
        """Test middleware exception handling."""
        # Mock an unexpected exception
        with patch('api.middleware.auth.verify_token', side_effect=Exception("Unexpected error")):
            with pytest.raises(HTTPException) as exc_info:
                await auth_middleware(mock_request, mock_call_next)
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Authentication error" in str(exc_info.value.detail)

class TestGetCurrentUser:
    """Test get_current_user dependency function."""
    
    @pytest.fixture
    def mock_jwt_bearer(self):
        """Mock JWTBearer dependency."""
        bearer = Mock(spec=JWTBearer)
        return bearer
    
    @pytest.mark.asyncio
    @patch('api.middleware.auth.verify_token')
    async def test_get_current_user_success(self, mock_verify_token):
        """Test successful user retrieval."""
        # Mock successful token verification
        mock_user = Mock(spec=User)
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_verify_token.return_value = mock_user
        
        token = "valid_token"
        user = await get_current_user(token)
        
        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.is_active is True
        mock_verify_token.assert_called_once_with(token)
    
    @pytest.mark.asyncio
    @patch('api.middleware.auth.verify_token')
    async def test_get_current_user_invalid_token(self, mock_verify_token):
        """Test user retrieval with invalid token."""
        # Mock token verification failure
        mock_verify_token.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid_token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('api.middleware.auth.verify_token')
    async def test_get_current_user_none_returned(self, mock_verify_token):
        """Test user retrieval when None is returned."""
        # Mock token verification returning None
        mock_verify_token.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "User not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_success(self):
        """Test get_current_active_user with active user."""
        # Mock active user
        mock_user = Mock(spec=User)
        mock_user.id = "user-123"
        mock_user.is_active = True
        
        user = await get_current_active_user(mock_user)
        
        assert user.id == "user-123"
        assert user.is_active is True
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self):
        """Test get_current_active_user with inactive user."""
        # Mock inactive user
        mock_user = Mock(spec=User)
        mock_user.id = "user-123"
        mock_user.is_active = False
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(mock_user)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Inactive user" in str(exc_info.value.detail)

class TestVerifyToken:
    """Test verify_token function."""
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client."""
        client = Mock(spec=Client)
        return client
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock()
        return session
    
    @patch('api.middleware.auth.get_supabase_client')
    @patch('api.middleware.auth.get_db_session')
    @patch('api.middleware.auth.jwt.decode')
    async def test_verify_token_success(self, mock_jwt_decode, mock_get_db_session, mock_get_supabase_client):
        """Test successful token verification."""
        # Mock JWT decode
        mock_jwt_decode.return_value = VALID_JWT_PAYLOAD
        
        # Mock Supabase client
        mock_supabase = Mock()
        mock_supabase.auth.get_user.return_value.user.id = "user-123"
        mock_get_supabase_client.return_value = mock_supabase
        
        # Mock database session and user query
        mock_session = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        mock_get_db_session.return_value.__enter__.return_value = mock_session
        
        token = "valid_jwt_token"
        user = await verify_token(token)
        
        assert user.id == "user-123"
        assert user.email == "test@example.com"
        mock_jwt_decode.assert_called_once()
        mock_supabase.auth.get_user.assert_called_once_with(token)
    
    @patch('api.middleware.auth.jwt.decode')
    async def test_verify_token_invalid_jwt(self, mock_jwt_decode):
        """Test token verification with invalid JWT."""
        # Mock JWT decode failure
        mock_jwt_decode.side_effect = jwt.InvalidTokenError("Invalid token")
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_token("invalid_token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in str(exc_info.value.detail)
    
    @patch('api.middleware.auth.jwt.decode')
    async def test_verify_token_expired_jwt(self, mock_jwt_decode):
        """Test token verification with expired JWT."""
        # Mock JWT decode with expired token
        mock_jwt_decode.side_effect = jwt.ExpiredSignatureError("Token expired")
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_token("expired_token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token expired" in str(exc_info.value.detail)
    
    @patch('api.middleware.auth.get_supabase_client')
    @patch('api.middleware.auth.jwt.decode')
    async def test_verify_token_supabase_auth_failure(self, mock_jwt_decode, mock_get_supabase_client):
        """Test token verification with Supabase auth failure."""
        # Mock JWT decode success
        mock_jwt_decode.return_value = VALID_JWT_PAYLOAD
        
        # Mock Supabase client auth failure
        mock_supabase = Mock()
        mock_supabase.auth.get_user.side_effect = Exception("Supabase auth error")
        mock_get_supabase_client.return_value = mock_supabase
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_token("token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token validation failed" in str(exc_info.value.detail)
    
    @patch('api.middleware.auth.get_supabase_client')
    @patch('api.middleware.auth.get_db_session')
    @patch('api.middleware.auth.jwt.decode')
    async def test_verify_token_user_not_found_in_db(self, mock_jwt_decode, mock_get_db_session, mock_get_supabase_client):
        """Test token verification when user not found in database."""
        # Mock JWT decode
        mock_jwt_decode.return_value = VALID_JWT_PAYLOAD
        
        # Mock Supabase client
        mock_supabase = Mock()
        mock_supabase.auth.get_user.return_value.user.id = "user-123"
        mock_get_supabase_client.return_value = mock_supabase
        
        # Mock database session with no user found
        mock_session = Mock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_get_db_session.return_value.__enter__.return_value = mock_session
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_token("token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "User not found" in str(exc_info.value.detail)
    
    @patch('api.middleware.auth.get_supabase_client')
    @patch('api.middleware.auth.get_db_session')
    @patch('api.middleware.auth.jwt.decode')
    async def test_verify_token_inactive_user(self, mock_jwt_decode, mock_get_db_session, mock_get_supabase_client):
        """Test token verification with inactive user."""
        # Mock JWT decode
        mock_jwt_decode.return_value = VALID_JWT_PAYLOAD
        
        # Mock Supabase client
        mock_supabase = Mock()
        mock_supabase.auth.get_user.return_value.user.id = "user-123"
        mock_get_supabase_client.return_value = mock_supabase
        
        # Mock database session with inactive user
        mock_session = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = "user-123"
        mock_user.is_active = False
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        mock_get_db_session.return_value.__enter__.return_value = mock_session
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_token("token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "User account is inactive" in str(exc_info.value.detail)
    
    @patch('api.middleware.auth.jwt.decode')
    async def test_verify_token_missing_user_id(self, mock_jwt_decode):
        """Test token verification with missing user ID in payload."""
        # Mock JWT decode with missing sub claim
        invalid_payload = VALID_JWT_PAYLOAD.copy()
        del invalid_payload["sub"]
        mock_jwt_decode.return_value = invalid_payload
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_token("token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token payload" in str(exc_info.value.detail)
    
    @patch('api.middleware.auth.jwt.decode')
    async def test_verify_token_wrong_audience(self, mock_jwt_decode):
        """Test token verification with wrong audience."""
        # Mock JWT decode with wrong audience
        invalid_payload = VALID_JWT_PAYLOAD.copy()
        invalid_payload["aud"] = "wrong_audience"
        mock_jwt_decode.return_value = invalid_payload
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_token("token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token audience" in str(exc_info.value.detail)

class TestJWTBearer:
    """Test JWTBearer class."""
    
    @pytest.fixture
    def jwt_bearer(self):
        """Create JWTBearer instance."""
        return JWTBearer()
    
    @pytest.mark.asyncio
    async def test_jwt_bearer_call_success(self, jwt_bearer):
        """Test JWTBearer __call__ method with valid credentials."""
        # Mock request with valid authorization header
        mock_request = Mock()
        mock_credentials = Mock()
        mock_credentials.scheme = "Bearer"
        mock_credentials.credentials = "valid_token"
        
        with patch.object(HTTPBearer, '__call__', return_value=mock_credentials):
            token = await jwt_bearer(mock_request)
        
        assert token == "valid_token"
    
    @pytest.mark.asyncio
    async def test_jwt_bearer_call_invalid_scheme(self, jwt_bearer):
        """Test JWTBearer __call__ method with invalid scheme."""
        # Mock request with invalid scheme
        mock_request = Mock()
        mock_credentials = Mock()
        mock_credentials.scheme = "Basic"
        mock_credentials.credentials = "token"
        
        with patch.object(HTTPBearer, '__call__', return_value=mock_credentials):
            with pytest.raises(HTTPException) as exc_info:
                await jwt_bearer(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid authentication scheme" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_jwt_bearer_call_no_credentials(self, jwt_bearer):
        """Test JWTBearer __call__ method with no credentials."""
        # Mock request with no credentials
        mock_request = Mock()
        
        with patch.object(HTTPBearer, '__call__', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await jwt_bearer(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authorization credentials required" in str(exc_info.value.detail)

class TestAuthMiddlewareEdgeCases:
    """Test edge cases and error scenarios for auth middleware."""
    
    @pytest.fixture
    def auth_middleware(self):
        """Create AuthMiddleware instance."""
        with patch('api.middleware.auth.get_supabase_client'):
            return AuthMiddleware()
    
    @pytest.mark.asyncio
    async def test_middleware_malformed_jwt(self, auth_middleware):
        """Test middleware with malformed JWT token."""
        request = Mock()
        request.headers = {"authorization": "Bearer malformed.jwt.token"}
        request.url.path = "/api/protected"
        request.method = "GET"
        
        async def call_next(req):
            return Mock(status_code=200)
        
        with patch('api.middleware.auth.verify_token', side_effect=HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token"
        )):
            with pytest.raises(HTTPException) as exc_info:
                await auth_middleware(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Malformed token" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_middleware_database_connection_error(self, auth_middleware):
        """Test middleware with database connection error."""
        request = Mock()
        request.headers = {"authorization": "Bearer valid_token"}
        request.url.path = "/api/protected"
        request.method = "GET"
        
        async def call_next(req):
            return Mock(status_code=200)
        
        with patch('api.middleware.auth.verify_token', side_effect=Exception("Database connection failed")):
            with pytest.raises(HTTPException) as exc_info:
                await auth_middleware(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Authentication error" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_middleware_supabase_service_unavailable(self, auth_middleware):
        """Test middleware when Supabase service is unavailable."""
        request = Mock()
        request.headers = {"authorization": "Bearer valid_token"}
        request.url.path = "/api/protected"
        request.method = "GET"
        
        async def call_next(req):
            return Mock(status_code=200)
        
        with patch('api.middleware.auth.verify_token', side_effect=HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )):
            with pytest.raises(HTTPException) as exc_info:
                await auth_middleware(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Authentication service unavailable" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_middleware_rate_limiting(self, auth_middleware):
        """Test middleware with rate limiting scenario."""
        request = Mock()
        request.headers = {"authorization": "Bearer valid_token"}
        request.url.path = "/api/protected"
        request.method = "GET"
        request.client.host = "192.168.1.1"
        
        async def call_next(req):
            return Mock(status_code=200)
        
        with patch('api.middleware.auth.verify_token', side_effect=HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )):
            with pytest.raises(HTTPException) as exc_info:
                await auth_middleware(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            assert "Rate limit exceeded" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_middleware_token_blacklist(self, auth_middleware):
        """Test middleware with blacklisted token."""
        request = Mock()
        request.headers = {"authorization": "Bearer blacklisted_token"}
        request.url.path = "/api/protected"
        request.method = "GET"
        
        async def call_next(req):
            return Mock(status_code=200)
        
        with patch('api.middleware.auth.verify_token', side_effect=HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )):
            with pytest.raises(HTTPException) as exc_info:
                await auth_middleware(request, call_next)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Token has been revoked" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_middleware_concurrent_requests(self, auth_middleware):
        """Test middleware handling concurrent requests."""
        import asyncio
        
        async def make_request(token_suffix):
            request = Mock()
            request.headers = {"authorization": f"Bearer token_{token_suffix}"}
            request.url.path = "/api/protected"
            request.method = "GET"
            
            async def call_next(req):
                # Simulate some processing time
                await asyncio.sleep(0.01)
                return Mock(status_code=200)
            
            with patch('api.middleware.auth.verify_token') as mock_verify:
                mock_user = Mock(spec=User)
                mock_user.id = f"user-{token_suffix}"
                mock_user.is_active = True
                mock_verify.return_value = mock_user
                
                return await auth_middleware(request, call_next)
        
        # Make multiple concurrent requests
        tasks = [make_request(i) for i in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # All requests should succeed
        assert all(response.status_code == 200 for response in responses)
    
    @pytest.mark.asyncio
    async def test_middleware_memory_usage(self, auth_middleware):
        """Test middleware memory usage with many requests."""
        import gc
        import sys
        
        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Make many requests
        for i in range(100):
            request = Mock()
            request.headers = {"authorization": f"Bearer token_{i}"}
            request.url.path = "/api/protected"
            request.method = "GET"
            
            async def call_next(req):
                return Mock(status_code=200)
            
            with patch('api.middleware.auth.verify_token') as mock_verify:
                mock_user = Mock(spec=User)
                mock_user.id = f"user-{i}"
                mock_user.is_active = True
                mock_verify.return_value = mock_user
                
                try:
                    await auth_middleware(request, call_next)
                except Exception:
                    pass  # Ignore errors for this test
        
        # Check memory usage hasn't grown excessively
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory growth should be reasonable (less than 50% increase)
        memory_growth_ratio = (final_objects - initial_objects) / initial_objects
        assert memory_growth_ratio < 0.5, f"Memory growth too high: {memory_growth_ratio:.2%}"
    
    @pytest.mark.asyncio
    async def test_middleware_request_id_tracking(self, auth_middleware):
        """Test middleware request ID tracking for debugging."""
        request = Mock()
        request.headers = {
            "authorization": "Bearer valid_token",
            "x-request-id": "req-123"
        }
        request.url.path = "/api/protected"
        request.method = "GET"
        
        async def call_next(req):
            # Verify request ID is preserved
            assert hasattr(req, 'headers')
            assert req.headers.get("x-request-id") == "req-123"
            return Mock(status_code=200)
        
        with patch('api.middleware.auth.verify_token') as mock_verify:
            mock_user = Mock(spec=User)
            mock_user.id = "user-123"
            mock_user.is_active = True
            mock_verify.return_value = mock_user
            
            response = await auth_middleware(request, call_next)
            assert response.status_code == 200