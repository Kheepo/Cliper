import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from api.main import app
from api.tasks import generate_clips_task, _generate_single_clip, _validate_clip_generation_input, cleanup_job_resources
import subprocess
import json
from pathlib import Path


class TestClipErrorScenarios:
    """Comprehensive error scenario testing for clip generation."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture
    def invalid_video_data(self):
        """Mock invalid video data."""
        return {
            "id": "invalid_video",
            "title": "Invalid Video",
            "file_path": "/nonexistent/video.mp4",
            "duration": 0,
            "status": "error",
            "user_id": "user_test"
        }
    
    # Input Validation Error Tests
    
    def test_invalid_video_format_error(self, client, auth_headers):
        """Test error handling for invalid video formats."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/invalid.txt",  # Invalid format
                "status": "analyzed",
                "user_id": "user_test"
            }
            mock_supabase.get_user_by_id.return_value = {"id": "user_test", "credits_remaining": 100}
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "format" in data["error"].lower() or "invalid" in data["error"].lower()
    
    def test_missing_required_fields_error(self, client, auth_headers):
        """Test error handling for missing required fields."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/test.mp4",
                "status": "analyzed",
                "user_id": "user_test"
            }
            
            # Test missing platform
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 422  # Validation error
            
            # Test missing clip_type
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 422
    
    def test_invalid_time_ranges_error(self):
        """Test error handling for invalid time ranges."""
        
        # Test start time after end time
        with pytest.raises(ValueError, match="start_time must be less than end_time"):
            _validate_clip_generation_input(
                clip_id="test_clip",
                generation_options={
                    "platform": "youtube",
                    "clip_type": "manual",
                    "manual_segments": [{
                        "start_time": 60.0,
                        "end_time": 30.0  # Invalid: end before start
                    }]
                }
            )
        
        # Test negative time values
        with pytest.raises(ValueError, match="Time values must be non-negative"):
            _validate_clip_generation_input(
                clip_id="test_clip",
                generation_options={
                    "platform": "youtube",
                    "clip_type": "manual",
                    "manual_segments": [{
                        "start_time": -10.0,  # Invalid: negative time
                        "end_time": 30.0
                    }]
                }
            )
    
    def test_invalid_platform_configuration_error(self):
        """Test error handling for invalid platform configurations."""
        
        with pytest.raises(ValueError, match="Unsupported platform"):
            _validate_clip_generation_input(
                clip_id="test_clip",
                generation_options={
                    "platform": "invalid_platform",  # Invalid platform
                    "clip_type": "highlight",
                    "target_duration": 30.0
                }
            )
    
    # Network and External Service Error Tests
    
    @pytest.mark.asyncio
    async def test_ffmpeg_not_found_error(self):
        """Test error handling when FFmpeg is not available."""
        
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            temp_file.flush()
            video_path = temp_file.name
        
        try:
            with patch('subprocess.Popen') as mock_popen:
                # Simulate FFmpeg not found
                mock_popen.side_effect = FileNotFoundError("FFmpeg not found")
                
                with pytest.raises(FileNotFoundError):
                    await _generate_single_clip(
                        video_path=video_path,
                        output_path="/tmp/test_clip.mp4",
                        segment={
                            'start_time': 10.0,
                            'duration': 30.0
                        },
                        platform_config={
                            "aspect_ratio": "16:9",
                            "audio_codec": "aac",
                            "audio_bitrate": "128k"
                        }
                    )
        finally:
            os.unlink(video_path)
    
    @pytest.mark.asyncio
    async def test_ffmpeg_processing_error(self):
        """Test error handling for FFmpeg processing failures."""
        
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            temp_file.flush()
            video_path = temp_file.name
        
        try:
            with patch('subprocess.Popen') as mock_popen:
                # Mock FFmpeg process that fails
                mock_process = Mock()
                mock_process.communicate.return_value = (b'', b'FFmpeg error: Invalid input')
                mock_process.returncode = 1  # Error exit code
                mock_process.poll.return_value = 1
                mock_popen.return_value = mock_process
                
                with pytest.raises(subprocess.CalledProcessError):
                    await _generate_single_clip(
                        video_path=video_path,
                        output_path="/tmp/test_clip.mp4",
                        segment={
                            'start_time': 10.0,
                            'duration': 30.0
                        },
                        platform_config={
                            "aspect_ratio": "16:9",
                            "audio_codec": "aac",
                            "audio_bitrate": "128k"
                        }
                    )
        finally:
            os.unlink(video_path)
    
    def test_database_connection_error(self, client, auth_headers):
        """Test error handling for database connection failures."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            # Simulate database connection error
            mock_supabase.get_video_by_id.side_effect = Exception("Database connection failed")
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "error" in data
    
    def test_external_api_timeout_error(self, client, auth_headers):
        """Test error handling for external API timeouts."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/test.mp4",
                "status": "analyzed",
                "user_id": "user_test"
            }
            mock_supabase.get_user_by_id.return_value = {"id": "user_test", "credits_remaining": 100}
            
            # Simulate task queue timeout
            mock_task.side_effect = TimeoutError("Task queue timeout")
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "timeout" in data["error"].lower() or "error" in data
    
    # File System Error Tests
    
    @pytest.mark.asyncio
    async def test_insufficient_disk_space_error(self):
        """Test error handling for insufficient disk space."""
        
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            temp_file.flush()
            video_path = temp_file.name
        
        try:
            with patch('subprocess.Popen') as mock_popen, \
                 patch('os.path.exists', return_value=False):  # Output file not created
                
                # Mock FFmpeg process that appears successful but doesn't create output
                mock_process = Mock()
                mock_process.communicate.return_value = (b'', b'No space left on device')
                mock_process.returncode = 0  # FFmpeg exits successfully
                mock_process.poll.return_value = 0
                mock_popen.return_value = mock_process
                
                with pytest.raises(FileNotFoundError, match="Output file was not created"):
                    await _generate_single_clip(
                        video_path=video_path,
                        output_path="/tmp/test_clip.mp4",
                        segment={
                            'start_time': 10.0,
                            'duration': 30.0
                        },
                        platform_config={
                            "aspect_ratio": "16:9",
                            "audio_codec": "aac",
                            "audio_bitrate": "128k"
                        }
                    )
        finally:
            os.unlink(video_path)
    
    @pytest.mark.asyncio
    async def test_file_permission_error(self):
        """Test error handling for file permission issues."""
        
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            temp_file.flush()
            video_path = temp_file.name
        
        try:
            with patch('subprocess.Popen') as mock_popen:
                # Simulate permission denied error
                mock_popen.side_effect = PermissionError("Permission denied")
                
                with pytest.raises(PermissionError):
                    await _generate_single_clip(
                        video_path=video_path,
                        output_path="/readonly/test_clip.mp4",  # Read-only location
                        segment={
                            'start_time': 10.0,
                            'duration': 30.0
                        },
                        platform_config={
                            "aspect_ratio": "16:9",
                            "audio_codec": "aac",
                            "audio_bitrate": "128k"
                        }
                    )
        finally:
            os.unlink(video_path)
    
    def test_corrupted_video_file_error(self, client, auth_headers):
        """Test error handling for corrupted video files."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/corrupted.mp4",
                "status": "analyzed",
                "user_id": "user_test"
            }
            mock_supabase.get_user_by_id.return_value = {"id": "user_test", "credits_remaining": 100}
            
            # Mock task that fails due to corrupted video
            mock_task_result = Mock()
            mock_task_result.get.side_effect = Exception("Corrupted video file")
            mock_task.return_value = mock_task_result
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            # Should still return 200 with job_id, error will be in job status
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
    
    # Processing Timeout Error Tests
    
    @pytest.mark.asyncio
    async def test_processing_timeout_error(self):
        """Test error handling for processing timeouts."""
        
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            temp_file.flush()
            video_path = temp_file.name
        
        try:
            with patch('subprocess.Popen') as mock_popen:
                # Mock process that hangs
                mock_process = Mock()
                mock_process.poll.return_value = None  # Still running
                mock_process.communicate.side_effect = asyncio.TimeoutError("Process timeout")
                mock_popen.return_value = mock_process
                
                with pytest.raises(asyncio.TimeoutError):
                    await _generate_single_clip(
                        video_path=video_path,
                        output_path="/tmp/test_clip.mp4",
                        segment={
                            'start_time': 10.0,
                            'duration': 30.0
                        },
                        platform_config={
                            "aspect_ratio": "16:9",
                            "audio_codec": "aac",
                            "audio_bitrate": "128k"
                        }
                    )
        finally:
            os.unlink(video_path)
    
    # Authentication and Authorization Error Tests
    
    def test_unauthorized_access_error(self, client):
        """Test error handling for unauthorized access."""
        
        # Request without authentication headers
        response = client.post(
            "/api/videos/video_test/generate-clips",
            json={
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            }
        )
        
        assert response.status_code == 401
    
    def test_insufficient_credits_error(self, client, auth_headers):
        """Test error handling for insufficient user credits."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/test.mp4",
                "status": "analyzed",
                "user_id": "user_test"
            }
            # User with insufficient credits
            mock_supabase.get_user_by_id.return_value = {
                "id": "user_test",
                "credits_remaining": 0  # No credits
            }
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 402  # Payment required
            data = response.json()
            assert "credits" in data["error"].lower()
    
    def test_video_access_permission_error(self, client, auth_headers):
        """Test error handling when user doesn't own the video."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/test.mp4",
                "status": "analyzed",
                "user_id": "different_user"  # Different user owns the video
            }
            mock_supabase.get_user_by_id.return_value = {
                "id": "user_test",
                "credits_remaining": 100
            }
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 403  # Forbidden
            data = response.json()
            assert "permission" in data["error"].lower() or "access" in data["error"].lower()
    
    # Resource Limit Error Tests
    
    def test_max_clips_limit_error(self, client, auth_headers):
        """Test error handling for exceeding maximum clips limit."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/test.mp4",
                "status": "analyzed",
                "user_id": "user_test"
            }
            mock_supabase.get_user_by_id.return_value = {
                "id": "user_test",
                "credits_remaining": 100
            }
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0,
                    "max_clips": 1000  # Excessive number
                },
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "limit" in data["error"].lower() or "maximum" in data["error"].lower()
    
    def test_video_too_long_error(self, client, auth_headers):
        """Test error handling for videos that are too long."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/very_long_video.mp4",
                "duration": 7200.0,  # 2 hours - too long
                "status": "analyzed",
                "user_id": "user_test"
            }
            mock_supabase.get_user_by_id.return_value = {
                "id": "user_test",
                "credits_remaining": 100
            }
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "duration" in data["error"].lower() or "long" in data["error"].lower()
    
    # Concurrent Processing Error Tests
    
    def test_concurrent_generation_conflict_error(self, client, auth_headers):
        """Test error handling for concurrent generation conflicts."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = {
                "id": "video_test",
                "file_path": "/videos/test.mp4",
                "status": "processing",  # Already being processed
                "user_id": "user_test"
            }
            mock_supabase.get_user_by_id.return_value = {
                "id": "user_test",
                "credits_remaining": 100
            }
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 409  # Conflict
            data = response.json()
            assert "processing" in data["error"].lower() or "conflict" in data["error"].lower()
    
    # Recovery and Retry Error Tests
    
    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self):
        """Test recovery from partial failures during clip generation."""
        
        with patch('api.tasks._generate_single_clip') as mock_generate:
            # Mock partial failure - some clips succeed, some fail
            call_count = 0
            
            async def mock_clip_generation(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                if call_count <= 2:
                    # First two calls succeed
                    return {
                        "file_path": f"/tmp/clip_{call_count}.mp4",
                        "thumbnail_path": f"/tmp/thumb_{call_count}.jpg",
                        "duration": 30.0,
                        "file_size": 1024000
                    }
                else:
                    # Third call fails
                    raise subprocess.CalledProcessError(1, "ffmpeg", "Processing failed")
            
            mock_generate.side_effect = mock_clip_generation
            
            # Test that the system handles partial failures gracefully
            with patch('api.tasks.supabase_service') as mock_supabase, \
                 patch('api.services.unified_llm_service') as mock_llm:
                
                mock_supabase.get_video_by_id.return_value = {
                    "id": "video_test",
                    "file_path": "/videos/test.mp4",
                    "duration": 300.0
                }
                
                mock_llm.analyze_video_for_clips.return_value = {
                    "segments": [
                        {"start_time": 10, "end_time": 40, "virality_score": 0.9},
                        {"start_time": 50, "end_time": 80, "virality_score": 0.8},
                        {"start_time": 90, "end_time": 120, "virality_score": 0.7}
                    ]
                }
                
                result = await generate_clips_task(
                    video_id="video_test",
                    generation_options={
                        "platform": "youtube",
                        "clip_type": "highlight",
                        "target_duration": 30.0,
                        "max_clips": 3
                    }
                )
                
                # Should return partial success
                assert result["status"] == "partial_success"
                assert result["successful_clips"] == 2
                assert result["failed_clips"] == 1
                assert len(result["clips"]) == 2
                assert len(result["errors"]) == 1
    
    def test_error_message_formatting(self, client, auth_headers):
        """Test that error messages are properly formatted and informative."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            # Test various error scenarios and verify message format
            
            # Video not found
            mock_supabase.get_video_by_id.return_value = None
            
            response = client.post(
                "/api/videos/nonexistent/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 404
            data = response.json()
            assert "error" in data
            assert isinstance(data["error"], str)
            assert len(data["error"]) > 0
            assert "video" in data["error"].lower()
            assert "not found" in data["error"].lower()
    
    def test_error_logging_and_tracking(self, client, auth_headers):
        """Test that errors are properly logged and tracked."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.logger') as mock_logger:
            
            mock_supabase.get_video_by_id.side_effect = Exception("Database error")
            
            response = client.post(
                "/api/videos/video_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            # Verify error was logged
            assert mock_logger.error.called
            
            # Verify response format
            assert response.status_code == 500
            data = response.json()
            assert "error" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])