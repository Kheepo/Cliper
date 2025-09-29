"""Enhanced Celery tasks for distributed video processing.

This module provides production-ready Celery tasks with:
- Distributed processing across multiple workers
- Comprehensive error handling and retry mechanisms
- Real-time progress tracking
- Resource management and monitoring
- Graceful degradation and circuit breaker patterns
"""

import asyncio
import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

from celery import Celery, Task
from celery.exceptions import Retry, WorkerLostError
from celery.signals import task_prerun, task_postrun, task_failure

from api.core.exceptions import (
    VideoProcessingError, ResourceExhaustionError, TranscriptionError,
    EncodingError, ValidationError, TimeoutError as ProcessingTimeoutError
)
from api.core.video_pipeline import (
    ProcessingConfig, ClipSegment, ProcessingResult, ProcessingStatus
)
from api.services.enhanced_video_processor import enhanced_video_processor
from api.services.ai_service import ai_service
from api.services.redis_service import redis_service
from api.utils.retry import (
    exponential_backoff_retry, ROBUST_RETRY, CircuitBreaker
)
from api.utils.config import get_celery_config
from api.services.supabase_service import supabase_service
from api.services.websocket_service import websocket_service

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_config = get_celery_config()
celery_app = Celery('video_processing')
celery_app.config_from_object(celery_config)

# Circuit breakers for external services
supabase_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

ai_service_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30,
    expected_exception=Exception
)


class BaseVideoTask(Task):
    """Base task class with enhanced error handling."""
    
    autoretry_for = (
        VideoProcessingError,
        ResourceExhaustionError,
        TranscriptionError,
        EncodingError,
        ConnectionError,
        TimeoutError
    )
    
    retry_kwargs = {
        'max_retries': 3,
        'countdown': 60,
        'retry_backoff': True,
        'retry_backoff_max': 600,
        'retry_jitter': True
    }
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
        
        # Update status in database
        try:
            clip_id = kwargs.get('clip_id') or (args[0] if args else None)
            if clip_id:
                asyncio.create_task(self._update_clip_status(
                    clip_id, 'failed', error=str(exc)
                ))
        except Exception as e:
            logger.error(f"Failed to update clip status: {e}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {task_id} retrying: {exc}")
        
        try:
            clip_id = kwargs.get('clip_id') or (args[0] if args else None)
            if clip_id:
                asyncio.create_task(self._update_clip_status(
                    clip_id, 'retrying', error=str(exc)
                ))
        except Exception as e:
            logger.error(f"Failed to update retry status: {e}")
    
    async def _update_clip_status(self, clip_id: str, status: str, **kwargs):
        """Update clip status in database."""
        try:
            await supabase_service.update_clip_status(
                clip_id, status, **kwargs
            )
            
            # Broadcast status update
            await websocket_service.broadcast_clip_update({
                'clip_id': clip_id,
                'status': status,
                **kwargs
            })
            
        except Exception as e:
            logger.error(f"Failed to update clip status: {e}")


@celery_app.task(bind=True, base=BaseVideoTask, name='process_video_clips')
def process_video_clips_task(
    self,
    video_id: str,
    video_path: str,
    generation_options: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Main task for processing video clips with distributed processing."""
    
    task_id = self.request.id
    start_time = time.time()
    
    logger.info(f"Starting video processing task {task_id} for video {video_id}")
    
    try:
        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _process_video_clips_async(
                    task_id, video_id, video_path, generation_options, user_id
                )
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Video processing task {task_id} failed: {e}")
        raise
    finally:
        processing_time = time.time() - start_time
        logger.info(f"Video processing task {task_id} completed in {processing_time:.1f}s")


async def _process_video_clips_async(
    task_id: str,
    video_id: str,
    video_path: str,
    generation_options: Dict[str, Any],
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Async implementation of video clip processing with enhanced progress tracking for long videos."""
    
    try:
        # Initial progress tracker (will be updated with chunk count later)
        temp_tracker = ProgressTracker(task_id, video_id, 1)
        
        # Validate inputs
        await temp_tracker.update(5, "Validating inputs")
        await _validate_processing_inputs(video_id, video_path, generation_options)
        
        # Get video metadata to determine if chunking is needed
        await temp_tracker.update(10, "Analyzing video")
        metadata = await enhanced_video_processor.get_video_metadata(video_path)
        
        # Determine if this is a long video that needs chunking
        video_duration = metadata.duration
        is_long_video = video_duration > 1800  # 30 minutes
        
        # Calculate estimated chunks for progress tracking
        estimated_chunks = 1
        if is_long_video:
            # Estimate chunks based on video duration and processing complexity
            chunk_duration = 300  # 5-minute chunks for long videos
            estimated_chunks = max(1, int(video_duration / chunk_duration))
        
        # Create enhanced progress tracker with chunk information
        progress_tracker = ProgressTracker(task_id, video_id, estimated_chunks)
        
        # Extract and transcribe audio
        await progress_tracker.update(20, "Extracting audio")
        audio_path = await enhanced_video_processor.extract_audio(video_path)
        
        try:
            await progress_tracker.update(30, "Transcribing audio")
            if is_long_video:
                await progress_tracker.update(30, f"Transcribing {video_duration/60:.1f}-minute video (this may take longer)")
            
            transcription = await ai_service_circuit_breaker.call(
                ai_service.transcribe_audio_whisper_v3,
                audio_path,
                language=generation_options.get('language')
            )
        finally:
            # Cleanup audio file
            if os.path.exists(audio_path):
                os.unlink(audio_path)
        
        # Analyze content for viral moments
        await progress_tracker.update(50, "Analyzing content for viral moments")
        if is_long_video:
            await progress_tracker.update(50, f"Analyzing {len(transcription)} segments for viral content")
        
        content_moments = await ai_service_circuit_breaker.call(
            ai_service.analyze_content_moments,
            transcription,
            metadata.to_dict(),
            generation_options.get('platform', 'general')
        )
        
        # Convert moments to clip segments
        await progress_tracker.update(60, "Preparing clip segments")
        clip_segments = _convert_moments_to_segments(
            content_moments, generation_options
        )
        
        # Update chunk count based on actual segments
        progress_tracker.total_chunks = len(clip_segments)
        
        # Create processing configuration
        config = _create_processing_config(generation_options, metadata)
        
        # Process clips with enhanced progress tracking
        await progress_tracker.update(70, f"Processing {len(clip_segments)} clips")
        
        # Choose processing strategy based on video length and clip count
        if len(clip_segments) > 4 or is_long_video:
            # Use distributed processing for large batches or long videos
            results = await _process_clips_distributed(
                video_path, clip_segments, config, progress_tracker
            )
        else:
            # Process locally for small batches with chunk progress tracking
            results = []
            for i, segment in enumerate(clip_segments):
                chunk_id = f"clip_{i+1}"
                await progress_tracker.update(
                    70 + (i / len(clip_segments)) * 20,
                    f"Processing clip {i+1}/{len(clip_segments)}",
                    chunk_id
                )
                
                # Process individual clip
                result = await enhanced_video_processor._process_single_chunk(
                    video_path, segment, config, metadata
                )
                results.append(result)
                
                # Mark chunk as completed
                await progress_tracker.update_chunk_completed(
                    chunk_id, f"Completed clip {i+1}/{len(clip_segments)}"
                )
        
        # Save results to database
        await progress_tracker.update(90, "Saving results to database")
        saved_clips = await _save_processing_results(
            video_id, results, generation_options, user_id
        )
        
        await progress_tracker.update(100, "Processing completed successfully")
        
        final_result = {
            'task_id': task_id,
            'video_id': video_id,
            'status': 'completed',
            'clips_generated': len(saved_clips),
            'clips': saved_clips,
            'metadata': metadata.to_dict(),
            'processing_time': time.time() - progress_tracker.start_time,
            'is_long_video': is_long_video,
            'total_chunks_processed': progress_tracker.completed_chunks,
            'peak_memory_usage_mb': progress_tracker.memory_usage
        }
        
        logger.info(
            f"Video processing completed: {len(saved_clips)} clips generated "
            f"in {final_result['processing_time']:.1f}s "
            f"(Long video: {is_long_video}, Peak memory: {progress_tracker.memory_usage:.1f}MB)"
        )
        
        return final_result
        
    except Exception as e:
        # Create error tracker if progress_tracker doesn't exist
        if 'progress_tracker' not in locals():
            progress_tracker = ProgressTracker(task_id, video_id, 1)
        
        await progress_tracker.update_error(str(e))
        logger.error(f"Video processing failed: {e}")
        raise


class ProgressTracker:
    """Track and broadcast processing progress with enhanced support for long videos."""
    
    def __init__(self, task_id: str, video_id: str, total_chunks: int = 1):
        self.task_id = task_id
        self.video_id = video_id
        self.start_time = time.time()
        self.last_update = 0
        self.total_chunks = total_chunks
        self.completed_chunks = 0
        self.chunk_progress = {}  # Track progress per chunk
        self.memory_usage = 0
        self.estimated_completion = None
        
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            return 0.0
    
    def _estimate_completion_time(self, current_progress: float) -> float:
        """Estimate completion time based on current progress."""
        if current_progress <= 0:
            return 0.0
        
        elapsed_time = time.time() - self.start_time
        estimated_total_time = elapsed_time / (current_progress / 100)
        return max(0, estimated_total_time - elapsed_time)
    
    async def update(self, progress: float, message: str, chunk_id: str = None):
        """Update progress with enhanced tracking for long videos."""
        self.last_update = progress
        self.memory_usage = self._get_memory_usage()
        self.estimated_completion = self._estimate_completion_time(progress)
        
        # Track chunk-specific progress
        if chunk_id:
            self.chunk_progress[chunk_id] = progress
        
        # Calculate overall progress from chunks if available
        if self.chunk_progress:
            chunk_avg = sum(self.chunk_progress.values()) / len(self.chunk_progress)
            overall_progress = (self.completed_chunks / self.total_chunks) * 100
            overall_progress += (chunk_avg / self.total_chunks)
            progress = min(100, overall_progress)
        
        status_data = {
            'progress': progress,
            'message': message,
            'video_id': self.video_id,
            'timestamp': time.time(),
            'memory_usage_mb': self.memory_usage,
            'estimated_completion_seconds': self.estimated_completion,
            'total_chunks': self.total_chunks,
            'completed_chunks': self.completed_chunks,
            'chunk_progress': self.chunk_progress
        }
        
        # Update Redis cache
        await redis_service.set_processing_status(self.task_id, status_data)
        
        # Broadcast via WebSocket
        await websocket_service.broadcast_progress_update({
            'task_id': self.task_id,
            'video_id': self.video_id,
            'progress': progress,
            'message': message,
            'memory_usage_mb': self.memory_usage,
            'estimated_completion_seconds': self.estimated_completion,
            'chunk_info': {
                'total': self.total_chunks,
                'completed': self.completed_chunks,
                'current_progress': self.chunk_progress
            }
        })
        
        logger.info(
            f"Task {self.task_id}: {progress:.1f}% - {message} "
            f"(Memory: {self.memory_usage:.1f}MB, ETA: {self.estimated_completion:.0f}s)"
        )
    
    async def update_chunk_completed(self, chunk_id: str, message: str = None):
        """Mark a chunk as completed."""
        self.completed_chunks += 1
        if chunk_id in self.chunk_progress:
            self.chunk_progress[chunk_id] = 100
        
        progress = (self.completed_chunks / self.total_chunks) * 100
        default_message = f"Completed chunk {self.completed_chunks}/{self.total_chunks}"
        await self.update(progress, message or default_message, chunk_id)
    
    async def update_processing(self, progress: float, message: str, chunk_id: str = None):
        """Update processing progress (70-90% range) with chunk support."""
        adjusted_progress = 70 + (progress * 0.2)  # Map 0-100% to 70-90%
        await self.update(adjusted_progress, message, chunk_id)
    
    async def update_error(self, error: str):
        """Update with error status."""
        await redis_service.set_processing_status(
            self.task_id,
            {
                'progress': self.last_update,
                'message': f"Error: {error}",
                'video_id': self.video_id,
                'status': 'failed',
                'error': error,
                'timestamp': time.time()
            }
        )
        
        await websocket_service.broadcast_progress_update({
            'task_id': self.task_id,
            'video_id': self.video_id,
            'progress': self.last_update,
            'message': f"Error: {error}",
            'status': 'failed'
        })


@celery_app.task(bind=True, base=BaseVideoTask, name='process_single_clip')
def process_single_clip_task(
    self,
    video_path: str,
    clip_segment: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a single clip segment (for distributed processing)."""
    
    task_id = self.request.id
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Convert dict back to objects
            segment = ClipSegment(**clip_segment)
            processing_config = ProcessingConfig(**config)
            
            # Process the clip
            result = loop.run_until_complete(
                enhanced_video_processor._process_single_chunk(
                    video_path,
                    segment,
                    processing_config,
                    None  # Metadata will be fetched if needed
                )
            )
            
            return result.to_dict() if hasattr(result, 'to_dict') else result
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Single clip processing task {task_id} failed: {e}")
        raise


async def _process_clips_distributed(
    video_path: str,
    clip_segments: List[ClipSegment],
    config: ProcessingConfig,
    progress_tracker: ProgressTracker
) -> List[ProcessingResult]:
    """Process clips using distributed Celery workers."""
    
    # Split segments into batches for different workers
    batch_size = 2  # Process 2 clips per worker
    batches = [clip_segments[i:i + batch_size] for i in range(0, len(clip_segments), batch_size)]
    
    # Submit tasks to different workers
    async_results = []
    for batch in batches:
        for segment in batch:
            async_result = process_single_clip_task.delay(
                video_path,
                segment.to_dict(),
                config.to_dict()
            )
            async_results.append(async_result)
    
    # Wait for results with progress tracking
    results = []
    completed = 0
    
    for async_result in async_results:
        try:
            # Wait for result with timeout
            result_dict = async_result.get(timeout=600)  # 10 minutes
            results.append(ProcessingResult(**result_dict))
            
            completed += 1
            progress = (completed / len(async_results)) * 100
            await progress_tracker.update_processing(
                progress, f"Completed {completed}/{len(async_results)} clips"
            )
            
        except Exception as e:
            logger.error(f"Distributed clip processing failed: {e}")
            # Continue with other clips
            continue
    
    logger.info(f"Distributed processing completed: {len(results)}/{len(async_results)} clips")
    return results


async def _validate_processing_inputs(
    video_id: str,
    video_path: str,
    generation_options: Dict[str, Any]
):
    """Validate processing inputs."""
    
    if not video_id:
        raise ValidationError("Video ID is required")
    
    if not os.path.exists(video_path):
        raise ValidationError(f"Video file not found: {video_path}")
    
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        raise ValidationError("Video file is empty")
    
    # Check file size limit (e.g., 2GB)
    max_size = 2 * 1024 * 1024 * 1024  # 2GB
    if file_size > max_size:
        raise ValidationError(f"Video file too large: {file_size / 1024 / 1024:.1f}MB > {max_size / 1024 / 1024:.1f}MB")
    
    # Validate generation options
    required_options = ['platform', 'clip_type']
    for option in required_options:
        if option not in generation_options:
            raise ValidationError(f"Missing required option: {option}")


def _convert_moments_to_segments(
    content_moments: List[Any],
    generation_options: Dict[str, Any]
) -> List[ClipSegment]:
    """Convert content moments to clip segments."""
    
    segments = []
    
    for i, moment in enumerate(content_moments):
        segment = ClipSegment(
            clip_id=f"clip_{i+1}",
            start_time=moment.start_time,
            end_time=moment.end_time,
            title=moment.description[:50],  # Truncate title
            description=moment.description,
            tags=moment.keywords,
            virality_score=moment.virality_score.overall_score
        )
        segments.append(segment)
    
    return segments


def _create_processing_config(
    generation_options: Dict[str, Any],
    metadata: Any
) -> ProcessingConfig:
    """Create processing configuration."""
    
    platform = generation_options.get('platform', 'general')
    
    # Platform-specific configurations
    platform_configs = {
        'tiktok': {
            'width': 1080, 'height': 1920, 'fps': 30,
            'bitrate': 2500, 'max_duration': 180
        },
        'youtube': {
            'width': 1920, 'height': 1080, 'fps': 30,
            'bitrate': 5000, 'max_duration': 600
        },
        'instagram': {
            'width': 1080, 'height': 1080, 'fps': 30,
            'bitrate': 3500, 'max_duration': 90
        },
        'twitter': {
            'width': 1280, 'height': 720, 'fps': 30,
            'bitrate': 2000, 'max_duration': 140
        },
        'general': {
            'width': 1920, 'height': 1080, 'fps': 30,
            'bitrate': 4000, 'max_duration': 300
        }
    }
    
    config_data = platform_configs.get(platform, platform_configs['general'])
    
    return ProcessingConfig(
        width=config_data['width'],
        height=config_data['height'],
        fps=config_data['fps'],
        bitrate=config_data['bitrate'],
        codec='h264',
        audio_codec='aac',
        format='mp4'
    )


async def _save_processing_results(
    video_id: str,
    results: List[ProcessingResult],
    generation_options: Dict[str, Any],
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Save processing results to database."""
    
    saved_clips = []
    
    for result in results:
        if result.status == ProcessingStatus.COMPLETED:
            try:
                # Save clip to database
                clip_data = await supabase_circuit_breaker.call(
                    supabase_service.save_generated_clip,
                    {
                        'video_id': video_id,
                        'clip_id': result.clip_id,
                        'file_path': result.output_path,
                        'file_size': result.file_size,
                        'duration': result.duration,
                        'processing_time': result.processing_time,
                        'platform': generation_options.get('platform'),
                        'clip_type': generation_options.get('clip_type'),
                        'user_id': user_id,
                        'status': 'completed'
                    }
                )
                
                saved_clips.append(clip_data)
                
            except Exception as e:
                logger.error(f"Failed to save clip {result.clip_id}: {e}")
                continue
    
    return saved_clips


# Celery signal handlers
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task prerun."""
    logger.info(f"Task {task_id} starting: {task.name}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Handle task postrun."""
    logger.info(f"Task {task_id} finished: {state}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Handle task failure."""
    logger.error(f"Task {task_id} failed: {exception}")


def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get the status of a Celery task."""
    try:
        # Get task result from Celery
        result = celery_app.AsyncResult(task_id)
        
        # Get additional info from Redis if available
        additional_info = {}
        if redis_service and redis_service.health_check():
            try:
                task_key = f"task:{task_id}"
                cached_info = redis_service.get(task_key)
                if cached_info:
                    additional_info = json.loads(cached_info)
            except Exception as e:
                logger.warning(f"Failed to get additional task info from Redis: {e}")
        
        return {
            'task_id': task_id,
            'status': result.status,
            'result': result.result if result.ready() else None,
            'traceback': result.traceback if result.failed() else None,
            'progress': additional_info.get('progress', 0),
            'message': additional_info.get('message', ''),
            'created_at': additional_info.get('created_at'),
            'updated_at': additional_info.get('updated_at')
        }
        
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {e}")
        return {
            'task_id': task_id,
            'status': 'UNKNOWN',
            'error': str(e)
        }


# Health check task
@celery_app.task(name='health_check')
def health_check_task() -> Dict[str, Any]:
    """Health check task for monitoring."""
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Check video processor
            video_health = loop.run_until_complete(
                enhanced_video_processor.health_check()
            )
            
            # Check AI service
            ai_health = loop.run_until_complete(
                ai_service.health_check()
            )
            
            # Check Redis
            redis_health = loop.run_until_complete(
                redis_service.health_check()
            )
            
            return {
                'status': 'healthy',
                'timestamp': time.time(),
                'services': {
                    'video_processor': video_health,
                    'ai_service': ai_health,
                    'redis': redis_health
                }
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.time()
        }