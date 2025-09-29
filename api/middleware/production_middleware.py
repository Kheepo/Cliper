"""Production middleware for comprehensive request tracking and monitoring.

Provides:
- Request/response logging with correlation IDs
- Performance monitoring and metrics collection
- Error tracking and alerting
- Rate limiting and security monitoring
- Health check integration
"""

import time
import uuid
import json
from typing import Callable, Dict, Any, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncio
from collections import defaultdict, deque

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp
import psutil

from ..utils.enhanced_logging import EnhancedLogger, LogLevel, EventType, correlation_id
from ..utils.production_monitoring import get_production_monitor
from ..utils.memory_optimizer import EnhancedMemoryOptimizer


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking requests with correlation IDs and performance metrics."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = EnhancedLogger("request_tracking")
        self.production_monitor = get_production_monitor()
        self.memory_optimizer = EnhancedMemoryOptimizer()
        
        # Request metrics storage
        self.request_metrics = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "error_count": 0,
            "recent_times": deque(maxlen=100)
        })
        
        # Rate limiting storage
        self.rate_limit_storage = defaultdict(lambda: deque(maxlen=100))
        
        # Security monitoring
        self.security_events = deque(maxlen=1000)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with comprehensive tracking."""
        start_time = time.time()
        
        # Generate correlation ID
        request_id = str(uuid.uuid4())
        correlation_id.set(request_id)
        
        # Extract request information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        
        # Security checks
        security_issues = await self._check_security(request, client_ip, user_agent)
        
        # Rate limiting check
        rate_limit_exceeded = self._check_rate_limit(client_ip, path)
        
        if rate_limit_exceeded:
            self.logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                path=path,
                correlation_id=request_id,
                event_type=EventType.SECURITY
            )
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "correlation_id": request_id}
            )
        
        # Log request start
        self.logger.info(
            "Request started",
            method=method,
            path=path,
            client_ip=client_ip,
            user_agent=user_agent,
            query_params=query_params,
            correlation_id=request_id,
            event_type=EventType.REQUEST
        )
        
        # Process request
        response = None
        error = None
        status_code = 200
        
        try:
            # Add correlation ID to request state
            request.state.correlation_id = request_id
            request.state.start_time = start_time
            
            # Process the request
            response = await call_next(request)
            status_code = response.status_code
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = request_id
            
        except Exception as e:
            error = e
            status_code = 500
            
            # Log the error
            self.logger.error(
                "Request failed with exception",
                method=method,
                path=path,
                error=str(e),
                correlation_id=request_id,
                event_type=EventType.ERROR
            )
            
            # Return error response
            response = JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "correlation_id": request_id
                }
            )
            response.headers["X-Correlation-ID"] = request_id
        
        # Calculate response time
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Update metrics
        self._update_metrics(method, path, response_time, status_code >= 400)
        
        # Log request completion
        log_level = LogLevel.ERROR if status_code >= 400 else LogLevel.INFO
        self.logger.log(
            log_level,
            "Request completed",
            method=method,
            path=path,
            status_code=status_code,
            response_time_ms=response_time,
            client_ip=client_ip,
            correlation_id=request_id,
            event_type=EventType.REQUEST
        )
        
        # Performance monitoring
        if response_time > 5000:  # 5 seconds
            self.logger.warning(
                "Slow request detected",
                method=method,
                path=path,
                response_time_ms=response_time,
                correlation_id=request_id,
                event_type=EventType.PERFORMANCE
            )
        
        # Security event logging
        if security_issues:
            for issue in security_issues:
                self.security_events.append({
                    "timestamp": datetime.utcnow(),
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "path": path,
                    "issue": issue,
                    "correlation_id": request_id
                })
                
                self.logger.warning(
                    f"Security issue detected: {issue}",
                    client_ip=client_ip,
                    path=path,
                    correlation_id=request_id,
                    event_type=EventType.SECURITY
                )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _check_security(self, request: Request, client_ip: str, user_agent: str) -> list:
        """Check for security issues in the request."""
        issues = []
        
        # Check for suspicious user agents
        suspicious_agents = [
            "sqlmap", "nikto", "nmap", "masscan", "zap", "burp",
            "wget", "curl", "python-requests", "bot", "crawler"
        ]
        
        if any(agent.lower() in user_agent.lower() for agent in suspicious_agents):
            issues.append("suspicious_user_agent")
        
        # Check for SQL injection patterns in query parameters
        query_string = str(request.url.query)
        sql_patterns = [
            "union", "select", "insert", "update", "delete", "drop",
            "exec", "script", "<script", "javascript:", "onload="
        ]
        
        if any(pattern in query_string.lower() for pattern in sql_patterns):
            issues.append("potential_injection_attempt")
        
        # Check for path traversal attempts
        path = request.url.path
        if "../" in path or "..\\" in path or "%2e%2e" in path.lower():
            issues.append("path_traversal_attempt")
        
        # Check for excessive request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
            issues.append("large_request_body")
        
        return issues
    
    def _check_rate_limit(self, client_ip: str, path: str) -> bool:
        """Check if client has exceeded rate limits."""
        now = time.time()
        window = 60  # 1 minute window
        max_requests = 100  # Max requests per minute
        
        # Clean old entries
        client_requests = self.rate_limit_storage[client_ip]
        while client_requests and client_requests[0] < now - window:
            client_requests.popleft()
        
        # Check if limit exceeded
        if len(client_requests) >= max_requests:
            return True
        
        # Add current request
        client_requests.append(now)
        return False
    
    def _update_metrics(self, method: str, path: str, response_time: float, is_error: bool):
        """Update request metrics."""
        key = f"{method} {path}"
        metrics = self.request_metrics[key]
        
        metrics["count"] += 1
        metrics["total_time"] += response_time
        metrics["recent_times"].append(response_time)
        
        if is_error:
            metrics["error_count"] += 1
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of request metrics."""
        summary = {
            "endpoints": {},
            "total_requests": 0,
            "total_errors": 0,
            "avg_response_time": 0.0
        }
        
        total_time = 0.0
        total_requests = 0
        total_errors = 0
        
        for endpoint, metrics in self.request_metrics.items():
            count = metrics["count"]
            error_count = metrics["error_count"]
            avg_time = metrics["total_time"] / count if count > 0 else 0
            
            recent_times = list(metrics["recent_times"])
            p95_time = 0.0
            if recent_times:
                recent_times.sort()
                p95_index = int(len(recent_times) * 0.95)
                p95_time = recent_times[p95_index] if p95_index < len(recent_times) else recent_times[-1]
            
            summary["endpoints"][endpoint] = {
                "requests": count,
                "errors": error_count,
                "error_rate": (error_count / count * 100) if count > 0 else 0,
                "avg_response_time": avg_time,
                "p95_response_time": p95_time
            }
            
            total_requests += count
            total_errors += error_count
            total_time += metrics["total_time"]
        
        summary["total_requests"] = total_requests
        summary["total_errors"] = total_errors
        summary["avg_response_time"] = total_time / total_requests if total_requests > 0 else 0
        summary["error_rate"] = (total_errors / total_requests * 100) if total_requests > 0 else 0
        
        return summary


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware for health check endpoints with minimal overhead."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.health_paths = {"/health", "/health/live", "/health/ready", "/health/startup"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process health check requests with minimal logging."""
        # Skip detailed tracking for health check endpoints
        if request.url.path in self.health_paths:
            return await call_next(request)
        
        return await call_next(request)


class MemoryMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring memory usage during requests."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = EnhancedLogger("memory_monitoring")
        self.memory_optimizer = EnhancedMemoryOptimizer()
        self.memory_threshold_mb = 1000  # 1GB threshold
        self.cleanup_interval = 100  # Cleanup every 100 requests
        self.request_count = 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor memory usage during request processing."""
        # Get memory usage before request
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process request
        response = await call_next(request)
        
        # Get memory usage after request
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_diff = memory_after - memory_before
        
        # Log significant memory increases
        if memory_diff > 50:  # 50MB increase
            self.logger.warning(
                "Significant memory increase during request",
                path=request.url.path,
                memory_before_mb=memory_before,
                memory_after_mb=memory_after,
                memory_increase_mb=memory_diff,
                event_type=EventType.PERFORMANCE
            )
        
        # Check if cleanup is needed
        self.request_count += 1
        if self.request_count % self.cleanup_interval == 0:
            if memory_after > self.memory_threshold_mb:
                self.logger.info(
                    "Triggering memory cleanup",
                    current_memory_mb=memory_after,
                    threshold_mb=self.memory_threshold_mb,
                    event_type=EventType.SYSTEM
                )
                
                # Trigger async cleanup
                asyncio.create_task(self._cleanup_memory())
        
        return response
    
    async def _cleanup_memory(self):
        """Perform memory cleanup."""
        try:
            await self.memory_optimizer.emergency_cleanup()
            
            # Log cleanup results
            process = psutil.Process()
            memory_after_cleanup = process.memory_info().rss / 1024 / 1024
            
            self.logger.info(
                "Memory cleanup completed",
                memory_after_cleanup_mb=memory_after_cleanup,
                event_type=EventType.SYSTEM
            )
        except Exception as e:
            self.logger.error("Memory cleanup failed", error=e)


def setup_production_middleware(app: FastAPI) -> FastAPI:
    """Setup all production middleware in the correct order."""
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Add custom middleware (order matters - last added is executed first)
    app.add_middleware(MemoryMonitoringMiddleware)
    app.add_middleware(HealthCheckMiddleware)
    app.add_middleware(RequestTrackingMiddleware)
    
    return app


@asynccontextmanager
async def production_lifespan(app: FastAPI):
    """Production lifespan manager for startup and shutdown tasks."""
    logger = EnhancedLogger("production_lifespan")
    production_monitor = get_production_monitor()
    
    # Startup
    logger.info("Starting production application", event_type=EventType.SYSTEM)
    
    try:
        # Start production monitoring
        monitoring_task = asyncio.create_task(production_monitor.start_monitoring())
        
        # Initialize memory optimizer
        memory_optimizer = EnhancedMemoryOptimizer()
        await memory_optimizer.initialize()
        
        logger.info("Production application started successfully", event_type=EventType.SYSTEM)
        
        yield
        
    except Exception as e:
        logger.error("Failed to start production application", error=e)
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down production application", event_type=EventType.SYSTEM)
        
        try:
            # Stop monitoring
            await production_monitor.stop_monitoring()
            
            # Final memory cleanup
            await memory_optimizer.emergency_cleanup()
            
            logger.info("Production application shutdown completed", event_type=EventType.SYSTEM)
            
        except Exception as e:
            logger.error("Error during application shutdown", error=e)


# Export main components
__all__ = [
    'RequestTrackingMiddleware',
    'HealthCheckMiddleware',
    'MemoryMonitoringMiddleware',
    'setup_production_middleware',
    'production_lifespan'
]