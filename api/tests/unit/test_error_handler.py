import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import json
import uuid
from datetime import datetime
from fastapi import HTTPException, status, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError, BaseModel
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from api.middleware.error_handler import (
    ErrorHandlerMiddleware, create_error_response,
    AuthenticationError, AuthorizationError, ResourceNotFoundError,
    RateLimitError, ValidationError as CustomValidationError
)

# Mock data and fixtures
class MockModel(BaseModel):
    """Mock Pydantic model for testing."""
    name: str
    email: str
    age: int

SAMPLE_ERROR_DATA = {
    "error": "Test error",
    "password": "secret123",
    "api_key": "sk-1234567890",
    "token": "bearer_token_123",
    "safe_data": "this is safe"
}

class TestErrorHandlerMiddleware:
    """Test ErrorHandlerMiddleware class functionality."""
    
    @pytest.fixture
    def error_middleware(self):
        """Create ErrorHandlerMiddleware instance."""
        return ErrorHandlerMiddleware()
    
    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"
        request.headers = {"content-type": "application/json"}
        request.client.host = "127.0.0.1"
        return request
    
    @pytest.fixture
    def mock_call_next(self):
        """Mock call_next function that succeeds."""
        async def call_next(request):
            response = Mock(spec=Response)
            response.status_code = 200
            response.body = b'{"message": "success"}'
            return response
        return call_next
    
    @pytest.fixture
    def mock_call_next_error(self):
        """Mock call_next function that raises an exception."""
        async def call_next(request):
            raise Exception("Test error")
        return call_next
    
    @pytest.mark.asyncio
    async def test_middleware_initialization(self, error_middleware):
        """Test middleware initialization."""
        assert error_middleware is not None
        assert hasattr(error_middleware, '__call__')
    
    @pytest.mark.asyncio
    async def test_middleware_success_path(self, error_middleware, mock_request, mock_call_next):
        """Test middleware with successful request processing."""
        response = await error_middleware(mock_request, mock_call_next)
        
        assert response.status_code == 200
        assert response.body == b'{"message": "success"}'
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_middleware_generic_exception(self, mock_generate_id, mock_log_error, 
                                              error_middleware, mock_request, mock_call_next_error):
        """Test middleware handling generic exceptions."""
        mock_generate_id.return_value = "req-123"
        
        response = await error_middleware(mock_request, mock_call_next_error)
        
        assert response.status_code == 500
        mock_log_error.assert_called_once()
        mock_generate_id.assert_called_once()
        
        # Check response body
        response_data = json.loads(response.body)
        assert response_data["error"] == "Internal server error"
        assert response_data["request_id"] == "req-123"
        assert "timestamp" in response_data
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_middleware_http_exception(self, mock_generate_id, mock_log_error, 
                                           error_middleware, mock_request):
        """Test middleware handling HTTP exceptions."""
        mock_generate_id.return_value = "req-456"
        
        async def call_next_http_error(request):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        
        response = await error_middleware(mock_request, call_next_http_error)
        
        assert response.status_code == 404
        mock_log_error.assert_called_once()
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Resource not found"
        assert response_data["request_id"] == "req-456"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_middleware_validation_exception(self, mock_generate_id, mock_log_error, 
                                                 error_middleware, mock_request):
        """Test middleware handling validation exceptions."""
        mock_generate_id.return_value = "req-789"
        
        async def call_next_validation_error(request):
            # Create a mock validation error
            from pydantic import ValidationError
            try:
                MockModel(name="", email="invalid", age="not_a_number")
            except ValidationError as e:
                raise RequestValidationError(errors=e.errors())
        
        response = await error_middleware(mock_request, call_next_validation_error)
        
        assert response.status_code == 422
        mock_log_error.assert_called_once()
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Validation error"
        assert "details" in response_data
        assert response_data["request_id"] == "req-789"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_middleware_database_exception(self, mock_generate_id, mock_log_error, 
                                               error_middleware, mock_request):
        """Test middleware handling database exceptions."""
        mock_generate_id.return_value = "req-db1"
        
        async def call_next_db_error(request):
            raise SQLAlchemyError("Database connection failed")
        
        response = await error_middleware(mock_request, call_next_db_error)
        
        assert response.status_code == 500
        mock_log_error.assert_called_once()
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Database error"
        assert response_data["request_id"] == "req-db1"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_middleware_integrity_error(self, mock_generate_id, mock_log_error, 
                                            error_middleware, mock_request):
        """Test middleware handling database integrity errors."""
        mock_generate_id.return_value = "req-int1"
        
        async def call_next_integrity_error(request):
            raise IntegrityError(
                "duplicate key value violates unique constraint",
                params=None,
                orig=None
            )
        
        response = await error_middleware(mock_request, call_next_integrity_error)
        
        assert response.status_code == 409
        mock_log_error.assert_called_once()
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Data conflict"
        assert response_data["request_id"] == "req-int1"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_middleware_operational_error(self, mock_generate_id, mock_log_error, 
                                              error_middleware, mock_request):
        """Test middleware handling database operational errors."""
        mock_generate_id.return_value = "req-op1"
        
        async def call_next_operational_error(request):
            raise OperationalError(
                "could not connect to server",
                params=None,
                orig=None
            )
        
        response = await error_middleware(mock_request, call_next_operational_error)
        
        assert response.status_code == 503
        mock_log_error.assert_called_once()
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Service temporarily unavailable"
        assert response_data["request_id"] == "req-op1"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_middleware_timeout_error(self, mock_generate_id, mock_log_error, 
                                          error_middleware, mock_request):
        """Test middleware handling timeout errors."""
        mock_generate_id.return_value = "req-timeout"
        
        async def call_next_timeout_error(request):
            import asyncio
            raise asyncio.TimeoutError("Request timeout")
        
        response = await error_middleware(mock_request, call_next_timeout_error)
        
        assert response.status_code == 408
        mock_log_error.assert_called_once()
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Request timeout"
        assert response_data["request_id"] == "req-timeout"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.filter_sensitive_data')
    async def test_middleware_sensitive_data_filtering(self, mock_filter_data, 
                                                     error_middleware, mock_request):
        """Test middleware filters sensitive data from error responses."""
        mock_filter_data.return_value = {"safe_data": "filtered"}
        
        async def call_next_with_sensitive_data(request):
            raise Exception("Error with sensitive data")
        
        response = await error_middleware(mock_request, call_next_with_sensitive_data)
        
        assert response.status_code == 500
        mock_filter_data.assert_called()

class TestGlobalExceptionHandler:
    """Test global exception handler function."""
    
    @pytest.fixture
    def mock_request(self):
        """Mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "POST"
        return request
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_global_exception_handler_generic_error(self, mock_generate_id, mock_log_error, mock_request):
        """Test global exception handler with generic error."""
        mock_generate_id.return_value = "global-123"
        
        exc = Exception("Generic error")
        response = await global_exception_handler(mock_request, exc)
        
        assert response.status_code == 500
        mock_log_error.assert_called_once_with(mock_request, exc, "global-123")
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Internal server error"
        assert response_data["request_id"] == "global-123"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_global_exception_handler_custom_error(self, mock_generate_id, mock_log_error, mock_request):
        """Test global exception handler with custom application error."""
        mock_generate_id.return_value = "custom-456"
        
        exc = DatabaseError("Custom database error")
        response = await global_exception_handler(mock_request, exc)
        
        assert response.status_code == 500
        mock_log_error.assert_called_once_with(mock_request, exc, "custom-456")
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Database error"
        assert response_data["request_id"] == "custom-456"

class TestHTTPExceptionHandler:
    """Test HTTP exception handler function."""
    
    @pytest.fixture
    def mock_request(self):
        """Mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/users/999"
        request.method = "GET"
        return request
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_http_exception_handler_404(self, mock_generate_id, mock_log_error, mock_request):
        """Test HTTP exception handler with 404 error."""
        mock_generate_id.return_value = "http-404"
        
        exc = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        response = await http_exception_handler(mock_request, exc)
        
        assert response.status_code == 404
        mock_log_error.assert_called_once_with(mock_request, exc, "http-404")
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "User not found"
        assert response_data["request_id"] == "http-404"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_http_exception_handler_401(self, mock_generate_id, mock_log_error, mock_request):
        """Test HTTP exception handler with 401 error."""
        mock_generate_id.return_value = "http-401"
        
        exc = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
        response = await http_exception_handler(mock_request, exc)
        
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Invalid credentials"
        assert response_data["request_id"] == "http-401"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_http_exception_handler_with_headers(self, mock_generate_id, mock_log_error, mock_request):
        """Test HTTP exception handler preserves custom headers."""
        mock_generate_id.return_value = "http-headers"
        
        exc = HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "0"
            }
        )
        response = await http_exception_handler(mock_request, exc)
        
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "0"
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Rate limit exceeded"

class TestValidationExceptionHandler:
    """Test validation exception handler function."""
    
    @pytest.fixture
    def mock_request(self):
        """Mock request object."""
        request = Mock(spec=Request)
        request.url.path = "/api/users"
        request.method = "POST"
        return request
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_validation_exception_handler_single_error(self, mock_generate_id, mock_log_error, mock_request):
        """Test validation exception handler with single validation error."""
        mock_generate_id.return_value = "val-single"
        
        # Create a validation error
        validation_errors = [
            {
                "loc": ["body", "email"],
                "msg": "field required",
                "type": "value_error.missing"
            }
        ]
        exc = RequestValidationError(errors=validation_errors)
        
        response = await validation_exception_handler(mock_request, exc)
        
        assert response.status_code == 422
        mock_log_error.assert_called_once_with(mock_request, exc, "val-single")
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Validation error"
        assert "details" in response_data
        assert len(response_data["details"]) == 1
        assert response_data["details"][0]["field"] == "body.email"
        assert response_data["details"][0]["message"] == "field required"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_validation_exception_handler_multiple_errors(self, mock_generate_id, mock_log_error, mock_request):
        """Test validation exception handler with multiple validation errors."""
        mock_generate_id.return_value = "val-multiple"
        
        # Create multiple validation errors
        validation_errors = [
            {
                "loc": ["body", "email"],
                "msg": "field required",
                "type": "value_error.missing"
            },
            {
                "loc": ["body", "age"],
                "msg": "ensure this value is greater than 0",
                "type": "value_error.number.not_gt",
                "ctx": {"limit_value": 0}
            },
            {
                "loc": ["query", "limit"],
                "msg": "ensure this value is less than or equal to 100",
                "type": "value_error.number.not_le",
                "ctx": {"limit_value": 100}
            }
        ]
        exc = RequestValidationError(errors=validation_errors)
        
        response = await validation_exception_handler(mock_request, exc)
        
        assert response.status_code == 422
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Validation error"
        assert len(response_data["details"]) == 3
        
        # Check each error detail
        details = response_data["details"]
        assert details[0]["field"] == "body.email"
        assert details[1]["field"] == "body.age"
        assert details[2]["field"] == "query.limit"
    
    @pytest.mark.asyncio
    @patch('api.middleware.error_handler.log_error')
    @patch('api.middleware.error_handler.generate_request_id')
    async def test_validation_exception_handler_nested_field(self, mock_generate_id, mock_log_error, mock_request):
        """Test validation exception handler with nested field errors."""
        mock_generate_id.return_value = "val-nested"
        
        # Create nested field validation error
        validation_errors = [
            {
                "loc": ["body", "user", "profile", "settings", "notifications"],
                "msg": "invalid choice",
                "type": "value_error.choice",
                "ctx": {"choices": ["email", "sms", "push"]}
            }
        ]
        exc = RequestValidationError(errors=validation_errors)
        
        response = await validation_exception_handler(mock_request, exc)
        
        assert response.status_code == 422
        
        response_data = json.loads(response.body)
        assert response_data["details"][0]["field"] == "body.user.profile.settings.notifications"
        assert response_data["details"][0]["message"] == "invalid choice"

class TestErrorHandlerUtilities:
    """Test utility functions for error handling."""
    
    def test_generate_request_id(self):
        """Test request ID generation."""
        request_id = generate_request_id()
        
        assert isinstance(request_id, str)
        assert len(request_id) > 0
        assert request_id.startswith("req-")
        
        # Test uniqueness
        request_id2 = generate_request_id()
        assert request_id != request_id2
    
    def test_filter_sensitive_data_with_sensitive_fields(self):
        """Test filtering of sensitive data fields."""
        filtered_data = filter_sensitive_data(SAMPLE_ERROR_DATA)
        
        assert filtered_data["password"] == "[FILTERED]"
        assert filtered_data["api_key"] == "[FILTERED]"
        assert filtered_data["token"] == "[FILTERED]"
        assert filtered_data["safe_data"] == "this is safe"
        assert filtered_data["error"] == "Test error"
    
    def test_filter_sensitive_data_no_sensitive_fields(self):
        """Test filtering with no sensitive data."""
        safe_data = {
            "message": "Success",
            "count": 42,
            "items": ["item1", "item2"]
        }
        
        filtered_data = filter_sensitive_data(safe_data)
        
        assert filtered_data == safe_data
    
    def test_filter_sensitive_data_nested_objects(self):
        """Test filtering of nested objects with sensitive data."""
        nested_data = {
            "user": {
                "name": "John Doe",
                "password": "secret123",
                "profile": {
                    "email": "john@example.com",
                    "api_key": "sk-1234567890"
                }
            },
            "metadata": {
                "token": "bearer_token",
                "timestamp": "2023-01-01T00:00:00Z"
            }
        }
        
        filtered_data = filter_sensitive_data(nested_data)
        
        assert filtered_data["user"]["name"] == "John Doe"
        assert filtered_data["user"]["password"] == "[FILTERED]"
        assert filtered_data["user"]["profile"]["email"] == "john@example.com"
        assert filtered_data["user"]["profile"]["api_key"] == "[FILTERED]"
        assert filtered_data["metadata"]["token"] == "[FILTERED]"
        assert filtered_data["metadata"]["timestamp"] == "2023-01-01T00:00:00Z"
    
    def test_filter_sensitive_data_list_with_objects(self):
        """Test filtering of lists containing objects with sensitive data."""
        list_data = {
            "users": [
                {"name": "User1", "password": "pass1"},
                {"name": "User2", "api_key": "key2"}
            ]
        }
        
        filtered_data = filter_sensitive_data(list_data)
        
        assert filtered_data["users"][0]["name"] == "User1"
        assert filtered_data["users"][0]["password"] == "[FILTERED]"
        assert filtered_data["users"][1]["name"] == "User2"
        assert filtered_data["users"][1]["api_key"] == "[FILTERED]"
    
    @patch('api.middleware.error_handler.logger')
    def test_log_error_with_request_details(self, mock_logger):
        """Test error logging with request details."""
        # Mock request
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "POST"
        request.client.host = "192.168.1.1"
        request.headers = {"user-agent": "test-client"}
        
        # Mock exception
        exc = Exception("Test error")
        request_id = "test-req-123"
        
        log_error(request, exc, request_id)
        
        # Verify logger was called
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        
        assert "Test error" in call_args
        assert "test-req-123" in call_args
        assert "/api/test" in call_args
        assert "POST" in call_args
    
    @patch('api.middleware.error_handler.logger')
    def test_log_error_with_sensitive_data_filtering(self, mock_logger):
        """Test error logging filters sensitive data."""
        request = Mock(spec=Request)
        request.url.path = "/api/auth"
        request.method = "POST"
        request.client.host = "127.0.0.1"
        request.headers = {}
        
        # Create exception with sensitive data
        exc = Exception("Authentication failed for password: secret123")
        request_id = "auth-req-456"
        
        log_error(request, exc, request_id)
        
        # Verify logger was called and sensitive data was filtered
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        
        # Should not contain the actual password
        assert "secret123" not in call_args
        assert "auth-req-456" in call_args
    
    def test_create_error_response_basic(self):
        """Test basic error response creation."""
        response = create_error_response(
            status_code=400,
            message="Bad request",
            request_id="test-123"
        )
        
        assert response.status_code == 400
        assert response.headers["content-type"] == "application/json"
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Bad request"
        assert response_data["request_id"] == "test-123"
        assert "timestamp" in response_data
    
    def test_create_error_response_with_details(self):
        """Test error response creation with additional details."""
        details = [
            {"field": "email", "message": "Invalid format"},
            {"field": "age", "message": "Must be positive"}
        ]
        
        response = create_error_response(
            status_code=422,
            message="Validation failed",
            request_id="val-789",
            details=details
        )
        
        assert response.status_code == 422
        
        response_data = json.loads(response.body)
        assert response_data["error"] == "Validation failed"
        assert response_data["details"] == details
        assert response_data["request_id"] == "val-789"
    
    def test_create_error_response_with_headers(self):
        """Test error response creation with custom headers."""
        headers = {
            "Retry-After": "60",
            "X-Custom-Header": "custom-value"
        }
        
        response = create_error_response(
            status_code=429,
            message="Rate limited",
            request_id="rate-123",
            headers=headers
        )
        
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
        assert response.headers["X-Custom-Header"] == "custom-value"
        assert response.headers["content-type"] == "application/json"

class TestErrorHandlerEdgeCases:
    """Test edge cases and error scenarios for error handler."""
    
    @pytest.fixture
    def error_middleware(self):
        """Create ErrorHandlerMiddleware instance."""
        return ErrorHandlerMiddleware()
    
    @pytest.mark.asyncio
    async def test_middleware_exception_in_error_handling(self, error_middleware):
        """Test middleware when error handling itself fails."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"
        
        async def call_next_error(request):
            raise Exception("Original error")
        
        # Mock generate_request_id to fail
        with patch('api.middleware.error_handler.generate_request_id', side_effect=Exception("ID generation failed")):
            response = await error_middleware(request, call_next_error)
            
            # Should still return a response, even if error handling fails
            assert response.status_code == 500
            response_data = json.loads(response.body)
            assert "error" in response_data
    
    @pytest.mark.asyncio
    async def test_middleware_malformed_request(self, error_middleware):
        """Test middleware with malformed request object."""
        # Create a request with missing attributes
        request = Mock()
        request.url = None
        request.method = None
        
        async def call_next_error(request):
            raise Exception("Test error")
        
        response = await error_middleware(request, call_next_error)
        
        assert response.status_code == 500
        response_data = json.loads(response.body)
        assert "error" in response_data
    
    def test_filter_sensitive_data_non_serializable(self):
        """Test filtering with non-serializable data."""
        import datetime
        
        data_with_objects = {
            "timestamp": datetime.datetime.now(),
            "password": "secret",
            "function": lambda x: x,
            "normal_field": "value"
        }
        
        # Should handle non-serializable data gracefully
        filtered_data = filter_sensitive_data(data_with_objects)
        
        assert filtered_data["password"] == "[FILTERED]"
        assert filtered_data["normal_field"] == "value"
        # Non-serializable fields should be handled appropriately
        assert "timestamp" in filtered_data
        assert "function" in filtered_data
    
    def test_filter_sensitive_data_circular_reference(self):
        """Test filtering with circular references."""
        data = {"password": "secret"}
        data["self"] = data  # Create circular reference
        
        # Should handle circular references gracefully
        filtered_data = filter_sensitive_data(data)
        
        assert filtered_data["password"] == "[FILTERED]"
    
    def test_filter_sensitive_data_very_large_object(self):
        """Test filtering with very large data objects."""
        # Create a large data structure
        large_data = {
            "password": "secret",
            "large_list": list(range(10000)),
            "nested": {
                "api_key": "key123",
                "more_data": {str(i): f"value_{i}" for i in range(1000)}
            }
        }
        
        filtered_data = filter_sensitive_data(large_data)
        
        assert filtered_data["password"] == "[FILTERED]"
        assert filtered_data["nested"]["api_key"] == "[FILTERED]"
        assert len(filtered_data["large_list"]) == 10000
        assert len(filtered_data["nested"]["more_data"]) == 1000
    
    @pytest.mark.asyncio
    async def test_middleware_memory_leak_prevention(self, error_middleware):
        """Test middleware doesn't cause memory leaks with many errors."""
        import gc
        
        # Get initial object count
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Process many errors
        for i in range(100):
            request = Mock(spec=Request)
            request.url.path = f"/api/test/{i}"
            request.method = "GET"
            
            async def call_next_error(request):
                raise Exception(f"Error {i}")
            
            try:
                await error_middleware(request, call_next_error)
            except Exception:
                pass  # Ignore for this test
        
        # Check memory usage
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory growth should be reasonable
        memory_growth_ratio = (final_objects - initial_objects) / initial_objects
        assert memory_growth_ratio < 0.5, f"Memory growth too high: {memory_growth_ratio:.2%}"
    
    def test_generate_request_id_uniqueness(self):
        """Test request ID generation produces unique IDs."""
        # Generate many IDs and check for uniqueness
        ids = set()
        for _ in range(1000):
            request_id = generate_request_id()
            assert request_id not in ids, f"Duplicate request ID generated: {request_id}"
            ids.add(request_id)
        
        assert len(ids) == 1000
    
    def test_create_error_response_invalid_status_code(self):
        """Test error response creation with invalid status code."""
        # Should handle invalid status codes gracefully
        response = create_error_response(
            status_code=999,  # Invalid status code
            message="Test error",
            request_id="test-123"
        )
        
        # Should still create a response
        assert response.status_code == 999
        response_data = json.loads(response.body)
        assert response_data["error"] == "Test error"
    
    @patch('api.middleware.error_handler.logger')
    def test_log_error_with_unicode_characters(self, mock_logger):
        """Test error logging with unicode characters."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "POST"
        request.client.host = "127.0.0.1"
        request.headers = {}
        
        # Exception with unicode characters
        exc = Exception("Error with unicode: 你好世界 🌍")
        request_id = "unicode-123"
        
        # Should handle unicode gracefully
        log_error(request, exc, request_id)
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "unicode-123" in call_args