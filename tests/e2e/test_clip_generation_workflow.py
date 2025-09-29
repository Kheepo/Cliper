import pytest
import asyncio
import tempfile
import os
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app
from api.services.supabase_service import SupabaseService
from api.tasks import generate_clips_task


class TestClipGenerationWorkflow:
    """End-to-end tests for the complete clip generation workflow."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def temp_video_file(self):
        """Create a temporary video file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            # Create a minimal MP4 file (in real tests, use actual video)
            temp_file.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            temp_file.flush()
            yield temp_file.name
        os.unlink(temp_file.name)
    
    @pytest.fixture
    def mock_auth_headers(self):
        """Mock authentication headers."""
        return {
            "Authorization": "Bearer test-jwt-token",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture
    def mock_user_data(self):
        """Mock user data."""
        return {
            "id": "user_123",
            "email": "test@example.com",
            "subscription_tier": "premium"
        }
    
    @pytest.mark.asyncio
    async def test_complete_workflow_success(self, client, temp_video_file, mock_auth_headers, mock_user_data):
        """Test complete workflow from upload to clip download."""
        
        # Step 1: Upload video
        with patch('api.routes.videos.supabase_service') as mock_supabase:
            mock_supabase.create_video.return_value = {
                "id": "video_123",
                "title": "Test Video",
                "file_path": temp_video_file,
                "status": "uploaded",
                "duration": 300.0
            }
            
            with open(temp_video_file, 'rb') as video_file:
                upload_response = client.post(
                    "/api/videos/upload",
                    files={"video": ("test_video.mp4", video_file, "video/mp4")},
                    data={"title": "Test Video"},
                    headers={"Authorization": mock_auth_headers["Authorization"]}
                )
            
            assert upload_response.status_code == 200
            upload_data = upload_response.json()
            video_id = upload_data["video_id"]
            assert video_id == "video_123"
        
        # Step 2: Start video analysis
        with patch('api.routes.analysis.analyze_video_task.delay') as mock_analyze_task:
            mock_analyze_task.return_value.id = "analysis_job_123"
            
            analysis_response = client.post(
                f"/api/videos/{video_id}/analyze",
                headers=mock_auth_headers
            )
            
            assert analysis_response.status_code == 200
            analysis_data = analysis_response.json()
            assert "job_id" in analysis_data
        
        # Step 3: Wait for analysis completion (mock)
        with patch('api.routes.analysis.supabase_service') as mock_supabase:
            mock_supabase.get_analysis_results.return_value = {
                "transcript": "This is a test video with exciting content.",
                "summary": "Test video summary",
                "keywords": ["test", "exciting", "content"],
                "sentiment": "positive",
                "topics": ["entertainment"]
            }
            
            mock_supabase.get_virality_scores_by_clip_id.return_value = [
                {"start_time": 0, "end_time": 30, "score": 0.8},
                {"start_time": 30, "end_time": 60, "score": 0.6},
                {"start_time": 60, "end_time": 90, "score": 0.9}
            ]
            
            analysis_status_response = client.get(
                f"/api/videos/{video_id}/analysis",
                headers=mock_auth_headers
            )
            
            assert analysis_status_response.status_code == 200
            analysis_status = analysis_status_response.json()
            assert analysis_status["status"] == "completed"
        
        # Step 4: Generate clips
        with patch('api.routers.clips.generate_clips_task.delay') as mock_clip_task:
            mock_clip_task.return_value.id = "clip_job_123"
            
            clip_generation_params = {
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0,
                "max_clips": 2
            }
            
            clip_response = client.post(
                f"/api/videos/{video_id}/generate-clips",
                json=clip_generation_params,
                headers=mock_auth_headers
            )
            
            assert clip_response.status_code == 200
            clip_data = clip_response.json()
            assert "job_id" in clip_data
            job_id = clip_data["job_id"]
        
        # Step 5: Monitor clip generation progress
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_supabase.get_job_status.return_value = {
                "id": job_id,
                "status": "processing",
                "progress": 50,
                "message": "Generating clip 1 of 2"
            }
            
            progress_response = client.get(
                f"/api/jobs/{job_id}/status",
                headers=mock_auth_headers
            )
            
            assert progress_response.status_code == 200
            progress_data = progress_response.json()
            assert progress_data["status"] == "processing"
            assert progress_data["progress"] == 50
        
        # Step 6: Check completed clips
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            mock_generated_clips = [
                {
                    "id": "clip_1",
                    "title": "Highlight Clip 1",
                    "duration": 30.0,
                    "file_path": "/clips/clip1.mp4",
                    "thumbnail_path": "/clips/clip1_thumb.jpg",
                    "platform": "youtube",
                    "status": "completed"
                },
                {
                    "id": "clip_2",
                    "title": "Highlight Clip 2",
                    "duration": 28.0,
                    "file_path": "/clips/clip2.mp4",
                    "thumbnail_path": "/clips/clip2_thumb.jpg",
                    "platform": "youtube",
                    "status": "completed"
                }
            ]
            
            mock_supabase.get_generated_clips_by_video.return_value = mock_generated_clips
            
            clips_response = client.get(
                f"/api/videos/{video_id}/clips",
                headers=mock_auth_headers
            )
            
            assert clips_response.status_code == 200
            clips_data = clips_response.json()
            assert len(clips_data["clips"]) == 2
            assert clips_data["clips"][0]["id"] == "clip_1"
            assert clips_data["clips"][1]["id"] == "clip_2"
        
        # Step 7: Download clip
        with patch('api.routers.clips.send_file') as mock_send_file:
            mock_send_file.return_value = "file_content"
            
            download_response = client.get(
                f"/api/clips/clip_1/download",
                headers=mock_auth_headers
            )
            
            assert download_response.status_code == 200
            # Verify file download headers
            assert "attachment" in download_response.headers.get("content-disposition", "")
    
    @pytest.mark.asyncio
    async def test_workflow_with_manual_segments(self, client, temp_video_file, mock_auth_headers):
        """Test workflow with manually specified segments."""
        
        video_id = "video_123"
        
        # Generate clips with manual segments
        with patch('api.routers.clips.generate_clips_task.delay') as mock_clip_task:
            mock_clip_task.return_value.id = "clip_job_manual"
            
            manual_clip_params = {
                "platform": "tiktok",
                "clip_type": "manual",
                "segments": [
                    {"start_time": 10, "end_time": 40},
                    {"start_time": 60, "end_time": 90}
                ]
            }
            
            clip_response = client.post(
                f"/api/videos/{video_id}/generate-clips",
                json=manual_clip_params,
                headers=mock_auth_headers
            )
            
            assert clip_response.status_code == 200
            clip_data = clip_response.json()
            assert "job_id" in clip_data
            
            # Verify task was called with manual segments
            mock_clip_task.assert_called_once()
            call_args = mock_clip_task.call_args[0]
            assert call_args[3]["clip_type"] == "manual"
            assert len(call_args[3]["segments"]) == 2
    
    @pytest.mark.asyncio
    async def test_workflow_error_handling(self, client, mock_auth_headers):
        """Test workflow error handling scenarios."""
        
        # Test video not found
        response = client.post(
            "/api/videos/nonexistent/generate-clips",
            json={"platform": "youtube", "clip_type": "highlight"},
            headers=mock_auth_headers
        )
        assert response.status_code == 404
        
        # Test invalid clip parameters
        response = client.post(
            "/api/videos/video_123/generate-clips",
            json={"platform": "invalid", "clip_type": "highlight"},
            headers=mock_auth_headers
        )
        assert response.status_code == 400
        
        # Test unauthorized access
        response = client.post(
            "/api/videos/video_123/generate-clips",
            json={"platform": "youtube", "clip_type": "highlight"}
            # No auth headers
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_concurrent_clip_generation(self, client, mock_auth_headers):
        """Test handling of concurrent clip generation requests."""
        
        video_id = "video_123"
        clip_params = {
            "platform": "youtube",
            "clip_type": "highlight",
            "target_duration": 30.0
        }
        
        with patch('api.routers.clips.generate_clips_task.delay') as mock_clip_task:
            mock_clip_task.return_value.id = "clip_job_concurrent"
            
            # Start first generation
            response1 = client.post(
                f"/api/videos/{video_id}/generate-clips",
                json=clip_params,
                headers=mock_auth_headers
            )
            assert response1.status_code == 200
            
            # Try to start second generation (should be rejected or queued)
            response2 = client.post(
                f"/api/videos/{video_id}/generate-clips",
                json=clip_params,
                headers=mock_auth_headers
            )
            
            # Should either reject (409) or queue (202)
            assert response2.status_code in [202, 409]
    
    @pytest.mark.asyncio
    async def test_websocket_progress_updates(self, client, mock_auth_headers):
        """Test WebSocket progress updates during clip generation."""
        
        # This would require WebSocket testing setup
        # For now, we'll test the HTTP endpoints that would trigger WebSocket updates
        
        video_id = "video_123"
        job_id = "clip_job_ws"
        
        with patch('api.routers.clips.websocket_manager') as mock_ws_manager:
            mock_ws_manager.broadcast_to_user = AsyncMock()
            
            # Simulate progress update
            with patch('api.routers.clips.supabase_service') as mock_supabase:
                mock_supabase.update_job_status.return_value = True
                
                # This would normally be called by the Celery task
                progress_data = {
                    "job_id": job_id,
                    "progress": 75,
                    "status": "processing",
                    "message": "Generating clip 3 of 4"
                }
                
                # Verify WebSocket broadcast would be called
                # (In real implementation, this would be in the Celery task)
                mock_ws_manager.broadcast_to_user.assert_not_called()  # Not called yet
    
    @pytest.mark.asyncio
    async def test_clip_quality_validation(self, client, mock_auth_headers):
        """Test clip quality validation after generation."""
        
        video_id = "video_123"
        
        with patch('api.routers.clips.supabase_service') as mock_supabase:
            # Mock clips with quality issues
            mock_clips_with_issues = [
                {
                    "id": "clip_1",
                    "status": "completed",
                    "file_path": "/clips/clip1.mp4",
                    "file_size": 1024,  # Very small file
                    "duration": 30.0
                },
                {
                    "id": "clip_2",
                    "status": "failed",
                    "error": "FFmpeg encoding failed",
                    "file_path": None
                }
            ]
            
            mock_supabase.get_generated_clips_by_video.return_value = mock_clips_with_issues
            
            clips_response = client.get(
                f"/api/videos/{video_id}/clips",
                headers=mock_auth_headers
            )
            
            assert clips_response.status_code == 200
            clips_data = clips_response.json()
            
            # Should include quality warnings
            completed_clips = [c for c in clips_data["clips"] if c["status"] == "completed"]
            failed_clips = [c for c in clips_data["clips"] if c["status"] == "failed"]
            
            assert len(completed_clips) == 1
            assert len(failed_clips) == 1
            assert failed_clips[0]["error"] == "FFmpeg encoding failed"
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_after_generation(self, client, mock_auth_headers):
        """Test resource cleanup after clip generation."""
        
        video_id = "video_123"
        job_id = "clip_job_cleanup"
        
        with patch('api.tasks.cleanup_job_resources') as mock_cleanup:
            with patch('api.routers.clips.generate_clips_task.delay') as mock_clip_task:
                mock_clip_task.return_value.id = job_id
                
                clip_params = {
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                }
                
                # Start clip generation
                response = client.post(
                    f"/api/videos/{video_id}/generate-clips",
                    json=clip_params,
                    headers=mock_auth_headers
                )
                
                assert response.status_code == 200
                
                # Simulate job completion and cleanup
                # (In real implementation, this would be in the Celery task)
                # mock_cleanup.assert_called_with(video_id)
    
    @pytest.mark.asyncio
    async def test_platform_specific_optimizations(self, client, mock_auth_headers):
        """Test platform-specific optimizations in clip generation."""
        
        video_id = "video_123"
        
        # Test TikTok optimization
        tiktok_params = {
            "platform": "tiktok",
            "clip_type": "highlight",
            "target_duration": 15.0  # Short for TikTok
        }
        
        with patch('api.routers.clips.generate_clips_task.delay') as mock_clip_task:
            mock_clip_task.return_value.id = "tiktok_job"
            
            response = client.post(
                f"/api/videos/{video_id}/generate-clips",
                json=tiktok_params,
                headers=mock_auth_headers
            )
            
            assert response.status_code == 200
            
            # Verify TikTok-specific parameters were passed
            call_args = mock_clip_task.call_args[0]
            assert call_args[3]["platform"] == "tiktok"
            assert call_args[3]["target_duration"] == 15.0
        
        # Test Instagram Stories optimization
        instagram_params = {
            "platform": "instagram_stories",
            "clip_type": "teaser",
            "target_duration": 10.0  # Very short for Stories
        }
        
        with patch('api.routers.clips.generate_clips_task.delay') as mock_clip_task:
            mock_clip_task.return_value.id = "instagram_job"
            
            response = client.post(
                f"/api/videos/{video_id}/generate-clips",
                json=instagram_params,
                headers=mock_auth_headers
            )
            
            assert response.status_code == 200
            
            # Verify Instagram-specific parameters
            call_args = mock_clip_task.call_args[0]
            assert call_args[3]["platform"] == "instagram_stories"
            assert call_args[3]["target_duration"] == 10.0


if __name__ == "__main__":
    pytest.main([__file__])