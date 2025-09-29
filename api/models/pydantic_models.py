from pydantic import BaseModel, Field, validator, model_validator, EmailStr, HttpUrl
from typing import Optional, List, Dict, Any, Union, Literal
from datetime import datetime
from enum import Enum
import re
from uuid import UUID

# Auth Models
class UserCreate(BaseModel):
    """User creation model."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserLogin(BaseModel):
    """User login model."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """User response model."""
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class PasswordResetRequest(BaseModel):
    """Password reset request model."""
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    """Password reset confirmation model."""
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('Password must contain at least one letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v

# AuthResponse moved after UserProfileResponse definition

class LogoutRequest(BaseModel):
    """Logout request model."""
    refresh_token: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str = Field(..., min_length=1)

# Enums for validation
class JobTypeEnum(str, Enum):
    VIDEO_ANALYSIS = "video_analysis"
    CLIP_GENERATION = "clip_generation"
    TRANSCRIPT_GENERATION = "transcript_generation"
    VIRALITY_ANALYSIS = "virality_analysis"

class JobStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class QualityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"

class PlatformEnum(str, Enum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"

class LogLevelEnum(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class JobCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255, description="User ID from authentication system")
    job_type: JobTypeEnum = Field(..., description="Type of job to be processed")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional job metadata")
    priority: Optional[int] = Field(default=5, ge=1, le=10, description="Job priority (1=highest, 10=lowest)")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or v.isspace():
            raise ValueError('User ID cannot be empty or whitespace')
        return v.strip()
    
    @validator('metadata')
    def validate_metadata(cls, v):
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError('Metadata must be a dictionary')
        # Limit metadata size to prevent abuse
        if len(str(v)) > 10000:
            raise ValueError('Metadata too large (max 10KB)')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "auth0|123456789",
                "job_type": "video_analysis",
                "metadata": {
                    "video_url": "https://example.com/video.mp4",
                    "description": "Analysis of viral content"
                },
                "priority": 5
            }
        }

class JobResponse(BaseModel):
    job_id: str = Field(..., min_length=1, description="Unique job identifier")
    status: JobStatusEnum = Field(..., description="Current job status")
    message: str = Field(..., min_length=1, max_length=1000, description="Status message")
    
    @validator('job_id')
    def validate_job_id(cls, v):
        if not v or v.isspace():
            raise ValueError('Job ID cannot be empty')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "job_123456789",
                "status": "processing",
                "message": "Video analysis in progress"
            }
        }

class JobStatus(BaseModel):
    job_id: str = Field(..., min_length=1, description="Unique job identifier")
    status: JobStatusEnum = Field(..., description="Current job status")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage (0-100)")
    current_step: str = Field(..., min_length=1, max_length=200, description="Current processing step")
    estimated_remaining: float = Field(..., ge=0, description="Estimated remaining time in seconds")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    error_message: Optional[str] = Field(None, max_length=2000, description="Error message if job failed")
    
    @validator('job_id')
    def validate_job_id(cls, v):
        if not v or v.isspace():
            raise ValueError('Job ID cannot be empty')
        return v.strip()
    
    @model_validator(mode='after')
    def validate_timestamps(self):
        if self.created_at and self.updated_at and self.updated_at < self.created_at:
            raise ValueError('Updated timestamp cannot be before created timestamp')
        return self
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "job_123456789",
                "status": "processing",
                "progress": 75,
                "current_step": "Analyzing video segments",
                "estimated_remaining": 120.5,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:00Z",
                "error_message": None
            }
        }

class VideoUpload(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=255, description="Original filename")
    file_size: int = Field(..., gt=0, le=5_000_000_000, description="File size in bytes (max 5GB)")
    content_type: str = Field(..., description="MIME type of the video file")
    description: Optional[str] = Field(None, max_length=1000, description="Optional video description")
    duration: Optional[float] = Field(None, gt=0, le=7200, description="Video duration in seconds (max 2 hours)")
    
    @validator('file_name')
    def validate_file_name(cls, v):
        if not v or v.isspace():
            raise ValueError('File name cannot be empty')
        # Check for valid file extension
        valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
        if not any(v.lower().endswith(ext) for ext in valid_extensions):
            raise ValueError(f'Invalid file extension. Supported: {", ".join(valid_extensions)}')
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        if any(char in v for char in dangerous_chars):
            raise ValueError('File name contains invalid characters')
        return v.strip()
    
    @validator('content_type')
    def validate_content_type(cls, v):
        valid_types = [
            'video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo',
            'video/webm', 'video/x-flv', 'video/x-ms-wmv', 'video/x-matroska'
        ]
        if v not in valid_types:
            raise ValueError(f'Invalid content type. Supported: {", ".join(valid_types)}')
        return v
    
    @validator('description')
    def validate_description(cls, v):
        if v is not None and v.strip() == '':
            return None
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "file_name": "viral_video.mp4",
                "file_size": 52428800,
                "content_type": "video/mp4",
                "description": "Funny cat video for analysis",
                "duration": 120.5
            }
        }

class VideoUploadResponse(BaseModel):
    success: bool
    message: str
    job_id: str
    file_url: str
    filename: str
    task_id: Optional[str] = Field(None, description="Celery task ID for tracking processing")

class URLProcessResponse(BaseModel):
    success: bool
    message: str
    job_id: str
    url: str

class ViralityScore(BaseModel):
    start_time: float
    end_time: float
    score: float
    reasons: List[str]
    keywords: List[str]
    emotion: str
    engagement_factors: Dict[str, float]

class Hashtag(BaseModel):
    tag: str
    platform: str
    relevance_score: float

class PostingRecommendation(BaseModel):
    platform: str
    optimal_times: List[str]
    format_suggestions: Dict[str, Any]

class ClipResult(BaseModel):
    clip_id: str
    file_path: str
    start_time: int
    duration: int
    overall_virality_score: float
    transcript: str
    virality_scores: List[ViralityScore]
    hashtags: List[Hashtag]
    posting_recommendations: List[PostingRecommendation]

class JobResults(BaseModel):
    original_video_url: str
    clipped_video_url: str
    virality_scores: Dict[str, Dict[str, Any]]
    hashtags: List[str]
    posting_recommendations: Dict[str, Dict[str, Any]]
    transcript: str
    clip_start_time: int
    clip_duration: int

class UserHistory(BaseModel):
    jobs: List[Dict[str, Any]]

class AnalysisSegment(BaseModel):
    id: int
    start_time: float
    end_time: float
    transcript: str
    emotion_scores: Dict[str, float]
    face_count: int
    scene_type: str
    virality_score: float
    engagement_factors: List[str]

class AnalysisResponse(BaseModel):
    id: int
    job_id: int
    overall_virality_score: float
    emotion_analysis: Dict[str, Any]
    face_detection_summary: Dict[str, Any]
    scene_analysis: Dict[str, Any]
    transcript_summary: str
    key_moments: List[Dict[str, Any]]
    segments: List[AnalysisSegment]
    processing_time: float
    created_at: str
    updated_at: str

class GeneratedClip(BaseModel):
    id: int
    job_id: int
    title: str
    description: str
    start_time: float
    end_time: float
    duration: float
    file_path: str
    thumbnail_path: Optional[str] = None
    virality_score: float
    hashtags: List[str]
    posting_recommendations: Dict[str, Any]
    created_at: str

class ClipGenerationRequest(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: float
    end_time: float
    include_captions: bool = True
    quality: str = "high"  # high, medium, low

class UserSettingsResponse(BaseModel):
    id: int
    user_id: int
    default_clip_duration: int
    preferred_quality: str
    auto_generate_hashtags: bool
    notification_preferences: Dict[str, bool]
    export_settings: Dict[str, Any]
    created_at: str
    updated_at: str

class UserSettingsUpdate(BaseModel):
    default_clip_duration: Optional[int] = None
    preferred_quality: Optional[str] = None
    auto_generate_hashtags: Optional[bool] = None
    notification_preferences: Optional[Dict[str, bool]] = None
    export_settings: Optional[Dict[str, Any]] = None

class UserStatsResponse(BaseModel):
    total_jobs: int
    completed_jobs: int
    pending_jobs: int
    failed_jobs: int
    processing_jobs: int
    total_processing_time: float
    average_virality_score: Optional[float]

class UserProfileResponse(BaseModel):
    """User profile response model"""
    id: str = Field(..., description="User UUID")
    email: EmailStr = Field(..., description="User email address")
    display_name: Optional[str] = Field(None, description="User display name")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
    is_active: bool = Field(True, description="Whether user account is active")
    email_verified: bool = Field(False, description="Whether email is verified")
    role: str = Field("user", description="User role")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last profile update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "display_name": "John Doe",
                "photo_url": "https://example.com/photo.jpg",
                "is_active": True,
                "email_verified": True,
                "role": "user",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:00Z",
                "last_login": "2024-01-15T09:00:00Z"
            }
        }

class UserProfileUpdate(BaseModel):
    """User profile update request model"""
    display_name: Optional[str] = Field(None, min_length=2, max_length=100, description="User display name")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
    
    @validator('display_name')
    def validate_display_name(cls, v):
        if v is not None:
            if not v or v.isspace():
                raise ValueError('Display name cannot be empty or whitespace')
            # Remove excessive whitespace
            v = re.sub(r'\s+', ' ', v.strip())
            # Check for inappropriate content (basic filter)
            inappropriate_words = ['admin', 'root', 'system', 'null', 'undefined']
            if any(word in v.lower() for word in inappropriate_words):
                raise ValueError('Display name contains restricted words')
        return v
    
    @validator('photo_url')
    def validate_photo_url(cls, v):
        if v is not None and v.strip():
            # Basic URL validation
            if not v.startswith(('http://', 'https://')):
                raise ValueError('Photo URL must be a valid HTTP/HTTPS URL')
            if len(v) > 500:
                raise ValueError('Photo URL too long (max 500 characters)')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "display_name": "John Doe",
                "photo_url": "https://example.com/new-photo.jpg"
            }
        }

class AuthResponse(BaseModel):
    """Authentication response model."""
    user: UserProfileResponse
    tokens: TokenResponse

class ForgotPasswordRequest(BaseModel):
    """Password reset request"""
    email: EmailStr = Field(..., description="Email address to send reset link")
    
    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }

class ResetPasswordRequest(BaseModel):
    """Password reset confirmation request"""
    token: str = Field(..., description="Password reset token", min_length=1)
    new_password: str = Field(..., description="New password", min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "new_password": "NewSecurePass123"
            }
        }

class PasswordResetResponse(BaseModel):
    """Password reset response"""
    message: str = Field(..., description="Response message")
    success: bool = Field(..., description="Whether the operation was successful")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "Password reset email sent successfully",
                "success": True
            }
        }

# Enhanced validation models for comprehensive input validation

class UserCreateRequest(BaseModel):
    """Comprehensive user creation validation model"""
    email: EmailStr = Field(..., description="Valid email address")
    display_name: str = Field(..., min_length=2, max_length=100, description="User display name")
    auth_id: str = Field(..., min_length=1, max_length=128, description="Authentication provider ID")
    photo_url: Optional[HttpUrl] = Field(None, description="Profile photo URL")
    
    @validator('display_name')
    def validate_display_name(cls, v):
        if not v or v.isspace():
            raise ValueError('Display name cannot be empty or whitespace')
        # Remove excessive whitespace
        v = re.sub(r'\s+', ' ', v.strip())
        # Check for inappropriate content (basic filter)
        inappropriate_words = ['admin', 'root', 'system', 'null', 'undefined']
        if any(word in v.lower() for word in inappropriate_words):
            raise ValueError('Display name contains restricted words')
        return v
    
    @validator('auth_id')
    def validate_auth_id(cls, v):
        if not v or v.isspace():
            raise ValueError('Auth ID cannot be empty')
        # Basic format validation for common auth providers
        if not re.match(r'^[a-zA-Z0-9|_.-]+$', v):
            raise ValueError('Auth ID contains invalid characters')
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "display_name": "John Doe",
                "auth_id": "auth0|123456789",
                "photo_url": "https://example.com/photo.jpg"
            }
        }

class UserUpdateRequest(BaseModel):
    """User profile update validation model"""
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    photo_url: Optional[HttpUrl] = Field(None)
    
    @validator('display_name')
    def validate_display_name(cls, v):
        if v is not None:
            if not v or v.isspace():
                raise ValueError('Display name cannot be empty or whitespace')
            v = re.sub(r'\s+', ' ', v.strip())
        return v

class VideoAnalysisRequest(BaseModel):
    """Comprehensive video analysis request validation"""
    video_url: Optional[HttpUrl] = Field(None, description="URL of video to analyze")
    video_file_id: Optional[str] = Field(None, description="ID of uploaded video file")
    analysis_types: List[Literal["speech", "scene", "emotion", "face", "viral_score"]] = Field(
        default=["viral_score"], description="Types of analysis to perform"
    )
    target_platforms: List[PlatformEnum] = Field(
        default=[PlatformEnum.TIKTOK], description="Target platforms for optimization"
    )
    clip_duration_range: Optional[Dict[str, int]] = Field(
        default={"min": 15, "max": 60}, description="Desired clip duration range in seconds"
    )
    quality_preference: QualityEnum = Field(default=QualityEnum.HIGH, description="Processing quality")
    
    @model_validator(mode='after')
    def validate_video_source(self):
        if not self.video_url and not self.video_file_id:
            raise ValueError('Either video_url or video_file_id must be provided')
        if self.video_url and self.video_file_id:
            raise ValueError('Only one of video_url or video_file_id should be provided')
        return self
    
    @validator('analysis_types')
    def validate_analysis_types(cls, v):
        if not v:
            raise ValueError('At least one analysis type must be specified')
        if len(v) > 5:
            raise ValueError('Maximum 5 analysis types allowed')
        return list(set(v))  # Remove duplicates
    
    @validator('clip_duration_range')
    def validate_duration_range(cls, v):
        if v:
            min_duration = v.get('min', 15)
            max_duration = v.get('max', 60)
            if min_duration < 5 or min_duration > 300:
                raise ValueError('Minimum duration must be between 5 and 300 seconds')
            if max_duration < 10 or max_duration > 600:
                raise ValueError('Maximum duration must be between 10 and 600 seconds')
            if min_duration >= max_duration:
                raise ValueError('Minimum duration must be less than maximum duration')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "analysis_types": ["viral_score", "emotion", "scene"],
                "target_platforms": ["tiktok", "instagram"],
                "clip_duration_range": {"min": 15, "max": 45},
                "quality_preference": "high"
            }
        }

class ErrorResponse(BaseModel):
    """Standardized error response model"""
    error: bool = Field(default=True, description="Indicates this is an error response")
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid input parameters",
                "details": {
                    "field": "video_url",
                    "issue": "URL format is invalid"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789"
            }
        }

class ValidationErrorDetail(BaseModel):
    """Detailed validation error information"""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    invalid_value: Optional[Any] = Field(None, description="The invalid value that was provided")
    constraint: Optional[str] = Field(None, description="The constraint that was violated")

class ValidationErrorResponse(ErrorResponse):
    """Specialized error response for validation failures"""
    error_code: str = Field(default="VALIDATION_ERROR")
    validation_errors: List[ValidationErrorDetail] = Field(..., description="List of validation errors")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "validation_errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format",
                        "invalid_value": "not-an-email",
                        "constraint": "email_format"
                    }
                ],
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

class PaginationParams(BaseModel):
    """Standardized pagination parameters"""
    page: int = Field(default=1, ge=1, le=1000, description="Page number (1-based)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Sort order")
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        if v:
            # Allow only alphanumeric characters and underscores
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
                raise ValueError('Invalid sort field name')
        return v
    
    def get_offset(self) -> int:
        """Calculate offset for database queries"""
        return (self.page - 1) * self.limit

class PaginatedResponse(BaseModel):
    """Standardized paginated response wrapper"""
    items: List[Any] = Field(..., description="List of items for current page")
    total_count: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")
    
    @model_validator(mode='after')
    def calculate_pagination_info(self):
        self.total_pages = max(1, (self.total_count + self.limit - 1) // self.limit)
        self.has_next = self.page < self.total_pages
        self.has_prev = self.page > 1
        return self

class HealthCheckResponse(BaseModel):
    """Health check response model"""
    status: Literal["healthy", "degraded", "unhealthy"] = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., ge=0, description="System uptime in seconds")
    database_status: Literal["connected", "disconnected", "error"] = Field(..., description="Database connection status")
    storage_status: Literal["available", "unavailable", "error"] = Field(..., description="Storage service status")
    queue_status: Literal["operational", "degraded", "failed"] = Field(..., description="Job queue status")
    active_jobs: int = Field(..., ge=0, description="Number of currently active jobs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "1.0.0",
                "uptime_seconds": 86400.0,
                "database_status": "connected",
                "storage_status": "available",
                "queue_status": "operational",
                "active_jobs": 5
            }
        }

# Enhanced Hashtag and Posting Recommendation Models

class HashtagCategoryEnum(str, Enum):
    """Hashtag category enumeration"""
    TRENDING = "trending"
    NICHE = "niche"
    COMMUNITY = "community"
    BRANDED = "branded"
    LOCATION = "location"
    EMOTION = "emotion"
    EVERGREEN = "evergreen"
    SEASONAL = "seasonal"

class CompetitionLevelEnum(str, Enum):
    """Competition level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class EnhancedHashtag(BaseModel):
    """Enhanced hashtag model with detailed analytics"""
    tag: str = Field(..., description="Hashtag without # symbol", min_length=1, max_length=100)
    platform: PlatformEnum = Field(..., description="Target platform")
    category: HashtagCategoryEnum = Field(..., description="Hashtag category")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Content relevance score")
    engagement_prediction: float = Field(..., ge=0.0, le=1.0, description="Predicted engagement rate")
    trend_score: float = Field(..., ge=0.0, le=1.0, description="Current trending score")
    competition_level: CompetitionLevelEnum = Field(..., description="Competition level")
    estimated_reach: Optional[int] = Field(None, ge=0, description="Estimated reach potential")
    usage_frequency: Optional[int] = Field(None, ge=0, description="How often this hashtag is used")
    performance_metrics: Optional[Dict[str, float]] = Field(None, description="Historical performance data")
    reasoning: Optional[str] = Field(None, description="Why this hashtag was recommended")
    viral_alignment_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Alignment with viral factors")
    
    @validator('tag')
    def validate_hashtag(cls, v):
        # Remove # if present and validate format
        v = v.lstrip('#').strip()
        if not v:
            raise ValueError('Hashtag cannot be empty')
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Hashtag can only contain letters, numbers, and underscores')
        return v.lower()
    
    class Config:
        json_schema_extra = {
            "example": {
                "tag": "fyp",
                "platform": "tiktok",
                "category": "trending",
                "relevance_score": 0.85,
                "engagement_prediction": 0.12,
                "trend_score": 0.95,
                "competition_level": "high",
                "estimated_reach": 1000000,
                "usage_frequency": 50000,
                "performance_metrics": {
                    "avg_likes": 1500,
                    "avg_shares": 200,
                    "avg_comments": 150
                },
                "reasoning": "High trending score and strong engagement potential",
                "viral_alignment_score": 0.88
            }
        }

class OptimalPostingTime(BaseModel):
    """Optimal posting time recommendation"""
    day_of_week: Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] = Field(
        ..., description="Day of the week"
    )
    hour: int = Field(..., ge=0, le=23, description="Hour in 24-hour format")
    minute: int = Field(default=0, ge=0, le=59, description="Minute")
    timezone: str = Field(default="UTC", description="Timezone for the posting time")
    engagement_score: float = Field(..., ge=0.0, le=1.0, description="Expected engagement score")
    audience_size: float = Field(..., ge=0.0, le=1.0, description="Relative audience size")
    competition_level: CompetitionLevelEnum = Field(..., description="Content competition level at this time")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in this recommendation")
    reasoning: Optional[str] = Field(None, description="Explanation for this time recommendation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "day_of_week": "tuesday",
                "hour": 19,
                "minute": 30,
                "timezone": "UTC",
                "engagement_score": 0.85,
                "audience_size": 0.75,
                "competition_level": "medium",
                "confidence_score": 0.92,
                "reasoning": "Peak audience activity with moderate competition"
            }
        }

class PostingFrequencyRecommendation(BaseModel):
    """Posting frequency recommendations"""
    posts_per_day: float = Field(..., ge=0.1, le=10.0, description="Recommended posts per day")
    posts_per_week: float = Field(..., ge=0.5, le=50.0, description="Recommended posts per week")
    optimal_spacing_hours: float = Field(..., ge=1.0, le=168.0, description="Optimal hours between posts")
    peak_days: List[str] = Field(..., description="Best days of the week for posting")
    avoid_days: List[str] = Field(default_factory=list, description="Days to avoid posting")
    seasonal_adjustments: Optional[Dict[str, float]] = Field(None, description="Seasonal posting adjustments")
    
    class Config:
        json_schema_extra = {
            "example": {
                "posts_per_day": 1.5,
                "posts_per_week": 10.5,
                "optimal_spacing_hours": 8.0,
                "peak_days": ["tuesday", "wednesday", "thursday"],
                "avoid_days": ["sunday"],
                "seasonal_adjustments": {
                    "holiday_season": 1.2,
                    "summer": 0.9
                }
            }
        }

class EnhancedPostingRecommendation(BaseModel):
    """Enhanced posting recommendation with detailed insights"""
    platform: PlatformEnum = Field(..., description="Target platform")
    optimal_times: List[OptimalPostingTime] = Field(..., description="List of optimal posting times")
    posting_frequency: PostingFrequencyRecommendation = Field(..., description="Frequency recommendations")
    content_format_suggestions: List[str] = Field(..., description="Recommended content formats")
    engagement_tips: List[str] = Field(..., description="Platform-specific engagement tips")
    audience_insights: Dict[str, Any] = Field(..., description="Target audience insights")
    performance_predictions: Dict[str, float] = Field(..., description="Expected performance metrics")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in recommendations")
    
    class Config:
        json_schema_extra = {
            "example": {
                "platform": "tiktok",
                "optimal_times": [
                    {
                        "day_of_week": "tuesday",
                        "hour": 19,
                        "minute": 30,
                        "timezone": "UTC",
                        "engagement_score": 0.85,
                        "audience_size": 0.75,
                        "competition_level": "medium",
                        "confidence_score": 0.92
                    }
                ],
                "posting_frequency": {
                    "posts_per_day": 1.5,
                    "posts_per_week": 10.5,
                    "optimal_spacing_hours": 8.0,
                    "peak_days": ["tuesday", "wednesday", "thursday"]
                },
                "content_format_suggestions": ["short_video", "trending_audio", "text_overlay"],
                "engagement_tips": ["Use trending sounds", "Add captions", "Include call-to-action"],
                "audience_insights": {
                    "primary_age_group": "18-24",
                    "peak_activity": "evening",
                    "interests": ["entertainment", "music", "comedy"]
                },
                "performance_predictions": {
                    "expected_engagement_rate": 0.08,
                    "estimated_reach": 10000,
                    "viral_potential": 0.15
                },
                "confidence_score": 0.87
            }
        }

class HashtagRecommendationRequest(BaseModel):
    """Request model for hashtag recommendations"""
    content_description: str = Field(..., min_length=10, max_length=1000, description="Description of the content")
    platforms: List[PlatformEnum] = Field(..., min_items=1, max_items=3, description="Target platforms")
    target_audience: Optional[str] = Field(None, max_length=500, description="Target audience description")
    content_category: Optional[str] = Field(None, max_length=100, description="Content category")
    viral_score_data: Optional[Dict[str, Any]] = Field(None, description="Viral scoring data for enhancement")
    max_hashtags_per_platform: int = Field(default=10, ge=3, le=30, description="Maximum hashtags per platform")
    include_performance_predictions: bool = Field(default=True, description="Include performance predictions")
    
    @validator('content_description')
    def validate_content_description(cls, v):
        if not v or v.isspace():
            raise ValueError('Content description cannot be empty')
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_description": "Funny cooking video showing how to make pasta with unexpected ingredients",
                "platforms": ["tiktok", "instagram"],
                "target_audience": "Young adults interested in cooking and comedy",
                "content_category": "entertainment",
                "max_hashtags_per_platform": 8,
                "include_performance_predictions": True
            }
        }

class PostingTimeRequest(BaseModel):
    """Request model for posting time optimization"""
    platforms: List[PlatformEnum] = Field(..., min_items=1, max_items=3, description="Target platforms")
    target_audience: Optional[str] = Field(None, max_length=500, description="Target audience description")
    content_type: Optional[str] = Field(None, max_length=100, description="Type of content")
    geographic_region: Optional[str] = Field(None, max_length=100, description="Geographic region")
    historical_performance: Optional[Dict[str, Any]] = Field(None, description="Historical performance data")
    timezone: str = Field(default="UTC", description="Preferred timezone for recommendations")
    max_recommendations_per_platform: int = Field(default=5, ge=1, le=10, description="Max recommendations per platform")
    
    class Config:
        json_schema_extra = {
            "example": {
                "platforms": ["tiktok", "instagram"],
                "target_audience": "Young professionals",
                "content_type": "educational",
                "geographic_region": "North America",
                "timezone": "America/New_York",
                "max_recommendations_per_platform": 3
            }
        }

class ComprehensiveRecommendationResponse(BaseModel):
    """Comprehensive recommendation response"""
    success: bool = Field(default=True, description="Whether the request was successful")
    hashtag_recommendations: Dict[str, List[EnhancedHashtag]] = Field(..., description="Hashtag recommendations by platform")
    posting_recommendations: Dict[str, EnhancedPostingRecommendation] = Field(..., description="Posting recommendations by platform")
    performance_insights: Dict[str, Dict[str, float]] = Field(..., description="Performance insights by platform")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    analysis_summary: Dict[str, Any] = Field(..., description="Summary of the analysis performed")
    confidence_scores: Dict[str, float] = Field(..., description="Confidence scores by platform")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "hashtag_recommendations": {
                    "tiktok": [
                        {
                            "tag": "fyp",
                            "platform": "tiktok",
                            "category": "trending",
                            "relevance_score": 0.85,
                            "engagement_prediction": 0.12,
                            "trend_score": 0.95,
                            "competition_level": "high"
                        }
                    ]
                },
                "posting_recommendations": {
                    "tiktok": {
                        "platform": "tiktok",
                        "optimal_times": [],
                        "posting_frequency": {},
                        "content_format_suggestions": [],
                        "engagement_tips": [],
                        "audience_insights": {},
                        "performance_predictions": {},
                        "confidence_score": 0.87
                    }
                },
                "performance_insights": {
                    "tiktok": {
                        "expected_engagement_rate": 0.08,
                        "viral_potential": 0.15
                    }
                },
                "generated_at": "2024-01-15T10:30:00Z",
                "analysis_summary": {
                    "platforms_analyzed": ["tiktok"],
                    "content_category": "entertainment"
                },
                "confidence_scores": {
                    "tiktok": 0.87
                }
            }
        }