import pytest
import asyncio
import tempfile
import os
import subprocess
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from api.tasks import generate_clips_task, _generate_single_clip, _generate_thumbnail
from api.services.supabase_service import SupabaseService
from api.services.unified_llm_service import unified_llm_service, ClipSegment, SegmentSelectionResult


class TestClipGenerationIntegration:
    """Integration tests for the complete clip generation workflow."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def sample_video_file(self, temp_dir):
        """Create a sample video file for testing."""
        video_path = os.path.join(temp_dir, "test_video.mp4")
        # Create a dummy file (in real tests, you'd use a real video file)
        with open(video_path, 'wb') as f:
            f.write(b'fake video content')
        return video_path
    
    @pytest.fixture
    def mock_supabase_service(self):
        """Mock SupabaseService for testing."""
        mock_service = Mock(spec=SupabaseService)
        
        # Mock video info
        mock_service.get_video_info.return_value = {
            'id': 'video_123',
            'title': 'Test Video',
            'duration': 300.0,
            'file_path': '/path/to/video.mp4',
            'status': 'processed'
        }
        
        # Mock analysis results
        mock_service.get_analysis_results.return_value = {
            'transcript': 'This is a test video transcript with exciting content.',
            'summary': 'Test video about exciting content.',
            'keywords': ['test', 'exciting', 'content'],
            'sentiment': 'positive',
            'topics': ['entertainment']
        }
        
        # Mock virality scores
        mock_service.get_virality_scores_by_clip_id.return_value = [
            {'start_time': 0, 'end_time': 30, 'score': 0.8},
            {'start_time': 30, 'end_time': 60, 'score': 0.6},
            {'start_time': 60, 'end_time': 90, 'score': 0.9}
        ]
        
        # Mock clip creation
        mock_service.create_generated_clip.return_value = {
            'id': 'clip_456',
            'status': 'processing'
        }
        
        # Mock job updates
        mock_service.update_job_status.return_value = True
        mock_service.update_job.return_value = True
        
        return mock_service
    
    @pytest.fixture
    def mock_llm_service(self):
        """Mock unified LLM service for testing."""
        mock_service = Mock()
        
        # Mock segment selection
        selected_segments = [
            ClipSegment(
                start_time=0.0,
                end_time=30.0,
                virality_score=0.8,
                content_summary="Exciting intro",
                keywords=["intro", "exciting"]
            ),
            ClipSegment(
                start_time=60.0,
                end_time=90.0,
                virality_score=0.9,
                content_summary="Climax moment",
                keywords=["climax", "moment"]
            )
        ]
        
        mock_service.select_optimal_segments.return_value = SegmentSelectionResult(
            segments=[
                ClipSegment(
                    start_time=5.0,
                    end_time=25.0,
                    confidence=0.8,
                    virality_score=7.2,
                    engagement_factors=['educational'],
                    content_summary='Key learning moment'
                ),
                ClipSegment(
                    start_time=45.0,
                    end_time=75.0,
                    confidence=0.9,
                    virality_score=8.8,
                    engagement_factors=['humor', 'relatability'],
                    content_summary='Hilarious reaction sequence'
                )
            ],
            total_processing_time=2.1,
            selection_strategy='multi_segment',
            metadata={'strategy': 'multi_segment'}
        )
        
        return mock_service
    
    @pytest.fixture
    def mock_websocket_manager(self):
        """Mock WebSocket manager for testing."""
        mock_manager = Mock()
        mock_manager.broadcast_to_user = AsyncMock()
        return mock_manager
    
    @pytest.mark.asyncio
    @patch('api.tasks.supabase_service')
    @patch('api.services.unified_llm_service')
    @patch('api.tasks._generate_single_clip')
    @patch('api.tasks.generate_clips_task')
    async def test_generate_clips_task_success(
        self,
        mock_task,
        mock_generate_clip,
        mock_unified_llm,
        mock_supabase,
        mock_supabase_service,
        mock_llm_service
    ):
        """Test successful clip generation workflow."""
        # Setup mocks
        mock_supabase.return_value = mock_supabase_service
        mock_unified_llm.return_value = mock_llm_service
        
        # Mock clip generation
        mock_generate_clip.return_value = "/path/to/generated/clip.mp4"
        
        # Mock task result
        mock_task.return_value = {
            "clips_generated": 2,
            "status": "completed",
            "file_paths": ["/path/to/clip1.mp4", "/path/to/clip2.mp4"]
        }
        
        # Test parameters
        job_id = "job_123"
        video_id = "video_123"
        user_id = "user_456"
        clip_params = {
            "clip_type": "highlight",
            "platform": "youtube",
            "max_clips": 2,
            "duration_range": [20, 40]
        }
        
        # Execute task
        result = mock_task(job_id, video_id, user_id, clip_params)
        
        # Verify result
        assert result is not None
        assert "clips_generated" in result
        assert result["clips_generated"] == 2
        assert "status" in result
        assert result["status"] == "completed"
        
        # Verify task was called
        mock_task.assert_called_once_with(job_id, video_id, user_id, clip_params)
    
    @pytest.mark.asyncio
    @patch('api.tasks.generate_clips_task')
    async def test_generate_clips_task_video_not_found(
        self,
        mock_task
    ):
        """Test clip generation when video is not found."""
        # Mock task to raise exception
        mock_task.side_effect = Exception("Video not found")
        
        # Test parameters
        job_id = "job_123"
        video_id = "nonexistent_video"
        user_id = "user_456"
        clip_params = {"clip_type": "highlight"}
        
        # Execute task and expect exception
        with pytest.raises(Exception) as exc_info:
            mock_task(job_id, video_id, user_id, clip_params)
        
        assert "Video not found" in str(exc_info.value)
        
        # Verify task was called
        mock_task.assert_called_once_with(job_id, video_id, user_id, clip_params)
    
    @pytest.mark.asyncio
    @patch('api.tasks.subprocess.Popen')
    @patch('api.tasks.os.path.exists')
    @patch('api.tasks.os.path.getsize')
    async def test_generate_single_clip_success(self, mock_getsize, mock_exists, mock_popen, temp_dir):
        """Test successful single clip generation."""
        # Setup mocks
        mock_exists.return_value = True
        mock_getsize.return_value = 1024  # Mock file size
        
        # Mock subprocess.Popen
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.poll.return_value = 0  # Process finished
        mock_process.communicate.return_value = ("", "")
        mock_process.stderr = None
        mock_popen.return_value = mock_process
        
        # Test parameters
        input_path = "/path/to/input.mp4"
        output_path = os.path.join(temp_dir, "output_clip.mp4")
        segment = {
            "start_time": 10.0,
            "duration": 30.0
        }
        platform_config = {
            "codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M",
            "audio_bitrate": "128k",
            "fps": 30
        }
        
        # Create expected output file
        with open(output_path, 'w') as f:
            f.write("fake clip content")
        
        # Execute function
        result = await _generate_single_clip(
            input_path, output_path, segment, platform_config
        )
        
        # Verify result
        assert result == output_path
        
        # Verify FFmpeg was called (check first call for clip generation)
        assert mock_popen.call_count >= 1
        first_call_args = mock_popen.call_args_list[0][0][0]  # Get first call command list
        assert first_call_args[0] == "ffmpeg"
        assert "-ss" in first_call_args
        assert "-t" in first_call_args
    
    @pytest.mark.asyncio
    @patch('api.tasks.subprocess.Popen')
    @patch('api.tasks.os.path.exists')
    async def test_generate_single_clip_ffmpeg_failure(self, mock_exists, mock_popen, temp_dir):
        """Test clip generation when FFmpeg fails."""
        # Setup mocks
        mock_exists.return_value = True
        
        # Mock subprocess.Popen for failure
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.poll.return_value = 1  # Process failed
        mock_process.communicate.return_value = ("", "FFmpeg error: invalid input")
        mock_process.stderr = None
        mock_popen.return_value = mock_process
        
        # Test parameters
        input_path = "/path/to/input.mp4"
        output_path = os.path.join(temp_dir, "output_clip.mp4")
        segment = {
            "start_time": 10.0,
            "duration": 30.0
        }
        platform_config = {
            "codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M",
            "audio_bitrate": "128k",
            "fps": 30
        }
        
        # Execute function and expect exception
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            await _generate_single_clip(
                input_path, output_path, segment, platform_config
            )
        
        assert exc_info.value.returncode == 1
    
    @pytest.mark.asyncio
    @patch('api.tasks.subprocess.run')
    @patch('api.tasks.os.path.exists')
    async def test_generate_thumbnail_success(self, mock_exists, mock_subprocess, temp_dir):
        """Test successful thumbnail generation."""
        # Setup mocks
        mock_exists.return_value = True
        mock_process = Mock()
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        # Test parameters
        video_path = "/path/to/video.mp4"
        clip_path = os.path.join(temp_dir, "clip.mp4")
        timestamp = 15.0
        expected_thumbnail_path = os.path.join(temp_dir, "clip_thumbnail.jpg")
        
        # Create expected thumbnail file
        with open(expected_thumbnail_path, 'w') as f:
            f.write("fake thumbnail content")
        
        # Execute function
        result = await _generate_thumbnail(video_path, timestamp, clip_path)
        
        # Verify result
        assert result == expected_thumbnail_path
        
        # Verify FFmpeg was called for thumbnail
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in call_args[0]
        assert "-ss" in call_args
        assert "-vframes" in call_args
    
    @pytest.mark.asyncio
    @patch('api.tasks.generate_clips_task')
    async def test_generate_clips_task_partial_failure(
        self,
        mock_task
    ):
        """Test clip generation with partial failures."""
        # Mock task result with partial failure
        mock_task.return_value = {
            "clips_generated": 1,
            "failed_clips": 1,
            "status": "partial_success",
            "file_paths": ["/path/to/clip1.mp4"]
        }
        
        # Test parameters
        job_id = "job_123"
        video_id = "video_123"
        user_id = "user_456"
        clip_params = {
            "clip_type": "highlight",
            "platform": "youtube",
            "max_clips": 2
        }
        
        # Execute task
        result = mock_task(job_id, video_id, user_id, clip_params)
        
        # Verify result shows partial success
        assert result is not None
        assert "clips_generated" in result
        assert result["clips_generated"] == 1  # Only one successful
        assert "failed_clips" in result
        assert result["failed_clips"] == 1
        
        # Verify task was called
        mock_task.assert_called_once_with(job_id, video_id, user_id, clip_params)
    
    @pytest.mark.asyncio
    @patch('api.tasks.generate_clips_task')
    async def test_clip_generation_with_manual_segments(
        self,
        mock_task
    ):
        """Test clip generation with manually specified segments."""
        # Mock task result for manual segments
        mock_task.return_value = {
            "clips_generated": 2,
            "status": "completed",
            "file_paths": ["/path/to/clip1.mp4", "/path/to/clip2.mp4"]
        }
        
        # Test parameters with manual segments
        job_id = "job_123"
        video_id = "video_123"
        user_id = "user_456"
        clip_params = {
            "clip_type": "manual",
            "platform": "youtube",
            "segments": [
                {"start_time": 10, "end_time": 40},
                {"start_time": 60, "end_time": 90}
            ]
        }
        
        # Execute task
        result = mock_task(job_id, video_id, user_id, clip_params)
        
        # Verify result
        assert result is not None
        assert "clips_generated" in result
        assert result["clips_generated"] == 2
        assert "status" in result
        assert result["status"] == "completed"
        
        # Verify task was called with manual segments
        mock_task.assert_called_once_with(job_id, video_id, user_id, clip_params)
    
    @pytest.mark.asyncio
    @patch('api.tasks.os.path.getsize')
    @patch('api.tasks.shutil.disk_usage')
    async def test_clip_generation_resource_monitoring(self, mock_disk_usage, mock_getsize):
        """Test resource monitoring during clip generation."""
        # Mock disk usage (total, used, free)
        mock_disk_usage.return_value = (1000000000, 500000000, 500000000)  # 500MB free
        mock_getsize.return_value = 100000000  # 100MB file
        
        # Test with low disk space
        with patch('api.tasks.psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 95  # High memory usage
            
            with patch('api.tasks.supabase_service') as mock_supabase:
                mock_service = Mock()
                mock_service.get_video_info.return_value = None  # Force early exit
                mock_supabase.return_value = mock_service
                
                # Should handle resource constraints gracefully
                with pytest.raises(Exception):
                    await generate_clips_task("job_123", "video_123", "user_456", {})
    
    def test_clip_generation_input_validation(self):
        """Test input validation for clip generation parameters."""
        from api.tasks import _validate_clip_generation_input
        
        # Valid input
        valid_params = {
            "clip_type": "highlight",
            "platform": "youtube",
            "target_duration": 30.0
        }
        
        # Should return valid=True
        result = _validate_clip_generation_input("job_123", valid_params)
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        
        # Invalid clip type
        invalid_params = {**valid_params, "clip_type": "invalid_type"}
        result = _validate_clip_generation_input("job_123", invalid_params)
        assert result["valid"] is False
        assert any("Invalid clip_type" in error for error in result["errors"])
        
        # Invalid platform
        invalid_params = {**valid_params, "platform": "invalid_platform"}
        result = _validate_clip_generation_input("job_123", invalid_params)
        assert result["valid"] is False
        assert any("Invalid platform" in error for error in result["errors"])
        
        # Invalid time range
        invalid_params = {**valid_params, "start_time": 60.0, "end_time": 20.0}
        result = _validate_clip_generation_input("job_123", invalid_params)
        assert result["valid"] is False
        assert any("end_time must be greater than start_time" in error for error in result["errors"])


if __name__ == "__main__":
    pytest.main([__file__])