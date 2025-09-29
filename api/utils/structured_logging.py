"""Enhanced structured logging with correlation IDs and comprehensive error tracking.

Provides:
- Correlation ID tracking across requests
- Structured JSON logging
- Performance metrics logging
- Error tracking and aggregation
- Request/response logging
- Security event logging
- Business event logging
- Log filtering and sampling
"""

import json
import time
import uuid
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import logging
import logging.handlers
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variables for correlation tracking
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
session_id_var: ContextVar[str] = ContextVar('session_id', default='')


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(str, Enum):
    """Event types for categorizing log entries."""
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    SECURITY = "security"
    BUSINESS = "business"
    PERFORMANCE = "performance"
    SYSTEM = "system"
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"
    WEBSOCKET = "websocket"
    BACKGROUND_TASK = "background_task"


class SecurityEventType(str, Enum):
    """Security event types."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_ACCESS = "data_access"
    ADMIN_ACTION = "admin_action"


@dataclass
class LogContext:
    """Context information for log entries."""
    correlation_id: str = ""
    request_id: str = ""
    user_id: str = ""
    session_id: str = ""
    ip_address: str = ""
    user_agent: str = ""
    endpoint: str = ""
    method: str = ""
    trace_id: str = ""
    span_id: str = ""


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""
    operation: str
    duration_ms: float
    cpu_time_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    db_queries: Optional[int] = None
    cache_hits: Optional[int] = None
    cache_misses: Optional[int] = None
    external_calls: Optional[int] = None


@dataclass
class ErrorDetails:
    """Detailed error information."""
    error_type: str
    error_message: str
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    user_message: Optional[str] = None
    recovery_suggestion: Optional[str] = None


@dataclass
class SecurityEvent:
    """Security event details."""
    event_type: SecurityEventType
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    risk_score: Optional[int] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class BusinessEvent:
    """Business event details."""
    event_name: str
    entity_type: str
    entity_id: str
    action: str
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    value: Optional[float] = None
    currency: Optional[str] = None


class StructuredLogger:
    """Enhanced structured logger with correlation tracking."""
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Console handler with JSON formatter
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=100 * 1024 * 1024,  # 100MB
                backupCount=10
            )
            file_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(file_handler)
        
        # Error aggregation
        self.error_counts: Dict[str, int] = {}
        self.last_errors: List[Dict[str, Any]] = []
    
    def _get_context(self) -> LogContext:
        """Get current logging context."""
        return LogContext(
            correlation_id=correlation_id_var.get(),
            request_id=request_id_var.get(),
            user_id=user_id_var.get(),
            session_id=session_id_var.get()
        )
    
    def _create_log_entry(self, level: LogLevel, message: str, **kwargs) -> Dict[str, Any]:
        """Create a structured log entry."""
        context = self._get_context()
        
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.value,
            "logger": self.name,
            "message": message,
            "correlation_id": context.correlation_id,
            "request_id": context.request_id,
            "user_id": context.user_id,
            "session_id": context.session_id,
            **kwargs
        }
        
        # Remove empty values
        return {k: v for k, v in entry.items() if v}
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        entry = self._create_log_entry(LogLevel.DEBUG, message, **kwargs)
        self.logger.debug(json.dumps(entry))
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        entry = self._create_log_entry(LogLevel.INFO, message, **kwargs)
        self.logger.info(json.dumps(entry))
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        entry = self._create_log_entry(LogLevel.WARNING, message, **kwargs)
        self.logger.warning(json.dumps(entry))
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception details."""
        error_details = None
        if error:
            error_details = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "stack_trace": traceback.format_exc()
            }
            
            # Track error for aggregation
            error_key = f"{type(error).__name__}:{str(error)[:100]}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        entry = self._create_log_entry(
            LogLevel.ERROR, 
            message, 
            event_type=EventType.ERROR,
            error_details=error_details,
            **kwargs
        )
        
        # Store recent errors
        self.last_errors.append(entry)
        if len(self.last_errors) > 100:
            self.last_errors.pop(0)
        
        self.logger.error(json.dumps(entry))
    
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log critical message."""
        error_details = None
        if error:
            error_details = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "stack_trace": traceback.format_exc()
            }
        
        entry = self._create_log_entry(
            LogLevel.CRITICAL, 
            message, 
            event_type=EventType.ERROR,
            error_details=error_details,
            **kwargs
        )
        
        self.logger.critical(json.dumps(entry))
    
    def log_request(self, request: Request, response_time_ms: Optional[float] = None):
        """Log HTTP request."""
        entry = self._create_log_entry(
            LogLevel.INFO,
            f"{request.method} {request.url.path}",
            event_type=EventType.REQUEST,
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            headers={k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'cookie']},
            client_ip=request.client.host if request.client else None,
            response_time_ms=response_time_ms
        )
        
        self.logger.info(json.dumps(entry))
    
    def log_response(self, request: Request, response: Response, response_time_ms: float):
        """Log HTTP response."""
        entry = self._create_log_entry(
            LogLevel.INFO,
            f"{request.method} {request.url.path} -> {response.status_code}",
            event_type=EventType.RESPONSE,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            response_size=response.headers.get('content-length')
        )
        
        self.logger.info(json.dumps(entry))
    
    def log_performance(self, metrics: PerformanceMetrics):
        """Log performance metrics."""
        entry = self._create_log_entry(
            LogLevel.INFO,
            f"Performance: {metrics.operation}",
            event_type=EventType.PERFORMANCE,
            **asdict(metrics)
        )
        
        self.logger.info(json.dumps(entry))
    
    def log_security_event(self, event: SecurityEvent):
        """Log security event."""
        entry = self._create_log_entry(
            LogLevel.WARNING if event.risk_score and event.risk_score > 5 else LogLevel.INFO,
            f"Security: {event.event_type.value}",
            event_type=EventType.SECURITY,
            **asdict(event)
        )
        
        self.logger.warning(json.dumps(entry)) if event.risk_score and event.risk_score > 5 else self.logger.info(json.dumps(entry))
    
    def log_business_event(self, event: BusinessEvent):
        """Log business event."""
        entry = self._create_log_entry(
            LogLevel.INFO,
            f"Business: {event.event_name}",
            event_type=EventType.BUSINESS,
            **asdict(event)
        )
        
        self.logger.info(json.dumps(entry))
    
    def log_database_operation(self, operation: str, table: str, duration_ms: float, rows_affected: Optional[int] = None):
        """Log database operation."""
        entry = self._create_log_entry(
            LogLevel.DEBUG,
            f"DB: {operation} on {table}",
            event_type=EventType.DATABASE,
            operation=operation,
            table=table,
            duration_ms=duration_ms,
            rows_affected=rows_affected
        )
        
        self.logger.debug(json.dumps(entry))
    
    def log_cache_operation(self, operation: str, key: str, hit: bool, duration_ms: Optional[float] = None):
        """Log cache operation."""
        entry = self._create_log_entry(
            LogLevel.DEBUG,
            f"Cache: {operation} {key} ({'HIT' if hit else 'MISS'})",
            event_type=EventType.CACHE,
            operation=operation,
            key=key,
            hit=hit,
            duration_ms=duration_ms
        )
        
        self.logger.debug(json.dumps(entry))
    
    def log_external_api_call(self, service: str, endpoint: str, method: str, status_code: int, duration_ms: float):
        """Log external API call."""
        entry = self._create_log_entry(
            LogLevel.INFO,
            f"External API: {method} {service}{endpoint} -> {status_code}",
            event_type=EventType.EXTERNAL_API,
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms
        )
        
        self.logger.info(json.dumps(entry))
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary for monitoring."""
        return {
            "error_counts": self.error_counts,
            "recent_errors": self.last_errors[-10:],
            "total_errors": sum(self.error_counts.values())
        }


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        # If the message is already JSON, return it as-is
        try:
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, ValueError):
            # Create structured log entry for non-JSON messages
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            
            return json.dumps(log_entry)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging with correlation tracking."""
    
    def __init__(self, app, logger: StructuredLogger):
        super().__init__(app)
        self.logger = logger
    
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        
        # Set context variables
        correlation_id_var.set(correlation_id)
        request_id_var.set(request_id)
        
        # Extract user info from headers or JWT
        user_id = request.headers.get('x-user-id', '')
        session_id = request.headers.get('x-session-id', '')
        
        if user_id:
            user_id_var.set(user_id)
        if session_id:
            session_id_var.set(session_id)
        
        # Add correlation ID to response headers
        start_time = time.time()
        
        # Log request
        self.logger.log_request(request)
        
        try:
            response = await call_next(request)
            response_time_ms = (time.time() - start_time) * 1000
            
            # Add correlation ID to response
            response.headers['x-correlation-id'] = correlation_id
            response.headers['x-request-id'] = request_id
            
            # Log response
            self.logger.log_response(request, response, response_time_ms)
            
            return response
        
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            
            # Log error
            self.logger.error(
                f"Request failed: {request.method} {request.url.path}",
                error=e,
                response_time_ms=response_time_ms
            )
            
            raise


def performance_logger(operation_name: str):
    """Decorator for logging performance metrics."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                metrics = PerformanceMetrics(
                    operation=operation_name,
                    duration_ms=duration_ms
                )
                
                logger.log_performance(metrics)
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Operation failed: {operation_name}",
                    error=e,
                    duration_ms=duration_ms
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                metrics = PerformanceMetrics(
                    operation=operation_name,
                    duration_ms=duration_ms
                )
                
                logger.log_performance(metrics)
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Operation failed: {operation_name}",
                    error=e,
                    duration_ms=duration_ms
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def security_logger(event_type: SecurityEventType, resource: Optional[str] = None):
    """Decorator for logging security events."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            
            try:
                result = await func(*args, **kwargs)
                
                event = SecurityEvent(
                    event_type=event_type,
                    user_id=user_id_var.get(),
                    resource=resource,
                    result="success"
                )
                
                logger.log_security_event(event)
                return result
            
            except Exception as e:
                event = SecurityEvent(
                    event_type=event_type,
                    user_id=user_id_var.get(),
                    resource=resource,
                    result="failure",
                    additional_data={"error": str(e)}
                )
                
                logger.log_security_event(event)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            
            try:
                result = func(*args, **kwargs)
                
                event = SecurityEvent(
                    event_type=event_type,
                    user_id=user_id_var.get(),
                    resource=resource,
                    result="success"
                )
                
                logger.log_security_event(event)
                return result
            
            except Exception as e:
                event = SecurityEvent(
                    event_type=event_type,
                    user_id=user_id_var.get(),
                    resource=resource,
                    result="failure",
                    additional_data={"error": str(e)}
                )
                
                logger.log_security_event(event)
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Global logger registry
_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str, log_file: Optional[str] = None) -> StructuredLogger:
    """Get or create a structured logger."""
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name, log_file)
    return _loggers[name]


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """Setup global logging configuration."""
    # Set root logger level
    logging.getLogger().setLevel(getattr(logging, log_level.upper()))
    
    # Create logs directory if needed
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Disable uvicorn access logs (we handle them in middleware)
    logging.getLogger("uvicorn.access").disabled = True


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id_var.get()


def get_request_id() -> str:
    """Get current request ID."""
    return request_id_var.get()


def get_user_id() -> str:
    """Get current user ID."""
    return user_id_var.get()


def set_user_context(user_id: str, session_id: Optional[str] = None):
    """Set user context for logging."""
    user_id_var.set(user_id)
    if session_id:
        session_id_var.set(session_id)


def log_security_event(event_type: str, additional_data: Optional[Dict[str, Any]] = None):
    """Standalone function to log security events."""
    logger = get_logger("security")
    
    # Create SecurityEvent from string event_type
    try:
        security_event_type = SecurityEventType(event_type)
    except ValueError:
        # If event_type is not a valid enum, use AUTHENTICATION as default
        security_event_type = SecurityEventType.AUTHENTICATION
    
    event = SecurityEvent(
        event_type=security_event_type,
        user_id=user_id_var.get() if user_id_var.get() else None,
        additional_data=additional_data or {}
    )
    
    logger.log_security_event(event)


# Export commonly used items
__all__ = [
    'StructuredLogger',
    'LoggingMiddleware',
    'performance_logger',
    'security_logger',
    'get_logger',
    'setup_logging',
    'get_correlation_id',
    'get_request_id',
    'get_user_id',
    'set_user_context',
    'log_security_event',
    'LogLevel',
    'EventType',
    'SecurityEventType',
    'PerformanceMetrics',
    'ErrorDetails',
    'SecurityEvent',
    'BusinessEvent'
]