"""Advanced queue management system for background task processing.

Provides:
- Multiple queue types (priority, delayed, batch)
- Job scheduling and retry mechanisms
- Worker pool management
- Queue monitoring and analytics
- Dead letter queue handling
- Distributed job coordination
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Union, Type
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
from functools import wraps
import heapq
import pickle

import redis.asyncio as redis
from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger, PerformanceMetrics
from api.config.production import get_settings


logger = get_logger(__name__)
settings = get_settings()


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    DEAD = "dead"


class QueueType(str, Enum):
    """Queue type enumeration."""
    FIFO = "fifo"  # First In First Out
    PRIORITY = "priority"  # Priority-based
    DELAYED = "delayed"  # Delayed execution
    BATCH = "batch"  # Batch processing
    BROADCAST = "broadcast"  # Broadcast to all workers


class RetryStrategy(str, Enum):
    """Retry strategy enumeration."""
    FIXED = "fixed"  # Fixed delay
    EXPONENTIAL = "exponential"  # Exponential backoff
    LINEAR = "linear"  # Linear backoff
    CUSTOM = "custom"  # Custom function


@dataclass
class JobConfig:
    """Job configuration."""
    max_retries: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_delay: float = 1.0  # Base delay in seconds
    timeout: Optional[float] = None  # Job timeout in seconds
    priority: int = 0  # Higher number = higher priority
    delay: Optional[float] = None  # Delay before execution
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    """Job representation."""
    id: str
    queue_name: str
    func_name: str
    args: tuple
    kwargs: dict
    config: JobConfig
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    worker_id: Optional[str] = None
    
    @property
    def execution_time(self) -> Optional[float]:
        """Get job execution time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def total_time(self) -> float:
        """Get total time since job creation."""
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.created_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            'id': self.id,
            'queue_name': self.queue_name,
            'func_name': self.func_name,
            'args': self.args,
            'kwargs': self.kwargs,
            'config': asdict(self.config),
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result,
            'error': self.error,
            'retry_count': self.retry_count,
            'worker_id': self.worker_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create job from dictionary."""
        config_data = data.get('config', {})
        config = JobConfig(**config_data)
        
        return cls(
            id=data['id'],
            queue_name=data['queue_name'],
            func_name=data['func_name'],
            args=tuple(data['args']),
            kwargs=data['kwargs'],
            config=config,
            status=JobStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            result=data.get('result'),
            error=data.get('error'),
            retry_count=data.get('retry_count', 0),
            worker_id=data.get('worker_id')
        )


class QueueStats(BaseModel):
    """Queue statistics."""
    pending_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    dead_jobs: int = 0
    total_jobs: int = 0
    avg_execution_time: float = 0.0
    avg_wait_time: float = 0.0
    throughput: float = 0.0  # jobs per second
    error_rate: float = 0.0


class BaseQueue:
    """Base queue implementation."""
    
    def __init__(self, name: str, queue_type: QueueType = QueueType.FIFO):
        self.name = name
        self.queue_type = queue_type
        self.jobs: Dict[str, Job] = {}
        self.pending_jobs: List[Job] = []
        self.running_jobs: Dict[str, Job] = {}
        self.completed_jobs: List[Job] = []
        self.failed_jobs: List[Job] = []
        self.dead_jobs: List[Job] = []
        self.stats = QueueStats()
        self._lock = asyncio.Lock()
    
    async def enqueue(self, job: Job) -> str:
        """Add job to queue."""
        async with self._lock:
            self.jobs[job.id] = job
            
            if job.config.delay and job.config.delay > 0:
                # Schedule delayed job
                asyncio.create_task(self._schedule_delayed_job(job))
            else:
                await self._add_to_pending(job)
            
            self.stats.total_jobs += 1
            self.stats.pending_jobs += 1
            
            logger.info(f"Job {job.id} enqueued to {self.name}")
            return job.id
    
    async def dequeue(self) -> Optional[Job]:
        """Get next job from queue."""
        async with self._lock:
            if not self.pending_jobs:
                return None
            
            job = await self._get_next_job()
            if job:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.utcnow()
                self.running_jobs[job.id] = job
                
                self.stats.pending_jobs -= 1
                self.stats.running_jobs += 1
                
                logger.info(f"Job {job.id} dequeued from {self.name}")
            
            return job
    
    async def complete_job(self, job_id: str, result: Any = None, error: Optional[str] = None):
        """Mark job as completed or failed."""
        async with self._lock:
            if job_id not in self.running_jobs:
                return
            
            job = self.running_jobs.pop(job_id)
            job.completed_at = datetime.utcnow()
            
            if error:
                job.status = JobStatus.FAILED
                job.error = error
                
                # Check if job should be retried
                if job.retry_count < job.config.max_retries:
                    await self._schedule_retry(job)
                else:
                    # Move to dead letter queue
                    job.status = JobStatus.DEAD
                    self.dead_jobs.append(job)
                    self.stats.dead_jobs += 1
                    logger.warning(f"Job {job_id} moved to dead letter queue")
                
                self.failed_jobs.append(job)
                self.stats.failed_jobs += 1
            else:
                job.status = JobStatus.COMPLETED
                job.result = result
                self.completed_jobs.append(job)
                self.stats.completed_jobs += 1
            
            self.stats.running_jobs -= 1
            await self._update_stats(job)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        async with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            
            if job.status in [JobStatus.PENDING, JobStatus.RETRYING]:
                job.status = JobStatus.CANCELLED
                
                # Remove from pending
                self.pending_jobs = [j for j in self.pending_jobs if j.id != job_id]
                self.stats.pending_jobs -= 1
                
                logger.info(f"Job {job_id} cancelled")
                return True
            
            return False
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    async def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        return self.stats
    
    async def _add_to_pending(self, job: Job):
        """Add job to pending list based on queue type."""
        if self.queue_type == QueueType.PRIORITY:
            # Use negative priority for max heap behavior
            heapq.heappush(self.pending_jobs, (-job.config.priority, job.created_at, job))
        else:
            self.pending_jobs.append(job)
    
    async def _get_next_job(self) -> Optional[Job]:
        """Get next job based on queue type."""
        if not self.pending_jobs:
            return None
        
        if self.queue_type == QueueType.PRIORITY:
            _, _, job = heapq.heappop(self.pending_jobs)
            return job
        else:
            return self.pending_jobs.pop(0)
    
    async def _schedule_delayed_job(self, job: Job):
        """Schedule a delayed job."""
        await asyncio.sleep(job.config.delay)
        async with self._lock:
            if job.status == JobStatus.PENDING:
                await self._add_to_pending(job)
    
    async def _schedule_retry(self, job: Job):
        """Schedule job retry."""
        job.retry_count += 1
        job.status = JobStatus.RETRYING
        
        # Calculate retry delay
        delay = self._calculate_retry_delay(job)
        
        logger.info(f"Scheduling retry for job {job.id} in {delay} seconds")
        
        async def retry_job():
            await asyncio.sleep(delay)
            async with self._lock:
                if job.status == JobStatus.RETRYING:
                    job.status = JobStatus.PENDING
                    await self._add_to_pending(job)
                    self.stats.pending_jobs += 1
        
        asyncio.create_task(retry_job())
    
    def _calculate_retry_delay(self, job: Job) -> float:
        """Calculate retry delay based on strategy."""
        base_delay = job.config.retry_delay
        retry_count = job.retry_count
        
        if job.config.retry_strategy == RetryStrategy.FIXED:
            return base_delay
        elif job.config.retry_strategy == RetryStrategy.EXPONENTIAL:
            return base_delay * (2 ** (retry_count - 1))
        elif job.config.retry_strategy == RetryStrategy.LINEAR:
            return base_delay * retry_count
        else:
            return base_delay
    
    async def _update_stats(self, job: Job):
        """Update queue statistics."""
        # Update execution time average
        if job.execution_time:
            total_completed = self.stats.completed_jobs + self.stats.failed_jobs
            if total_completed > 1:
                self.stats.avg_execution_time = (
                    (self.stats.avg_execution_time * (total_completed - 1) + job.execution_time) / total_completed
                )
            else:
                self.stats.avg_execution_time = job.execution_time
        
        # Update error rate
        total_finished = self.stats.completed_jobs + self.stats.failed_jobs
        if total_finished > 0:
            self.stats.error_rate = self.stats.failed_jobs / total_finished


class RedisQueue(BaseQueue):
    """Redis-based distributed queue."""
    
    def __init__(self, name: str, redis_client: redis.Redis, 
                 queue_type: QueueType = QueueType.FIFO):
        super().__init__(name, queue_type)
        self.redis = redis_client
        self.key_prefix = f"queue:{name}"
    
    async def enqueue(self, job: Job) -> str:
        """Add job to Redis queue."""
        try:
            # Serialize job
            job_data = pickle.dumps(job.to_dict())
            
            # Add to Redis
            if self.queue_type == QueueType.PRIORITY:
                await self.redis.zadd(f"{self.key_prefix}:pending", {job.id: -job.config.priority})
            else:
                await self.redis.lpush(f"{self.key_prefix}:pending", job.id)
            
            # Store job data
            await self.redis.hset(f"{self.key_prefix}:jobs", job.id, job_data)
            
            # Update stats
            await self.redis.hincrby(f"{self.key_prefix}:stats", "total_jobs", 1)
            await self.redis.hincrby(f"{self.key_prefix}:stats", "pending_jobs", 1)
            
            logger.info(f"Job {job.id} enqueued to Redis queue {self.name}")
            return job.id
            
        except Exception as e:
            logger.error(f"Failed to enqueue job to Redis: {e}")
            raise
    
    async def dequeue(self) -> Optional[Job]:
        """Get next job from Redis queue."""
        try:
            # Get job ID
            if self.queue_type == QueueType.PRIORITY:
                result = await self.redis.zpopmax(f"{self.key_prefix}:pending")
                if not result:
                    return None
                job_id = result[0][0].decode()
            else:
                job_id = await self.redis.rpop(f"{self.key_prefix}:pending")
                if not job_id:
                    return None
                job_id = job_id.decode()
            
            # Get job data
            job_data = await self.redis.hget(f"{self.key_prefix}:jobs", job_id)
            if not job_data:
                return None
            
            # Deserialize job
            job_dict = pickle.loads(job_data)
            job = Job.from_dict(job_dict)
            
            # Update job status
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            
            # Move to running
            await self.redis.hset(f"{self.key_prefix}:running", job.id, pickle.dumps(job.to_dict()))
            
            # Update stats
            await self.redis.hincrby(f"{self.key_prefix}:stats", "pending_jobs", -1)
            await self.redis.hincrby(f"{self.key_prefix}:stats", "running_jobs", 1)
            
            logger.info(f"Job {job.id} dequeued from Redis queue {self.name}")
            return job
            
        except Exception as e:
            logger.error(f"Failed to dequeue job from Redis: {e}")
            return None
    
    async def complete_job(self, job_id: str, result: Any = None, error: Optional[str] = None):
        """Mark job as completed or failed in Redis."""
        try:
            # Get job from running
            job_data = await self.redis.hget(f"{self.key_prefix}:running", job_id)
            if not job_data:
                return
            
            job_dict = pickle.loads(job_data)
            job = Job.from_dict(job_dict)
            job.completed_at = datetime.utcnow()
            
            if error:
                job.status = JobStatus.FAILED
                job.error = error
                
                # Check retry
                if job.retry_count < job.config.max_retries:
                    await self._schedule_redis_retry(job)
                else:
                    job.status = JobStatus.DEAD
                    await self.redis.hset(f"{self.key_prefix}:dead", job.id, pickle.dumps(job.to_dict()))
                    await self.redis.hincrby(f"{self.key_prefix}:stats", "dead_jobs", 1)
                
                await self.redis.hset(f"{self.key_prefix}:failed", job.id, pickle.dumps(job.to_dict()))
                await self.redis.hincrby(f"{self.key_prefix}:stats", "failed_jobs", 1)
            else:
                job.status = JobStatus.COMPLETED
                job.result = result
                await self.redis.hset(f"{self.key_prefix}:completed", job.id, pickle.dumps(job.to_dict()))
                await self.redis.hincrby(f"{self.key_prefix}:stats", "completed_jobs", 1)
            
            # Remove from running
            await self.redis.hdel(f"{self.key_prefix}:running", job.id)
            await self.redis.hincrby(f"{self.key_prefix}:stats", "running_jobs", -1)
            
            # Update job data
            await self.redis.hset(f"{self.key_prefix}:jobs", job.id, pickle.dumps(job.to_dict()))
            
        except Exception as e:
            logger.error(f"Failed to complete job in Redis: {e}")
    
    async def _schedule_redis_retry(self, job: Job):
        """Schedule retry for Redis job."""
        job.retry_count += 1
        job.status = JobStatus.RETRYING
        
        delay = self._calculate_retry_delay(job)
        retry_time = time.time() + delay
        
        # Add to delayed queue
        await self.redis.zadd(f"{self.key_prefix}:delayed", {job.id: retry_time})
        await self.redis.hset(f"{self.key_prefix}:jobs", job.id, pickle.dumps(job.to_dict()))


class Worker:
    """Queue worker for processing jobs."""
    
    def __init__(self, worker_id: str, queues: List[BaseQueue], 
                 concurrency: int = 1):
        self.worker_id = worker_id
        self.queues = queues
        self.concurrency = concurrency
        self.running = False
        self.tasks: List[asyncio.Task] = []
        self.job_functions: Dict[str, Callable] = {}
        self.stats = {
            'jobs_processed': 0,
            'jobs_failed': 0,
            'total_execution_time': 0.0,
            'started_at': None
        }
    
    def register_function(self, name: str, func: Callable):
        """Register a job function."""
        self.job_functions[name] = func
    
    async def start(self):
        """Start the worker."""
        if self.running:
            return
        
        self.running = True
        self.stats['started_at'] = datetime.utcnow()
        
        # Start worker tasks
        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker_loop(f"{self.worker_id}-{i}"))
            self.tasks.append(task)
        
        logger.info(f"Worker {self.worker_id} started with {self.concurrency} concurrent tasks")
    
    async def stop(self):
        """Stop the worker."""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        
        logger.info(f"Worker {self.worker_id} stopped")
    
    async def _worker_loop(self, task_id: str):
        """Main worker loop."""
        logger.info(f"Worker task {task_id} started")
        
        while self.running:
            try:
                # Try to get job from any queue
                job = None
                for queue in self.queues:
                    job = await queue.dequeue()
                    if job:
                        break
                
                if not job:
                    await asyncio.sleep(1)  # No jobs available
                    continue
                
                # Process job
                await self._process_job(job, task_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker task {task_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker task {task_id} stopped")
    
    async def _process_job(self, job: Job, task_id: str):
        """Process a single job."""
        start_time = time.time()
        job.worker_id = task_id
        
        try:
            logger.info(f"Processing job {job.id} with function {job.func_name}")
            
            # Get job function
            if job.func_name not in self.job_functions:
                raise ValueError(f"Unknown job function: {job.func_name}")
            
            func = self.job_functions[job.func_name]
            
            # Execute with timeout
            if job.config.timeout:
                result = await asyncio.wait_for(
                    func(*job.args, **job.kwargs),
                    timeout=job.config.timeout
                )
            else:
                result = await func(*job.args, **job.kwargs)
            
            # Mark as completed
            for queue in self.queues:
                if queue.name == job.queue_name:
                    await queue.complete_job(job.id, result=result)
                    break
            
            execution_time = time.time() - start_time
            self.stats['jobs_processed'] += 1
            self.stats['total_execution_time'] += execution_time
            
            logger.info(f"Job {job.id} completed in {execution_time:.2f}s")
            
        except asyncio.TimeoutError:
            error = f"Job timeout after {job.config.timeout}s"
            logger.error(f"Job {job.id} timed out")
            await self._handle_job_error(job, error)
            
        except Exception as e:
            error = str(e)
            logger.error(f"Job {job.id} failed: {error}")
            await self._handle_job_error(job, error)
    
    async def _handle_job_error(self, job: Job, error: str):
        """Handle job execution error."""
        self.stats['jobs_failed'] += 1
        
        for queue in self.queues:
            if queue.name == job.queue_name:
                await queue.complete_job(job.id, error=error)
                break


class QueueManager:
    """Central queue management system."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.queues: Dict[str, BaseQueue] = {}
        self.workers: Dict[str, Worker] = {}
        self.redis_client = None
        
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for queues: {e}")
    
    def create_queue(self, name: str, queue_type: QueueType = QueueType.FIFO, 
                    use_redis: bool = True) -> BaseQueue:
        """Create a new queue."""
        if use_redis and self.redis_client:
            queue = RedisQueue(name, self.redis_client, queue_type)
        else:
            queue = BaseQueue(name, queue_type)
        
        self.queues[name] = queue
        logger.info(f"Created queue '{name}' of type {queue_type.value}")
        return queue
    
    def get_queue(self, name: str) -> Optional[BaseQueue]:
        """Get queue by name."""
        return self.queues.get(name)
    
    def create_worker(self, worker_id: str, queue_names: List[str], 
                     concurrency: int = 1) -> Worker:
        """Create a new worker."""
        queues = [self.queues[name] for name in queue_names if name in self.queues]
        worker = Worker(worker_id, queues, concurrency)
        self.workers[worker_id] = worker
        
        logger.info(f"Created worker '{worker_id}' for queues {queue_names}")
        return worker
    
    def get_worker(self, worker_id: str) -> Optional[Worker]:
        """Get worker by ID."""
        return self.workers.get(worker_id)
    
    async def enqueue_job(self, queue_name: str, func_name: str, 
                         args: tuple = (), kwargs: dict = None, 
                         config: Optional[JobConfig] = None) -> str:
        """Enqueue a job."""
        if queue_name not in self.queues:
            raise ValueError(f"Queue '{queue_name}' not found")
        
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            queue_name=queue_name,
            func_name=func_name,
            args=args,
            kwargs=kwargs or {},
            config=config or JobConfig()
        )
        
        queue = self.queues[queue_name]
        await queue.enqueue(job)
        
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status."""
        for queue in self.queues.values():
            job = await queue.get_job(job_id)
            if job:
                return job.to_dict()
        return None
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        for queue in self.queues.values():
            if await queue.cancel_job(job_id):
                return True
        return False
    
    async def get_queue_stats(self, queue_name: str) -> Optional[QueueStats]:
        """Get queue statistics."""
        if queue_name in self.queues:
            return await self.queues[queue_name].get_stats()
        return None
    
    async def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all queues and workers."""
        stats = {
            'queues': {},
            'workers': {}
        }
        
        # Queue stats
        for name, queue in self.queues.items():
            queue_stats = await queue.get_stats()
            stats['queues'][name] = asdict(queue_stats)
        
        # Worker stats
        for worker_id, worker in self.workers.items():
            stats['workers'][worker_id] = worker.stats.copy()
        
        return stats
    
    async def start_all_workers(self):
        """Start all workers."""
        for worker in self.workers.values():
            await worker.start()
    
    async def stop_all_workers(self):
        """Stop all workers."""
        for worker in self.workers.values():
            await worker.stop()


# Decorator for creating job functions
def job(queue_name: str, config: Optional[JobConfig] = None):
    """Decorator to mark function as a job."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        # Store job metadata
        wrapper._job_queue = queue_name
        wrapper._job_config = config or JobConfig()
        wrapper._job_func_name = func.__name__
        
        return wrapper
    return decorator


# Global queue manager
queue_manager = QueueManager(
    redis_url=getattr(settings, 'redis_url', None)
)


def get_queue_manager() -> QueueManager:
    """Get the global queue manager."""
    return queue_manager