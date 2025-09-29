"""Performance optimization utilities and configurations."""

import asyncio
import time
import functools
import logging
from typing import Dict, Any, Optional, Callable, List
from contextlib import asynccontextmanager
from dataclasses import dataclass
from collections import defaultdict, deque
import psutil
import redis
# SQLAlchemy imports removed for Supabase migration
# from sqlalchemy import event
# from sqlalchemy.engine import Engine
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uvloop
import orjson

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    request_count: int = 0
    total_response_time: float = 0.0
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    error_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    db_query_count: int = 0
    db_query_time: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0

class PerformanceOptimizer:
    """Main performance optimization manager."""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.request_times = deque(maxlen=1000)
        self.slow_queries = deque(maxlen=100)
        self.cache_stats = defaultdict(int)
        self.connection_pools = {}
        self.circuit_breakers = {}
        
    def setup_event_loop(self):
        """Setup optimized event loop."""
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            logger.info("Using uvloop for better performance")
        except ImportError:
            logger.warning("uvloop not available, using default event loop")
    
    def setup_json_serialization(self):
        """Setup fast JSON serialization."""
        import orjson
        
        def orjson_dumps(obj):
            return orjson.dumps(obj).decode()
        
        return orjson_dumps
    
    async def monitor_system_resources(self):
        """Monitor system resources continuously."""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.metrics.cpu_usage = cpu_percent
                
                # Memory usage
                memory = psutil.virtual_memory()
                self.metrics.memory_usage = memory.percent
                
                # Log warnings for high resource usage
                if cpu_percent > 80:
                    logger.warning(f"High CPU usage: {cpu_percent}%")
                
                if memory.percent > 85:
                    logger.warning(f"High memory usage: {memory.percent}%")
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring system resources: {e}")
                await asyncio.sleep(60)
    
    # Database optimization disabled for Supabase migration
    # def setup_database_optimization(self, engine: Engine):
    #     """Setup database query optimization."""
    #     
    #     @event.listens_for(engine, "before_cursor_execute")
    #     def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    #         context._query_start_time = time.time()
    #     
    #     @event.listens_for(engine, "after_cursor_execute")
    #     def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    #         total = time.time() - context._query_start_time
    #         self.metrics.db_query_count += 1
    #         self.metrics.db_query_time += total
    #         
    #         # Log slow queries
    #         if total > 1.0:  # Queries taking more than 1 second
    #             self.slow_queries.append({
    #                 'query': statement[:200],
    #                 'duration': total,
    #                 'timestamp': time.time()
    #             })
    #             logger.warning(f"Slow query detected: {total:.2f}s - {statement[:100]}...")
    
    def create_cache_decorator(self, redis_client: redis.Redis, ttl: int = 300):
        """Create a caching decorator for functions."""
        
        def cache_decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Create cache key
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
                
                try:
                    # Try to get from cache
                    cached_result = redis_client.get(cache_key)
                    if cached_result:
                        self.metrics.cache_hits += 1
                        self.cache_stats['hits'] += 1
                        return orjson.loads(cached_result)
                    
                    # Cache miss - execute function
                    self.metrics.cache_misses += 1
                    self.cache_stats['misses'] += 1
                    
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    # Store in cache
                    redis_client.setex(
                        cache_key,
                        ttl,
                        orjson.dumps(result)
                    )
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Cache error for {func.__name__}: {e}")
                    # Fallback to direct execution
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
            
            return wrapper
        return cache_decorator
    
    def create_circuit_breaker(self, failure_threshold: int = 5, timeout: int = 60):
        """Create a circuit breaker for external service calls."""
        
        class CircuitBreaker:
            def __init__(self):
                self.failure_count = 0
                self.last_failure_time = None
                self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
            
            def call(self, func: Callable):
                @functools.wraps(func)
                async def wrapper(*args, **kwargs):
                    if self.state == 'OPEN':
                        if time.time() - self.last_failure_time > timeout:
                            self.state = 'HALF_OPEN'
                        else:
                            raise Exception("Circuit breaker is OPEN")
                    
                    try:
                        if asyncio.iscoroutinefunction(func):
                            result = await func(*args, **kwargs)
                        else:
                            result = func(*args, **kwargs)
                        
                        # Success - reset failure count
                        if self.state == 'HALF_OPEN':
                            self.state = 'CLOSED'
                        self.failure_count = 0
                        return result
                        
                    except Exception as e:
                        self.failure_count += 1
                        self.last_failure_time = time.time()
                        
                        if self.failure_count >= failure_threshold:
                            self.state = 'OPEN'
                            logger.warning(f"Circuit breaker opened for {func.__name__}")
                        
                        raise e
                
                return wrapper
        
        return CircuitBreaker()
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        return {
            'metrics': {
                'request_count': self.metrics.request_count,
                'avg_response_time': self.metrics.avg_response_time,
                'min_response_time': self.metrics.min_response_time,
                'max_response_time': self.metrics.max_response_time,
                'error_count': self.metrics.error_count,
                'cache_hit_ratio': self.metrics.cache_hits / max(self.metrics.cache_hits + self.metrics.cache_misses, 1),
                'db_query_count': self.metrics.db_query_count,
                'avg_db_query_time': self.metrics.db_query_time / max(self.metrics.db_query_count, 1),
                'memory_usage': self.metrics.memory_usage,
                'cpu_usage': self.metrics.cpu_usage
            },
            'slow_queries': list(self.slow_queries),
            'cache_stats': dict(self.cache_stats),
            'recent_response_times': list(self.request_times)[-50:],  # Last 50 requests
            'system_info': {
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'disk_usage': psutil.disk_usage('/').percent
            }
        }

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for performance monitoring and optimization."""
    
    def __init__(self, app, optimizer: PerformanceOptimizer):
        super().__init__(app)
        self.optimizer = optimizer
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Update metrics
            self.optimizer.metrics.request_count += 1
            self.optimizer.metrics.total_response_time += response_time
            self.optimizer.metrics.avg_response_time = (
                self.optimizer.metrics.total_response_time / 
                self.optimizer.metrics.request_count
            )
            
            if response_time < self.optimizer.metrics.min_response_time:
                self.optimizer.metrics.min_response_time = response_time
            
            if response_time > self.optimizer.metrics.max_response_time:
                self.optimizer.metrics.max_response_time = response_time
            
            self.optimizer.request_times.append(response_time)
            
            # Add performance headers
            response.headers["X-Response-Time"] = str(response_time)
            response.headers["X-Request-ID"] = getattr(request.state, 'request_id', 'unknown')
            
            # Log slow requests
            if response_time > 2.0:
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} - {response_time:.2f}s"
                )
            
            return response
            
        except Exception as e:
            self.optimizer.metrics.error_count += 1
            logger.error(f"Request error: {e}")
            raise

class ConnectionPoolManager:
    """Manage database and Redis connection pools for optimal performance."""
    
    def __init__(self):
        self.pools = {}
    
    def create_redis_pool(self, redis_url: str, max_connections: int = 20):
        """Create optimized Redis connection pool."""
        return redis.ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
            health_check_interval=30
        )
    
    def create_database_pool(self, database_url: str):
        """Create optimized database connection pool."""
        from sqlalchemy import create_engine
        from sqlalchemy.pool import QueuePool
        
        return create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )

class AsyncTaskOptimizer:
    """Optimize async task execution and Celery performance."""
    
    def __init__(self):
        self.task_metrics = defaultdict(list)
    
    def optimize_celery_config(self) -> Dict[str, Any]:
        """Return optimized Celery configuration."""
        return {
            'broker_connection_retry_on_startup': True,
            'broker_connection_retry': True,
            'broker_connection_max_retries': 10,
            'broker_pool_limit': 10,
            'worker_prefetch_multiplier': 4,
            'task_acks_late': True,
            'worker_max_tasks_per_child': 1000,
            'task_compression': 'gzip',
            'result_compression': 'gzip',
            'task_serializer': 'json',
            'result_serializer': 'json',
            'accept_content': ['json'],
            'result_expires': 3600,
            'task_track_started': True,
            'task_time_limit': 300,
            'task_soft_time_limit': 240,
            'worker_disable_rate_limits': True,
            'broker_transport_options': {
                'priority_steps': list(range(10)),
                'sep': ':',
                'queue_order_strategy': 'priority'
            }
        }
    
    async def batch_process_tasks(self, tasks: List[Callable], batch_size: int = 10):
        """Process tasks in optimized batches."""
        results = []
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)
            
            # Small delay to prevent overwhelming the system
            await asyncio.sleep(0.01)
        
        return results

# Global performance optimizer instance
performance_optimizer = PerformanceOptimizer()
connection_pool_manager = ConnectionPoolManager()
async_task_optimizer = AsyncTaskOptimizer()

# Performance monitoring context manager
@asynccontextmanager
async def performance_monitor(operation_name: str):
    """Context manager for monitoring operation performance."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"Operation '{operation_name}' completed in {duration:.3f}s")
        
        if duration > 5.0:
            logger.warning(f"Slow operation detected: {operation_name} took {duration:.3f}s")

# Utility functions
def memory_efficient_json_loads(data: str):
    """Memory-efficient JSON loading using orjson."""
    try:
        return orjson.loads(data)
    except Exception:
        import json
        return json.loads(data)

def memory_efficient_json_dumps(obj: Any) -> str:
    """Memory-efficient JSON dumping using orjson."""
    try:
        return orjson.dumps(obj).decode()
    except Exception:
        import json
        return json.dumps(obj)

def setup_performance_optimization(app, redis_client, database_engine):
    """Setup all performance optimizations for the application."""
    
    # Setup event loop optimization
    performance_optimizer.setup_event_loop()
    
    # Setup database optimization
    performance_optimizer.setup_database_optimization(database_engine)
    
    # Add performance middleware
    app.add_middleware(PerformanceMiddleware, optimizer=performance_optimizer)
    
    # Start system monitoring
    asyncio.create_task(performance_optimizer.monitor_system_resources())
    
    logger.info("Performance optimization setup completed")
    
    return performance_optimizer