#!/usr/bin/env python3
"""
Enhanced structured logging configuration with correlation IDs and error tracking.
Provides comprehensive logging capabilities for production monitoring and debugging.
"""

import logging
import logging.config
import json
import sys
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextvars import ContextVar
from functools import wraps
import asyncio
import time
from pathlib import Path

from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException

from .config import get_settings

# Context variables for correlation tracking
correlation_id: ContextVar[str] = ContextVar('correlation_id', default=None)
user_id: ContextVar[str] = ContextVar('user_id', default=None)
request_id: ContextVar[str] = ContextVar('request_id', default=None)
session_id: ContextVar[str] = ContextVar('session_id', default=None)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID and other context to log records."""
    
    def filter(self, record):
        record.correlation_id = correlation_id.get(None)
        record.user_id = user_id.get(None)
        record.request_id = request_id.get(None)
        record.session_id = session_id.get(None)
        record.service_name = "clip-generation-api"
        record.environment = get_settings().ENVIRONMENT
        return True


class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        # Add log level
        log_record['level'] = record.levelname
        
        # Add logger name
        log_record['logger'] = record.name
        
        # Add correlation tracking
        if hasattr(record, 'correlation_id') and record.correlation_id:
            log_record['correlation_id'] = record.correlation_id
        
        if hasattr(record, 'user_id') and record.user_id:
            log_record['user_id'] = record.user_id
        
        if hasattr(record, 'request_id') and record.request_id:
            log_record['request_id'] = record.request_id
        
        if hasattr(record, 'session_id') and record.session_id:
            log_record['session_id'] = record.session_id
        
        # Add service information
        if hasattr(record, 'service_name'):
            log_record['service'] = record.service_name
        
        if hasattr(record, 'environment'):
            log_record['environment'] = record.environment
        
        # Add exception information if present
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from the log record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'getMessage', 'exc_info',
                          'exc_text', 'stack_info', 'correlation_id', 'user_id',
                          'request_id', 'session_id', 'service_name', 'environment']:
                if not key.startswith('_'):
                    log_record[key] = value


class ErrorTracker:
    """Track and aggregate errors for monitoring."""
    
    def __init__(self):
        self.error_counts = {}
        self.error_details = []
        self.max_error_details = 1000
    
    def track_error(self, error_type: str, error_message: str, 
                   context: Dict[str, Any] = None):
        """Track an error occurrence."""
        # Increment error count
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        # Store error details
        error_detail = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': error_type,
            'message': error_message,
            'correlation_id': correlation_id.get(None),
            'user_id': user_id.get(None),
            'request_id': request_id.get(None),
            'context': context or {}
        }
        
        self.error_details.append(error_detail)
        
        # Keep only recent errors
        if len(self.error_details) > self.max_error_details:
            self.error_details = self.error_details[-self.max_error_details:]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics."""
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_counts_by_type': self.error_counts.copy(),
            'recent_errors': self.error_details[-10:],  # Last 10 errors
            'unique_error_types': len(self.error_counts)
        }
    
    def clear_errors(self):
        """Clear error tracking data."""
        self.error_counts.clear()
        self.error_details.clear()


# Global error tracker instance
error_tracker = ErrorTracker()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging with correlation tracking."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        corr_id = str(uuid.uuid4())
        req_id = str(uuid.uuid4())
        
        # Set context variables
        correlation_id.set(corr_id)
        request_id.set(req_id)
        
        # Extract user ID from request if available
        user_id_value = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id_value = str(request.state.user.id)
            user_id.set(user_id_value)
        
        # Extract session ID from headers or cookies
        session_id_value = request.headers.get('X-Session-ID') or request.cookies.get('session_id')
        if session_id_value:
            session_id.set(session_id_value)
        
        # Log request
        start_time = time.time()
        logger = logging.getLogger(__name__)
        
        logger.info(
            "Request started",
            extra={
                'event_type': 'request_started',
                'method': request.method,
                'url': str(request.url),
                'path': request.url.path,
                'query_params': dict(request.query_params),
                'headers': dict(request.headers),
                'client_ip': request.client.host if request.client else None,
                'user_agent': request.headers.get('user-agent'),
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    'event_type': 'request_completed',
                    'status_code': response.status_code,
                    'processing_time_ms': round(processing_time * 1000, 2),
                    'response_size': response.headers.get('content-length'),
                }
            )
            
            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = corr_id
            response.headers['X-Request-ID'] = req_id
            
            return response
            
        except Exception as e:
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Track error
            error_tracker.track_error(
                error_type=type(e).__name__,
                error_message=str(e),
                context={
                    'method': request.method,
                    'path': request.url.path,
                    'processing_time_ms': round(processing_time * 1000, 2)
                }
            )
            
            # Log error
            logger.error(
                "Request failed",
                extra={
                    'event_type': 'request_failed',
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'processing_time_ms': round(processing_time * 1000, 2),
                },
                exc_info=True
            )
            
            raise


class StructuredLogger:
    """Enhanced logger with structured logging capabilities."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log with additional context."""
        extra = kwargs.pop('extra', {})
        
        # Add any additional keyword arguments as extra fields
        for key, value in kwargs.items():
            if key not in ['exc_info', 'stack_info']:
                extra[key] = value
        
        self.logger.log(level, message, extra=extra, **{k: v for k, v in kwargs.items() if k in ['exc_info', 'stack_info']})
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        # Track error
        error_tracker.track_error(
            error_type=kwargs.get('error_type', 'UnknownError'),
            error_message=message,
            context=kwargs.get('context', {})
        )
        
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        # Track critical error
        error_tracker.track_error(
            error_type=kwargs.get('error_type', 'CriticalError'),
            error_message=message,
            context=kwargs.get('context', {})
        )
        
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def log_event(self, event_type: str, message: str, **kwargs):
        """Log a structured event."""
        self.info(message, event_type=event_type, **kwargs)
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics."""
        self.info(
            f"Performance: {operation}",
            event_type='performance',
            operation=operation,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_business_event(self, event: str, entity_type: str, entity_id: str, **kwargs):
        """Log business events."""
        self.info(
            f"Business event: {event}",
            event_type='business_event',
            business_event=event,
            entity_type=entity_type,
            entity_id=entity_id,
            **kwargs
        )
    
    def log_security_event(self, event: str, severity: str = 'medium', **kwargs):
        """Log security events."""
        log_level = logging.WARNING if severity in ['medium', 'high'] else logging.INFO
        if severity == 'critical':
            log_level = logging.CRITICAL
        
        self._log_with_context(
            log_level,
            f"Security event: {event}",
            event_type='security_event',
            security_event=event,
            severity=severity,
            **kwargs
        )


def log_function_call(include_args: bool = False, include_result: bool = False):
    """Decorator to log function calls."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = StructuredLogger(func.__module__)
            start_time = time.time()
            
            # Log function entry
            log_data = {
                'function': func.__name__,
                'module': func.__module__,
            }
            
            if include_args:
                log_data['args'] = str(args)
                log_data['kwargs'] = str(kwargs)
            
            logger.debug(f"Function {func.__name__} started", **log_data)
            
            try:
                result = await func(*args, **kwargs)
                
                # Log successful completion
                duration_ms = (time.time() - start_time) * 1000
                log_data['duration_ms'] = round(duration_ms, 2)
                log_data['status'] = 'success'
                
                if include_result:
                    log_data['result'] = str(result)[:500]  # Truncate long results
                
                logger.debug(f"Function {func.__name__} completed", **log_data)
                return result
                
            except Exception as e:
                # Log error
                duration_ms = (time.time() - start_time) * 1000
                log_data['duration_ms'] = round(duration_ms, 2)
                log_data['status'] = 'error'
                log_data['error_type'] = type(e).__name__
                log_data['error_message'] = str(e)
                
                logger.error(
                    f"Function {func.__name__} failed",
                    exc_info=True,
                    **log_data
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = StructuredLogger(func.__module__)
            start_time = time.time()
            
            # Log function entry
            log_data = {
                'function': func.__name__,
                'module': func.__module__,
            }
            
            if include_args:
                log_data['args'] = str(args)
                log_data['kwargs'] = str(kwargs)
            
            logger.debug(f"Function {func.__name__} started", **log_data)
            
            try:
                result = func(*args, **kwargs)
                
                # Log successful completion
                duration_ms = (time.time() - start_time) * 1000
                log_data['duration_ms'] = round(duration_ms, 2)
                log_data['status'] = 'success'
                
                if include_result:
                    log_data['result'] = str(result)[:500]  # Truncate long results
                
                logger.debug(f"Function {func.__name__} completed", **log_data)
                return result
                
            except Exception as e:
                # Log error
                duration_ms = (time.time() - start_time) * 1000
                log_data['duration_ms'] = round(duration_ms, 2)
                log_data['status'] = 'error'
                log_data['error_type'] = type(e).__name__
                log_data['error_message'] = str(e)
                
                logger.error(
                    f"Function {func.__name__} failed",
                    exc_info=True,
                    **log_data
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """Setup structured logging configuration."""
    settings = get_settings()
    
    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'structured': {
                '()': StructuredFormatter,
                'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
            },
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'filters': {
            'correlation_id': {
                '()': CorrelationIdFilter
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'structured' if settings.ENVIRONMENT == 'production' else 'simple',
                'filters': ['correlation_id'],
                'stream': sys.stdout
            }
        },
        'loggers': {
            '': {  # Root logger
                'level': log_level,
                'handlers': ['console'],
                'propagate': False
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'uvicorn.access': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'sqlalchemy': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            }
        }
    }
    
    # Add file handler if log file is specified
    if log_file:
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level,
            'formatter': 'structured',
            'filters': ['correlation_id'],
            'filename': log_file,
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5
        }
        
        # Add file handler to all loggers
        for logger_name in config['loggers']:
            config['loggers'][logger_name]['handlers'].append('file')
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Log startup message
    logger = StructuredLogger(__name__)
    logger.info(
        "Logging system initialized",
        event_type='system_startup',
        log_level=log_level,
        environment=settings.ENVIRONMENT,
        log_file=log_file
    )


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


def set_correlation_id(corr_id: str):
    """Set correlation ID for current context."""
    correlation_id.set(corr_id)


def set_user_context(user_id_value: str, session_id_value: str = None):
    """Set user context for logging."""
    user_id.set(user_id_value)
    if session_id_value:
        session_id.set(session_id_value)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id.get(None)


def get_error_summary() -> Dict[str, Any]:
    """Get error tracking summary."""
    return error_tracker.get_error_summary()


def clear_error_tracking():
    """Clear error tracking data."""
    error_tracker.clear_errors()


# Context manager for temporary correlation ID
class CorrelationContext:
    """Context manager for setting temporary correlation ID."""
    
    def __init__(self, corr_id: str = None):
        self.corr_id = corr_id or str(uuid.uuid4())
        self.token = None
    
    def __enter__(self):
        self.token = correlation_id.set(self.corr_id)
        return self.corr_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            correlation_id.reset(self.token)


# Async context manager for correlation ID
class AsyncCorrelationContext:
    """Async context manager for setting temporary correlation ID."""
    
    def __init__(self, corr_id: str = None):
        self.corr_id = corr_id or str(uuid.uuid4())
        self.token = None
    
    async def __aenter__(self):
        self.token = correlation_id.set(self.corr_id)
        return self.corr_id
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            correlation_id.reset(self.token)