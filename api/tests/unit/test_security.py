import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, HTTPException
from fastapi.testclient import TestClient
from api.middleware.security import (
    SecurityMiddleware, SecurityConfig, InputValidator, 
    CSRFProtection, rate_limit
)
from api.main import app

class TestSecurityConfig:
    """Test security configuration."""
    
    def test_default_config(self):
        """Test default security configuration values."""
        config = SecurityConfig()
        
        assert config.rate_limit_requests == 100
        assert config.rate_limit_window == 3600
        assert config.max_content_length == 100 * 1024 * 1024  # 100MB
        assert config.enforce_https is True
        assert config.allowed_content_types == [
            "application/json", "multipart/form-data", 
            "application/x-www-form-urlencoded", "video/mp4", 
            "video/avi", "video/mov", "video/wmv"
        ]
    
    def test_custom_config(self):
        """Test custom security configuration."""
        config = SecurityConfig(
            rate_limit_requests=50,
            rate_limit_window=1800,
            max_content_length=50 * 1024 * 1024,
            enforce_https=False
        )
        
        assert config.rate_limit_requests == 50
        assert config.rate_limit_window == 1800
        assert config.max_content_length == 50 * 1024 * 1024
        assert config.enforce_https is False

class TestInputValidator:
    """Test input validation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = InputValidator()
    
    def test_sanitize_string_basic(self):
        """Test basic string sanitization."""
        clean_text = "Hello World"
        result = self.validator.sanitize_string(clean_text)
        assert result == clean_text
    
    def test_sanitize_string_html_injection(self):
        """Test HTML injection sanitization."""
        malicious_text = "<script>alert('xss')</script>Hello"
        result = self.validator.sanitize_string(malicious_text)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Hello" in result
    
    def test_sanitize_string_sql_injection(self):
        """Test SQL injection sanitization."""
        malicious_text = "'; DROP TABLE users; --"
        result = self.validator.sanitize_string(malicious_text)
        assert "DROP TABLE" not in result
        assert "--" not in result
    
    def test_validate_filename_valid(self):
        """Test valid filename validation."""
        valid_filenames = [
            "video.mp4",
            "my_video_2024.avi",
            "test-file.mov",
            "document.pdf"
        ]
        
        for filename in valid_filenames:
            assert self.validator.validate_filename(filename) is True
    
    def test_validate_filename_invalid(self):
        """Test invalid filename validation."""
        invalid_filenames = [
            "../../../etc/passwd",
            "file\\with\\backslashes.txt",
            "file:with:colons.txt",
            "file<with>brackets.txt",
            "file|with|pipes.txt",
            "file*with*asterisks.txt",
            "file?with?questions.txt",
            "file\"with\"quotes.txt"
        ]
        
        for filename in invalid_filenames:
            assert self.validator.validate_filename(filename) is False
    
    def test_validate_email_valid(self):
        """Test valid email validation."""
        valid_emails = [
            "user@example.com",
            "test.email+tag@domain.co.uk",
            "user123@test-domain.org"
        ]
        
        for email in valid_emails:
            assert self.validator.validate_email(email) is True
    
    def test_validate_email_invalid(self):
        """Test invalid email validation."""
        invalid_emails = [
            "invalid-email",
            "@domain.com",
            "user@",
            "user..double.dot@domain.com",
            "user@domain",
            "user name@domain.com"  # space in local part
        ]
        
        for email in invalid_emails:
            assert self.validator.validate_email(email) is False
    
    def test_validate_url_valid(self):
        """Test valid URL validation."""
        valid_urls = [
            "https://www.example.com",
            "http://localhost:3000",
            "https://api.domain.com/v1/endpoint",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ]
        
        for url in valid_urls:
            assert self.validator.validate_url(url) is True
    
    def test_validate_url_invalid(self):
        """Test invalid URL validation."""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",  # Only HTTP/HTTPS allowed
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "file:///etc/passwd"
        ]
        
        for url in invalid_urls:
            assert self.validator.validate_url(url) is False

class TestCSRFProtection:
    """Test CSRF protection functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.csrf = CSRFProtection()
    
    def test_generate_token(self):
        """Test CSRF token generation."""
        token = self.csrf.generate_token()
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Generate another token and ensure they're different
        token2 = self.csrf.generate_token()
        assert token != token2
    
    def test_validate_token_valid(self):
        """Test valid CSRF token validation."""
        token = self.csrf.generate_token()
        
        # Store token in session
        session = {"csrf_token": token}
        
        # Validate the same token
        assert self.csrf.validate_token(token, session) is True
    
    def test_validate_token_invalid(self):
        """Test invalid CSRF token validation."""
        token = self.csrf.generate_token()
        session = {"csrf_token": token}
        
        # Try to validate a different token
        invalid_token = "invalid-token-123"
        assert self.csrf.validate_token(invalid_token, session) is False
    
    def test_validate_token_missing_session(self):
        """Test CSRF token validation with missing session token."""
        token = self.csrf.generate_token()
        session = {}  # No CSRF token in session
        
        assert self.csrf.validate_token(token, session) is False

class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @patch('redis.Redis')
    def test_rate_limit_within_limit(self, mock_redis):
        """Test rate limiting when within limits."""
        # Mock Redis client
        mock_redis_client = Mock()
        mock_redis_client.get.return_value = b'5'  # 5 requests made
        mock_redis_client.incr.return_value = 6
        mock_redis_client.expire.return_value = True
        mock_redis.return_value = mock_redis_client
        
        # Mock request
        mock_request = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Should not raise exception (within limit of 100)
        try:
            rate_limit(mock_request, limit=100, window=3600)
        except HTTPException:
            pytest.fail("Rate limit should not be exceeded")
    
    @patch('redis.Redis')
    def test_rate_limit_exceeded(self, mock_redis):
        """Test rate limiting when limit is exceeded."""
        # Mock Redis client
        mock_redis_client = Mock()
        mock_redis_client.get.return_value = b'100'  # 100 requests made
        mock_redis_client.incr.return_value = 101
        mock_redis.return_value = mock_redis_client
        
        # Mock request
        mock_request = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            rate_limit(mock_request, limit=100, window=3600)
        
        assert exc_info.value.status_code == 429
        assert "rate limit exceeded" in exc_info.value.detail.lower()
    
    @patch('redis.Redis')
    def test_rate_limit_redis_error(self, mock_redis):
        """Test rate limiting when Redis is unavailable."""
        # Mock Redis client to raise exception
        mock_redis_client = Mock()
        mock_redis_client.get.side_effect = Exception("Redis connection failed")
        mock_redis.return_value = mock_redis_client
        
        # Mock request
        mock_request = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Should not raise exception (fail open)
        try:
            rate_limit(mock_request, limit=100, window=3600)
        except HTTPException:
            pytest.fail("Rate limit should fail open when Redis is unavailable")

class TestSecurityMiddleware:
    """Test security middleware integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = SecurityConfig(
            rate_limit_requests=10,
            rate_limit_window=60,
            max_content_length=1024,
            enforce_https=False  # Disable for testing
        )
        self.middleware = SecurityMiddleware(app, config=self.config)
    
    @pytest.mark.asyncio
    async def test_security_headers_added(self):
        """Test that security headers are added to responses."""
        # Mock request and response
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/health"
        mock_request.headers = {}
        mock_request.client.host = "127.0.0.1"
        
        mock_response = Mock()
        mock_response.headers = {}
        
        # Mock call_next to return the response
        async def mock_call_next(request):
            return mock_response
        
        # Process request through middleware
        result = await self.middleware.dispatch(mock_request, mock_call_next)
        
        # Check that security headers are added
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "Referrer-Policy"
        ]
        
        for header in expected_headers:
            assert header in result.headers
    
    @pytest.mark.asyncio
    async def test_content_length_validation(self):
        """Test content length validation."""
        # Mock request with large content
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/videos/upload"
        mock_request.headers = {
            "content-length": str(self.config.max_content_length + 1)
        }
        mock_request.client.host = "127.0.0.1"
        
        async def mock_call_next(request):
            return Mock()
        
        # Should raise HTTPException for large content
        with pytest.raises(HTTPException) as exc_info:
            await self.middleware.dispatch(mock_request, mock_call_next)
        
        assert exc_info.value.status_code == 413
    
    @pytest.mark.asyncio
    async def test_content_type_validation(self):
        """Test content type validation."""
        # Mock request with invalid content type
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/videos/upload"
        mock_request.headers = {
            "content-type": "application/octet-stream",
            "content-length": "1024"
        }
        mock_request.client.host = "127.0.0.1"
        
        async def mock_call_next(request):
            return Mock()
        
        # Should raise HTTPException for invalid content type
        with pytest.raises(HTTPException) as exc_info:
            await self.middleware.dispatch(mock_request, mock_call_next)
        
        assert exc_info.value.status_code == 415

class TestSecurityIntegration:
    """Test security features integration with the API."""
    
    def test_security_headers_in_response(self, client):
        """Test that security headers are present in API responses."""
        response = client.get("/api/health")
        
        # Check for security headers
        assert "x-content-type-options" in response.headers
        assert "x-frame-options" in response.headers
        assert "x-xss-protection" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
    
    def test_rate_limiting_integration(self, client, rate_limit_headers):
        """Test rate limiting integration with API endpoints."""
        # Make multiple requests to trigger rate limiting
        responses = []
        for i in range(15):  # Exceed the limit
            response = client.get("/api/health", headers=rate_limit_headers)
            responses.append(response)
        
        # Some requests should be rate limited
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        assert len(rate_limited_responses) > 0
    
    def test_input_validation_integration(self, client):
        """Test input validation integration."""
        # Test with malicious input
        malicious_data = {
            "url": "javascript:alert('xss')",
            "user_id": "<script>alert('xss')</script>"
        }
        
        response = client.post("/api/process-url", json=malicious_data)
        
        # Should either reject or sanitize the input
        assert response.status_code in [400, 422]
        
        if response.status_code == 200:
            # If accepted, ensure response doesn't contain malicious content
            response_text = response.text
            assert "<script>" not in response_text
            assert "javascript:" not in response_text
    
    def test_file_upload_security(self, client):
        """Test file upload security measures."""
        # Test with malicious filename
        malicious_filename = "../../../etc/passwd"
        
        response = client.post(
            "/api/videos/upload",
            files={"file": (malicious_filename, b"fake video content", "video/mp4")},
            data={"user_id": "test-user"}
        )
        
        # Should reject malicious filenames
        assert response.status_code in [400, 422]
    
    def test_https_enforcement_disabled_in_test(self, client):
        """Test that HTTPS enforcement is properly disabled in test environment."""
        # This should work in test environment
        response = client.get("/api/health")
        assert response.status_code == 200
        
        # In production, this would redirect to HTTPS
        # but in test environment, it should work normally