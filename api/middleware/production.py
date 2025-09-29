"""Production middleware for enhanced request handling.

Integrates:
- Enhanced logging with correlation IDs
- Load balancing and circuit breaker patterns
- Performance monitoring and metrics
- Security headers and rate limiting
- Error handling and recovery
- Request/response tracking
"""

import time
import uuid
import json
import asyncio
from typing import Callable, Dict, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis

from ..utils.enhanced_logging import (
    get_enhanced_logger,
    set_correlation_context,
    EventType,
    LogLevel
)
from ..utils.load_balancing import (
    get_service_registry,
    get_load_balancer,
    ServiceNode,
    NodeStatus
)
from ..utils.rate_limiting import RateLimiter
from ..utils.security import SecurityHeaders
from ..config.environments import get_settings

logger = get_enhanced_logger(__name__)


class ProductionMiddleware(BaseHTTPMiddleware):
    """Comprehensive production middleware."""
    
    def __init__(
        self,
        app: ASGIApp,
        redis_client: Optional[redis.Redis] = None,
        enable_load_balancing: bool = True,
        enable_rate_limiting: bool = True,
        enable_security_headers: bool = True,
        enable_metrics: bool = True
    ):
        super().__init__(app)
        self.redis_client = redis_client
        self.enable_load_balancing = enable_load_balancing
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_security_headers = enable_security_headers
        self.enable_metrics = enable_metrics
        
        # Initialize components
        self.settings = get_settings()
        self.rate_limiter = RateLimiter(redis_client) if enable_rate_limiting and redis_client else None
        self.security_headers = SecurityHeaders() if enable_security_headers else None
        
        # Metrics storage
        self.request_metrics: Dict[str, Any] = {
            'total_requests': 0,
            'total_errors': 0,
            'response_times': [],
            'status_codes': {},
            'endpoints': {}
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through production middleware stack."""
        start_time = time.time()
        
        # Generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        request_id = str(uuid.uuid4())
        
        # Set correlation context
        with set_correlation_context(
            correlation_id=correlation_id,
            request_id=request_id,
            user_id=getattr(request.state, 'user_id', ''),
            session_id=request.headers.get('X-Session-ID', '')
        ):
            try:
                # Pre-processing
                await self._pre_process_request(request, correlation_id)
                
                # Rate limiting check
                if self.rate_limiter:
                    await self._check_rate_limit(request)
                
                # Load balancing (if enabled and needed)
                if self.enable_load_balancing:
                    await self._handle_load_balancing(request)
                
                # Process request
                response = await call_next(request)
                
                # Post-processing
                await self._post_process_response(request, response, start_time)
                
                return response
                
            except HTTPException as e:
                # Handle HTTP exceptions
                response = await self._handle_http_exception(request, e, start_time)
                return response
                
            except Exception as e:
                # Handle unexpected exceptions
                response = await self._handle_unexpected_exception(request, e, start_time)
                return response
    
    async def _pre_process_request(self, request: Request, correlation_id: str):
        """Pre-process incoming request."""
        # Log incoming request
        logger.log_request(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            user_agent=request.headers.get('User-Agent')
        )
        
        # Add correlation ID to request state
        request.state.correlation_id = correlation_id
        request.state.start_time = time.time()
        
        # Security logging for sensitive endpoints
        if self._is_sensitive_endpoint(request.url.path):
            logger.log_security_event(
                event="sensitive_endpoint_access",
                severity="low",
                details={
                    "endpoint": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get('User-Agent', ''),
                    "referer": request.headers.get('Referer', '')
                },
                ip_address=self._get_client_ip(request)
            )
    
    async def _check_rate_limit(self, request: Request):
        """Check rate limiting."""
        if not self.rate_limiter:
            return
        
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.state, 'user_id', None)
        
        # Check rate limit
        is_allowed, remaining, reset_time = await self.rate_limiter.check_rate_limit(
            key=user_id or client_ip,
            limit=100,  # requests per window
            window=3600  # 1 hour window
        )
        
        if not is_allowed:
            logger.log_security_event(
                event="rate_limit_exceeded",
                severity="medium",
                details={
                    "client_ip": client_ip,
                    "user_id": user_id,
                    "endpoint": request.url.path,
                    "remaining": remaining,
                    "reset_time": reset_time
                },
                ip_address=client_ip
            )
            
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - time.time())
                }
            )
    
    async def _handle_load_balancing(self, request: Request):
        """Handle load balancing for internal service calls."""
        if not self.redis_client:
            return
        
        # Only apply load balancing to specific internal endpoints
        if not self._requires_load_balancing(request.url.path):
            return
        
        try:
            # Get service registry
            service_name = self._extract_service_name(request.url.path)
            registry = get_service_registry(service_name, self.redis_client)
            load_balancer = get_load_balancer(service_name, self.redis_client)
            
            # Select target node
            session_id = request.headers.get('X-Session-ID')
            target_node = await load_balancer.select_node(session_id=session_id)
            
            if target_node:
                # Add target node info to request state
                request.state.target_node = target_node
                request.state.load_balanced = True
                
                logger.info(
                    f"Load balanced request to node {target_node.id}",
                    data={
                        "service": service_name,
                        "target_node": target_node.id,
                        "target_endpoint": target_node.endpoint,
                        "algorithm": load_balancer.algorithm.value
                    }
                )
            
        except Exception as e:
            logger.error(f"Load balancing error: {e}", error=e)
            # Continue without load balancing
    
    async def _post_process_response(self, request: Request, response: Response, start_time: float):
        """Post-process outgoing response."""
        response_time = (time.time() - start_time) * 1000
        
        # Add security headers
        if self.security_headers:
            self.security_headers.add_headers(response)
        
        # Add correlation ID to response
        correlation_id = getattr(request.state, 'correlation_id', '')
        response.headers['X-Correlation-ID'] = correlation_id
        
        # Add performance headers
        response.headers['X-Response-Time'] = f"{response_time:.2f}ms"
        
        # Log response
        logger.log_response(
            status_code=response.status_code,
            response_time_ms=response_time,
            response_size=len(response.body) if hasattr(response, 'body') else 0
        )
        
        # Record metrics
        if self.enable_metrics:
            await self._record_metrics(request, response, response_time)
        
        # Update load balancer metrics
        if hasattr(request.state, 'target_node'):
            target_node = request.state.target_node
            target_node.response_time_ms = response_time
            
            # Update connection count (simplified)
            if response.status_code < 400:
                target_node.active_connections = max(0, target_node.active_connections - 1)
    
    async def _handle_http_exception(self, request: Request, exc: HTTPException, start_time: float) -> JSONResponse:
        """Handle HTTP exceptions."""
        response_time = (time.time() - start_time) * 1000
        correlation_id = getattr(request.state, 'correlation_id', '')
        
        # Log error
        logger.error(
            f"HTTP {exc.status_code}: {exc.detail}",
            data={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "endpoint": request.url.path,
                "method": request.method,
                "response_time_ms": response_time
            }
        )
        
        # Create error response
        error_response = {
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Add additional headers from exception
        headers = {
            "X-Correlation-ID": correlation_id,
            "X-Response-Time": f"{response_time:.2f}ms"
        }
        
        if hasattr(exc, 'headers') and exc.headers:
            headers.update(exc.headers)
        
        response = JSONResponse(
            status_code=exc.status_code,
            content=error_response,
            headers=headers
        )
        
        # Add security headers
        if self.security_headers:
            self.security_headers.add_headers(response)
        
        return response
    
    async def _handle_unexpected_exception(self, request: Request, exc: Exception, start_time: float) -> JSONResponse:
        """Handle unexpected exceptions."""
        response_time = (time.time() - start_time) * 1000
        correlation_id = getattr(request.state, 'correlation_id', '')
        
        # Log critical error
        logger.critical(
            f"Unexpected error: {str(exc)}",
            error=exc,
            data={
                "endpoint": request.url.path,
                "method": request.method,
                "response_time_ms": response_time
            }
        )
        
        # Create generic error response (don't expose internal details)
        error_response = {
            "error": {
                "code": 500,
                "message": "Internal server error",
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # In development, include more details
        if self.settings.environment == "development":
            error_response["error"]["details"] = str(exc)
            error_response["error"]["type"] = type(exc).__name__
        
        response = JSONResponse(
            status_code=500,
            content=error_response,
            headers={
                "X-Correlation-ID": correlation_id,
                "X-Response-Time": f"{response_time:.2f}ms"
            }
        )
        
        # Add security headers
        if self.security_headers:
            self.security_headers.add_headers(response)
        
        return response
    
    async def _record_metrics(self, request: Request, response: Response, response_time: float):
        """Record request metrics."""
        try:
            # Update basic metrics
            self.request_metrics['total_requests'] += 1
            
            if response.status_code >= 400:
                self.request_metrics['total_errors'] += 1
            
            # Track response times (keep last 1000)
            self.request_metrics['response_times'].append(response_time)
            if len(self.request_metrics['response_times']) > 1000:
                self.request_metrics['response_times'].pop(0)
            
            # Track status codes
            status_code = str(response.status_code)
            self.request_metrics['status_codes'][status_code] = (
                self.request_metrics['status_codes'].get(status_code, 0) + 1
            )
            
            # Track endpoints
            endpoint = request.url.path
            if endpoint not in self.request_metrics['endpoints']:
                self.request_metrics['endpoints'][endpoint] = {
                    'count': 0,
                    'total_time': 0,
                    'errors': 0
                }
            
            endpoint_metrics = self.request_metrics['endpoints'][endpoint]
            endpoint_metrics['count'] += 1
            endpoint_metrics['total_time'] += response_time
            
            if response.status_code >= 400:
                endpoint_metrics['errors'] += 1
            
            # Store in Redis if available
            if self.redis_client:
                await self._store_metrics_in_redis(request, response, response_time)
                
        except Exception as e:
            logger.error(f"Error recording metrics: {e}", error=e)
    
    async def _store_metrics_in_redis(self, request: Request, response: Response, response_time: float):
        """Store metrics in Redis for distributed collection."""
        try:
            metric_data = {
                "timestamp": time.time(),
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "response_time_ms": response_time,
                "user_id": getattr(request.state, 'user_id', ''),
                "correlation_id": getattr(request.state, 'correlation_id', ''),
                "node_id": self.settings.node_id if hasattr(self.settings, 'node_id') else 'unknown'
            }
            
            # Store in time-series format
            await self.redis_client.lpush(
                "request_metrics",
                json.dumps(metric_data)
            )
            
            # Keep only last 10000 entries
            await self.redis_client.ltrim("request_metrics", 0, 9999)
            
        except Exception as e:
            logger.error(f"Error storing metrics in Redis: {e}", error=e)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if hasattr(request.client, 'host'):
            return request.client.host
        
        return 'unknown'
    
    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint is sensitive."""
        sensitive_patterns = [
            '/auth/',
            '/admin/',
            '/api/users/',
            '/api/clips/upload',
            '/api/clips/delete'
        ]
        
        return any(pattern in path for pattern in sensitive_patterns)
    
    def _requires_load_balancing(self, path: str) -> bool:
        """Check if endpoint requires load balancing."""
        # Only apply load balancing to specific internal service calls
        load_balanced_patterns = [
            '/api/clips/process',
            '/api/clips/generate',
            '/internal/'
        ]
        
        return any(pattern in path for pattern in load_balanced_patterns)
    
    def _extract_service_name(self, path: str) -> str:
        """Extract service name from path."""
        if '/api/clips/' in path:
            return 'clip-service'
        elif '/api/users/' in path:
            return 'user-service'
        elif '/internal/' in path:
            return 'internal-service'
        else:
            return 'default-service'
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary."""
        if not self.request_metrics['response_times']:
            return {"message": "No metrics available"}
        
        response_times = self.request_metrics['response_times']
        
        return {
            "total_requests": self.request_metrics['total_requests'],
            "total_errors": self.request_metrics['total_errors'],
            "error_rate": (
                self.request_metrics['total_errors'] / self.request_metrics['total_requests']
                if self.request_metrics['total_requests'] > 0 else 0
            ),
            "avg_response_time": sum(response_times) / len(response_times),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "status_codes": self.request_metrics['status_codes'],
            "top_endpoints": sorted(
                [
                    {
                        "endpoint": endpoint,
                        "count": data['count'],
                        "avg_time": data['total_time'] / data['count'],
                        "error_rate": data['errors'] / data['count']
                    }
                    for endpoint, data in self.request_metrics['endpoints'].items()
                ],
                key=lambda x: x['count'],
                reverse=True
            )[:10]
        }


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware for health check endpoints."""
    
    def __init__(self, app: ASGIApp, health_check_path: str = "/health"):
        super().__init__(app)
        self.health_check_path = health_check_path
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle health check requests."""
        if request.url.path == self.health_check_path:
            return await self._handle_health_check(request)
        
        return await call_next(request)
    
    async def _handle_health_check(self, request: Request) -> JSONResponse:
        """Handle health check request."""
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": getattr(get_settings(), 'version', '1.0.0'),
            "uptime": time.time() - getattr(request.app.state, 'start_time', time.time())
        }
        
        return JSONResponse(
            status_code=200,
            content=health_data,
            headers={"Cache-Control": "no-cache"}
        )


# Export middleware classes
__all__ = [
    'ProductionMiddleware',
    'HealthCheckMiddleware'
]