"""Logging middleware for FastAPI with correlation ID tracking.

Provides:
- Automatic correlation ID generation and tracking
- Request/response logging with structured data
- Performance metrics collection
- Error tracking and context preservation
- Security event logging
"""

import time
import uuid
import json
from typing import Callable, Optional, Dict, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI
from fastapi.security.utils import get_authorization_scheme_param

from ..utils.enhanced_logging import (
    get_enhanced_logger,
    set_correlation_context,
    EventType,
    LogLevel
)
from ..core.security import decode_access_token


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging."""
    
    def __init__(
        self,
        app,
        logger_name: str = "api.requests",
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_size: int = 1024,
        exclude_paths: Optional[list] = None,
        sensitive_headers: Optional[list] = None
    ):
        super().__init__(app)
        self.logger = get_enhanced_logger(logger_name)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
        self.sensitive_headers = sensitive_headers or [
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with logging."""
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Generate correlation ID and extract user context
        correlation_id = self._get_or_generate_correlation_id(request)
        user_id = await self._extract_user_id(request)
        request_id = str(uuid.uuid4())
        session_id = self._extract_session_id(request)
        
        # Set correlation context
        with set_correlation_context(
            correlation_id=correlation_id,
            user_id=user_id,
            request_id=request_id,
            session_id=session_id
        ):
            # Add correlation ID to request state
            request.state.correlation_id = correlation_id
            request.state.request_id = request_id
            
            # Log incoming request
            await self._log_request(request)
            
            # Process request
            start_time = time.time()
            response = None
            error = None
            
            try:
                response = await call_next(request)
                
                # Add correlation ID to response headers
                response.headers["X-Correlation-ID"] = correlation_id
                response.headers["X-Request-ID"] = request_id
                
                return response
            
            except Exception as e:
                error = e
                # Log error
                self.logger.error(
                    f"Request failed: {request.method} {request.url.path}",
                    error=e,
                    event_type=EventType.ERROR,
                    data={
                        "method": request.method,
                        "path": request.url.path,
                        "query_params": dict(request.query_params),
                        "client_ip": self._get_client_ip(request)
                    }
                )
                raise
            
            finally:
                # Calculate response time
                response_time_ms = (time.time() - start_time) * 1000
                
                # Log response
                await self._log_response(
                    request=request,
                    response=response,
                    response_time_ms=response_time_ms,
                    error=error
                )
                
                # Log performance metrics
                self.logger.log_performance(
                    operation=f"{request.method} {request.url.path}",
                    duration_ms=response_time_ms,
                    success=error is None and (response is None or response.status_code < 400),
                    metadata={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code if response else None,
                        "client_ip": self._get_client_ip(request)
                    }
                )
    
    def _get_or_generate_correlation_id(self, request: Request) -> str:
        """Get correlation ID from headers or generate new one."""
        # Check for existing correlation ID in headers
        correlation_id = (
            request.headers.get("X-Correlation-ID") or
            request.headers.get("X-Request-ID") or
            request.headers.get("X-Trace-ID")
        )
        
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        return correlation_id
    
    async def _extract_user_id(self, request: Request) -> str:
        """Extract user ID from JWT token."""
        try:
            authorization = request.headers.get("Authorization")
            if not authorization:
                return ""
            
            scheme, token = get_authorization_scheme_param(authorization)
            if scheme.lower() != "bearer":
                return ""
            
            payload = decode_access_token(token)
            return payload.get("sub", "")
        
        except Exception:
            return ""
    
    def _extract_session_id(self, request: Request) -> str:
        """Extract session ID from cookies or headers."""
        # Try to get session ID from cookie
        session_id = request.cookies.get("session_id")
        if session_id:
            return session_id
        
        # Try to get from header
        session_id = request.headers.get("X-Session-ID")
        if session_id:
            return session_id
        
        return ""
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if hasattr(request.client, "host"):
            return request.client.host
        
        return "unknown"
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize sensitive headers."""
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized
    
    async def _log_request(self, request: Request):
        """Log incoming request details."""
        # Prepare request data
        request_data = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": self._sanitize_headers(dict(request.headers)),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", "")
        }
        
        # Add request body if enabled
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await self._get_request_body(request)
                if body:
                    request_data["body_preview"] = body[:self.max_body_size]
                    request_data["body_size"] = len(body)
            except Exception as e:
                request_data["body_error"] = str(e)
        
        self.logger.log(
            LogLevel.INFO,
            f"Incoming request: {request.method} {request.url.path}",
            event_type=EventType.REQUEST,
            data=request_data
        )
    
    async def _log_response(
        self,
        request: Request,
        response: Optional[Response],
        response_time_ms: float,
        error: Optional[Exception] = None
    ):
        """Log outgoing response details."""
        # Prepare response data
        response_data = {
            "method": request.method,
            "path": request.url.path,
            "response_time_ms": round(response_time_ms, 2),
            "client_ip": self._get_client_ip(request)
        }
        
        if response:
            response_data.update({
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content_length": response.headers.get("content-length", 0)
            })
            
            # Add response body if enabled
            if self.log_response_body:
                try:
                    body = await self._get_response_body(response)
                    if body:
                        response_data["body_preview"] = body[:self.max_body_size]
                        response_data["body_size"] = len(body)
                except Exception as e:
                    response_data["body_error"] = str(e)
        
        if error:
            response_data["error"] = {
                "type": type(error).__name__,
                "message": str(error)
            }
        
        # Determine log level based on status code
        log_level = LogLevel.INFO
        if response and response.status_code >= 500:
            log_level = LogLevel.ERROR
        elif response and response.status_code >= 400:
            log_level = LogLevel.WARNING
        elif error:
            log_level = LogLevel.ERROR
        
        self.logger.log(
            log_level,
            f"Response: {response.status_code if response else 'ERROR'} - {request.method} {request.url.path}",
            event_type=EventType.RESPONSE,
            data=response_data
        )
        
        # Log security events for suspicious activity
        await self._check_security_events(request, response, error)
    
    async def _get_request_body(self, request: Request) -> str:
        """Get request body as string."""
        try:
            body = await request.body()
            return body.decode('utf-8')
        except Exception:
            return ""
    
    async def _get_response_body(self, response: Response) -> str:
        """Get response body as string."""
        try:
            if hasattr(response, 'body'):
                if isinstance(response.body, bytes):
                    return response.body.decode('utf-8')
                elif isinstance(response.body, str):
                    return response.body
            return ""
        except Exception:
            return ""
    
    async def _check_security_events(
        self,
        request: Request,
        response: Optional[Response],
        error: Optional[Exception]
    ):
        """Check for security-related events."""
        client_ip = self._get_client_ip(request)
        
        # Check for authentication failures
        if response and response.status_code == 401:
            self.logger.log_security_event(
                event="authentication_failure",
                severity="medium",
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get("User-Agent", "")
                },
                ip_address=client_ip
            )
        
        # Check for authorization failures
        elif response and response.status_code == 403:
            self.logger.log_security_event(
                event="authorization_failure",
                severity="medium",
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get("User-Agent", "")
                },
                ip_address=client_ip
            )
        
        # Check for potential attacks
        elif response and response.status_code == 400:
            # Check for SQL injection attempts
            query_string = str(request.url.query)
            if any(keyword in query_string.lower() for keyword in ['union', 'select', 'drop', 'insert']):
                self.logger.log_security_event(
                    event="potential_sql_injection",
                    severity="high",
                    details={
                        "path": request.url.path,
                        "query_params": dict(request.query_params),
                        "user_agent": request.headers.get("User-Agent", "")
                    },
                    ip_address=client_ip
                )
        
        # Check for rate limiting
        elif response and response.status_code == 429:
            self.logger.log_security_event(
                event="rate_limit_exceeded",
                severity="medium",
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get("User-Agent", "")
                },
                ip_address=client_ip
            )


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware specifically for performance logging."""
    
    def __init__(
        self,
        app,
        slow_request_threshold_ms: float = 1000.0,
        log_all_requests: bool = False
    ):
        super().__init__(app)
        self.logger = get_enhanced_logger("api.performance")
        self.slow_request_threshold_ms = slow_request_threshold_ms
        self.log_all_requests = log_all_requests
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log performance metrics for requests."""
        start_time = time.time()
        
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            # Log slow requests or all requests if enabled
            if duration_ms > self.slow_request_threshold_ms or self.log_all_requests:
                self.logger.log(
                    LogLevel.WARNING if duration_ms > self.slow_request_threshold_ms else LogLevel.INFO,
                    f"{'Slow' if duration_ms > self.slow_request_threshold_ms else 'Request'} performance: {request.method} {request.url.path}",
                    event_type=EventType.PERFORMANCE,
                    data={
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration_ms, 2),
                        "is_slow": duration_ms > self.slow_request_threshold_ms,
                        "threshold_ms": self.slow_request_threshold_ms
                    }
                )


def setup_logging_middleware(
    app: FastAPI,
    enable_request_logging: bool = True,
    enable_performance_logging: bool = True,
    log_request_body: bool = False,
    log_response_body: bool = False,
    slow_request_threshold_ms: float = 1000.0
):
    """Setup logging middleware for the FastAPI application."""
    
    if enable_performance_logging:
        app.add_middleware(
            PerformanceLoggingMiddleware,
            slow_request_threshold_ms=slow_request_threshold_ms
        )
    
    if enable_request_logging:
        app.add_middleware(
            LoggingMiddleware,
            log_request_body=log_request_body,
            log_response_body=log_response_body
        )


# Export main components
__all__ = [
    'LoggingMiddleware',
    'PerformanceLoggingMiddleware',
    'setup_logging_middleware'
]