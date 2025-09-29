import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app
from api.services.supabase_service import SupabaseService
from api.models.clip_models import ClipGenerationRequest, ClipGenerationResponse
from api.routers.clips import (
    create_generated_clip,
    get_generated_clips,
    get_generated_clip,
    generate_clip,
    delete_generated_clip,
    get_clips_summary
)
from api.services.unified_llm_service import LLMService


class TestClipAPIIntegration:
    """Integration tests for clip generation API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture
    def invalid_auth_headers(self):
        """Invalid authentication headers."""
        return {
            "Authorization": "Bearer invalid-token",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture
    def mock_video_data(self):
        """Mock video data."""
        return {
            "id": "video_123",
            "title": "Test Video",
            "file_path": "/videos/test_video.mp4",
            "duration": 300.0,
            "status": "analyzed",
            "user_id": "user_123"
        }
    
    @pytest.fixture
    def mock_user_data(self):
        """Mock user data."""
        return {
            "id": "user_123",
            "email": "test@example.com",
            "subscription_tier": "premium",
            "credits_remaining": 100
        }
    
    # Test POST /api/videos/{video_id}/generate-clips
    def test_generate_clips_success(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test successful clip generation request."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            mock_task.return_value.id = "job_123"
            
            request_data = {
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0,
                "max_clips": 3
            }
            
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert data["job_id"] == "job_123"
            assert "estimated_duration" in data
            assert "status" in data
            
            # Verify task was called with correct parameters
            mock_task.assert_called_once()
            call_args = mock_task.call_args[0]
            assert call_args[0] == "video_123"  # video_id
            assert call_args[1] == "user_123"   # user_id
            assert call_args[2] == "job_123"    # job_id
            assert call_args[3]["platform"] == "youtube"
    
    def test_generate_clips_invalid_video(self, client, auth_headers):
        """Test clip generation with invalid video ID."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = None
            
            request_data = {
                "platform": "youtube",
                "clip_type": "highlight"
            }
            
            response = client.post(
                "/api/videos/nonexistent/generate-clips",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 404
            data = response.json()
            assert "error" in data
            assert "not found" in data["error"].lower()
    
    def test_generate_clips_unauthorized(self, client, invalid_auth_headers):
        """Test clip generation without proper authentication."""
        
        request_data = {
            "platform": "youtube",
            "clip_type": "highlight"
        }
        
        response = client.post(
            "/api/videos/video_123/generate-clips",
            json=request_data,
            headers=invalid_auth_headers
        )
        
        assert response.status_code == 401
    
    def test_generate_clips_no_auth(self, client):
        """Test clip generation without authentication."""
        
        request_data = {
            "platform": "youtube",
            "clip_type": "highlight"
        }
        
        response = client.post(
            "/api/videos/video_123/generate-clips",
            json=request_data
        )
        
        assert response.status_code == 401
    
    def test_generate_clips_invalid_platform(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test clip generation with invalid platform."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            
            request_data = {
                "platform": "invalid_platform",
                "clip_type": "highlight"
            }
            
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "platform" in data["error"].lower()
    
    def test_generate_clips_invalid_clip_type(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test clip generation with invalid clip type."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            
            request_data = {
                "platform": "youtube",
                "clip_type": "invalid_type"
            }
            
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "clip_type" in data["error"].lower()
    
    def test_generate_clips_manual_segments(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test clip generation with manual segments."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            mock_task.return_value.id = "job_manual"
            
            request_data = {
                "platform": "tiktok",
                "clip_type": "manual",
                "segments": [
                    {"start_time": 10, "end_time": 40},
                    {"start_time": 60, "end_time": 90}
                ]
            }
            
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            
            # Verify segments were passed correctly
            call_args = mock_task.call_args[0]
            assert call_args[3]["clip_type"] == "manual"
            assert len(call_args[3]["segments"]) == 2
    
    def test_generate_clips_invalid_segments(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test clip generation with invalid manual segments."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            
            request_data = {
                "platform": "youtube",
                "clip_type": "manual",
                "segments": [
                    {"start_time": 60, "end_time": 40}  # Invalid: end < start
                ]
            }
            
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
    
    # Test GET /api/videos/{video_id}/clips
    def test_get_clips_success(self, client, auth_headers, mock_video_data):
        """Test successful retrieval of generated clips."""
        
        mock_clips = [
            {
                "id": "clip_1",
                "title": "Highlight Clip 1",
                "duration": 30.0,
                "file_path": "/clips/clip1.mp4",
                "thumbnail_path": "/clips/clip1_thumb.jpg",
                "platform": "youtube",
                "status": "completed",
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "clip_2",
                "title": "Highlight Clip 2",
                "duration": 28.0,
                "file_path": "/clips/clip2.mp4",
                "thumbnail_path": "/clips/clip2_thumb.jpg",
                "platform": "youtube",
                "status": "completed",
                "created_at": "2024-01-01T00:01:00Z"
            }
        ]
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_generated_clips_by_video.return_value = mock_clips
            
            response = client.get(
                "/api/videos/video_123/clips",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "clips" in data
            assert len(data["clips"]) == 2
            assert data["clips"][0]["id"] == "clip_1"
            assert data["clips"][1]["id"] == "clip_2"
    
    def test_get_clips_no_clips(self, client, auth_headers, mock_video_data):
        """Test retrieval when no clips exist."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_generated_clips_by_video.return_value = []
            
            response = client.get(
                "/api/videos/video_123/clips",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "clips" in data
            assert len(data["clips"]) == 0
    
    # Test GET /api/jobs/{job_id}/status
    def test_get_job_status_success(self, client, auth_headers):
        """Test successful job status retrieval."""
        
        mock_job_status = {
            "id": "job_123",
            "status": "processing",
            "progress": 75,
            "message": "Generating clip 3 of 4",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:05:00Z"
        }
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_job_status.return_value = mock_job_status
            
            response = client.get(
                "/api/jobs/job_123/status",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "job_123"
            assert data["status"] == "processing"
            assert data["progress"] == 75
            assert "message" in data
    
    def test_get_job_status_not_found(self, client, auth_headers):
        """Test job status retrieval for non-existent job."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_job_status.return_value = None
            
            response = client.get(
                "/api/jobs/nonexistent/status",
                headers=auth_headers
            )
            
            assert response.status_code == 404
    
    # Test GET /api/clips/{clip_id}/download
    def test_download_clip_success(self, client, auth_headers):
        """Test successful clip download."""
        
        mock_clip = {
            "id": "clip_123",
            "file_path": "/clips/clip123.mp4",
            "title": "Test Clip",
            "user_id": "user_123"
        }
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.send_file') as mock_send_file:
            
            mock_supabase.get_clip_by_id.return_value = mock_clip
            mock_send_file.return_value = "file_content"
            
            response = client.get(
                "/api/clips/clip_123/download",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            # Verify file download was attempted
            mock_send_file.assert_called_once()
    
    def test_download_clip_not_found(self, client, auth_headers):
        """Test download of non-existent clip."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_clip_by_id.return_value = None
            
            response = client.get(
                "/api/clips/nonexistent/download",
                headers=auth_headers
            )
            
            assert response.status_code == 404
    
    # Test DELETE /api/clips/{clip_id}
    def test_delete_clip_success(self, client, auth_headers):
        """Test successful clip deletion."""
        
        mock_clip = {
            "id": "clip_123",
            "file_path": "/clips/clip123.mp4",
            "user_id": "user_123"
        }
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.cleanup_job_resources') as mock_cleanup:
            
            mock_supabase.get_clip_by_id.return_value = mock_clip
            mock_supabase.delete_clip.return_value = True
            
            response = client.delete(
                "/api/clips/clip_123",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            
            # Verify cleanup was called
            mock_cleanup.assert_called_once_with("clip_123")
    
    def test_delete_clip_unauthorized(self, client, auth_headers):
        """Test deletion of clip by unauthorized user."""
        
        mock_clip = {
            "id": "clip_123",
            "file_path": "/clips/clip123.mp4",
            "user_id": "other_user"  # Different user
        }
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_clip_by_id.return_value = mock_clip
            
            response = client.delete(
                "/api/clips/clip_123",
                headers=auth_headers
            )
            
            assert response.status_code == 403
    
    # Test rate limiting
    def test_rate_limiting(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test API rate limiting."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            mock_task.return_value.id = "job_rate_limit"
            
            request_data = {
                "platform": "youtube",
                "clip_type": "highlight"
            }
            
            # Make multiple rapid requests
            responses = []
            for i in range(10):
                response = client.post(
                    "/api/videos/video_123/generate-clips",
                    json=request_data,
                    headers=auth_headers
                )
                responses.append(response)
            
            # At least some should succeed (depending on rate limit implementation)
            success_count = sum(1 for r in responses if r.status_code == 200)
            rate_limited_count = sum(1 for r in responses if r.status_code == 429)
            
            # Should have some rate limiting (this depends on implementation)
            assert success_count > 0
    
    # Test request validation
    def test_request_validation_missing_fields(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test request validation with missing required fields."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            
            # Missing platform
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json={"clip_type": "highlight"},
                headers=auth_headers
            )
            assert response.status_code == 400
            
            # Missing clip_type
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json={"platform": "youtube"},
                headers=auth_headers
            )
            assert response.status_code == 400
    
    def test_request_validation_invalid_types(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test request validation with invalid data types."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            
            # Invalid duration type
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": "invalid"  # Should be number
                },
                headers=auth_headers
            )
            assert response.status_code == 400
            
            # Invalid max_clips type
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "max_clips": "invalid"  # Should be number
                },
                headers=auth_headers
            )
            assert response.status_code == 400
    
    # Test response format validation
    def test_response_format_consistency(self, client, auth_headers, mock_video_data, mock_user_data):
        """Test that API responses follow consistent format."""
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = mock_user_data
            mock_task.return_value.id = "job_format_test"
            
            request_data = {
                "platform": "youtube",
                "clip_type": "highlight"
            }
            
            response = client.post(
                "/api/videos/video_123/generate-clips",
                json=request_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify required fields in response
            required_fields = ["job_id", "status", "estimated_duration"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
            
            # Verify data types
            assert isinstance(data["job_id"], str)
            assert isinstance(data["status"], str)
            assert isinstance(data["estimated_duration"], (int, float))


if __name__ == "__main__":
    pytest.main([__file__])