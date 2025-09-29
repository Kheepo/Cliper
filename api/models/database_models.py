from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, JSON, Enum as SQLEnum, CheckConstraint, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from typing import Optional

Base = declarative_base()

class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobType(enum.Enum):
    VIDEO_UPLOAD = "video_upload"
    URL_ANALYSIS = "url_analysis"

class AnalysisType(enum.Enum):
    SPEECH = "speech"
    SCENE = "scene"
    EMOTION = "emotion"
    FACE = "face"
    VIRAL_SCORE = "viral_score"

class ClipStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    auth_id = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    photo_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True, index=True)
    
    __table_args__ = (
        CheckConstraint('length(auth_id) > 0', name='check_auth_id_not_empty'),
        CheckConstraint('length(email) > 0', name='check_email_not_empty'),
        CheckConstraint('email LIKE \'%@%\'', name='check_email_format'),
    )
    
    # Relationships
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    job_logs = relationship("JobLog", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', auth_id='{self.auth_id}')>"

class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    preferred_language = Column(String(10), default="en", nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    email_notifications = Column(Boolean, default=True, nullable=False)
    push_notifications = Column(Boolean, default=True, nullable=False)
    auto_process_uploads = Column(Boolean, default=False, nullable=False)
    max_concurrent_jobs = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint('max_concurrent_jobs > 0 AND max_concurrent_jobs <= 10', name='check_max_concurrent_jobs_range'),
        CheckConstraint('length(preferred_language) >= 2', name='check_language_code_length'),
    )
    
    # Relationships
    user = relationship("User", back_populates="settings")
    
    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, language='{self.preferred_language}')>"

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(SQLEnum(JobType), nullable=False, index=True)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # Input data
    video_url = Column(String(1000), nullable=True)  # For URL analysis
    video_file_path = Column(String(500), nullable=True)  # For uploaded files
    video_file_name = Column(String(255), nullable=True)
    video_file_size = Column(Integer, nullable=True)  # Size in bytes
    video_duration = Column(Float, nullable=True)  # Duration in seconds
    
    # Processing metadata
    processing_started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint('retry_count >= 0 AND retry_count <= 5', name='check_retry_count_range'),
        CheckConstraint('video_file_size IS NULL OR video_file_size > 0', name='check_video_file_size_positive'),
        CheckConstraint('video_duration IS NULL OR video_duration > 0', name='check_video_duration_positive'),
        CheckConstraint('processing_completed_at IS NULL OR processing_started_at IS NULL OR processing_completed_at >= processing_started_at', name='check_processing_times_order'),
    )
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    results = relationship("JobResult", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Job(id={self.id}, user_id={self.user_id}, type='{self.job_type.value}', status='{self.status.value}')>"

class JobResult(Base):
    __tablename__ = "job_results"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Analysis results
    virality_score = Column(Float, nullable=True)  # 0.0 to 1.0
    engagement_prediction = Column(Float, nullable=True)
    
    # Recommended hashtags (JSON array)
    hashtags = Column(JSON, nullable=True)  # [{"tag": "#viral", "relevance": 0.95}, ...]
    
    # Posting recommendations
    best_posting_times = Column(JSON, nullable=True)  # [{"time": "18:00", "day": "friday", "score": 0.9}, ...]
    target_audience = Column(JSON, nullable=True)  # {"age_range": "18-24", "interests": [...], ...}
    
    # Generated clips
    clips = Column(JSON, nullable=True)  # [{"start_time": 10.5, "end_time": 25.3, "score": 0.85, "url": "..."}, ...]
    
    # Additional metadata
    processing_time_seconds = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)  # Overall confidence in results
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint('virality_score IS NULL OR (virality_score >= 0.0 AND virality_score <= 1.0)', name='check_virality_score_range'),
        CheckConstraint('engagement_prediction IS NULL OR (engagement_prediction >= 0.0 AND engagement_prediction <= 1.0)', name='check_engagement_prediction_range'),
        CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)', name='check_confidence_score_range'),
        CheckConstraint('processing_time_seconds IS NULL OR processing_time_seconds >= 0', name='check_processing_time_positive'),
        UniqueConstraint('job_id', name='uq_job_result_job_id'),
    )
    
    # Relationships
    job = relationship("Job", back_populates="results")
    
    def __repr__(self):
        return f"<JobResult(id={self.id}, job_id={self.job_id}, virality_score={self.virality_score})>"

class JobLog(Base):
    __tablename__ = "job_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    level = Column(String(20), nullable=False, index=True)  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)  # Additional structured data
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    job = relationship("Job", back_populates="logs")
    user = relationship("User", back_populates="job_logs")
    
    def __repr__(self):
        return f"<JobLog(id={self.id}, job_id={self.job_id}, level='{self.level}')>"

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_type = Column(SQLEnum(AnalysisType), nullable=False, index=True)
    analysis_data = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)', name='check_analysis_confidence_score_range'),
        CheckConstraint('processing_time_ms IS NULL OR processing_time_ms >= 0', name='check_analysis_processing_time_positive'),
        UniqueConstraint('job_id', 'analysis_type', name='uq_analysis_result_job_type'),
    )
    
    # Relationships
    job = relationship("Job")
    segments = relationship("AnalysisSegment", back_populates="analysis", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, job_id={self.job_id}, type='{self.analysis_type.value}')>"

class AnalysisSegment(Base):
    __tablename__ = "analysis_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False, index=True)
    segment_data = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    __table_args__ = (
        CheckConstraint('start_time >= 0', name='check_start_time_positive'),
        CheckConstraint('end_time > start_time', name='check_end_time_after_start'),
        CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)', name='check_segment_confidence_score_range'),
    )
    
    # Relationships
    analysis = relationship("AnalysisResult", back_populates="segments")
    
    def __repr__(self):
        return f"<AnalysisSegment(id={self.id}, analysis_id={self.analysis_id}, start={self.start_time}, end={self.end_time})>"

class GeneratedClip(Base):
    __tablename__ = "generated_clips"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False, index=True)
    duration = Column(Float, nullable=False)
    file_path = Column(String(500), nullable=True)
    file_url = Column(String(1000), nullable=True)
    file_size = Column(Integer, nullable=True)
    format = Column(String(10), nullable=False, default="mp4")
    resolution = Column(String(20), nullable=True)
    bitrate = Column(Integer, nullable=True)
    status = Column(SQLEnum(ClipStatus), default=ClipStatus.PENDING, nullable=False, index=True)
    virality_score = Column(Float, nullable=True)
    engagement_prediction = Column(Float, nullable=True)
    clip_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint('start_time >= 0', name='check_clip_start_time_positive'),
        CheckConstraint('end_time > start_time', name='check_clip_end_time_after_start'),
        CheckConstraint('duration > 0', name='check_clip_duration_positive'),
        CheckConstraint('duration = end_time - start_time', name='check_clip_duration_matches_times'),
        CheckConstraint('file_size IS NULL OR file_size > 0', name='check_clip_file_size_positive'),
        CheckConstraint('bitrate IS NULL OR bitrate > 0', name='check_clip_bitrate_positive'),
        CheckConstraint('virality_score IS NULL OR (virality_score >= 0.0 AND virality_score <= 1.0)', name='check_clip_virality_score_range'),
        CheckConstraint('engagement_prediction IS NULL OR (engagement_prediction >= 0.0 AND engagement_prediction <= 1.0)', name='check_clip_engagement_prediction_range'),
        CheckConstraint('length(title) > 0', name='check_clip_title_not_empty'),
    )
    
    # Relationships
    job = relationship("Job")
    
    def __repr__(self):
        return f"<GeneratedClip(id={self.id}, job_id={self.job_id}, title='{self.title}')>"

class ProcessingLog(Base):
    __tablename__ = "processing_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    operation_type = Column(String(50), nullable=False, index=True)
    status = Column(SQLEnum(ProcessingStatus), nullable=False, index=True)
    progress_percentage = Column(Float, default=0.0, nullable=False)
    current_step = Column(String(100), nullable=True)
    total_steps = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    log_metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint('progress_percentage >= 0.0 AND progress_percentage <= 100.0', name='check_progress_percentage_range'),
        CheckConstraint('total_steps IS NULL OR total_steps > 0', name='check_total_steps_positive'),
        CheckConstraint('completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at', name='check_processing_log_times_order'),
        CheckConstraint('length(operation_type) > 0', name='check_operation_type_not_empty'),
    )
    
    # Relationships
    job = relationship("Job")
    user = relationship("User")
    
    def __repr__(self):
        return f"<ProcessingLog(id={self.id}, job_id={self.job_id}, operation='{self.operation_type}', status='{self.status.value}')>"

# Create indexes for better query performance
from sqlalchemy import Index

# Composite indexes for common queries
Index('idx_jobs_user_status', Job.user_id, Job.status)
Index('idx_jobs_user_created', Job.user_id, Job.created_at.desc())
Index('idx_jobs_status_created', Job.status, Job.created_at.desc())
Index('idx_jobs_user_type_status', Job.user_id, Job.job_type, Job.status)
Index('idx_job_results_job_created', JobResult.job_id, JobResult.created_at.desc())
Index('idx_job_logs_job_level_created', JobLog.job_id, JobLog.level, JobLog.created_at.desc())
Index('idx_job_logs_user_created', JobLog.user_id, JobLog.created_at.desc())
Index('idx_users_auth_email', User.auth_id, User.email)
Index('idx_users_active_created', User.is_active, User.created_at.desc())
Index('idx_analysis_results_job_type', AnalysisResult.job_id, AnalysisResult.analysis_type)
Index('idx_analysis_segments_analysis_time', AnalysisSegment.analysis_id, AnalysisSegment.start_time)
Index('idx_generated_clips_job_status', GeneratedClip.job_id, GeneratedClip.status)
Index('idx_generated_clips_job_score', GeneratedClip.job_id, GeneratedClip.virality_score.desc())
Index('idx_processing_logs_job_status', ProcessingLog.job_id, ProcessingLog.status)
Index('idx_processing_logs_user_operation', ProcessingLog.user_id, ProcessingLog.operation_type)
Index('idx_processing_logs_status_created', ProcessingLog.status, ProcessingLog.created_at.desc())