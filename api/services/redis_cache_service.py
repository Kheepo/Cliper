#!/usr/bin/env python3
"""
Redis Caching Service

Provides comprehensive Redis-based caching functionality including:
- User session caching
- API response caching
- Database query result caching
- Rate limiting data
- Temporary data storage
- Cache invalidation strategies
"""

import json
import pickle
import hashlib
import asyncio
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import Redis
from pydantic import BaseModel

from api.config.environments import get_environment_config
from api.utils.structured_logging import get_logger

logger = get_logger(__name__)

class CacheStrategy(Enum):
    """Cache invalidation strategies"""
    TTL = "ttl"  # Time-based expiration
    LRU = "lru"  # Least Recently Used
    MANUAL = "manual"  # Manual invalidation
    WRITE_THROUGH = "write_through"  # Update cache on write
    WRITE_BEHIND = "write_behind"  # Async cache update

class SerializationMethod(Enum):
    """Data serialization methods"""
    JSON = "json"
    PICKLE = "pickle"
    STRING = "string"

@dataclass
class CacheConfig:
    """Cache configuration settings"""
    default_ttl: int = 3600  # 1 hour
    max_connections: int = 20
    retry_on_timeout: bool = True
    key_prefix: str = "cliper"
    compression_enabled: bool = True
    serialization_method: SerializationMethod = SerializationMethod.JSON
    
class CacheKey:
    """Cache key generator and manager"""
    
    def __init__(self, prefix: str = "cliper"):
        self.prefix = prefix
    
    def user_session(self, user_id: str) -> str:
        """Generate cache key for user session"""
        return f"{self.prefix}:session:user:{user_id}"
    
    def user_profile(self, user_id: str) -> str:
        """Generate cache key for user profile"""
        return f"{self.prefix}:profile:user:{user_id}"
    
    def user_settings(self, user_id: str) -> str:
        """Generate cache key for user settings"""
        return f"{self.prefix}:settings:user:{user_id}"
    
    def job_result(self, job_id: str) -> str:
        """Generate cache key for job result"""
        return f"{self.prefix}:job:result:{job_id}"
    
    def job_status(self, job_id: str) -> str:
        """Generate cache key for job status"""
        return f"{self.prefix}:job:status:{job_id}"
    
    def user_jobs(self, user_id: str, page: int = 1) -> str:
        """Generate cache key for user jobs list"""
        return f"{self.prefix}:jobs:user:{user_id}:page:{page}"
    
    def api_response(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key for API response"""
        params_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]
        return f"{self.prefix}:api:{endpoint}:{params_hash}"
    
    def rate_limit(self, identifier: str, window: str) -> str:
        """Generate cache key for rate limiting"""
        return f"{self.prefix}:ratelimit:{identifier}:{window}"
    
    def temp_data(self, identifier: str) -> str:
        """Generate cache key for temporary data"""
        return f"{self.prefix}:temp:{identifier}"
    
    def analytics(self, metric: str, period: str) -> str:
        """Generate cache key for analytics data"""
        return f"{self.prefix}:analytics:{metric}:{period}"
    
    def search_results(self, query: str, filters: Dict[str, Any]) -> str:
        """Generate cache key for search results"""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        filters_hash = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:8]
        return f"{self.prefix}:search:{query_hash}:{filters_hash}"

class RedisCacheService:
    """Comprehensive Redis caching service"""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.redis_client: Optional[Redis] = None
        self.key_generator = CacheKey(self.config.key_prefix)
        self.env_config = get_environment_config()
        
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            redis_url = self.env_config.get("REDIS_URL", "redis://localhost:6379")
            
            self.redis_client = redis.from_url(
                redis_url,
                max_connections=self.config.max_connections,
                retry_on_timeout=self.config.retry_on_timeout,
                decode_responses=False,  # We handle encoding ourselves
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis cache service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache service: {e}")
            raise
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data based on configuration"""
        try:
            if self.config.serialization_method == SerializationMethod.JSON:
                if isinstance(data, (dict, list, str, int, float, bool)) or data is None:
                    return json.dumps(data, default=str).encode('utf-8')
                else:
                    # Fallback to pickle for complex objects
                    return pickle.dumps(data)
            elif self.config.serialization_method == SerializationMethod.PICKLE:
                return pickle.dumps(data)
            elif self.config.serialization_method == SerializationMethod.STRING:
                return str(data).encode('utf-8')
            else:
                raise ValueError(f"Unsupported serialization method: {self.config.serialization_method}")
        except Exception as e:
            logger.error(f"Error serializing data: {e}")
            raise
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize data based on configuration"""
        try:
            if self.config.serialization_method == SerializationMethod.JSON:
                try:
                    return json.loads(data.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Fallback to pickle if JSON fails
                    return pickle.loads(data)
            elif self.config.serialization_method == SerializationMethod.PICKLE:
                return pickle.loads(data)
            elif self.config.serialization_method == SerializationMethod.STRING:
                return data.decode('utf-8')
            else:
                raise ValueError(f"Unsupported serialization method: {self.config.serialization_method}")
        except Exception as e:
            logger.error(f"Error deserializing data: {e}")
            raise
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache with optional TTL"""
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return False
        
        try:
            serialized_value = self._serialize_data(value)
            ttl = ttl or self.config.default_ttl
            
            await self.redis_client.setex(key, ttl, serialized_value)
            logger.debug(f"Cached data with key: {key}, TTL: {ttl}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return None
        
        try:
            cached_data = await self.redis_client.get(key)
            if cached_data is None:
                return None
            
            return self._deserialize_data(cached_data)
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return False
        
        try:
            result = await self.redis_client.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        if not self.redis_client:
            return False
        
        try:
            return bool(await self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Error checking cache key existence {key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key"""
        if not self.redis_client:
            return False
        
        try:
            return bool(await self.redis_client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Error setting expiration for key {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get time to live for a key"""
        if not self.redis_client:
            return -1
        
        try:
            return await self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {e}")
            return -1
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value in cache"""
        if not self.redis_client:
            return None
        
        try:
            return await self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {e}")
            return None
    
    async def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement a numeric value in cache"""
        if not self.redis_client:
            return None
        
        try:
            return await self.redis_client.decrby(key, amount)
        except Exception as e:
            logger.error(f"Error decrementing key {key}: {e}")
            return None
    
    async def set_if_not_exists(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value only if the key doesn't exist"""
        if not self.redis_client:
            return False
        
        try:
            serialized_value = self._serialize_data(value)
            ttl = ttl or self.config.default_ttl
            
            result = await self.redis_client.set(key, serialized_value, ex=ttl, nx=True)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error setting cache key {key} if not exists: {e}")
            return False
    
    async def get_or_set(self, key: str, factory: Callable, ttl: Optional[int] = None) -> Any:
        """Get value from cache or set it using factory function"""
        # Try to get from cache first
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        # Generate value using factory function
        try:
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()
            
            # Cache the generated value
            await self.set(key, value, ttl)
            return value
            
        except Exception as e:
            logger.error(f"Error in get_or_set for key {key}: {e}")
            raise
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern"""
        if not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Error invalidating pattern {pattern}: {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.redis_client:
            return {}
        
        try:
            info = await self.redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
                "redis_version": info.get("redis_version", "unknown")
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    # High-level caching methods for specific use cases
    
    async def cache_user_session(self, user_id: str, session_data: Dict[str, Any], ttl: int = 86400) -> bool:
        """Cache user session data (24 hours default)"""
        key = self.key_generator.user_session(user_id)
        return await self.set(key, session_data, ttl)
    
    async def get_user_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user session data"""
        key = self.key_generator.user_session(user_id)
        return await self.get(key)
    
    async def invalidate_user_session(self, user_id: str) -> bool:
        """Invalidate user session cache"""
        key = self.key_generator.user_session(user_id)
        return await self.delete(key)
    
    async def cache_user_profile(self, user_id: str, profile_data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Cache user profile data (1 hour default)"""
        key = self.key_generator.user_profile(user_id)
        return await self.set(key, profile_data, ttl)
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user profile data"""
        key = self.key_generator.user_profile(user_id)
        return await self.get(key)
    
    async def invalidate_user_data(self, user_id: str) -> int:
        """Invalidate all cached data for a user"""
        pattern = f"{self.config.key_prefix}:*:user:{user_id}*"
        return await self.invalidate_pattern(pattern)
    
    async def cache_job_result(self, job_id: str, result_data: Dict[str, Any], ttl: int = 7200) -> bool:
        """Cache job result data (2 hours default)"""
        key = self.key_generator.job_result(job_id)
        return await self.set(key, result_data, ttl)
    
    async def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get cached job result data"""
        key = self.key_generator.job_result(job_id)
        return await self.get(key)
    
    async def cache_api_response(self, endpoint: str, params: Dict[str, Any], response_data: Any, ttl: int = 300) -> bool:
        """Cache API response (5 minutes default)"""
        key = self.key_generator.api_response(endpoint, params)
        return await self.set(key, response_data, ttl)
    
    async def get_cached_api_response(self, endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
        """Get cached API response"""
        key = self.key_generator.api_response(endpoint, params)
        return await self.get(key)
    
    async def rate_limit_check(self, identifier: str, window: str, limit: int, ttl: int = 3600) -> Dict[str, Any]:
        """Check and update rate limit counter"""
        key = self.key_generator.rate_limit(identifier, window)
        
        try:
            current = await self.get(key) or 0
            if current >= limit:
                return {
                    "allowed": False,
                    "current": current,
                    "limit": limit,
                    "reset_time": await self.ttl(key)
                }
            
            # Increment counter
            new_count = await self.increment(key)
            if new_count == 1:  # First request in window
                await self.expire(key, ttl)
            
            return {
                "allowed": True,
                "current": new_count,
                "limit": limit,
                "reset_time": await self.ttl(key)
            }
            
        except Exception as e:
            logger.error(f"Error in rate limit check: {e}")
            # Allow request on error
            return {
                "allowed": True,
                "current": 0,
                "limit": limit,
                "reset_time": ttl
            }
    
    async def store_temp_data(self, identifier: str, data: Any, ttl: int = 3600) -> bool:
        """Store temporary data with expiration"""
        key = self.key_generator.temp_data(identifier)
        return await self.set(key, data, ttl)
    
    async def get_temp_data(self, identifier: str) -> Optional[Any]:
        """Get temporary data"""
        key = self.key_generator.temp_data(identifier)
        return await self.get(key)
    
    async def cleanup(self):
        """Clean up Redis connections"""
        try:
            if self.redis_client:
                await self.redis_client.close()
                logger.info("Redis cache service connections closed")
        except Exception as e:
            logger.error(f"Error during Redis cleanup: {e}")
    
    @asynccontextmanager
    async def pipeline(self):
        """Context manager for Redis pipeline operations"""
        if not self.redis_client:
            raise RuntimeError("Redis client not initialized")
        
        pipe = self.redis_client.pipeline()
        try:
            yield pipe
            await pipe.execute()
        except Exception as e:
            logger.error(f"Error in Redis pipeline: {e}")
            raise
        finally:
            await pipe.reset()

# Global cache service instance
cache_service: Optional[RedisCacheService] = None

async def get_cache_service() -> RedisCacheService:
    """Get or create global cache service instance"""
    global cache_service
    
    if cache_service is None:
        cache_service = RedisCacheService()
        await cache_service.initialize()
    
    return cache_service

async def initialize_cache_service(config: Optional[CacheConfig] = None) -> RedisCacheService:
    """Initialize global cache service with custom config"""
    global cache_service
    
    cache_service = RedisCacheService(config)
    await cache_service.initialize()
    
    return cache_service

# Decorator for caching function results
def cache_result(key_template: str, ttl: int = 3600):
    """Decorator to cache function results"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key from template and arguments
            cache_key = key_template.format(*args, **kwargs)
            
            service = await get_cache_service()
            
            # Try to get from cache
            cached_result = await service.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await service.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator

# Example usage functions
async def example_usage():
    """Example of how to use the Redis cache service"""
    # Initialize cache service
    cache = await get_cache_service()
    
    # Basic operations
    await cache.set("test_key", {"data": "value"}, ttl=300)
    result = await cache.get("test_key")
    print(f"Cached result: {result}")
    
    # User session caching
    await cache.cache_user_session("user123", {
        "user_id": "user123",
        "login_time": datetime.now().isoformat(),
        "permissions": ["read", "write"]
    })
    
    session = await cache.get_user_session("user123")
    print(f"User session: {session}")
    
    # Rate limiting
    rate_limit_result = await cache.rate_limit_check("user123", "minute", 10, 60)
    print(f"Rate limit: {rate_limit_result}")
    
    # Cache statistics
    stats = await cache.get_cache_stats()
    print(f"Cache stats: {stats}")
    
    # Cleanup
    await cache.cleanup()

if __name__ == "__main__":
    asyncio.run(example_usage())