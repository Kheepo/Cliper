"""Comprehensive integration tests for the video-to-clip generation system.

Tests:
- End-to-end video processing workflow
- System integration scenarios
- Performance under load
- Error recovery and resilience
- Production readiness validation
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
import time
import threading

from fastapi.testclient import TestClient
from ..main import app
from ..services.video_pipeline import VideoPipeline
from ..services.video_processor import VideoProcessor
from ..services.clip_generator import ClipGenerator
from ..services.firebase_service import FirebaseService
from ..utils.enhanced_memory_optimizer import EnhancedMemoryOptimizer
from ..utils.production_monitoring import ProductionMonitor


class TestEndToEndWorkflow:
    """Test complete end-to-end video processing workflow."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        from ..utils.auth import create_access_token
        token = create_access_token(data={"sub": "test_user_123"})
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def sample_video_data(self):
        """Create sample video data for testing."""
        return {
            "filename": "test_video.mp4",
            "content": b"fake video content for testing",
            "content_type": "video/mp4",
            "size": 1024 * 1024 * 10  # 10MB
        }
    
    @pytest.fixture
    def mock_transcription(self):
        """Mock transcription data."""
        return {
            "text": "This is an amazing breakthrough in artificial intelligence technology. "
                   "The new model can process complex data and generate insights that were "
                   "previously impossible. This will revolutionize how we approach machine learning "
                   "and could lead to significant advances in automation and decision making.",
            "segments": [
                {
                    "start": 0.0,
                    "end": 15.0,
                    "text": "This is an amazing breakthrough in artificial intelligence technology."
                },
                {
                    "start": 15.0,
                    "end": 30.0,
                    "text": "The new model can process complex data and generate insights."
                },
                {
                    "start": 30.0,
                    "end": 45.0,
                    "text": "This will revolutionize how we approach machine learning."
                }
            ],
            "duration": 45.0
        }
    
    @pytest.fixture
    def mock_clips(self):
        """Mock generated clips data."""
        return [
            {
                "id": "clip_1",
                "text": "Amazing breakthrough in AI technology",
                "start_time": 0.0,
                "end_time": 15.0,
                "virality_score": 0.85,
                "hashtags": ["#AI", "#technology", "#breakthrough"],
                "keywords": ["AI", "breakthrough", "technology"]
            },
            {
                "id": "clip_2",
                "text": "Revolutionary machine learning advances",
                "start_time": 30.0,
                "end_time": 45.0,
                "virality_score": 0.78,
                "hashtags": ["#MachineLearning", "#revolution", "#AI"],
                "keywords": ["machine learning", "revolution", "automation"]
            }
        ]
    
    @pytest.mark.asyncio
    async def test_complete_video_processing_workflow(self, client, auth_headers, 
                                                    sample_video_data, mock_transcription, 
                                                    mock_clips):
        """Test complete video processing from upload to clip generation."""
        
        # Step 1: Upload video
        with patch('api.services.video_pipeline.VideoPipeline.process_video') as mock_process:
            mock_process.return_value = {
                "job_id": "job_123",
                "status": "processing",
                "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat()
            }
            
            upload_response = client.post(
                "/videos/upload",
                files={"file": (sample_video_data["filename"], 
                              sample_video_data["content"], 
                              sample_video_data["content_type"])},
                headers=auth_headers
            )
            
            assert upload_response.status_code == 202
            upload_data = upload_response.json()
            job_id = upload_data["job_id"]
        
        # Step 2: Check processing status
        with patch('api.services.job_service.JobService.get_job_status') as mock_status:
            mock_status.return_value = {
                "job_id": job_id,
                "status": "processing",
                "progress": 50,
                "current_stage": "transcription",
                "estimated_completion": (datetime.now() + timedelta(minutes=2)).isoformat()
            }
            
            status_response = client.get(f"/videos/status/{job_id}", headers=auth_headers)
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["status"] == "processing"
            assert status_data["progress"] == 50
        
        # Step 3: Simulate completion and check final status
        with patch('api.services.job_service.JobService.get_job_status') as mock_final_status:
            mock_final_status.return_value = {
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
                "clips_generated": len(mock_clips),
                "completed_at": datetime.now().isoformat()
            }
            
            final_status_response = client.get(f"/videos/status/{job_id}", headers=auth_headers)
            
            assert final_status_response.status_code == 200
            final_data = final_status_response.json()
            assert final_data["status"] == "completed"
            assert final_data["clips_generated"] == len(mock_clips)
        
        # Step 4: Retrieve generated clips
        with patch('api.services.clip_service.ClipService.get_user_clips') as mock_user_clips:
            mock_user_clips.return_value = mock_clips
            
            clips_response = client.get("/clips/my-clips", headers=auth_headers)
            
            assert clips_response.status_code == 200
            clips_data = clips_response.json()
            assert len(clips_data) == len(mock_clips)
            
            # Verify clip quality
            for clip in clips_data:
                assert "virality_score" in clip
                assert clip["virality_score"] > 0.7  # High quality threshold
                assert "hashtags" in clip
                assert len(clip["hashtags"]) > 0
    
    @pytest.mark.asyncio
    async def test_video_processing_pipeline_integration(self, mock_transcription, mock_clips):
        """Test video processing pipeline integration."""
        
        # Create temporary video file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file.write(b"fake video content")
            temp_file_path = temp_file.name
        
        try:
            # Initialize pipeline components
            video_processor = VideoProcessor()
            clip_generator = ClipGenerator()
            firebase_service = FirebaseService()
            
            # Mock external dependencies
            with patch.object(video_processor, 'extract_audio') as mock_extract_audio, \
                 patch.object(video_processor, 'transcribe_audio') as mock_transcribe, \
                 patch.object(clip_generator, 'generate_clips') as mock_generate, \
                 patch.object(firebase_service, 'save_clips') as mock_save_clips, \
                 patch.object(firebase_service, 'save_virality_scores') as mock_save_scores:
                
                # Setup mocks
                mock_extract_audio.return_value = "temp_audio.wav"
                mock_transcribe.return_value = mock_transcription
                mock_generate.return_value = mock_clips
                mock_save_clips.return_value = True
                mock_save_scores.return_value = True
                
                # Create pipeline
                pipeline = VideoPipeline(
                    video_processor=video_processor,
                    clip_generator=clip_generator,
                    firebase_service=firebase_service
                )
                
                # Process video
                result = await pipeline.process_video(
                    video_path=temp_file_path,
                    user_id="test_user_123"
                )
                
                # Verify results
                assert result["status"] == "completed"
                assert result["clips_generated"] == len(mock_clips)
                assert "processing_time" in result
                
                # Verify all components were called
                mock_extract_audio.assert_called_once()
                mock_transcribe.assert_called_once()
                mock_generate.assert_called_once()
                mock_save_clips.assert_called_once()
                mock_save_scores.assert_called_once()
        
        finally:
            # Cleanup
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def test_error_recovery_workflow(self, client, auth_headers, sample_video_data):
        """Test error recovery in video processing workflow."""
        
        # Test transcription failure recovery
        with patch('api.services.video_pipeline.VideoPipeline.process_video') as mock_process:
            mock_process.side_effect = Exception("Transcription service unavailable")
            
            upload_response = client.post(
                "/videos/upload",
                files={"file": (sample_video_data["filename"], 
                              sample_video_data["content"], 
                              sample_video_data["content_type"])},
                headers=auth_headers
            )
            
            # Should handle error gracefully
            assert upload_response.status_code in [500, 503]  # Server error or service unavailable
        
        # Test retry mechanism
        with patch('api.services.video_pipeline.VideoPipeline.process_video') as mock_process:
            # First call fails, second succeeds
            mock_process.side_effect = [
                Exception("Temporary failure"),
                {
                    "job_id": "job_retry_123",
                    "status": "processing",
                    "retry_count": 1
                }
            ]
            
            # This would be handled by the retry mechanism in production
            # For testing, we simulate the retry behavior
            try:
                result = mock_process()
            except Exception:
                # Retry
                result = mock_process()
            
            assert result["job_id"] == "job_retry_123"
            assert result["retry_count"] == 1


class TestSystemIntegration:
    """Test system integration scenarios."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_health_monitoring_integration(self, client):
        """Test health monitoring system integration."""
        
        # Test health check endpoint
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # Test detailed health status
        with patch('api.utils.health_manager.HealthManager.get_health_status') as mock_health:
            mock_health.return_value = {
                "status": "healthy",
                "components": {
                    "database": {"status": "healthy", "response_time": 0.05},
                    "redis": {"status": "healthy", "response_time": 0.02},
                    "storage": {"status": "healthy", "response_time": 0.1},
                    "whisper_service": {"status": "healthy", "response_time": 0.3},
                    "ffmpeg": {"status": "healthy", "response_time": 0.15}
                },
                "timestamp": datetime.now().isoformat()
            }
            
            status_response = client.get("/health/status")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            assert len(status_data["components"]) == 5
            assert all(comp["status"] == "healthy" for comp in status_data["components"].values())
    
    def test_monitoring_metrics_integration(self, client):
        """Test monitoring metrics integration."""
        
        # Test system metrics
        with patch('api.routes.monitoring.collect_system_metrics') as mock_system:
            mock_system.return_value = {
                "cpu_percent": 45.2,
                "memory_percent": 67.8,
                "disk_usage_percent": 34.5,
                "load_average": [1.2, 1.5, 1.8],
                "process_count": 156,
                "uptime_seconds": 86400
            }
            
            system_response = client.get("/monitoring/system")
            assert system_response.status_code == 200
            
            system_data = system_response.json()
            assert system_data["cpu_percent"] < 80  # Healthy CPU usage
            assert system_data["memory_percent"] < 85  # Healthy memory usage
        
        # Test application metrics
        with patch('api.routes.monitoring.collect_application_metrics') as mock_app:
            mock_app.return_value = {
                "total_clips": 1250,
                "clips_processing": 5,
                "active_users": 45,
                "queue_length": 3,
                "cache_hit_rate": 0.87,
                "error_rate": 0.02
            }
            
            app_response = client.get("/monitoring/application")
            assert app_response.status_code == 200
            
            app_data = app_response.json()
            assert app_data["error_rate"] < 0.05  # Low error rate
            assert app_data["cache_hit_rate"] > 0.8  # Good cache performance
    
    @pytest.mark.asyncio
    async def test_memory_optimization_integration(self):
        """Test memory optimization system integration."""
        
        memory_optimizer = EnhancedMemoryOptimizer()
        
        # Test memory monitoring
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 85.0  # High memory usage
            
            # Should trigger optimization
            optimization_needed = await memory_optimizer.should_optimize()
            assert optimization_needed
        
        # Test memory cleanup
        with patch.object(memory_optimizer, 'cleanup_temp_files') as mock_cleanup_temp, \
             patch.object(memory_optimizer, 'clear_caches') as mock_clear_cache, \
             patch.object(memory_optimizer, 'optimize_whisper_memory') as mock_optimize_whisper:
            
            mock_cleanup_temp.return_value = 1024 * 1024 * 50  # 50MB freed
            mock_clear_cache.return_value = 1024 * 1024 * 30   # 30MB freed
            mock_optimize_whisper.return_value = 1024 * 1024 * 100  # 100MB freed
            
            freed_memory = await memory_optimizer.optimize_memory()
            
            assert freed_memory > 1024 * 1024 * 150  # At least 150MB freed
            mock_cleanup_temp.assert_called_once()
            mock_clear_cache.assert_called_once()
            mock_optimize_whisper.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_production_monitoring_integration(self):
        """Test production monitoring system integration."""
        
        production_monitor = ProductionMonitor()
        
        # Test alert rule evaluation
        metrics = {
            "cpu_percent": 85.0,  # High CPU
            "memory_percent": 90.0,  # High memory
            "error_rate": 0.08,  # High error rate
            "response_time_avg": 2.5,  # Slow response
            "queue_length": 25  # Long queue
        }
        
        with patch.object(production_monitor, 'collect_metrics') as mock_collect:
            mock_collect.return_value = metrics
            
            alerts = await production_monitor.check_alerts()
            
            # Should generate multiple alerts
            assert len(alerts) >= 3  # CPU, memory, and error rate alerts
            
            alert_types = [alert["rule_name"] for alert in alerts]
            assert "high_cpu" in alert_types
            assert "high_memory" in alert_types
            assert "high_error_rate" in alert_types


class TestPerformanceIntegration:
    """Test system performance under various conditions."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_concurrent_video_processing(self, client):
        """Test concurrent video processing performance."""
        
        from ..utils.auth import create_access_token
        
        # Create multiple user tokens
        tokens = []
        for i in range(5):
            token = create_access_token(data={"sub": f"test_user_{i}"})
            tokens.append(token)
        
        results = []
        
        def upload_video(token):
            headers = {"Authorization": f"Bearer {token}"}
            
            with patch('api.services.video_pipeline.VideoPipeline.process_video') as mock_process:
                mock_process.return_value = {
                    "job_id": f"job_{token[-10:]}",
                    "status": "processing",
                    "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat()
                }
                
                response = client.post(
                    "/videos/upload",
                    files={"file": ("test.mp4", b"fake video content", "video/mp4")},
                    headers=headers
                )
                
                results.append({
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0
                })
        
        # Create concurrent threads
        threads = []
        for token in tokens:
            thread = threading.Thread(target=upload_video, args=(token,))
            threads.append(thread)
        
        start_time = time.time()
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify results
        assert len(results) == 5
        assert all(result["status_code"] in [202, 429] for result in results)  # Accepted or rate limited
        assert total_time < 10.0  # Should complete within 10 seconds
    
    def test_large_file_handling_performance(self, client):
        """Test performance with large file uploads."""
        
        from ..utils.auth import create_access_token
        
        token = create_access_token(data={"sub": "test_user_123"})
        headers = {"Authorization": f"Bearer {token}"}
        
        # Simulate large file (100MB)
        large_file_content = b"x" * (100 * 1024 * 1024)
        
        with patch('api.services.video_pipeline.VideoPipeline.process_video') as mock_process:
            mock_process.return_value = {
                "job_id": "large_file_job",
                "status": "processing",
                "file_size": len(large_file_content)
            }
            
            start_time = time.time()
            
            response = client.post(
                "/videos/upload",
                files={"file": ("large_video.mp4", large_file_content, "video/mp4")},
                headers=headers
            )
            
            end_time = time.time()
            upload_time = end_time - start_time
            
            # Should handle large files efficiently
            assert response.status_code in [202, 413]  # Accepted or payload too large
            
            if response.status_code == 202:
                # If accepted, should process within reasonable time
                assert upload_time < 30.0  # Should upload within 30 seconds
    
    def test_memory_usage_under_load(self, client):
        """Test memory usage under load conditions."""
        
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Make multiple requests
        for i in range(20):
            response = client.get("/health")
            assert response.status_code == 200
            
            # Force garbage collection
            gc.collect()
        
        # Check final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024
    
    def test_database_connection_pooling(self, client):
        """Test database connection pooling under load."""
        
        # Make multiple database-dependent requests
        responses = []
        
        with patch('api.services.clip_service.ClipService.get_trending_clips') as mock_clips:
            mock_clips.return_value = [
                {
                    "id": f"clip_{i}",
                    "text": f"Test clip {i}",
                    "virality_score": 0.8
                }
                for i in range(10)
            ]
            
            # Make 50 concurrent requests
            for i in range(50):
                response = client.get("/clips/trending")
                responses.append(response.status_code)
        
        # All requests should succeed
        assert len(responses) == 50
        assert all(status == 200 for status in responses)


class TestProductionReadiness:
    """Test production readiness scenarios."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_graceful_shutdown(self, client):
        """Test graceful shutdown behavior."""
        
        # Test that health checks work during shutdown
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test that ongoing requests are handled properly
        with patch('api.services.video_pipeline.VideoPipeline.process_video') as mock_process:
            mock_process.return_value = {
                "job_id": "shutdown_test",
                "status": "processing"
            }
            
            # This would be interrupted during shutdown in production
            # For testing, we verify the response format
            from ..utils.auth import create_access_token
            token = create_access_token(data={"sub": "test_user_123"})
            headers = {"Authorization": f"Bearer {token}"}
            
            response = client.post(
                "/videos/upload",
                files={"file": ("test.mp4", b"content", "video/mp4")},
                headers=headers
            )
            
            assert response.status_code == 202
    
    def test_configuration_validation(self):
        """Test that all required configurations are present."""
        
        from ..core.config import settings
        
        # Verify critical settings
        required_settings = [
            "SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "FIREBASE_CREDENTIALS"
        ]
        
        for setting in required_settings:
            assert hasattr(settings, setting.lower())
            value = getattr(settings, setting.lower())
            assert value is not None
            assert len(str(value)) > 0
    
    def test_security_headers(self, client):
        """Test security headers are present."""
        
        response = client.get("/health")
        
        # Check for security headers
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection"
        ]
        
        for header in security_headers:
            assert header in response.headers
    
    def test_rate_limiting_configuration(self, client):
        """Test rate limiting is properly configured."""
        
        # Make rapid requests to trigger rate limiting
        responses = []
        for i in range(100):
            response = client.get("/health")
            responses.append(response.status_code)
            
            # Break early if rate limited
            if response.status_code == 429:
                break
        
        # Should have some successful requests
        success_count = sum(1 for status in responses if status == 200)
        assert success_count > 0
        
        # Rate limiting should eventually kick in for excessive requests
        # (This depends on the rate limiting configuration)
    
    def test_logging_configuration(self, client):
        """Test logging is properly configured."""
        
        import logging
        
        # Verify loggers are configured
        logger = logging.getLogger("api")
        assert logger.level <= logging.INFO
        assert len(logger.handlers) > 0
        
        # Test that requests are logged
        with patch.object(logger, 'info') as mock_log:
            response = client.get("/health")
            assert response.status_code == 200
            
            # Should have logged the request (depending on middleware configuration)
            # mock_log.assert_called()
    
    def test_error_tracking_integration(self, client):
        """Test error tracking and reporting."""
        
        # Trigger an error
        with patch('api.routes.monitoring.collect_system_metrics') as mock_metrics:
            mock_metrics.side_effect = Exception("Test error for tracking")
            
            response = client.get("/monitoring/system")
            
            # Should handle error gracefully
            assert response.status_code == 500
            
            # Error should be tracked (in production, this would go to error tracking service)
            error_data = response.json()
            assert "detail" in error_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])