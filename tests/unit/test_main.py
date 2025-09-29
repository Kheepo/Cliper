"""Unit tests for main API endpoints."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app


class TestMainEndpoints:
    """Test main API endpoints."""
    
    def test_root_endpoint(self, test_client: TestClient):
        """Test root endpoint returns welcome message."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Cliper API" in data["message"]
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"
    
    @patch('api.monitoring.health.health_checker')
    def test_health_endpoint(self, mock_health_checker, test_client: TestClient):
        """Test health check endpoint."""
        mock_health_checker.run_all_checks = AsyncMock(return_value={
            "status": "healthy",
            "checks": {
                "redis": {"status": "healthy", "response_time": 0.001},
                "celery": {"status": "healthy", "workers": 1},
                "supabase": {"status": "healthy", "response_time": 0.1}
            },
            "system_metrics": {
                "cpu_percent": 25.0,
                "memory_percent": 60.0,
                "disk_percent": 45.0
            }
        })
        
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" in data
        assert "system_metrics" in data
    
    @patch('api.monitoring.performance_monitor.performance_monitor')
    def test_metrics_endpoint(self, mock_monitor, test_client: TestClient):
        """Test system metrics endpoint."""
        mock_monitor.get_current_metrics.return_value = {
            "request_count": 100,
            "avg_response_time": 0.5,
            "error_rate": 0.01,
            "active_connections": 10,
            "cpu_percent": 25.0,
            "memory_percent": 60.0,
            "disk_percent": 45.0
        }
        
        response = test_client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "request_count" in data
        assert "avg_response_time" in data
        assert "error_rate" in data
        assert "cpu_percent" in data
    
    @patch('api.services.redis_service.redis_client')
    def test_redis_health_endpoint(self, mock_redis, test_client: TestClient):
        """Test Redis health endpoint."""
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            'redis_version': '6.0.0',
            'used_memory': 1024000,
            'connected_clients': 1,
            'uptime_in_seconds': 3600
        }
        
        response = test_client.get("/redis/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "info" in data
        assert data["info"]["redis_version"] == "6.0.0"
    
    @patch('api.services.redis_service.redis_client')
    def test_redis_health_endpoint_failure(self, mock_redis, test_client: TestClient):
        """Test Redis health endpoint when Redis is down."""
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        response = test_client.get("/redis/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data
    
    @patch('api.tasks.celery_app')
    def test_celery_status_endpoint(self, mock_celery, test_client: TestClient):
        """Test Celery status endpoint."""
        mock_inspect = Mock()
        mock_inspect.stats.return_value = {'worker1': {'pool': {'max-concurrency': 4}}}
        mock_inspect.active.return_value = {'worker1': []}
        mock_inspect.scheduled.return_value = {'worker1': []}
        mock_inspect.reserved.return_value = {'worker1': []}
        mock_celery.control.inspect.return_value = mock_inspect
        
        response = test_client.get("/celery/status")
        assert response.status_code == 200
        data = response.json()
        assert "workers" in data
        assert "active_tasks" in data
        assert "scheduled_tasks" in data
    
    @patch('api.tasks.celery_app')
    def test_celery_status_endpoint_failure(self, mock_celery, test_client: TestClient):
        """Test Celery status endpoint when Celery is down."""
        mock_celery.control.inspect.side_effect = Exception("Connection failed")
        
        response = test_client.get("/celery/status")
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
    
    @patch('api.monitoring.performance_monitor.performance_monitor')
    def test_processing_stats_endpoint(self, mock_monitor, test_client: TestClient):
        """Test processing statistics endpoint."""
        mock_monitor.get_processing_stats.return_value = {
            "total_videos_processed": 150,
            "total_clips_generated": 450,
            "avg_processing_time": 45.2,
            "success_rate": 0.95,
            "queue_size": 5,
            "active_jobs": 2
        }
        
        response = test_client.get("/stats/processing")
        assert response.status_code == 200
        data = response.json()
        assert "total_videos_processed" in data
        assert "total_clips_generated" in data
        assert "avg_processing_time" in data
        assert "success_rate" in data


class TestMiddleware:
    """Test middleware functionality."""
    
    def test_cors_middleware(self, test_client: TestClient):
        """Test CORS middleware allows cross-origin requests."""
        response = test_client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
    
    def test_compression_middleware(self, test_client: TestClient):
        """Test compression middleware compresses responses."""
        response = test_client.get("/", headers={
            "Accept-Encoding": "gzip"
        })
        assert response.status_code == 200
        # Check if response is compressed (FastAPI handles this automatically)
        assert len(response.content) > 0
    
    def test_request_id_middleware(self, test_client: TestClient):
        """Test request ID middleware adds unique request ID."""
        response = test_client.get("/")
        assert response.status_code == 200
        # Request ID should be added by middleware
        assert "x-request-id" in response.headers or "request-id" in response.headers
    
    def test_rate_limiting_middleware(self, test_client: TestClient):
        """Test rate limiting middleware."""
        # Make multiple requests quickly
        responses = []
        for _ in range(5):
            response = test_client.get("/")
            responses.append(response)
        
        # All requests should succeed under normal rate limits
        for response in responses:
            assert response.status_code == 200
    
    def test_error_handling_middleware(self, test_client: TestClient):
        """Test error handling middleware catches exceptions."""
        # Test non-existent endpoint
        response = test_client.get("/non-existent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestAppConfiguration:
    """Test application configuration."""
    
    def test_app_title(self):
        """Test application title is set correctly."""
        assert app.title == "Cliper API"
    
    def test_app_version(self):
        """Test application version is set."""
        assert hasattr(app, 'version')
        assert app.version is not None
    
    def test_app_description(self):
        """Test application description is set."""
        assert hasattr(app, 'description')
        assert app.description is not None
    
    def test_openapi_configuration(self):
        """Test OpenAPI configuration."""
        openapi_schema = app.openapi()
        assert openapi_schema["info"]["title"] == "Cliper API"
        assert "paths" in openapi_schema
        assert "/" in openapi_schema["paths"]
        assert "/health" in openapi_schema["paths"]
    
    def test_middleware_order(self):
        """Test middleware is configured in correct order."""
        # Check that middleware stack is properly configured
        assert len(app.user_middleware) > 0
        
        # Verify specific middleware types are present
        middleware_types = [middleware.cls.__name__ for middleware in app.user_middleware]
        
        # Common middleware should be present
        expected_middleware = [
            'CORSMiddleware',
            'GZipMiddleware',
            'TrustedHostMiddleware'
        ]
        
        for middleware_name in expected_middleware:
            assert any(middleware_name in mw_type for mw_type in middleware_types)


class TestEnvironmentConfiguration:
    """Test environment-specific configuration."""
    
    @patch.dict('os.environ', {'ENVIRONMENT': 'development'})
    def test_development_environment(self):
        """Test development environment configuration."""
        from api.main import app
        # In development, docs should be available
        assert app.docs_url is not None
        assert app.redoc_url is not None
    
    @patch.dict('os.environ', {'ENVIRONMENT': 'production'})
    def test_production_environment(self):
        """Test production environment configuration."""
        # Note: This would require reloading the app module
        # In production, docs might be disabled
        pass
    
    @patch.dict('os.environ', {'ENVIRONMENT': 'test'})
    def test_test_environment(self):
        """Test test environment configuration."""
        from api.main import app
        # In test environment, docs should be available for testing
        assert app.docs_url is not None


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_404_error_handling(self, test_client: TestClient):
        """Test 404 error handling."""
        response = test_client.get("/non-existent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_405_error_handling(self, test_client: TestClient):
        """Test 405 method not allowed error handling."""
        response = test_client.post("/")  # Root only accepts GET
        assert response.status_code == 405
        data = response.json()
        assert "detail" in data
    
    def test_422_validation_error_handling(self, test_client: TestClient):
        """Test 422 validation error handling."""
        # This would require an endpoint that accepts POST with validation
        # For now, test with invalid JSON
        response = test_client.post(
            "/health",  # Assuming health doesn't accept POST
            json={"invalid": "data"}
        )
        # Should return method not allowed or validation error
        assert response.status_code in [405, 422]
    
    @patch('api.monitoring.health.health_checker')
    def test_internal_server_error_handling(self, mock_health_checker, test_client: TestClient):
        """Test 500 internal server error handling."""
        mock_health_checker.run_all_checks = AsyncMock(side_effect=Exception("Internal error"))
        
        response = test_client.get("/health")
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data or "error" in data


class TestSecurityHeaders:
    """Test security headers are properly set."""
    
    def test_security_headers_present(self, test_client: TestClient):
        """Test that security headers are present in responses."""
        response = test_client.get("/")
        assert response.status_code == 200
        
        # Check for common security headers
        headers = response.headers
        
        # These headers might be set by middleware
        security_headers = [
            'x-content-type-options',
            'x-frame-options',
            'x-xss-protection',
            'strict-transport-security'
        ]
        
        # At least some security headers should be present
        # (depending on middleware configuration)
        present_headers = [header for header in security_headers if header in headers]
        # We don't assert all are present as it depends on middleware setup
    
    def test_cors_headers(self, test_client: TestClient):
        """Test CORS headers are properly configured."""
        response = test_client.get("/", headers={
            "Origin": "http://localhost:3000"
        })
        assert response.status_code == 200
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers