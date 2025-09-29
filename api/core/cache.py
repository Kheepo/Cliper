"""Core caching module for the API.

Provides centralized cache management and Redis client access.
"""

import redis
import os
from typing import Optional, Any
from api.utils.redis_cache import RedisCache, cache


# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client instance."""
    global _redis_client
    
    if _redis_client is None:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    
    return _redis_client


def get_cache_instance() -> RedisCache:
    """Get the default cache instance."""
    return cache


class CacheManager:
    """Central cache manager for the application."""
    
    def __init__(self):
        self.redis_client = get_redis_client()
        self.cache = get_cache_instance()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return await self.cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        return await self.cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return await self.cache.delete(key)
    
    async def clear(self) -> bool:
        """Clear all cache entries."""
        return await self.cache.clear()
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return await self.cache.exists(key)


# Global cache manager instance
cache_manager = CacheManager()