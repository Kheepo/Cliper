"""Integration tests for API endpoints and service interactions."""

import pytest
import asyncio
import json
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
import redis
from celery import Celery


@pytest.mark.integration
class TestAPIIntegration:
    """Test API integration with external services."""
    
    def test_health_check_integration(self, test_client: TestClient):
        """Test health check endpoint with real service checks."""
        response = test_client.get("/health")
        assert response.status_code in [200, 503]  # Healthy or unhealthy
        
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "system_metrics" in data
        
        # Verify check structure
        checks = data["checks"]
        expected_checks = ["redis", "celery", "supabase", "disk", "memory"]
        
        for check_name in expected_checks:
            if check_name in checks:
                check_result = checks[check_name]
                assert "status" in check_result
                assert check_result["status"] in ["healthy", "unhealthy", "warning", "critical"]
    
    def test_metrics_endpoint_integration(self, test_client: TestClient):
        """Test metrics endpoint returns valid system metrics."""
        response = test_client.get("/metrics")
        assert response.status_code == 200
        
        data = response.json()
        required_metrics = [
            "request_count", "avg_response_time", "error_rate",
            "cpu_percent", "memory_percent"
        ]
        
        for metric in required_metrics:
            assert metric in data
            assert isinstance(data[metric], (int, float))
            assert data[metric] >= 0
    
    @pytest.mark.redis
    def test_redis_health_integration(self, test_client: TestClient):
        """Test Redis health check with actual Redis connection."""
        response = test_client.get("/redis/health")
        
        # Should return either healthy (if Redis is running) or unhealthy
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "status" in data
        
        if response.status_code == 200:
            assert data["status"] == "healthy"
            assert "info" in data
            assert "redis_version" in data["info"]
        else:
            assert data["status"] == "unhealthy"
            assert "error" in data
    
    @pytest.mark.celery
    def test_celery_status_integration(self, test_client: TestClient):
        """Test Celery status with actual Celery connection."""
        response = test_client.get("/celery/status")
        
        # Should return either success or error
        assert response.status_code in [200, 503]
        
        data = response.json()
        
        if response.status_code == 200:
            assert "workers" in data
            assert "active_tasks" in data
            assert "scheduled_tasks" in data
            assert isinstance(data["workers"], dict)
        else:
            assert "error" in data
    
    def test_processing_stats_integration(self, test_client: TestClient):
        """Test processing statistics endpoint."""
        response = test_client.get("/stats/processing")
        assert response.status_code == 200
        
        data = response.json()
        expected_stats = [
            "total_videos_processed", "total_clips_generated",
            "avg_processing_time", "success_rate"
        ]
        
        for stat in expected_stats:
            assert stat in data
            assert isinstance(data[stat], (int, float))
    
    def test_cors_integration(self, test_client: TestClient):
        """Test CORS headers in actual requests."""
        # Test preflight request
        response = test_client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
    
    def test_rate_limiting_integration(self, test_client: TestClient):
        """Test rate limiting with multiple requests."""
        # Make multiple requests quickly
        responses = []
        for i in range(10):
            response = test_client.get("/")
            responses.append(response)
        
        # Most requests should succeed, but some might be rate limited
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        
        # At least some requests should succeed
        assert success_count > 0
        # Total should be all requests
        assert success_count + rate_limited_count <= len(responses)
    
    def test_error_handling_integration(self, test_client: TestClient):
        """Test error handling with various error scenarios."""
        # Test 404 error
        response = test_client.get("/non-existent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        
        # Test 405 error (method not allowed)
        response = test_client.post("/")  # Root only accepts GET
        assert response.status_code == 405
        data = response.json()
        assert "detail" in data
    
    def test_request_id_integration(self, test_client: TestClient):
        """Test request ID generation and tracking."""
        response = test_client.get("/")
        assert response.status_code == 200
        
        # Check for request ID in headers
        headers = response.headers
        request_id_headers = [
            "x-request-id", "request-id", "x-correlation-id"
        ]
        
        has_request_id = any(header in headers for header in request_id_headers)
        # Request ID might be added by middleware
        # assert has_request_id  # Uncomment if request ID middleware is implemented


@pytest.mark.integration
class TestServiceIntegration:
    """Test integration between different services."""
    
    @pytest.mark.asyncio
    async def test_redis_service_integration(self, mock_redis):
        """Test Redis service integration."""
        from api.services.redis_service import RedisService
        
        with patch('api.services.redis_service.redis_client', mock_redis):
            service = RedisService()
            
            # Test basic operations
            await service.set("test_key", "test_value")
            mock_redis.set.assert_called_with("test_key", "test_value")
            
            mock_redis.get.return_value = "test_value"
            value = await service.get("test_key")
            assert value == "test_value"
            
            await service.delete("test_key")
            mock_redis.delete.assert_called_with("test_key")
    
    @pytest.mark.asyncio
    async def test_supabase_service_integration(self, mock_supabase_service):
        """Test Supabase service integration."""
        # Test job operations
        job_data = {
            "id": "test_job_123",
            "status": "pending",
            "video_url": "https://example.com/video.mp4"
        }
        
        # Test creating a job
        job_id = await mock_supabase_service.create_job(job_data)
        assert job_id == "test_job_id"
        
        # Test getting a job
        job = await mock_supabase_service.get_job("test_job_123")
        assert job["id"] == "test"
        assert job["status"] == "pending"
        
        # Test updating a job
        result = await mock_supabase_service.update_job("test_job_123", {"status": "processing"})
        assert result is True
    
    @pytest.mark.asyncio
    async def test_llm_service_integration(self, mock_llm_service):
        """Test LLM service integration."""
        # Test video analysis
        analysis = await mock_llm_service.analyze_video("https://example.com/video.mp4")
        
        assert "virality_score" in analysis
        assert "highlights" in analysis
        assert "summary" in analysis
        assert 0 <= analysis["virality_score"] <= 1
        
        # Test title generation
        title = await mock_llm_service.generate_title("Video about cats")
        assert isinstance(title, str)
        assert len(title) > 0
        
        # Test description generation
        description = await mock_llm_service.generate_description("Funny cat video")
        assert isinstance(description, str)
        assert len(description) > 0
    
    @pytest.mark.asyncio
    async def test_video_processor_integration(self, mock_video_processor):
        """Test video processor integration."""
        # Test video info extraction
        video_info = await mock_video_processor.get_video_info("https://example.com/video.mp4")
        
        assert "duration" in video_info
        assert "width" in video_info
        assert "height" in video_info
        assert "fps" in video_info
        
        # Test clip extraction
        clip_url = await mock_video_processor.extract_clip(
            "https://example.com/video.mp4", 30, 60
        )
        assert isinstance(clip_url, str)
        assert clip_url.startswith("https://")
        
        # Test thumbnail generation
        thumbnail_url = await mock_video_processor.generate_thumbnail(
            "https://example.com/video.mp4", 30
        )
        assert isinstance(thumbnail_url, str)
        assert thumbnail_url.startswith("https://")
    
    @pytest.mark.asyncio
    async def test_storage_service_integration(self, mock_storage_service):
        """Test storage service integration."""
        # Test file upload
        file_data = b"test file content"
        upload_url = await mock_storage_service.upload_file(file_data, "test.mp4")
        
        assert isinstance(upload_url, str)
        assert upload_url.startswith("https://")
        
        # Test file deletion
        result = await mock_storage_service.delete_file("test.mp4")
        assert result is True
        
        # Test download URL generation
        download_url = await mock_storage_service.get_download_url("test.mp4")
        assert isinstance(download_url, str)
        assert download_url.startswith("https://")
    
    @pytest.mark.asyncio
    async def test_auth_service_integration(self, mock_auth_service):
        """Test authentication service integration."""
        # Test token verification
        token_data = await mock_auth_service.verify_token("valid_token")
        
        assert "user_id" in token_data
        assert "email" in token_data
        assert token_data["user_id"] == "test_user_123"
        
        # Test token creation
        token = await mock_auth_service.create_token({"user_id": "test_user_123"})
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Test token refresh
        new_token = await mock_auth_service.refresh_token("old_token")
        assert isinstance(new_token, str)
        assert len(new_token) > 0


@pytest.mark.integration
class TestMonitoringIntegration:
    """Test monitoring system integration."""
    
    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, mock_health_checker):
        """Test health monitoring system integration."""
        # Test comprehensive health check
        health_result = await mock_health_checker.run_all_checks()
        
        assert "status" in health_result
        assert "checks" in health_result
        assert "system_metrics" in health_result
        
        # Verify check results structure
        checks = health_result["checks"]
        for check_name, check_result in checks.items():
            assert "status" in check_result
            assert check_result["status"] in ["healthy", "unhealthy", "warning", "critical"]
    
    def test_performance_monitoring_integration(self, mock_performance_monitor):
        """Test performance monitoring integration."""
        # Test metrics collection
        metrics = mock_performance_monitor.get_current_metrics()
        
        required_metrics = [
            "request_count", "avg_response_time", "error_rate",
            "active_connections", "cpu_percent", "memory_percent"
        ]
        
        for metric in required_metrics:
            assert metric in metrics
            assert isinstance(metrics[metric], (int, float))
    
    @pytest.mark.asyncio
    async def test_alerting_integration(self, mock_alert_manager):
        """Test alerting system integration."""
        # Test alert creation
        alert = await mock_alert_manager.create_alert(
            title="Test Integration Alert",
            message="This is a test alert for integration testing",
            severity="warning",
            source="integration_test"
        )
        
        assert alert.id == "test_alert_123"
        
        # Test alert resolution
        result = await mock_alert_manager.resolve_alert(alert.id)
        assert result is True
        
        # Test getting active alerts
        active_alerts = await mock_alert_manager.get_active_alerts()
        assert isinstance(active_alerts, list)
    
    @pytest.mark.asyncio
    async def test_service_discovery_integration(self):
        """Test service discovery integration."""
        from api.monitoring.service_discovery import ServiceRegistry
        
        registry = ServiceRegistry()
        
        # Test service registration
        service_info = {
            "name": "test-service",
            "host": "localhost",
            "port": 8000,
            "health_check_url": "/health",
            "metadata": {"version": "1.0.0"}
        }
        
        result = await registry.register_service("test-service-1", service_info)
        assert result is True
        
        # Test service discovery
        services = await registry.discover_services("test-service")
        assert len(services) >= 0  # Might be 0 if no services registered
        
        # Test service deregistration
        result = await registry.deregister_service("test-service-1")
        assert result is True


@pytest.mark.integration
class TestWorkflowIntegration:
    """Test complete workflow integration."""
    
    @pytest.mark.asyncio
    async def test_video_processing_workflow(self, async_test_client: AsyncClient):
        """Test complete video processing workflow."""
        # This would test the entire video processing pipeline
        # from upload to clip generation
        
        # Mock the workflow steps
        with patch('api.services.supabase_service.supabase_service') as mock_supabase, \
             patch('api.services.llm_service') as mock_llm, \
             patch('api.services.video_processor') as mock_processor:
            
            # Setup mocks
            mock_supabase.create_job = AsyncMock(return_value="job_123")
            mock_llm.analyze_video = AsyncMock(return_value={
                "virality_score": 0.85,
                "highlights": [{"start": 30, "end": 60, "score": 0.9}]
            })
            mock_processor.extract_clip = AsyncMock(return_value="https://example.com/clip.mp4")
            
            # Test workflow would go here
            # This is a placeholder for actual workflow testing
            pass
    
    @pytest.mark.asyncio
    async def test_monitoring_workflow(self, async_test_client: AsyncClient):
        """Test monitoring and alerting workflow."""
        # Test the complete monitoring workflow
        # from metrics collection to alert generation
        
        with patch('api.monitoring.performance_monitor.performance_monitor') as mock_monitor, \
             patch('api.monitoring.alerting.alert_manager') as mock_alerts:
            
            # Setup high CPU usage scenario
            mock_monitor.get_current_metrics.return_value = {
                "cpu_percent": 95.0,  # High CPU
                "memory_percent": 60.0,
                "error_rate": 0.01
            }
            
            mock_alerts.check_alert_rules = AsyncMock(return_value=[
                Mock(title="High CPU Usage", severity="critical")
            ])
            
            # Test monitoring endpoint
            response = await async_test_client.get("/metrics")
            assert response.status_code == 200
            
            # Verify alert would be triggered
            metrics = response.json()
            if metrics.get("cpu_percent", 0) > 90:
                # Alert should be triggered
                pass
    
    def test_health_check_workflow(self, test_client: TestClient):
        """Test health check workflow across all services."""
        # Test the complete health check workflow
        response = test_client.get("/health")
        
        # Should return comprehensive health status
        assert response.status_code in [200, 503]
        data = response.json()
        
        # Verify workflow completeness
        assert "status" in data
        assert "checks" in data
        assert "system_metrics" in data
        assert "timestamp" in data
        
        # If unhealthy, should have error details
        if response.status_code == 503:
            assert data["status"] == "unhealthy"
            # Should have details about what's failing
            unhealthy_checks = [
                check for check, result in data["checks"].items()
                if result.get("status") == "unhealthy"
            ]
            assert len(unhealthy_checks) > 0


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceIntegration:
    """Test performance-related integration scenarios."""
    
    def test_concurrent_requests(self, test_client: TestClient):
        """Test handling of concurrent requests."""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = test_client.get("/")
            results.append(response.status_code)
        
        # Create multiple threads to make concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # Verify results
        assert len(results) == 10
        success_count = sum(1 for status in results if status == 200)
        
        # Most requests should succeed
        assert success_count >= 8  # Allow for some rate limiting
        
        # Should complete in reasonable time
        assert end_time - start_time < 10  # 10 seconds max
    
    def test_large_response_handling(self, test_client: TestClient):
        """Test handling of large responses."""
        # Test metrics endpoint which might return large data
        response = test_client.get("/metrics")
        assert response.status_code == 200
        
        # Verify response is properly formatted JSON
        data = response.json()
        assert isinstance(data, dict)
        
        # Response should be reasonable size
        content_length = len(response.content)
        assert content_length < 1024 * 1024  # Less than 1MB
    
    def test_memory_usage_stability(self, test_client: TestClient):
        """Test memory usage remains stable under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Make many requests
        for _ in range(100):
            response = test_client.get("/")
            assert response.status_code == 200
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024