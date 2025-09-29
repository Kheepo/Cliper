#!/usr/bin/env python3
"""
Shared Utility Functions for Video Processing System

Provides common utility functions for file handling, validation,
formatting, and other operations used across the application.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import aiofiles
import structlog
from PIL import Image

from .types import VideoMetadata, VideoFormat, ErrorType
from .exceptions import VideoProcessingError, ValidationError


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: Optional[str] = None
) -> None:
    """Setup structured logging configuration."""
    
    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
            *([logging.FileHandler(log_file)] if log_file else [])
        ]
    )


def generate_id(prefix: str = "") -> str:
    """Generate a unique identifier."""
    unique_id = str(uuid.uuid4())
    return f"{prefix}{unique_id}" if prefix else unique_id


def generate_short_id(length: int = 8) -> str:
    """Generate a short unique identifier."""
    return str(uuid.uuid4()).replace("-", "")[:length]


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"


def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human-readable string."""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters."""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    # Ensure not empty
    if not filename:
        filename = "untitled"
    
    return filename


def calculate_file_hash(file_path: Union[str, Path], algorithm: str = "sha256") -> str:
    """Calculate hash of a file."""
    hash_func = hashlib.new(algorithm)
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


async def calculate_file_hash_async(
    file_path: Union[str, Path], 
    algorithm: str = "sha256"
) -> str:
    """Calculate hash of a file asynchronously."""
    hash_func = hashlib.new(algorithm)
    
    async with aiofiles.open(file_path, "rb") as f:
        while chunk := await f.read(4096):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def validate_video_file(file_path: Union[str, Path]) -> bool:
    """Validate if file is a supported video format."""
    if not os.path.exists(file_path):
        return False
    
    # Check file extension
    ext = Path(file_path).suffix.lower().lstrip('.')
    supported_formats = [fmt.value for fmt in VideoFormat]
    
    if ext not in supported_formats:
        return False
    
    # Check file size (not empty)
    if os.path.getsize(file_path) == 0:
        return False
    
    return True


def get_video_info(file_path: Union[str, Path]) -> VideoMetadata:
    """Extract video metadata using ffprobe."""
    if not validate_video_file(file_path):
        raise ValidationError(f"Invalid video file: {file_path}")
    
    try:
        # Use ffprobe to get video information
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        
        data = json.loads(result.stdout)
        
        # Find video stream
        video_stream = None
        audio_stream = None
        
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream
        
        if not video_stream:
            raise ValidationError("No video stream found")
        
        # Extract metadata
        format_info = data.get("format", {})
        file_path_obj = Path(file_path)
        
        metadata = VideoMetadata(
            filename=file_path_obj.name,
            file_size=int(format_info.get("size", 0)),
            duration=float(format_info.get("duration", 0)),
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=eval(video_stream.get("r_frame_rate", "0/1")),
            bitrate=int(format_info.get("bit_rate", 0)),
            format=VideoFormat(file_path_obj.suffix.lower().lstrip('.')),
            codec=video_stream.get("codec_name", "unknown"),
            audio_codec=audio_stream.get("codec_name") if audio_stream else None,
            audio_channels=int(audio_stream.get("channels", 0)) if audio_stream else None,
            audio_sample_rate=int(audio_stream.get("sample_rate", 0)) if audio_stream else None,
            created_at=datetime.fromtimestamp(os.path.getctime(file_path)),
            file_hash=calculate_file_hash(file_path)
        )
        
        return metadata
        
    except subprocess.CalledProcessError as e:
        raise VideoProcessingError(f"Failed to analyze video: {e}")
    except subprocess.TimeoutExpired:
        raise VideoProcessingError("Video analysis timed out")
    except json.JSONDecodeError as e:
        raise VideoProcessingError(f"Failed to parse video metadata: {e}")
    except Exception as e:
        raise VideoProcessingError(f"Unexpected error analyzing video: {e}")


def create_thumbnail(
    video_path: Union[str, Path],
    output_path: Union[str, Path],
    timestamp: float = 5.0,
    width: int = 320,
    height: int = 180
) -> bool:
    """Create a thumbnail from video at specified timestamp."""
    try:
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-ss", str(timestamp),
            "-vframes", "1",
            "-vf", f"scale={width}:{height}",
            "-y",  # Overwrite output file
            str(output_path)
        ]
        
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=30
        )
        
        return os.path.exists(output_path)
        
    except subprocess.CalledProcessError:
        return False
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Exception, ...] = (Exception,)
):
    """Decorator for retrying functions with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        break
                    
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    logger = structlog.get_logger()
                    logger.warning(
                        "Function failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e)
                    )
                    
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        break
                    
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    logger = structlog.get_logger()
                    logger.warning(
                        "Function failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e)
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def measure_time(func: Callable) -> Callable:
    """Decorator to measure function execution time."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            execution_time = time.time() - start_time
            logger = structlog.get_logger()
            logger.info(
                "Function execution completed",
                function=func.__name__,
                execution_time=execution_time
            )
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            execution_time = time.time() - start_time
            logger = structlog.get_logger()
            logger.info(
                "Function execution completed",
                function=func.__name__,
                execution_time=execution_time
            )
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def safe_json_loads(data: str, default: Any = None) -> Any:
    """Safely parse JSON string."""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """Safely serialize data to JSON string."""
    try:
        return json.dumps(data, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return default


def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure directory exists, create if it doesn't."""
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def cleanup_temp_files(directory: Union[str, Path], max_age_hours: int = 24) -> int:
    """Clean up temporary files older than specified age."""
    directory = Path(directory)
    if not directory.exists():
        return 0
    
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    cleaned_count = 0
    
    for file_path in directory.rglob("*"):
        if file_path.is_file():
            try:
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_time:
                    file_path.unlink()
                    cleaned_count += 1
            except (OSError, PermissionError):
                continue
    
    return cleaned_count


def get_available_disk_space(path: Union[str, Path]) -> int:
    """Get available disk space in bytes."""
    try:
        stat = os.statvfs(path)
        return stat.f_bavail * stat.f_frsize
    except (OSError, AttributeError):
        # Fallback for Windows
        import shutil
        return shutil.disk_usage(path).free


def check_system_resources() -> Dict[str, Any]:
    """Check system resource availability."""
    import psutil
    
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": {
            path: psutil.disk_usage(path).percent
            for path in ["/", "/tmp"] if os.path.exists(path)
        },
        "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None,
        "process_count": len(psutil.pids())
    }


def validate_url(url: str) -> bool:
    """Validate URL format."""
    import re
    
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain...
        r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # host...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(url))


def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    return bool(email_pattern.match(email))


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length."""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text using simple frequency analysis."""
    import re
    from collections import Counter
    
    # Simple keyword extraction
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    
    # Filter out common stop words
    stop_words = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
        'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'among', 'this',
        'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'can', 'shall'
    }
    
    filtered_words = [word for word in words if word not in stop_words]
    
    # Get most common words
    word_counts = Counter(filtered_words)
    keywords = [word for word, count in word_counts.most_common(max_keywords)]
    
    return keywords


def parse_time_string(time_str: str) -> float:
    """Parse time string (HH:MM:SS or MM:SS or SS) to seconds."""
    parts = time_str.split(':')
    
    if len(parts) == 1:
        # Just seconds
        return float(parts[0])
    elif len(parts) == 2:
        # MM:SS
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    elif len(parts) == 3:
        # HH:MM:SS
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    else:
        raise ValueError(f"Invalid time format: {time_str}")


def format_timestamp(timestamp: float) -> str:
    """Format timestamp to HH:MM:SS.mmm format."""
    hours = int(timestamp // 3600)
    minutes = int((timestamp % 3600) // 60)
    seconds = timestamp % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def is_development() -> bool:
    """Check if running in development environment."""
    return os.getenv("ENVIRONMENT", "development").lower() == "development"


def is_production() -> bool:
    """Check if running in production environment."""
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def get_environment() -> str:
    """Get current environment name."""
    return os.getenv("ENVIRONMENT", "development").lower()


class ProgressTracker:
    """Simple progress tracking utility."""
    
    def __init__(self, total: int, description: str = ""):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
    
    def update(self, increment: int = 1) -> None:
        """Update progress."""
        self.current = min(self.current + increment, self.total)
    
    def set_progress(self, current: int) -> None:
        """Set current progress."""
        self.current = min(max(current, 0), self.total)
    
    @property
    def percentage(self) -> float:
        """Get progress percentage."""
        if self.total == 0:
            return 100.0
        return (self.current / self.total) * 100
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time
    
    @property
    def estimated_total_time(self) -> Optional[float]:
        """Estimate total time based on current progress."""
        if self.current == 0:
            return None
        
        elapsed = self.elapsed_time
        return (elapsed / self.current) * self.total
    
    @property
    def estimated_remaining_time(self) -> Optional[float]:
        """Estimate remaining time."""
        total_time = self.estimated_total_time
        if total_time is None:
            return None
        
        return max(0, total_time - self.elapsed_time)
    
    def __str__(self) -> str:
        """String representation of progress."""
        desc = f"{self.description}: " if self.description else ""
        return f"{desc}{self.current}/{self.total} ({self.percentage:.1f}%)"


class RateLimiter:
    """Simple rate limiter implementation."""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    def is_allowed(self) -> bool:
        """Check if a call is allowed."""
        now = time.time()
        
        # Remove old calls outside the time window
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        # Check if we can make another call
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        
        return False
    
    def time_until_next_call(self) -> float:
        """Get time until next call is allowed."""
        if len(self.calls) < self.max_calls:
            return 0.0
        
        oldest_call = min(self.calls)
        return max(0.0, self.time_window - (time.time() - oldest_call))