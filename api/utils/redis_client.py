"""Redis client utilities.

Provides Redis client creation and management.
"""

import redis
import os
from typing import Optional
from functools import lru_cache

from api.utils.enhanced_logging import get_logger

logger = get_logger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """Get Redis client instance.
    
    Returns:
        Redis client instance
    """
    global _redis_client
    
    if _redis_client is None:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        
        try:
            _redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            _redis_client.ping()
            logger.info(f"Connected to Redis at {redis_url}")
            
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            # Return a mock Redis client for testing
            _redis_client = MockRedisClient()
    
    return _redis_client


def reset_redis_client():
    """Reset Redis client instance."""
    global _redis_client
    _redis_client = None
    get_redis_client.cache_clear()


class MockRedisClient:
    """Mock Redis client for testing and fallback."""
    
    def __init__(self):
        self._data = {}
        self._ttl = {}
    
    def ping(self):
        """Mock ping."""
        return True
    
    def get(self, key: str) -> Optional[str]:
        """Mock get."""
        return self._data.get(key)
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Mock set."""
        self._data[key] = value
        if ex:
            self._ttl[key] = ex
        return True
    
    def delete(self, *keys: str) -> int:
        """Mock delete."""
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                self._ttl.pop(key, None)
                count += 1
        return count
    
    def exists(self, key: str) -> bool:
        """Mock exists."""
        return key in self._data
    
    def flushdb(self) -> bool:
        """Mock flushdb."""
        self._data.clear()
        self._ttl.clear()
        return True
    
    def keys(self, pattern: str = '*') -> list:
        """Mock keys."""
        if pattern == '*':
            return list(self._data.keys())
        # Simple pattern matching
        import fnmatch
        return [key for key in self._data.keys() if fnmatch.fnmatch(key, pattern)]
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """Mock hget."""
        hash_data = self._data.get(name, {})
        if isinstance(hash_data, dict):
            return hash_data.get(key)
        return None
    
    def hset(self, name: str, key: str, value: str) -> int:
        """Mock hset."""
        if name not in self._data:
            self._data[name] = {}
        if not isinstance(self._data[name], dict):
            self._data[name] = {}
        
        is_new = key not in self._data[name]
        self._data[name][key] = value
        return 1 if is_new else 0
    
    def hdel(self, name: str, *keys: str) -> int:
        """Mock hdel."""
        if name not in self._data or not isinstance(self._data[name], dict):
            return 0
        
        count = 0
        for key in keys:
            if key in self._data[name]:
                del self._data[name][key]
                count += 1
        return count
    
    def hgetall(self, name: str) -> dict:
        """Mock hgetall."""
        hash_data = self._data.get(name, {})
        if isinstance(hash_data, dict):
            return hash_data
        return {}
    
    def expire(self, key: str, time: int) -> bool:
        """Mock expire."""
        if key in self._data:
            self._ttl[key] = time
            return True
        return False
    
    def ttl(self, key: str) -> int:
        """Mock ttl."""
        if key not in self._data:
            return -2  # Key doesn't exist
        return self._ttl.get(key, -1)  # -1 means no expiration