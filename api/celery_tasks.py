from celery import current_task
from celery.exceptions import Retry
import asyncio
import os
import gc
import psutil
import time
import logging
from typing import Dict, List, Any, Optional
import tempfile
import shutil
from datetime import datetime, timedelta

from .celery_app import celery_app
from .services.supabase_service import SupabaseService
from .services.websocket_service import WebSocketService
from .services.video_processor import VideoProcessor
from .services.llm_service import LLMService
from .tasks import _generate_single_clip, _determine_clip_segments
from .utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)

# Initialize services
supabase_service = SupabaseService()
websocket_service = WebSocketService()
redis_cache = RedisCache()

@celery_app.task(bind=True, max_retries=3)
def process_video_clips(self, clip_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main Celery task for processing video clips with distributed processing.
    
    Args:
        clip_data: Dictionary containing clip processing parameters
        
    Returns:
        Dictionary with processing results
    """
    task_id = self.request.id
    clip_id = clip_data.get('clip_id')
    
    try:
        logger.info(f"Starting clip processing task {task_id} for clip {clip_id}")
        
        # Update task status
        current_task.update_state(
            state='PROGRESS',
            meta={'progress': 0, 'step': 'Initializing'}
        )
        
        # Memory check before starting
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 80:
            logger.warning(f"High memory usage ({memory_usage}%) before starting task")
            gc.collect()
            
        # Initialize services
        video_processor = VideoProcessor()
        llm_service = LLMService()
        
        # Update progress
        current_task.update_state(
            state='PROGRESS',
            meta={'progress': 10, 'step': 'Services initialized'}
        )
        
        # Process the video clips
        result = asyncio.run(_process_clips_async(
            clip_data=clip_data,
            video_processor=video_processor,
            llm_service=llm_service,
            task_id=task_id
        ))
        
        logger.info(f"Completed clip processing task {task_id} for clip {clip_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Error in clip processing task {task_id}: {exc}")
        
        # Update clip status to failed
        if clip_id:
            asyncio.run(supabase_service.update_clip_status(
                clip_id=clip_id,
                status="failed",
                error_message=str(exc)
            ))
            
        # Retry logic with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60  # Exponential backoff
            logger.info(f"Retrying task {task_id} in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay, exc=exc)
        else:
            raise exc

async def _process_clips_async(
    clip_data: Dict[str, Any],
    video_processor: VideoProcessor,
    llm_service: LLMService,
    task_id: str
) -> Dict[str, Any]:
    """
    Async function to process clips with enhanced error handling and monitoring.
    """
    clip_id = clip_data['clip_id']
    video_path = clip_data['video_path']
    generation_options = clip_data['generation_options']
    
    try:
        # Update status to processing
        await supabase_service.update_clip_status(
            clip_id=clip_id,
            status="processing",
            progress=15,
            current_step="Starting video analysis"
        )
        
        # Check for cached transcription
        cache_key = f"transcription:{os.path.basename(video_path)}"
        cached_transcription = await redis_cache.get(cache_key)
        
        if cached_transcription:
            logger.info(f"Using cached transcription for {video_path}")
            transcription_result = cached_transcription
        else:
            # Perform transcription
            current_task.update_state(
                state='PROGRESS',
                meta={'progress': 20, 'step': 'Transcribing audio'}
            )
            
            transcription_result = await video_processor.transcribe_audio(
                video_path=video_path,
                priority='accuracy'  # Use high accuracy for better results
            )
            
            # Cache the transcription result
            await redis_cache.set(cache_key, transcription_result, expire=3600)  # 1 hour cache
        
        # Update progress
        await supabase_service.update_clip_status(
            clip_id=clip_id,
            status="processing",
            progress=40,
            current_step="Analyzing content for optimal clips"
        )
        
        # Determine clip segments using AI
        clip_segments = await _determine_clip_segments(
            video_path=video_path,
            analysis_results={
                'transcription': transcription_result,
                'virality_scores': await _calculate_virality_scores(
                    transcription_result, llm_service
                )
            },
            generation_options=generation_options,
            video_processor=video_processor
        )
        
        # Update progress
        await supabase_service.update_clip_status(
            clip_id=clip_id,
            status="processing",
            progress=50,
            current_step=f"Generating {len(clip_segments)} clips"
        )
        
        # Process clips in chunks to manage memory
        chunk_size = 2  # Process 2 clips at a time
        generated_clips = []
        
        for i in range(0, len(clip_segments), chunk_size):
            chunk = clip_segments[i:i + chunk_size]
            
            # Process chunk
            chunk_results = await _process_clip_chunk(
                video_path=video_path,
                segments=chunk,
                clip_id=clip_id,
                generation_options=generation_options,
                chunk_index=i // chunk_size,
                total_chunks=(len(clip_segments) + chunk_size - 1) // chunk_size
            )
            
            generated_clips.extend(chunk_results)
            
            # Memory cleanup between chunks
            gc.collect()
            await asyncio.sleep(1)  # Brief pause
        
        # Finalize results
        await supabase_service.update_clip_status(
            clip_id=clip_id,
            status="completed",
            progress=100,
            current_step="Clips generated successfully"
        )
        
        return {
            'status': 'completed',
            'clips': generated_clips,
            'total_clips': len(generated_clips),
            'task_id': task_id
        }
        
    except Exception as e:
        logger.error(f"Error in async clip processing: {e}")
        raise

async def _process_clip_chunk(
    video_path: str,
    segments: List[Dict],
    clip_id: str,
    generation_options: Dict,
    chunk_index: int,
    total_chunks: int
) -> List[Dict]:
    """
    Process a chunk of clip segments.
    """
    results = []
    platform_config = generation_options.get('platform_config', {})
    
    # Create temporary directory for this chunk
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, segment in enumerate(segments):
            try:
                # Memory check
                memory_usage = psutil.virtual_memory().percent
                if memory_usage > 85:
                    logger.warning(f"High memory usage ({memory_usage}%), forcing cleanup")
                    gc.collect()
                    await asyncio.sleep(2)
                
                # Generate output path
                output_filename = f"clip_{chunk_index}_{i}_{clip_id}.{platform_config.get('format', 'mp4')}"
                output_path = os.path.join(temp_dir, output_filename)
                
                # Update progress
                progress = 50 + ((chunk_index * len(segments) + i) / (total_chunks * len(segments))) * 40
                await supabase_service.update_clip_status(
                    clip_id=clip_id,
                    status="processing",
                    progress=int(progress),
                    current_step=f"Processing chunk {chunk_index + 1}/{total_chunks}, clip {i + 1}/{len(segments)}"
                )
                
                # Generate clip
                clip_path = await _generate_single_clip(
                    video_path=video_path,
                    output_path=output_path,
                    segment=segment,
                    platform_config=platform_config
                )
                
                if clip_path and os.path.exists(clip_path):
                    # Move to permanent location
                    permanent_dir = os.path.join(os.path.dirname(video_path), 'clips')
                    os.makedirs(permanent_dir, exist_ok=True)
                    
                    permanent_path = os.path.join(permanent_dir, output_filename)
                    shutil.move(clip_path, permanent_path)
                    
                    results.append({
                        'file_path': permanent_path,
                        'segment': segment,
                        'duration': segment['duration'],
                        'file_size': os.path.getsize(permanent_path)
                    })
                    
                    logger.info(f"Generated clip: {permanent_path}")
                
            except Exception as e:
                logger.error(f"Error processing segment {i} in chunk {chunk_index}: {e}")
                continue
    
    return results

async def _calculate_virality_scores(transcription_result: Dict, llm_service: LLMService) -> List[Dict]:
    """
    Calculate virality scores for transcription segments using AI analysis.
    """
    try:
        if not transcription_result or 'segments' not in transcription_result:
            return []
        
        segments = transcription_result['segments']
        virality_scores = []
        
        # Analyze segments in batches
        batch_size = 10
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            
            # Create prompt for virality analysis
            texts = [seg.get('text', '') for seg in batch]
            prompt = f"""
            Analyze the following video transcript segments for viral potential.
            Rate each segment from 0-100 based on:
            - Emotional impact
            - Surprise factor
            - Relatability
            - Shareability
            - Entertainment value
            
            Segments:
            {chr(10).join([f"{j+1}. {text}" for j, text in enumerate(texts)])}
            
            Return JSON array with scores: [{"segment_index": 0, "score": 85, "reason": "High emotional impact"}]
            """
            
            try:
                response = await llm_service.generate_response(prompt)
                batch_scores = response.get('scores', [])
                
                for j, score_data in enumerate(batch_scores):
                    if j < len(batch):
                        virality_scores.append({
                            'start_time': batch[j].get('start', 0),
                            'end_time': batch[j].get('end', 0),
                            'score': score_data.get('score', 50),
                            'reason': score_data.get('reason', 'No analysis')
                        })
                        
            except Exception as e:
                logger.error(f"Error analyzing batch {i//batch_size}: {e}")
                # Fallback scores
                for j, segment in enumerate(batch):
                    virality_scores.append({
                        'start_time': segment.get('start', 0),
                        'end_time': segment.get('end', 0),
                        'score': 50,  # Default score
                        'reason': 'Analysis failed'
                    })
        
        return virality_scores
        
    except Exception as e:
        logger.error(f"Error calculating virality scores: {e}")
        return []

@celery_app.task
def transcribe_video(video_path: str, priority: str = 'speed') -> Dict[str, Any]:
    """
    Dedicated task for video transcription.
    """
    try:
        video_processor = VideoProcessor()
        result = asyncio.run(video_processor.transcribe_audio(
            video_path=video_path,
            priority=priority
        ))
        return result
    except Exception as e:
        logger.error(f"Error in transcription task: {e}")
        raise

@celery_app.task
def analyze_virality(transcription_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Dedicated task for virality analysis.
    """
    try:
        llm_service = LLMService()
        result = asyncio.run(_calculate_virality_scores(transcription_data, llm_service))
        return result
    except Exception as e:
        logger.error(f"Error in virality analysis task: {e}")
        raise

@celery_app.task
def cleanup_temp_files() -> Dict[str, Any]:
    """
    Periodic task to clean up temporary files.
    """
    try:
        temp_dirs = ['/tmp', tempfile.gettempdir()]
        cleaned_files = 0
        cleaned_size = 0
        
        for temp_dir in temp_dirs:
            if not os.path.exists(temp_dir):
                continue
                
            cutoff_time = time.time() - (24 * 3600)  # 24 hours ago
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.startswith('clip_') or file.startswith('temp_'):
                        file_path = os.path.join(root, file)
                        try:
                            if os.path.getmtime(file_path) < cutoff_time:
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                cleaned_files += 1
                                cleaned_size += file_size
                        except Exception as e:
                            logger.warning(f"Could not clean file {file_path}: {e}")
        
        logger.info(f"Cleaned {cleaned_files} files, freed {cleaned_size} bytes")
        return {
            'cleaned_files': cleaned_files,
            'cleaned_size': cleaned_size
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")
        raise

@celery_app.task
def health_check() -> Dict[str, Any]:
    """
    Health check task for monitoring system status.
    """
    try:
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=1)
        disk_usage = psutil.disk_usage('/').percent
        
        status = {
            'timestamp': datetime.utcnow().isoformat(),
            'memory_usage': memory_usage,
            'cpu_usage': cpu_usage,
            'disk_usage': disk_usage,
            'status': 'healthy' if memory_usage < 80 and cpu_usage < 80 else 'warning'
        }
        
        logger.info(f"Health check: {status}")
        return status
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {'status': 'error', 'error': str(e)}