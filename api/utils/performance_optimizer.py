"""Performance optimization utilities for the clip generation system.

Provides:
- Parallel processing and task distribution
- Resource pooling and connection management
- Advanced queue management
- Memory optimization and garbage collection
- CPU and I/O optimization
- Performance profiling and monitoring
- Adaptive scaling and load balancing
"""

import asyncio
import threading
import multiprocessing
import time
import gc
import psutil
import resource
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from queue import Queue, PriorityQueue
from collections import deque, defaultdict
from functools import wraps, lru_cache
from contextlib import asynccontextmanager, contextmanager

import aiofiles
import aiohttp
from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger, PerformanceMetrics
from api.config.production import get_settings
from api.utils.redis_client import get_redis_client


logger = get_logger()
settings = get_settings()
redis_client = get_redis_client()

T = TypeVar('T')
R = TypeVar('R')


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


class ResourceType(str, Enum):
    """Resource types for pooling."""
    DATABASE = "database"
    HTTP_CLIENT = "http_client"
    FILE_HANDLE = "file_handle"
    MEMORY_BUFFER = "memory_buffer"
    THREAD = "thread"
    PROCESS = "process"


class OptimizationStrategy(str, Enum):
    """Optimization strategies."""
    CPU_BOUND = "cpu_bound"
    IO_BOUND = "io_bound"
    MEMORY_BOUND = "memory_bound"
    NETWORK_BOUND = "network_bound"
    BALANCED = "balanced"


@dataclass
class TaskMetrics:
    """Task execution metrics."""
    task_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    memory_usage: Optional[int] = None
    cpu_usage: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    
    def complete(self, success: bool = True, error: Optional[str] = None):
        """Mark task as completed."""
        self.end_time = datetime.utcnow()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.success = success
        self.error = error


@dataclass
class ResourcePoolConfig:
    """Resource pool configuration."""
    min_size: int = 1
    max_size: int = 10
    idle_timeout: int = 300  # seconds
    max_lifetime: int = 3600  # seconds
    health_check_interval: int = 60  # seconds
    retry_attempts: int = 3
    retry_delay: float = 1.0


class PriorityTask:
    """Priority task wrapper."""
    
    def __init__(self, priority: TaskPriority, task_id: str, func: Callable, 
                 args: tuple = (), kwargs: dict = None):
        self.priority = priority
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Any = None
        self.error: Optional[Exception] = None
    
    def __lt__(self, other):
        """Compare tasks by priority (higher priority first)."""
        if self.priority != other.priority:
            return self.priority.value > other.priority.value
        return self.created_at < other.created_at
    
    async def execute(self) -> Any:
        """Execute the task."""
        self.started_at = datetime.utcnow()
        
        try:
            if asyncio.iscoroutinefunction(self.func):
                self.result = await self.func(*self.args, **self.kwargs)
            else:
                self.result = self.func(*self.args, **self.kwargs)
            
            self.completed_at = datetime.utcnow()
            return self.result
            
        except Exception as e:
            self.error = e
            self.completed_at = datetime.utcnow()
            raise
    
    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def wait_time(self) -> Optional[float]:
        """Get task wait time in seconds."""
        if self.started_at:
            return (self.started_at - self.created_at).total_seconds()
        return None


class ResourcePool(Generic[T]):
    """Generic resource pool with health checking and lifecycle management."""
    
    def __init__(self, resource_factory: Callable[[], T], 
                 resource_destroyer: Callable[[T], None],
                 health_checker: Callable[[T], bool],
                 config: ResourcePoolConfig):
        
        self.resource_factory = resource_factory
        self.resource_destroyer = resource_destroyer
        self.health_checker = health_checker
        self.config = config
        
        self.pool: deque[Tuple[T, datetime]] = deque()
        self.active_resources: Dict[T, datetime] = {}
        self.lock = asyncio.Lock()
        self.stats = {
            'created': 0,
            'destroyed': 0,
            'borrowed': 0,
            'returned': 0,
            'health_check_failures': 0
        }
        
        # Start background tasks
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._cleanup_loop())
    
    async def acquire(self) -> T:
        """Acquire a resource from the pool."""
        async with self.lock:
            # Try to get from pool
            while self.pool:
                resource, created_at = self.pool.popleft()
                
                # Check if resource is still healthy
                if self.health_checker(resource):
                    self.active_resources[resource] = datetime.utcnow()
                    self.stats['borrowed'] += 1
                    return resource
                else:
                    # Resource is unhealthy, destroy it
                    self.resource_destroyer(resource)
                    self.stats['destroyed'] += 1
                    self.stats['health_check_failures'] += 1
            
            # No healthy resources available, create new one
            if len(self.active_resources) < self.config.max_size:
                resource = self.resource_factory()
                self.active_resources[resource] = datetime.utcnow()
                self.stats['created'] += 1
                self.stats['borrowed'] += 1
                return resource
            
            # Pool is at max capacity, wait for a resource to be returned
            raise RuntimeError("Resource pool exhausted")
    
    async def release(self, resource: T):
        """Release a resource back to the pool."""
        async with self.lock:
            if resource in self.active_resources:
                del self.active_resources[resource]
                
                # Check if resource is still healthy
                if self.health_checker(resource):
                    self.pool.append((resource, datetime.utcnow()))
                    self.stats['returned'] += 1
                else:
                    # Resource is unhealthy, destroy it
                    self.resource_destroyer(resource)
                    self.stats['destroyed'] += 1
                    self.stats['health_check_failures'] += 1
    
    @asynccontextmanager
    async def get_resource(self):
        """Context manager for resource acquisition and release."""
        resource = await self.acquire()
        try:
            yield resource
        finally:
            await self.release(resource)
    
    async def _health_check_loop(self):
        """Background health checking."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                async with self.lock:
                    # Check pooled resources
                    healthy_resources = []
                    
                    for resource, created_at in self.pool:
                        if self.health_checker(resource):
                            healthy_resources.append((resource, created_at))
                        else:
                            self.resource_destroyer(resource)
                            self.stats['destroyed'] += 1
                            self.stats['health_check_failures'] += 1
                    
                    self.pool = deque(healthy_resources)
                    
                    # Ensure minimum pool size
                    while len(self.pool) < self.config.min_size:
                        try:
                            resource = self.resource_factory()
                            self.pool.append((resource, datetime.utcnow()))
                            self.stats['created'] += 1
                        except Exception as e:
                            logger.error(f"Failed to create resource for pool: {e}")
                            break
                
            except Exception as e:
                logger.error(f"Error in resource pool health check: {e}")
    
    async def _cleanup_loop(self):
        """Background cleanup of old resources."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow()
                
                async with self.lock:
                    # Clean up idle resources
                    fresh_resources = []
                    
                    for resource, created_at in self.pool:
                        age = (current_time - created_at).total_seconds()
                        
                        if age < self.config.idle_timeout and age < self.config.max_lifetime:
                            fresh_resources.append((resource, created_at))
                        else:
                            self.resource_destroyer(resource)
                            self.stats['destroyed'] += 1
                    
                    self.pool = deque(fresh_resources)
                    
                    # Clean up active resources that exceeded max lifetime
                    expired_resources = []
                    
                    for resource, acquired_at in self.active_resources.items():
                        age = (current_time - acquired_at).total_seconds()
                        
                        if age > self.config.max_lifetime:
                            expired_resources.append(resource)
                    
                    for resource in expired_resources:
                        logger.warning(f"Force destroying expired active resource")
                        del self.active_resources[resource]
                        self.resource_destroyer(resource)
                        self.stats['destroyed'] += 1
                
            except Exception as e:
                logger.error(f"Error in resource pool cleanup: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            **self.stats,
            'pool_size': len(self.pool),
            'active_count': len(self.active_resources),
            'total_resources': len(self.pool) + len(self.active_resources)
        }


class AdvancedTaskQueue:
    """Advanced task queue with priority, batching, and load balancing."""
    
    def __init__(self, max_workers: int = None, strategy: OptimizationStrategy = OptimizationStrategy.BALANCED):
        self.max_workers = max_workers or min(32, (multiprocessing.cpu_count() or 1) + 4)
        self.strategy = strategy
        
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.result_futures: Dict[str, asyncio.Future] = {}
        self.workers: List[asyncio.Task] = []
        self.running = False
        
        self.metrics = {
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_execution_time': 0.0,
            'average_wait_time': 0.0,
            'queue_size': 0
        }
        
        self.task_history: deque[TaskMetrics] = deque(maxlen=1000)
        
        # Thread and process pools for different strategies
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=min(self.max_workers, multiprocessing.cpu_count()))
    
    async def start(self):
        """Start the task queue workers."""
        if self.running:
            return
        
        self.running = True
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info(f"Started task queue with {self.max_workers} workers")
    
    async def stop(self):
        """Stop the task queue workers."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        # Shutdown thread and process pools
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)
        
        logger.info("Task queue stopped")
    
    async def submit_task(self, func: Callable, *args, priority: TaskPriority = TaskPriority.NORMAL, 
                         task_id: Optional[str] = None, **kwargs) -> str:
        """Submit a task to the queue."""
        if task_id is None:
            task_id = f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{id(func)}"
        
        task = PriorityTask(priority, task_id, func, args, kwargs)
        future = asyncio.Future()
        
        self.result_futures[task_id] = future
        await self.task_queue.put(task)
        
        self.metrics['tasks_submitted'] += 1
        self.metrics['queue_size'] = self.task_queue.qsize()
        
        logger.debug(f"Task submitted: {task_id} (priority: {priority.name})")
        
        return task_id
    
    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """Get task result."""
        if task_id not in self.result_futures:
            raise ValueError(f"Task not found: {task_id}")
        
        future = self.result_futures[task_id]
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        finally:
            # Clean up
            if task_id in self.result_futures:
                del self.result_futures[task_id]
    
    async def submit_and_wait(self, func: Callable, *args, priority: TaskPriority = TaskPriority.NORMAL,
                             timeout: Optional[float] = None, **kwargs) -> Any:
        """Submit task and wait for result."""
        task_id = await self.submit_task(func, *args, priority=priority, **kwargs)
        return await self.get_result(task_id, timeout=timeout)
    
    async def submit_batch(self, tasks: List[Tuple[Callable, tuple, dict]], 
                          priority: TaskPriority = TaskPriority.NORMAL) -> List[str]:
        """Submit multiple tasks as a batch."""
        task_ids = []
        
        for func, args, kwargs in tasks:
            task_id = await self.submit_task(func, *args, priority=priority, **kwargs)
            task_ids.append(task_id)
        
        return task_ids
    
    async def wait_for_batch(self, task_ids: List[str], timeout: Optional[float] = None) -> List[Any]:
        """Wait for batch of tasks to complete."""
        results = []
        
        for task_id in task_ids:
            result = await self.get_result(task_id, timeout=timeout)
            results.append(result)
        
        return results
    
    async def _worker(self, worker_name: str):
        """Worker coroutine to process tasks."""
        logger.info(f"Worker {worker_name} started")
        
        while self.running:
            try:
                # Get task from queue
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                # Create task metrics
                task_metrics = TaskMetrics(
                    task_id=task.task_id,
                    start_time=datetime.utcnow()
                )
                
                try:
                    # Execute task based on strategy
                    result = await self._execute_task(task)
                    
                    # Mark task as successful
                    task_metrics.complete(success=True)
                    
                    # Set result
                    if task.task_id in self.result_futures:
                        self.result_futures[task.task_id].set_result(result)
                    
                    self.metrics['tasks_completed'] += 1
                    
                except Exception as e:
                    # Mark task as failed
                    task_metrics.complete(success=False, error=str(e))
                    
                    # Set exception
                    if task.task_id in self.result_futures:
                        self.result_futures[task.task_id].set_exception(e)
                    
                    self.metrics['tasks_failed'] += 1
                    logger.error(f"Task {task.task_id} failed: {e}")
                
                finally:
                    # Update metrics
                    if task_metrics.duration:
                        self.metrics['total_execution_time'] += task_metrics.duration
                    
                    self.task_history.append(task_metrics)
                    self.metrics['queue_size'] = self.task_queue.qsize()
                    
                    # Mark task as done
                    self.task_queue.task_done()
                
            except asyncio.TimeoutError:
                # No tasks available, continue
                continue
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _execute_task(self, task: PriorityTask) -> Any:
        """Execute task based on optimization strategy."""
        if self.strategy == OptimizationStrategy.CPU_BOUND:
            # Use process pool for CPU-bound tasks
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self.process_pool, task.func, *task.args)
        
        elif self.strategy == OptimizationStrategy.IO_BOUND:
            # Use thread pool for I/O-bound tasks
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self.thread_pool, task.func, *task.args)
        
        else:
            # Execute directly for async tasks or balanced strategy
            return await task.execute()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get queue metrics."""
        total_tasks = self.metrics['tasks_completed'] + self.metrics['tasks_failed']
        
        return {
            **self.metrics,
            'success_rate': self.metrics['tasks_completed'] / total_tasks if total_tasks > 0 else 0,
            'failure_rate': self.metrics['tasks_failed'] / total_tasks if total_tasks > 0 else 0,
            'average_execution_time': self.metrics['total_execution_time'] / self.metrics['tasks_completed'] if self.metrics['tasks_completed'] > 0 else 0,
            'workers_count': len(self.workers),
            'active_workers': sum(1 for w in self.workers if not w.done())
        }


class MemoryOptimizer:
    """Memory optimization utilities."""
    
    def __init__(self):
        self.memory_threshold = 0.8  # 80% memory usage threshold
        self.gc_interval = 60  # seconds
        self.monitoring = False
        
        # Start memory monitoring
        asyncio.create_task(self._memory_monitor())
    
    async def _memory_monitor(self):
        """Monitor memory usage and trigger cleanup."""
        self.monitoring = True
        
        while self.monitoring:
            try:
                await asyncio.sleep(self.gc_interval)
                
                # Get memory usage
                memory_info = psutil.virtual_memory()
                memory_usage = memory_info.percent / 100.0
                
                if memory_usage > self.memory_threshold:
                    logger.warning(f"High memory usage detected: {memory_usage:.1%}")
                    
                    # Force garbage collection
                    collected = gc.collect()
                    logger.info(f"Garbage collection freed {collected} objects")
                    
                    # Log memory usage after cleanup
                    new_memory_info = psutil.virtual_memory()
                    new_memory_usage = new_memory_info.percent / 100.0
                    logger.info(f"Memory usage after cleanup: {new_memory_usage:.1%}")
                
            except Exception as e:
                logger.error(f"Error in memory monitor: {e}")
    
    @contextmanager
    def memory_limit(self, max_memory_mb: int):
        """Context manager to limit memory usage."""
        # Set memory limit (Unix only)
        if hasattr(resource, 'RLIMIT_AS'):
            old_limit = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (max_memory_mb * 1024 * 1024, old_limit[1]))
        
        try:
            yield
        finally:
            # Restore old limit
            if hasattr(resource, 'RLIMIT_AS'):
                resource.setrlimit(resource.RLIMIT_AS, old_limit)
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        memory_info = psutil.virtual_memory()
        
        return {
            'total': memory_info.total,
            'available': memory_info.available,
            'used': memory_info.used,
            'percentage': memory_info.percent,
            'free': memory_info.free
        }
    
    def stop_monitoring(self):
        """Stop memory monitoring."""
        self.monitoring = False


class PerformanceProfiler:
    """Performance profiling and monitoring."""
    
    def __init__(self):
        self.profiles: Dict[str, List[PerformanceMetrics]] = defaultdict(list)
        self.active_profiles: Dict[str, datetime] = {}
    
    @contextmanager
    def profile(self, operation_name: str):
        """Profile an operation."""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss
        
        self.active_profiles[operation_name] = datetime.utcnow()
        
        try:
            yield
        finally:
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss
            
            duration = end_time - start_time
            memory_delta = end_memory - start_memory
            
            metrics = PerformanceMetrics(
                operation=operation_name,
                duration=duration,
                memory_usage=memory_delta,
                timestamp=datetime.utcnow()
            )
            
            self.profiles[operation_name].append(metrics)
            
            if operation_name in self.active_profiles:
                del self.active_profiles[operation_name]
            
            logger.performance(metrics)
    
    def get_profile_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get profiling statistics for an operation."""
        if operation_name not in self.profiles:
            return {}
        
        metrics_list = self.profiles[operation_name]
        durations = [m.duration for m in metrics_list]
        memory_usage = [m.memory_usage for m in metrics_list if m.memory_usage]
        
        return {
            'count': len(metrics_list),
            'total_duration': sum(durations),
            'average_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'average_memory': sum(memory_usage) / len(memory_usage) if memory_usage else 0,
            'max_memory': max(memory_usage) if memory_usage else 0
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get all profiling statistics."""
        return {op: self.get_profile_stats(op) for op in self.profiles.keys()}


# Performance decorators
def optimize_for_cpu(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to optimize function for CPU-bound operations."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Set thread affinity if available
        if hasattr(os, 'sched_setaffinity'):
            os.sched_setaffinity(0, range(multiprocessing.cpu_count()))
        
        return func(*args, **kwargs)
    
    return wrapper


def optimize_for_io(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to optimize function for I/O-bound operations."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Use asyncio for I/O operations
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)
    
    return wrapper


def batch_process(batch_size: int = 100, max_wait: float = 1.0):
    """Decorator to batch process function calls."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        batch_queue = []
        last_process_time = time.time()
        lock = threading.Lock()
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal batch_queue, last_process_time
            
            with lock:
                batch_queue.append((args, kwargs))
                current_time = time.time()
                
                # Process batch if size reached or max wait time exceeded
                if len(batch_queue) >= batch_size or (current_time - last_process_time) >= max_wait:
                    batch_to_process = batch_queue.copy()
                    batch_queue.clear()
                    last_process_time = current_time
                    
                    # Process batch
                    results = []
                    for batch_args, batch_kwargs in batch_to_process:
                        if asyncio.iscoroutinefunction(func):
                            result = await func(*batch_args, **batch_kwargs)
                        else:
                            result = func(*batch_args, **batch_kwargs)
                        results.append(result)
                    
                    return results[-1]  # Return result for current call
                
                # If batch not ready, wait a bit and try again
                await asyncio.sleep(0.01)
                return await wrapper(*args, **kwargs)
        
        return wrapper
    return decorator


# Global instances
task_queue = AdvancedTaskQueue()
memory_optimizer = MemoryOptimizer()
performance_profiler = PerformanceProfiler()


def get_task_queue() -> AdvancedTaskQueue:
    """Get the global task queue."""
    return task_queue


def get_memory_optimizer() -> MemoryOptimizer:
    """Get the global memory optimizer."""
    return memory_optimizer


def get_performance_profiler() -> PerformanceProfiler:
    """Get the global performance profiler."""
    return performance_profiler


# Utility functions
async def parallel_map(func: Callable[[T], R], items: List[T], 
                      max_concurrency: int = 10) -> List[R]:
    """Apply function to items in parallel with concurrency limit."""
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def bounded_func(item: T) -> R:
        async with semaphore:
            if asyncio.iscoroutinefunction(func):
                return await func(item)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, func, item)
    
    return await asyncio.gather(*[bounded_func(item) for item in items])


async def adaptive_retry(func: Callable[..., T], *args, max_retries: int = 3, 
                        base_delay: float = 1.0, backoff_factor: float = 2.0, 
                        **kwargs) -> T:
    """Retry function with adaptive backoff."""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                delay = base_delay * (backoff_factor ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed")
    
    raise last_exception