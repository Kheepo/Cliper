"""Enhanced Celery application configuration.

This module provides:
- Celery app initialization with optimized settings
- Task routing and queue configuration
- Worker monitoring and health checks
- Integration with Redis and enhanced services
- Production-ready configuration
"""

import os
import logging
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, task_prerun, task_postrun
from kombu import Queue

from api.utils.config import get_cached_celery_config, get_cached_redis_config
from api.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Get configuration
celery_config = get_cached_celery_config()
redis_config = get_cached_redis_config()

# Create Celery app
celery_app = Celery('virality_clipper')

# Configure Celery
celery_app.conf.update(
    # Broker and backend
    broker_url=celery_config.broker_url,
    result_backend=celery_config.result_backend,
    
    # Serialization
    task_serializer=celery_config.task_serializer,
    accept_content=celery_config.accept_content,
    result_serializer=celery_config.result_serializer,
    
    # Timezone
    timezone=celery_config.timezone,
    enable_utc=celery_config.enable_utc,
    
    # Worker configuration
    worker_concurrency=celery_config.worker_concurrency,
    worker_prefetch_multiplier=celery_config.worker_prefetch_multiplier,
    worker_max_tasks_per_child=celery_config.worker_max_tasks_per_child,
    worker_max_memory_per_child=celery_config.worker_max_memory_per_child,
    
    # Task configuration
    task_soft_time_limit=celery_config.task_soft_time_limit,
    task_time_limit=celery_config.task_time_limit,
    task_acks_late=celery_config.task_acks_late,
    task_reject_on_worker_lost=celery_config.task_reject_on_worker_lost,
    
    # Result configuration
    result_expires=celery_config.result_expires,
    result_compression=celery_config.result_compression,
    
    # Queue configuration
    task_default_queue='default',
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('video_processing', routing_key='video_processing'),
        Queue('clip_processing', routing_key='clip_processing'),
        Queue('transcription', routing_key='transcription'),
        Queue('ai_analysis', routing_key='ai_analysis'),
        Queue('health_checks', routing_key='health_checks'),
        Queue('cleanup', routing_key='cleanup'),
    ),
    
    # Task routing
    task_routes={
        # Video processing tasks
        'api.services.enhanced_celery_tasks.process_video_clips_task': {
            'queue': 'video_processing',
            'routing_key': 'video_processing'
        },
        'api.services.enhanced_celery_tasks.process_single_clip_task': {
            'queue': 'clip_processing',
            'routing_key': 'clip_processing'
        },
        
        # AI tasks
        'api.services.ai_service.transcribe_audio': {
            'queue': 'transcription',
            'routing_key': 'transcription'
        },
        'api.services.ai_service.analyze_content_moments': {
            'queue': 'ai_analysis',
            'routing_key': 'ai_analysis'
        },
        
        # Health and maintenance
        'api.services.enhanced_celery_tasks.health_check_task': {
            'queue': 'health_checks',
            'routing_key': 'health_checks'
        },
        'api.services.enhanced_celery_tasks.cleanup_temp_files_task': {
            'queue': 'cleanup',
            'routing_key': 'cleanup'
        },
        
        # Legacy tasks (for backward compatibility)
        'api.tasks.generate_clips_task': {
            'queue': 'video_processing',
            'routing_key': 'video_processing'
        },
        'api.tasks._generate_single_clip': {
            'queue': 'clip_processing',
            'routing_key': 'clip_processing'
        }
    },
    
    # Monitoring and logging
    
    # Error handling (updated for 1-hour video support)
    task_annotations={
        '*': {
            'rate_limit': '100/m',  # 100 tasks per minute max
            'time_limit': celery_config.task_time_limit,
            'soft_time_limit': celery_config.task_soft_time_limit
        },
        'api.services.enhanced_celery_tasks.process_video_clips_task': {
            'rate_limit': '5/m',  # Reduced rate for 1-hour videos
            'time_limit': 3600,  # 1 hour for full video processing
            'soft_time_limit': 3300  # 55 minutes soft limit
        },
        'api.services.enhanced_celery_tasks.process_single_clip_task': {
            'rate_limit': '30/m',  # Reduced rate for longer clips
            'time_limit': 1800,  # 30 minutes per clip
            'soft_time_limit': 1500  # 25 minutes soft limit
        },
        'api.tasks.generate_clips_task': {
            'rate_limit': '5/m',  # Reduced rate for 1-hour videos
            'time_limit': 3600,  # 1 hour for full video processing
            'soft_time_limit': 3300  # 55 minutes soft limit
        }
    },
    
    # Redis connection settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Result backend settings
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
        'retry_policy': {
            'timeout': 5.0
        }
    },
    
    # Beat schedule (for periodic tasks)
    beat_schedule={
        'health-check': {
            'task': 'api.services.enhanced_celery_tasks.health_check_task',
            'schedule': 300.0,  # Every 5 minutes
            'options': {'queue': 'health_checks'}
        },
        'cleanup-temp-files': {
            'task': 'api.services.enhanced_celery_tasks.cleanup_temp_files_task',
            'schedule': 3600.0,  # Every hour
            'options': {'queue': 'cleanup'}
        },
        'redis-stats': {
            'task': 'api.services.enhanced_celery_tasks.update_redis_stats_task',
            'schedule': 60.0,  # Every minute
            'options': {'queue': 'health_checks'}
        }
    },
    beat_scheduler='celery.beat:PersistentScheduler',
    
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
    
    # Performance optimizations
    task_compression='gzip',
    task_ignore_result=False,
    
    # Advanced settings
    worker_disable_rate_limits=False,
    worker_enable_remote_control=True,
    
    # Database settings (if using database as result backend)
    database_short_lived_sessions=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Custom settings for our application
    include=[
        'api.services.enhanced_celery_tasks',
        'api.tasks',  # Legacy tasks for backward compatibility
    ]
)


# Signal handlers for monitoring and logging
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker ready signal."""
    logger.info(f"Celery worker {sender} is ready")
    
    # Initialize services
    try:
        from api.services.redis_service import RedisService
        from api.services.enhanced_video_processor import EnhancedVideoProcessor
        from api.services.ai_service import EnhancedAIService
        
        # Test service connections
        redis_service = RedisService()
        if redis_service.health_check():
            logger.info("Redis service connection established")
        else:
            logger.warning("Redis service connection failed")
        
        # Test video processor
        video_processor = EnhancedVideoProcessor()
        if video_processor.health_check():
            logger.info("Video processor initialized successfully")
        else:
            logger.warning("Video processor initialization failed")
        
        # Test AI service
        ai_service = EnhancedAIService()
        if ai_service.health_check():
            logger.info("AI service initialized successfully")
        else:
            logger.warning("AI service initialization failed")
            
    except Exception as e:
        logger.error(f"Error initializing services: {e}")


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Handle worker shutdown signal."""
    logger.info(f"Celery worker {sender} is shutting down")
    
    # Cleanup resources
    try:
        from api.services.redis_service import RedisService
        
        redis_service = RedisService()
        redis_service.close_connections()
        logger.info("Redis connections closed")
        
    except Exception as e:
        logger.error(f"Error during worker shutdown: {e}")


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task prerun signal."""
    logger.info(f"Starting task {task.name} with ID {task_id}")
    
    # Log resource usage before task
    try:
        import psutil
        memory_percent = psutil.virtual_memory().percent
        cpu_percent = psutil.cpu_percent(interval=1)
        
        logger.info(f"System resources before task: Memory {memory_percent}%, CPU {cpu_percent}%")
        
        # Store start time for performance tracking
        import time
        task.start_time = time.time()
        
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Error logging system resources: {e}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """Handle task postrun signal."""
    
    # Calculate task duration
    duration = None
    if hasattr(task, 'start_time'):
        import time
        duration = time.time() - task.start_time
    
    logger.info(f"Completed task {task.name} with ID {task_id} in {duration:.2f}s (state: {state})")
    
    # Log resource usage after task
    try:
        import psutil
        memory_percent = psutil.virtual_memory().percent
        cpu_percent = psutil.cpu_percent(interval=1)
        
        logger.info(f"System resources after task: Memory {memory_percent}%, CPU {cpu_percent}%")
        
        # Store task metrics in Redis
        from api.services.redis_service import RedisService
        redis_service = RedisService()
        
        metrics = {
            'task_name': task.name,
            'task_id': task_id,
            'duration': duration,
            'state': state,
            'memory_percent': memory_percent,
            'cpu_percent': cpu_percent,
            'timestamp': time.time()
        }
        
        redis_service.store_task_metrics(task_id, metrics)
        
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Error logging task metrics: {e}")


def get_celery_app() -> Celery:
    """Get the configured Celery app instance."""
    return celery_app


def start_worker(queues=None, concurrency=None, loglevel='INFO'):
    """Start a Celery worker programmatically."""
    
    if queues is None:
        queues = ['default', 'video_processing', 'clip_processing', 'transcription', 'ai_analysis']
    
    if concurrency is None:
        concurrency = celery_config.worker_concurrency
    
    logger.info(f"Starting Celery worker with queues: {queues}, concurrency: {concurrency}")
    
    # Start worker
    celery_app.worker_main([
        'worker',
        f'--queues={','.join(queues)}',
        f'--concurrency={concurrency}',
        f'--loglevel={loglevel}',
        '--without-gossip',
        '--without-mingle',
        '--without-heartbeat'
    ])


def start_beat(loglevel='INFO'):
    """Start Celery beat scheduler."""
    
    logger.info("Starting Celery beat scheduler")
    
    celery_app.start([
        'celery',
        'beat',
        f'--loglevel={loglevel}',
        '--pidfile=',
        '--schedule=/tmp/celerybeat-schedule'
    ])


def monitor_workers():
    """Monitor active Celery workers."""
    
    try:
        inspect = celery_app.control.inspect()
        
        # Get active workers
        active_workers = inspect.active()
        if active_workers:
            logger.info(f"Active workers: {list(active_workers.keys())}")
            
            for worker, tasks in active_workers.items():
                logger.info(f"Worker {worker} has {len(tasks)} active tasks")
        else:
            logger.warning("No active workers found")
        
        # Get worker stats
        stats = inspect.stats()
        if stats:
            for worker, worker_stats in stats.items():
                logger.info(f"Worker {worker} stats: {worker_stats}")
        
        # Get reserved tasks
        reserved = inspect.reserved()
        if reserved:
            for worker, tasks in reserved.items():
                if tasks:
                    logger.info(f"Worker {worker} has {len(tasks)} reserved tasks")
        
        return {
            'active_workers': active_workers or {},
            'stats': stats or {},
            'reserved': reserved or {}
        }
        
    except Exception as e:
        logger.error(f"Error monitoring workers: {e}")
        return {'error': str(e)}


def get_task_status(task_id: str):
    """Get status of a specific task."""
    
    try:
        result = celery_app.AsyncResult(task_id)
        
        return {
            'task_id': task_id,
            'state': result.state,
            'result': result.result,
            'traceback': result.traceback,
            'successful': result.successful(),
            'failed': result.failed(),
            'ready': result.ready()
        }
        
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return {'error': str(e)}


def purge_all_tasks():
    """Purge all pending tasks from all queues."""
    
    try:
        celery_app.control.purge()
        logger.info("All pending tasks purged")
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error purging tasks: {e}")
        return {'error': str(e)}


def revoke_task(task_id: str, terminate=False):
    """Revoke a specific task."""
    
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task {task_id} revoked (terminate={terminate})")
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error revoking task: {e}")
        return {'error': str(e)}


def is_redis_available() -> bool:
    """Check if Redis is available for Celery."""
    try:
        from redis import Redis
        redis_client = Redis.from_url(redis_config.get_url())
        redis_client.ping()
        return True
    except Exception as e:
        logger.debug(f"Redis not available: {e}")
        return False


def is_background_tasks_enabled() -> bool:
    """Check if background task processing is enabled."""
    # Check if Celery is properly configured and Redis is available
    return is_redis_available()


def is_background_tasks_available() -> bool:
    """Check if background task processing is available."""
    # Alias for is_background_tasks_enabled for compatibility
    return is_background_tasks_enabled()


if __name__ == '__main__':
    # For development - start worker directly
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'worker':
            start_worker()
        elif command == 'beat':
            start_beat()
        elif command == 'monitor':
            import json
            print(json.dumps(monitor_workers(), indent=2))
        else:
            print(f"Unknown command: {command}")
            print("Available commands: worker, beat, monitor")
    else:
        print("Usage: python celery_app.py [worker|beat|monitor]")