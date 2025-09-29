import pytest
import asyncio
import tempfile
import os
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import psutil
import time
from datetime import datetime, timedelta

from api.main import app
from api.models.video import Video, VideoStatus
from api.models.clip import GeneratedClip, ClipStatus
from api.models.user import User
from api.services.video_processor import VideoProcessor
from api.services.clip_service import ClipService
from api.core.database import get_db
from api.core.exceptions import (
    VideoProcessingError,
    FFmpegError,
    StorageError,
    AIServiceError,
    DatabaseError
)


class TestClipErrorRecovery:
    """Comprehensive error recovery testing for clip generation failures."""
    
    def setup_method(self):
        """Setup test environment and dependencies."""
        self.client = TestClient(app)
        self.test_user_id = "test_user_123"
        self.test_video_id = "test_video_456"
        
        # Mock authentication
        self.auth_headers = {"Authorization": "Bearer valid_token"}
        
        # Test data
        self.clip_request = {
            "video_id": self.test_video_id,
            "platform": "youtube",
            "max_clips": 3,
            "min_duration": 30,
            "max_duration": 60
        }
        
        self.mock_video = MagicMock(spec=Video)
        self.mock_video.id = self.test_video_id
        self.mock_video.user_id = self.test_user_id
        self.mock_video.file_path = "/test/video.mp4"
        self.mock_video.status = VideoStatus.PROCESSED
        
        self.mock_user = MagicMock(spec=User)
        self.mock_user.id = self.test_user_id
        self.mock_user.credits = 100
    
    def test_ffmpeg_not_found_error_recovery(self):
        """Test recovery when FFmpeg is not installed or not found."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments') as mock_segments:
            
            # Simulate FFmpeg not found
            mock_segments.side_effect = FFmpegError("FFmpeg not found in system PATH")
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 500
            error_data = response.json()
            assert "FFmpeg not found" in error_data["detail"]
            assert error_data["error_type"] == "ffmpeg_error"
            assert "recovery_suggestions" in error_data
    
    def test_corrupted_video_file_recovery(self):
        """Test recovery when video file is corrupted or unreadable."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments') as mock_segments:
            
            # Simulate corrupted video file
            mock_segments.side_effect = VideoProcessingError(
                "Video file is corrupted or unreadable",
                error_code="CORRUPTED_FILE"
            )
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 422
            error_data = response.json()
            assert "corrupted" in error_data["detail"].lower()
            assert error_data["error_code"] == "CORRUPTED_FILE"
    
    def test_insufficient_disk_space_recovery(self):
        """Test recovery when disk space is insufficient for processing."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('shutil.disk_usage') as mock_disk_usage:
            
            # Simulate insufficient disk space (less than 1GB)
            mock_disk_usage.return_value = (1000000000, 500000000, 100000000)  # total, used, free
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 507
            error_data = response.json()
            assert "insufficient disk space" in error_data["detail"].lower()
    
    def test_memory_exhaustion_recovery(self):
        """Test recovery when system runs out of memory during processing."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments') as mock_segments:
            
            # Simulate memory error
            mock_segments.side_effect = MemoryError("Unable to allocate memory for video processing")
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 507
            error_data = response.json()
            assert "memory" in error_data["detail"].lower()
            assert "retry_after" in error_data
    
    def test_ai_service_timeout_recovery(self):
        """Test recovery when AI service times out."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.unified_ai_service.UnifiedAIService.generate_clip_segments') as mock_ai:
            
            # Simulate AI service timeout
            mock_ai.side_effect = AIServiceError(
                "AI service request timed out after 30 seconds",
                error_code="TIMEOUT",
                retry_after=60
            )
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 504
            error_data = response.json()
            assert "timed out" in error_data["detail"].lower()
            assert error_data["retry_after"] == 60
    
    def test_ai_service_rate_limit_recovery(self):
        """Test recovery when AI service rate limit is exceeded."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.unified_ai_service.UnifiedAIService.generate_clip_segments') as mock_ai:
            
            # Simulate rate limit exceeded
            mock_ai.side_effect = AIServiceError(
                "Rate limit exceeded. Try again later.",
                error_code="RATE_LIMIT_EXCEEDED",
                retry_after=300
            )
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 429
            error_data = response.json()
            assert "rate limit" in error_data["detail"].lower()
            assert error_data["retry_after"] == 300
    
    def test_storage_service_failure_recovery(self):
        """Test recovery when storage service fails."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.storage_service.upload_clip') as mock_upload:
            
            # Simulate storage failure
            mock_upload.side_effect = StorageError(
                "Failed to upload clip to storage service",
                error_code="UPLOAD_FAILED"
            )
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 503
            error_data = response.json()
            assert "storage" in error_data["detail"].lower()
            assert error_data["error_code"] == "UPLOAD_FAILED"
    
    def test_database_connection_failure_recovery(self):
        """Test recovery when database connection fails."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.clip_service.create_clip') as mock_create:
            
            # Simulate database connection failure
            mock_create.side_effect = DatabaseError(
                "Database connection lost",
                error_code="CONNECTION_LOST"
            )
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 503
            error_data = response.json()
            assert "database" in error_data["detail"].lower()
            assert "retry_after" in error_data
    
    def test_partial_processing_failure_recovery(self):
        """Test recovery when processing partially completes then fails."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments') as mock_segments, \
             patch('api.services.clip_service.create_clip') as mock_create:
            
            # Simulate successful segment finding but failed clip creation
            mock_segments.return_value = [
                {"start_time": 10, "end_time": 40, "score": 0.9},
                {"start_time": 60, "end_time": 90, "score": 0.8}
            ]
            
            mock_create.side_effect = Exception("Unexpected error during clip creation")
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 500
            error_data = response.json()
            assert "unexpected error" in error_data["detail"].lower()
    
    def test_concurrent_processing_conflict_recovery(self):
        """Test recovery when multiple concurrent requests conflict."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.clip_service.is_video_being_processed') as mock_processing:
            
            # Simulate video already being processed
            mock_processing.return_value = True
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 409
            error_data = response.json()
            assert "already being processed" in error_data["detail"].lower()
            assert "retry_after" in error_data
    
    def test_cleanup_after_failure(self):
        """Test that temporary files are cleaned up after processing failure."""
        temp_files = []
        
        def mock_create_temp_file(*args, **kwargs):
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_files.append(temp_file.name)
            return temp_file
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('tempfile.NamedTemporaryFile', side_effect=mock_create_temp_file), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments') as mock_segments:
            
            # Simulate processing failure after temp files are created
            mock_segments.side_effect = Exception("Processing failed")
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 500
            
            # Verify temp files are cleaned up
            for temp_file in temp_files:
                assert not os.path.exists(temp_file), f"Temp file {temp_file} was not cleaned up"
    
    def test_retry_mechanism_with_exponential_backoff(self):
        """Test retry mechanism with exponential backoff for transient failures."""
        retry_count = 0
        
        def mock_ai_service_with_retries(*args, **kwargs):
            nonlocal retry_count
            retry_count += 1
            
            if retry_count < 3:
                raise AIServiceError("Temporary service unavailable", error_code="TEMPORARY_FAILURE")
            
            return [{"start_time": 10, "end_time": 40, "score": 0.9}]
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.unified_ai_service.UnifiedAIService.generate_clip_segments', side_effect=mock_ai_service_with_retries), \
             patch('time.sleep'):  # Mock sleep to speed up test
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            # Should succeed after retries
            assert response.status_code == 200
            assert retry_count == 3
    
    def test_circuit_breaker_pattern(self):
        """Test circuit breaker pattern for repeated failures."""
        failure_count = 0
        
        def mock_failing_service(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            raise AIServiceError("Service consistently failing", error_code="SERVICE_DOWN")
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.unified_ai_service.UnifiedAIService.generate_clip_segments', side_effect=mock_failing_service):
            
            # Make multiple requests to trigger circuit breaker
            for i in range(5):
                response = self.client.post(
                    "/api/clips/generate",
                    json=self.clip_request,
                    headers=self.auth_headers
                )
                
                if i < 3:
                    assert response.status_code == 503  # Service unavailable
                else:
                    assert response.status_code == 503  # Circuit breaker open
                    error_data = response.json()
                    assert "circuit breaker" in error_data["detail"].lower()
    
    def test_graceful_degradation_when_ai_unavailable(self):
        """Test graceful degradation when AI service is unavailable."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.unified_ai_service.UnifiedAIService.generate_clip_segments') as mock_ai, \
             patch('api.services.video_processor.VideoProcessor.find_best_segments_fallback') as mock_fallback:
            
            # AI service fails
            mock_ai.side_effect = AIServiceError("AI service unavailable", error_code="SERVICE_DOWN")
            
            # Fallback method succeeds
            mock_fallback.return_value = [
                {"start_time": 10, "end_time": 40, "score": 0.7},
                {"start_time": 60, "end_time": 90, "score": 0.6}
            ]
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            response_data = response.json()
            assert "fallback_mode" in response_data
            assert response_data["fallback_mode"] is True
    
    def test_error_notification_and_logging(self):
        """Test that errors are properly logged and notifications sent."""
        with patch('api.services.user_service.get_user_by_id', return_value=self.mock_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.mock_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments') as mock_segments, \
             patch('api.core.logging.logger.error') as mock_logger, \
             patch('api.services.notification_service.send_error_notification') as mock_notify:
            
            # Simulate critical error
            mock_segments.side_effect = Exception("Critical processing error")
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 500
            
            # Verify error logging
            mock_logger.assert_called()
            
            # Verify error notification
            mock_notify.assert_called_once()
    
    def test_health_check_after_recovery(self):
        """Test system health check after error recovery."""
        with patch('api.services.health_service.check_system_health') as mock_health:
            mock_health.return_value = {
                "status": "healthy",
                "services": {
                    "database": "healthy",
                    "storage": "healthy",
                    "ai_service": "healthy",
                    "ffmpeg": "healthy"
                }
            }
            
            response = self.client.get("/api/health")
            
            assert response.status_code == 200
            health_data = response.json()
            assert health_data["status"] == "healthy"
            assert all(service == "healthy" for service in health_data["services"].values())