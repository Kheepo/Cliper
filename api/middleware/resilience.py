"""Resilience middleware for error handling, circuit breakers, and retry mechanisms."""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
from contextlib import asynccontextmanager

import redis
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_exception: type = Exception
    name: str = "default"

@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    state: CircuitState = CircuitState.CLOSED
    total_requests: int = 0
    
class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""
    
    def __init__(self, config: CircuitBreakerConfig, redis_client: Optional[redis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        
    async def _get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker stats from Redis or memory."""
        if self.redis_client:
            try:
                key = f"circuit_breaker:{self.config.name}"
                data = await self.redis_client.hgetall(key)
                if data:
                    return CircuitBreakerStats(
                        failure_count=int(data.get(b'failure_count', 0)),
                        success_count=int(data.get(b'success_count', 0)),
                        last_failure_time=float(data.get(b'last_failure_time', 0)) or None,
                        state=CircuitState(data.get(b'state', b'closed').decode()),
                        total_requests=int(data.get(b'total_requests', 0))
                    )
            except Exception as e:
                logger.warning(f"Failed to get circuit breaker stats from Redis: {e}")
        
        return self.stats
    
    async def _update_stats(self, stats: CircuitBreakerStats):
        """Update circuit breaker stats in Redis or memory."""
        if self.redis_client:
            try:
                key = f"circuit_breaker:{self.config.name}"
                await self.redis_client.hset(key, mapping={
                    'failure_count': stats.failure_count,
                    'success_count': stats.success_count,
                    'last_failure_time': stats.last_failure_time or 0,
                    'state': stats.state.value,
                    'total_requests': stats.total_requests
                })
                await self.redis_client.expire(key, 3600)  # 1 hour TTL
            except Exception as e:
                logger.warning(f"Failed to update circuit breaker stats in Redis: {e}")
        
        self.stats = stats
    
    async def _should_attempt_reset(self, stats: CircuitBreakerStats) -> bool:
        """Check if circuit should attempt reset."""
        if stats.state != CircuitState.OPEN:
            return False
        
        if not stats.last_failure_time:
            return True
        
        return time.time() - stats.last_failure_time >= self.config.recovery_timeout
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            stats = await self._get_stats()
            stats.total_requests += 1
            
            # Check if circuit is open
            if stats.state == CircuitState.OPEN:
                if not await self._should_attempt_reset(stats):
                    raise HTTPException(
                        status_code=503,
                        detail=f"Circuit breaker '{self.config.name}' is open"
                    )
                else:
                    stats.state = CircuitState.HALF_OPEN
                    await self._update_stats(stats)
            
            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success - reset failure count
                stats.success_count += 1
                if stats.state == CircuitState.HALF_OPEN:
                    stats.state = CircuitState.CLOSED
                    stats.failure_count = 0
                
                await self._update_stats(stats)
                return result
                
            except self.config.expected_exception as e:
                # Failure - increment failure count
                stats.failure_count += 1
                stats.last_failure_time = time.time()
                
                if stats.failure_count >= self.config.failure_threshold:
                    stats.state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit breaker '{self.config.name}' opened after {stats.failure_count} failures"
                    )
                
                await self._update_stats(stats)
                raise e

class RetryConfig:
    """Configuration for retry mechanism."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: List[type] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [Exception]

def retry_with_backoff(config: RetryConfig):
    """Decorator for retry with exponential backoff."""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                        
                except Exception as e:
                    last_exception = e
                    
                    # Check if exception is retryable
                    if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                        raise e
                    
                    # Don't retry on last attempt
                    if attempt == config.max_attempts - 1:
                        break
                    
                    # Calculate delay
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    await asyncio.sleep(delay)
            
            # All attempts failed
            logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                        
                except Exception as e:
                    last_exception = e
                    
                    # Check if exception is retryable
                    if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                        raise e
                    
                    # Don't retry on last attempt
                    if attempt == config.max_attempts - 1:
                        break
                    
                    # Calculate delay
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    time.sleep(delay)
            
            # All attempts failed
            logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive error handling and resilience."""
    
    def __init__(self, app, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        self.redis_client = redis_client
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig) -> CircuitBreaker:
        """Get or create circuit breaker."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
        return self.circuit_breakers[name]
    
    async def dispatch(self, request: Request, call_next):
        """Handle request with error handling and resilience."""
        start_time = time.time()
        
        try:
            # Add request context
            request.state.start_time = start_time
            request.state.request_id = getattr(request.state, 'request_id', 'unknown')
            
            response = await call_next(request)
            
            # Log successful requests
            duration = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Duration: {duration:.3f}s"
            )
            
            return response
            
        except HTTPException as e:
            # Handle HTTP exceptions
            duration = time.time() - start_time
            logger.warning(
                f"HTTP exception: {request.method} {request.url.path} "
                f"- Status: {e.status_code} - Duration: {duration:.3f}s - Error: {e.detail}"
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.detail,
                    "status_code": e.status_code,
                    "request_id": getattr(request.state, 'request_id', 'unknown'),
                    "timestamp": time.time()
                }
            )
            
        except Exception as e:
            # Handle unexpected exceptions
            duration = time.time() - start_time
            logger.error(
                f"Unexpected error: {request.method} {request.url.path} "
                f"- Duration: {duration:.3f}s - Error: {str(e)}",
                exc_info=True
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "status_code": 500,
                    "request_id": getattr(request.state, 'request_id', 'unknown'),
                    "timestamp": time.time()
                }
            )

# Graceful degradation utilities
class GracefulDegradation:
    """Utilities for graceful service degradation."""
    
    @staticmethod
    async def with_fallback(primary_func: Callable, fallback_func: Callable, *args, **kwargs):
        """Execute primary function with fallback on failure."""
        try:
            if asyncio.iscoroutinefunction(primary_func):
                return await primary_func(*args, **kwargs)
            else:
                return primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Primary function failed: {e}. Using fallback.")
            
            try:
                if asyncio.iscoroutinefunction(fallback_func):
                    return await fallback_func(*args, **kwargs)
                else:
                    return fallback_func(*args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"Fallback function also failed: {fallback_error}")
                raise e  # Raise original exception
    
    @staticmethod
    @asynccontextmanager
    async def timeout_context(timeout_seconds: float):
        """Context manager for operation timeout."""
        try:
            async with asyncio.timeout(timeout_seconds):
                yield
        except asyncio.TimeoutError:
            logger.warning(f"Operation timed out after {timeout_seconds}s")
            raise HTTPException(status_code=408, detail="Request timeout")

class RetryMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic request retries with exponential backoff."""
    
    def __init__(self, app, config: Optional[RetryConfig] = None):
        super().__init__(app)
        self.config = config or RetryConfig()
        
    async def dispatch(self, request: Request, call_next):
        """Handle request with retry logic."""
        
        @retry_with_backoff(self.config)
        async def make_request():
            return await call_next(request)
        
        try:
            return await make_request()
        except Exception as e:
            logger.error(f"Request failed after all retries: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "status_code": 503,
                    "request_id": getattr(request.state, 'request_id', 'unknown'),
                    "timestamp": time.time()
                }
            )

# Health check utilities
class HealthChecker:
    """Health check utilities for services."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.checks: Dict[str, Callable] = {}
    
    def register_check(self, name: str, check_func: Callable):
        """Register a health check function."""
        self.checks[name] = check_func
    
    async def run_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                results[name] = {
                    "status": "healthy",
                    "details": result
                }
            except Exception as e:
                overall_healthy = False
                results[name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return {
            "overall_status": "healthy" if overall_healthy else "unhealthy",
            "checks": results,
            "timestamp": time.time()
        }