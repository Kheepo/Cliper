"""Advanced caching system for the clip generation application.

Provides:
- Multi-level caching (memory, Redis, file-based)
- Cache invalidation strategies
- Cache warming and preloading
- Cache analytics and monitoring
- Distributed cache coordination
- Cache compression and serialization
"""

import asyncio
import json
import pickle
import gzip
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, asdict
from enum import Enum
from collections import OrderedDict
from functools import wraps

import redis.asyncio as redis
import aiofiles
from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger, PerformanceMetrics
from api.config.production import get_settings


logger = get_logger(__name__)
settings = get_settings()

T = TypeVar('T')


class CacheLevel(str, Enum):
    """Cache levels."""
    MEMORY = "memory"
    REDIS = "redis"
    FILE = "file"
    DATABASE = "database"


class CacheStrategy(str, Enum):
    """Cache strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In First Out
    RANDOM = "random"


class SerializationMethod(str, Enum):
    """Serialization methods."""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"
    COMPRESSED_JSON = "compressed_json"
    COMPRESSED_PICKLE = "compressed_pickle"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int
    ttl: Optional[int]  # seconds
    size: int  # bytes
    tags: List[str]
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.ttl is None:
            return False
        return (datetime.utcnow() - self.created_at).total_seconds() > self.ttl
    
    @property
    def age(self) -> float:
        """Get entry age in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    def touch(self):
        """Update access time and count."""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1


class CacheStats(BaseModel):
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    total_size: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """Calculate miss rate."""
        return 1.0 - self.hit_rate


class MemoryCache:
    """In-memory cache with LRU eviction."""
    
    def __init__(self, max_size: int = 1000, max_memory: int = 100 * 1024 * 1024):  # 100MB
        self.max_size = max_size
        self.max_memory = max_memory
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.stats = CacheStats()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                
                if entry.is_expired:
                    del self.cache[key]
                    self.stats.misses += 1
                    return None
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                entry.touch()
                self.stats.hits += 1
                
                return entry.value
            
            self.stats.misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, 
                 tags: Optional[List[str]] = None) -> bool:
        """Set value in cache."""
        async with self._lock:
            # Calculate size
            try:
                size = len(pickle.dumps(value))
            except:
                size = 1024  # Default size if can't calculate
            
            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                accessed_at=datetime.utcnow(),
                access_count=1,
                ttl=ttl,
                size=size,
                tags=tags or []
            )
            
            # Remove existing entry if present
            if key in self.cache:
                old_entry = self.cache[key]
                self.stats.total_size -= old_entry.size
                del self.cache[key]
            
            # Add new entry
            self.cache[key] = entry
            self.stats.total_size += size
            self.stats.sets += 1
            self.stats.entry_count = len(self.cache)
            
            # Evict if necessary
            await self._evict_if_needed()
            
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                self.stats.total_size -= entry.size
                del self.cache[key]
                self.stats.deletes += 1
                self.stats.entry_count = len(self.cache)
                return True
            return False
    
    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            self.stats.total_size = 0
            self.stats.entry_count = 0
    
    async def _evict_if_needed(self):
        """Evict entries if cache is full."""
        # Evict expired entries first
        expired_keys = [k for k, v in self.cache.items() if v.is_expired]
        for key in expired_keys:
            entry = self.cache[key]
            self.stats.total_size -= entry.size
            del self.cache[key]
            self.stats.evictions += 1
        
        # Evict by size limit
        while len(self.cache) > self.max_size:
            key, entry = self.cache.popitem(last=False)  # Remove least recently used
            self.stats.total_size -= entry.size
            self.stats.evictions += 1
        
        # Evict by memory limit
        while self.stats.total_size > self.max_memory and self.cache:
            key, entry = self.cache.popitem(last=False)
            self.stats.total_size -= entry.size
            self.stats.evictions += 1
        
        self.stats.entry_count = len(self.cache)


class RedisCache:
    """Redis-based distributed cache."""
    
    def __init__(self, redis_client: redis.Redis, prefix: str = "cache:"):
        self.redis = redis_client
        self.prefix = prefix
        self.stats = CacheStats()
    
    def _make_key(self, key: str) -> str:
        """Create Redis key with prefix."""
        return f"{self.prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        try:
            redis_key = self._make_key(key)
            data = await self.redis.get(redis_key)
            
            if data is None:
                self.stats.misses += 1
                return None
            
            # Deserialize
            value = pickle.loads(data)
            self.stats.hits += 1
            
            return value
            
        except Exception as e:
            logger.error(f"Redis cache get error: {e}")
            self.stats.misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, 
                 tags: Optional[List[str]] = None) -> bool:
        """Set value in Redis cache."""
        try:
            redis_key = self._make_key(key)
            
            # Serialize
            data = pickle.dumps(value)
            
            # Set with TTL
            if ttl:
                await self.redis.setex(redis_key, ttl, data)
            else:
                await self.redis.set(redis_key, data)
            
            # Store tags if provided
            if tags:
                for tag in tags:
                    tag_key = f"{self.prefix}tag:{tag}"
                    await self.redis.sadd(tag_key, key)
                    if ttl:
                        await self.redis.expire(tag_key, ttl)
            
            self.stats.sets += 1
            return True
            
        except Exception as e:
            logger.error(f"Redis cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache."""
        try:
            redis_key = self._make_key(key)
            result = await self.redis.delete(redis_key)
            
            if result > 0:
                self.stats.deletes += 1
                return True
            return False
            
        except Exception as e:
            logger.error(f"Redis cache delete error: {e}")
            return False
    
    async def clear(self):
        """Clear all cache entries."""
        try:
            pattern = f"{self.prefix}*"
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
                
        except Exception as e:
            logger.error(f"Redis cache clear error: {e}")
    
    async def invalidate_by_tag(self, tag: str):
        """Invalidate all cache entries with a specific tag."""
        try:
            tag_key = f"{self.prefix}tag:{tag}"
            keys = await self.redis.smembers(tag_key)
            
            if keys:
                # Delete all keys with this tag
                redis_keys = [self._make_key(key.decode()) for key in keys]
                await self.redis.delete(*redis_keys)
                
                # Delete the tag set
                await self.redis.delete(tag_key)
                
        except Exception as e:
            logger.error(f"Redis cache tag invalidation error: {e}")


class MultiLevelCache:
    """Multi-level cache with memory and Redis."""
    
    def __init__(self, redis_url: Optional[str] = None, 
                 memory_max_size: int = 1000,
                 memory_max_memory: int = 100 * 1024 * 1024):
        
        # Memory cache (L1)
        self.memory_cache = MemoryCache(memory_max_size, memory_max_memory)
        
        # Redis cache (L2)
        self.redis_cache = None
        if redis_url:
            try:
                redis_client = redis.from_url(redis_url)
                self.redis_cache = RedisCache(redis_client)
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
        
        self.stats = CacheStats()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from multi-level cache."""
        # Try memory cache first (L1)
        value = await self.memory_cache.get(key)
        if value is not None:
            self.stats.hits += 1
            return value
        
        # Try Redis cache (L2)
        if self.redis_cache:
            value = await self.redis_cache.get(key)
            if value is not None:
                # Populate memory cache
                await self.memory_cache.set(key, value)
                self.stats.hits += 1
                return value
        
        self.stats.misses += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, 
                 tags: Optional[List[str]] = None) -> bool:
        """Set value in multi-level cache."""
        success = True
        
        # Set in memory cache (L1)
        await self.memory_cache.set(key, value, ttl, tags)
        
        # Set in Redis cache (L2)
        if self.redis_cache:
            redis_success = await self.redis_cache.set(key, value, ttl, tags)
            success = success and redis_success
        
        if success:
            self.stats.sets += 1
        
        return success
    
    async def delete(self, key: str) -> bool:
        """Delete value from multi-level cache."""
        success = True
        
        # Delete from memory cache
        memory_success = await self.memory_cache.delete(key)
        
        # Delete from Redis cache
        redis_success = True
        if self.redis_cache:
            redis_success = await self.redis_cache.delete(key)
        
        success = memory_success or redis_success
        
        if success:
            self.stats.deletes += 1
        
        return success
    
    async def clear(self):
        """Clear all cache levels."""
        await self.memory_cache.clear()
        if self.redis_cache:
            await self.redis_cache.clear()
    
    async def invalidate_by_tag(self, tag: str):
        """Invalidate cache entries by tag."""
        # For memory cache, we need to iterate and check tags
        keys_to_delete = []
        for key, entry in self.memory_cache.cache.items():
            if tag in entry.tags:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            await self.memory_cache.delete(key)
        
        # For Redis cache
        if self.redis_cache:
            await self.redis_cache.invalidate_by_tag(tag)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined cache statistics."""
        combined_stats = {
            'total': asdict(self.stats),
            'memory': asdict(self.memory_cache.stats),
        }
        
        if self.redis_cache:
            combined_stats['redis'] = asdict(self.redis_cache.stats)
        
        return combined_stats


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments."""
    key_parts = []
    
    # Add positional arguments
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
    
    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}:{v}")
        else:
            key_parts.append(f"{k}:{hashlib.md5(str(v).encode()).hexdigest()[:8]}")
    
    return ":".join(key_parts)


def cached(ttl: Optional[int] = None, tags: Optional[List[str]] = None, 
          key_func: Optional[Callable] = None):
    """Decorator for caching function results."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Cache result
            await cache.set(key, result, ttl, tags)
            
            # Log performance
            logger.performance(PerformanceMetrics(
                operation=f"cache_miss:{func.__name__}",
                duration=execution_time,
                details={'cache_key': key}
            ))
            
            return result
        
        return wrapper
    return decorator


class CacheWarmer:
    """Cache warming utility."""
    
    def __init__(self, cache: MultiLevelCache):
        self.cache = cache
        self.warming_tasks: Dict[str, asyncio.Task] = {}
    
    async def warm_cache(self, key: str, value_func: Callable, 
                        ttl: Optional[int] = None, 
                        tags: Optional[List[str]] = None):
        """Warm cache with a specific key."""
        try:
            value = await value_func()
            await self.cache.set(key, value, ttl, tags)
            logger.info(f"Cache warmed for key: {key}")
        except Exception as e:
            logger.error(f"Cache warming failed for key {key}: {e}")
    
    async def warm_multiple(self, warming_specs: List[Dict[str, Any]]):
        """Warm multiple cache entries."""
        tasks = []
        
        for spec in warming_specs:
            task = asyncio.create_task(
                self.warm_cache(
                    spec['key'],
                    spec['value_func'],
                    spec.get('ttl'),
                    spec.get('tags')
                )
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def schedule_warming(self, key: str, value_func: Callable, 
                             interval: int, ttl: Optional[int] = None,
                             tags: Optional[List[str]] = None):
        """Schedule periodic cache warming."""
        async def warming_loop():
            while True:
                try:
                    await self.warm_cache(key, value_func, ttl, tags)
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Scheduled cache warming error for {key}: {e}")
                    await asyncio.sleep(interval)
        
        if key in self.warming_tasks:
            self.warming_tasks[key].cancel()
        
        self.warming_tasks[key] = asyncio.create_task(warming_loop())
    
    def stop_warming(self, key: str):
        """Stop scheduled warming for a key."""
        if key in self.warming_tasks:
            self.warming_tasks[key].cancel()
            del self.warming_tasks[key]
    
    def stop_all_warming(self):
        """Stop all scheduled warming tasks."""
        for task in self.warming_tasks.values():
            task.cancel()
        self.warming_tasks.clear()


# Global cache instance
cache = MultiLevelCache(
    redis_url=getattr(settings, 'redis_url', None),
    memory_max_size=getattr(settings, 'cache_memory_max_size', 1000),
    memory_max_memory=getattr(settings, 'cache_memory_max_memory', 100 * 1024 * 1024)
)

# Global cache warmer
cache_warmer = CacheWarmer(cache)


def get_cache() -> MultiLevelCache:
    """Get the global cache instance."""
    return cache


def get_cache_warmer() -> CacheWarmer:
    """Get the global cache warmer."""
    return cache_warmer