from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import re
from uuid import UUID
from .pydantic_models import JobTypeEnum, JobStatusEnum, QualityEnum, PlatformEnum

class URLValidationMixin:
    """Mixin for URL validation"""
    
    @staticmethod
    def validate_url(url: str) -> str:
        """Validate URL format"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain...
            r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # host...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(url):
            raise ValueError('Invalid URL format')
        return url

class TimeValidationMixin:
    """Mixin for time-related validation"""
    
    @staticmethod
    def validate_time_range(start_time: float, end_time: float) -> tuple:
        """Validate time range"""
        if start_time < 0:
            raise ValueError('Start time cannot be negative')
        if end_time < 0:
            raise ValueError('End time cannot be negative')
        if start_time >= end_time:
            raise ValueError('Start time must be less than end time')
        if end_time - start_time > 3600:  # 1 hour max
            raise ValueError('Time range cannot exceed 1 hour')
        return start_time, end_time

class VideoProcessingRequest(BaseModel, URLValidationMixin):
    """Enhanced video processing request with comprehensive validation"""
    
    video_url: str = Field(..., description="URL of the video to process")
    job_type: JobTypeEnum = Field(..., description="Type of processing job")
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    priority: int = Field(default=5, ge=1, le=10, description="Job priority")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for job completion")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('video_url')
    def validate_video_url(cls, v):
        return cls.validate_url(v)
    
    @validator('webhook_url')
    def validate_webhook_url(cls, v):
        if v is not None:
            return cls.validate_url(v)
        return v
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or v.isspace():
            raise ValueError('User ID cannot be empty')
        # Check for valid UUID format or auth provider format
        if not (re.match(r'^[a-zA-Z0-9_|\-]+$', v) and len(v) >= 3):
            raise ValueError('Invalid user ID format')
        return v.strip()
    
    @validator('metadata')
    def validate_metadata(cls, v):
        if len(str(v)) > 10000:
            raise ValueError('Metadata too large (max 10KB)')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "job_type": "video_analysis",
                "user_id": "auth0|123456789",
                "priority": 5,
                "webhook_url": "https://myapp.com/webhook",
                "metadata": {
                    "source": "upload",
                    "tags": ["viral", "entertainment"]
                }
            }
        }

class ClipGenerationRequest(BaseModel, TimeValidationMixin):
    """Enhanced clip generation request with time validation"""
    
    job_id: str = Field(..., min_length=1, description="Source job ID")
    title: str = Field(..., min_length=1, max_length=200, description="Clip title")
    description: Optional[str] = Field(None, max_length=1000, description="Clip description")
    start_time: float = Field(..., ge=0, description="Start time in seconds")
    end_time: float = Field(..., gt=0, description="End time in seconds")
    quality: QualityEnum = Field(default=QualityEnum.HIGH, description="Output quality")
    include_captions: bool = Field(default=True, description="Include captions")
    target_platforms: List[PlatformEnum] = Field(default_factory=list, description="Target platforms")
    custom_settings: Dict[str, Any] = Field(default_factory=dict, description="Custom export settings")
    
    @validator('title')
    def validate_title(cls, v):
        if not v or v.isspace():
            raise ValueError('Title cannot be empty')
        # Remove excessive whitespace
        return ' '.join(v.split())
    
    @validator('description')
    def validate_description(cls, v):
        if v is not None and v.strip() == '':
            return None
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_time_range_root(cls, values):
        start_time = values.get('start_time')
        end_time = values.get('end_time')
        if start_time is not None and end_time is not None:
            cls.validate_time_range(start_time, end_time)
        return values
    
    @validator('target_platforms')
    def validate_platforms(cls, v):
        if len(v) > 10:
            raise ValueError('Too many target platforms (max 10)')
        return list(set(v))  # Remove duplicates
    
    @validator('custom_settings')
    def validate_custom_settings(cls, v):
        if len(str(v)) > 5000:
            raise ValueError('Custom settings too large (max 5KB)')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "job_123456789",
                "title": "Viral Moment #1",
                "description": "The funniest part of the video",
                "start_time": 30.5,
                "end_time": 60.0,
                "quality": "high",
                "include_captions": True,
                "target_platforms": ["tiktok", "instagram"],
                "custom_settings": {
                    "aspect_ratio": "9:16",
                    "add_watermark": False
                }
            }
        }

class UserSettingsUpdate(BaseModel):
    """Enhanced user settings update with validation"""
    
    default_clip_duration: Optional[int] = Field(None, ge=5, le=300, description="Default clip duration in seconds")
    preferred_quality: Optional[QualityEnum] = Field(None, description="Preferred output quality")
    auto_generate_hashtags: Optional[bool] = Field(None, description="Auto-generate hashtags")
    max_concurrent_jobs: Optional[int] = Field(None, ge=1, le=10, description="Maximum concurrent jobs")
    notification_preferences: Optional[Dict[str, bool]] = Field(None, description="Notification settings")
    export_settings: Optional[Dict[str, Any]] = Field(None, description="Export preferences")
    api_rate_limit: Optional[int] = Field(None, ge=1, le=1000, description="API rate limit per hour")
    
    @validator('notification_preferences')
    def validate_notifications(cls, v):
        if v is not None:
            valid_keys = ['email', 'webhook', 'in_app', 'sms']
            for key in v.keys():
                if key not in valid_keys:
                    raise ValueError(f'Invalid notification type: {key}. Valid types: {", ".join(valid_keys)}')
        return v
    
    @validator('export_settings')
    def validate_export_settings(cls, v):
        if v is not None:
            if len(str(v)) > 5000:
                raise ValueError('Export settings too large (max 5KB)')
            # Validate specific export settings
            if 'bitrate' in v and not isinstance(v['bitrate'], (int, float)):
                raise ValueError('Bitrate must be a number')
            if 'resolution' in v and not re.match(r'^\d+x\d+$', str(v['resolution'])):
                raise ValueError('Resolution must be in format WIDTHxHEIGHT')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "default_clip_duration": 30,
                "preferred_quality": "high",
                "auto_generate_hashtags": True,
                "max_concurrent_jobs": 3,
                "notification_preferences": {
                    "email": True,
                    "webhook": False,
                    "in_app": True
                },
                "export_settings": {
                    "bitrate": 5000000,
                    "resolution": "1920x1080",
                    "format": "mp4"
                },
                "api_rate_limit": 100
            }
        }

class BulkJobRequest(BaseModel):
    """Request for processing multiple jobs"""
    
    jobs: List[VideoProcessingRequest] = Field(..., min_items=1, max_items=50, description="List of jobs to process")
    batch_priority: int = Field(default=5, ge=1, le=10, description="Priority for the entire batch")
    webhook_url: Optional[str] = Field(None, description="Webhook for batch completion")
    
    @validator('jobs')
    def validate_jobs(cls, v):
        if len(v) == 0:
            raise ValueError('At least one job is required')
        
        # Check for duplicate video URLs
        urls = [job.video_url for job in v]
        if len(urls) != len(set(urls)):
            raise ValueError('Duplicate video URLs found in batch')
        
        return v
    
    @validator('webhook_url')
    def validate_webhook_url(cls, v):
        if v is not None:
            return URLValidationMixin.validate_url(v)
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "jobs": [
                    {
                        "video_url": "https://example.com/video1.mp4",
                        "job_type": "video_analysis",
                        "user_id": "auth0|123456789",
                        "priority": 5
                    }
                ],
                "batch_priority": 3,
                "webhook_url": "https://myapp.com/batch-webhook"
            }
        }

class ErrorResponse(BaseModel):
    """Standardized error response"""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid input data provided",
                "details": {
                    "field": "video_url",
                    "issue": "Invalid URL format"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789"
            }
        }

class PaginationParams(BaseModel):
    """Pagination parameters with validation"""
    
    page: int = Field(default=1, ge=1, le=10000, description="Page number")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, max_length=50, description="Sort field")
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        if v is not None:
            # Only allow alphanumeric and underscore
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
                raise ValueError('Invalid sort field name')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "page": 1,
                "limit": 20,
                "sort_by": "created_at",
                "sort_order": "desc"
            }
        }