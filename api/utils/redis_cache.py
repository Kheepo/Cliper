import redis
import json
import pickle
import logging
from typing import Any, Optional, Union
import os
from datetime import timedelta

logger = logging.getLogger(__name__)

class RedisCache:
    """
    Redis cache utility for storing transcription results and other frequently accessed data.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis connection.
        
        Args:
            redis_url: Redis connection URL. If None, uses environment variable.
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """
        Establish Redis connection with retry logic.
        """
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _ensure_connection(self):
        """
        Ensure Redis connection is active, reconnect if necessary.
        """
        if self.redis_client is None:
            self._connect()
            return
        
        try:
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis connection lost, reconnecting: {e}")
            self._connect()
    
    def _serialize_value(self, value: Any) -> bytes:
        """
        Serialize value for Redis storage.
        
        Args:
            value: Value to serialize
            
        Returns:
            Serialized bytes
        """
        try:
            # Try JSON first for simple types
            if isinstance(value, (dict, list, str, int, float, bool, type(None))):
                return json.dumps(value).encode('utf-8')
            else:
                # Use pickle for complex objects
                return pickle.dumps(value)
        except Exception as e:
            logger.error(f"Error serializing value: {e}")
            raise
    
    def _deserialize_value(self, data: bytes) -> Any:
        """
        Deserialize value from Redis storage.
        
        Args:
            data: Serialized bytes
            
        Returns:
            Deserialized value
        """
        try:
            # Try JSON first
            try:
                return json.loads(data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fall back to pickle
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Error deserializing value: {e}")
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if self.redis_client is None:
            logger.warning("Redis not available, cache miss")
            return None
        
        try:
            self._ensure_connection()
            data = self.redis_client.get(key)
            
            if data is None:
                return None
            
            return self._deserialize_value(data)
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds or timedelta
            
        Returns:
            True if successful, False otherwise
        """
        if self.redis_client is None:
            logger.warning("Redis not available, cache set failed")
            return False
        
        try:
            self._ensure_connection()
            serialized_value = self._serialize_value(value)
            
            if expire is not None:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                return self.redis_client.setex(key, expire, serialized_value)
            else:
                return self.redis_client.set(key, serialized_value)
                
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        if self.redis_client is None:
            logger.warning("Redis not available, cache delete failed")
            return False
        
        try:
            self._ensure_connection()
            return bool(self.redis_client.delete(key))
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        if self.redis_client is None:
            return False
        
        try:
            self._ensure_connection()
            return bool(self.redis_client.exists(key))
            
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a numeric value in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment, or None if failed
        """
        if self.redis_client is None:
            return None
        
        try:
            self._ensure_connection()
            return self.redis_client.incrby(key, amount)
            
        except Exception as e:
            logger.error(f"Error incrementing cache key {key}: {e}")
            return None
    
    async def get_many(self, keys: list) -> dict:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key-value pairs
        """
        if self.redis_client is None or not keys:
            return {}
        
        try:
            self._ensure_connection()
            values = self.redis_client.mget(keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = self._deserialize_value(value)
                    except Exception as e:
                        logger.error(f"Error deserializing key {key}: {e}")
                        result[key] = None
                else:
                    result[key] = None
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting multiple cache keys: {e}")
            return {}
    
    async def set_many(self, mapping: dict, expire: Optional[int] = None) -> bool:
        """
        Set multiple values in cache.
        
        Args:
            mapping: Dictionary of key-value pairs
            expire: Expiration time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if self.redis_client is None or not mapping:
            return False
        
        try:
            self._ensure_connection()
            
            # Serialize all values
            serialized_mapping = {}
            for key, value in mapping.items():
                serialized_mapping[key] = self._serialize_value(value)
            
            # Use pipeline for efficiency
            pipe = self.redis_client.pipeline()
            pipe.mset(serialized_mapping)
            
            # Set expiration if specified
            if expire is not None:
                for key in mapping.keys():
                    pipe.expire(key, expire)
            
            pipe.execute()
            return True
            
        except Exception as e:
            logger.error(f"Error setting multiple cache keys: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern.
        
        Args:
            pattern: Redis pattern (e.g., 'transcription:*')
            
        Returns:
            Number of keys deleted
        """
        if self.redis_client is None:
            return 0
        
        try:
            self._ensure_connection()
            keys = self.redis_client.keys(pattern)
            
            if keys:
                return self.redis_client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error(f"Error clearing pattern {pattern}: {e}")
            return 0
    
    def get_stats(self) -> dict:
        """
        Get Redis connection and memory statistics.
        
        Returns:
            Dictionary with Redis stats
        """
        if self.redis_client is None:
            return {'status': 'disconnected'}
        
        try:
            self._ensure_connection()
            info = self.redis_client.info()
            
            return {
                'status': 'connected',
                'used_memory': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': (
                    info.get('keyspace_hits', 0) / 
                    max(1, info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0))
                ) * 100
            }
            
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def close(self):
        """
        Close Redis connection.
        """
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self.redis_client = None

# Global cache instance
cache = RedisCache()