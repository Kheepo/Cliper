"""Enhanced structured logging with correlation IDs.

Provides:
- Correlation ID tracking across requests
- Structured JSON logging
- Performance metrics logging
- Error tracking and alerting
- Request/response logging
- Security event logging
"""

import json
import time
import uuid
import logging
import traceback
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict

from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(str, Enum):
    """Event types for structured logging."""
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    SYSTEM = "system"
    AUDIT = "audit"


# Context variables for correlation tracking
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
session_id: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


@dataclass
class LogContext:
    """Logging context information."""
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PerformanceMetrics:
    """Performance metrics for logging."""
    duration_ms: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    db_queries: Optional[int] = None
    cache_hits: Optional[int] = None
    cache_misses: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SecurityEvent:
    """Security event information."""
    event_type: str
    severity: str
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}


class CorrelationFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with correlation ID support."""
    
    def add_fields(self, log_record, record, message_dict):
        """Add correlation and context fields to log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Add correlation context
        context = LogContext(
            correlation_id=correlation_id.get(),
            user_id=user_id.get(),
            session_id=session_id.get(),
            request_id=request_id.get()
        )
        
        log_record.update(context.to_dict())
        
        # Add service information
        log_record['service'] = 'clip-generation-api'
        log_record['version'] = '1.0.0'
        
        # Add thread/process info
        log_record['thread_id'] = record.thread
        log_record['process_id'] = record.process
        
        # Add source location
        log_record['source'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName,
            'module': record.module
        }


class EnhancedLogger:
    """Enhanced logger with structured logging and correlation support."""
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))
        self._metrics = defaultdict(int)
        self._error_patterns = defaultdict(int)
        
        # Clear existing handlers to prevent duplicates
        self.logger.handlers.clear()
        
        # Create formatters
        json_formatter = CorrelationFormatter()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(json_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for all logs
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / "app.log")
        file_handler.setFormatter(json_formatter)
        self.logger.addHandler(file_handler)
        
        # Error-specific file handler
        error_handler = logging.FileHandler(log_dir / "errors.log")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)
        self.logger.addHandler(error_handler)
        
        # Set log level based on environment
        env = os.getenv('ENVIRONMENT', 'development')
        if env == 'production':
            self.logger.setLevel(logging.INFO)
        elif env == 'development':
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.WARNING)
    
    def _ensure_log_directory(self) -> bool:
        """Ensure log directory exists."""
        try:
            Path("logs").mkdir(exist_ok=True)
            return True
        except Exception:
            return False
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """Internal logging method."""
        extra = {
            'event_type': kwargs.pop('event_type', EventType.SYSTEM),
            **kwargs
        }
        
        getattr(self.logger, level.value.lower())(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception."""
        if error:
            # Track error patterns for analysis
            error_key = f"{type(error).__name__}:{str(error)[:100]}"
            self._error_patterns[error_key] += 1
            
            kwargs.update({
                'error_type': type(error).__name__,
                'error_message': str(error),
                'error_module': getattr(error, '__module__', 'unknown'),
                'error_args': getattr(error, 'args', []),
                'traceback': traceback.format_exc(),
                'error_count': self._error_patterns[error_key]
            })
            
            # Add file and line info if available
            if hasattr(error, '__traceback__') and error.__traceback__:
                tb = error.__traceback__
                kwargs.update({
                    'error_file': tb.tb_frame.f_code.co_filename,
                    'error_line': tb.tb_lineno,
                    'error_function': tb.tb_frame.f_code.co_name
                })
        
        self._log(LogLevel.ERROR, message, event_type=EventType.ERROR, **kwargs)
    
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log critical message with optional exception."""
        if error:
            kwargs.update({
                'error_type': type(error).__name__,
                'error_message': str(error),
                'traceback': traceback.format_exc()
            })
        
        self._log(LogLevel.CRITICAL, message, event_type=EventType.ERROR, **kwargs)
    
    def request(self, method: str, path: str, status_code: int, 
                duration_ms: float, **kwargs):
        """Log HTTP request."""
        self._log(
            LogLevel.INFO,
            f"{method} {path} - {status_code}",
            event_type=EventType.REQUEST,
            http_method=method,
            http_path=path,
            http_status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def performance(self, operation: str, metrics: PerformanceMetrics, **kwargs):
        """Log performance metrics."""
        # Track performance metrics for analysis
        metric_key = f"{operation}"
        self._metrics[f"{metric_key}_count"] += 1
        self._metrics[f"{metric_key}_total_duration"] += metrics.duration_ms
        
        # Calculate average duration
        count = self._metrics[f"{metric_key}_count"]
        avg_duration = self._metrics[f"{metric_key}_total_duration"] / count
        
        # Add performance analysis
        performance_data = metrics.to_dict()
        performance_data.update({
            'operation_count': count,
            'average_duration_ms': avg_duration,
            'performance_trend': 'slow' if metrics.duration_ms > avg_duration * 1.5 else 'normal'
        })
        
        # Alert on slow operations
        level = LogLevel.WARNING if metrics.duration_ms > 5000 else LogLevel.INFO  # 5 second threshold
        
        self._log(
            level,
            f"Performance: {operation} ({'SLOW' if level == LogLevel.WARNING else 'OK'})",
            event_type=EventType.PERFORMANCE,
            operation=operation,
            metrics=performance_data,
            **kwargs
        )
    
    def security(self, event: SecurityEvent, **kwargs):
        """Log security event."""
        # Determine log level based on severity
        level_map = {
            'low': LogLevel.INFO,
            'medium': LogLevel.WARNING,
            'high': LogLevel.ERROR,
            'critical': LogLevel.CRITICAL
        }
        level = level_map.get(event.severity, LogLevel.WARNING)
        
        # Track security event patterns
        event_key = f"{event.event_type}:{event.severity}"
        self._metrics[f"security_{event_key}"] += 1
        
        # Add security context
        security_data = event.to_dict()
        security_data.update({
            'event_count': self._metrics[f"security_{event_key}"],
            'risk_level': self._calculate_risk_level(event),
            'requires_investigation': event.severity in ['high', 'critical']
        })
        
        self._log(
            level,
            f"Security event: {event.event_type} [{event.severity.upper()}]",
            event_type=EventType.SECURITY,
            security_event=security_data,
            **kwargs
        )
    
    def _calculate_risk_level(self, event: SecurityEvent) -> str:
        """Calculate risk level based on event type and frequency."""
        high_risk_events = ['brute_force', 'sql_injection', 'xss_attempt', 'unauthorized_access']
        medium_risk_events = ['rate_limit_exceeded', 'invalid_token', 'suspicious_activity']
        
        if event.event_type in high_risk_events:
            return 'high'
        elif event.event_type in medium_risk_events:
            return 'medium'
        return 'low'
    
    def business(self, event: str, data: Dict[str, Any], **kwargs):
        """Log business event."""
        self._log(
            LogLevel.INFO,
            f"Business event: {event}",
            event_type=EventType.BUSINESS,
            business_event=event,
            business_data=data,
            **kwargs
        )
    
    def audit(self, action: str, resource: str, result: str, **kwargs):
        """Log audit event."""
        # Track audit patterns
        audit_key = f"{action}:{resource}"
        self._metrics[f"audit_{audit_key}"] += 1
        
        # Add audit context
        audit_data = {
            'action': action,
            'resource': resource,
            'result': result,
            'action_count': self._metrics[f"audit_{audit_key}"],
            'session_id': session_id.get(),
            'user_id': user_id.get(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Determine log level based on result
        level = LogLevel.WARNING if result in ['failed', 'denied', 'error'] else LogLevel.INFO
        
        self._log(
            level,
            f"Audit: {action} on {resource} - {result.upper()}",
            event_type=EventType.AUDIT,
            audit_data=audit_data,
            **kwargs
        )
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        return dict(self._metrics)
    
    def get_error_patterns(self) -> Dict[str, int]:
        """Get error patterns and their frequencies."""
        return dict(self._error_patterns)
    
    def reset_metrics(self):
        """Reset collected metrics."""
        self._metrics.clear()
        self._error_patterns.clear()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging with correlation IDs."""
    
    def __init__(self, app, logger: Optional[EnhancedLogger] = None):
        super().__init__(app)
        self.logger = logger or get_enhanced_logger("middleware")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with logging."""
        # Generate correlation ID
        correlation_id_value = request.headers.get('X-Correlation-ID') or str(uuid.uuid4())
        request_id_value = str(uuid.uuid4())
        
        # Set context variables
        correlation_id.set(correlation_id_value)
        request_id.set(request_id_value)
        
        # Extract user info if available
        user_id_value = request.headers.get('X-User-ID')
        session_id_value = request.headers.get('X-Session-ID')
        
        if user_id_value:
            user_id.set(user_id_value)
        if session_id_value:
            session_id.set(session_id_value)
        
        # Start timing
        start_time = time.time()
        
        # Log request
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            event_type=EventType.REQUEST,
            http_method=request.method,
            http_path=request.url.path,
            http_query=str(request.url.query) if request.url.query else None,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get('User-Agent'),
            content_length=request.headers.get('Content-Length'),
            content_type=request.headers.get('Content-Type')
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            self.logger.request(
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                response_size=response.headers.get('Content-Length')
            )
            
            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = correlation_id_value
            response.headers['X-Request-ID'] = request_id_value
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            status_code = getattr(e, 'status_code', 500)
            self.logger.error(
                f"Request failed: {request.method} {request.url.path}",
                error=e,
                event_type=EventType.ERROR,
                http_method=request.method,
                http_path=request.url.path,
                http_status_code=status_code,
                duration_ms=duration_ms
            )
            
            raise


class PerformanceLogger:
    """Performance logging utility."""
    
    def __init__(self, logger: Optional[EnhancedLogger] = None):
        self.logger = logger or get_enhanced_logger("performance")
    
    def log_operation(self, operation: str, duration_ms: float, **kwargs):
        """Log operation performance."""
        metrics = PerformanceMetrics(duration_ms=duration_ms, **kwargs)
        self.logger.performance(operation, metrics)
    
    def log_database_query(self, query: str, duration_ms: float, rows_affected: int = 0):
        """Log database query performance."""
        self.logger.performance(
            "database_query",
            PerformanceMetrics(duration_ms=duration_ms),
            query_type=query.split()[0].upper() if query else "UNKNOWN",
            rows_affected=rows_affected
        )
    
    def log_cache_operation(self, operation: str, hit: bool, duration_ms: float):
        """Log cache operation performance."""
        self.logger.performance(
            f"cache_{operation}",
            PerformanceMetrics(
                duration_ms=duration_ms,
                cache_hits=1 if hit else 0,
                cache_misses=0 if hit else 1
            ),
            cache_hit=hit
        )


class SecurityLogger:
    """Security event logging utility."""
    
    def __init__(self, logger: Optional[EnhancedLogger] = None):
        self.logger = logger or get_enhanced_logger("security")
    
    def log_authentication_attempt(self, username: str, success: bool, 
                                 source_ip: str, user_agent: str):
        """Log authentication attempt."""
        event = SecurityEvent(
            event_type="authentication_attempt",
            severity="low" if success else "medium",
            source_ip=source_ip,
            user_agent=user_agent,
            details={"username": username, "success": success}
        )
        self.logger.security(event)
    
    def log_authorization_failure(self, user_id: str, resource: str, 
                                action: str, source_ip: str):
        """Log authorization failure."""
        event = SecurityEvent(
            event_type="authorization_failure",
            severity="medium",
            source_ip=source_ip,
            details={
                "user_id": user_id,
                "resource": resource,
                "action": action
            }
        )
        self.logger.security(event)
    
    def log_suspicious_activity(self, activity_type: str, details: Dict[str, Any],
                              source_ip: str, severity: str = "high"):
        """Log suspicious activity."""
        event = SecurityEvent(
            event_type="suspicious_activity",
            severity=severity,
            source_ip=source_ip,
            details={"activity_type": activity_type, **details}
        )
        self.logger.security(event)
    
    def log_rate_limit_exceeded(self, endpoint: str, source_ip: str, 
                              user_agent: str, limit: int):
        """Log rate limit exceeded."""
        event = SecurityEvent(
            event_type="rate_limit_exceeded",
            severity="medium",
            source_ip=source_ip,
            user_agent=user_agent,
            endpoint=endpoint,
            details={"limit": limit}
        )
        self.logger.security(event)


class BusinessLogger:
    """Business event logging utility."""
    
    def __init__(self, logger: Optional[EnhancedLogger] = None):
        self.logger = logger or get_enhanced_logger("business")
    
    def log_clip_generation_started(self, job_id: str, video_id: str, 
                                  user_id: str, platform: str):
        """Log clip generation started."""
        self.logger.business(
            "clip_generation_started",
            {
                "job_id": job_id,
                "video_id": video_id,
                "user_id": user_id,
                "platform": platform
            }
        )
    
    def log_clip_generation_completed(self, job_id: str, clips_generated: int,
                                    duration_ms: float, success: bool):
        """Log clip generation completed."""
        self.logger.business(
            "clip_generation_completed",
            {
                "job_id": job_id,
                "clips_generated": clips_generated,
                "duration_ms": duration_ms,
                "success": success
            }
        )
    
    def log_user_action(self, action: str, user_id: str, resource_id: str,
                       metadata: Optional[Dict[str, Any]] = None):
        """Log user action."""
        data = {
            "action": action,
            "user_id": user_id,
            "resource_id": resource_id
        }
        
        if metadata:
            data["metadata"] = metadata
        
        self.logger.business("user_action", data)


# Global logger instances
_loggers: Dict[str, EnhancedLogger] = {}
_performance_logger: Optional[PerformanceLogger] = None
_security_logger: Optional[SecurityLogger] = None
_business_logger: Optional[BusinessLogger] = None


def get_enhanced_logger(name: str, level: LogLevel = LogLevel.INFO) -> EnhancedLogger:
    """Get or create enhanced logger instance."""
    if name not in _loggers:
        _loggers[name] = EnhancedLogger(name, level)
    return _loggers[name]


def get_logger(name: str, level: LogLevel = LogLevel.INFO) -> EnhancedLogger:
    """Get or create logger instance (alias for get_enhanced_logger)."""
    return get_enhanced_logger(name, level)


def get_performance_logger() -> PerformanceLogger:
    """Get performance logger instance."""
    global _performance_logger
    if _performance_logger is None:
        _performance_logger = PerformanceLogger()
    return _performance_logger


def get_security_logger() -> SecurityLogger:
    """Get security logger instance."""
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger


def get_business_logger() -> BusinessLogger:
    """Get business logger instance."""
    global _business_logger
    if _business_logger is None:
        _business_logger = BusinessLogger()
    return _business_logger


def set_correlation_context(correlation_id_value: str, user_id_value: Optional[str] = None,
                          session_id_value: Optional[str] = None):
    """Set correlation context for current request."""
    correlation_id.set(correlation_id_value)
    if user_id_value:
        user_id.set(user_id_value)
    if session_id_value:
        session_id.set(session_id_value)


def get_correlation_context() -> LogContext:
    """Get current correlation context."""
    return LogContext(
        correlation_id=correlation_id.get(),
        user_id=user_id.get(),
        session_id=session_id.get(),
        request_id=request_id.get()
    )


# Context manager for performance timing
class performance_timer:
    """Context manager for timing operations."""
    
    def __init__(self, operation: str, logger: Optional[PerformanceLogger] = None):
        self.operation = operation
        self.logger = logger or get_performance_logger()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.logger.log_operation(self.operation, duration_ms)


# Export main components
__all__ = [
    'LogLevel',
    'EventType',
    'LogContext',
    'PerformanceMetrics',
    'SecurityEvent',
    'EnhancedLogger',
    'LoggingMiddleware',
    'PerformanceLogger',
    'SecurityLogger',
    'BusinessLogger',
    'get_enhanced_logger',
    'get_logger',
    'get_performance_logger',
    'get_security_logger',
    'get_business_logger',
    'set_correlation_context',
    'get_correlation_context',
    'performance_timer'
]