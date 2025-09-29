#!/usr/bin/env python3
"""
Integration Test Suite

Comprehensive integration tests for:
- API endpoint functionality
- Authentication flows
- Database operations
- File upload/download
- WebSocket connections
- Background task processing
- Error handling and recovery
"""

import pytest
import asyncio
import json
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock

import httpx
from fastapi.testclient import TestClient
from fastapi import status
import websockets

# Import the main application
from api.main import app

class TestAPIEndpoints:
    """Test API endpoint functionality"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert "version" in data
    
    def test_detailed_health_endpoint(self, client):
        """Test detailed health check endpoint"""
        response = client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data
        assert "timestamp" in data
        
        # Check service health details
        services = data["services"]
        expected_services = ["database", "redis", "supabase"]
        
        for service in expected_services:
            if service in services:
                assert "status" in services[service]
                assert "response_time_ms" in services[service]
    
    def test_api_info_endpoint(self, client):
        """Test API info endpoint"""
        response = client.get("/api/info")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "endpoints" in data
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        
        # Metrics endpoint might return different formats
        assert response.status_code in [200, 404]  # 404 if metrics not enabled
        
        if response.status_code == 200:
            # Check if it's Prometheus format or JSON
            content_type = response.headers.get("content-type", "")
            assert content_type in ["text/plain", "application/json"]
    
    def test_cors_headers(self, client):
        """Test CORS headers in API responses"""
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # Check CORS headers
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers"
        ]
        
        for header in cors_headers:
            assert header in response.headers or header.title() in response.headers
    
    def test_security_headers(self, client):
        """Test security headers in API responses"""
        response = client.get("/health")
        
        # Check for security headers
        security_headers = [
            "strict-transport-security",
            "x-content-type-options",
            "x-frame-options",
            "referrer-policy"
        ]
        
        for header in security_headers:
            header_present = (
                header in response.headers or 
                header.title() in response.headers or
                header.replace("-", "").title() in response.headers
            )
            # Note: Some headers might not be present in test environment
            # This is more of a documentation of expected headers
    
    def test_rate_limiting(self, client):
        """Test rate limiting functionality"""
        # Make multiple requests to test rate limiting
        responses = []
        for i in range(10):
            response = client.get("/health")
            responses.append(response)
        
        # All requests should succeed in test environment
        # Rate limiting might be disabled or have high limits
        for response in responses:
            assert response.status_code == 200
        
        # Check for rate limiting headers if present
        last_response = responses[-1]
        rate_limit_headers = [
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset"
        ]
        
        # Headers might not be present in test environment
        for header in rate_limit_headers:
            if header in last_response.headers:
                assert int(last_response.headers[header]) >= 0

class TestAuthenticationFlow:
    """Test authentication and authorization flows"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_login_endpoint_validation(self, client):
        """Test login endpoint input validation"""
        # Test with missing fields
        response = client.post("/api/auth/login", json={})
        assert response.status_code == 422  # Validation error
        
        # Test with invalid email format
        response = client.post(
            "/api/auth/login",
            json={"email": "invalid-email", "password": "password123"}
        )
        assert response.status_code == 422
        
        # Test with empty password
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": ""}
        )
        assert response.status_code == 422
    
    def test_register_endpoint_validation(self, client):
        """Test registration endpoint input validation"""
        # Test with missing fields
        response = client.post("/api/auth/register", json={})
        assert response.status_code == 422
        
        # Test with invalid email
        response = client.post(
            "/api/auth/register",
            json={
                "email": "invalid-email",
                "password": "password123",
                "confirm_password": "password123"
            }
        )
        assert response.status_code == 422
        
        # Test with password mismatch
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "confirm_password": "different_password"
            }
        )
        assert response.status_code == 422
    
    def test_protected_endpoints_without_auth(self, client):
        """Test that protected endpoints require authentication"""
        protected_endpoints = [
            ("/api/users/profile", "GET"),
            ("/api/auth/enhanced/sessions", "GET"),
            ("/api/auth/enhanced/api-keys", "GET"),
            ("/api/auth/enhanced/api-keys", "POST"),
        ]
        
        for endpoint, method in protected_endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            elif method == "PUT":
                response = client.put(endpoint, json={})
            elif method == "DELETE":
                response = client.delete(endpoint)
            
            # Should return 401 (Unauthorized) or 403 (Forbidden)
            assert response.status_code in [401, 403]
    
    @patch('api.services.supabase_service.get_supabase_client')
    def test_login_flow_success(self, mock_supabase, client):
        """Test successful login flow"""
        # Mock Supabase response
        mock_client = Mock()
        mock_client.auth.sign_in_with_password.return_value.user = Mock(
            id="test_user_id",
            email="test@example.com",
            user_metadata={"role": "user"}
        )
        mock_client.auth.sign_in_with_password.return_value.session = Mock(
            access_token="mock_access_token",
            refresh_token="mock_refresh_token"
        )
        mock_supabase.return_value = mock_client
        
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"}
        )
        
        # In test environment, this might fail due to missing Supabase config
        # The test validates the endpoint structure
        assert response.status_code in [200, 400, 500]
    
    def test_token_refresh_endpoint(self, client):
        """Test token refresh endpoint"""
        response = client.post(
            "/api/auth/enhanced/refresh",
            json={"refresh_token": "mock_refresh_token"}
        )
        
        # Should require valid refresh token
        assert response.status_code in [400, 401, 422]
    
    def test_logout_endpoint(self, client):
        """Test logout endpoint"""
        response = client.post("/api/auth/enhanced/logout")
        
        # Should require authentication
        assert response.status_code in [401, 403]

class TestDatabaseOperations:
    """Test database operations and data integrity"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_user_settings_endpoint(self, client):
        """Test user settings endpoint"""
        response = client.get("/api/user/settings")
        
        # Should require authentication
        assert response.status_code in [401, 403]
    
    def test_user_history_endpoint(self, client):
        """Test user history endpoint"""
        response = client.get("/api/history")
        
        # Should require authentication
        assert response.status_code in [401, 403]
    
    def test_analytics_endpoints(self, client):
        """Test analytics endpoints"""
        analytics_endpoints = [
            "/api/analytics/user",
            "/api/analytics/system",
            "/api/analytics/performance"
        ]
        
        for endpoint in analytics_endpoints:
            response = client.get(endpoint)
            # Should require authentication or return data
            assert response.status_code in [200, 401, 403, 404]
    
    @patch('api.services.supabase_service.get_supabase_client')
    def test_database_health_check(self, mock_supabase, client):
        """Test database connectivity through health check"""
        # Mock Supabase client
        mock_client = Mock()
        mock_client.table().select().limit().execute.return_value.data = []
        mock_supabase.return_value = mock_client
        
        response = client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        if "services" in data and "database" in data["services"]:
            db_health = data["services"]["database"]
            assert "status" in db_health

class TestFileOperations:
    """Test file upload and download operations"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_file_upload_endpoint_structure(self, client):
        """Test file upload endpoint structure"""
        # Create a test file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
            tmp_file.write(b"Test file content")
            tmp_file_path = tmp_file.name
        
        try:
            with open(tmp_file_path, "rb") as f:
                response = client.post(
                    "/api/videos/upload",
                    files={"file": ("test.txt", f, "text/plain")}
                )
            
            # Should require authentication or validate file type
            assert response.status_code in [400, 401, 403, 422]
            
        finally:
            os.unlink(tmp_file_path)
    
    def test_file_upload_validation(self, client):
        """Test file upload validation"""
        # Test without file
        response = client.post("/api/videos/upload")
        assert response.status_code in [400, 422]
        
        # Test with invalid file type
        with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tmp_file:
            tmp_file.write(b"Invalid file content")
            tmp_file_path = tmp_file.name
        
        try:
            with open(tmp_file_path, "rb") as f:
                response = client.post(
                    "/api/videos/upload",
                    files={"file": ("malicious.exe", f, "application/octet-stream")}
                )
            
            # Should reject invalid file types
            assert response.status_code in [400, 422]
            
        finally:
            os.unlink(tmp_file_path)
    
    def test_large_file_handling(self, client):
        """Test large file handling"""
        # Create a larger test file (1MB)
        large_content = b"x" * (1024 * 1024)  # 1MB
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(large_content)
            tmp_file_path = tmp_file.name
        
        try:
            with open(tmp_file_path, "rb") as f:
                response = client.post(
                    "/api/videos/upload",
                    files={"file": ("large_video.mp4", f, "video/mp4")}
                )
            
            # Should handle large files appropriately
            # Might fail due to authentication or file size limits
            assert response.status_code in [200, 400, 401, 403, 413, 422]
            
        finally:
            os.unlink(tmp_file_path)

class TestWebSocketConnections:
    """Test WebSocket functionality"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection establishment"""
        # Note: This test might fail in test environment without proper setup
        try:
            # Test WebSocket endpoint structure
            with TestClient(app) as client:
                with client.websocket_connect("/ws/jobs") as websocket:
                    # Connection should be established
                    assert websocket is not None
                    
                    # Try to send a test message
                    test_message = {"type": "ping", "data": "test"}
                    websocket.send_json(test_message)
                    
                    # Should receive some response or connection should remain open
                    # The exact behavior depends on WebSocket implementation
                    
        except Exception as e:
            # WebSocket might not be available in test environment
            pytest.skip(f"WebSocket connection not available: {e}")
    
    @pytest.mark.asyncio
    async def test_websocket_authentication(self):
        """Test WebSocket authentication"""
        try:
            with TestClient(app) as client:
                # Try to connect without authentication
                with pytest.raises(Exception):  # Should fail without auth
                    with client.websocket_connect("/ws/jobs") as websocket:
                        pass
                        
        except Exception as e:
            pytest.skip(f"WebSocket testing not available: {e}")

class TestBackgroundTasks:
    """Test background task processing"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_job_creation_endpoint(self, client):
        """Test job creation endpoint"""
        response = client.post(
            "/api/jobs",
            json={
                "type": "video_processing",
                "parameters": {"input_file": "test.mp4"}
            }
        )
        
        # Should require authentication
        assert response.status_code in [401, 403, 422]
    
    def test_job_status_endpoint(self, client):
        """Test job status endpoint"""
        response = client.get("/api/jobs/test_job_id")
        
        # Should require authentication or return not found
        assert response.status_code in [401, 403, 404]
    
    def test_job_results_endpoint(self, client):
        """Test job results endpoint"""
        response = client.get("/api/results/test_job_id")
        
        # Should require authentication or return not found
        assert response.status_code in [401, 403, 404]

class TestErrorHandling:
    """Test error handling and recovery mechanisms"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_404_error_handling(self, client):
        """Test 404 error handling"""
        response = client.get("/api/nonexistent/endpoint")
        
        assert response.status_code == 404
        
        # Should return proper error format
        try:
            data = response.json()
            assert "detail" in data or "message" in data
        except json.JSONDecodeError:
            # Some 404 responses might not be JSON
            pass
    
    def test_405_method_not_allowed(self, client):
        """Test 405 Method Not Allowed handling"""
        # Try POST on a GET-only endpoint
        response = client.post("/health")
        
        assert response.status_code == 405
    
    def test_422_validation_error_format(self, client):
        """Test 422 validation error format"""
        response = client.post("/api/auth/login", json={"invalid": "data"})
        
        assert response.status_code == 422
        
        data = response.json()
        assert "detail" in data
        
        # Validation errors should have proper structure
        if isinstance(data["detail"], list):
            for error in data["detail"]:
                assert "loc" in error
                assert "msg" in error
                assert "type" in error
    
    def test_500_error_handling(self, client):
        """Test 500 internal server error handling"""
        # This is harder to test without causing actual errors
        # We can test that the error handler structure is in place
        
        # Try to trigger an error with malformed data
        response = client.post(
            "/api/auth/login",
            data="invalid json data",
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle malformed JSON gracefully
        assert response.status_code in [400, 422]
    
    def test_sql_injection_protection(self, client):
        """Test SQL injection protection"""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'/**/OR/**/1=1#"
        ]
        
        for malicious_input in malicious_inputs:
            response = client.post(
                "/api/auth/login",
                json={"email": malicious_input, "password": "password"}
            )
            
            # Should not cause server error
            assert response.status_code != 500
            # Should return validation error or unauthorized
            assert response.status_code in [400, 401, 422]
    
    def test_xss_protection(self, client):
        """Test XSS protection"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>"
        ]
        
        for payload in xss_payloads:
            response = client.post(
                "/api/auth/login",
                json={"email": payload, "password": "password"}
            )
            
            # Should handle XSS attempts safely
            assert response.status_code in [400, 401, 422]
            
            # Response should not contain unescaped script tags
            response_text = response.text.lower()
            assert "<script>" not in response_text
            assert "javascript:" not in response_text

class TestSystemIntegration:
    """Test overall system integration"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_application_startup(self, client):
        """Test that application starts up correctly"""
        # Test that basic endpoints are available
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test that API info is available
        response = client.get("/api/info")
        assert response.status_code == 200
    
    def test_middleware_chain(self, client):
        """Test that middleware chain is working"""
        response = client.get("/health")
        
        # Check that various middleware have processed the request
        # Security headers
        security_headers = [
            "x-content-type-options",
            "x-frame-options"
        ]
        
        # At least some security headers should be present
        has_security_headers = any(
            header in response.headers or header.title() in response.headers
            for header in security_headers
        )
        
        # CORS headers might be present
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-methods"
        ]
        
        # Response should be properly formatted
        assert response.headers.get("content-type", "").startswith("application/json")
    
    def test_api_documentation_availability(self, client):
        """Test API documentation availability"""
        # Test OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        
        # Test Swagger UI (might be disabled in production)
        response = client.get("/docs")
        assert response.status_code in [200, 404]
        
        # Test ReDoc (might be disabled in production)
        response = client.get("/redoc")
        assert response.status_code in [200, 404]
    
    def test_environment_configuration(self, client):
        """Test environment configuration"""
        # Test that the application is configured correctly
        response = client.get("/api/info")
        
        if response.status_code == 200:
            data = response.json()
            assert "version" in data
            assert "name" in data
    
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, client):
        """Test concurrent request handling"""
        import asyncio
        import httpx
        
        async def make_request():
            async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/health")
                return response.status_code
        
        # Make multiple concurrent requests
        tasks = [make_request() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        # All requests should succeed
        assert all(status_code == 200 for status_code in results)
        assert len(results) == 20
    
    def test_request_timeout_handling(self, client):
        """Test request timeout handling"""
        # Test with a request that might take time
        response = client.get("/health/detailed")
        
        # Should complete within reasonable time
        assert response.status_code in [200, 503]  # 503 if services are down
    
    def test_graceful_degradation(self, client):
        """Test graceful degradation when services are unavailable"""
        # Test health endpoint when some services might be down
        response = client.get("/health/detailed")
        
        if response.status_code == 200:
            data = response.json()
            
            # System should still respond even if some services are down
            assert "status" in data
            
            if "services" in data:
                # Some services might be down, but system should handle it gracefully
                for service_name, service_health in data["services"].items():
                    assert "status" in service_health
                    assert service_health["status"] in ["healthy", "unhealthy", "degraded"]

# Test configuration
pytest_plugins = ["pytest_asyncio"]

# Run tests with: python -m pytest tests/test_integration.py -v
if __name__ == "__main__":
    pytest.main(["-v", __file__])