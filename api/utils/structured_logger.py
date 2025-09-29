#!/usr/bin/env python3
"""
Structured logging module with correlation IDs, context tracking, and enhanced error handling.
Provides comprehensive logging capabilities for production environments.
"""

import logging
import json
import time
import uuid
import traceback
import threading
import asyncio
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone
from contextvars import ContextVar
from functools import wraps
import inspect
import sys
import os
from pathlib import Path

from api.core.config import get_settings


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Log category enumeration."""
    API = "api"
    DATABASE = "database"
    TASK = "task"
    AUTH = "auth"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    SYSTEM = "system"
    EXTERNAL = "external"
    MONITORING = "monitoring"


@dataclass
class LogContext:
    """Log context information."""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    version: Optional[str] = None
    environment: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: str
    level: str
    category: str
    message: str
    context: LogContext
    module: str
    function: str
    line_number: int
    thread_id: str
    process_id: int
    duration_ms: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    business_metrics: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
    extra_fields: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['context'] = self.context.to_dict()
        return {k: v for k, v in data.items() if v is not None}
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)


# Context variables for correlation tracking
correlation_context: ContextVar[LogContext] = ContextVar('correlation_context', default=LogContext())


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        try:
            # Get current context
            context = correlation_context.get(LogContext())
            
            # Extract caller information
            frame = inspect.currentframe()
            caller_frame = None
            
            # Walk up the stack to find the actual caller
            while frame:
                if (frame.f_code.co_filename != __file__ and 
                    'logging' not in frame.f_code.co_filename):
                    caller_frame = frame
                    break
                frame = frame.f_back
            
            if caller_frame:
                module = caller_frame.f_globals.get('__name__', 'unknown')
                function = caller_frame.f_code.co_name
                line_number = caller_frame.f_lineno
            else:
                module = getattr(record, 'module', record.name)
                function = getattr(record, 'funcName', 'unknown')
                line_number = getattr(record, 'lineno', 0)
            
            # Create log entry
            log_entry = LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                level=record.levelname,
                category=getattr(record, 'category', LogCategory.SYSTEM.value),
                message=record.getMessage(),
                context=context,
                module=module,
                function=function,
                line_number=line_number,
                thread_id=str(threading.get_ident()),
                process_id=os.getpid(),
                duration_ms=getattr(record, 'duration_ms', None),
                error_details=getattr(record, 'error_details', None),
                performance_metrics=getattr(record, 'performance_metrics', None),
                business_metrics=getattr(record, 'business_metrics', None),
                tags=getattr(record, 'tags', []),
                extra_fields=getattr(record, 'extra_fields', {})
            )
            
            # Add exception information if present
            if record.exc_info:
                log_entry.error_details = {
                    'exception_type': record.exc_info[0].__name__,
                    'exception_message': str(record.exc_info[1]),
                    'traceback': traceback.format_exception(*record.exc_info)
                }
            
            return log_entry.to_json()
            
        except Exception as e:
            # Fallback to simple format if structured formatting fails
            return f"{{\"timestamp\": \"{datetime.now(timezone.utc).isoformat()}\", \"level\": \"{record.levelname}\", \"message\": \"Logging error: {e}\", \"original_message\": \"{record.getMessage()}\"}}"


class StructuredLogger:
    """Enhanced structured logger with correlation tracking."""
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))
        
        # Configure handlers if not already configured
        if not self.logger.handlers:
            self._configure_handlers()
        
        self.settings = get_settings()
    
    def _configure_handlers(self):
        """Configure log handlers."""
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler (if configured)
        log_file = os.getenv('LOG_FILE')
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(file_handler)
    
    def set_context(self, **kwargs):
        """Set logging context."""
        current_context = correlation_context.get(LogContext())
        
        # Update context with new values
        for key, value in kwargs.items():
            if hasattr(current_context, key):
                setattr(current_context, key, value)
            else:
                current_context.metadata[key] = value
        
        correlation_context.set(current_context)
    
    def get_context(self) -> LogContext:
        """Get current logging context."""
        return correlation_context.get(LogContext())
    
    def clear_context(self):
        """Clear logging context."""
        correlation_context.set(LogContext())
    
    def _log(self, level: LogLevel, message: str, category: LogCategory = LogCategory.SYSTEM,
            error_details: Optional[Dict[str, Any]] = None,
            performance_metrics: Optional[Dict[str, Any]] = None,
            business_metrics: Optional[Dict[str, Any]] = None,
            tags: Optional[List[str]] = None,
            duration_ms: Optional[float] = None,
            **extra_fields):
        """Internal logging method."""
        
        # Create log record
        record = self.logger.makeRecord(
            name=self.name,
            level=getattr(logging, level.value),
            fn='',
            lno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        
        # Add custom attributes
        record.category = category.value
        record.error_details = error_details
        record.performance_metrics = performance_metrics
        record.business_metrics = business_metrics
        record.tags = tags or []
        record.duration_ms = duration_ms
        record.extra_fields = extra_fields
        
        # Handle the record
        self.logger.handle(record)
    
    def debug(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, category, **kwargs)
    
    def info(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log info message."""
        self._log(LogLevel.INFO, message, category, **kwargs)
    
    def warning(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, category, **kwargs)
    
    def error(self, message: str, category: LogCategory = LogCategory.SYSTEM, 
             error: Optional[Exception] = None, **kwargs):
        """Log error message."""
        error_details = kwargs.get('error_details')
        
        if error and not error_details:
            error_details = {
                'exception_type': type(error).__name__,
                'exception_message': str(error),
                'traceback': traceback.format_exc() if error else None
            }
            kwargs['error_details'] = error_details
        
        self._log(LogLevel.ERROR, message, category, **kwargs)
    
    def critical(self, message: str, category: LogCategory = LogCategory.SYSTEM, 
                error: Optional[Exception] = None, **kwargs):
        """Log critical message."""
        error_details = kwargs.get('error_details')
        
        if error and not error_details:
            error_details = {
                'exception_type': type(error).__name__,
                'exception_message': str(error),
                'traceback': traceback.format_exc() if error else None
            }
            kwargs['error_details'] = error_details
        
        self._log(LogLevel.CRITICAL, message, category, **kwargs)
    
    def log_api_request(self, method: str, path: str, status_code: int, 
                       duration_ms: float, user_id: Optional[str] = None,
                       request_size: Optional[int] = None,
                       response_size: Optional[int] = None):
        """Log API request."""
        performance_metrics = {
            'duration_ms': duration_ms,
            'request_size_bytes': request_size,
            'response_size_bytes': response_size
        }
        
        self.info(
            f"{method} {path} - {status_code}",
            category=LogCategory.API,
            performance_metrics=performance_metrics,
            tags=['api_request'],
            method=method,
            path=path,
            status_code=status_code,
            user_id=user_id
        )
    
    def log_database_query(self, query: str, duration_ms: float, 
                          rows_affected: Optional[int] = None,
                          error: Optional[Exception] = None):
        """Log database query."""
        performance_metrics = {
            'duration_ms': duration_ms,
            'rows_affected': rows_affected
        }
        
        if error:
            self.error(
                f"Database query failed: {query[:100]}...",
                category=LogCategory.DATABASE,
                error=error,
                performance_metrics=performance_metrics,
                tags=['database_error']
            )
        else:
            self.debug(
                f"Database query executed: {query[:100]}...",
                category=LogCategory.DATABASE,
                performance_metrics=performance_metrics,
                tags=['database_query']
            )
    
    def log_task_execution(self, task_name: str, status: str, duration_ms: float,
                          task_id: Optional[str] = None,
                          error: Optional[Exception] = None,
                          result_size: Optional[int] = None):
        """Log task execution."""
        performance_metrics = {
            'duration_ms': duration_ms,
            'result_size_bytes': result_size
        }
        
        business_metrics = {
            'task_name': task_name,
            'task_status': status,
            'task_id': task_id
        }
        
        if error:
            self.error(
                f"Task {task_name} failed",
                category=LogCategory.TASK,
                error=error,
                performance_metrics=performance_metrics,
                business_metrics=business_metrics,
                tags=['task_error']
            )
        else:
            self.info(
                f"Task {task_name} completed with status: {status}",
                category=LogCategory.TASK,
                performance_metrics=performance_metrics,
                business_metrics=business_metrics,
                tags=['task_success']
            )
    
    def log_security_event(self, event_type: str, user_id: Optional[str] = None,
                          ip_address: Optional[str] = None,
                          user_agent: Optional[str] = None,
                          severity: str = 'medium'):
        """Log security event."""
        self.warning(
            f"Security event: {event_type}",
            category=LogCategory.SECURITY,
            tags=['security_event', severity],
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=severity
        )
    
    def log_business_event(self, event_name: str, user_id: Optional[str] = None,
                          metrics: Optional[Dict[str, Any]] = None,
                          **properties):
        """Log business event."""
        self.info(
            f"Business event: {event_name}",
            category=LogCategory.BUSINESS,
            business_metrics=metrics,
            tags=['business_event'],
            event_name=event_name,
            user_id=user_id,
            **properties
        )
    
    def log_performance_metric(self, metric_name: str, value: float, 
                              unit: str = 'ms', tags: Optional[List[str]] = None):
        """Log performance metric."""
        performance_metrics = {
            metric_name: value,
            'unit': unit
        }
        
        self.info(
            f"Performance metric: {metric_name} = {value} {unit}",
            category=LogCategory.PERFORMANCE,
            performance_metrics=performance_metrics,
            tags=(tags or []) + ['performance_metric']
        )


class LoggerManager:
    """Manager for structured loggers."""
    
    _loggers: Dict[str, StructuredLogger] = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_logger(cls, name: str, level: LogLevel = LogLevel.INFO) -> StructuredLogger:
        """Get or create a structured logger."""
        with cls._lock:
            if name not in cls._loggers:
                cls._loggers[name] = StructuredLogger(name, level)
            return cls._loggers[name]
    
    @classmethod
    def configure_root_logger(cls, level: LogLevel = LogLevel.INFO,
                            log_file: Optional[str] = None):
        """Configure root logger."""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.value))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(file_handler)


def correlation_id_middleware(get_response):
    """Middleware to set correlation ID for each request."""
    def middleware(request):
        # Generate or extract correlation ID
        correlation_id = (
            request.headers.get('X-Correlation-ID') or
            request.headers.get('X-Request-ID') or
            str(uuid.uuid4())
        )
        
        # Set context
        context = LogContext(
            correlation_id=correlation_id,
            request_id=getattr(request, 'id', None),
            user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None
        )
        correlation_context.set(context)
        
        # Add correlation ID to response headers
        response = get_response(request)
        response['X-Correlation-ID'] = correlation_id
        
        return response
    
    return middleware


def log_execution_time(category: LogCategory = LogCategory.PERFORMANCE,
                      include_args: bool = False,
                      include_result: bool = False):
    """Decorator to log function execution time."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = LoggerManager.get_logger(func.__module__)
            start_time = time.time()
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                duration_ms = (time.time() - start_time) * 1000
                
                log_data = {
                    'function': func.__name__,
                    'duration_ms': duration_ms
                }
                
                if include_args:
                    log_data['args'] = str(args)[:200]  # Truncate for safety
                    log_data['kwargs'] = {k: str(v)[:100] for k, v in kwargs.items()}
                
                if include_result:
                    log_data['result'] = str(result)[:200]  # Truncate for safety
                
                logger.info(
                    f"Function {func.__name__} executed in {duration_ms:.2f}ms",
                    category=category,
                    performance_metrics={'duration_ms': duration_ms},
                    tags=['function_execution'],
                    **log_data
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.error(
                    f"Function {func.__name__} failed after {duration_ms:.2f}ms",
                    category=category,
                    error=e,
                    performance_metrics={'duration_ms': duration_ms},
                    tags=['function_error'],
                    function=func.__name__
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = LoggerManager.get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                log_data = {
                    'function': func.__name__,
                    'duration_ms': duration_ms
                }
                
                if include_args:
                    log_data['args'] = str(args)[:200]
                    log_data['kwargs'] = {k: str(v)[:100] for k, v in kwargs.items()}
                
                if include_result:
                    log_data['result'] = str(result)[:200]
                
                logger.info(
                    f"Function {func.__name__} executed in {duration_ms:.2f}ms",
                    category=category,
                    performance_metrics={'duration_ms': duration_ms},
                    tags=['function_execution'],
                    **log_data
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.error(
                    f"Function {func.__name__} failed after {duration_ms:.2f}ms",
                    category=category,
                    error=e,
                    performance_metrics={'duration_ms': duration_ms},
                    tags=['function_error'],
                    function=func.__name__
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def get_logger(name: str = None, level: LogLevel = LogLevel.INFO) -> StructuredLogger:
    """Get a structured logger instance."""
    if name is None:
        # Get caller's module name
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return LoggerManager.get_logger(name, level)


# Configure logging on module import
if not logging.getLogger().handlers:
    LoggerManager.configure_root_logger(
        level=LogLevel.INFO,
        log_file=os.getenv('LOG_FILE')
    )