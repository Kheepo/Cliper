"""Redis service for caching and session management.

This module provides Redis-based caching for transcription results,
video metadata, and other frequently accessed data to improve performance.
"""

import json
import logging
import hashlib
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta

try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    aioredis = None

from api.utils.config import get_redis_config

logger = logging.getLogger(__name__)


class RedisService:
    """Redis service for caching and data management."""
    
    def __init__(self):
        self.client = None
        self.async_client = None
        self.enabled = False
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, caching disabled")
            return
        
        try:
            config = get_redis_config()
            
            # Synchronous client
            self.client = redis.Redis(
                host=config.get('host', 'localhost'),
                port=config.get('port', 6379),
                db=config.get('db', 0),
                password=config.get('password'),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Asynchronous client
            self.async_client = aioredis.Redis(
                host=config.get('host', 'localhost'),
                port=config.get('port', 6379),
                db=config.get('db', 0),
                password=config.get('password'),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.client.ping()
            self.enabled = True
            logger.info("Redis connection established")
            
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self.enabled = False
    
    def _generate_cache_key(self, prefix: str, *args) -> str:
        """Generate a cache key from prefix and arguments."""
        key_data = f"{prefix}:{'_'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.enabled or not self.async_client:
            return None
        
        try:
            value = await self.async_client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis get error for key {key}: {e}")
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600
    ) -> bool:
        """Set value in cache with TTL."""
        if not self.enabled or not self.async_client:
            return False
        
        try:
            serialized_value = json.dumps(value, default=str)
            await self.async_client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.warning(f"Redis set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.enabled or not self.async_client:
            return False
        
        try:
            await self.async_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.enabled or not self.async_client:
            return False
        
        try:
            return bool(await self.async_client.exists(key))
        except Exception as e:
            logger.warning(f"Redis exists error for key {key}: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter in cache."""
        if not self.enabled or not self.async_client:
            return None
        
        try:
            return await self.async_client.incrby(key, amount)
        except Exception as e:
            logger.warning(f"Redis increment error for key {key}: {e}")
            return None
    
    async def set_hash(self, key: str, mapping: Dict[str, Any], ttl: int = 3600) -> bool:
        """Set hash in cache."""
        if not self.enabled or not self.async_client:
            return False
        
        try:
            # Serialize values in mapping
            serialized_mapping = {
                k: json.dumps(v, default=str) for k, v in mapping.items()
            }
            await self.async_client.hset(key, mapping=serialized_mapping)
            await self.async_client.expire(key, ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis set_hash error for key {key}: {e}")
            return False
    
    async def get_hash(self, key: str) -> Optional[Dict[str, Any]]:
        """Get hash from cache."""
        if not self.enabled or not self.async_client:
            return None
        
        try:
            hash_data = await self.async_client.hgetall(key)
            if hash_data:
                return {
                    k: json.loads(v) for k, v in hash_data.items()
                }
        except Exception as e:
            logger.warning(f"Redis get_hash error for key {key}: {e}")
        
        return None
    
    # Specialized caching methods for video processing
    
    async def cache_transcription(
        self,
        video_path: str,
        transcription_data: Dict[str, Any],
        ttl: int = 86400  # 24 hours
    ) -> bool:
        """Cache transcription results."""
        key = self._generate_cache_key("transcription", video_path)
        return await self.set(key, transcription_data, ttl)
    
    async def get_cached_transcription(
        self,
        video_path: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached transcription results."""
        key = self._generate_cache_key("transcription", video_path)
        return await self.get(key)
    
    async def cache_video_metadata(
        self,
        video_path: str,
        metadata: Dict[str, Any],
        ttl: int = 3600  # 1 hour
    ) -> bool:
        """Cache video metadata."""
        key = self._generate_cache_key("video_metadata", video_path)
        return await self.set(key, metadata, ttl)
    
    async def get_cached_video_metadata(
        self,
        video_path: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached video metadata."""
        key = self._generate_cache_key("video_metadata", video_path)
        return await self.get(key)
    
    async def cache_clip_segments(
        self,
        video_path: str,
        platform: str,
        segments: List[Dict[str, Any]],
        ttl: int = 1800  # 30 minutes
    ) -> bool:
        """Cache clip segments for a video and platform."""
        key = self._generate_cache_key("clip_segments", video_path, platform)
        return await self.set(key, segments, ttl)
    
    async def get_cached_clip_segments(
        self,
        video_path: str,
        platform: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached clip segments."""
        key = self._generate_cache_key("clip_segments", video_path, platform)
        return await self.get(key)
    
    async def cache_processing_status(
        self,
        clip_id: str,
        status_data: Dict[str, Any],
        ttl: int = 3600  # 1 hour
    ) -> bool:
        """Cache processing status for a clip."""
        key = self._generate_cache_key("processing_status", clip_id)
        return await self.set(key, status_data, ttl)
    
    async def get_cached_processing_status(
        self,
        clip_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached processing status."""
        key = self._generate_cache_key("processing_status", clip_id)
        return await self.get(key)
    
    async def increment_processing_counter(
        self,
        counter_type: str,
        identifier: str = "global"
    ) -> Optional[int]:
        """Increment processing counter."""
        key = self._generate_cache_key("counter", counter_type, identifier)
        return await self.increment(key)
    
    async def set_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int = 3600
    ) -> bool:
        """Set rate limit for an identifier."""
        key = self._generate_cache_key("rate_limit", identifier)
        return await self.set(key, limit, window_seconds)
    
    async def check_rate_limit(
        self,
        identifier: str
    ) -> Optional[int]:
        """Check current rate limit count."""
        key = self._generate_cache_key("rate_limit", identifier)
        return await self.get(key)
    
    async def clear_cache_pattern(self, pattern: str) -> int:
        """Clear cache entries matching pattern."""
        if not self.enabled or not self.async_client:
            return 0
        
        try:
            keys = await self.async_client.keys(pattern)
            if keys:
                return await self.async_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis clear_cache_pattern error: {e}")
        
        return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.enabled or not self.async_client:
            return {'enabled': False}
        
        try:
            info = await self.async_client.info()
            return {
                'enabled': True,
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', '0B'),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'total_commands_processed': info.get('total_commands_processed', 0)
            }
        except Exception as e:
            logger.warning(f"Redis stats error: {e}")
            return {'enabled': False, 'error': str(e)}
    
    async def health_check(self) -> bool:
        """Check Redis health."""
        if not self.enabled or not self.async_client:
            return False
        
        try:
            await self.async_client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False
    
    async def close(self):
        """Close Redis connections."""
        if self.async_client:
            await self.async_client.close()
        if self.client:
            self.client.close()


# Global Redis service instance
redis_service = RedisService()