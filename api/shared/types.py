#!/usr/bin/env python3
"""
Shared Type Definitions for Video Processing System

Defines common data structures, enums, and type hints
used across the video processing application.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator


class ProcessingStatus(str, Enum):
    """Video processing status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    GENERATING_CLIPS = "generating_clips"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class VideoFormat(str, Enum):
    """Supported video formats."""
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    MKV = "mkv"
    WEBM = "webm"
    FLV = "flv"
    WMV = "wmv"


class AudioFormat(str, Enum):
    """Supported audio formats."""
    MP3 = "mp3"
    WAV = "wav"
    AAC = "aac"
    FLAC = "flac"
    OGG = "ogg"


class AIModel(str, Enum):
    """AI models used in the system."""
    WHISPER_TINY = "whisper-tiny"
    WHISPER_BASE = "whisper-base"
    WHISPER_SMALL = "whisper-small"
    WHISPER_MEDIUM = "whisper-medium"
    WHISPER_LARGE = "whisper-large"
    WHISPER_LARGE_V2 = "whisper-large-v2"
    WHISPER_LARGE_V3 = "whisper-large-v3"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4_MINI = "gpt-4o-mini"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_OPUS = "claude-3-opus"


class ErrorType(str, Enum):
    """Error type classification."""
    VALIDATION_ERROR = "validation_error"
    PROCESSING_ERROR = "processing_error"
    TRANSCRIPTION_ERROR = "transcription_error"
    AI_SERVICE_ERROR = "ai_service_error"
    STORAGE_ERROR = "storage_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    RESOURCE_ERROR = "resource_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class VideoMetadata:
    """Video file metadata."""
    filename: str
    file_size: int
    duration: float
    width: int
    height: int
    fps: float
    bitrate: int
    format: VideoFormat
    codec: str
    audio_codec: Optional[str] = None
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    created_at: Optional[datetime] = None
    file_hash: Optional[str] = None
    thumbnail_path: Optional[str] = None
    
    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio."""
        return self.width / self.height if self.height > 0 else 0
    
    @property
    def resolution(self) -> str:
        """Get resolution string."""
        return f"{self.width}x{self.height}"
    
    @property
    def is_hd(self) -> bool:
        """Check if video is HD quality."""
        return self.height >= 720
    
    @property
    def is_4k(self) -> bool:
        """Check if video is 4K quality."""
        return self.height >= 2160


@dataclass
class ClipMetadata:
    """Video clip metadata."""
    start_time: float
    end_time: float
    duration: float
    title: str
    description: Optional[str] = None
    virality_score: float = 0.0
    confidence_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    transcript_segment: Optional[str] = None
    thumbnail_path: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    
    @property
    def formatted_duration(self) -> str:
        """Get formatted duration string."""
        minutes = int(self.duration // 60)
        seconds = int(self.duration % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def is_viral_worthy(self) -> bool:
        """Check if clip has high virality potential."""
        return self.virality_score >= 0.7 and self.confidence_score >= 0.6


class TranscriptionSegment(BaseModel):
    """Individual transcription segment."""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    speaker: Optional[str] = Field(default=None, description="Speaker identification")
    language: Optional[str] = Field(default=None, description="Detected language")
    
    @validator('start', 'end')
    def validate_times(cls, v):
        if v < 0:
            raise ValueError("Time values must be non-negative")
        return v
    
    @validator('end')
    def validate_end_after_start(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError("End time must be after start time")
        return v
    
    @property
    def duration(self) -> float:
        """Get segment duration."""
        return self.end - self.start


class TranscriptionResult(BaseModel):
    """Complete transcription result."""
    segments: List[TranscriptionSegment] = Field(default_factory=list)
    full_text: str = Field(default="", description="Complete transcribed text")
    language: str = Field(default="en", description="Detected language")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall confidence")
    processing_time: float = Field(default=0.0, description="Processing time in seconds")
    model_used: AIModel = Field(default=AIModel.WHISPER_BASE, description="Model used for transcription")
    word_count: int = Field(default=0, description="Total word count")
    
    @validator('segments')
    def validate_segments_order(cls, v):
        """Ensure segments are in chronological order."""
        for i in range(1, len(v)):
            if v[i].start < v[i-1].end:
                raise ValueError("Segments must be in chronological order")
        return v
    
    @property
    def total_duration(self) -> float:
        """Get total duration of all segments."""
        if not self.segments:
            return 0.0
        return self.segments[-1].end - self.segments[0].start
    
    @property
    def words_per_minute(self) -> float:
        """Calculate words per minute."""
        if self.total_duration == 0:
            return 0.0
        return (self.word_count / self.total_duration) * 60


class ViralityScore(BaseModel):
    """Virality scoring result."""
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall virality score")
    engagement_score: float = Field(..., ge=0.0, le=1.0, description="Engagement potential")
    emotion_score: float = Field(..., ge=0.0, le=1.0, description="Emotional impact")
    content_score: float = Field(..., ge=0.0, le=1.0, description="Content quality")
    timing_score: float = Field(..., ge=0.0, le=1.0, description="Timing relevance")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence")
    reasoning: str = Field(default="", description="Explanation of the score")
    tags: List[str] = Field(default_factory=list, description="Relevant tags")
    
    @property
    def is_viral_worthy(self) -> bool:
        """Check if content has high viral potential."""
        return self.overall_score >= 0.7 and self.confidence >= 0.6
    
    @property
    def score_breakdown(self) -> Dict[str, float]:
        """Get score breakdown."""
        return {
            "engagement": self.engagement_score,
            "emotion": self.emotion_score,
            "content": self.content_score,
            "timing": self.timing_score
        }


class AIServiceResponse(BaseModel):
    """Response from AI service."""
    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_type: Optional[ErrorType] = Field(default=None, description="Error type classification")
    processing_time: float = Field(default=0.0, description="Processing time in seconds")
    model_used: Optional[AIModel] = Field(default=None, description="AI model used")
    tokens_used: Optional[int] = Field(default=None, description="Tokens consumed")
    cost: Optional[float] = Field(default=None, description="API cost in USD")
    
    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.success and self.error is None


class TaskResult(BaseModel):
    """Result of a processing task."""
    task_id: str = Field(..., description="Unique task identifier")
    status: ProcessingStatus = Field(..., description="Task status")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress percentage")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Task result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_type: Optional[ErrorType] = Field(default=None, description="Error type")
    started_at: Optional[datetime] = Field(default=None, description="Task start time")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion time")
    processing_time: Optional[float] = Field(default=None, description="Total processing time")
    retry_count: int = Field(default=0, description="Number of retries")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]
    
    @property
    def is_successful(self) -> bool:
        """Check if task completed successfully."""
        return self.status == ProcessingStatus.COMPLETED and self.error is None
    
    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return self.processing_time


class ProcessingConfig(BaseModel):
    """Configuration for video processing."""
    # Video processing settings
    max_video_size: int = Field(default=500 * 1024 * 1024, description="Max video size in bytes")
    max_video_duration: int = Field(default=3600, description="Max video duration in seconds")
    chunk_duration: int = Field(default=60, description="Chunk duration for processing")
    
    # Clip generation settings
    min_clip_duration: float = Field(default=5.0, description="Minimum clip duration")
    max_clip_duration: float = Field(default=60.0, description="Maximum clip duration")
    default_clip_duration: float = Field(default=30.0, description="Default clip duration")
    max_clips_per_video: int = Field(default=10, description="Maximum clips per video")
    
    # Quality settings
    output_resolution: str = Field(default="1080p", description="Output resolution")
    output_bitrate: str = Field(default="2M", description="Output bitrate")
    output_fps: int = Field(default=30, description="Output frame rate")
    
    # AI settings
    transcription_model: AIModel = Field(default=AIModel.WHISPER_LARGE_V3)
    analysis_model: AIModel = Field(default=AIModel.GPT_4_MINI)
    enable_speaker_detection: bool = Field(default=True)
    enable_emotion_analysis: bool = Field(default=True)
    
    # Performance settings
    max_concurrent_tasks: int = Field(default=4, description="Max concurrent processing tasks")
    task_timeout: int = Field(default=600, description="Task timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    
    # Storage settings
    cleanup_temp_files: bool = Field(default=True)
    keep_original_files: bool = Field(default=True)
    compress_output: bool = Field(default=True)


class SystemMetrics(BaseModel):
    """System performance metrics."""
    cpu_usage: float = Field(..., ge=0.0, le=100.0, description="CPU usage percentage")
    memory_usage: float = Field(..., ge=0.0, le=100.0, description="Memory usage percentage")
    disk_usage: float = Field(..., ge=0.0, le=100.0, description="Disk usage percentage")
    active_tasks: int = Field(..., ge=0, description="Number of active tasks")
    queue_size: int = Field(..., ge=0, description="Task queue size")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate")
    avg_processing_time: float = Field(..., ge=0.0, description="Average processing time")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        return (
            self.cpu_usage < 80.0 and
            self.memory_usage < 80.0 and
            self.disk_usage < 90.0 and
            self.error_rate < 0.1
        )


# Type aliases for common use cases
VideoId = str
TaskId = str
UserId = str
ClipId = str
Timestamp = float
FilePath = str
FileSize = int
Duration = float
Score = float

# Union types
ProcessingResult = Union[TranscriptionResult, List[ClipMetadata], ViralityScore]
AIResponse = Union[TranscriptionResult, ViralityScore, str]
Metadata = Union[VideoMetadata, ClipMetadata]

# Generic response types
ApiResponse = Dict[str, Any]
ErrorResponse = Dict[str, Union[str, int, List[str]]]
SuccessResponse = Dict[str, Any]