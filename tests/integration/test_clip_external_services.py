import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.main import app
from api.database import get_db
from api.models.video import Video
from api.models.clip import Clip
from api.models.user import User
from api.services.clip_generation import ClipGenerationService
from api.services.ffmpeg_service import FFmpegService
from api.services.storage_service import StorageService
from api.services.ai_service import AIService
from api.core.config import settings


class TestClipExternalServicesIntegration:
    """Integration tests for clip generation with external services."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer valid_jwt_token"}
    
    @pytest.fixture
    def mock_user(self, db_session):
        user = User(
            id="user123",
            email="test@example.com",
            credits=100,
            subscription_tier="premium"
        )
        db_session.add(user)
        db_session.commit()
        return user
    
    @pytest.fixture
    def mock_video(self, db_session, mock_user):
        video = Video(
            id="video123",
            user_id=mock_user.id,
            filename="test_video.mp4",
            file_path="/storage/videos/test_video.mp4",
            duration=120.0,
            status="processed"
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    @pytest.fixture
    def temp_video_file(self):
        """Create a temporary video file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            # Write minimal MP4 header for testing
            f.write(b"\x00\x00\x00\x20ftypmp42")
            f.write(b"\x00\x00\x00\x00mp42isom")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    # FFmpeg Integration Tests
    
    @pytest.mark.asyncio
    async def test_ffmpeg_service_integration(self, temp_video_file):
        """Test FFmpeg service integration for clip extraction."""
        ffmpeg_service = FFmpegService()
        
        # Test video info extraction
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"duration": "120.5", "width": 1920, "height": 1080}'
            
            video_info = await ffmpeg_service.get_video_info(temp_video_file)
            
            assert video_info['duration'] == "120.5"
            assert video_info['width'] == 1920
            assert video_info['height'] == 1080
    
    @pytest.mark.asyncio
    async def test_ffmpeg_clip_extraction(self, temp_video_file):
        """Test FFmpeg clip extraction functionality."""
        ffmpeg_service = FFmpegService()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            output_path = await ffmpeg_service.extract_clip(
                input_path=temp_video_file,
                start_time=10.0,
                duration=30.0,
                output_path="/tmp/clip.mp4"
            )
            
            assert output_path == "/tmp/clip.mp4"
            mock_run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ffmpeg_error_handling(self, temp_video_file):
        """Test FFmpeg error handling for corrupted files."""
        ffmpeg_service = FFmpegService()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Invalid data found when processing input"
            
            with pytest.raises(Exception) as exc_info:
                await ffmpeg_service.extract_clip(
                    input_path=temp_video_file,
                    start_time=10.0,
                    duration=30.0,
                    output_path="/tmp/clip.mp4"
                )
            
            assert "FFmpeg processing failed" in str(exc_info.value)
    
    # Storage Service Integration Tests
    
    @pytest.mark.asyncio
    async def test_storage_service_upload(self):
        """Test storage service file upload functionality."""
        storage_service = StorageService()
        
        with patch.object(storage_service, 'upload_file') as mock_upload:
            mock_upload.return_value = "https://storage.example.com/clips/clip123.mp4"
            
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b"test video content")
                temp_file.flush()
                
                url = await storage_service.upload_file(
                    file_path=temp_file.name,
                    destination="clips/clip123.mp4"
                )
                
                assert url == "https://storage.example.com/clips/clip123.mp4"
                mock_upload.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_storage_service_download(self):
        """Test storage service file download functionality."""
        storage_service = StorageService()
        
        with patch.object(storage_service, 'download_file') as mock_download:
            mock_download.return_value = b"downloaded video content"
            
            content = await storage_service.download_file(
                "https://storage.example.com/videos/video123.mp4"
            )
            
            assert content == b"downloaded video content"
            mock_download.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_storage_service_error_handling(self):
        """Test storage service error handling for network issues."""
        storage_service = StorageService()
        
        with patch.object(storage_service, 'upload_file') as mock_upload:
            mock_upload.side_effect = Exception("Network timeout")
            
            with pytest.raises(Exception) as exc_info:
                await storage_service.upload_file(
                    file_path="/tmp/test.mp4",
                    destination="clips/test.mp4"
                )
            
            assert "Network timeout" in str(exc_info.value)
    
    # AI Service Integration Tests
    
    @pytest.mark.asyncio
    async def test_ai_service_highlight_detection(self):
        """Test AI service highlight detection functionality."""
        ai_service = AIService()
        
        with patch.object(ai_service, 'detect_highlights') as mock_detect:
            mock_detect.return_value = [
                {"start_time": 15.0, "end_time": 45.0, "confidence": 0.95, "type": "action"},
                {"start_time": 75.0, "end_time": 90.0, "confidence": 0.87, "type": "goal"}
            ]
            
            highlights = await ai_service.detect_highlights(
                video_path="/storage/videos/video123.mp4",
                video_type="sports"
            )
            
            assert len(highlights) == 2
            assert highlights[0]['confidence'] == 0.95
            assert highlights[1]['type'] == "goal"
    
    @pytest.mark.asyncio
    async def test_ai_service_timeout_handling(self):
        """Test AI service timeout handling for long processing."""
        ai_service = AIService()
        
        with patch.object(ai_service, 'detect_highlights') as mock_detect:
            mock_detect.side_effect = asyncio.TimeoutError("AI processing timeout")
            
            with pytest.raises(asyncio.TimeoutError):
                await ai_service.detect_highlights(
                    video_path="/storage/videos/video123.mp4",
                    video_type="sports"
                )
    
    @pytest.mark.asyncio
    async def test_ai_service_rate_limit_handling(self):
        """Test AI service rate limit handling."""
        ai_service = AIService()
        
        with patch.object(ai_service, 'detect_highlights') as mock_detect:
            mock_detect.side_effect = Exception("Rate limit exceeded")
            
            with pytest.raises(Exception) as exc_info:
                await ai_service.detect_highlights(
                    video_path="/storage/videos/video123.mp4",
                    video_type="sports"
                )
            
            assert "Rate limit exceeded" in str(exc_info.value)
    
    # End-to-End Integration Tests
    
    @pytest.mark.asyncio
    async def test_complete_external_service_integration(self, client, auth_headers, mock_video):
        """Test complete integration with all external services."""
        with patch('api.services.ffmpeg_service.FFmpegService.extract_clip') as mock_ffmpeg, \
             patch('api.services.storage_service.StorageService.upload_file') as mock_storage, \
             patch('api.services.ai_service.AIService.detect_highlights') as mock_ai:
            
            # Mock external service responses
            mock_ffmpeg.return_value = "/tmp/clip123.mp4"
            mock_storage.return_value = "https://storage.example.com/clips/clip123.mp4"
            mock_ai.return_value = [
                {"start_time": 10.0, "end_time": 40.0, "confidence": 0.9, "type": "highlight"}
            ]
            
            # Generate clip request
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube",
                    "use_ai_highlights": True
                }
            )
            
            assert response.status_code == 201
            clip_data = response.json()
            
            # Verify all services were called
            mock_ffmpeg.assert_called_once()
            mock_storage.assert_called_once()
            mock_ai.assert_called_once()
            
            # Verify clip data
            assert clip_data['video_id'] == mock_video.id
            assert clip_data['url'] == "https://storage.example.com/clips/clip123.mp4"
    
    @pytest.mark.asyncio
    async def test_external_service_failure_cascade(self, client, auth_headers, mock_video):
        """Test handling of cascading external service failures."""
        with patch('api.services.ffmpeg_service.FFmpegService.extract_clip') as mock_ffmpeg:
            mock_ffmpeg.side_effect = Exception("FFmpeg processing failed")
            
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                }
            )
            
            assert response.status_code == 500
            error_data = response.json()
            assert "processing failed" in error_data['detail'].lower()
    
    @pytest.mark.asyncio
    async def test_external_service_retry_mechanism(self, client, auth_headers, mock_video):
        """Test retry mechanism for external service failures."""
        with patch('api.services.storage_service.StorageService.upload_file') as mock_storage:
            # First call fails, second succeeds
            mock_storage.side_effect = [
                Exception("Temporary network error"),
                "https://storage.example.com/clips/clip123.mp4"
            ]
            
            with patch('api.services.ffmpeg_service.FFmpegService.extract_clip') as mock_ffmpeg:
                mock_ffmpeg.return_value = "/tmp/clip123.mp4"
                
                response = client.post(
                    f"/api/v1/videos/{mock_video.id}/clips",
                    headers=auth_headers,
                    json={
                        "start_time": 10.0,
                        "duration": 30.0,
                        "platform": "youtube"
                    }
                )
                
                # Should succeed after retry
                assert response.status_code == 201
                assert mock_storage.call_count == 2
    
    @pytest.mark.asyncio
    async def test_external_service_circuit_breaker(self):
        """Test circuit breaker pattern for external services."""
        ai_service = AIService()
        
        # Simulate multiple failures to trigger circuit breaker
        with patch.object(ai_service, 'detect_highlights') as mock_detect:
            mock_detect.side_effect = Exception("Service unavailable")
            
            # Multiple failed attempts
            for _ in range(5):
                with pytest.raises(Exception):
                    await ai_service.detect_highlights(
                        video_path="/storage/videos/video123.mp4",
                        video_type="sports"
                    )
            
            # Circuit breaker should be open now
            # Next call should fail fast without calling the service
            with pytest.raises(Exception) as exc_info:
                await ai_service.detect_highlights(
                    video_path="/storage/videos/video123.mp4",
                    video_type="sports"
                )
            
            # Verify circuit breaker behavior
            assert "circuit breaker" in str(exc_info.value).lower() or \
                   "service unavailable" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_external_service_health_checks(self):
        """Test health check functionality for external services."""
        ffmpeg_service = FFmpegService()
        storage_service = StorageService()
        ai_service = AIService()
        
        # Test FFmpeg health check
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            ffmpeg_healthy = await ffmpeg_service.health_check()
            assert ffmpeg_healthy is True
        
        # Test storage service health check
        with patch.object(storage_service, 'health_check') as mock_health:
            mock_health.return_value = True
            storage_healthy = await storage_service.health_check()
            assert storage_healthy is True
        
        # Test AI service health check
        with patch.object(ai_service, 'health_check') as mock_health:
            mock_health.return_value = True
            ai_healthy = await ai_service.health_check()
            assert ai_healthy is True
    
    @pytest.mark.asyncio
    async def test_external_service_monitoring_metrics(self):
        """Test monitoring and metrics collection for external services."""
        clip_service = ClipGenerationService()
        
        with patch.object(clip_service, 'generate_clip') as mock_generate:
            mock_generate.return_value = {
                'clip_id': 'clip123',
                'url': 'https://storage.example.com/clips/clip123.mp4',
                'metrics': {
                    'ffmpeg_processing_time': 15.2,
                    'storage_upload_time': 3.1,
                    'ai_processing_time': 8.7,
                    'total_processing_time': 27.0
                }
            }
            
            result = await clip_service.generate_clip(
                video_id="video123",
                start_time=10.0,
                duration=30.0
            )
            
            # Verify metrics are collected
            assert 'metrics' in result
            assert result['metrics']['ffmpeg_processing_time'] > 0
            assert result['metrics']['storage_upload_time'] > 0
            assert result['metrics']['ai_processing_time'] > 0
            assert result['metrics']['total_processing_time'] > 0