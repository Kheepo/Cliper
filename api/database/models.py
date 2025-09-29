from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    auth_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    job_type = Column(String, nullable=False)  # 'video_upload', 'url_processing'
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0, nullable=False)  # 0-100
    current_step = Column(String, nullable=True)
    estimated_remaining = Column(Float, nullable=True)  # seconds
    
    # Input data
    input_data = Column(JSON, nullable=True)  # Original video URL, file path, etc.
    job_metadata = Column(JSON, nullable=True)  # Additional job metadata
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    results = relationship("JobResult", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_job_user_status', 'user_id', 'status'),
        Index('idx_job_created_at', 'created_at'),
        Index('idx_job_status_updated', 'status', 'updated_at'),
    )

class JobResult(Base):
    __tablename__ = "job_results"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    
    # Video information
    original_video_url = Column(String, nullable=True)
    clipped_video_url = Column(String, nullable=True)
    clip_start_time = Column(Integer, nullable=True)  # seconds
    clip_duration = Column(Integer, nullable=True)  # seconds
    
    # Analysis results
    transcript = Column(Text, nullable=True)
    virality_scores = Column(JSON, nullable=True)  # Dict of niche scores
    hashtags = Column(JSON, nullable=True)  # List of hashtag objects
    posting_recommendations = Column(JSON, nullable=True)  # Platform recommendations
    
    # Overall metrics
    overall_virality_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # File paths
    file_paths = Column(JSON, nullable=True)  # Storage paths for generated files
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    job = relationship("Job", back_populates="results")

class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Profile settings
    profile_name = Column(String, nullable=True)
    profile_bio = Column(Text, nullable=True)
    
    # Video processing preferences
    default_clip_duration = Column(Integer, default=60, nullable=False)  # seconds
    quality_preference = Column(String, default="high", nullable=False)  # low, medium, high
    auto_generate_hashtags = Column(Boolean, default=True, nullable=False)
    
    # Output preferences
    output_format = Column(String, default="mp4", nullable=False)
    include_subtitles = Column(Boolean, default=True, nullable=False)
    watermark_enabled = Column(Boolean, default=False, nullable=False)
    
    # Platform settings
    preferred_platforms = Column(JSON, nullable=True)  # List of platform preferences
    platform_credentials = Column(JSON, nullable=True)  # Encrypted platform API keys
    
    # Notification preferences
    email_notifications = Column(Boolean, default=True, nullable=False)
    job_completion_notifications = Column(Boolean, default=True, nullable=False)
    weekly_summary = Column(Boolean, default=False, nullable=False)
    
    # Appearance
    theme = Column(String, default="light", nullable=False)  # light, dark, auto
    language = Column(String, default="en", nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="settings")

class JobLog(Base):
    __tablename__ = "job_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    
    level = Column(String, nullable=False)  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)  # Additional structured data
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    job = relationship("Job", back_populates="logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_job_log_job_created', 'job_id', 'created_at'),
        Index('idx_job_log_level', 'level'),
    )

class Clip(Base):
    __tablename__ = "clips"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=True, index=True)
    
    # Clip information
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # List of tags
    
    # Video details
    original_video_url = Column(String, nullable=True)
    clip_url = Column(String, nullable=True)
    start_time = Column(Float, nullable=False)  # seconds
    end_time = Column(Float, nullable=False)  # seconds
    duration = Column(Float, nullable=False)  # seconds
    
    # Analysis results
    virality_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    transcript = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)
    
    # Status
    status = Column(String, default="pending", nullable=False)  # pending, processing, completed, failed
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User")
    job = relationship("Job")
    
    # Indexes
    __table_args__ = (
        Index('idx_clip_user_created', 'user_id', 'created_at'),
        Index('idx_clip_status', 'status'),
        Index('idx_clip_virality', 'virality_score'),
    )


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Video information
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    original_url = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    
    # Video metadata
    duration = Column(Float, nullable=True)  # seconds
    file_size = Column(Integer, nullable=True)  # bytes
    format = Column(String, nullable=True)  # mp4, avi, etc.
    resolution = Column(String, nullable=True)  # 1920x1080, etc.
    fps = Column(Float, nullable=True)  # frames per second
    
    # Processing status
    status = Column(String, default="uploaded", nullable=False)  # uploaded, processing, processed, failed
    processing_progress = Column(Integer, default=0, nullable=False)  # 0-100
    
    # Analysis results
    transcript = Column(Text, nullable=True)
    analysis_results = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_video_user_created', 'user_id', 'created_at'),
        Index('idx_video_status', 'status'),
    )