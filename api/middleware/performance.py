"""Performance optimization middleware and utilities."""

import time
import gzip
import json
import hashlib
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
import redis
import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os

logger = logging.getLogger(__name__)

class PerformanceCache:
    """High-performance caching system with Redis backend and memory fallback."""
    
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'errors': 0
        }
        self.max_memory_items = int(os.getenv('CACHE_MAX_SIZE', '1000'))
        self.default_ttl = int(os.getenv('CACHE_TTL', '3600'))
        
        # Initialize Redis connection
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
            self.redis_client.ping()
            logger.info("Redis cache initialized successfully")
        except Exception as e:
            logger.warning(f"Redis cache initialization failed: {e}. Using memory cache.")
            self.redis_client = None
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = f"{prefix}:{':'.join(map(str, args))}:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            # Try Redis first
            if self.redis_client:
                value = await asyncio.get_event_loop().run_in_executor(
                    None, self.redis_client.get, key
                )
                if value:
                    self.cache_stats['hits'] += 1
                    return json.loads(value)
            
            # Fallback to memory cache
            if key in self.memory_cache:
                item = self.memory_cache[key]
                if item['expires'] > datetime.utcnow():
                    self.cache_stats['hits'] += 1
                    return item['value']
                else:
                    del self.memory_cache[key]
            
            self.cache_stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.cache_stats['errors'] += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value, default=str)
            
            # Try Redis first
            if self.redis_client:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.redis_client.setex, key, ttl, serialized_value
                )
            else:
                # Fallback to memory cache
                if len(self.memory_cache) >= self.max_memory_items:
                    # Remove oldest item
                    oldest_key = min(self.memory_cache.keys(), 
                                   key=lambda k: self.memory_cache[k]['created'])
                    del self.memory_cache[oldest_key]
                
                self.memory_cache[key] = {
                    'value': value,
                    'created': datetime.utcnow(),
                    'expires': datetime.utcnow() + timedelta(seconds=ttl)
                }
            
            self.cache_stats['sets'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.cache_stats['errors'] += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            if self.redis_client:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.redis_client.delete, key
                )
            
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        # Check if Redis is actually working
        redis_working = False
        if self.redis_client:
            try:
                self.redis_client.ping()
                redis_working = True
            except Exception:
                redis_working = False
        
        return {
            **self.cache_stats,
            'hit_rate': round(hit_rate, 2),
            'memory_items': len(self.memory_cache),
            'redis_connected': redis_working
        }

# Global cache instance
cache = PerformanceCache()

def cached(prefix: str = "default", ttl: Optional[int] = None):
    """Decorator for caching function results."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache._generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator

class CompressionMiddleware:
    """Advanced compression middleware with multiple algorithms."""
    
    def __init__(self):
        self.min_size = int(os.getenv('COMPRESSION_MIN_SIZE', '1000'))
        self.compression_level = int(os.getenv('COMPRESSION_LEVEL', '6'))
        self.compressible_types = {
            'application/json',
            'application/javascript',
            'text/css',
            'text/html',
            'text/plain',
            'text/xml',
            'application/xml'
        }
    
    def should_compress(self, response: Response, content_length: int) -> bool:
        """Determine if response should be compressed."""
        if content_length < self.min_size:
            return False
        
        content_type = response.headers.get('content-type', '').split(';')[0]
        return content_type in self.compressible_types
    
    def compress_content(self, content: bytes) -> bytes:
        """Compress content using gzip."""
        return gzip.compress(content, compresslevel=self.compression_level)

class PerformanceMonitor:
    """Performance monitoring and metrics collection."""
    
    def __init__(self):
        self.metrics = {
            'request_count': 0,
            'total_response_time': 0,
            'avg_response_time': 0,
            'slow_requests': 0,
            'error_count': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self.slow_request_threshold = float(os.getenv('SLOW_REQUEST_THRESHOLD', '1.0'))
        self.request_history = []
        self.max_history = 1000
    
    def record_request(self, duration: float, status_code: int, endpoint: str):
        """Record request metrics."""
        self.metrics['request_count'] += 1
        self.metrics['total_response_time'] += duration
        self.metrics['avg_response_time'] = self.metrics['total_response_time'] / self.metrics['request_count']
        
        if duration > self.slow_request_threshold:
            self.metrics['slow_requests'] += 1
            logger.warning(f"Slow request detected: {endpoint} took {duration:.2f}s")
        
        if status_code >= 400:
            self.metrics['error_count'] += 1
        
        # Store request history
        request_data = {
            'timestamp': datetime.utcnow(),
            'duration': duration,
            'status_code': status_code,
            'endpoint': endpoint
        }
        
        self.request_history.append(request_data)
        if len(self.request_history) > self.max_history:
            self.request_history.pop(0)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        cache_stats = cache.get_stats()
        
        return {
            **self.metrics,
            'cache_stats': cache_stats,
            'recent_requests': len(self.request_history),
            'uptime': time.time() - getattr(self, 'start_time', time.time())
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        metrics = self.get_metrics()
        
        # Determine health status
        health_score = 100
        issues = []
        
        if metrics['avg_response_time'] > 2.0:
            health_score -= 20
            issues.append("High average response time")
        
        if metrics['error_count'] / max(metrics['request_count'], 1) > 0.05:
            health_score -= 30
            issues.append("High error rate")
        
        if metrics['cache_stats']['hit_rate'] < 50:
            health_score -= 10
            issues.append("Low cache hit rate")
        
        status = "healthy" if health_score >= 80 else "degraded" if health_score >= 60 else "unhealthy"
        
        return {
            'status': status,
            'health_score': health_score,
            'issues': issues,
            'metrics': metrics,
            'timestamp': datetime.utcnow().isoformat()
        }

# Global performance monitor
performance_monitor = PerformanceMonitor()
performance_monitor.start_time = time.time()

async def performance_middleware(request: Request, call_next):
    """Performance monitoring middleware."""
    start_time = time.time()
    
    # Add performance headers
    request.state.start_time = start_time
    
    try:
        response = await call_next(request)
        
        # Calculate response time
        duration = time.time() - start_time
        
        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        response.headers["X-Request-ID"] = getattr(request.state, 'request_id', 'unknown')
        
        # Record metrics
        endpoint = f"{request.method} {request.url.path}"
        performance_monitor.record_request(duration, response.status_code, endpoint)
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        endpoint = f"{request.method} {request.url.path}"
        performance_monitor.record_request(duration, 500, endpoint)
        raise

class DatabaseOptimizer:
    """Database query optimization utilities."""
    
    def __init__(self):
        self.query_cache = {}
        self.slow_query_threshold = float(os.getenv('SLOW_QUERY_THRESHOLD', '0.5'))
        self.query_stats = {}
    
    def optimize_firestore_query(self, collection: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize Firestore queries with indexing hints."""
        optimized_filters = {}
        
        # Sort filters for consistent indexing
        for key, value in sorted(filters.items()):
            if value is not None:
                optimized_filters[key] = value
        
        # Add query optimization hints
        query_key = f"{collection}:{':'.join(f'{k}={v}' for k, v in optimized_filters.items())}"
        
        if query_key in self.query_stats:
            self.query_stats[query_key]['count'] += 1
        else:
            self.query_stats[query_key] = {'count': 1, 'avg_time': 0}
        
        return optimized_filters
    
    def record_query_time(self, query_key: str, duration: float):
        """Record query execution time."""
        if query_key in self.query_stats:
            stats = self.query_stats[query_key]
            stats['avg_time'] = (stats['avg_time'] * (stats['count'] - 1) + duration) / stats['count']
            
            if duration > self.slow_query_threshold:
                logger.warning(f"Slow query detected: {query_key} took {duration:.2f}s")
    
    def get_query_stats(self) -> Dict[str, Any]:
        """Get database query statistics."""
        return {
            'total_queries': sum(stats['count'] for stats in self.query_stats.values()),
            'unique_queries': len(self.query_stats),
            'slow_queries': sum(1 for stats in self.query_stats.values() 
                              if stats['avg_time'] > self.slow_query_threshold),
            'query_details': self.query_stats
        }

# Global database optimizer
db_optimizer = DatabaseOptimizer()

# Thread pool for CPU-intensive tasks
thread_pool = ThreadPoolExecutor(max_workers=int(os.getenv('THREAD_POOL_SIZE', '4')))

async def run_in_thread(func: Callable, *args, **kwargs):
    """Run CPU-intensive function in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, func, *args, **kwargs)