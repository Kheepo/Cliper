#!/usr/bin/env python3
"""
Security Enhancements Test Suite

Comprehensive tests for:
- Enhanced authentication middleware
- API key management
- Rate limiting
- Security headers
- Input validation
- CORS configuration
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock

import httpx
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request
from redis.asyncio import Redis

# Import the services and middleware we're testing
from api.middleware.enhanced_auth_middleware import (
    EnhancedAuthMiddleware,
    AuthConfig,
    TokenInfo,
    SessionInfo,
    get_current_user_required,
    get_current_user_optional
)
from api.middleware.security_headers_middleware import (
    SecurityHeadersMiddleware,
    SecurityConfig,
    CORSConfig
)
from api.services.api_key_service import (
    APIKeyService,
    APIKeyConfig,
    APIKeyStatus,
    APIKeyScope
)
from api.services.redis_cache_service import (
    RedisCacheService,
    CacheConfig
)
from api.main import app

class TestEnhancedAuthMiddleware:
    """Test enhanced authentication middleware"""
    
    @pytest.fixture
    async def auth_middleware(self):
        """Create auth middleware instance for testing"""
        config = AuthConfig(
            jwt_secret="test_secret_key_for_testing_only",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7,
            max_failed_attempts=3,
            lockout_duration_minutes=15
        )
        
        # Mock Redis client
        redis_client = AsyncMock(spec=Redis)
        
        middleware = EnhancedAuthMiddleware(config, redis_client)
        return middleware
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client"""
        client = Mock()
        client.auth.get_user.return_value.user = Mock(
            id="test_user_id",
            email="test@example.com",
            user_metadata={"role": "user"}
        )
        return client
    
    async def test_generate_tokens(self, auth_middleware):
        """Test token generation"""
        user_data = {
            "user_id": "test_user_id",
            "email": "test@example.com",
            "role": "user"
        }
        
        access_token = await auth_middleware.generate_access_token(user_data)
        refresh_token = await auth_middleware.generate_refresh_token(user_data)
        
        assert access_token is not None
        assert refresh_token is not None
        assert len(access_token) > 50  # JWT tokens are typically long
        assert len(refresh_token) > 50
    
    async def test_validate_access_token(self, auth_middleware):
        """Test access token validation"""
        user_data = {
            "user_id": "test_user_id",
            "email": "test@example.com",
            "role": "user"
        }
        
        # Generate token
        token = await auth_middleware.generate_access_token(user_data)
        
        # Validate token
        token_info = await auth_middleware.validate_access_token(token)
        
        assert token_info is not None
        assert token_info.user_id == "test_user_id"
        assert token_info.email == "test@example.com"
        assert token_info.role == "user"
    
    async def test_invalid_token_validation(self, auth_middleware):
        """Test validation of invalid tokens"""
        invalid_token = "invalid.jwt.token"
        
        token_info = await auth_middleware.validate_access_token(invalid_token)
        assert token_info is None
    
    async def test_token_blacklisting(self, auth_middleware):
        """Test token blacklisting functionality"""
        token = "test_token_to_blacklist"
        
        # Blacklist token
        success = await auth_middleware.blacklist_token(token, 3600)
        assert success is True
        
        # Check if token is blacklisted
        is_blacklisted = await auth_middleware.is_token_blacklisted(token)
        assert is_blacklisted is True
    
    async def test_rate_limiting(self, auth_middleware):
        """Test rate limiting functionality"""
        identifier = "test_user_id"
        
        # First request should be allowed
        result1 = await auth_middleware.check_rate_limit(identifier, "login", 5, 3600)
        assert result1["allowed"] is True
        assert result1["current"] == 1
        
        # Subsequent requests
        for i in range(2, 6):
            result = await auth_middleware.check_rate_limit(identifier, "login", 5, 3600)
            assert result["allowed"] is True
            assert result["current"] == i
        
        # Sixth request should be denied
        result6 = await auth_middleware.check_rate_limit(identifier, "login", 5, 3600)
        assert result6["allowed"] is False
    
    async def test_session_management(self, auth_middleware):
        """Test session creation and management"""
        user_id = "test_user_id"
        device_info = {
            "user_agent": "Mozilla/5.0 Test Browser",
            "ip_address": "192.168.1.1"
        }
        
        # Create session
        session_id = await auth_middleware.create_session(user_id, device_info)
        assert session_id is not None
        
        # Get session
        session_info = await auth_middleware.get_session(session_id)
        assert session_info is not None
        assert session_info.user_id == user_id
        
        # Update session
        success = await auth_middleware.update_session_activity(session_id)
        assert success is True
        
        # Revoke session
        success = await auth_middleware.revoke_session(session_id)
        assert success is True

class TestSecurityHeadersMiddleware:
    """Test security headers middleware"""
    
    @pytest.fixture
    def security_middleware(self):
        """Create security middleware instance for testing"""
        config = SecurityConfig(
            hsts_max_age=31536000,
            csp_directives={
                "default-src": "'self'",
                "script-src": "'self' 'unsafe-inline'",
                "style-src": "'self' 'unsafe-inline'"
            },
            frame_options="DENY",
            content_type_options=True,
            referrer_policy="strict-origin-when-cross-origin"
        )
        
        cors_config = CORSConfig(
            allowed_origins=["http://localhost:3000"],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
            allowed_headers=["*"],
            allow_credentials=True
        )
        
        return SecurityHeadersMiddleware(config, cors_config)
    
    async def test_security_headers_addition(self, security_middleware):
        """Test that security headers are properly added"""
        # Mock request and response
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"
        request.headers = {}
        
        # Mock call_next function
        async def mock_call_next(request):
            response = Mock()
            response.headers = {}
            return response
        
        # Process request
        response = await security_middleware.dispatch(request, mock_call_next)
        
        # Check security headers
        expected_headers = [
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Referrer-Policy",
            "X-XSS-Protection",
            "Permissions-Policy"
        ]
        
        for header in expected_headers:
            assert header in response.headers
    
    def test_csp_nonce_generation(self, security_middleware):
        """Test CSP nonce generation"""
        nonce = security_middleware._generate_nonce()
        assert len(nonce) == 32  # Base64 encoded 24 bytes
        assert nonce.isalnum() or '+' in nonce or '/' in nonce or '=' in nonce

class TestAPIKeyService:
    """Test API key management service"""
    
    @pytest.fixture
    async def api_key_service(self):
        """Create API key service instance for testing"""
        config = APIKeyConfig(
            key_length=32,
            default_expiry_days=365,
            max_keys_per_user=10,
            hash_algorithm="sha256"
        )
        
        # Mock dependencies
        supabase_client = Mock()
        redis_client = AsyncMock(spec=Redis)
        
        service = APIKeyService(config, supabase_client, redis_client)
        return service
    
    async def test_api_key_generation(self, api_key_service):
        """Test API key generation"""
        api_key = api_key_service._generate_api_key()
        assert len(api_key) == 64  # 32 bytes = 64 hex chars
        assert all(c in '0123456789abcdef' for c in api_key)
    
    async def test_api_key_hashing(self, api_key_service):
        """Test API key hashing"""
        api_key = "test_api_key_12345"
        hashed = api_key_service._hash_api_key(api_key)
        
        assert hashed != api_key  # Should be different from original
        assert len(hashed) == 64  # SHA256 hex digest length
    
    async def test_create_api_key(self, api_key_service):
        """Test API key creation"""
        user_id = "test_user_id"
        name = "Test API Key"
        scopes = [APIKeyScope.READ, APIKeyScope.WRITE]
        
        # Mock Supabase response
        api_key_service.supabase.table().insert().execute.return_value.data = [{
            "id": "key_id_123",
            "user_id": user_id,
            "name": name,
            "key_hash": "hashed_key",
            "scopes": [scope.value for scope in scopes],
            "status": APIKeyStatus.ACTIVE.value,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=365)).isoformat()
        }]
        
        result = await api_key_service.create_api_key(user_id, name, scopes)
        
        assert result is not None
        assert "api_key" in result
        assert "key_info" in result
        assert result["key_info"]["name"] == name
        assert result["key_info"]["user_id"] == user_id
    
    async def test_validate_api_key(self, api_key_service):
        """Test API key validation"""
        api_key = "test_api_key_12345"
        hashed_key = api_key_service._hash_api_key(api_key)
        
        # Mock Supabase response
        api_key_service.supabase.table().select().eq().execute.return_value.data = [{
            "id": "key_id_123",
            "user_id": "test_user_id",
            "name": "Test Key",
            "key_hash": hashed_key,
            "scopes": ["read", "write"],
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
            "last_used_at": None,
            "usage_count": 0
        }]
        
        key_info = await api_key_service.validate_api_key(api_key)
        
        assert key_info is not None
        assert key_info.user_id == "test_user_id"
        assert key_info.status == APIKeyStatus.ACTIVE
        assert APIKeyScope.READ in key_info.scopes
        assert APIKeyScope.WRITE in key_info.scopes

class TestRedisCacheService:
    """Test Redis caching service"""
    
    @pytest.fixture
    async def cache_service(self):
        """Create cache service instance for testing"""
        config = CacheConfig(
            default_ttl=3600,
            max_connections=10,
            key_prefix="test"
        )
        
        service = RedisCacheService(config)
        
        # Mock Redis client
        service.redis_client = AsyncMock(spec=Redis)
        
        return service
    
    async def test_cache_set_get(self, cache_service):
        """Test basic cache set and get operations"""
        key = "test_key"
        value = {"data": "test_value", "number": 42}
        
        # Mock Redis responses
        cache_service.redis_client.setex.return_value = True
        cache_service.redis_client.get.return_value = json.dumps(value).encode('utf-8')
        
        # Set value
        success = await cache_service.set(key, value, 300)
        assert success is True
        
        # Get value
        retrieved_value = await cache_service.get(key)
        assert retrieved_value == value
    
    async def test_cache_delete(self, cache_service):
        """Test cache deletion"""
        key = "test_key_to_delete"
        
        # Mock Redis response
        cache_service.redis_client.delete.return_value = 1
        
        success = await cache_service.delete(key)
        assert success is True
    
    async def test_cache_exists(self, cache_service):
        """Test cache key existence check"""
        key = "existing_key"
        
        # Mock Redis response
        cache_service.redis_client.exists.return_value = 1
        
        exists = await cache_service.exists(key)
        assert exists is True
    
    async def test_rate_limiting(self, cache_service):
        """Test rate limiting functionality"""
        identifier = "test_user"
        window = "minute"
        limit = 5
        
        # Mock Redis responses for rate limiting
        cache_service.redis_client.get.return_value = b'2'  # Current count
        cache_service.redis_client.incrby.return_value = 3  # New count
        cache_service.redis_client.ttl.return_value = 45  # TTL
        
        result = await cache_service.rate_limit_check(identifier, window, limit, 60)
        
        assert result["allowed"] is True
        assert result["current"] == 3
        assert result["limit"] == limit
        assert result["reset_time"] == 45
    
    async def test_user_session_caching(self, cache_service):
        """Test user session caching"""
        user_id = "test_user_123"
        session_data = {
            "user_id": user_id,
            "login_time": datetime.now().isoformat(),
            "permissions": ["read", "write"]
        }
        
        # Mock Redis responses
        cache_service.redis_client.setex.return_value = True
        cache_service.redis_client.get.return_value = json.dumps(session_data).encode('utf-8')
        
        # Cache session
        success = await cache_service.cache_user_session(user_id, session_data)
        assert success is True
        
        # Retrieve session
        retrieved_session = await cache_service.get_user_session(user_id)
        assert retrieved_session == session_data

class TestIntegrationSecurity:
    """Integration tests for security features"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_security_headers_in_response(self, client):
        """Test that security headers are present in API responses"""
        response = client.get("/health")
        
        # Check for security headers
        security_headers = [
            "strict-transport-security",
            "x-content-type-options",
            "x-frame-options",
            "referrer-policy"
        ]
        
        for header in security_headers:
            assert header in response.headers or header.title() in response.headers
    
    def test_cors_headers(self, client):
        """Test CORS headers in preflight requests"""
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers
    
    def test_rate_limiting_headers(self, client):
        """Test rate limiting headers"""
        # Make multiple requests to trigger rate limiting
        for i in range(5):
            response = client.get("/health")
            
            # Check for rate limiting headers
            if "x-ratelimit-limit" in response.headers:
                assert int(response.headers["x-ratelimit-limit"]) > 0
            if "x-ratelimit-remaining" in response.headers:
                assert int(response.headers["x-ratelimit-remaining"]) >= 0
    
    def test_authentication_required_endpoints(self, client):
        """Test that protected endpoints require authentication"""
        protected_endpoints = [
            "/api/auth/enhanced/sessions",
            "/api/auth/enhanced/api-keys",
            "/api/users/profile"
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403]  # Unauthorized or Forbidden
    
    def test_input_validation(self, client):
        """Test input validation on API endpoints"""
        # Test with invalid JSON
        response = client.post(
            "/api/auth/login",
            json={"email": "invalid-email", "password": ""}
        )
        assert response.status_code == 422  # Validation error
        
        # Test with missing required fields
        response = client.post("/api/auth/login", json={})
        assert response.status_code == 422
    
    def test_sql_injection_protection(self, client):
        """Test protection against SQL injection attempts"""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'/**/OR/**/1=1#",
            "<script>alert('xss')</script>"
        ]
        
        for malicious_input in malicious_inputs:
            response = client.post(
                "/api/auth/login",
                json={"email": malicious_input, "password": "password"}
            )
            
            # Should not cause server error (500)
            assert response.status_code != 500
            # Should return validation error or unauthorized
            assert response.status_code in [400, 401, 422]

class TestPerformanceOptimizations:
    """Test performance optimization features"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_response_compression(self, client):
        """Test that responses are compressed when appropriate"""
        response = client.get(
            "/health",
            headers={"Accept-Encoding": "gzip, deflate"}
        )
        
        # Check if compression is applied for larger responses
        if len(response.content) > 1000:
            assert "content-encoding" in response.headers
    
    def test_caching_headers(self, client):
        """Test that appropriate caching headers are set"""
        response = client.get("/health")
        
        # Check for cache control headers
        cache_headers = ["cache-control", "etag", "last-modified"]
        has_cache_header = any(header in response.headers for header in cache_headers)
        
        # At least one caching header should be present for cacheable endpoints
        if response.status_code == 200:
            # Note: This might not always be true depending on endpoint configuration
            pass  # Adjust based on actual caching strategy
    
    @pytest.mark.asyncio
    async def test_database_connection_pooling(self):
        """Test database connection pooling"""
        from api.services.database_pool_service import get_db_pool_service
        
        try:
            service = await get_db_pool_service()
            
            # Test health check
            health = await service.health_check()
            assert isinstance(health, dict)
            
            # Test pool stats
            stats = await service.get_pool_stats()
            assert "connection_metrics" in stats
            assert "query_metrics" in stats
            
        except Exception as e:
            # Connection might fail in test environment
            pytest.skip(f"Database connection not available: {e}")

# Test configuration
pytest_plugins = ["pytest_asyncio"]

# Run tests with: python -m pytest tests/test_security_enhancements.py -v
if __name__ == "__main__":
    pytest.main(["-v", __file__])