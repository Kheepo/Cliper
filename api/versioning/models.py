"""API versioning models and response structures."""

from typing import Any, Dict, Optional, List, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class APIVersion(str, Enum):
    """Supported API versions."""
    V1 = "v1"
    V2 = "v2"
    LATEST = "latest"

class VersionStatus(str, Enum):
    """Version status indicators."""
    STABLE = "stable"
    BETA = "beta"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"

class VersionInfo(BaseModel):
    """Version information model."""
    version: APIVersion
    status: VersionStatus
    release_date: datetime
    sunset_date: Optional[datetime] = None
    description: str
    breaking_changes: List[str] = Field(default_factory=list)
    new_features: List[str] = Field(default_factory=list)
    bug_fixes: List[str] = Field(default_factory=list)
    documentation_url: Optional[str] = None
    migration_guide_url: Optional[str] = None

class VersionedResponse(BaseModel):
    """Standard versioned API response."""
    api_version: APIVersion
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    data: Any
    meta: Optional[Dict[str, Any]] = None
    links: Optional[Dict[str, str]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ErrorResponse(BaseModel):
    """Standard error response."""
    api_version: APIVersion
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    error: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)
    has_next: bool
    has_prev: bool

class PaginatedResponse(VersionedResponse):
    """Paginated response model."""
    data: List[Any]
    pagination: PaginationMeta

# Video processing models
class VideoUploadRequest(BaseModel):
    """Video upload request model."""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    privacy: str = Field(default="public", pattern="^(public|private|unlisted)$")
    
class VideoUploadResponse(BaseModel):
    """Video upload response model."""
    video_id: str
    upload_url: Optional[str] = None
    status: str
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class VideoProcessingStatus(BaseModel):
    """Video processing status model."""
    video_id: str
    status: str
    progress: float = Field(ge=0, le=100)
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class VideoMetadata(BaseModel):
    """Video metadata model."""
    video_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    format: Optional[str] = None
    resolution: Optional[str] = None
    frame_rate: Optional[float] = None
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# URL processing models
class URLProcessRequest(BaseModel):
    """URL processing request model."""
    url: str = Field(..., pattern=r'^https?://.+')
    options: Optional[Dict[str, Any]] = None
    
class URLProcessResponse(BaseModel):
    """URL processing response model."""
    task_id: str
    url: str
    status: str
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# System health models
class HealthCheck(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    uptime: float
    checks: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SystemMetrics(BaseModel):
    """System metrics model."""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    request_rate: float
    error_rate: float
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Authentication models
class AuthToken(BaseModel):
    """Authentication token model."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None

class UserProfile(BaseModel):
    """User profile model."""
    user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# API rate limiting models
class RateLimitInfo(BaseModel):
    """Rate limit information model."""
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Webhook models
class WebhookEvent(BaseModel):
    """Webhook event model."""
    event_id: str
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    signature: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# API documentation models
class EndpointInfo(BaseModel):
    """API endpoint information."""
    path: str
    method: str
    summary: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    deprecated: bool = False
    version_added: APIVersion
    version_deprecated: Optional[APIVersion] = None
    
class APIDocumentation(BaseModel):
    """Complete API documentation model."""
    title: str
    description: str
    version: str
    base_url: str
    endpoints: List[EndpointInfo]
    models: Dict[str, Any]
    authentication: Dict[str, Any]
    rate_limiting: Dict[str, Any]
    versioning: Dict[str, Any]
    changelog: List[VersionInfo]