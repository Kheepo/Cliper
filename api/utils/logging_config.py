"""Logging configuration for the clip generation system.

This module provides comprehensive logging setup with:
- Structured logging with JSON format
- Multiple log levels and handlers
- Performance monitoring
- Error tracking
- Request/response logging
- File rotation
- Production-ready configuration
"""

import logging
import logging.config
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import json
import traceback


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'process_id': os.getpid(),
            'thread_id': record.thread,
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'job_id'):
            log_entry['job_id'] = record.job_id
        if hasattr(record, 'clip_id'):
            log_entry['clip_id'] = record.clip_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'duration'):
            log_entry['duration_ms'] = record.duration
        if hasattr(record, 'file_size'):
            log_entry['file_size_bytes'] = record.file_size
        if hasattr(record, 'memory_usage'):
            log_entry['memory_usage_mb'] = record.memory_usage
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add stack info if present
        if record.stack_info:
            log_entry['stack_info'] = record.stack_info
        
        return json.dumps(log_entry, ensure_ascii=False)


class PerformanceFilter(logging.Filter):
    """Filter to add performance metrics to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add performance context to log records."""
        # Add memory usage if available
        try:
            import psutil
            process = psutil.Process()
            record.memory_usage = round(process.memory_info().rss / 1024 / 1024, 2)
        except ImportError:
            pass
        
        return True


class ClipGenerationLogger:
    """Centralized logger for clip generation system."""
    
    def __init__(self, name: str = 'clip_generation'):
        self.logger = logging.getLogger(name)
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        # Create logs directory
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Get log level from environment
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        
        # Configure logging
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'json': {
                    '()': JSONFormatter,
                },
                'simple': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                },
                'detailed': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s'
                }
            },
            'filters': {
                'performance': {
                    '()': PerformanceFilter,
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': log_level,
                    'formatter': 'simple' if os.getenv('ENVIRONMENT') == 'development' else 'json',
                    'stream': sys.stdout,
                    'filters': ['performance']
                },
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'DEBUG',
                    'formatter': 'json',
                    'filename': log_dir / 'clip_generation.log',
                    'maxBytes': 10 * 1024 * 1024,  # 10MB
                    'backupCount': 5,
                    'filters': ['performance']
                },
                'error_file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'ERROR',
                    'formatter': 'json',
                    'filename': log_dir / 'errors.log',
                    'maxBytes': 10 * 1024 * 1024,  # 10MB
                    'backupCount': 10,
                    'filters': ['performance']
                },
                'performance_file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'INFO',
                    'formatter': 'json',
                    'filename': log_dir / 'performance.log',
                    'maxBytes': 10 * 1024 * 1024,  # 10MB
                    'backupCount': 5,
                    'filters': ['performance']
                }
            },
            'loggers': {
                'clip_generation': {
                    'level': 'DEBUG',
                    'handlers': ['console', 'file', 'error_file'],
                    'propagate': False
                },
                'clip_generation.performance': {
                    'level': 'INFO',
                    'handlers': ['performance_file'],
                    'propagate': False
                },
                'celery': {
                    'level': 'INFO',
                    'handlers': ['console', 'file'],
                    'propagate': False
                },
                'ffmpeg': {
                    'level': 'WARNING',
                    'handlers': ['console', 'file'],
                    'propagate': False
                }
            },
            'root': {
                'level': log_level,
                'handlers': ['console']
            }
        }
        
        logging.config.dictConfig(config)
    
    def log_clip_generation_start(self, job_id: str, user_id: str, video_path: str, **kwargs):
        """Log clip generation start."""
        self.logger.info(
            "Clip generation started",
            extra={
                'job_id': job_id,
                'user_id': user_id,
                'video_path': video_path,
                'event': 'clip_generation_start',
                **kwargs
            }
        )
    
    def log_clip_generation_complete(self, job_id: str, user_id: str, clips_count: int, duration: float, **kwargs):
        """Log clip generation completion."""
        self.logger.info(
            f"Clip generation completed: {clips_count} clips in {duration:.2f}s",
            extra={
                'job_id': job_id,
                'user_id': user_id,
                'clips_count': clips_count,
                'duration': duration * 1000,  # Convert to ms
                'event': 'clip_generation_complete',
                **kwargs
            }
        )
    
    def log_clip_generation_error(self, job_id: str, user_id: str, error: Exception, **kwargs):
        """Log clip generation error."""
        self.logger.error(
            f"Clip generation failed: {str(error)}",
            extra={
                'job_id': job_id,
                'user_id': user_id,
                'error_type': type(error).__name__,
                'event': 'clip_generation_error',
                **kwargs
            },
            exc_info=True
        )
    
    def log_single_clip_start(self, clip_id: str, start_time: float, end_time: float, **kwargs):
        """Log single clip generation start."""
        self.logger.debug(
            f"Generating clip {clip_id}: {start_time}s - {end_time}s",
            extra={
                'clip_id': clip_id,
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'event': 'single_clip_start',
                **kwargs
            }
        )
    
    def log_single_clip_complete(self, clip_id: str, output_path: str, file_size: int, duration: float, **kwargs):
        """Log single clip generation completion."""
        self.logger.info(
            f"Clip {clip_id} generated successfully",
            extra={
                'clip_id': clip_id,
                'output_path': output_path,
                'file_size': file_size,
                'duration': duration * 1000,  # Convert to ms
                'event': 'single_clip_complete',
                **kwargs
            }
        )
    
    def log_ffmpeg_command(self, command: list, **kwargs):
        """Log FFmpeg command execution."""
        self.logger.debug(
            f"Executing FFmpeg command: {' '.join(command)}",
            extra={
                'ffmpeg_command': command,
                'event': 'ffmpeg_command',
                **kwargs
            }
        )
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str = '', **kwargs):
        """Log performance metric."""
        perf_logger = logging.getLogger('clip_generation.performance')
        perf_logger.info(
            f"Performance metric: {metric_name} = {value}{unit}",
            extra={
                'metric_name': metric_name,
                'metric_value': value,
                'metric_unit': unit,
                'event': 'performance_metric',
                **kwargs
            }
        )
    
    def log_resource_usage(self, memory_mb: float, disk_usage_gb: float, **kwargs):
        """Log resource usage."""
        self.log_performance_metric('memory_usage', memory_mb, 'MB', **kwargs)
        self.log_performance_metric('disk_usage', disk_usage_gb, 'GB', **kwargs)
    
    def log_websocket_event(self, event_type: str, user_id: str, data: Dict[str, Any], **kwargs):
        """Log WebSocket event."""
        self.logger.debug(
            f"WebSocket event: {event_type}",
            extra={
                'event_type': event_type,
                'user_id': user_id,
                'websocket_data': data,
                'event': 'websocket_event',
                **kwargs
            }
        )
    
    def log_database_operation(self, operation: str, table: str, duration: float, **kwargs):
        """Log database operation."""
        self.logger.debug(
            f"Database {operation} on {table} completed in {duration:.3f}s",
            extra={
                'db_operation': operation,
                'db_table': table,
                'duration': duration * 1000,  # Convert to ms
                'event': 'database_operation',
                **kwargs
            }
        )
    
    def log_api_request(self, method: str, endpoint: str, user_id: Optional[str], duration: float, status_code: int, **kwargs):
        """Log API request."""
        self.logger.info(
            f"{method} {endpoint} - {status_code} ({duration:.3f}s)",
            extra={
                'http_method': method,
                'http_endpoint': endpoint,
                'user_id': user_id,
                'duration': duration * 1000,  # Convert to ms
                'status_code': status_code,
                'event': 'api_request',
                **kwargs
            }
        )


# Global logger instance
logger = ClipGenerationLogger()


def get_logger(name: str = 'clip_generation') -> ClipGenerationLogger:
    """Get logger instance."""
    return ClipGenerationLogger(name)


def setup_logging():
    """Setup logging for the application."""
    # This is called automatically when the module is imported
    pass


# Setup logging when module is imported
setup_logging()