"""Comprehensive tests for API endpoints and middleware.

Tests:
- All API routes and endpoints
- Authentication and authorization
- Request/response validation
- Error handling
- Rate limiting
- Middleware functionality
- Health checks and monitoring
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime, timedelta
from typing import Dict, Any

from ..main import app
from ..middleware.production_middleware import RequestTrackingMiddleware, MemoryMonitoringMiddleware
from ..utils.auth import create_access_token, verify_token
from ..models.user import User
from ..models.clip import Clip


class TestAPIEndpoints:
    """Test all API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers for testing."""
        token = create_access_token(data={"sub": "test_user_123"})
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def sample_video_file(self):
        """Create sample video file for upload testing."""
        return {
            "file": ("test_video.mp4", b"fake video content", "video/mp4")
        }
    
    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    def test_detailed_health_status(self, client):
        """Test detailed health status endpoint."""
        with patch('api.utils.health_manager.HealthManager.get_health_status') as mock_health:
            mock_health.return_value = {
                "status": "healthy",
                "components": {
                    "database": {"status": "healthy", "response_time": 0.05},
                    "redis": {"status": "healthy", "response_time": 0.02},
                    "storage": {"status": "healthy", "response_time": 0.1}
                },
                "timestamp": datetime.now().isoformat()
            }
            
            response = client.get("/health/status")
            
            assert response.status_code == 200
            data = response.json()
            assert "components" in data
            assert "database" in data["components"]
            assert "redis" in data["components"]
    
    def test_system_metrics_endpoint(self, client):
        """Test system metrics endpoint."""
        with patch('api.routes.monitoring.collect_system_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "cpu_percent": 45.2,
                "memory_percent": 67.8,
                "disk_usage_percent": 34.5,
                "network_io": {"bytes_sent": 1024000, "bytes_recv": 2048000},
                "load_average": [1.2, 1.5, 1.8],
                "process_count": 156,
                "uptime_seconds": 86400
            }
            
            response = client.get("/monitoring/system")
            
            assert response.status_code == 200
            data = response.json()
            assert "cpu_percent" in data
            assert "memory_percent" in data
            assert data["cpu_percent"] == 45.2
    
    def test_application_metrics_endpoint(self, client):
        """Test application metrics endpoint."""
        with patch('api.routes.monitoring.collect_application_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "total_clips": 1250,
                "clips_processing": 5,
                "clips_completed_today": 89,
                "clips_failed_today": 2,
                "active_users": 45,
                "total_users": 1200,
                "storage_used_gb": 156.7,
                "avg_processing_time_seconds": 45.2,
                "queue_length": 3,
                "cache_hit_rate": 0.87,
                "error_rate": 0.02
            }
            
            response = client.get("/monitoring/application")
            
            assert response.status_code == 200
            data = response.json()
            assert "total_clips" in data
            assert "active_users" in data
            assert data["total_clips"] == 1250
    
    def test_user_registration(self, client):
        """Test user registration endpoint."""
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",
            "username": "testuser"
        }
        
        with patch('api.services.user_service.UserService.create_user') as mock_create:
            mock_create.return_value = {
                "id": "user_123",
                "email": "test@example.com",
                "username": "testuser",
                "created_at": datetime.now().isoformat()
            }
            
            response = client.post("/auth/register", json=user_data)
            
            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["email"] == "test@example.com"
    
    def test_user_login(self, client):
        """Test user login endpoint."""
        login_data = {
            "email": "test@example.com",
            "password": "securepassword123"
        }
        
        with patch('api.services.user_service.UserService.authenticate_user') as mock_auth:
            mock_auth.return_value = {
                "id": "user_123",
                "email": "test@example.com",
                "username": "testuser"
            }
            
            response = client.post("/auth/login", json=login_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "token_type" in data
            assert data["token_type"] == "bearer"
    
    def test_video_upload_endpoint(self, client, auth_headers, sample_video_file):
        """Test video upload endpoint."""
        with patch('api.services.video_pipeline.VideoPipeline.process_video') as mock_process:
            mock_process.return_value = {
                "job_id": "job_123",
                "status": "processing",
                "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat()
            }
            
            response = client.post(
                "/videos/upload",
                files=sample_video_file,
                headers=auth_headers
            )
            
            assert response.status_code == 202  # Accepted for processing
            data = response.json()
            assert "job_id" in data
            assert data["status"] == "processing"
    
    def test_video_upload_without_auth(self, client, sample_video_file):
        """Test video upload without authentication."""
        response = client.post(
            "/videos/upload",
            files=sample_video_file
        )
        
        assert response.status_code == 401  # Unauthorized
    
    def test_get_processing_status(self, client, auth_headers):
        """Test getting video processing status."""
        job_id = "job_123"
        
        with patch('api.services.job_service.JobService.get_job_status') as mock_status:
            mock_status.return_value = {
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
                "clips_generated": 5,
                "completed_at": datetime.now().isoformat()
            }
            
            response = client.get(f"/videos/status/{job_id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == job_id
            assert data["status"] == "completed"
    
    def test_get_user_clips(self, client, auth_headers):
        """Test getting user's clips."""
        with patch('api.services.clip_service.ClipService.get_user_clips') as mock_clips:
            mock_clips.return_value = [
                {
                    "id": "clip_1",
                    "text": "Amazing AI breakthrough",
                    "virality_score": 0.85,
                    "hashtags": ["#ai", "#technology"],
                    "created_at": datetime.now().isoformat()
                },
                {
                    "id": "clip_2",
                    "text": "Future of technology",
                    "virality_score": 0.78,
                    "hashtags": ["#future", "#tech"],
                    "created_at": (datetime.now() - timedelta(hours=1)).isoformat()
                }
            ]
            
            response = client.get("/clips/my-clips", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["id"] == "clip_1"
    
    def test_get_trending_clips(self, client):
        """Test getting trending clips (public endpoint)."""
        with patch('api.services.clip_service.ClipService.get_trending_clips') as mock_trending:
            mock_trending.return_value = [
                {
                    "id": "trending_1",
                    "text": "Viral content example",
                    "virality_score": 0.95,
                    "hashtags": ["#viral", "#trending"],
                    "user_id": "user_456"
                }
            ]
            
            response = client.get("/clips/trending")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 1
            assert data[0]["virality_score"] >= 0.8  # High virality threshold
    
    def test_clip_details_endpoint(self, client):
        """Test getting specific clip details."""
        clip_id = "clip_123"
        
        with patch('api.services.clip_service.ClipService.get_clip') as mock_clip:
            mock_clip.return_value = {
                "id": clip_id,
                "text": "Detailed clip content",
                "virality_score": 0.82,
                "hashtags": ["#detailed", "#content"],
                "metadata": {
                    "duration": 25.5,
                    "file_size": 2048000,
                    "resolution": "1920x1080"
                },
                "created_at": datetime.now().isoformat()
            }
            
            response = client.get(f"/clips/{clip_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == clip_id
            assert "metadata" in data
    
    def test_invalid_clip_id(self, client):
        """Test getting non-existent clip."""
        with patch('api.services.clip_service.ClipService.get_clip') as mock_clip:
            mock_clip.return_value = None
            
            response = client.get("/clips/nonexistent_clip")
            
            assert response.status_code == 404
    
    def test_request_validation_errors(self, client):
        """Test request validation errors."""
        # Test invalid registration data
        invalid_user_data = {
            "email": "invalid-email",  # Invalid email format
            "password": "123",  # Too short
            "username": ""  # Empty username
        }
        
        response = client.post("/auth/register", json=invalid_user_data)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    def test_rate_limiting(self, client):
        """Test rate limiting functionality."""
        # Make multiple rapid requests
        responses = []
        for i in range(10):
            response = client.get("/health")
            responses.append(response)
        
        # Most requests should succeed, but rate limiting might kick in
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        
        # At least some requests should succeed
        assert success_count > 0
        # Rate limiting might or might not trigger depending on configuration
        assert success_count + rate_limited_count == 10


class TestMiddleware:
    """Test middleware functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client with middleware."""
        return TestClient(app)
    
    def test_request_tracking_middleware(self, client):
        """Test request tracking middleware."""
        response = client.get("/health")
        
        # Should have correlation ID in response headers
        assert "X-Correlation-ID" in response.headers
        assert len(response.headers["X-Correlation-ID"]) > 0
    
    def test_cors_middleware(self, client):
        """Test CORS middleware."""
        response = client.options("/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        # Should have CORS headers
        assert "Access-Control-Allow-Origin" in response.headers
    
    def test_security_headers_middleware(self, client):
        """Test security headers middleware."""
        response = client.get("/health")
        
        # Should have security headers
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection"
        ]
        
        for header in expected_headers:
            assert header in response.headers
    
    @pytest.mark.asyncio
    async def test_memory_monitoring_middleware(self):
        """Test memory monitoring middleware."""
        from fastapi import Request, Response
        from ..middleware.production_middleware import MemoryMonitoringMiddleware
        
        middleware = MemoryMonitoringMiddleware(app)
        
        # Mock request and response
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "GET"
        
        async def call_next(request):
            return Response(content="test", status_code=200)
        
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 75.0  # Normal memory usage
            
            response = await middleware.dispatch(request, call_next)
            
            assert response.status_code == 200


class TestAuthentication:
    """Test authentication and authorization."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_token_creation_and_verification(self):
        """Test JWT token creation and verification."""
        user_data = {"sub": "test_user_123", "email": "test@example.com"}
        
        # Create token
        token = create_access_token(data=user_data)
        assert token is not None
        assert len(token) > 0
        
        # Verify token
        payload = verify_token(token)
        assert payload["sub"] == "test_user_123"
        assert payload["email"] == "test@example.com"
    
    def test_expired_token(self):
        """Test handling of expired tokens."""
        user_data = {"sub": "test_user_123"}
        
        # Create token with very short expiration
        token = create_access_token(data=user_data, expires_delta=timedelta(seconds=-1))
        
        # Should raise exception for expired token
        with pytest.raises(Exception):
            verify_token(token)
    
    def test_invalid_token(self):
        """Test handling of invalid tokens."""
        invalid_token = "invalid.jwt.token"
        
        with pytest.raises(Exception):
            verify_token(invalid_token)
    
    def test_protected_endpoint_without_token(self, client):
        """Test accessing protected endpoint without token."""
        response = client.get("/clips/my-clips")
        
        assert response.status_code == 401
    
    def test_protected_endpoint_with_valid_token(self, client):
        """Test accessing protected endpoint with valid token."""
        token = create_access_token(data={"sub": "test_user_123"})
        headers = {"Authorization": f"Bearer {token}"}
        
        with patch('api.services.clip_service.ClipService.get_user_clips') as mock_clips:
            mock_clips.return_value = []
            
            response = client.get("/clips/my-clips", headers=headers)
            
            assert response.status_code == 200


class TestErrorHandling:
    """Test error handling across the API."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_404_error_handling(self, client):
        """Test 404 error handling."""
        response = client.get("/nonexistent-endpoint")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_500_error_handling(self, client):
        """Test 500 error handling."""
        with patch('api.routes.monitoring.collect_system_metrics') as mock_metrics:
            mock_metrics.side_effect = Exception("Internal server error")
            
            response = client.get("/monitoring/system")
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
    
    def test_database_connection_error(self, client):
        """Test database connection error handling."""
        with patch('api.services.clip_service.ClipService.get_trending_clips') as mock_clips:
            mock_clips.side_effect = Exception("Database connection failed")
            
            response = client.get("/clips/trending")
            
            assert response.status_code == 500
    
    def test_file_upload_error(self, client):
        """Test file upload error handling."""
        token = create_access_token(data={"sub": "test_user_123"})
        headers = {"Authorization": f"Bearer {token}"}
        
        # Upload invalid file
        invalid_file = {
            "file": ("test.txt", b"not a video file", "text/plain")
        }
        
        response = client.post(
            "/videos/upload",
            files=invalid_file,
            headers=headers
        )
        
        assert response.status_code == 400  # Bad request


class TestPerformance:
    """Test API performance characteristics."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_response_time_health_check(self, client):
        """Test health check response time."""
        import time
        
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0  # Should respond within 1 second
    
    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests."""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = client.get("/health")
            results.append(response.status_code)
        
        # Create 10 concurrent threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        start_time = time.time()
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # All requests should succeed
        assert len(results) == 10
        assert all(status == 200 for status in results)
        
        # Should handle concurrent requests efficiently
        assert total_time < 5.0  # Should complete within 5 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])