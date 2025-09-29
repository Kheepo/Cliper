"""Configuration utilities for the video processing system.

This module provides:
- Celery configuration management
- FFmpeg configuration and path detection
- Environment variable handling
- Service configuration validation
- Performance tuning parameters
"""

import os
import shutil
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
import platform

logger = logging.getLogger(__name__)


@dataclass
class FFmpegConfig:
    """FFmpeg configuration."""
    ffmpeg_path: str
    ffprobe_path: str
    available: bool
    version: Optional[str] = None
    gpu_acceleration: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ffmpeg_path': self.ffmpeg_path,
            'ffprobe_path': self.ffprobe_path,
            'available': self.available,
            'version': self.version,
            'gpu_acceleration': self.gpu_acceleration
        }


@dataclass
class CeleryConfig:
    """Celery configuration."""
    broker_url: str
    result_backend: str
    task_serializer: str = 'json'
    accept_content: List[str] = None
    result_serializer: str = 'json'
    timezone: str = 'UTC'
    enable_utc: bool = True
    
    # Worker configuration
    worker_concurrency: int = 4
    worker_prefetch_multiplier: int = 1
    worker_max_tasks_per_child: int = 100
    worker_max_memory_per_child: int = 200000  # 200MB in KB
    
    # Task configuration (updated for 1-hour video support)
    task_soft_time_limit: int = 3300  # 55 minutes (for 1-hour videos)
    task_time_limit: int = 3600  # 1 hour (for 1-hour videos)
    task_acks_late: bool = True
    task_reject_on_worker_lost: bool = True
    
    # Result configuration
    result_expires: int = 3600  # 1 hour
    result_compression: str = 'gzip'
    
    # Route configuration
    task_routes: Dict[str, Dict[str, str]] = None
    
    def __post_init__(self):
        if self.accept_content is None:
            self.accept_content = ['json']
        
        if self.task_routes is None:
            self.task_routes = {
                'api.services.enhanced_celery_tasks.process_video_clips_task': {
                    'queue': 'video_processing'
                },
                'api.services.enhanced_celery_tasks.process_single_clip_task': {
                    'queue': 'clip_processing'
                },
                'api.services.enhanced_celery_tasks.health_check_task': {
                    'queue': 'health_checks'
                }
            }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'broker_url': self.broker_url,
            'result_backend': self.result_backend,
            'task_serializer': self.task_serializer,
            'accept_content': self.accept_content,
            'result_serializer': self.result_serializer,
            'timezone': self.timezone,
            'enable_utc': self.enable_utc,
            'worker_concurrency': self.worker_concurrency,
            'worker_prefetch_multiplier': self.worker_prefetch_multiplier,
            'worker_max_tasks_per_child': self.worker_max_tasks_per_child,
            'worker_max_memory_per_child': self.worker_max_memory_per_child,
            'task_soft_time_limit': self.task_soft_time_limit,
            'task_time_limit': self.task_time_limit,
            'task_acks_late': self.task_acks_late,
            'task_reject_on_worker_lost': self.task_reject_on_worker_lost,
            'result_expires': self.result_expires,
            'result_compression': self.result_compression,
            'task_routes': self.task_routes
        }


@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str = 'localhost'
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    max_connections: int = 50
    
    def get_url(self) -> str:
        """Get Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'password': self.password,
            'socket_timeout': self.socket_timeout,
            'socket_connect_timeout': self.socket_connect_timeout,
            'retry_on_timeout': self.retry_on_timeout,
            'health_check_interval': self.health_check_interval,
            'max_connections': self.max_connections
        }


@dataclass
class ProcessingConfig:
    """Video processing configuration."""
    # Resource limits
    max_memory_usage: float = 0.8  # 80% of available memory
    max_disk_usage: float = 0.9  # 90% of available disk
    max_concurrent_clips: int = 2  # Reduced for 1-hour videos
    max_video_size_mb: int = 2048  # 2GB (supports 1-hour videos)
    
    # Processing timeouts (increased for 1-hour videos)
    clip_processing_timeout: int = 1800  # 30 minutes
    transcription_timeout: int = 900  # 15 minutes
    encoding_timeout: int = 1800  # 30 minutes
    
    # Quality settings
    default_bitrate: int = 4000  # kbps
    default_fps: int = 30
    audio_bitrate: int = 128  # kbps
    audio_sample_rate: int = 44100
    
    # Chunk processing (optimized for 1-hour videos)
    chunk_duration: int = 60  # seconds
    overlap_duration: int = 2  # seconds
    max_chunks_in_memory: int = 3  # Limit memory usage for long videos
    chunk_processing_batch_size: int = 5  # Process chunks in batches
    
    # Temporary file management
    temp_dir: Optional[str] = None
    cleanup_temp_files: bool = True
    temp_file_ttl: int = 3600  # 1 hour
    
    def __post_init__(self):
        if self.temp_dir is None:
            self.temp_dir = os.path.join(os.getcwd(), 'temp')
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'max_memory_usage': self.max_memory_usage,
            'max_disk_usage': self.max_disk_usage,
            'max_concurrent_clips': self.max_concurrent_clips,
            'max_video_size_mb': self.max_video_size_mb,
            'clip_processing_timeout': self.clip_processing_timeout,
            'transcription_timeout': self.transcription_timeout,
            'encoding_timeout': self.encoding_timeout,
            'default_bitrate': self.default_bitrate,
            'default_fps': self.default_fps,
            'audio_bitrate': self.audio_bitrate,
            'audio_sample_rate': self.audio_sample_rate,
            'chunk_duration': self.chunk_duration,
            'overlap_duration': self.overlap_duration,
            'max_chunks_in_memory': self.max_chunks_in_memory,
            'chunk_processing_batch_size': self.chunk_processing_batch_size,
            'temp_dir': self.temp_dir,
            'cleanup_temp_files': self.cleanup_temp_files,
            'temp_file_ttl': self.temp_file_ttl
        }


def detect_ffmpeg_path() -> FFmpegConfig:
    """Detect FFmpeg installation and configuration."""
    
    # Project-specific FFmpeg installation (highest priority)
    # Get the project root directory (parent of api directory)
    api_dir = os.path.dirname(os.path.dirname(__file__))
    project_root = os.path.dirname(api_dir)
    project_ffmpeg = os.path.join(project_root, 'ffmpeg-8.0-essentials_build', 'bin', 'ffmpeg.exe')
    project_ffprobe = os.path.join(project_root, 'ffmpeg-8.0-essentials_build', 'bin', 'ffprobe.exe')
    
    if os.path.exists(project_ffmpeg) and os.path.exists(project_ffprobe):
        return FFmpegConfig(
            ffmpeg_path=project_ffmpeg,
            ffprobe_path=project_ffprobe,
            available=True,
            version='8.0'
        )
    
    # Common FFmpeg installation paths
    common_paths = [
        # Windows
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
        # Linux/macOS
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        '/opt/homebrew/bin/ffmpeg',
        '/snap/bin/ffmpeg'
    ]
    
    # Check environment variable first
    ffmpeg_path = os.environ.get('FFMPEG_PATH')
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        ffprobe_path = ffmpeg_path.replace('ffmpeg', 'ffprobe')
        if os.path.exists(ffprobe_path):
            return FFmpegConfig(
                ffmpeg_path=ffmpeg_path,
                ffprobe_path=ffprobe_path,
                available=True
            )
    
    # Check system PATH
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        ffprobe_path = shutil.which('ffprobe')
        if ffprobe_path:
            return FFmpegConfig(
                ffmpeg_path=ffmpeg_path,
                ffprobe_path=ffprobe_path,
                available=True
            )
    
    # Check common installation paths
    for path in common_paths:
        if os.path.exists(path):
            ffprobe_path = path.replace('ffmpeg', 'ffprobe')
            if platform.system() == 'Windows':
                ffprobe_path = ffprobe_path.replace('.exe', '.exe')
            
            if os.path.exists(ffprobe_path):
                return FFmpegConfig(
                    ffmpeg_path=path,
                    ffprobe_path=ffprobe_path,
                    available=True
                )
    
    # FFmpeg not found
    logger.warning("FFmpeg not found in system PATH or common locations")
    return FFmpegConfig(
        ffmpeg_path='ffmpeg',  # Fallback to system PATH
        ffprobe_path='ffprobe',
        available=False
    )


def get_redis_config() -> RedisConfig:
    """Get Redis configuration from environment."""
    
    return RedisConfig(
        host=os.environ.get('REDIS_HOST', 'localhost'),
        port=int(os.environ.get('REDIS_PORT', '6379')),
        db=int(os.environ.get('REDIS_DB', '0')),
        password=os.environ.get('REDIS_PASSWORD'),
        socket_timeout=int(os.environ.get('REDIS_SOCKET_TIMEOUT', '5')),
        socket_connect_timeout=int(os.environ.get('REDIS_CONNECT_TIMEOUT', '5')),
        retry_on_timeout=os.environ.get('REDIS_RETRY_ON_TIMEOUT', 'true').lower() == 'true',
        health_check_interval=int(os.environ.get('REDIS_HEALTH_CHECK_INTERVAL', '30')),
        max_connections=int(os.environ.get('REDIS_MAX_CONNECTIONS', '50'))
    )


def get_celery_config() -> CeleryConfig:
    """Get Celery configuration from environment."""
    
    redis_config = get_redis_config()
    redis_url = redis_config.get_url()
    
    return CeleryConfig(
        broker_url=os.environ.get('CELERY_BROKER_URL', redis_url),
        result_backend=os.environ.get('CELERY_RESULT_BACKEND', redis_url),
        worker_concurrency=int(os.environ.get('CELERY_WORKER_CONCURRENCY', '2')),  # Reduced for 1-hour videos
        worker_prefetch_multiplier=int(os.environ.get('CELERY_WORKER_PREFETCH', '1')),
        worker_max_tasks_per_child=int(os.environ.get('CELERY_MAX_TASKS_PER_CHILD', '50')),  # Reduced for memory management
        worker_max_memory_per_child=int(os.environ.get('CELERY_MAX_MEMORY_PER_CHILD', '500000')),  # Increased to 500MB
        task_soft_time_limit=int(os.environ.get('CELERY_SOFT_TIME_LIMIT', '3300')),  # 55 minutes for 1-hour videos
        task_time_limit=int(os.environ.get('CELERY_TIME_LIMIT', '3600')),  # 1 hour for 1-hour videos
        result_expires=int(os.environ.get('CELERY_RESULT_EXPIRES', '7200'))  # 2 hours for longer processing
    )


def get_processing_config() -> ProcessingConfig:
    """Get processing configuration from environment."""
    
    return ProcessingConfig(
        max_memory_usage=float(os.environ.get('MAX_MEMORY_USAGE', '0.8')),
        max_disk_usage=float(os.environ.get('MAX_DISK_USAGE', '0.9')),
        max_concurrent_clips=int(os.environ.get('MAX_CONCURRENT_CLIPS', '2')),
        max_video_size_mb=int(os.environ.get('MAX_VIDEO_SIZE_MB', '2048')),
        clip_processing_timeout=int(os.environ.get('PROCESSING_TIMEOUT', '1800')),
        transcription_timeout=int(os.environ.get('TRANSCRIPTION_TIMEOUT', '900')),
        encoding_timeout=int(os.environ.get('ENCODING_TIMEOUT', '1800')),
        default_bitrate=int(os.environ.get('DEFAULT_BITRATE', '4000')),
        default_fps=int(os.environ.get('DEFAULT_FPS', '30')),
        audio_bitrate=int(os.environ.get('AUDIO_BITRATE', '128')),
        audio_sample_rate=int(os.environ.get('AUDIO_SAMPLE_RATE', '44100')),
        chunk_duration=int(os.environ.get('CHUNK_DURATION', '60')),
        overlap_duration=int(os.environ.get('OVERLAP_DURATION', '2')),
        max_chunks_in_memory=int(os.environ.get('MAX_CHUNKS_IN_MEMORY', '3')),
        chunk_processing_batch_size=int(os.environ.get('CHUNK_PROCESSING_BATCH_SIZE', '5')),
        temp_dir=os.environ.get('TEMP_DIR'),
        cleanup_temp_files=os.environ.get('CLEANUP_TEMP_FILES', 'true').lower() == 'true',
        temp_file_ttl=int(os.environ.get('TEMP_FILE_TTL', '3600'))
    )


def validate_configuration() -> Dict[str, Any]:
    """Validate all configuration settings."""
    
    validation_results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'configs': {}
    }
    
    try:
        # Validate FFmpeg
        ffmpeg_config = detect_ffmpeg_path()
        validation_results['configs']['ffmpeg'] = ffmpeg_config.to_dict()
        
        if not ffmpeg_config.available:
            validation_results['errors'].append(
                "FFmpeg not found. Please install FFmpeg and ensure it's in your PATH."
            )
            validation_results['valid'] = False
        
        # Validate Redis
        redis_config = get_redis_config()
        validation_results['configs']['redis'] = redis_config.to_dict()
        
        # Validate Celery
        celery_config = get_celery_config()
        validation_results['configs']['celery'] = celery_config.to_dict()
        
        # Validate Processing
        processing_config = get_processing_config()
        validation_results['configs']['processing'] = processing_config.to_dict()
        
        # Check temp directory
        temp_dir = processing_config.temp_dir
        if not os.path.exists(temp_dir):
            try:
                os.makedirs(temp_dir, exist_ok=True)
                validation_results['warnings'].append(
                    f"Created temporary directory: {temp_dir}"
                )
            except Exception as e:
                validation_results['errors'].append(
                    f"Cannot create temporary directory {temp_dir}: {e}"
                )
                validation_results['valid'] = False
        
        # Check environment variables
        required_env_vars = [
            'OPENAI_API_KEY',
            'SUPABASE_URL',
            'SUPABASE_ANON_KEY'
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            validation_results['warnings'].append(
                f"Missing environment variables: {', '.join(missing_vars)}"
            )
        
        # Performance warnings
        if celery_config.worker_concurrency > 8:
            validation_results['warnings'].append(
                f"High worker concurrency ({celery_config.worker_concurrency}) may cause resource exhaustion"
            )
        
        if processing_config.max_memory_usage > 0.9:
            validation_results['warnings'].append(
                f"High memory usage limit ({processing_config.max_memory_usage}) may cause system instability"
            )
        
    except Exception as e:
        validation_results['valid'] = False
        validation_results['errors'].append(f"Configuration validation failed: {e}")
    
    return validation_results


def get_system_info() -> Dict[str, Any]:
    """Get system information for configuration optimization."""
    
    import psutil
    
    try:
        # CPU information
        cpu_count = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)
        
        # Memory information
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024 ** 3)
        memory_available_gb = memory.available / (1024 ** 3)
        
        # Disk information
        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024 ** 3)
        disk_free_gb = disk.free / (1024 ** 3)
        
        return {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'architecture': platform.architecture()[0],
            'cpu_count_logical': cpu_count,
            'cpu_count_physical': cpu_count_physical,
            'memory_total_gb': round(memory_total_gb, 2),
            'memory_available_gb': round(memory_available_gb, 2),
            'memory_usage_percent': memory.percent,
            'disk_total_gb': round(disk_total_gb, 2),
            'disk_free_gb': round(disk_free_gb, 2),
            'disk_usage_percent': disk.percent
        }
        
    except ImportError:
        logger.warning("psutil not available, system info limited")
        return {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'architecture': platform.architecture()[0]
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {'error': str(e)}


def optimize_configuration_for_system() -> Dict[str, Any]:
    """Optimize configuration based on system capabilities."""
    
    system_info = get_system_info()
    optimizations = {
        'recommendations': [],
        'optimized_config': {}
    }
    
    try:
        cpu_count = system_info.get('cpu_count_logical', 4)
        memory_gb = system_info.get('memory_total_gb', 8)
        
        # Optimize Celery worker concurrency
        if cpu_count >= 8:
            recommended_concurrency = min(cpu_count - 2, 8)  # Leave 2 cores for system
        elif cpu_count >= 4:
            recommended_concurrency = cpu_count - 1
        else:
            recommended_concurrency = 2
        
        optimizations['optimized_config']['celery_worker_concurrency'] = recommended_concurrency
        optimizations['recommendations'].append(
            f"Set Celery worker concurrency to {recommended_concurrency} based on {cpu_count} CPU cores"
        )
        
        # Optimize memory settings
        if memory_gb >= 16:
            max_memory_usage = 0.8
            worker_memory_limit = 300000  # 300MB
        elif memory_gb >= 8:
            max_memory_usage = 0.7
            worker_memory_limit = 200000  # 200MB
        else:
            max_memory_usage = 0.6
            worker_memory_limit = 150000  # 150MB
        
        optimizations['optimized_config']['max_memory_usage'] = max_memory_usage
        optimizations['optimized_config']['worker_max_memory_per_child'] = worker_memory_limit
        optimizations['recommendations'].append(
            f"Set memory usage limit to {max_memory_usage*100}% based on {memory_gb}GB RAM"
        )
        
        # Optimize concurrent clips
        if memory_gb >= 16 and cpu_count >= 8:
            max_concurrent_clips = 6
        elif memory_gb >= 8 and cpu_count >= 4:
            max_concurrent_clips = 4
        else:
            max_concurrent_clips = 2
        
        optimizations['optimized_config']['max_concurrent_clips'] = max_concurrent_clips
        optimizations['recommendations'].append(
            f"Set max concurrent clips to {max_concurrent_clips} based on system resources"
        )
        
    except Exception as e:
        optimizations['error'] = str(e)
    
    return optimizations


# Global configuration instances
_ffmpeg_config = None
_redis_config = None
_celery_config = None
_processing_config = None


def get_ffmpeg_config() -> FFmpegConfig:
    """Get cached FFmpeg configuration."""
    global _ffmpeg_config
    if _ffmpeg_config is None:
        _ffmpeg_config = detect_ffmpeg_path()
    return _ffmpeg_config


def get_cached_redis_config() -> RedisConfig:
    """Get cached Redis configuration."""
    global _redis_config
    if _redis_config is None:
        _redis_config = get_redis_config()
    return _redis_config


def get_cached_celery_config() -> CeleryConfig:
    """Get cached Celery configuration."""
    global _celery_config
    if _celery_config is None:
        _celery_config = get_celery_config()
    return _celery_config


def get_cached_processing_config() -> ProcessingConfig:
    """Get cached processing configuration."""
    global _processing_config
    if _processing_config is None:
        _processing_config = get_processing_config()
    return _processing_config


@dataclass
class OpenAIConfig:
    """OpenAI configuration."""
    api_key: str
    model: str = 'gpt-3.5-turbo'
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'api_key': self.api_key,
            'model': self.model,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'timeout': self.timeout
        }


def get_openai_config() -> OpenAIConfig:
    """Get OpenAI configuration from environment."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return OpenAIConfig(
        api_key=api_key,
        model=os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo'),
        max_tokens=int(os.environ.get('OPENAI_MAX_TOKENS', '4000')),
        temperature=float(os.environ.get('OPENAI_TEMPERATURE', '0.7')),
        timeout=int(os.environ.get('OPENAI_TIMEOUT', '30'))
    )


def reload_configuration():
    """Reload all configuration from environment."""
    global _ffmpeg_config, _redis_config, _celery_config, _processing_config
    _ffmpeg_config = None
    _redis_config = None
    _celery_config = None
    _processing_config = None
    
    logger.info("Configuration reloaded from environment")