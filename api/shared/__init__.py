#!/usr/bin/env python3
"""
Shared Utilities for Video Processing System

This module provides common utilities, types, and functions
that are used across different components of the video processing system.
"""

__version__ = "1.0.0"
__author__ = "Video Processing Team"

# Import commonly used utilities
from .types import *
from .utils import *
from .exceptions import *
from .constants import *

__all__ = [
    # Types
    "VideoMetadata",
    "ClipMetadata", 
    "ProcessingStatus",
    "TaskResult",
    "AIServiceResponse",
    "TranscriptionResult",
    "ViralityScore",
    
    # Utilities
    "format_duration",
    "calculate_file_hash",
    "validate_video_file",
    "sanitize_filename",
    "get_video_info",
    "create_thumbnail",
    "setup_logging",
    "retry_with_backoff",
    "measure_time",
    "safe_json_loads",
    "safe_json_dumps",
    
    # Exceptions
    "VideoProcessingError",
    "TranscriptionError",
    "AIServiceError",
    "ValidationError",
    "StorageError",
    "ConfigurationError",
    
    # Constants
    "SUPPORTED_VIDEO_FORMATS",
    "MAX_VIDEO_SIZE",
    "MAX_VIDEO_DURATION",
    "DEFAULT_CLIP_DURATION",
    "PROCESSING_TIMEOUTS",
    "AI_MODEL_CONFIGS",
]