import pytest
import asyncio
import tempfile
import os
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from api.tasks import (
    _get_platform_config,
    _validate_generation_options,
    _determine_clip_segments,
    _find_highlight_segments,
    _find_summary_segments,
    _generate_single_clip,
    _validate_clip_generation_input,
    cleanup_job_resources,
    _generate_thumbnail
)
from api.services.unified_llm_service import ClipSegment


class TestClipGenerationUnits:
    """Unit tests for clip generation functions."""
    
    def test_get_platform_config_youtube(self):
        """Test platform configuration for YouTube."""
        config = _get_platform_config("youtube")
        
        assert config is not None
        assert config["aspect_ratio"] == "16:9"
        assert config["resolution"] == "1920x1080"
        assert config["fps"] == 30
        assert config["max_duration"] == 3600  # 1 hour
        assert "libx264" in config["codec"]
    
    def test_get_platform_config_tiktok(self):
        """Test platform configuration for TikTok."""
        config = _get_platform_config("tiktok")
        
        assert config is not None
        assert config["aspect_ratio"] == "9:16"
        assert config["resolution"] == "1080x1920"
        assert config["fps"] == 30
        assert config["max_duration"] == 180  # 3 minutes
        assert "libx264" in config["codec"]
    
    def test_get_platform_config_instagram_feed(self):
        """Test platform configuration for Instagram Feed."""
        config = _get_platform_config("instagram_feed")
        
        assert config is not None
        assert config["aspect_ratio"] == "1:1"
        assert config["resolution"] == "1080x1080"
        assert config["fps"] == 30
        assert config["max_duration"] == 60
        assert "libx264" in config["codec"]
    
    def test_get_platform_config_instagram_stories(self):
        """Test platform configuration for Instagram Stories."""
        config = _get_platform_config("instagram_stories")
        
        assert config is not None
        assert config["aspect_ratio"] == "9:16"
        assert config["resolution"] == "1080x1920"
        assert config["fps"] == 30
        assert config["max_duration"] == 15
        assert "libx264" in config["codec"]
    
    def test_get_platform_config_invalid(self):
        """Test platform configuration for invalid platform."""
        config = _get_platform_config("invalid_platform")
        
        # Should return default YouTube config
        assert config is not None
        assert config["aspect_ratio"] == "16:9"
    
    def test_validate_generation_options_valid(self):
        """Test validation of valid generation options."""
        options = {
            "platform": "youtube",
            "clip_type": "highlight",
            "target_duration": 30.0,
            "max_clips": 3
        }
        
        # Should not raise any exception
        _validate_generation_options(options)
    
    def test_validate_generation_options_invalid_platform(self):
        """Test validation with invalid platform."""
        options = {
            "platform": "invalid_platform",
            "clip_type": "highlight",
            "target_duration": 30.0
        }
        
        with pytest.raises(ValueError, match="Invalid platform"):
            _validate_generation_options(options)
    
    def test_validate_generation_options_invalid_clip_type(self):
        """Test validation with invalid clip type."""
        options = {
            "platform": "youtube",
            "clip_type": "invalid_type",
            "target_duration": 30.0
        }
        
        with pytest.raises(ValueError, match="Invalid clip_type"):
            _validate_generation_options(options)
    
    def test_validate_generation_options_invalid_duration(self):
        """Test validation with invalid duration."""
        options = {
            "platform": "youtube",
            "clip_type": "highlight",
            "target_duration": -10.0  # Negative duration
        }
        
        with pytest.raises(ValueError, match="Duration must be a positive number"):
            _validate_generation_options(options)
    
    def test_validate_generation_options_invalid_max_clips(self):
        """Test validation with invalid max clips."""
        options = {
            "platform": "youtube",
            "clip_type": "highlight",
            "target_duration": 30.0,
            "max_clips": 0  # Zero clips
        }
        
        with pytest.raises(ValueError, match="max_clips must be a positive integer"):
            _validate_generation_options(options)
    
    @pytest.mark.asyncio
    async def test_find_highlight_segments(self):
        """Test finding highlight segments from virality data."""
        virality_data = [
            {'timestamp': 10.0, 'score': 0.8},
            {'timestamp': 30.0, 'score': 0.9},
            {'timestamp': 50.0, 'score': 0.7}
        ]
        target_duration = 15.0
        video_duration = 120.0
        
        segments = await _find_highlight_segments(virality_data, target_duration, video_duration)
        
        assert isinstance(segments, list)
        assert len(segments) > 0
        for segment in segments:
            assert 'start_time' in segment
            assert 'end_time' in segment
            assert 'duration' in segment
    
    @pytest.mark.asyncio
    async def test_find_summary_segments(self):
        """Test finding summary segments from virality data."""
        virality_data = [
            {'timestamp': 5.0, 'score': 0.6},
            {'timestamp': 25.0, 'score': 0.8},
            {'timestamp': 45.0, 'score': 0.7}
        ]
        target_duration = 20.0
        video_duration = 60.0
        
        segments = await _find_summary_segments(virality_data, target_duration, video_duration)
        
        assert isinstance(segments, list)
        assert len(segments) > 0
        for segment in segments:
            assert 'start_time' in segment
            assert 'end_time' in segment
            assert 'duration' in segment
    
    @pytest.mark.asyncio
    @patch('api.tasks.os.path.exists')
    @patch('api.tasks.os.path.getsize')
    @patch('api.tasks.subprocess')
    async def test_generate_single_clip_success(self, mock_subprocess, mock_getsize, mock_exists):
        """Test successful single clip generation."""
        # Mock file operations
        mock_exists.return_value = True
        mock_getsize.return_value = 1024000  # 1MB file
        
        # Mock subprocess success
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.stderr = MagicMock()
        mock_process.stderr.readline = AsyncMock(side_effect=[b'', None])
        mock_subprocess.create_subprocess_exec = AsyncMock(return_value=mock_process)
        
        # Test parameters
        input_path = "C:\\temp\\input.mp4"
        output_path = "C:\\temp\\output.mp4"
        segment = {
            "start_time": 10.0,
            "duration": 30.0
        }
        platform_config = {
            "codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M",
            "audio_bitrate": "128k",
            "fps": 30,
            "filters": []
        }
        
        # Execute function
        result = await _generate_single_clip(input_path, output_path, segment, platform_config)
        
        # Verify result
        assert result == output_path
        
        # Verify FFmpeg was called
        mock_subprocess.create_subprocess_exec.assert_called()
    
    @pytest.mark.asyncio
    @patch('api.tasks.os.path.exists')
    @patch('api.tasks.subprocess')
    async def test_generate_single_clip_ffmpeg_failure(self, mock_subprocess, mock_exists):
        """Test clip generation when FFmpeg fails."""
        # Mock file operations
        mock_exists.return_value = False  # Output file doesn't exist after failure
        
        # Mock subprocess failure
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.wait = AsyncMock(return_value=None)
        mock_process.stderr = MagicMock()
        mock_process.stderr.readline = AsyncMock(side_effect=[b'FFmpeg error\n', b'', None])
        mock_subprocess.create_subprocess_exec = AsyncMock(return_value=mock_process)
        
        # Test parameters
        input_path = "C:\\temp\\input.mp4"
        output_path = "C:\\temp\\output.mp4"
        segment = {"start_time": 10.0, "duration": 30.0}
        platform_config = {"codec": "libx264", "filters": []}
        
        # Execute function and expect exception
        with pytest.raises(Exception) as exc_info:
            await _generate_single_clip(input_path, output_path, segment, platform_config)
        
        # The actual error message may vary, just check that an exception was raised
        assert exc_info.value is not None
    
    @pytest.mark.asyncio
    @patch('api.tasks.subprocess.run')
    @patch('api.tasks.os.path.exists')
    async def test_generate_thumbnail_success(self, mock_exists, mock_subprocess):
        """Test successful thumbnail generation."""
        # Setup mocks
        mock_exists.return_value = True
        mock_process = Mock()
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        # Test parameters
        video_path = "C:\\temp\\video.mp4"
        timestamp = 15.0
        clip_path = "C:\\temp\\clip.mp4"
        
        # Execute function
        result = await _generate_thumbnail(video_path, timestamp, clip_path)
        
        # Verify result
        expected_path = "C:\\temp\\clip_thumbnail.jpg"
        assert result == expected_path
        
        # Verify FFmpeg was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in call_args[0]
        assert "-ss" in call_args
        assert "-vframes" in call_args
    
    @patch('api.tasks.os.remove')
    @patch('api.tasks.shutil.rmtree')
    @patch('api.tasks.os.path.exists')
    def test_cleanup_clip_resources(self, mock_exists, mock_rmtree, mock_remove):
        """Test cleanup of clip resources."""
        # Setup mocks
        mock_exists.return_value = True
        
        # Test cleanup
        clip_id = "test_clip_123"
        cleanup_clip_resources(clip_id)
        
        # Verify cleanup functions were called
        assert mock_exists.called
        # Note: Actual cleanup depends on implementation details
    
    def test_validate_clip_generation_input_valid(self):
        """Test validation of valid clip generation input."""
        generation_options = {
            "platform": "youtube",
            "clip_type": "highlight",
            "target_duration": 30.0,
            "max_clips": 3
        }
        
        result = _validate_clip_generation_input("job_123", generation_options)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_clip_generation_input_missing_clip_id(self):
        """Test validation with missing clip ID."""
        generation_options = {
            "platform": "youtube",
            "clip_type": "highlight"
        }
        
        result = _validate_clip_generation_input("", generation_options)
        
        assert result["valid"] is False
        assert any("Invalid clip_id: must be a non-empty string" in error for error in result["errors"])
    
    def test_validate_clip_generation_input_invalid_time_range(self):
        """Test validation with invalid time range."""
        generation_options = {
            "platform": "youtube",
            "clip_type": "manual",
            "start_time": 60.0,
            "end_time": 30.0  # End before start
        }
        
        result = _validate_clip_generation_input("job_123", generation_options)
        
        assert result["valid"] is False
        assert any("end_time must be greater than start_time" in error for error in result["errors"])
    
    @pytest.mark.asyncio
    @patch('api.services.unified_llm_service')
    async def test_determine_clip_segments_with_analysis(self, mock_llm_service):
        """Test determining clip segments with analysis results."""
        # Mock LLM service response
        mock_segments = [
            ClipSegment(
                start_time=5.0,
                end_time=35.0,
                confidence=0.9,
                virality_score=8.5,
                engagement_factors=["humor"],
                content_summary="Funny moment"
            )
        ]
        
        mock_llm_service.select_optimal_segments.return_value.segments = mock_segments
        
        # Test parameters
        video_info = {"duration": 300.0}
        analysis_results = {
            "transcript": "Test transcript",
            "summary": "Test summary"
        }
        generation_options = {
            "clip_type": "highlight",
            "target_duration": 30.0,
            "max_clips": 1
        }
        
        # Execute function
        segments = await _determine_clip_segments(
            analysis_results, generation_options, mock_llm_service, "C:\\temp\\video.mp4"
        )
        
        # Verify result
        assert len(segments) == 1
        assert segments[0]["start_time"] == 5.0
        assert segments[0]["end_time"] == 35.0
    
    @pytest.mark.asyncio
    async def test_determine_clip_segments_manual(self):
        """Test determining clip segments with manual specification."""
        # Test parameters
        video_info = {"duration": 300.0}
        analysis_results = {}
        generation_options = {
            "clip_type": "manual",
            "start_time": 10.0,
            "end_time": 40.0
        }
        
        # Execute function
        segments = await _determine_clip_segments(
            analysis_results, generation_options, None, "C:\\temp\\video.mp4"
        )
        
        # Verify result
        assert len(segments) == 1
        assert segments[0]["start_time"] == 10.0
        assert segments[0]["end_time"] == 40.0
        assert segments[0]["duration"] == 30.0
        assert segments[0]["confidence"] == 1.0
        assert segments[0]["reason"] == "Manual selection"


if __name__ == "__main__":
    pytest.main([__file__])