"""
Unified Celery Tasks for Cliper
Consolidates all background processing tasks
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from celery import Celery
from celery.exceptions import Retry

from .services.unified_task_processor import unified_task_processor, ProcessingOptions
from .services.unified_ai_service import unified_ai_service
from .services.unified_video_processor import unified_video_processor
from .services.supabase_service import supabase_service

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery('cliper')

# Configure Celery
celery_app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    result_expires=3600,  # 1 hour
    worker_max_tasks_per_child=50,
    task_routes={
        'process_video_unified_task': {'queue': 'video_processing'},
        'process_url_unified_task': {'queue': 'video_processing'},
        'cleanup_task': {'queue': 'maintenance'},
    }
)


class TaskProgress:
    """Task progress tracking."""
    
    def __init__(self, task_id: str, job_id: str):
        self.task_id = task_id
        self.job_id = job_id
        self.start_time = time.time()
        self.last_update = time.time()
    
    async def update(self, progress: int, current_step: str, status: str = "processing"):
        """Update task progress."""
        try:
            await supabase_service.update_job_status(
                self.job_id,
                status=status,
                progress=progress,
                current_step=current_step
            )
            self.last_update = time.time()
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")


@celery_app.task(bind=True, name='process_video_unified_task')
def process_video_unified_task(
    self,
    job_id: str,
    video_path: str,
    original_filename: str,
    file_size: int,
    processing_options_dict: Dict[str, Any]
):
    """Process video file using unified task processor."""
    
    start_time = time.time()
    progress = TaskProgress(self.request.id, job_id)
    
    try:
        # Create processing options from dict
        processing_options = ProcessingOptions(**processing_options_dict)
        
        # Run async task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                unified_task_processor.process_video_task(
                    job_id=job_id,
                    video_path=video_path,
                    original_filename=original_filename,
                    file_size=file_size,
                    processing_options=processing_options,
                    progress_callback=progress.update
                )
            )
            
            processing_time = time.time() - start_time
            logger.info(f"Video processing completed in {processing_time:.2f}s: {job_id}")
            
            return {
                'success': True,
                'job_id': job_id,
                'processing_time': processing_time,
                'result': result
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Video processing failed after {processing_time:.2f}s: {e}")
        
        # Update job status to failed
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                supabase_service.update_job_status(
                    job_id,
                    status="failed",
                    progress=0,
                    current_step=f"Processing failed: {str(e)}"
                )
            )
            loop.close()
        except Exception as update_error:
            logger.error(f"Failed to update job status: {update_error}")
        
        # Retry logic
        if self.request.retries < 3:
            retry_delay = 60 * (2 ** self.request.retries)  # Exponential backoff
            logger.info(f"Retrying video processing in {retry_delay}s (attempt {self.request.retries + 1}/3)")
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {
            'success': False,
            'job_id': job_id,
            'error': str(e),
            'processing_time': processing_time
        }


@celery_app.task(bind=True, name='process_url_unified_task')
def process_url_unified_task(
    self,
    job_id: str,
    video_url: str,
    processing_options_dict: Dict[str, Any]
):
    """Process video from URL using unified task processor."""
    
    start_time = time.time()
    progress = TaskProgress(self.request.id, job_id)
    
    try:
        # Create processing options from dict
        processing_options = ProcessingOptions(**processing_options_dict)
        
        # Run async task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                unified_task_processor.process_url_task(
                    job_id=job_id,
                    video_url=video_url,
                    processing_options=processing_options,
                    progress_callback=progress.update
                )
            )
            
            processing_time = time.time() - start_time
            logger.info(f"URL processing completed in {processing_time:.2f}s: {job_id}")
            
            return {
                'success': True,
                'job_id': job_id,
                'processing_time': processing_time,
                'result': result
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"URL processing failed after {processing_time:.2f}s: {e}")
        
        # Update job status to failed
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                supabase_service.update_job_status(
                    job_id,
                    status="failed",
                    progress=0,
                    current_step=f"URL processing failed: {str(e)}"
                )
            )
            loop.close()
        except Exception as update_error:
            logger.error(f"Failed to update job status: {update_error}")
        
        # Retry logic
        if self.request.retries < 3:
            retry_delay = 60 * (2 ** self.request.retries)  # Exponential backoff
            logger.info(f"Retrying URL processing in {retry_delay}s (attempt {self.request.retries + 1}/3)")
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {
            'success': False,
            'job_id': job_id,
            'error': str(e),
            'processing_time': processing_time
        }


@celery_app.task(name='cleanup_task')
def cleanup_task():
    """Cleanup old files and temporary data."""
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            cleanup_result = loop.run_until_complete(cleanup_old_files())
            logger.info(f"Cleanup completed: {cleanup_result}")
            return cleanup_result
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return {'success': False, 'error': str(e)}


async def cleanup_old_files():
    """Cleanup old files and temporary data."""
    
    cleanup_stats = {
        'deleted_files': 0,
        'freed_space': 0,
        'deleted_temp_files': 0,
        'deleted_old_jobs': 0
    }
    
    try:
        # Cleanup temporary files older than 24 hours
        temp_dirs = ['temp', 'uploads/temp']
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_age = time.time() - os.path.getctime(file_path)
                            if file_age > 86400:  # 24 hours
                                file_size = os.path.getsize(file_path)
                                os.unlink(file_path)
                                cleanup_stats['deleted_temp_files'] += 1
                                cleanup_stats['freed_space'] += file_size
                        except Exception as e:
                            logger.warning(f"Failed to delete temp file {file_path}: {e}")
        
        # Cleanup old failed jobs (older than 7 days)
        cutoff_date = datetime.now().timestamp() - (7 * 24 * 3600)  # 7 days ago
        
        # This would need to be implemented in supabase_service
        # old_jobs = await supabase_service.get_old_failed_jobs(cutoff_date)
        # for job in old_jobs:
        #     await cleanup_job_files(job)
        #     cleanup_stats['deleted_old_jobs'] += 1
        
        cleanup_stats['success'] = True
        cleanup_stats['timestamp'] = datetime.now().isoformat()
        
        logger.info(f"Cleanup completed: {cleanup_stats}")
        return cleanup_stats
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


async def cleanup_job_files(job_data: Dict[str, Any]):
    """Cleanup files associated with a job."""
    
    try:
        job_id = job_data.get('id')
        
        # Delete video file
        video_path = job_data.get('file_path')
        if video_path and os.path.exists(video_path):
            os.unlink(video_path)
        
        # Delete clips directory
        clips_dir = os.path.join('uploads', 'clips', job_id)
        if os.path.exists(clips_dir):
            import shutil
            shutil.rmtree(clips_dir)
        
        # Delete job from database
        await supabase_service.delete_job(job_id)
        
        logger.info(f"Cleaned up job files: {job_id}")
        
    except Exception as e:
        logger.error(f"Failed to cleanup job files: {e}")


@celery_app.task(name='health_check_task')
def health_check_task():
    """Periodic health check task."""
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Check AI service health
            ai_health = loop.run_until_complete(unified_ai_service.health_check())
            
            # Check video processor health
            video_health = loop.run_until_complete(unified_video_processor.health_check())
            
            # Check system resources
            system_resources = unified_video_processor.get_system_resources()
            
            health_status = {
                'ai_service': ai_health,
                'video_processor': video_health,
                'system_resources': system_resources,
                'timestamp': datetime.now().isoformat()
            }
            
            # Log warnings if any component is unhealthy
            if ai_health.get('status') == 'error':
                logger.warning(f"AI service health check failed: {ai_health}")
            
            if video_health.get('status') == 'error':
                logger.warning(f"Video processor health check failed: {video_health}")
            
            # Check memory usage
            memory_percent = system_resources.get('memory', {}).get('percent', 0)
            if memory_percent > 90:
                logger.warning(f"High memory usage: {memory_percent}%")
            
            # Check disk usage
            disk_percent = system_resources.get('disk', {}).get('percent', 0)
            if disk_percent > 90:
                logger.warning(f"High disk usage: {disk_percent}%")
            
            return health_status
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Health check task failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# Periodic tasks configuration
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-every-hour': {
        'task': 'cleanup_task',
        'schedule': crontab(minute=0),  # Every hour
    },
    'health-check-every-5-minutes': {
        'task': 'health_check_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}

celery_app.conf.timezone = 'UTC'
