import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from api.tasks import (
    _determine_clip_segments,
    _get_platform_config,
    _generate_single_clip,
    _validate_generation_options,
    cleanup_clip_resources
)
from api.services.unified_llm_service import unified_llm_service

class TestClipGenerationHelpers:
    """Test individual helper functions for clip generation."""
    
    def test_get_platform_config_all_platforms(self):
        """Test platform configuration for all supported platforms."""
        
        # Test TikTok
        tiktok_config = _get_platform_config("tiktok")
        expected_tiktok = {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M",
            "max_duration": 60,
            "fps": 30,
            "format": "mp4"
        }
        assert tiktok_config == expected_tiktok
        
        # Test YouTube Shorts
        youtube_config = _get_platform_config("youtube_shorts")
        expected_youtube = {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "3M",
            "max_duration": 60,
            "fps": 30,
            "format": "mp4"
        }
        assert youtube_config == expected_youtube
        
        # Test Instagram Stories
        instagram_stories_config = _get_platform_config("instagram_stories")
        expected_instagram_stories = {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M",
            "max_duration": 15,
            "fps": 30,
            "format": "mp4"
        }
        assert instagram_stories_config == expected_instagram_stories
        
        # Test Instagram Reels
        instagram_reels_config = _get_platform_config("instagram_reels")
        expected_instagram_reels = {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2.5M",
            "max_duration": 90,
            "fps": 30,
            "format": "mp4"
        }
        assert instagram_reels_config == expected_instagram_reels
        
        # Test Instagram Feed
        instagram_feed_config = _get_platform_config("instagram_feed")
        expected_instagram_feed = {
            "aspect_ratio": "1:1",
            "resolution": "1080x1080",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M",
            "max_duration": 60,
            "fps": 30,
            "format": "mp4"
        }
        assert instagram_feed_config == expected_instagram_feed
        
        # Test Twitter/X
        twitter_config = _get_platform_config("twitter")
        expected_twitter = {
            "aspect_ratio": "16:9",
            "resolution": "1280x720",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M",
            "max_duration": 140,
            "fps": 30,
            "format": "mp4"
        }
        assert twitter_config == expected_twitter
        
        # Test LinkedIn
        linkedin_config = _get_platform_config("linkedin")
        expected_linkedin = {
            "aspect_ratio": "16:9",
            "resolution": "1920x1080",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "3M",
            "max_duration": 600,
            "fps": 30,
            "format": "mp4"
        }
        assert linkedin_config == expected_linkedin
        
        # Test General/Default
        general_config = _get_platform_config("general")
        expected_general = {
            "aspect_ratio": "16:9",
            "resolution": "1920x1080",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "4M",
            "max_duration": 300,
            "fps": 30,
            "format": "mp4"
        }
        assert general_config == expected_general
        
        # Test Unknown Platform (should return general)
        unknown_config = _get_platform_config("unknown_platform")
        assert unknown_config == expected_general
    
    def test_validate_generation_options_valid(self):
        """Test validation of valid generation options."""
        
        valid_options = {
            "platform": "tiktok",
            "clip_type": "highlight",
            "target_duration": 30.0,
            "max_clips": 3,
            "min_virality_score": 0.8
        }
        
        # Should not raise any exception
        _validate_generation_options(valid_options)
    
    def test_validate_generation_options_invalid(self):
        """Test validation of invalid generation options."""
        
        # Test missing required fields
        with pytest.raises(ValueError, match="Missing required field: platform"):
            _validate_generation_options({})
        
        # Test invalid platform
        with pytest.raises(ValueError, match="Invalid platform"):
            _validate_generation_options({"platform": "invalid_platform"})
        
        # Test invalid clip type
        with pytest.raises(ValueError, match="Invalid clip_type"):
            _validate_generation_options({
                "platform": "tiktok",
                "clip_type": "invalid_type"
            })
        
        # Test invalid target duration
        with pytest.raises(ValueError, match="target_duration must be between"):
            _validate_generation_options({
                "platform": "tiktok",
                "clip_type": "highlight",
                "target_duration": 0
            })
        
        # Test invalid max clips
        with pytest.raises(ValueError, match="max_clips must be between"):
            _validate_generation_options({
                "platform": "tiktok",
                "clip_type": "highlight",
                "target_duration": 30,
                "max_clips": 0
            })
        
        # Test invalid virality score
        with pytest.raises(ValueError, match="min_virality_score must be between"):
            _validate_generation_options({
                "platform": "tiktok",
                "clip_type": "highlight",
                "target_duration": 30,
                "max_clips": 3,
                "min_virality_score": 1.5
            })
    
    @patch('api.services.unified_llm_service.unified_llm_service')
    async def test_determine_clip_segments_highlight_type(
        self,
        mock_unified_llm_service
    ):
        """Test segment determination for highlight clips."""
        
        # Mock analysis results
        analysis_results = {
            "virality_analysis": {
                "segments": [
                    {
                        "start_time": 10.0,
                        "end_time": 25.0,
                        "virality_score": 0.95,
                        "engagement_factors": ["high_energy", "visual_appeal"],
                        "transcript": "Amazing moment!"
                    },
                    {
                        "start_time": 45.0,
                        "end_time": 60.0,
                        "virality_score": 0.88,
                        "engagement_factors": ["emotional_peak"],
                        "transcript": "Emotional content"
                    },
                    {
                        "start_time": 120.0,
                        "end_time": 140.0,
                        "virality_score": 0.75,  # Below threshold
                        "engagement_factors": ["humor"],
                        "transcript": "Funny moment"
                    }
                ]
            }
        }
        
        generation_options = {
            "clip_type": "highlight",
            "target_duration": 30.0,
            "max_clips": 3,
            "min_virality_score": 0.8
        }
        
        # Mock LLM service
        mock_llm = Mock()
        mock_llm.analyze_segments_for_clips = AsyncMock(return_value={
            "recommended_segments": [
                {
                    "start_time": 10.0,
                    "end_time": 25.0,
                    "confidence": 0.95,
                    "reasoning": "High energy with visual appeal"
                },
                {
                    "start_time": 45.0,
                    "end_time": 60.0,
                    "confidence": 0.88,
                    "reasoning": "Strong emotional peak"
                }
            ]
        })
        mock_llm_service.return_value = mock_llm
        
        # Execute segment determination
        segments = await _determine_clip_segments(
            analysis_results=analysis_results,
            generation_options=generation_options,
            llm_service=mock_llm,
            video_path="/test/video.mp4"
        )
        
        # Verify results
        assert len(segments) == 2  # Only segments above virality threshold
        assert all(segment["virality_score"] >= 0.8 for segment in segments)
        assert all(segment["type"] == "highlight" for segment in segments)
        
        # Verify LLM was called
        mock_llm.analyze_segments_for_clips.assert_called_once()
    
    @patch('api.services.llm_service.LLMService')
    async def test_determine_clip_segments_summary_type(
        self,
        mock_llm_service
    ):
        """Test segment determination for summary clips."""
        
        analysis_results = {
            "virality_analysis": {
                "segments": [
                    {"start_time": 0, "end_time": 30, "virality_score": 0.7},
                    {"start_time": 30, "end_time": 60, "virality_score": 0.8},
                    {"start_time": 60, "end_time": 90, "virality_score": 0.9},
                    {"start_time": 90, "end_time": 120, "virality_score": 0.6}
                ],
                "total_duration": 120.0
            }
        }
        
        generation_options = {
            "clip_type": "summary",
            "target_duration": 60.0,
            "max_clips": 1
        }
        
        # Mock LLM service
        mock_llm = Mock()
        mock_llm.create_summary_segments = AsyncMock(return_value={
            "summary_segments": [
                {
                    "start_time": 0,
                    "end_time": 60,
                    "summary_type": "overview",
                    "key_points": ["Point 1", "Point 2"]
                }
            ]
        })
        mock_llm_service.return_value = mock_llm
        
        # Execute segment determination
        segments = await _determine_clip_segments(
            analysis_results=analysis_results,
            generation_options=generation_options,
            llm_service=mock_llm,
            video_path="/test/video.mp4"
        )
        
        # Verify results
        assert len(segments) == 1
        assert segments[0]["type"] == "summary"
        assert segments[0]["duration"] == 60.0
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    @patch('os.makedirs')
    async def test_generate_single_clip_success(
        self,
        mock_makedirs,
        mock_exists,
        mock_subprocess
    ):
        """Test successful single clip generation."""
        
        # Mock file operations
        mock_exists.side_effect = lambda path: True if 'video.mp4' in path else False
        mock_makedirs.return_value = None
        
        # Mock successful FFmpeg execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b"FFmpeg processing completed successfully"
        mock_result.stderr = b""
        mock_subprocess.return_value = mock_result
        
        segment = {
            "start_time": 10.0,
            "end_time": 25.0,
            "type": "highlight",
            "virality_score": 0.95,
            "transcript": "Amazing content!"
        }
        
        platform_config = {
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "video_codec": "libx264",
            "audio_codec": "aac",
            "bitrate": "2M",
            "fps": 30,
            "format": "mp4"
        }
        
        # Execute clip generation
        result = await _generate_single_clip(
            video_path="/test/input/video.mp4",
            segment=segment,
            platform_config=platform_config,
            output_dir="/test/output",
            clip_index=0
        )
        
        # Verify result structure
        assert "file_path" in result
        assert "thumbnail_path" in result
        assert "duration" in result
        assert "file_size" in result
        assert "metadata" in result
        
        # Verify metadata
        metadata = result["metadata"]
        assert metadata["segment"] == segment
        assert metadata["platform_config"] == platform_config
        assert metadata["clip_index"] == 0
        
        # Verify FFmpeg was called with correct parameters
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in call_args[0]
        assert "-ss" in call_args  # Start time
        assert "10.0" in call_args  # Start time value
        assert "-t" in call_args   # Duration
        assert "15.0" in call_args  # Duration value (25-10)
    
    @patch('subprocess.run')
    async def test_generate_single_clip_ffmpeg_failure(
        self,
        mock_subprocess
    ):
        """Test single clip generation with FFmpeg failure."""
        
        # Mock failed FFmpeg execution
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b"FFmpeg error: Invalid input file"
        mock_subprocess.return_value = mock_result
        
        segment = {
            "start_time": 10.0,
            "end_time": 25.0,
            "type": "highlight"
        }
        
        platform_config = _get_platform_config("tiktok")
        
        # Execute clip generation and expect failure
        with pytest.raises(Exception) as exc_info:
            await _generate_single_clip(
                video_path="/test/invalid_video.mp4",
                segment=segment,
                platform_config=platform_config,
                output_dir="/test/output",
                clip_index=0
            )
        
        assert "FFmpeg processing failed" in str(exc_info.value)
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('shutil.rmtree')
    def test_cleanup_clip_resources(
        self,
        mock_rmtree,
        mock_remove,
        mock_exists
    ):
        """Test cleanup of clip generation resources."""
        
        # Mock file existence
        mock_exists.return_value = True
        
        # Execute cleanup
        cleanup_clip_resources("test-clip-123")
        
        # Verify cleanup operations
        assert mock_exists.call_count >= 1
        # Note: Actual cleanup calls depend on implementation
    
    def test_ffmpeg_command_generation(self):
        """Test FFmpeg command generation for different platforms."""
        
        from api.tasks import _build_ffmpeg_command
        
        # Test TikTok command
        tiktok_config = _get_platform_config("tiktok")
        tiktok_cmd = _build_ffmpeg_command(
            input_path="/input/video.mp4",
            output_path="/output/clip.mp4",
            start_time=10.0,
            duration=15.0,
            platform_config=tiktok_config
        )
        
        expected_tiktok = [
            "ffmpeg", "-y",
            "-ss", "10.0",
            "-i", "/input/video.mp4",
            "-t", "15.0",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:v", "2M",
            "-r", "30",
            "-f", "mp4",
            "/output/clip.mp4"
        ]
        
        assert tiktok_cmd == expected_tiktok
        
        # Test Instagram Feed command (square aspect ratio)
        instagram_config = _get_platform_config("instagram_feed")
        instagram_cmd = _build_ffmpeg_command(
            input_path="/input/video.mp4",
            output_path="/output/clip.mp4",
            start_time=5.0,
            duration=20.0,
            platform_config=instagram_config
        )
        
        # Verify square aspect ratio processing
        assert "scale=1080:1080" in " ".join(instagram_cmd)
    
    def test_segment_duration_calculation(self):
        """Test segment duration calculations."""
        
        from api.tasks import _calculate_segment_duration
        
        # Test normal segment
        duration1 = _calculate_segment_duration(10.0, 25.0)
        assert duration1 == 15.0
        
        # Test zero duration
        duration2 = _calculate_segment_duration(10.0, 10.0)
        assert duration2 == 0.0
        
        # Test negative duration (invalid)
        with pytest.raises(ValueError):
            _calculate_segment_duration(25.0, 10.0)
    
    def test_clip_metadata_generation(self):
        """Test clip metadata generation."""
        
        from api.tasks import _generate_clip_metadata
        
        segment = {
            "start_time": 10.0,
            "end_time": 25.0,
            "type": "highlight",
            "virality_score": 0.95,
            "transcript": "Amazing content!"
        }
        
        platform_config = _get_platform_config("tiktok")
        
        metadata = _generate_clip_metadata(
            segment=segment,
            platform_config=platform_config,
            clip_index=0,
            file_path="/output/clip_0.mp4",
            file_size=1024000
        )
        
        # Verify metadata structure
        assert metadata["segment"] == segment
        assert metadata["platform_config"] == platform_config
        assert metadata["clip_index"] == 0
        assert metadata["file_path"] == "/output/clip_0.mp4"
        assert metadata["file_size"] == 1024000
        assert "created_at" in metadata
        assert "processing_time" in metadata

class TestClipGenerationValidation:
    """Test validation functions for clip generation."""
    
    def test_validate_video_file_path(self):
        """Test video file path validation."""
        
        from api.tasks import _validate_video_file
        
        # Test valid extensions
        valid_files = [
            "/path/video.mp4",
            "/path/video.avi",
            "/path/video.mov",
            "/path/video.mkv",
            "/path/video.webm"
        ]
        
        for file_path in valid_files:
            assert _validate_video_file(file_path) == True
        
        # Test invalid extensions
        invalid_files = [
            "/path/video.txt",
            "/path/video.jpg",
            "/path/video.pdf",
            "/path/video"
        ]
        
        for file_path in invalid_files:
            assert _validate_video_file(file_path) == False
    
    def test_validate_segment_timing(self):
        """Test segment timing validation."""
        
        from api.tasks import _validate_segment_timing
        
        # Test valid timing
        valid_segment = {
            "start_time": 10.0,
            "end_time": 25.0
        }
        assert _validate_segment_timing(valid_segment, 180.0) == True
        
        # Test invalid timing (end before start)
        invalid_segment1 = {
            "start_time": 25.0,
            "end_time": 10.0
        }
        assert _validate_segment_timing(invalid_segment1, 180.0) == False
        
        # Test invalid timing (beyond video duration)
        invalid_segment2 = {
            "start_time": 10.0,
            "end_time": 200.0
        }
        assert _validate_segment_timing(invalid_segment2, 180.0) == False
        
        # Test negative start time
        invalid_segment3 = {
            "start_time": -5.0,
            "end_time": 25.0
        }
        assert _validate_segment_timing(invalid_segment3, 180.0) == False
    
    def test_validate_platform_constraints(self):
        """Test platform-specific constraint validation."""
        
        from api.tasks import _validate_platform_constraints
        
        # Test TikTok constraints
        tiktok_segment = {
            "start_time": 10.0,
            "end_time": 40.0  # 30 seconds, within TikTok limit
        }
        assert _validate_platform_constraints(tiktok_segment, "tiktok") == True
        
        # Test TikTok constraint violation
        tiktok_long_segment = {
            "start_time": 10.0,
            "end_time": 80.0  # 70 seconds, exceeds TikTok limit
        }
        assert _validate_platform_constraints(tiktok_long_segment, "tiktok") == False
        
        # Test Instagram Stories constraints
        instagram_segment = {
            "start_time": 5.0,
            "end_time": 18.0  # 13 seconds, within Instagram Stories limit
        }
        assert _validate_platform_constraints(instagram_segment, "instagram_stories") == True