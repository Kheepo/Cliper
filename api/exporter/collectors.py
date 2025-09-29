#!/usr/bin/env python3
"""
Metric Collectors for Video Processing System

Implements specialized collectors for different system components:
- System metrics (CPU, memory, disk)
- Database metrics (PostgreSQL)
- Redis metrics
- Celery metrics
- Video processing metrics
- AI service metrics
- FFmpeg metrics
- WebSocket metrics
"""

import asyncio
import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

import aioredis
import asyncpg
import httpx
import psutil
import structlog
from prometheus_client import Counter, Gauge, Histogram, Info


class BaseCollector(ABC):
    """Base class for all metric collectors."""
    
    def __init__(self, settings):
        self.settings = settings
        self.logger = structlog.get_logger()
        self.last_collection = 0
        self.collection_count = 0
        self.error_count = 0
    
    @abstractmethod
    async def collect(self):
        """Collect metrics from the target system."""
        pass
    
    async def is_healthy(self) -> bool:
        """Check if the collector is healthy."""
        # Default implementation: healthy if collected recently
        return time.time() - self.last_collection < 300  # 5 minutes
    
    async def close(self):
        """Clean up resources."""
        pass


class SystemCollector(BaseCollector):
    """Collects system-level metrics."""
    
    def __init__(self, settings):
        super().__init__(settings)
        
        # System metrics
        self.cpu_usage = Gauge(
            'video_processing_system_cpu_usage_percent',
            'System CPU usage percentage'
        )
        
        self.memory_usage = Gauge(
            'video_processing_system_memory_usage_bytes',
            'System memory usage in bytes'
        )
        
        self.memory_total = Gauge(
            'video_processing_system_memory_total_bytes',
            'Total system memory in bytes'
        )
        
        self.disk_usage = Gauge(
            'video_processing_system_disk_usage_bytes',
            'Disk usage in bytes',
            ['device', 'mountpoint']
        )
        
        self.disk_total = Gauge(
            'video_processing_system_disk_total_bytes',
            'Total disk space in bytes',
            ['device', 'mountpoint']
        )
        
        self.load_average = Gauge(
            'video_processing_system_load_average',
            'System load average',
            ['period']
        )
        
        self.network_bytes = Counter(
            'video_processing_system_network_bytes_total',
            'Network bytes transferred',
            ['interface', 'direction']
        )
        
        self.process_count = Gauge(
            'video_processing_system_process_count',
            'Number of running processes'
        )
        
        self.open_files = Gauge(
            'video_processing_system_open_files',
            'Number of open file descriptors'
        )
    
    async def collect(self):
        """Collect system metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.memory_usage.set(memory.used)
            self.memory_total.set(memory.total)
            
            # Disk usage
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    self.disk_usage.labels(
                        device=partition.device,
                        mountpoint=partition.mountpoint
                    ).set(usage.used)
                    self.disk_total.labels(
                        device=partition.device,
                        mountpoint=partition.mountpoint
                    ).set(usage.total)
                except (PermissionError, OSError):
                    continue
            
            # Load average (Unix-like systems)
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()
                self.load_average.labels(period='1m').set(load_avg[0])
                self.load_average.labels(period='5m').set(load_avg[1])
                self.load_average.labels(period='15m').set(load_avg[2])
            
            # Network statistics
            net_io = psutil.net_io_counters(pernic=True)
            for interface, stats in net_io.items():
                self.network_bytes.labels(
                    interface=interface,
                    direction='sent'
                )._value._value = stats.bytes_sent
                self.network_bytes.labels(
                    interface=interface,
                    direction='recv'
                )._value._value = stats.bytes_recv
            
            # Process count
            self.process_count.set(len(psutil.pids()))
            
            # Open files
            try:
                open_files = len(psutil.Process().open_files())
                self.open_files.set(open_files)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            self.last_collection = time.time()
            self.collection_count += 1
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Failed to collect system metrics",
                error=str(e),
                exc_info=True
            )
            raise


class DatabaseCollector(BaseCollector):
    """Collects PostgreSQL database metrics."""
    
    def __init__(self, settings):
        super().__init__(settings)
        self.connection_pool = None
        
        # Database metrics
        self.connections_active = Gauge(
            'video_processing_db_connections_active',
            'Number of active database connections'
        )
        
        self.connections_total = Gauge(
            'video_processing_db_connections_total',
            'Total number of database connections'
        )
        
        self.query_duration = Histogram(
            'video_processing_db_query_duration_seconds',
            'Database query duration',
            ['query_type']
        )
        
        self.transactions_total = Counter(
            'video_processing_db_transactions_total',
            'Total number of database transactions',
            ['status']
        )
        
        self.table_size = Gauge(
            'video_processing_db_table_size_bytes',
            'Database table size in bytes',
            ['table_name']
        )
        
        self.index_size = Gauge(
            'video_processing_db_index_size_bytes',
            'Database index size in bytes',
            ['table_name', 'index_name']
        )
        
        self.slow_queries = Counter(
            'video_processing_db_slow_queries_total',
            'Number of slow queries (>1s)'
        )
    
    async def _get_connection(self):
        """Get database connection."""
        if not self.connection_pool:
            self.connection_pool = await asyncpg.create_pool(
                self.settings.database_url,
                min_size=1,
                max_size=5
            )
        return self.connection_pool
    
    async def collect(self):
        """Collect database metrics."""
        try:
            pool = await self._get_connection()
            
            async with pool.acquire() as conn:
                # Connection statistics
                result = await conn.fetchrow(
                    "SELECT count(*) as active FROM pg_stat_activity WHERE state = 'active'"
                )
                self.connections_active.set(result['active'])
                
                result = await conn.fetchrow(
                    "SELECT count(*) as total FROM pg_stat_activity"
                )
                self.connections_total.set(result['total'])
                
                # Transaction statistics
                result = await conn.fetchrow(
                    "SELECT xact_commit, xact_rollback FROM pg_stat_database WHERE datname = current_database()"
                )
                if result:
                    self.transactions_total.labels(status='commit')._value._value = result['xact_commit']
                    self.transactions_total.labels(status='rollback')._value._value = result['xact_rollback']
                
                # Table sizes
                tables = await conn.fetch(
                    """
                    SELECT 
                        schemaname,
                        tablename,
                        pg_total_relation_size(schemaname||'.'||tablename) as size
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    """
                )
                
                for table in tables:
                    self.table_size.labels(
                        table_name=table['tablename']
                    ).set(table['size'])
                
                # Index sizes
                indexes = await conn.fetch(
                    """
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        pg_relation_size(indexname) as size
                    FROM pg_indexes 
                    WHERE schemaname = 'public'
                    """
                )
                
                for index in indexes:
                    self.index_size.labels(
                        table_name=index['tablename'],
                        index_name=index['indexname']
                    ).set(index['size'])
                
                # Slow queries (from pg_stat_statements if available)
                try:
                    slow_queries = await conn.fetchrow(
                        """
                        SELECT count(*) as slow_count 
                        FROM pg_stat_statements 
                        WHERE mean_exec_time > 1000
                        """
                    )
                    if slow_queries:
                        self.slow_queries._value._value = slow_queries['slow_count']
                except Exception:
                    # pg_stat_statements extension not available
                    pass
            
            self.last_collection = time.time()
            self.collection_count += 1
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Failed to collect database metrics",
                error=str(e),
                exc_info=True
            )
            raise
    
    async def close(self):
        """Close database connection pool."""
        if self.connection_pool:
            await self.connection_pool.close()


class RedisCollector(BaseCollector):
    """Collects Redis metrics."""
    
    def __init__(self, settings):
        super().__init__(settings)
        self.redis_client = None
        
        # Redis metrics
        self.memory_usage = Gauge(
            'video_processing_redis_memory_usage_bytes',
            'Redis memory usage in bytes'
        )
        
        self.connections = Gauge(
            'video_processing_redis_connections',
            'Number of Redis connections'
        )
        
        self.commands_processed = Counter(
            'video_processing_redis_commands_processed_total',
            'Total number of Redis commands processed'
        )
        
        self.keyspace_hits = Counter(
            'video_processing_redis_keyspace_hits_total',
            'Total number of Redis keyspace hits'
        )
        
        self.keyspace_misses = Counter(
            'video_processing_redis_keyspace_misses_total',
            'Total number of Redis keyspace misses'
        )
        
        self.keys_count = Gauge(
            'video_processing_redis_keys_count',
            'Number of keys in Redis database',
            ['database']
        )
        
        self.expired_keys = Counter(
            'video_processing_redis_expired_keys_total',
            'Total number of expired keys'
        )
    
    async def _get_client(self):
        """Get Redis client."""
        if not self.redis_client:
            self.redis_client = aioredis.from_url(
                self.settings.redis_url,
                decode_responses=True
            )
        return self.redis_client
    
    async def collect(self):
        """Collect Redis metrics."""
        try:
            client = await self._get_client()
            
            # Get Redis info
            info = await client.info()
            
            # Memory usage
            self.memory_usage.set(info.get('used_memory', 0))
            
            # Connections
            self.connections.set(info.get('connected_clients', 0))
            
            # Commands processed
            self.commands_processed._value._value = info.get('total_commands_processed', 0)
            
            # Keyspace statistics
            self.keyspace_hits._value._value = info.get('keyspace_hits', 0)
            self.keyspace_misses._value._value = info.get('keyspace_misses', 0)
            
            # Expired keys
            self.expired_keys._value._value = info.get('expired_keys', 0)
            
            # Database key counts
            for key, value in info.items():
                if key.startswith('db'):
                    db_num = key[2:]  # Remove 'db' prefix
                    # Parse db info: "keys=X,expires=Y,avg_ttl=Z"
                    db_info = dict(item.split('=') for item in value.split(','))
                    keys_count = int(db_info.get('keys', 0))
                    self.keys_count.labels(database=db_num).set(keys_count)
            
            self.last_collection = time.time()
            self.collection_count += 1
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Failed to collect Redis metrics",
                error=str(e),
                exc_info=True
            )
            raise
    
    async def close(self):
        """Close Redis client."""
        if self.redis_client:
            await self.redis_client.close()


class CeleryCollector(BaseCollector):
    """Collects Celery worker and task metrics."""
    
    def __init__(self, settings):
        super().__init__(settings)
        
        # Celery metrics
        self.active_workers = Gauge(
            'video_processing_celery_active_workers',
            'Number of active Celery workers'
        )
        
        self.active_tasks = Gauge(
            'video_processing_celery_active_tasks',
            'Number of active Celery tasks',
            ['worker', 'task_name']
        )
        
        self.task_queue_length = Gauge(
            'video_processing_celery_queue_length',
            'Length of Celery task queues',
            ['queue']
        )
        
        self.tasks_total = Counter(
            'video_processing_celery_tasks_total',
            'Total number of Celery tasks',
            ['task_name', 'status']
        )
        
        self.task_duration = Histogram(
            'video_processing_celery_task_duration_seconds',
            'Celery task duration',
            ['task_name']
        )
        
        self.worker_memory = Gauge(
            'video_processing_celery_worker_memory_bytes',
            'Celery worker memory usage',
            ['worker']
        )
    
    async def collect(self):
        """Collect Celery metrics."""
        try:
            # Use Flower API if available
            flower_url = "http://localhost:5555"
            
            async with httpx.AsyncClient() as client:
                try:
                    # Get worker statistics
                    response = await client.get(f"{flower_url}/api/workers")
                    if response.status_code == 200:
                        workers = response.json()
                        self.active_workers.set(len(workers))
                        
                        for worker_name, worker_info in workers.items():
                            # Worker memory usage
                            if 'rusage' in worker_info:
                                memory_usage = worker_info['rusage'].get('maxrss', 0) * 1024  # Convert to bytes
                                self.worker_memory.labels(worker=worker_name).set(memory_usage)
                    
                    # Get active tasks
                    response = await client.get(f"{flower_url}/api/tasks")
                    if response.status_code == 200:
                        tasks = response.json()
                        
                        # Count active tasks by worker and task name
                        active_tasks = {}
                        for task_id, task_info in tasks.items():
                            if task_info.get('state') in ['PENDING', 'STARTED', 'RETRY']:
                                worker = task_info.get('worker', 'unknown')
                                task_name = task_info.get('name', 'unknown')
                                key = (worker, task_name)
                                active_tasks[key] = active_tasks.get(key, 0) + 1
                        
                        # Update metrics
                        for (worker, task_name), count in active_tasks.items():
                            self.active_tasks.labels(
                                worker=worker,
                                task_name=task_name
                            ).set(count)
                    
                except httpx.RequestError:
                    # Flower not available, try Redis directly
                    await self._collect_from_redis()
            
            self.last_collection = time.time()
            self.collection_count += 1
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Failed to collect Celery metrics",
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _collect_from_redis(self):
        """Collect Celery metrics directly from Redis."""
        try:
            import aioredis
            client = aioredis.from_url(self.settings.redis_url)
            
            # Get queue lengths
            queues = ['celery', 'video_processing', 'ai_tasks']
            for queue in queues:
                length = await client.llen(queue)
                self.task_queue_length.labels(queue=queue).set(length)
            
            await client.close()
            
        except Exception as e:
            self.logger.warning(
                "Failed to collect Celery metrics from Redis",
                error=str(e)
            )


class VideoProcessingCollector(BaseCollector):
    """Collects video processing specific metrics."""
    
    def __init__(self, settings):
        super().__init__(settings)
        
        # Video processing metrics
        self.videos_processed = Counter(
            'video_processing_videos_processed_total',
            'Total number of videos processed',
            ['status']
        )
        
        self.clips_generated = Counter(
            'video_processing_clips_generated_total',
            'Total number of clips generated'
        )
        
        self.processing_duration = Histogram(
            'video_processing_duration_seconds',
            'Video processing duration',
            ['video_duration_bucket']
        )
        
        self.queue_size = Gauge(
            'video_processing_queue_size',
            'Number of videos in processing queue'
        )
        
        self.active_processing = Gauge(
            'video_processing_active_count',
            'Number of videos currently being processed'
        )
        
        self.storage_usage = Gauge(
            'video_processing_storage_usage_bytes',
            'Storage usage for video files',
            ['type']  # original, processed, clips
        )
        
        self.transcription_accuracy = Gauge(
            'video_processing_transcription_accuracy',
            'Transcription accuracy score'
        )
    
    async def collect(self):
        """Collect video processing metrics."""
        try:
            # Get metrics from API
            api_url = f"{self.settings.api_base_url}/metrics/video-processing"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, timeout=10.0)
                if response.status_code == 200:
                    metrics = response.json()
                    
                    # Update metrics
                    self.queue_size.set(metrics.get('queue_size', 0))
                    self.active_processing.set(metrics.get('active_processing', 0))
                    
                    # Storage usage
                    storage = metrics.get('storage_usage', {})
                    for storage_type, usage in storage.items():
                        self.storage_usage.labels(type=storage_type).set(usage)
                    
                    # Transcription accuracy
                    accuracy = metrics.get('transcription_accuracy', 0)
                    self.transcription_accuracy.set(accuracy)
            
            self.last_collection = time.time()
            self.collection_count += 1
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Failed to collect video processing metrics",
                error=str(e),
                exc_info=True
            )
            raise


class AIServiceCollector(BaseCollector):
    """Collects AI service metrics."""
    
    def __init__(self, settings):
        super().__init__(settings)
        
        # AI service metrics
        self.api_requests = Counter(
            'video_processing_ai_api_requests_total',
            'Total AI API requests',
            ['service', 'status']
        )
        
        self.api_duration = Histogram(
            'video_processing_ai_api_duration_seconds',
            'AI API request duration',
            ['service']
        )
        
        self.tokens_used = Counter(
            'video_processing_ai_tokens_used_total',
            'Total AI tokens used',
            ['service', 'type']  # input, output
        )
        
        self.model_accuracy = Gauge(
            'video_processing_ai_model_accuracy',
            'AI model accuracy score',
            ['service', 'model']
        )
    
    async def collect(self):
        """Collect AI service metrics."""
        try:
            # Get metrics from API
            api_url = f"{self.settings.api_base_url}/metrics/ai-services"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, timeout=10.0)
                if response.status_code == 200:
                    metrics = response.json()
                    
                    # Update metrics from API response
                    for service, service_metrics in metrics.items():
                        # API requests
                        requests = service_metrics.get('requests', {})
                        for status, count in requests.items():
                            self.api_requests.labels(
                                service=service,
                                status=status
                            )._value._value = count
                        
                        # Tokens used
                        tokens = service_metrics.get('tokens', {})
                        for token_type, count in tokens.items():
                            self.tokens_used.labels(
                                service=service,
                                type=token_type
                            )._value._value = count
                        
                        # Model accuracy
                        accuracy = service_metrics.get('accuracy', 0)
                        model = service_metrics.get('model', 'unknown')
                        self.model_accuracy.labels(
                            service=service,
                            model=model
                        ).set(accuracy)
            
            self.last_collection = time.time()
            self.collection_count += 1
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Failed to collect AI service metrics",
                error=str(e),
                exc_info=True
            )
            raise


class FFmpegCollector(BaseCollector):
    """Collects FFmpeg operation metrics."""
    
    def __init__(self, settings):
        super().__init__(settings)
        
        # FFmpeg metrics
        self.operations_total = Counter(
            'video_processing_ffmpeg_operations_total',
            'Total FFmpeg operations',
            ['operation', 'status']
        )
        
        self.operation_duration = Histogram(
            'video_processing_ffmpeg_operation_duration_seconds',
            'FFmpeg operation duration',
            ['operation']
        )
        
        self.active_processes = Gauge(
            'video_processing_ffmpeg_active_processes',
            'Number of active FFmpeg processes'
        )
        
        self.memory_usage = Gauge(
            'video_processing_ffmpeg_memory_usage_bytes',
            'FFmpeg process memory usage'
        )
        
        self.gpu_usage = Gauge(
            'video_processing_ffmpeg_gpu_usage_percent',
            'FFmpeg GPU usage percentage'
        )
    
    async def collect(self):
        """Collect FFmpeg metrics."""
        try:
            # Count active FFmpeg processes
            ffmpeg_processes = []
            total_memory = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if 'ffmpeg' in proc.info['name'].lower():
                        ffmpeg_processes.append(proc)
                        total_memory += proc.info['memory_info'].rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self.active_processes.set(len(ffmpeg_processes))
            self.memory_usage.set(total_memory)
            
            # Get GPU usage if available
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    avg_gpu_usage = sum(gpu.load * 100 for gpu in gpus) / len(gpus)
                    self.gpu_usage.set(avg_gpu_usage)
            except ImportError:
                pass
            
            self.last_collection = time.time()
            self.collection_count += 1
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Failed to collect FFmpeg metrics",
                error=str(e),
                exc_info=True
            )
            raise


class WebSocketCollector(BaseCollector):
    """Collects WebSocket connection metrics."""
    
    def __init__(self, settings):
        super().__init__(settings)
        
        # WebSocket metrics
        self.active_connections = Gauge(
            'video_processing_websocket_active_connections',
            'Number of active WebSocket connections'
        )
        
        self.messages_sent = Counter(
            'video_processing_websocket_messages_sent_total',
            'Total WebSocket messages sent',
            ['message_type']
        )
        
        self.messages_received = Counter(
            'video_processing_websocket_messages_received_total',
            'Total WebSocket messages received',
            ['message_type']
        )
        
        self.connection_duration = Histogram(
            'video_processing_websocket_connection_duration_seconds',
            'WebSocket connection duration'
        )
        
        self.connection_errors = Counter(
            'video_processing_websocket_connection_errors_total',
            'Total WebSocket connection errors',
            ['error_type']
        )
    
    async def collect(self):
        """Collect WebSocket metrics."""
        try:
            # Get metrics from API
            api_url = f"{self.settings.api_base_url}/metrics/websocket"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, timeout=10.0)
                if response.status_code == 200:
                    metrics = response.json()
                    
                    # Update metrics
                    self.active_connections.set(metrics.get('active_connections', 0))
                    
                    # Messages
                    messages_sent = metrics.get('messages_sent', {})
                    for msg_type, count in messages_sent.items():
                        self.messages_sent.labels(message_type=msg_type)._value._value = count
                    
                    messages_received = metrics.get('messages_received', {})
                    for msg_type, count in messages_received.items():
                        self.messages_received.labels(message_type=msg_type)._value._value = count
                    
                    # Connection errors
                    errors = metrics.get('connection_errors', {})
                    for error_type, count in errors.items():
                        self.connection_errors.labels(error_type=error_type)._value._value = count
            
            self.last_collection = time.time()
            self.collection_count += 1
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(
                "Failed to collect WebSocket metrics",
                error=str(e),
                exc_info=True
            )
            raise