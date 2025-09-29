"""Unit tests for validation schemas and utilities."""

import pytest
from datetime import datetime
from pydantic import ValidationError

# Import existing models
from api.models.pydantic_models import (
    JobCreate,
    JobStatus,
    JobTypeEnum,
    JobStatusEnum
)
from api.models.validation_models import (
    VideoProcessingRequest,
    ClipGenerationRequest,
    UserSettingsUpdate
)

# Test constants
VALID_URL = "https://example.com/video.mp4"
VALID_EMAIL = "test@example.com"
INVALID_URLS = [
    "not-a-url",
    "ftp://example.com",
    "http://",
    "",
    "javascript:alert('xss')"
]
INVALID_EMAILS = [
    "not-an-email",
    "@example.com",
    "test@",
    "test.example.com",
    ""
]


class TestJobValidation:
    """Test job-related validation schemas."""
    
    def test_job_create_valid_data(self):
        """Test JobCreate with valid data."""
        job_data = {
            "user_id": "auth0|123456789",
            "job_type": JobTypeEnum.VIDEO_ANALYSIS,
            "priority": 5,
            "metadata": {"source": "upload"}
        }
        
        job = JobCreate(**job_data)
        
        assert job.user_id == "auth0|123456789"
        assert job.job_type == JobTypeEnum.VIDEO_ANALYSIS
        assert job.priority == 5
        assert job.metadata == {"source": "upload"}
    
    def test_job_create_invalid_priority(self):
        """Test JobCreate with invalid priority values."""
        invalid_priorities = [0, 11, -1, 100]
        
        for invalid_priority in invalid_priorities:
            job_data = {
                "user_id": "auth0|123456789",
                "job_type": JobTypeEnum.VIDEO_ANALYSIS,
                "priority": invalid_priority
            }
            
            with pytest.raises(ValidationError) as exc_info:
                JobCreate(**job_data)
            
            errors = exc_info.value.errors()
            assert any(error["loc"] == ("priority",) for error in errors)
    
    def test_job_create_large_metadata(self):
        """Test JobCreate with oversized metadata."""
        large_metadata = {"data": "x" * 10001}  # Over 10KB limit
        
        job_data = {
            "user_id": "auth0|123456789",
            "job_type": JobTypeEnum.VIDEO_ANALYSIS,
            "metadata": large_metadata
        }
        
        with pytest.raises(ValidationError) as exc_info:
            JobCreate(**job_data)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("metadata",) for error in errors)
    
    def test_job_status_valid_data(self):
        """Test JobStatus with valid data"""
        data = {
            "job_id": "job_123",
            "status": JobStatusEnum.PROCESSING,
            "progress": 50,
            "current_step": "Processing video",
            "estimated_remaining": 120.5,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        job_status = JobStatus(**data)
        assert job_status.job_id == "job_123"
        assert job_status.status == JobStatusEnum.PROCESSING
        assert job_status.progress == 50
    
    def test_job_status_invalid_progress(self):
        """Test JobStatus with invalid progress"""
        data = {
            "job_id": "job_123",
            "status": JobStatusEnum.PROCESSING,
            "progress": 150,  # Invalid: > 100
            "current_step": "Processing",
            "estimated_remaining": 60.0,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        with pytest.raises(ValidationError):
            JobStatus(**data)


class TestVideoProcessingValidation:
    """Test video processing validation schemas."""
    
    def test_video_processing_request_valid_data(self):
        """Test VideoProcessingRequest with valid data."""
        request_data = {
            "video_url": VALID_URL,
            "job_type": "video_analysis",
            "user_id": "auth0|123456789",
            "priority": 5,
            "webhook_url": VALID_URL,
            "metadata": {"source": "upload"}
        }
        
        request = VideoProcessingRequest(**request_data)
        
        assert request.video_url == VALID_URL
        assert request.job_type == "video_analysis"
        assert request.user_id == "auth0|123456789"
        assert request.priority == 5
        assert request.webhook_url == VALID_URL
        assert request.metadata == {"source": "upload"}
    
    def test_video_processing_request_invalid_url(self):
        """Test VideoProcessingRequest with invalid URLs."""
        for invalid_url in INVALID_URLS:
            request_data = {
                "video_url": invalid_url,
                "job_type": "video_analysis",
                "user_id": "auth0|123456789"
            }
            
            with pytest.raises(ValidationError) as exc_info:
                VideoProcessingRequest(**request_data)
            
            errors = exc_info.value.errors()
            assert any(error["loc"] == ("video_url",) for error in errors)
    
    def test_video_processing_request_invalid_priority(self):
        """Test VideoProcessingRequest with invalid priority values."""
        invalid_priorities = [0, 11, -1, 100]
        
        for invalid_priority in invalid_priorities:
            request_data = {
                "video_url": VALID_URL,
                "job_type": "video_analysis",
                "user_id": "auth0|123456789",
                "priority": invalid_priority
            }
            
            with pytest.raises(ValidationError) as exc_info:
                VideoProcessingRequest(**request_data)
            
            errors = exc_info.value.errors()
            assert any(error["loc"] == ("priority",) for error in errors)
    
    def test_video_processing_request_large_metadata(self):
        """Test VideoProcessingRequest with oversized metadata."""
        large_metadata = {"data": "x" * 10001}  # Over 10KB limit
        
        request_data = {
            "video_url": VALID_URL,
            "job_type": "video_analysis",
            "user_id": "auth0|123456789",
            "metadata": large_metadata
        }
        
        with pytest.raises(ValidationError) as exc_info:
            VideoProcessingRequest(**request_data)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("metadata",) for error in errors)
    
    def test_video_processing_request_optional_fields(self):
        """Test VideoProcessingRequest with optional fields."""
        request_data = {
            "video_url": VALID_URL,
            "job_type": "video_analysis",
            "user_id": "auth0|123456789"
            # priority, webhook_url, metadata are optional
        }
        
        request = VideoProcessingRequest(**request_data)
        
        assert request.video_url == VALID_URL
        assert request.job_type == "video_analysis"
        assert request.user_id == "auth0|123456789"
        assert request.priority == 5  # default value
        assert request.webhook_url is None
        assert request.metadata == {}  # default empty dict


class TestClipGenerationValidation:
    """Test clip generation validation schemas."""
    
    def test_clip_generation_request_valid_data(self):
        """Test ClipGenerationRequest with valid data"""
        data = {
            "job_id": "job_123",
            "title": "Test Clip",
            "start_time": 10.0,
            "end_time": 30.0,
            "quality": "high",
            "include_captions": True,
            "target_platforms": ["tiktok"],
            "custom_settings": {}
        }
        clip_request = ClipGenerationRequest(**data)
        assert clip_request.job_id == "job_123"
        assert clip_request.title == "Test Clip"
    
    def test_clip_generation_request_invalid_time_range(self):
        """Test ClipGenerationRequest with invalid time range."""
        request_data = {
            "video_url": VALID_URL,
            "start_time": 30.0,  # start > end
            "end_time": 10.0,
            "user_id": "auth0|123456789"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ClipGenerationRequest(**request_data)
        
        errors = exc_info.value.errors()
        # Should have validation error for time range
        assert len(errors) > 0


class TestUserSettingsValidation:
    """Test user settings validation schemas."""
    
    def test_user_settings_update_valid_data(self):
        """Test UserSettingsUpdate with valid data"""
        data = {
            "default_clip_duration": 30,
            "preferred_quality": "high",
            "auto_generate_hashtags": True,
            "max_concurrent_jobs": 3
        }
        settings = UserSettingsUpdate(**data)
        assert settings.default_clip_duration == 30
        assert settings.preferred_quality == "high"
    
    def test_user_settings_update_partial_data(self):
        """Test UserSettingsUpdate with partial data"""
        data = {
            "preferred_quality": "medium"
        }
        settings = UserSettingsUpdate(**data)
        assert settings.preferred_quality == "medium"