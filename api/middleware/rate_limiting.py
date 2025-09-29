"""Advanced rate limiting and throttling middleware.

Provides:
- Multiple rate limiting algorithms (token bucket, sliding window, fixed window)
- User-based and IP-based rate limiting
- Dynamic rate limit adjustment
- Rate limit bypass for premium users
- Distributed rate limiting with Redis
- Rate limit analytics and monitoring
"""

import time
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

import redis.asyncio as redis
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger, SecurityEvent
from api.config.production import get_settings


logger = get_logger(__name__)
settings = get_settings()


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithms."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitScope(str, Enum):
    """Rate limit scope."""
    GLOBAL = "global"
    USER = "user"
    IP = "ip"
    ENDPOINT = "endpoint"
    API_KEY = "api_key"


class UserTier(str, Enum):
    """User tier for different rate limits."""
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    ADMIN = "admin"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_limit: int
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    scope: RateLimitScope = RateLimitScope.USER
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RateLimitStatus(BaseModel):
    """Rate limit status response."""
    allowed: bool
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None
    scope: str
    algorithm: str
    
    class Config:
        use_enum_values = True


class RateLimitExceeded(HTTPException):
    """Rate limit exceeded exception."""
    
    def __init__(self, status: RateLimitStatus, detail: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={
                "X-RateLimit-Limit": str(status.limit),
                "X-RateLimit-Remaining": str(status.remaining),
                "X-RateLimit-Reset": str(int(status.reset_time.timestamp())),
                "Retry-After": str(status.retry_after) if status.retry_after else "60"
            }
        )
        self.status = status


class TokenBucket:
    """Token bucket rate limiter."""
    
    def __init__(self, capacity: int, refill_rate: float, redis_client: Optional[redis.Redis] = None):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.redis_client = redis_client
        self.local_buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            'tokens': capacity,
            'last_refill': time.time()
        })
    
    async def is_allowed(self, key: str, tokens_requested: int = 1) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed and return status."""
        if self.redis_client:
            return await self._redis_check(key, tokens_requested)
        else:
            return await self._local_check(key, tokens_requested)
    
    async def _local_check(self, key: str, tokens_requested: int) -> tuple[bool, Dict[str, Any]]:
        """Local token bucket check."""
        bucket = self.local_buckets[key]
        current_time = time.time()
        
        # Refill tokens
        time_passed = current_time - bucket['last_refill']
        tokens_to_add = time_passed * self.refill_rate
        bucket['tokens'] = min(self.capacity, bucket['tokens'] + tokens_to_add)
        bucket['last_refill'] = current_time
        
        # Check if request can be served
        if bucket['tokens'] >= tokens_requested:
            bucket['tokens'] -= tokens_requested
            return True, {
                'remaining': int(bucket['tokens']),
                'reset_time': current_time + (self.capacity - bucket['tokens']) / self.refill_rate
            }
        else:
            return False, {
                'remaining': int(bucket['tokens']),
                'reset_time': current_time + (tokens_requested - bucket['tokens']) / self.refill_rate
            }
    
    async def _redis_check(self, key: str, tokens_requested: int) -> tuple[bool, Dict[str, Any]]:
        """Redis-based distributed token bucket check."""
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local current_time = tonumber(ARGV[4])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or current_time
        
        -- Refill tokens
        local time_passed = current_time - last_refill
        local tokens_to_add = time_passed * refill_rate
        tokens = math.min(capacity, tokens + tokens_to_add)
        
        -- Check if request can be served
        local allowed = 0
        local reset_time = current_time + (capacity - tokens) / refill_rate
        
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            allowed = 1
        else
            reset_time = current_time + (tokens_requested - tokens) / refill_rate
        end
        
        -- Update bucket
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', current_time)
        redis.call('EXPIRE', key, 3600)  -- 1 hour TTL
        
        return {allowed, math.floor(tokens), reset_time}
        """
        
        try:
            result = await self.redis_client.eval(
                lua_script,
                1,
                f"rate_limit:token_bucket:{key}",
                self.capacity,
                self.refill_rate,
                tokens_requested,
                time.time()
            )
            
            allowed, remaining, reset_time = result
            return bool(allowed), {
                'remaining': remaining,
                'reset_time': reset_time
            }
            
        except Exception as e:
            logger.error(f"Redis token bucket error: {e}")
            # Fallback to local check
            return await self._local_check(key, tokens_requested)


class SlidingWindowCounter:
    """Sliding window rate limiter."""
    
    def __init__(self, window_size: int, limit: int, redis_client: Optional[redis.Redis] = None):
        self.window_size = window_size  # seconds
        self.limit = limit
        self.redis_client = redis_client
        self.local_windows: Dict[str, List[float]] = defaultdict(list)
    
    async def is_allowed(self, key: str) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed."""
        if self.redis_client:
            return await self._redis_check(key)
        else:
            return await self._local_check(key)
    
    async def _local_check(self, key: str) -> tuple[bool, Dict[str, Any]]:
        """Local sliding window check."""
        current_time = time.time()
        window = self.local_windows[key]
        
        # Remove old entries
        cutoff_time = current_time - self.window_size
        window[:] = [t for t in window if t > cutoff_time]
        
        # Check limit
        if len(window) < self.limit:
            window.append(current_time)
            return True, {
                'remaining': self.limit - len(window),
                'reset_time': current_time + self.window_size
            }
        else:
            # Calculate when the oldest request will expire
            oldest_request = min(window) if window else current_time
            reset_time = oldest_request + self.window_size
            
            return False, {
                'remaining': 0,
                'reset_time': reset_time
            }
    
    async def _redis_check(self, key: str) -> tuple[bool, Dict[str, Any]]:
        """Redis-based sliding window check."""
        lua_script = """
        local key = KEYS[1]
        local window_size = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        local current_time = tonumber(ARGV[3])
        
        -- Remove old entries
        local cutoff_time = current_time - window_size
        redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff_time)
        
        -- Count current requests
        local current_count = redis.call('ZCARD', key)
        
        if current_count < limit then
            -- Add current request
            redis.call('ZADD', key, current_time, current_time)
            redis.call('EXPIRE', key, window_size)
            return {1, limit - current_count - 1, current_time + window_size}
        else
            -- Get oldest request time
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            local reset_time = current_time + window_size
            if #oldest > 0 then
                reset_time = tonumber(oldest[2]) + window_size
            end
            return {0, 0, reset_time}
        end
        """
        
        try:
            result = await self.redis_client.eval(
                lua_script,
                1,
                f"rate_limit:sliding_window:{key}",
                self.window_size,
                self.limit,
                time.time()
            )
            
            allowed, remaining, reset_time = result
            return bool(allowed), {
                'remaining': remaining,
                'reset_time': reset_time
            }
            
        except Exception as e:
            logger.error(f"Redis sliding window error: {e}")
            return await self._local_check(key)


class RateLimitManager:
    """Manages rate limiting for different scopes and users."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using local rate limiting.")
        
        # Default rate limit configurations
        self.configs = {
            UserTier.FREE: RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=1000,
                requests_per_day=10000,
                burst_limit=10
            ),
            UserTier.PREMIUM: RateLimitConfig(
                requests_per_minute=300,
                requests_per_hour=10000,
                requests_per_day=100000,
                burst_limit=50
            ),
            UserTier.ENTERPRISE: RateLimitConfig(
                requests_per_minute=1000,
                requests_per_hour=50000,
                requests_per_day=1000000,
                burst_limit=200
            ),
            UserTier.ADMIN: RateLimitConfig(
                requests_per_minute=10000,
                requests_per_hour=500000,
                requests_per_day=10000000,
                burst_limit=1000
            )
        }
        
        # Rate limiters
        self.limiters: Dict[str, Union[TokenBucket, SlidingWindowCounter]] = {}
        
        # Analytics
        self.analytics = defaultdict(lambda: {
            'total_requests': 0,
            'blocked_requests': 0,
            'last_reset': time.time()
        })
    
    def get_user_tier(self, user_id: Optional[str], api_key: Optional[str]) -> UserTier:
        """Determine user tier based on user ID or API key."""
        # This would typically query a database or cache
        # For now, return default tier
        if not user_id and not api_key:
            return UserTier.FREE
        
        # Example logic - replace with actual implementation
        if api_key and api_key.startswith('admin_'):
            return UserTier.ADMIN
        elif api_key and api_key.startswith('enterprise_'):
            return UserTier.ENTERPRISE
        elif api_key and api_key.startswith('premium_'):
            return UserTier.PREMIUM
        else:
            return UserTier.FREE
    
    def get_rate_limit_key(self, scope: RateLimitScope, identifier: str, 
                          endpoint: Optional[str] = None) -> str:
        """Generate rate limit key."""
        if scope == RateLimitScope.GLOBAL:
            return "global"
        elif scope == RateLimitScope.USER:
            return f"user:{identifier}"
        elif scope == RateLimitScope.IP:
            return f"ip:{identifier}"
        elif scope == RateLimitScope.ENDPOINT:
            return f"endpoint:{endpoint}:{identifier}"
        elif scope == RateLimitScope.API_KEY:
            return f"api_key:{identifier}"
        else:
            return f"unknown:{identifier}"
    
    async def check_rate_limit(self, request: Request, user_id: Optional[str] = None, 
                             api_key: Optional[str] = None) -> RateLimitStatus:
        """Check rate limit for a request."""
        # Determine user tier
        user_tier = self.get_user_tier(user_id, api_key)
        config = self.configs[user_tier]
        
        if not config.enabled:
            return RateLimitStatus(
                allowed=True,
                limit=999999,
                remaining=999999,
                reset_time=datetime.utcnow() + timedelta(hours=1),
                scope=config.scope.value,
                algorithm=config.algorithm.value
            )
        
        # Determine identifier
        if config.scope == RateLimitScope.USER and user_id:
            identifier = user_id
        elif config.scope == RateLimitScope.API_KEY and api_key:
            identifier = api_key
        else:
            # Fallback to IP
            identifier = self._get_client_ip(request)
            config.scope = RateLimitScope.IP
        
        # Get rate limit key
        endpoint = f"{request.method}:{request.url.path}"
        rate_limit_key = self.get_rate_limit_key(config.scope, identifier, endpoint)
        
        # Check different time windows
        checks = [
            ('minute', config.requests_per_minute, 60),
            ('hour', config.requests_per_hour, 3600),
            ('day', config.requests_per_day, 86400)
        ]
        
        for window_name, limit, window_size in checks:
            limiter_key = f"{rate_limit_key}:{window_name}"
            
            if config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                if limiter_key not in self.limiters:
                    refill_rate = limit / window_size  # tokens per second
                    self.limiters[limiter_key] = TokenBucket(
                        capacity=min(limit, config.burst_limit),
                        refill_rate=refill_rate,
                        redis_client=self.redis_client
                    )
                
                allowed, status_info = await self.limiters[limiter_key].is_allowed(limiter_key)
                
            elif config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
                if limiter_key not in self.limiters:
                    self.limiters[limiter_key] = SlidingWindowCounter(
                        window_size=window_size,
                        limit=limit,
                        redis_client=self.redis_client
                    )
                
                allowed, status_info = await self.limiters[limiter_key].is_allowed(limiter_key)
            
            else:
                # Default to sliding window
                if limiter_key not in self.limiters:
                    self.limiters[limiter_key] = SlidingWindowCounter(
                        window_size=window_size,
                        limit=limit,
                        redis_client=self.redis_client
                    )
                
                allowed, status_info = await self.limiters[limiter_key].is_allowed(limiter_key)
            
            if not allowed:
                # Update analytics
                self.analytics[rate_limit_key]['blocked_requests'] += 1
                
                # Log security event
                await self._log_rate_limit_exceeded(request, user_tier, window_name, limit)
                
                return RateLimitStatus(
                    allowed=False,
                    limit=limit,
                    remaining=status_info.get('remaining', 0),
                    reset_time=datetime.fromtimestamp(status_info.get('reset_time', time.time() + 60)),
                    retry_after=int(status_info.get('reset_time', time.time() + 60) - time.time()),
                    scope=config.scope.value,
                    algorithm=config.algorithm.value
                )
        
        # Update analytics
        self.analytics[rate_limit_key]['total_requests'] += 1
        
        # All checks passed
        return RateLimitStatus(
            allowed=True,
            limit=config.requests_per_minute,
            remaining=config.requests_per_minute - 1,
            reset_time=datetime.utcnow() + timedelta(minutes=1),
            scope=config.scope.value,
            algorithm=config.algorithm.value
        )
    
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
        return request.client.host if request.client else 'unknown'
    
    async def _log_rate_limit_exceeded(self, request: Request, user_tier: UserTier, 
                                     window: str, limit: int):
        """Log rate limit exceeded event."""
        security_logger = logger
        
        event = SecurityEvent(
            event_type='rate_limit_exceeded',
            severity='medium',
            source_ip=self._get_client_ip(request),
            user_agent=request.headers.get('User-Agent', 'unknown'),
            details={
                'endpoint': f"{request.method} {request.url.path}",
                'user_tier': user_tier.value,
                'window': window,
                'limit': limit,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        security_logger.security(event)
    
    async def get_analytics(self) -> Dict[str, Any]:
        """Get rate limiting analytics."""
        return dict(self.analytics)
    
    async def reset_rate_limits(self, identifier: str, scope: RateLimitScope):
        """Reset rate limits for a specific identifier."""
        pattern = self.get_rate_limit_key(scope, identifier)
        
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(f"rate_limit:*:{pattern}*")
                if keys:
                    await self.redis_client.delete(*keys)
                logger.info(f"Reset rate limits for {pattern}")
            except Exception as e:
                logger.error(f"Error resetting rate limits: {e}")
        else:
            # Reset local limiters
            keys_to_remove = [k for k in self.limiters.keys() if pattern in k]
            for key in keys_to_remove:
                del self.limiters[key]
            logger.info(f"Reset local rate limits for {pattern}")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    def __init__(self, app, rate_limit_manager: RateLimitManager):
        super().__init__(app)
        self.rate_limit_manager = rate_limit_manager
        
        # Exempt paths (health checks, etc.)
        self.exempt_paths = [
            '/health',
            '/metrics',
            '/docs',
            '/redoc',
            '/openapi.json'
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)
        
        # Extract user information
        user_id = None
        api_key = None
        
        # Try to get user ID from JWT token or session
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            # This would typically decode JWT and extract user ID
            # For now, we'll use a placeholder
            pass
        
        # Try to get API key
        api_key = request.headers.get('X-API-Key') or request.query_params.get('api_key')
        
        try:
            # Check rate limit
            status = await self.rate_limit_manager.check_rate_limit(request, user_id, api_key)
            
            if not status.allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        'error': 'Rate limit exceeded',
                        'message': f'Too many requests. Limit: {status.limit} per window.',
                        'retry_after': status.retry_after
                    },
                    headers={
                        'X-RateLimit-Limit': str(status.limit),
                        'X-RateLimit-Remaining': str(status.remaining),
                        'X-RateLimit-Reset': str(int(status.reset_time.timestamp())),
                        'Retry-After': str(status.retry_after) if status.retry_after else '60'
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to response
            response.headers['X-RateLimit-Limit'] = str(status.limit)
            response.headers['X-RateLimit-Remaining'] = str(status.remaining)
            response.headers['X-RateLimit-Reset'] = str(int(status.reset_time.timestamp()))
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Continue without rate limiting on error
            return await call_next(request)


# Global rate limit manager
rate_limit_manager = RateLimitManager(redis_url=getattr(settings, 'redis_url', None))


def get_rate_limit_manager() -> RateLimitManager:
    """Get the global rate limit manager."""
    return rate_limit_manager