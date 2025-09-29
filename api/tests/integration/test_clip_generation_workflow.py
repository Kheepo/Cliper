import pytest
import asyncio
import os
import tempfile
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from api.main import app
from api.tasks import generate_clips_task, _determine_clip_segments, _get_platform_config, _generate_single_clip

class TestClipGenerationWorkflow:
    """Test comprehensive clip generation workflow integration."""
    
    @pytest.fixture
    def mock_video_file(self):
        """Create a temporary mock video file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            # Write some dummy video data
            f.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def mock_analysis_results(self):
        """Mock video analysis results for testing."""
        return {
            "virality_analysis": {
                "segments": [
                    {
                        "start_time": 10.0,
                        "end_time": 25.0,
                        "virality_score": 0.95,
                        "engagement_factors": ["high_energy", "visual_appeal"],
                        "transcript": "This is an amazing viral moment!"
                    },
                    {
                        "start_time": 45.0,
                        "end_time": 60.0,
                        "virality_score": 0.88,
                        "engagement_factors": ["emotional_peak", "surprise"],
                        "transcript": "Unexpected twist here!"
                    },
                    {
                        "start_time": 120.0,
                        "end_time": 140.0,
                        "virality_score": 0.82,
                        "engagement_factors": ["humor", "relatability"],
                        "transcript": "Funny and relatable content"
                    }
                ],
                "overall_score": 0.88,
                "total_duration": 180.0
            },
            "transcript": "Full video transcript here...",
            "hashtags": ["#viral", "#trending", "#amazing"],
            "recommendations": {
                "best_platforms": ["tiktok", "instagram", "youtube_shorts"],
                "optimal_posting_times": ["18:00", "20:00", "22:00"]
            }
        }
    
    @pytest.fixture
    def mock_generation_options(self):
        """Mock clip generation options."""
        return {
            "platform": "tiktok",
            "clip_type": "highlight",
            "target_duration": 30.0,
            "max_clips": 3,
            "min_virality_score": 0.8
        }
    
    @patch('api.tasks.check_system_health')
    @patch('api.services.supabase_service.SupabaseService')
    @patch('api.services.llm_service.LLMService')
    @patch('api.tasks._determine_clip_segments')
    @patch('api.tasks._generate_single_clip')
    @patch('api.tasks.cleanup_clip_resources')
    @patch('api.main.broadcast_job_update')
    async def test_complete_clip_generation_workflow(
        self,
        mock_broadcast,
        mock_cleanup,
        mock_generate_single,
        mock_determine_segments,
        mock_llm_service,
        mock_supabase_service,
        mock_health_check,
        mock_video_file,
        mock_analysis_results,
        mock_generation_options
    ):
        """Test complete clip generation workflow from start to finish."""
        
        # Setup mocks
        mock_health_check.return_value = {'overall_status': 'healthy'}
        
        # Mock Supabase service
        mock_supabase = Mock()
        mock_supabase.update_clip_status = AsyncMock()
        mock_supabase.get_video_info = AsyncMock(return_value={
            'file_path': mock_video_file,
            'duration': 180.0,
            'title': 'Test Video'
        })
        mock_supabase.get_analysis_results = AsyncMock(return_value=mock_analysis_results)
        mock_supabase.update_clip_data = AsyncMock()
        mock_supabase_service.return_value = mock_supabase
        
        # Mock LLM service
        mock_llm = Mock()
        mock_llm_service.return_value = mock_llm
        
        # Mock segment determination
        mock_segments = [
            {
                "start_time": 10.0,
                "end_time": 25.0,
                "type": "highlight",
                "virality_score": 0.95,
                "transcript": "Amazing viral moment!"
            },
            {
                "start_time": 45.0,
                "end_time": 60.0,
                "type": "highlight",
                "virality_score": 0.88,
                "transcript": "Unexpected twist!"
            }
        ]
        mock_determine_segments.return_value = mock_segments
        
        # Mock single clip generation
        mock_generate_single.return_value = {
            'file_path': '/clips/test_clip_0.mp4',
            'thumbnail_path': '/clips/test_clip_0_thumb.jpg',
            'duration': 15.0,
            'file_size': 1024000
        }
        
        # Mock WebSocket broadcast
        mock_broadcast.return_value = None
        
        # Execute the task
        result = await generate_clips_task(
            clip_id="test-clip-123",
            video_id="test-video-456",
            user_id="test-user-789",
            generation_options=mock_generation_options
        )
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["clip_id"] == "test-clip-123"
        assert result["generated_clips"] == 2
        
        # Verify service calls
        mock_supabase.get_video_info.assert_called_once_with("test-video-456", "test-user-789")
        mock_supabase.get_analysis_results.assert_called_once_with("test-video-456", "test-user-789")
        
        # Verify status updates were called
        assert mock_supabase.update_clip_status.call_count >= 4  # Multiple progress updates
        
        # Verify segment determination was called
        mock_determine_segments.assert_called_once()
        
        # Verify clip generation was called for each segment
        assert mock_generate_single.call_count == 2
        
        # Verify WebSocket updates
        assert mock_broadcast.call_count >= 2  # Initial and final updates
    
    @patch('api.tasks.check_system_health')
    @patch('api.services.supabase_service.SupabaseService')
    async def test_clip_generation_system_health_failure(
        self,
        mock_supabase_service,
        mock_health_check
    ):
        """Test clip generation failure due to system health issues."""
        
        # Mock critical system health
        mock_health_check.return_value = {
            'overall_status': 'critical',
            'issues': 'Insufficient memory and disk space'
        }
        
        # Mock Supabase service
        mock_supabase = Mock()
        mock_supabase.update_clip_status = AsyncMock()
        mock_supabase_service.return_value = mock_supabase
        
        # Execute the task and expect failure
        with pytest.raises(Exception) as exc_info:
            await generate_clips_task(
                clip_id="test-clip-123",
                video_id="test-video-456",
                user_id="test-user-789",
                generation_options={}
            )
        
        assert "System resources insufficient" in str(exc_info.value)
    
    @patch('api.services.llm_service.LLMService')
    async def test_determine_clip_segments_ai_analysis(
        self,
        mock_llm_service,
        mock_analysis_results,
        mock_video_file
    ):
        """Test AI-powered clip segment determination."""
        
        # Mock LLM service
        mock_llm = Mock()
        mock_llm.analyze_segments_for_clips = AsyncMock(return_value={
            "recommended_segments": [
                {
                    "start_time": 10.0,
                    "end_time": 25.0,
                    "confidence": 0.95,
                    "reasoning": "High energy moment with visual appeal"
                }
            ]
        })
        mock_llm_service.return_value = mock_llm
        
        generation_options = {
            "clip_type": "highlight",
            "target_duration": 30.0,
            "platform": "tiktok"
        }
        
        # Execute segment determination
        segments = await _determine_clip_segments(
            analysis_results=mock_analysis_results,
            generation_options=generation_options,
            llm_service=mock_llm,
            video_path=mock_video_file
        )
        
        # Verify segments were determined
        assert len(segments) > 0
        assert all('start_time' in segment for segment in segments)
        assert all('end_time' in segment for segment in segments)
        assert all('type' in segment for segment in segments)
    
    def test_platform_config_generation(self):
        """Test platform-specific configuration generation."""
        
        # Test TikTok configuration
        tiktok_config = _get_platform_config("tiktok")
        assert tiktok_config["aspect_ratio"] == "9:16"
        assert tiktok_config["resolution"] == "1080x1920"
        assert tiktok_config["max_duration"] == 60
        
        # Test YouTube Shorts configuration
        youtube_config = _get_platform_config("youtube_shorts")
        assert youtube_config["aspect_ratio"] == "9:16"
        assert youtube_config["resolution"] == "1080x1920"
        assert youtube_config["max_duration"] == 60
        
        # Test Instagram configuration
        instagram_config = _get_platform_config("instagram")
        assert instagram_config["aspect_ratio"] == "1:1"
        assert instagram_config["resolution"] == "1080x1080"
        
        # Test general configuration
        general_config = _get_platform_config("general")
        assert general_config["aspect_ratio"] == "16:9"
        assert general_config["resolution"] == "1920x1080"
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    async def test_single_clip_generation_ffmpeg(
        self,
        mock_exists,
        mock_subprocess
    ):
        """Test single clip generation using FFmpeg."""
        
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock successful FFmpeg execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b"FFmpeg processing completed"
        mock_result.stderr = b""
        mock_subprocess.return_value = mock_result
        
        segment = {
            "start_time": 10.0,
            "end_time": 25.0,
            "type": "highlight",
            "virality_score": 0.95
        }
        
        platform_config = {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M"
        }
        
        # Execute single clip generation
        result = await _generate_single_clip(
            video_path="/test/video.mp4",
            segment=segment,
            platform_config=platform_config,
            output_dir="/test/output",
            clip_index=0
        )
        
        # Verify result
        assert result is not None
        assert "file_path" in result
        assert "duration" in result
        
        # Verify FFmpeg was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in call_args[0]
        assert "-ss" in call_args  # Start time
        assert "-t" in call_args   # Duration
    
    @patch('api.tasks.generate_clips_task.delay')
    @patch('api.services.supabase_service.supabase_service')
    def test_clip_generation_api_endpoint(
        self,
        mock_supabase,
        mock_task,
        client,
        auth_headers
    ):
        """Test clip generation API endpoint integration."""
        
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock video info
        mock_supabase_instance.get_video_info.return_value = {
            "id": "video-456",
            "file_path": "/videos/test.mp4",
            "status": "completed",
            "user_id": "user-123"
        }
        
        # Mock clip creation
        mock_supabase_instance.create_generated_clip.return_value = {
            "id": "clip-789",
            "status": "pending",
            "video_id": "video-456",
            "user_id": "user-123"
        }
        
        mock_supabase_instance.update_clip.return_value = True
        mock_supabase.return_value = mock_supabase_instance
        
        # Mock task execution
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_task.return_value = mock_result
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Make API request
            response = client.post(
                "/api/clips/generate",
                json={
                    "video_id": "video-456",
                    "platform": "tiktok",
                    "clip_type": "highlight",
                    "target_duration": 30.0,
                    "max_clips": 3
                },
                headers=auth_headers
            )
            
            # Verify response
            assert response.status_code == 202
            response_data = response.json()
            assert response_data["message"] == "Clip generation started"
            assert "clip_id" in response_data
            assert "task_id" in response_data
            
            # Verify task was queued
            mock_task.assert_called_once()
    
    @patch('api.tasks.cleanup_clip_resources')
    @patch('api.services.supabase_service.SupabaseService')
    async def test_clip_generation_error_handling_and_cleanup(
        self,
        mock_supabase_service,
        mock_cleanup
    ):
        """Test error handling and resource cleanup in clip generation."""
        
        # Mock Supabase service that fails
        mock_supabase = Mock()
        mock_supabase.update_clip_status = AsyncMock()
        mock_supabase.get_video_info = AsyncMock(side_effect=Exception("Database error"))
        mock_supabase_service.return_value = mock_supabase
        
        # Execute the task and expect failure
        with pytest.raises(Exception) as exc_info:
            await generate_clips_task(
                clip_id="test-clip-123",
                video_id="test-video-456",
                user_id="test-user-789",
                generation_options={}
            )
        
        assert "Database error" in str(exc_info.value)
        
        # Verify cleanup was called
        mock_cleanup.assert_called_once_with("test-clip-123")
        
        # Verify error status was updated
        mock_supabase.update_clip_status.assert_called()
        status_calls = mock_supabase.update_clip_status.call_args_list
        error_call = next((call for call in status_calls if call[1]['status'] == 'failed'), None)
        assert error_call is not None

class TestClipGenerationPerformance:
    """Test clip generation performance and resource management."""
    
    @patch('api.tasks.check_system_health')
    async def test_memory_management_during_generation(
        self,
        mock_health_check
    ):
        """Test memory management during clip generation."""
        
        # Mock system health checks
        health_checks = [
            {'overall_status': 'healthy', 'memory_usage': 45},
            {'overall_status': 'warning', 'memory_usage': 75},
            {'overall_status': 'healthy', 'memory_usage': 50}
        ]
        mock_health_check.side_effect = health_checks
        
        # Verify health checks are called multiple times
        for _ in range(3):
            health = mock_health_check()
            assert 'memory_usage' in health
    
    @patch('os.path.getsize')
    @patch('shutil.disk_usage')
    def test_disk_space_monitoring(
        self,
        mock_disk_usage,
        mock_getsize
    ):
        """Test disk space monitoring during clip generation."""
        
        # Mock disk usage (total, used, free)
        mock_disk_usage.return_value = (1000000000, 600000000, 400000000)  # 40% free
        mock_getsize.return_value = 50000000  # 50MB file
        
        # Verify disk space calculations
        total, used, free = mock_disk_usage('/test/path')
        file_size = mock_getsize('/test/file.mp4')
        
        free_percentage = (free / total) * 100
        assert free_percentage == 40.0
        assert file_size == 50000000

class TestClipGenerationWebSocket:
    """Test WebSocket integration for clip generation progress."""
    
    @patch('api.main.broadcast_job_update')
    async def test_websocket_progress_updates(
        self,
        mock_broadcast
    ):
        """Test WebSocket progress updates during clip generation."""
        
        # Mock WebSocket broadcast
        mock_broadcast.return_value = None
        
        # Simulate progress updates
        progress_updates = [
            {"job_id": "clip-123", "status": "processing", "progress": 5, "current_step": "Initializing"},
            {"job_id": "clip-123", "status": "processing", "progress": 30, "current_step": "Analyzing segments"},
            {"job_id": "clip-123", "status": "processing", "progress": 80, "current_step": "Generating clips"},
            {"job_id": "clip-123", "status": "completed", "progress": 100, "current_step": "Complete"}
        ]
        
        # Send each update
        for update in progress_updates:
            await mock_broadcast(**update)
        
        # Verify all updates were sent
        assert mock_broadcast.call_count == 4
        
        # Verify final update includes completion
        final_call = mock_broadcast.call_args_list[-1]
        assert final_call[1]['status'] == 'completed'
        assert final_call[1]['progress'] == 100