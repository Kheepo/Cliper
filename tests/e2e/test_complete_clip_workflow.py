import pytest
import asyncio
import tempfile
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import json

from api.main import app
from api.models.user import User
from api.models.video import Video, VideoStatus
from api.models.clip import GeneratedClip, ClipStatus
from api.core.database import get_db
from api.services.video_processor import VideoProcessor
from api.services.clip_service import ClipService
from api.services.storage_service import StorageService


class TestCompleteClipWorkflow:
    """End-to-end tests for complete clip generation workflow."""
    
    def setup_method(self):
        """Setup test environment for E2E testing."""
        self.client = TestClient(app)
        self.test_user_id = "e2e_user_123"
        self.test_video_id = "e2e_video_456"
        
        # Mock authentication
        self.auth_headers = {"Authorization": "Bearer valid_e2e_token"}
        
        # Test user with sufficient credits
        self.test_user = MagicMock(spec=User)
        self.test_user.id = self.test_user_id
        self.test_user.email = "e2e@example.com"
        self.test_user.credits = 100
        self.test_user.subscription_tier = "premium"
        
        # Test video data
        self.test_video = MagicMock(spec=Video)
        self.test_video.id = self.test_video_id
        self.test_video.user_id = self.test_user_id
        self.test_video.title = "E2E Test Video"
        self.test_video.file_path = "/test/e2e_video.mp4"
        self.test_video.duration = 300  # 5 minutes
        self.test_video.status = VideoStatus.PROCESSED
        self.test_video.created_at = datetime.utcnow()
        
        # Clip generation request
        self.clip_request = {
            "video_id": self.test_video_id,
            "platform": "youtube",
            "max_clips": 3,
            "min_duration": 30,
            "max_duration": 60,
            "target_audience": "general",
            "content_type": "educational"
        }
        
        # Expected clip segments
        self.expected_segments = [
            {
                "start_time": 15.0,
                "end_time": 45.0,
                "score": 0.95,
                "reason": "High engagement moment with clear audio",
                "tags": ["highlight", "engaging"]
            },
            {
                "start_time": 120.0,
                "end_time": 180.0,
                "score": 0.88,
                "reason": "Educational content with visual elements",
                "tags": ["educational", "visual"]
            },
            {
                "start_time": 240.0,
                "end_time": 290.0,
                "score": 0.82,
                "reason": "Conclusion with key takeaways",
                "tags": ["conclusion", "summary"]
            }
        ]
    
    def test_complete_clip_generation_workflow(self):
        """Test the complete end-to-end clip generation workflow."""
        generated_clips = []
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.test_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.test_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments', return_value=self.expected_segments), \
             patch('api.services.unified_ai_service.UnifiedAIService.generate_clip_segments', return_value=self.expected_segments), \
             patch('api.services.clip_service.create_clip') as mock_create_clip, \
             patch('api.services.storage_service.upload_clip') as mock_upload, \
             patch('api.services.notification_service.send_clip_ready_notification') as mock_notify:
            
            # Mock clip creation
            def create_clip_side_effect(clip_data):
                clip = MagicMock(spec=GeneratedClip)
                clip.id = f"clip_{len(generated_clips) + 1}"
                clip.video_id = self.test_video_id
                clip.user_id = self.test_user_id
                clip.start_time = clip_data["start_time"]
                clip.end_time = clip_data["end_time"]
                clip.status = ClipStatus.PROCESSING
                clip.file_path = f"/clips/{clip.id}.mp4"
                clip.created_at = datetime.utcnow()
                generated_clips.append(clip)
                return clip
            
            mock_create_clip.side_effect = create_clip_side_effect
            
            # Mock successful upload
            mock_upload.return_value = {
                "url": "https://storage.example.com/clips/clip_1.mp4",
                "size": 1024000,
                "duration": 30.0
            }
            
            # Step 1: Initiate clip generation
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 202  # Accepted for processing
            response_data = response.json()
            assert "job_id" in response_data
            assert response_data["status"] == "processing"
            assert response_data["estimated_completion_time"] is not None
            
            job_id = response_data["job_id"]
            
            # Step 2: Check processing status
            status_response = self.client.get(
                f"/api/clips/jobs/{job_id}/status",
                headers=self.auth_headers
            )
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["job_id"] == job_id
            assert status_data["status"] in ["processing", "completed"]
            assert "progress_percentage" in status_data
            
            # Step 3: Verify clips were created
            assert len(generated_clips) == 3
            assert mock_create_clip.call_count == 3
            
            # Step 4: Verify user credits were deducted
            # In a real scenario, this would be checked via database
            assert self.test_user.credits >= 97  # 3 clips generated
            
            # Step 5: Verify notification was sent
            mock_notify.assert_called_once()
    
    def test_video_upload_to_clip_generation_workflow(self):
        """Test complete workflow from video upload to clip generation."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
            temp_video.write(b"fake video content for testing")
            temp_video_path = temp_video.name
        
        try:
            with patch('api.services.user_service.get_user_by_id', return_value=self.test_user), \
                 patch('api.services.video_service.upload_video') as mock_upload_video, \
                 patch('api.services.video_processor.VideoProcessor.process_video') as mock_process, \
                 patch('api.services.video_processor.VideoProcessor.find_best_segments', return_value=self.expected_segments):
                
                # Mock video upload
                uploaded_video = MagicMock(spec=Video)
                uploaded_video.id = "uploaded_video_123"
                uploaded_video.user_id = self.test_user_id
                uploaded_video.status = VideoStatus.UPLOADED
                mock_upload_video.return_value = uploaded_video
                
                # Mock video processing
                def process_video_side_effect(video_id):
                    uploaded_video.status = VideoStatus.PROCESSED
                    return uploaded_video
                
                mock_process.side_effect = process_video_side_effect
                
                # Step 1: Upload video
                with open(temp_video_path, "rb") as video_file:
                    upload_response = self.client.post(
                        "/api/videos/upload",
                        files={"video": ("test_video.mp4", video_file, "video/mp4")},
                        data={"title": "Test Video for E2E"},
                        headers=self.auth_headers
                    )
                
                assert upload_response.status_code == 201
                upload_data = upload_response.json()
                video_id = upload_data["video_id"]
                
                # Step 2: Wait for video processing (simulated)
                processing_complete = False
                max_attempts = 10
                attempt = 0
                
                while not processing_complete and attempt < max_attempts:
                    status_response = self.client.get(
                        f"/api/videos/{video_id}/status",
                        headers=self.auth_headers
                    )
                    
                    status_data = status_response.json()
                    if status_data["status"] == "processed":
                        processing_complete = True
                    else:
                        time.sleep(0.1)  # Short delay for simulation
                        attempt += 1
                
                assert processing_complete, "Video processing did not complete"
                
                # Step 3: Generate clips from processed video
                clip_request = self.clip_request.copy()
                clip_request["video_id"] = video_id
                
                clip_response = self.client.post(
                    "/api/clips/generate",
                    json=clip_request,
                    headers=self.auth_headers
                )
                
                assert clip_response.status_code == 202
                
        finally:
            # Cleanup
            if os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
    
    def test_bulk_clip_generation_workflow(self):
        """Test bulk clip generation for multiple videos."""
        video_ids = [f"bulk_video_{i}" for i in range(5)]
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.test_user), \
             patch('api.services.video_service.get_videos_by_ids') as mock_get_videos, \
             patch('api.services.video_processor.VideoProcessor.find_best_segments', return_value=self.expected_segments), \
             patch('api.services.clip_service.create_clip') as mock_create_clip:
            
            # Mock multiple videos
            mock_videos = []
            for i, video_id in enumerate(video_ids):
                video = MagicMock(spec=Video)
                video.id = video_id
                video.user_id = self.test_user_id
                video.status = VideoStatus.PROCESSED
                video.duration = 300 + (i * 60)  # Varying durations
                mock_videos.append(video)
            
            mock_get_videos.return_value = mock_videos
            
            # Mock clip creation
            created_clips = []
            def create_clip_side_effect(clip_data):
                clip = MagicMock(spec=GeneratedClip)
                clip.id = f"bulk_clip_{len(created_clips) + 1}"
                clip.video_id = clip_data["video_id"]
                clip.status = ClipStatus.PROCESSING
                created_clips.append(clip)
                return clip
            
            mock_create_clip.side_effect = create_clip_side_effect
            
            # Bulk clip generation request
            bulk_request = {
                "video_ids": video_ids,
                "platform": "youtube",
                "max_clips_per_video": 2,
                "min_duration": 30,
                "max_duration": 60
            }
            
            response = self.client.post(
                "/api/clips/generate/bulk",
                json=bulk_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 202
            response_data = response.json()
            assert "batch_job_id" in response_data
            assert len(response_data["video_jobs"]) == 5
            
            # Verify clips were created for all videos
            expected_total_clips = 5 * 2  # 5 videos, 2 clips each
            assert len(created_clips) <= expected_total_clips
    
    def test_clip_customization_workflow(self):
        """Test workflow with custom clip parameters and post-processing."""
        custom_request = {
            "video_id": self.test_video_id,
            "platform": "tiktok",
            "max_clips": 5,
            "min_duration": 15,
            "max_duration": 30,
            "aspect_ratio": "9:16",
            "add_captions": True,
            "add_music": True,
            "music_genre": "upbeat",
            "color_grading": "vibrant",
            "transition_effects": True
        }
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.test_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.test_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments', return_value=self.expected_segments), \
             patch('api.services.clip_service.create_clip') as mock_create_clip, \
             patch('api.services.post_processing_service.apply_customizations') as mock_customize:
            
            # Mock clip creation with customizations
            def create_customized_clip(clip_data):
                clip = MagicMock(spec=GeneratedClip)
                clip.id = f"custom_clip_{len(mock_create_clip.call_args_list) + 1}"
                clip.video_id = self.test_video_id
                clip.customizations = {
                    "aspect_ratio": custom_request["aspect_ratio"],
                    "captions": custom_request["add_captions"],
                    "music": custom_request["add_music"],
                    "color_grading": custom_request["color_grading"]
                }
                clip.status = ClipStatus.PROCESSING
                return clip
            
            mock_create_clip.side_effect = create_customized_clip
            
            # Mock post-processing
            mock_customize.return_value = {
                "status": "completed",
                "processing_time": 45.2,
                "output_file": "/clips/custom_clip_1_processed.mp4"
            }
            
            response = self.client.post(
                "/api/clips/generate",
                json=custom_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 202
            response_data = response.json()
            assert "customizations_applied" in response_data
            assert response_data["customizations_applied"] is True
            
            # Verify customizations were applied
            mock_customize.assert_called()
    
    def test_clip_sharing_and_analytics_workflow(self):
        """Test workflow including clip sharing and analytics tracking."""
        clip_id = "shareable_clip_123"
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.test_user), \
             patch('api.services.clip_service.get_clip_by_id') as mock_get_clip, \
             patch('api.services.sharing_service.create_share_link') as mock_create_share, \
             patch('api.services.analytics_service.track_clip_view') as mock_track_view:
            
            # Mock clip
            mock_clip = MagicMock(spec=GeneratedClip)
            mock_clip.id = clip_id
            mock_clip.user_id = self.test_user_id
            mock_clip.status = ClipStatus.COMPLETED
            mock_clip.file_url = "https://storage.example.com/clips/clip_123.mp4"
            mock_get_clip.return_value = mock_clip
            
            # Mock share link creation
            mock_create_share.return_value = {
                "share_id": "share_abc123",
                "public_url": "https://cliper.app/share/share_abc123",
                "expires_at": datetime.utcnow() + timedelta(days=30)
            }
            
            # Step 1: Create shareable link
            share_response = self.client.post(
                f"/api/clips/{clip_id}/share",
                json={"expires_in_days": 30, "password_protected": False},
                headers=self.auth_headers
            )
            
            assert share_response.status_code == 201
            share_data = share_response.json()
            assert "public_url" in share_data
            assert "share_id" in share_data
            
            share_id = share_data["share_id"]
            
            # Step 2: Access shared clip (simulate external user)
            public_response = self.client.get(f"/api/share/{share_id}")
            
            assert public_response.status_code == 200
            public_data = public_response.json()
            assert "clip_url" in public_data
            assert "metadata" in public_data
            
            # Step 3: Track analytics
            mock_track_view.assert_called_once()
            
            # Step 4: Get analytics data
            analytics_response = self.client.get(
                f"/api/clips/{clip_id}/analytics",
                headers=self.auth_headers
            )
            
            assert analytics_response.status_code == 200
            analytics_data = analytics_response.json()
            assert "views" in analytics_data
            assert "shares" in analytics_data
    
    def test_subscription_tier_workflow_limits(self):
        """Test workflow respecting subscription tier limits."""
        # Test with free tier user
        free_user = MagicMock(spec=User)
        free_user.id = "free_user_123"
        free_user.subscription_tier = "free"
        free_user.credits = 5
        free_user.monthly_clip_limit = 10
        free_user.clips_generated_this_month = 8
        
        with patch('api.services.user_service.get_user_by_id', return_value=free_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.test_video), \
             patch('api.services.subscription_service.check_tier_limits') as mock_check_limits:
            
            # Mock tier limit check
            mock_check_limits.return_value = {
                "allowed": True,
                "remaining_clips": 2,
                "upgrade_required": False
            }
            
            # Request within limits
            limited_request = self.clip_request.copy()
            limited_request["max_clips"] = 2  # Within remaining limit
            
            response = self.client.post(
                "/api/clips/generate",
                json=limited_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 202
            
            # Test exceeding limits
            mock_check_limits.return_value = {
                "allowed": False,
                "remaining_clips": 0,
                "upgrade_required": True,
                "upgrade_url": "https://cliper.app/upgrade"
            }
            
            exceeded_request = self.clip_request.copy()
            exceeded_request["max_clips"] = 5  # Exceeds limit
            
            response = self.client.post(
                "/api/clips/generate",
                json=exceeded_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 402  # Payment required
            response_data = response.json()
            assert "upgrade_required" in response_data
            assert "upgrade_url" in response_data
    
    def test_workflow_with_webhook_notifications(self):
        """Test workflow with webhook notifications for external integrations."""
        webhook_url = "https://external-app.com/webhooks/clip-ready"
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.test_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.test_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments', return_value=self.expected_segments), \
             patch('api.services.webhook_service.send_webhook') as mock_webhook:
            
            # Request with webhook URL
            webhook_request = self.clip_request.copy()
            webhook_request["webhook_url"] = webhook_url
            webhook_request["webhook_events"] = ["clip_ready", "processing_failed"]
            
            response = self.client.post(
                "/api/clips/generate",
                json=webhook_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 202
            
            # Verify webhook was configured
            mock_webhook.assert_called()
            webhook_call_args = mock_webhook.call_args[1]
            assert webhook_call_args["url"] == webhook_url
            assert "clip_ready" in webhook_call_args["event_type"]
    
    def test_complete_workflow_performance_metrics(self):
        """Test complete workflow while tracking performance metrics."""
        start_time = time.time()
        
        with patch('api.services.user_service.get_user_by_id', return_value=self.test_user), \
             patch('api.services.video_service.get_video_by_id', return_value=self.test_video), \
             patch('api.services.video_processor.VideoProcessor.find_best_segments', return_value=self.expected_segments), \
             patch('api.services.metrics_service.track_performance') as mock_metrics:
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            assert response.status_code == 202
            assert processing_time < 5.0  # Should complete within 5 seconds
            
            # Verify performance metrics were tracked
            mock_metrics.assert_called()
            metrics_call = mock_metrics.call_args[1]
            assert "processing_time" in metrics_call
            assert "memory_usage" in metrics_call
            assert "cpu_usage"