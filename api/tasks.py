import os
import shutil
import asyncio
import time
import traceback
import gc
import psutil
import subprocess
import glob
from pathlib import Path
from celery import Celery
from celery.utils.log import get_task_logger
from celery.exceptions import Retry, WorkerLostError
import yt_dlp
from functools import wraps
from typing import Optional, Dict, Any, List
import json
import sys
import logging
from pathlib import Path

from .services.video_processor import VideoProcessor
from .services.llm_service import LLMService
# Import supabase_service for database operations
from .services.supabase_service import supabase_service
from .celery_app import celery_app

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/tasks.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = get_task_logger(__name__)

# Ensure logs directory exists
Path('logs').mkdir(exist_ok=True)

# Configuration
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads")
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds
TASK_TIMEOUT = 3600  # 60 minutes (increased for large file processing)
STUCK_TASK_THRESHOLD = 1800  # 30 minutes

def with_error_recovery(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY):
    """Enhanced decorator for adding error recovery and retry logic to tasks with system monitoring"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Handle both bound and unbound task calls
            if args and hasattr(args[0], 'request'):
                # This is a bound Celery task, first arg is self
                self = args[0]
                task_args = args[1:]
            else:
                # This shouldn't happen with bound tasks, but handle gracefully
                self = None
                task_args = args
            # Extract job_id from different possible locations
            job_id = None
            if task_args:
                # For generate_clips_task, first arg is clip_id, second is video_id
                if len(task_args) >= 2:
                    job_id = task_args[1]  # video_id as job_id for generate_clips_task
                else:
                    job_id = task_args[0]  # fallback to first arg
            else:
                # Try to get from kwargs
                job_id = kwargs.get('job_id') or kwargs.get('video_id') or kwargs.get('clip_id', 'unknown')
            
            # Log task start with system info
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent
            logger.info(f"Starting task {func.__name__} with job_id: {job_id} (Memory: {memory_percent:.1f}%, Disk: {disk_percent:.1f}%)")
            logger.debug(f"Task args: {task_args}, kwargs: {kwargs}")
            
            for attempt in range(max_retries + 1):
                try:
                    # Enhanced system checks before task execution
                    current_memory = psutil.virtual_memory().percent
                    if current_memory > 85:  # High memory usage
                        logger.warning(f"High memory usage detected: {current_memory:.1f}%. Forcing garbage collection.")
                        gc.collect()
                        time.sleep(2)  # Brief pause for cleanup
                    
                    # Check if task has been running too long
                    if self and hasattr(self, 'request') and self.request.id:
                        task_start_time = getattr(self.request, 'eta', None) or time.time()
                        if time.time() - task_start_time > STUCK_TASK_THRESHOLD:
                            logger.warning(f"Task {self.request.id} has been running for too long, forcing restart")
                            raise Exception("Task timeout - forcing restart")
                    
                    # Check disk space
                    current_disk = psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent
                    if current_disk > 90:  # Low disk space
                        logger.error(f"Low disk space: {current_disk:.1f}%. Cleaning up temporary files.")
                        cleanup_job_resources(job_id)
                        raise Exception(f"Insufficient disk space: {current_disk:.1f}% used")
                    
                    # Call the original function with the correct arguments
                    if self is not None:
                        result = func(self, *task_args, **kwargs)
                    else:
                        result = func(*task_args, **kwargs)
                    logger.info(f"Task {func.__name__} completed successfully for job_id: {job_id}")
                    
                    # Log final system state
                    final_memory = psutil.virtual_memory().percent
                    logger.debug(f"Task completion - Memory: {final_memory:.1f}% (change: {final_memory - memory_percent:+.1f}%)")
                    
                    return result
                    
                except (ConnectionError, TimeoutError, WorkerLostError, MemoryError) as e:
                    if attempt < max_retries:
                        # Enhanced error handling with specific recovery strategies
                        error_type = type(e).__name__
                        logger.warning(f"Attempt {attempt + 1} failed for job {job_id} ({error_type}): {str(e)}. Retrying in {retry_delay} seconds...")
                        logger.debug(f"Full traceback: {traceback.format_exc()}")
                        
                        # Specific recovery actions based on error type
                        if isinstance(e, MemoryError):
                            logger.warning("Memory error detected. Performing aggressive cleanup.")
                            gc.collect()
                            cleanup_job_resources(job_id)  # Clean up any partial files
                            time.sleep(5)  # Longer pause for memory recovery
                        elif isinstance(e, (ConnectionError, TimeoutError)):
                            logger.warning("Network/timeout error detected. Checking system resources.")
                            # Brief system check
                            current_memory = psutil.virtual_memory().percent
                            if current_memory > 80:
                                gc.collect()
                        
                        # Update job status to indicate retry with error context
                        if job_id:
                            try:
                                asyncio.run(supabase_service.update_job_status(
                                    job_id, 
                                    status="analyzing", 
                                    progress=0, 
                                    current_step=f"Retrying after {error_type}... (attempt {attempt + 2}/{max_retries + 1})"
                                ))
                            except Exception as db_error:
                                logger.error(f"Failed to update job status during retry: {db_error}")
                        
                        # Exponential backoff for retries
                        backoff_delay = retry_delay * (2 ** attempt)
                        logger.info(f"Retrying task {func.__name__} for job_id {job_id} in {backoff_delay} seconds...")
                        time.sleep(backoff_delay)
                        continue
                    else:
                        error_msg = f"All retry attempts failed for job {job_id} ({type(e).__name__}): {str(e)}"
                        logger.error(f"Task {func.__name__} failed permanently for job_id {job_id}: {error_msg}")
                        
                        # Final cleanup on permanent failure
                        cleanup_job_resources(job_id)
                        
                        # Update job status to failed with detailed error info
                        if job_id:
                            try:
                                asyncio.run(supabase_service.update_job_status(
                                    job_id, 
                                    status="failed", 
                                    progress=0, 
                                    current_step=f"Failed after {max_retries + 1} attempts"
                                ))
                            except Exception as db_error:
                                logger.error(f"Failed to update job status on permanent failure: {db_error}")
                        
                        raise e
                        
                except Exception as e:
                    # Enhanced handling for other exceptions with detailed system diagnostics
                    error_type = type(e).__name__
                    error_msg = f"Non-retryable error ({error_type}) for job {job_id}: {str(e)}"
                    logger.error(f"Task {func.__name__} failed for job_id {job_id}: {error_msg}")
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    
                    # Comprehensive system diagnostics for debugging
                    try:
                        memory_info = psutil.virtual_memory()
                        disk_info = psutil.disk_usage('/') if os.name != 'nt' else psutil.disk_usage('C:\\')
                        cpu_percent = psutil.cpu_percent(interval=1)
                        
                        logger.error(
                            f"System diagnostics at failure - "
                            f"Memory: {memory_info.percent:.1f}% ({memory_info.available / (1024**3):.1f}GB available), "
                            f"Disk: {disk_info.percent:.1f}% ({disk_info.free / (1024**3):.1f}GB free), "
                            f"CPU: {cpu_percent:.1f}%"
                        )
                        
                        # Check for specific error patterns that might indicate system issues
                        error_str = str(e).lower()
                        if 'memory' in error_str or 'out of memory' in error_str:
                            logger.error("Memory-related error detected. Consider reducing batch sizes or enabling swap.")
                        elif 'disk' in error_str or 'no space' in error_str:
                            logger.error("Disk space error detected. Clean up temporary files and check available storage.")
                        elif 'permission' in error_str or 'access' in error_str:
                            logger.error("Permission error detected. Check file/directory permissions.")
                        elif 'timeout' in error_str or 'connection' in error_str:
                            logger.error("Network/timeout error detected. Check network connectivity and service availability.")
                            
                    except Exception as diag_error:
                        logger.warning(f"Failed to collect system diagnostics: {diag_error}")
                    
                    # Update job status with detailed error information
                    if job_id:
                        try:
                            asyncio.run(supabase_service.update_job_status(
                                job_id, 
                                status="failed", 
                                progress=0, 
                                current_step=f"Critical error: {error_type}"
                            ))
                        except Exception as db_error:
                            logger.error(f"Failed to update job status on critical failure: {db_error}")
                    
                    # Cleanup resources on critical failure
                    cleanup_job_resources(job_id)
                    
                    raise e
                    
            return None
        return wrapper
    return decorator

def cleanup_job_resources(job_id: str, aggressive: bool = False):
    """Enhanced cleanup of all resources associated with a job"""
    try:
        cleaned_dirs = []
        total_size_freed = 0
        
        # Define directories to clean
        directories_to_clean = [
            os.path.join(UPLOADS_DIR, "uploads", job_id),
            os.path.join(UPLOADS_DIR, "downloads", job_id),
            os.path.join(UPLOADS_DIR, "clips", job_id),
            os.path.join(UPLOADS_DIR, "temp", job_id),  # Additional temp directory
        ]
        
        for directory in directories_to_clean:
            if os.path.exists(directory):
                try:
                    # Calculate directory size before deletion
                    dir_size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, dirnames, filenames in os.walk(directory)
                        for filename in filenames
                    )
                    
                    # Force remove with retry logic
                    for attempt in range(3):
                        try:
                            shutil.rmtree(directory)
                            cleaned_dirs.append(os.path.basename(os.path.dirname(directory)))
                            total_size_freed += dir_size
                            break
                        except PermissionError as pe:
                            if attempt < 2:  # Retry up to 3 times
                                logger.warning(f"Permission error cleaning {directory}, retrying in 1 second...")
                                time.sleep(1)
                                continue
                            else:
                                logger.error(f"Failed to clean {directory} after 3 attempts: {pe}")
                        except Exception as cleanup_error:
                            logger.error(f"Error cleaning directory {directory}: {cleanup_error}")
                            break
                            
                except Exception as size_error:
                    logger.debug(f"Could not calculate size for {directory}: {size_error}")
                    # Still try to clean even if size calculation fails
                    try:
                        shutil.rmtree(directory)
                        cleaned_dirs.append(os.path.basename(os.path.dirname(directory)))
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning directory {directory}: {cleanup_error}")
        
        # Aggressive cleanup mode - clean up any orphaned temp files
        if aggressive:
            try:
                temp_patterns = [
                    f"*{job_id}*",
                    f"chunk_{job_id}_*",
                    f"temp_{job_id}_*"
                ]
                
                import glob
                import tempfile
                
                # Clean system temp directory
                system_temp = tempfile.gettempdir()
                for pattern in temp_patterns:
                    temp_files = glob.glob(os.path.join(system_temp, pattern))
                    for temp_file in temp_files:
                        try:
                            if os.path.isfile(temp_file):
                                file_size = os.path.getsize(temp_file)
                                os.remove(temp_file)
                                total_size_freed += file_size
                                logger.debug(f"Removed orphaned temp file: {temp_file}")
                            elif os.path.isdir(temp_file):
                                shutil.rmtree(temp_file)
                                logger.debug(f"Removed orphaned temp directory: {temp_file}")
                        except Exception as temp_cleanup_error:
                            logger.debug(f"Could not clean temp file {temp_file}: {temp_cleanup_error}")
                            
            except Exception as aggressive_cleanup_error:
                logger.warning(f"Aggressive cleanup failed: {aggressive_cleanup_error}")
        
        # Force garbage collection after cleanup
        gc.collect()
        
        if cleaned_dirs:
            size_mb = total_size_freed / (1024 * 1024)
            logger.info(f"Cleaned up {len(cleaned_dirs)} directories for job {job_id}: {cleaned_dirs} (freed {size_mb:.1f}MB)")
        else:
            logger.debug(f"No directories found to clean for job {job_id}")
            
    except Exception as e:
        logger.error(f"Error during resource cleanup for job {job_id}: {str(e)}")
        logger.debug(f"Cleanup traceback: {traceback.format_exc()}")

def check_disk_space_requirements(file_size: int, job_id: str) -> bool:
    """Check if there's enough disk space for processing"""
    try:
        # Estimate space needed: original file + temp files + output (roughly 3x file size)
        estimated_space_needed = file_size * 3
        
        # Add 1GB buffer for safety
        buffer_space = 1024 * 1024 * 1024  # 1GB
        total_space_needed = estimated_space_needed + buffer_space
        
        # Check disk space
        disk = psutil.disk_usage('/') if os.name != 'nt' else psutil.disk_usage('C:\\')
        available_space = disk.free
        
        if available_space < total_space_needed:
            space_needed_gb = total_space_needed / (1024**3)
            space_available_gb = available_space / (1024**3)
            logger.error(f"Insufficient disk space for job {job_id}: need {space_needed_gb:.1f}GB, have {space_available_gb:.1f}GB")
            return False
            
        logger.info(f"Disk space check passed for job {job_id}: {available_space / (1024**3):.1f}GB available, {total_space_needed / (1024**3):.1f}GB needed")
        return True
        
    except Exception as e:
        logger.warning(f"Disk space check failed for job {job_id}: {e}")
        return True  # Allow processing if check fails

def check_system_health() -> Dict[str, Any]:
    """Comprehensive system health check"""
    try:
        # Memory information
        memory = psutil.virtual_memory()
        
        # Disk information
        disk = psutil.disk_usage('/') if os.name != 'nt' else psutil.disk_usage('C:\\')
        
        # CPU information
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Process information
        current_process = psutil.Process()
        process_memory = current_process.memory_info()
        
        health_status = {
            "memory": {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent_used": memory.percent,
                "status": "critical" if memory.percent > 90 else "warning" if memory.percent > 80 else "good"
            },
            "disk": {
                "total_gb": disk.total / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent_used": disk.percent,
                "status": "critical" if disk.percent > 95 else "warning" if disk.percent > 85 else "good"
            },
            "cpu": {
                "percent_used": cpu_percent,
                "core_count": cpu_count,
                "status": "critical" if cpu_percent > 95 else "warning" if cpu_percent > 80 else "good"
            },
            "process": {
                "memory_mb": process_memory.rss / (1024**2),
                "memory_percent": current_process.memory_percent(),
            },
            "overall_status": "good"
        }
        
        # Determine overall status
        critical_components = [comp for comp in ["memory", "disk", "cpu"] 
                             if health_status[comp]["status"] == "critical"]
        warning_components = [comp for comp in ["memory", "disk", "cpu"] 
                            if health_status[comp]["status"] == "warning"]
        
        if critical_components:
            health_status["overall_status"] = "critical"
            health_status["issues"] = f"Critical: {', '.join(critical_components)}"
        elif warning_components:
            health_status["overall_status"] = "warning"
            health_status["issues"] = f"Warning: {', '.join(warning_components)}"
        
        return health_status
        
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return {
            "overall_status": "unknown",
            "error": str(e)
        }

def handle_task_failure(job_id: str, error: Exception, cleanup: bool = True):
    """Handle task failure with proper cleanup and status update"""
    try:
        error_message = str(error)
        logger.error(f"Task failed for job {job_id}: {error_message}")
        
        # Update job status to failed
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="failed", 
            progress=0, 
            current_step=f"Error: {error_message[:80]}"
        ))
        
        # Broadcast failure update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="failed",
                progress=0,
                current_step=f"Error: {error_message[:80]}",
                additional_data={"error": error_message}
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket failure update for job {job_id}: {ws_error}")
        
        # Clean up resources if requested
        if cleanup:
            cleanup_job_resources(job_id)
            
    except Exception as cleanup_error:
        logger.error(f"Error during failure handling for job {job_id}: {str(cleanup_error)}")

async def handle_task_failure_async(job_id: str, error: Exception, cleanup: bool = True):
    """Async version of handle task failure with proper cleanup and status update"""
    try:
        error_message = str(error)
        logger.error(f"Task failed for job {job_id}: {error_message}")
        
        # Update job status to failed
        await supabase_service.update_job_status(
            job_id, 
            status="failed", 
            progress=0, 
            current_step=f"Error: {error_message[:80]}"
        )
        
        # Broadcast failure update via WebSocket
        try:
            from api.main import broadcast_job_update
            await broadcast_job_update(
                job_id=job_id,
                status="failed",
                progress=0,
                current_step=f"Error: {error_message[:80]}",
                additional_data={"error": error_message}
            )
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket failure update for job {job_id}: {ws_error}")
        
        # Clean up resources if requested
        if cleanup:
            cleanup_job_resources(job_id)
            
    except Exception as cleanup_error:
        logger.error(f"Error during failure handling for job {job_id}: {str(cleanup_error)}")

# Create uploads directory
os.makedirs(UPLOADS_DIR, exist_ok=True)

@celery_app.task(bind=True, soft_time_limit=TASK_TIMEOUT, time_limit=TASK_TIMEOUT + 300)
@with_error_recovery(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
def process_video_task(self, job_id: str, video_path: str, original_filename: str, file_size: int):
    """Process uploaded video file with enhanced error recovery and system monitoring"""
    
    # Task heartbeat mechanism to prevent timeout
    import threading
    import time
    
    heartbeat_active = threading.Event()
    heartbeat_active.set()
    
    def task_heartbeat():
        """Send periodic heartbeat updates every 5 minutes"""
        heartbeat_count = 0
        while heartbeat_active.is_set():
            try:
                time.sleep(300)  # 5 minutes
                if heartbeat_active.is_set():
                    heartbeat_count += 1
                    logger.info(f"Task heartbeat {heartbeat_count} for job {job_id} - task still active")
                    
                    # Send heartbeat update
                    try:
                        asyncio.run(supabase_service.update_job_status(
                            job_id, 
                            status="analyzing", 
                            progress=None,  # Don't update progress, just heartbeat
                            current_step=f"Processing continues... (heartbeat {heartbeat_count})"
                        ))
                    except Exception as heartbeat_error:
                        logger.warning(f"Heartbeat update failed for job {job_id}: {heartbeat_error}")
            except Exception as e:
                logger.warning(f"Heartbeat thread error for job {job_id}: {e}")
                break
    
    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=task_heartbeat, daemon=True)
    heartbeat_thread.start()
    try:
        # Initial system health check
        health_status = check_system_health()
        logger.info(f"Starting video processing task for job {job_id} (attempt {getattr(self.request, 'retries', 0) + 1})")
        logger.info(f"System health: {health_status['overall_status']} - Memory: {health_status.get('process', {}).get('memory_percent', 0):.1f}%, Disk: {health_status.get('disk', {}).get('percent_used', 0):.1f}%")
        
        # Check if system is in critical state
        if health_status['overall_status'] == 'critical':
            logger.warning(f"System in critical state: {health_status.get('issues', 'Unknown issues')}")
            # Perform aggressive cleanup before proceeding
            cleanup_job_resources(job_id, aggressive=True)
            gc.collect()
            time.sleep(2)
        
        # Validate input parameters
        if not job_id or not video_path:
            raise ValueError("Missing required parameters: job_id or video_path")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Check disk space requirements before processing
        if not check_disk_space_requirements(file_size, job_id):
            raise Exception("Insufficient disk space for video processing. Please free up disk space and try again.")
        
        # Dynamic file size limit based on available memory
        available_memory_gb = health_status.get('memory', {}).get('available_gb', 4.0)  # Default to 4GB
        max_file_size = min(2048 * 1024 * 1024, int(available_memory_gb * 0.5 * 1024 * 1024 * 1024))  # 50% of available memory or 2GB, whichever is smaller
        
        if file_size > max_file_size:
            raise ValueError(f"File too large: {file_size / (1024*1024):.1f}MB. Maximum allowed based on system resources: {max_file_size / (1024*1024):.1f}MB")
        
        # Update job status
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=10, 
            current_step="Initializing video processing"
        ))
        
        # Create video record
        video_data = {
            "job_id": job_id,
            "file_path": video_path,
            "original_filename": original_filename,
            "file_size": file_size
        }
        video_id = asyncio.run(supabase_service.create_video(video_data))
        
        # Initialize services with error handling
        try:
            video_processor = VideoProcessor()
            # Use unified LLM service (already initialized globally)
        except Exception as init_error:
            raise Exception(f"Failed to initialize services: {str(init_error)}")
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=20, 
            current_step="Processing video content"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=20,
                current_step="Processing video content"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Process video with timeout handling and system monitoring
        output_dir = os.path.join(UPLOADS_DIR, "clips", job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # Monitor system resources before intensive processing
        pre_processing_health = check_system_health()
        logger.debug(f"Pre-processing system state: Memory {pre_processing_health.get('process', {}).get('memory_percent', 0):.1f}%, CPU {pre_processing_health.get('cpu', {}).get('percent_used', 0):.1f}%")
        
        # Define progress callback for video processing
        def video_progress_callback(progress_percent: int, step_description: str):
            """Callback to update progress during video processing"""
            try:
                # Map video processing progress (0-100) to overall progress (20-50)
                overall_progress = 20 + int((progress_percent / 100) * 30)
                
                asyncio.run(supabase_service.update_job_status(
                    job_id, 
                    status="analyzing", 
                    progress=overall_progress, 
                    current_step=f"Video processing: {step_description}"
                ))
                
                # Broadcast progress update via WebSocket
                try:
                    from api.main import broadcast_job_update
                    asyncio.run(broadcast_job_update(
                        job_id=job_id,
                        status="analyzing",
                        progress=overall_progress,
                        current_step=f"Video processing: {step_description}"
                    ))
                except Exception as ws_error:
                    logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
                    
            except Exception as callback_error:
                logger.warning(f"Progress callback error for job {job_id}: {callback_error}")
        
        try:
            processing_result = video_processor.process_video(video_path, output_dir, progress_callback=video_progress_callback)
        except Exception as processing_error:
            # Check if processing failed due to system resources
            post_error_health = check_system_health()
            if post_error_health['overall_status'] == 'critical':
                logger.error(f"Video processing failed due to system resource constraints: {post_error_health.get('issues', '')}")
                # Attempt cleanup and retry once
                cleanup_job_resources(job_id, aggressive=True)
                gc.collect()
                time.sleep(5)
                
                # Single retry with reduced resource usage
                try:
                    logger.info(f"Retrying video processing with reduced resource usage for job {job_id}")
                    processing_result = video_processor.process_video(video_path, output_dir, progress_callback=video_progress_callback)
                except Exception as retry_error:
                    raise Exception(f"Video processing failed after resource cleanup retry: {str(retry_error)}")
            else:
                raise Exception(f"Video processing failed: {str(processing_error)}")
        
        if not processing_result.get("success", False):
            error_msg = processing_result.get('error', 'Unknown video processing error')
            raise Exception(f"Video processing failed: {error_msg}")
        
        # Monitor system resources after processing
        post_processing_health = check_system_health()
        memory_change = post_processing_health.get('process', {}).get('memory_percent', 0) - pre_processing_health.get('process', {}).get('memory_percent', 0)
        logger.debug(f"Post-processing system state: Memory {post_processing_health.get('process', {}).get('memory_percent', 0):.1f}% (change: {memory_change:+.1f}%)")
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=50, 
            current_step="Analyzing content for virality"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=50,
                current_step="Analyzing content for virality"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Analyze virality with error handling
        transcript = processing_result.get("transcript", "")
        video_features = processing_result.get("video_features", {})
        
        if not transcript:
            logger.warning(f"No transcript available for job {job_id}, using fallback")
            transcript = "[No transcript available]"
        
        try:
            # Initialize LLM service for this task
            llm_service = LLMService()
            virality_scores = asyncio.run(llm_service.analyze_virality(transcript))
        except Exception as virality_error:
            logger.error(f"Virality analysis failed: {virality_error}")
            # Use fallback scores
            from .services.llm_service import ViralityScore
            virality_scores = [
                ViralityScore(start_time=0, end_time=30, score=0.5, reason="Analysis unavailable due to processing error", content_type="general")
            ]
        
        # Get top content types for hashtag generation
        top_content_types = [score.content_type for score in sorted(virality_scores, key=lambda x: x.score, reverse=True)[:3]]
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=70, 
            current_step="Generating hashtags and recommendations"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=70,
                current_step="Generating hashtags and recommendations"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Generate hashtags and recommendations with error handling
        try:
            # For now, use simple hashtag generation based on content types
            hashtags = []
            for content_type in top_content_types[:3]:
                # Clean content_type for hashtag formatting
                clean_content_type = ''.join(c for c in content_type.lower() if c.isalnum())
                if clean_content_type:  # Only add if there's content left
                    hashtags.append({"tag": f"#{clean_content_type}", "platform": "general", "relevance_score": 0.8})
            hashtags.append({"tag": "#viral", "platform": "general", "relevance_score": 0.7})
        except Exception as hashtag_error:
            logger.error(f"Hashtag generation failed: {hashtag_error}")
            # Use fallback hashtags
            hashtags = [{"tag": "#video", "platform": "general", "relevance_score": 0.5}]
        
        try:
            # Simple recommendations based on content analysis
            recommendations = [{
                "platform": "general", 
                "optimal_times": ["12:00", "18:00"], 
                "format_suggestions": ["Short-form video", "Highlight reel"]
            }]
        except Exception as rec_error:
            logger.error(f"Recommendation generation failed: {rec_error}")
            # Use fallback recommendations
            recommendations = [{
                "platform": "general", 
                "optimal_times": ["12:00", "18:00"], 
                "format_suggestions": ["Standard post"]
            }]
        
        # Calculate overall virality score
        overall_score = sum(score.score for score in virality_scores) / len(virality_scores) if virality_scores else 0.5
        
        # Create clip record
        clip_data = {
            "job_id": job_id,
            "video_id": video_id,
            "file_path": processing_result.get("clip_path", ""),
            "start_time": processing_result.get("segment_info", {}).get("start_time", 0),
            "duration": processing_result.get("segment_info", {}).get("duration", 0),
            "transcript": transcript,
            "overall_virality_score": overall_score
        }
        
        clip_id = asyncio.run(supabase_service.create_clip(clip_data))
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=85, 
            current_step="Saving results"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=85,
                current_step="Saving results"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Save results with error handling
        try:
            # Save virality scores
            scores_data = [{
                "start_time": score.start_time,
                "end_time": score.end_time,
                "score": score.score,
                "reason": score.reason,
                "content_type": score.content_type
            } for score in virality_scores]
            
            asyncio.run(supabase_service.save_virality_scores(clip_id, scores_data))
            
            # Save hashtags
            hashtags_data = [{
                "tag": hashtag.tag,
                "platform": hashtag.platform,
                "relevance_score": hashtag.relevance_score
            } for hashtag in hashtags]
            
            asyncio.run(supabase_service.save_hashtags(clip_id, hashtags_data))
            
            # Save recommendations
            recommendations_data = [{
                "platform": rec.platform,
                "optimal_times": rec.optimal_times,
                "format_suggestions": rec.format_suggestions
            } for rec in recommendations]
            
            asyncio.run(supabase_service.save_posting_recommendations(clip_id, recommendations_data))
            
        except Exception as save_error:
            logger.error(f"Failed to save some results for job {job_id}: {save_error}")
            # Continue anyway as the main processing is done
        
        # Update job status to complete
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="complete", 
            progress=100, 
            current_step="Processing complete"
        ))
        
        # Broadcast completion update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="complete",
                progress=100,
                current_step="Processing complete",
                additional_data={
                    "clip_id": clip_id,
                    "overall_score": overall_score
                }
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket completion update for job {job_id}: {ws_error}")
        
        # Broadcast completion update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="complete",
                progress=100,
                current_step="Processing complete",
                additional_data={
                    "clip_id": clip_id,
                    "overall_score": overall_score
                }
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket completion update for job {job_id}: {ws_error}")
        
        logger.info(f"Video processing completed for job {job_id}")
        
        # Stop heartbeat thread
        heartbeat_active.clear()
        
        return {
            "status": "complete",
            "job_id": job_id,
            "clip_id": clip_id,
            "overall_score": overall_score
        }
        
    except Exception as e:
        # Stop heartbeat thread on error
        heartbeat_active.clear()
        logger.error(f"Video processing failed for job {job_id}: {str(e)}")
        handle_task_failure(job_id, e, cleanup=True)
        raise e
    finally:
        # Ensure heartbeat thread is stopped
        heartbeat_active.clear()

@celery_app.task(bind=True, soft_time_limit=TASK_TIMEOUT, time_limit=TASK_TIMEOUT + 300)
@with_error_recovery(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY)
def process_url_task(self, job_id: str, video_url: str):
    """Process video from URL (YouTube, etc.) with enhanced error recovery"""
    try:
        logger.info(f"Starting URL processing task for job {job_id} (attempt {getattr(self.request, 'retries', 0) + 1})")
        
        # Validate input parameters
        if not job_id or not video_url:
            raise ValueError("Missing required parameters: job_id or video_url")
        
        # Update job status
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=5, 
            current_step="Downloading video from URL"
        ))
        
        # Download video using yt-dlp
        download_dir = os.path.join(UPLOADS_DIR, "downloads", job_id)
        os.makedirs(download_dir, exist_ok=True)
        
        ydl_opts = {
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'format': 'best[height<=720]',  # Limit quality for faster processing
            'extractaudio': False,
            'audioformat': 'mp3',
            'embed_subs': True,
            'writesubtitles': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'ignoreerrors': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video info with timeout
                try:
                    info = ydl.extract_info(video_url, download=False)
                except Exception as info_error:
                    raise Exception(f"Failed to extract video information: {str(info_error)}")
                
                title = info.get('title', 'video')
                duration = info.get('duration', 0)
                
                # Check if video is too long (limit to 30 minutes)
                if duration and duration > 1800:  # 30 minutes
                    raise Exception(f"Video is too long ({duration//60} minutes). Please use videos under 30 minutes.")
                
                # Check file size estimate
                filesize = info.get('filesize') or info.get('filesize_approx')
                if filesize and filesize > 2048 * 1024 * 1024:  # 2GB
                    raise Exception(f"Video file too large ({filesize/(1024*1024):.1f}MB). Maximum allowed: 2GB")
                
                # Download the video with timeout handling
                try:
                    ydl.download([video_url])
                except Exception as download_error:
                    raise Exception(f"Failed to download video: {str(download_error)}")
                    
        except Exception as ydl_error:
            raise Exception(f"Video download failed: {str(ydl_error)}")
        
        # Find the downloaded file
        downloaded_files = list(Path(download_dir).glob('*'))
        video_files = [f for f in downloaded_files if f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.webm']]
        
        if not video_files:
            raise Exception("No video file found after download")
        
        video_path = str(video_files[0])
        file_size = os.path.getsize(video_path)
        original_filename = video_files[0].name
        
        # Validate downloaded file
        if not video_path or not os.path.exists(video_path):
            raise FileNotFoundError(f"Downloaded video file not found: {video_path}")
        
        # Validate file size (limit to 2GB)
        max_file_size = 2048 * 1024 * 1024  # 2GB
        if file_size > max_file_size:
            # Clean up downloaded file
            try:
                os.remove(video_path)
            except:
                pass
            raise ValueError(f"Downloaded file too large: {file_size / (1024*1024):.1f}MB. Maximum allowed: {max_file_size / (1024*1024):.1f}MB")
        
        logger.info(f"Video downloaded successfully for job {job_id}: {video_path} ({file_size / (1024*1024):.1f}MB)")
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=15, 
            current_step="Download complete, starting analysis"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=15,
                current_step="Download complete, starting analysis"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Create video record
        video_data = {
            "job_id": job_id,
            "file_path": video_path,
            "original_filename": original_filename,
            "file_size": file_size
        }
        video_id = asyncio.run(supabase_service.create_video(video_data))
        
        # Initialize services with error handling
        try:
            video_processor = VideoProcessor()
            # Use unified LLM service (already initialized globally)
        except Exception as init_error:
            raise Exception(f"Failed to initialize services: {str(init_error)}")
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=25, 
            current_step="Processing video content"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=25,
                current_step="Processing video content"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Process video with timeout handling
        output_dir = os.path.join(UPLOADS_DIR, "clips", job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            processing_result = video_processor.process_video(video_path, output_dir)
        except Exception as processing_error:
            raise Exception(f"Video processing failed: {str(processing_error)}")
        
        if not processing_result.get("success", False):
            error_msg = processing_result.get('error', 'Unknown video processing error')
            raise Exception(f"Video processing failed: {error_msg}")
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=55, 
            current_step="Analyzing content for virality"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=55,
                current_step="Analyzing content for virality"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Analyze virality with error handling
        transcript = processing_result.get("transcript", "")
        video_features = processing_result.get("video_features", {})
        
        if not transcript:
            logger.warning(f"No transcript available for job {job_id}, using fallback")
            transcript = "[No transcript available]"
        
        try:
            # Initialize LLM service for this task
            llm_service = LLMService()
            virality_scores = asyncio.run(llm_service.analyze_virality(transcript))
        except Exception as virality_error:
            logger.error(f"Virality analysis failed: {virality_error}")
            # Use fallback scores
            from .services.llm_service import ViralityScore
            virality_scores = [
                ViralityScore(start_time=0, end_time=30, score=0.5, reason="Analysis unavailable due to processing error", content_type="general")
            ]
        
        # Get top content types
        top_content_types = [score.content_type for score in sorted(virality_scores, key=lambda x: x.score, reverse=True)[:3]]
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=75, 
            current_step="Generating hashtags and recommendations"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=75,
                current_step="Generating hashtags and recommendations"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Generate hashtags and recommendations with simplified approach
        try:
            # Simplified hashtag generation based on content types
            hashtags = []
            for content_type in top_content_types[:3]:
                # Clean content_type for hashtag formatting
                clean_content_type = ''.join(c for c in content_type.lower() if c.isalnum())
                if clean_content_type:  # Only add if there's content left
                    hashtags.append({
                        "tag": f"#{clean_content_type}",
                        "platform": "general",
                        "relevance_score": 0.8
                    })
            # Add generic hashtags
            hashtags.extend([
                {"tag": "#viral", "platform": "general", "relevance_score": 0.7},
                {"tag": "#content", "platform": "general", "relevance_score": 0.6}
            ])
        except Exception as hashtag_error:
            logger.error(f"Hashtag generation failed: {hashtag_error}")
            hashtags = [{"tag": "#video", "platform": "general", "relevance_score": 0.5}]
        
        try:
            # Simplified recommendation generation
            recommendations = [{
                "platform": "general",
                "optimal_times": ["12:00", "18:00", "20:00"],
                "format_suggestions": {
                    "type": "Short-form content",
                    "description": f"Focus on {', '.join(top_content_types[:2])} content"
                }
            }]
        except Exception as rec_error:
            logger.error(f"Recommendation generation failed: {rec_error}")
            recommendations = [{
                "platform": "general",
                "optimal_times": ["12:00", "18:00"],
                "format_suggestions": {"type": "Standard post", "description": "Regular social media post"}
            }]
        
        # Calculate overall virality score
        overall_score = sum(score.score for score in virality_scores) / len(virality_scores) if virality_scores else 0.5
        
        # Create clip record
        clip_data = {
            "job_id": job_id,
            "video_id": video_id,
            "file_path": processing_result.get("clip_path", ""),
            "start_time": processing_result.get("segment_info", {}).get("start_time", 0),
            "duration": processing_result.get("segment_info", {}).get("duration", 0),
            "transcript": transcript,
            "overall_virality_score": overall_score
        }
        
        clip_id = asyncio.run(supabase_service.create_clip(clip_data))
        
        # Update progress
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=90, 
            current_step="Saving results"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="analyzing",
                progress=90,
                current_step="Saving results"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for job {job_id}: {ws_error}")
        
        # Save results with error handling
        try:
            # Save virality scores with new format
            scores_data = [{
                "start_time": score.start_time,
                "end_time": score.end_time,
                "score": score.score,
                "reason": score.reason,
                "content_type": score.content_type
            } for score in virality_scores]
            
            asyncio.run(supabase_service.save_virality_scores(clip_id, scores_data))
            
            # Save hashtags (already in dict format)
            asyncio.run(supabase_service.save_hashtags(clip_id, hashtags))
            
            # Save posting recommendations (already in dict format)
            asyncio.run(supabase_service.save_posting_recommendations(clip_id, recommendations))
            
        except Exception as save_error:
            logger.error(f"Failed to save some results for job {job_id}: {save_error}")
            # Continue anyway as the main processing is done
        
        # Update job status to complete
        asyncio.run(supabase_service.update_job_status(
            job_id, 
            status="complete", 
            progress=100, 
            current_step="Processing complete"
        ))
        
        # Broadcast completion update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=job_id,
                status="complete",
                progress=100,
                current_step="Processing complete",
                additional_data={
                    "clip_id": clip_id,
                    "overall_score": overall_score
                }
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket completion update for job {job_id}: {ws_error}")
        
        logger.info(f"URL processing completed for job {job_id}")
        
        return {
            "status": "complete",
            "job_id": job_id,
            "clip_id": clip_id,
            "overall_score": overall_score
        }
        
    except Exception as e:
        logger.error(f"URL processing failed for job {job_id}: {str(e)}")
        handle_task_failure(job_id, e, cleanup=True)
        raise e

# Async processing functions for when Redis is unavailable
async def process_video_sync(job_id: str, video_path: str, original_filename: str, file_size: int):
    """Async video processing when Redis/Celery is unavailable"""
    logger.info(f"Starting async video processing for job {job_id}")
    
    # Create a mock task object for compatibility
    class MockTask:
        def __init__(self):
            self.request = type('obj', (object,), {'retries': 0, 'id': f'sync-{job_id}'})()    
    mock_task = MockTask()
    
    # Call the main processing function without Celery decorators
    try:
        return await _process_video_core(job_id, video_path, original_filename, file_size)
    except Exception as e:
        logger.error(f"Async video processing failed for job {job_id}: {str(e)}")
        await handle_task_failure_async(job_id, e, cleanup=True)
        raise e

async def process_url_sync(job_id: str, video_url: str):
    """Async URL processing when Redis/Celery is unavailable"""
    logger.info(f"Starting async URL processing for job {job_id}")
    
    # Create a mock task object for compatibility
    class MockTask:
        def __init__(self):
            self.request = type('obj', (object,), {'retries': 0, 'id': f'sync-{job_id}'})()    
    mock_task = MockTask()
    
    # Call the main processing function without Celery decorators
    try:
        return await _process_url_core(mock_task, job_id, video_url)
    except Exception as e:
        logger.error(f"Async URL processing failed for job {job_id}: {str(e)}")
        await handle_task_failure_async(job_id, e, cleanup=True)
        raise e

async def _process_video_core(job_id: str, video_path: str, original_filename: str, file_size: int):
    """Core video processing logic extracted for reuse"""
    local_video_path = None
    try:
        logger.info(f"Starting video processing for job {job_id} (async mode)")
        
        # Validate input parameters
        if not job_id or not video_path:
            raise ValueError("Missing required parameters: job_id or video_path")
        
        # Check if video_path is a URL or local file
        if video_path.startswith(('http://', 'https://')):
            # Download video from URL to local temporary file
            logger.info(f"Downloading video from URL: {video_path}")
            import tempfile
            import requests
            
            # Create temporary file with proper extension
            file_extension = os.path.splitext(original_filename)[1] or '.mp4'
            temp_fd, local_video_path = tempfile.mkstemp(suffix=file_extension, prefix=f"video_{job_id}_")
            
            try:
                # Download the video file
                response = requests.get(video_path, stream=True, timeout=300)
                response.raise_for_status()
                
                with os.fdopen(temp_fd, 'wb') as temp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            temp_file.write(chunk)
                
                logger.info(f"Video downloaded to: {local_video_path}")
                video_path = local_video_path  # Use local path for processing
                
            except Exception as download_error:
                # Clean up temp file if download failed
                try:
                    os.close(temp_fd)
                    if local_video_path and os.path.exists(local_video_path):
                        os.remove(local_video_path)
                except:
                    pass
                raise Exception(f"Failed to download video: {str(download_error)}")
        
        # Now check if the local file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Validate file size (limit to 2GB)
        max_file_size = 2048 * 1024 * 1024  # 2GB
        if file_size > max_file_size:
            raise ValueError(f"File too large: {file_size / (1024*1024):.1f}MB. Maximum allowed: {max_file_size / (1024*1024):.1f}MB")
        
        # Update job status
        if supabase_service:
            await supabase_service.update_job_status(
                job_id, 
                status="analyzing", 
                progress=10, 
                current_step="Initializing video processing"
            )
        else:
            logger.warning(f"Supabase service unavailable - cannot update job status for {job_id}")
        
        # Create video record
        video_data = {
            "job_id": job_id,
            "file_path": video_path,
            "original_filename": original_filename,
            "file_size": file_size
        }
        video_id = None
        if supabase_service:
            video_id = await supabase_service.create_video(video_data)
        else:
            logger.warning(f"Supabase service unavailable - cannot create video record for {job_id}")
        
        # Initialize services with error handling
        try:
            video_processor = VideoProcessor()
            # Unified LLM service is globally initialized
        except Exception as init_error:
            raise Exception(f"Failed to initialize services: {str(init_error)}")
        
        # Update progress
        if supabase_service:
            await supabase_service.update_job_status(
                job_id, 
                status="analyzing", 
                progress=20, 
                current_step="Processing video content"
            )
        
        # Process video with enhanced progress callback
        async def video_processing_progress(message):
            try:
                logger.info(f"Video processing: {message}")
                if "transcribing" in message.lower():
                    await supabase_service.update_job_status(
                        job_id, status="analyzing", progress=30, current_step=message
                    )
                elif "analyzing" in message.lower():
                    await supabase_service.update_job_status(
                        job_id, status="analyzing", progress=35, current_step=message
                    )
                elif "extracting" in message.lower():
                    await supabase_service.update_job_status(
                        job_id, status="analyzing", progress=30, current_step=message
                    )
            except Exception as progress_error:
                logger.warning(f"Failed to update progress: {progress_error}")
        
        # Process video with timeout handling
        output_dir = os.path.join(UPLOADS_DIR, "clips", job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            processing_result = video_processor.process_video(video_path, output_dir)
        except Exception as processing_error:
            raise Exception(f"Video processing failed: {str(processing_error)}")
        
        if not processing_result.get("success", False):
            error_msg = processing_result.get('error', 'Unknown video processing error')
            raise Exception(f"Video processing failed: {error_msg}")
        
        # Update progress
        await supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=50, 
            current_step="Analyzing content for virality"
        )
        
        # Analyze virality with error handling
        transcript = processing_result.get("transcript", "")
        video_features = processing_result.get("video_features", {})
        
        if not transcript:
            logger.warning(f"No transcript available for job {job_id}, using fallback")
            transcript = "[No transcript available]"
        
        try:
            # Initialize LLM service for this task
            llm_service = LLMService()
            virality_scores = await llm_service.analyze_virality(transcript)
        except Exception as virality_error:
            logger.error(f"Virality analysis failed: {virality_error}")
            # Use fallback scores
            from .services.llm_service import ViralityScore
            virality_scores = [
                ViralityScore(start_time=0, end_time=30, score=0.5, reason="Analysis unavailable due to processing error", content_type="general")
            ]
        
        # Get top content types for hashtag generation
        top_content_types = [score.content_type for score in sorted(virality_scores, key=lambda x: x.score, reverse=True)[:3]]
        
        # Update progress
        await supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=70, 
            current_step="Generating hashtags and recommendations"
        )
        
        # Generate hashtags and recommendations with simplified approach
        try:
            # Simplified hashtag generation based on content types
            hashtags = []
            for content_type in top_content_types[:3]:
                # Clean content_type for hashtag formatting
                clean_content_type = ''.join(c for c in content_type.lower() if c.isalnum())
                if clean_content_type:  # Only add if there's content left
                    hashtags.append({
                        "tag": f"#{clean_content_type}",
                        "platform": "general",
                        "relevance_score": 0.8
                    })
            # Add generic hashtags
            hashtags.extend([
                {"tag": "#viral", "platform": "general", "relevance_score": 0.7},
                {"tag": "#content", "platform": "general", "relevance_score": 0.6}
            ])
        except Exception as hashtag_error:
            logger.error(f"Hashtag generation failed: {hashtag_error}")
            hashtags = [{"tag": "#video", "platform": "general", "relevance_score": 0.5}]
        
        try:
            # Simplified recommendation generation
            recommendations = [{
                "platform": "general",
                "optimal_times": ["12:00", "18:00", "20:00"],
                "format_suggestions": {
                    "type": "Short-form content",
                    "description": f"Focus on {', '.join(top_content_types[:2])} content"
                }
            }]
        except Exception as rec_error:
            logger.error(f"Recommendation generation failed: {rec_error}")
            recommendations = [{
                "platform": "general",
                "optimal_times": ["12:00", "18:00"],
                "format_suggestions": {"type": "Standard post", "description": "Regular social media post"}
            }]
        
        # Calculate overall virality score
        overall_score = sum(score.score for score in virality_scores) / len(virality_scores) if virality_scores else 0.5
        
        # Create clip record
        clip_data = {
            "job_id": job_id,
            "video_id": video_id,
            "file_path": processing_result.get("clip_path", ""),
            "start_time": processing_result.get("segment_info", {}).get("start_time", 0),
            "duration": processing_result.get("segment_info", {}).get("duration", 0),
            "transcript": transcript,
            "overall_virality_score": overall_score
        }
        
        clip_id = await supabase_service.create_clip(clip_data)
        
        # Update progress
        await supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=85, 
            current_step="Saving results"
        )
        
        # Save results with error handling
        try:
            # Save virality scores with new format
            scores_data = [{
                "start_time": score.start_time,
                "end_time": score.end_time,
                "score": score.score,
                "reason": score.reason,
                "content_type": score.content_type
            } for score in virality_scores]
            
            await supabase_service.save_virality_scores(clip_id, scores_data)
            
            # Save hashtags (already in dict format)
            await supabase_service.save_hashtags(clip_id, hashtags)
            
            # Save recommendations (already in dict format)
            await supabase_service.save_posting_recommendations(clip_id, recommendations)
            
        except Exception as save_error:
            logger.error(f"Failed to save some results for job {job_id}: {save_error}")
            # Continue anyway as the main processing is done
        
        # Update job status to complete
        await supabase_service.update_job_status(
            job_id, 
            status="complete", 
            progress=100, 
            current_step="Processing complete"
        )
        
        logger.info(f"Video processing completed for job {job_id}")
        
        return {
            "status": "complete",
            "job_id": job_id,
            "clip_id": clip_id,
            "overall_score": overall_score
        }
        
    except Exception as e:
        logger.error(f"Video processing failed for job {job_id}: {str(e)}")
        await handle_task_failure_async(job_id, e, cleanup=True)
        raise e
    finally:
        # Clean up temporary video file if it was downloaded
        if local_video_path and os.path.exists(local_video_path):
            try:
                os.remove(local_video_path)
                logger.info(f"Cleaned up temporary video file: {local_video_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary file {local_video_path}: {cleanup_error}")

async def _process_url_core(job_id: str, video_url: str):
    """Core URL processing logic extracted for reuse"""
    try:
        logger.info(f"Starting URL processing for job {job_id} (async mode)")
        
        # Validate input parameters
        if not job_id or not video_url:
            raise ValueError("Missing required parameters: job_id or video_url")
        
        # Update job status
        await supabase_service.update_job_status(
            job_id, 
            status="uploading", 
            progress=5, 
            current_step="Starting video download"
        )
        
        # Download video using yt-dlp
        download_dir = os.path.join(UPLOADS_DIR, "downloads", job_id)
        os.makedirs(download_dir, exist_ok=True)
        
        ydl_opts = {
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'format': 'best[height<=720]',  # Limit quality for faster processing
            'extractaudio': False,
            'audioformat': 'mp3',
            'embed_subs': True,
            'writesubtitles': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'ignoreerrors': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video info with timeout
                try:
                    info = ydl.extract_info(video_url, download=False)
                except Exception as info_error:
                    raise Exception(f"Failed to extract video information: {str(info_error)}")
                
                title = info.get('title', 'video')
                duration = info.get('duration', 0)
                
                # Check if video is too long (limit to 30 minutes)
                if duration and duration > 1800:  # 30 minutes
                    raise Exception(f"Video is too long ({duration//60} minutes). Please use videos under 30 minutes.")
                
                # Check file size estimate
                filesize = info.get('filesize') or info.get('filesize_approx')
                if filesize and filesize > 2048 * 1024 * 1024:  # 2GB
                    raise Exception(f"Video file too large ({filesize/(1024*1024):.1f}MB). Maximum allowed: 2GB")
                
                # Update progress during download
                await supabase_service.update_job_status(
                    job_id, 
                    status="uploading", 
                    progress=10, 
                    current_step="Downloading video from URL"
                )
                
                # Download the video with timeout handling
                try:
                    ydl.download([video_url])
                except Exception as download_error:
                    raise Exception(f"Failed to download video: {str(download_error)}")
                    
        except Exception as ydl_error:
            logger.error(f"Video download failed for job {job_id}: {str(ydl_error)}")
            raise Exception(f"Video download failed: {str(ydl_error)}")
        
        # Find the downloaded file
        downloaded_files = list(Path(download_dir).glob('*'))
        video_files = [f for f in downloaded_files if f.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.webm']]
        
        if not video_files:
            raise Exception("No video file found after download")
        
        video_path = str(video_files[0])
        file_size = os.path.getsize(video_path)
        original_filename = video_files[0].name
        
        # Validate downloaded file
        if not video_path or not os.path.exists(video_path):
            raise FileNotFoundError(f"Downloaded video file not found: {video_path}")
        
        # Validate file size (limit to 2GB)
        max_file_size = 2048 * 1024 * 1024  # 2GB
        if file_size > max_file_size:
            # Clean up downloaded file
            try:
                os.remove(video_path)
            except:
                pass
            raise ValueError(f"Downloaded file too large: {file_size / (1024*1024):.1f}MB. Maximum allowed: {max_file_size / (1024*1024):.1f}MB")
        
        logger.info(f"Video downloaded successfully for job {job_id}: {video_path} ({file_size / (1024*1024):.1f}MB)")
        
        # Update progress
        await supabase_service.update_job_status(
            job_id, 
            status="analyzing", 
            progress=15, 
            current_step="Download complete, starting analysis"
        )
        
        # Continue with video processing using the core function
        return await _process_video_core(job_id, video_path, original_filename, file_size)
        
    except Exception as e:
        logger.error(f"URL processing failed for job {job_id}: {str(e)}")
        await handle_task_failure_async(job_id, e, cleanup=True)
        raise e


@celery_app.task(bind=True, name="generate_clips_task")
def generate_clips_task(self, clip_id: str, video_id: str, user_id: str, generation_options: dict):
    """
    Generate video clips with AI-powered segment selection and platform optimization.
    
    Args:
        clip_id: Unique identifier for the clip generation job
        video_id: Source video ID from the jobs table
        user_id: User ID who owns the video
        generation_options: Dictionary containing:
            - clip_type: Type of clip (highlight, teaser, summary, custom)
            - target_duration: Desired clip duration in seconds
            - platform: Target platform (tiktok, youtube, instagram, etc.)
            - custom_parameters: Additional generation parameters
            - start_time: Optional manual start time
            - end_time: Optional manual end time
    """
    import asyncio
    import subprocess
    import json
    import shutil
    import time
    import psutil
    import gc
    from pathlib import Path
    from typing import Dict, List, Tuple, Optional
    
    start_time = time.time()
    logger.info(f"Starting clip generation for clip_id: {clip_id}, video_id: {video_id}")
    
    try:
        # Validate input parameters
        if not all([clip_id, video_id, user_id]):
            raise ValueError("Missing required parameters: clip_id, video_id, or user_id")
        
        # Initialize services with enhanced error handling
        from api.services.supabase_service import supabase_service
        
        # Initialize enhanced services
        llm_service = LLMService()
        video_processor = VideoProcessor()
        
        # Initialize transcription priority for enhanced processing
        video_processor._initialize_transcription_priority()
        
        # Enhanced system health check with memory management
        pre_generation_health = check_system_health()
        memory_usage = psutil.virtual_memory().percent
        
        if pre_generation_health['overall_status'] == 'critical' or memory_usage > 90:
            # Force garbage collection before failing
            gc.collect()
            asyncio.run(asyncio.sleep(1))
            
            # Recheck after cleanup
            memory_usage = psutil.virtual_memory().percent
            if memory_usage > 90:
                raise Exception(
                    f"System resources insufficient for clip generation: "
                    f"Memory: {memory_usage}%, Issues: {pre_generation_health.get('issues', '')}"
                )
        
        logger.info(
            f"Starting clip generation with system status: "
            f"Memory: {memory_usage}%, CPU: {psutil.cpu_percent()}%"
        )
        
        # Update clip status to processing
        asyncio.run(supabase_service.update_clip_status(
            clip_id=clip_id,
            status="processing",
            progress=5,
            current_step="Initializing clip generation"
        ))
        
        # Broadcast progress update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=clip_id,
                status="processing",
                progress=5,
                current_step="Initializing clip generation"
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast WebSocket update for clip {clip_id}: {ws_error}")
        
        # Get video information and file path
        video_info = asyncio.run(supabase_service.get_video_info(video_id, user_id))
        if not video_info:
            raise Exception(f"Video not found or access denied: {video_id}")
        
        video_path = video_info.get('file_path')
        if not video_path or not os.path.exists(video_path):
            raise FileNotFoundError(f"Source video file not found: {video_path}")
        
        # Get analysis results with enhanced transcription if needed
        analysis_results = asyncio.run(supabase_service.get_analysis_results(video_id, user_id))
        
        # If no analysis results exist, perform enhanced transcription
        if not analysis_results or not analysis_results.get('transcript'):
            logger.info("No existing analysis found, performing enhanced transcription")
            
            asyncio.run(supabase_service.update_clip_status(
                clip_id=clip_id,
                status="processing",
                progress=10,
                current_step="Performing enhanced audio transcription"
            ))
            
            try:
                # Use enhanced async transcription
                transcription_result = asyncio.run(video_processor.transcribe_audio(video_path))
                
                if transcription_result and transcription_result.text:
                    # Update analysis results with new transcription
                    analysis_results = analysis_results or {}
                    analysis_results['transcript'] = transcription_result.text
                    analysis_results['transcription_confidence'] = transcription_result.confidence
                    analysis_results['transcription_method'] = transcription_result.method
                    
                    # Save enhanced transcription results
                    asyncio.run(supabase_service.update_analysis_results(
                        video_id, user_id, analysis_results
                    ))
                    
                    logger.info(
                        f"Enhanced transcription completed with {transcription_result.method} "
                        f"(confidence: {transcription_result.confidence:.2f})"
                    )
                else:
                    logger.warning("Enhanced transcription failed, proceeding with existing data")
                    
            except Exception as transcription_error:
                logger.error(f"Enhanced transcription failed: {transcription_error}")
                # Continue with existing analysis results
        
        # Update progress
        asyncio.run(supabase_service.update_clip_status(
            clip_id=clip_id,
            status="processing",
            progress=20,
            current_step="Analyzing video segments with AI"
        ))
        
        # Determine optimal clip segments using AI with enhanced analysis
        clip_segments = asyncio.run(_determine_clip_segments(
            analysis_results=analysis_results,
            generation_options=generation_options,
            llm_service=llm_service,
            video_path=video_path,
            video_processor=video_processor
        ))
        
        # Perform viral scoring analysis on the selected segments
        asyncio.run(supabase_service.update_clip_status(
            clip_id=clip_id,
            status="processing",
            progress=25,
            current_step="Analyzing viral potential of segments"
        ))
        
        try:
            from api.services.viral_scoring import ViralScoringService
            viral_service = ViralScoringService()
            
            # Analyze viral potential for each segment
            for segment in clip_segments:
                viral_analysis = asyncio.run(viral_service.analyze_viral_potential(
                    video_path=video_path,
                    start_time=segment['start_time'],
                    end_time=segment['end_time'],
                    platform=generation_options.get('platform', 'general'),
                    transcript_segment=_extract_transcript_segment(
                        analysis_results.get('transcript', ''),
                        segment['start_time'],
                        segment['end_time']
                    )
                ))
                
                # Add viral scoring data to segment
                segment['viral_analysis'] = {
                    'overall_score': viral_analysis.overall_score,
                    'platform_scores': {
                        platform: score.score for platform, score in viral_analysis.platform_scores.items()
                    },
                    'viral_factors': [
                        {
                            'factor': factor.factor_type.value,
                            'score': factor.score,
                            'confidence': factor.confidence,
                            'explanation': factor.explanation
                        }
                        for factor in viral_analysis.viral_factors
                    ],
                    'viral_moments': [
                        {
                            'timestamp': moment.timestamp,
                            'intensity': moment.intensity,
                            'description': moment.description,
                            'factors': [f.value for f in moment.factors]
                        }
                        for moment in viral_analysis.viral_moments
                    ],
                    'insights': viral_analysis.insights,
                    'confidence': viral_analysis.confidence
                }
                
                logger.info(f"Viral analysis completed for segment {segment['start_time']:.1f}-{segment['end_time']:.1f}s: score {viral_analysis.overall_score:.2f}")
                
        except Exception as viral_error:
            logger.warning(f"Viral scoring failed, continuing without viral analysis: {viral_error}")
            # Continue without viral scoring if it fails
        
        # Update progress
        asyncio.run(supabase_service.update_clip_status(
            clip_id=clip_id,
            status="processing",
            progress=35,
            current_step="Preparing video processing"
        ))
        
        # Get platform-specific processing parameters
        platform_config = _get_platform_config(generation_options.get('platform', 'general'))
        
        # Create output directory
        output_dir = os.path.join(UPLOADS_DIR, "clips", clip_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # Process each segment
        generated_clips = []
        total_segments = len(clip_segments)
        failed_clips = 0
        max_failures = max(1, total_segments // 2)  # Allow up to 50% failures
        
        for i, segment in enumerate(clip_segments):
            try:
                # Enhanced memory check before each clip
                current_memory = psutil.virtual_memory().percent
                if current_memory > 85:
                    logger.warning(f"High memory usage ({current_memory}%) before clip {i+1}, forcing cleanup")
                    gc.collect()
                    asyncio.run(asyncio.sleep(2))  # Allow cleanup time
                    
                    # Recheck memory
                    current_memory = psutil.virtual_memory().percent
                    if current_memory > 90:
                        logger.error(f"Memory usage too high ({current_memory}%), skipping clip {i+1}")
                        failed_clips += 1
                        continue
                
                segment_progress = 35 + (i / total_segments) * 50  # 35-85% for processing
                
                asyncio.run(supabase_service.update_clip_status(
                    clip_id=clip_id,
                    status="processing",
                    progress=int(segment_progress),
                    current_step=f"Processing segment {i+1}/{total_segments} (Memory: {current_memory:.1f}%)"
                ))
                
                # Generate clip for this segment
                output_filename = f"clip_{i+1}_{clip_id}.{platform_config['format']}"
                output_path = os.path.join(output_dir, output_filename)
                
                # Generate clip with timeout
                clip_start_time = asyncio.get_event_loop().time()
                
                try:
                    clip_file_path = asyncio.run(asyncio.wait_for(
                        _generate_single_clip(
                            video_path=video_path,
                            output_path=output_path,
                            segment=segment,
                            platform_config=platform_config,
                            progress_callback=lambda progress: supabase_service.update_clip_status(
                                clip_id=clip_id,
                                status="processing",
                                progress=int(segment_progress + (progress * 0.1)),
                                current_step=f"Processing segment {i+1}/{total_segments} ({progress:.1f}%)"
                            )
                        ),
                        timeout=600  # 10 minutes per clip
                    ))
                    
                    clip_duration = asyncio.get_event_loop().time() - clip_start_time
                    
                    if clip_file_path and os.path.exists(clip_file_path):
                        # Create clip result object
                        clip_result = {
                            'file_path': clip_file_path,
                            'thumbnail_path': clip_file_path.replace('.mp4', '_thumbnail.jpg'),
                            'segment': segment,
                            'duration': segment['duration'],
                            'file_size': os.path.getsize(clip_file_path)
                        }
                        generated_clips.append(clip_result)
                        logger.info(
                            f"Successfully generated clip {i+1}/{total_segments} in {clip_duration:.1f}s: "
                            f"{clip_file_path} (size: {clip_result['file_size']} bytes)"
                        )
                    else:
                        logger.error(f"Failed to generate clip {i+1}/{total_segments}")
                        failed_clips += 1
                        
                except asyncio.TimeoutError:
                    logger.error(f"Clip {i+1} generation timed out after 10 minutes")
                    failed_clips += 1
                    continue
                    
                # Check if too many failures
                if failed_clips > max_failures:
                    logger.error(f"Too many clip generation failures ({failed_clips}/{total_segments}), aborting")
                    raise Exception(f"Clip generation failed: {failed_clips} out of {total_segments} clips failed")
                    
            except Exception as clip_error:
                logger.error(f"Error generating clip {i+1}/{total_segments}: {clip_error}")
                failed_clips += 1
                
                # Check if too many failures
                if failed_clips > max_failures:
                    logger.error(f"Too many clip generation failures ({failed_clips}/{total_segments}), aborting")
                    raise Exception(f"Clip generation failed: {failed_clips} out of {total_segments} clips failed")
                    
                continue
            
            # Brief pause between clips to prevent resource exhaustion
            if i < total_segments - 1:  # Don't pause after last clip
                asyncio.run(asyncio.sleep(1))
        
        if not generated_clips:
            raise Exception("No clips were successfully generated")
        
        # Update progress
        asyncio.run(supabase_service.update_clip_status(
            clip_id=clip_id,
            status="processing",
            progress=90,
            current_step="Finalizing clips"
        ))
        
        # Save clip information to database
        clip_data = {
            "file_paths": [clip['file_path'] for clip in generated_clips],
            "thumbnail_paths": [clip.get('thumbnail_path') for clip in generated_clips],
            "segments": clip_segments,
            "platform_config": platform_config,
            "generation_metadata": {
                "total_clips": len(generated_clips),
                "processing_time": time.time() - start_time,
                "platform": generation_options.get('platform', 'general'),
                "clip_type": generation_options.get('clip_type', 'highlight')
            },
            "viral_analysis": {
                "segments_analyzed": len([s for s in clip_segments if 'viral_analysis' in s]),
                "average_viral_score": sum(
                    s.get('viral_analysis', {}).get('overall_score', 0) 
                    for s in clip_segments
                ) / len(clip_segments) if clip_segments else 0,
                "best_viral_score": max(
                    (s.get('viral_analysis', {}).get('overall_score', 0) for s in clip_segments),
                    default=0
                ),
                "platform_optimized": generation_options.get('platform', 'general') != 'general'
            }
        }
        
        asyncio.run(supabase_service.update_clip_data(clip_id, clip_data))
        
        # Update final status
        asyncio.run(supabase_service.update_clip_status(
            clip_id=clip_id,
            status="completed",
            progress=100,
            current_step="Clip generation complete"
        ))
        
        # Broadcast final update via WebSocket
        try:
            from api.main import broadcast_job_update
            asyncio.run(broadcast_job_update(
                job_id=clip_id,
                status="completed",
                progress=100,
                current_step="Clip generation complete",
                additional_data={"clips_data": clip_data}
            ))
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast final WebSocket update for clip {clip_id}: {ws_error}")
        
        logger.info(f"Clip generation completed successfully for clip_id: {clip_id}")
        
        return {
            "status": "completed",
            "clip_id": clip_id,
            "generated_clips": len(generated_clips),
            "total_duration": sum(clip['duration'] for clip in generated_clips)
        }
        
    except Exception as e:
        logger.error(f"Clip generation failed for clip_id {clip_id}: {str(e)}")
        
        # Update clip status to failed
        try:
            asyncio.run(supabase_service.update_clip_status(
                clip_id=clip_id,
                status="failed",
                progress=0,
                current_step=f"Generation failed: {str(e)}"
            ))
            
            # Broadcast failure via WebSocket
            try:
                from api.main import broadcast_job_update
                asyncio.run(broadcast_job_update(
                    job_id=clip_id,
                    status="failed",
                    progress=0,
                    current_step=f"Generation failed: {str(e)}"
                ))
            except Exception as ws_error:
                logger.warning(f"Failed to broadcast failure WebSocket update: {ws_error}")
                
        except Exception as update_error:
            logger.error(f"Failed to update clip status after error: {update_error}")
        
        # Cleanup resources
        cleanup_clip_resources(clip_id)
        raise e


async def _determine_clip_segments(
    analysis_results: dict,
    generation_options: dict,
    llm_service,
    video_path: str,
    video_processor=None
) -> List[Dict]:
    """
    Determine optimal clip segments using AI analysis and user preferences.
    Enhanced with video processor integration for better analysis.
    """
    import subprocess
    import json
    
    clip_type = generation_options.get('clip_type', 'highlight')
    target_duration = generation_options.get('target_duration', 30.0)
    platform = generation_options.get('platform', 'general')
    
    # If manual start/end times are provided, use them
    if 'start_time' in generation_options and 'end_time' in generation_options:
        return [{
            'start_time': generation_options['start_time'],
            'end_time': generation_options['end_time'],
            'duration': generation_options['end_time'] - generation_options['start_time'],
            'confidence': 1.0,
            'reason': 'Manual selection'
        }]
    
    # Get video duration using ffprobe
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            video_info = json.loads(result.stdout)
            video_duration = float(video_info['format']['duration'])
        else:
            logger.warning(f"Failed to get video duration, using default: {result.stderr}")
            video_duration = 300.0  # Default 5 minutes
    except Exception as e:
        logger.warning(f"Error getting video duration: {e}")
        video_duration = 300.0
    
    # Use analysis results to find high-engagement segments
    segments = []
    
    if analysis_results and 'virality_scores' in analysis_results:
        # Find segments with high virality scores
        virality_data = analysis_results['virality_scores']
        
        if clip_type == 'highlight':
            # Find the highest scoring continuous segment
            segments = await _find_highlight_segments(
                virality_data, target_duration, video_duration
            )
        elif clip_type == 'teaser':
            # Find multiple short, high-impact segments
            segments = await _find_teaser_segments(
                virality_data, target_duration, video_duration
            )
        elif clip_type == 'summary':
            # Find representative segments across the video
            segments = await _find_summary_segments(
                virality_data, target_duration, video_duration
            )
    
    # Fallback to simple segmentation if no analysis results
    if not segments:
        logger.warning("No analysis results available, using fallback segmentation")
        segments = _create_fallback_segments(video_duration, target_duration, clip_type)
    
    # Ensure segments don't exceed video duration
    segments = [s for s in segments if s['end_time'] <= video_duration]
    
    return segments[:5]  # Limit to 5 clips maximum


async def _find_highlight_segments(virality_data: List[dict], target_duration: float, video_duration: float) -> List[Dict]:
    """
    Find the best highlight segments based on virality scores.
    """
    # Sort by virality score and find continuous high-scoring segments
    sorted_scores = sorted(virality_data, key=lambda x: x.get('score', 0), reverse=True)
    
    segments = []
    for score_data in sorted_scores[:3]:  # Top 3 segments
        start_time = max(0, score_data.get('timestamp', 0) - target_duration / 2)
        end_time = min(video_duration, start_time + target_duration)
        
        # Adjust start_time if end_time was clamped
        if end_time == video_duration:
            start_time = max(0, end_time - target_duration)
        
        segments.append({
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'confidence': score_data.get('score', 0.5),
            'reason': f"High virality score: {score_data.get('score', 0.5):.2f}"
        })
    
    return segments


async def _find_teaser_segments(virality_data: List[dict], target_duration: float, video_duration: float) -> List[Dict]:
    """
    Find short, impactful segments for teasers.
    """
    segment_duration = min(15.0, target_duration / 2)  # Shorter segments for teasers
    segments = []
    
    # Find peak moments
    sorted_scores = sorted(virality_data, key=lambda x: x.get('score', 0), reverse=True)
    
    for i, score_data in enumerate(sorted_scores[:4]):  # Up to 4 short segments
        start_time = max(0, score_data.get('timestamp', 0) - segment_duration / 2)
        end_time = min(video_duration, start_time + segment_duration)
        
        segments.append({
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'confidence': score_data.get('score', 0.5),
            'reason': f"Peak moment {i+1}"
        })
    
    return segments


async def _find_summary_segments(virality_data: List[dict], target_duration: float, video_duration: float) -> List[Dict]:
    """
    Find representative segments across the entire video.
    """
    num_segments = max(2, min(5, int(target_duration / 10)))  # 2-5 segments
    segment_duration = target_duration / num_segments
    
    segments = []
    time_intervals = video_duration / num_segments
    
    for i in range(num_segments):
        interval_start = i * time_intervals
        interval_end = (i + 1) * time_intervals
        
        # Find best scoring moment in this interval
        interval_scores = [
            s for s in virality_data 
            if interval_start <= s.get('timestamp', 0) <= interval_end
        ]
        
        if interval_scores:
            best_score = max(interval_scores, key=lambda x: x.get('score', 0))
            start_time = max(interval_start, best_score.get('timestamp', interval_start) - segment_duration / 2)
            end_time = min(interval_end, start_time + segment_duration)
        else:
            # Fallback to middle of interval
            start_time = interval_start + (time_intervals - segment_duration) / 2
            end_time = start_time + segment_duration
        
        segments.append({
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'confidence': best_score.get('score', 0.3) if interval_scores else 0.3,
            'reason': f"Summary segment {i+1}/{num_segments}"
        })
    
    return segments


def _create_fallback_segments(video_duration: float, target_duration: float, clip_type: str) -> List[Dict]:
    """
    Create fallback segments when no analysis data is available.
    """
    segments = []
    
    if clip_type == 'highlight':
        # Single segment from the middle third of the video
        start_time = video_duration / 3
        end_time = min(video_duration, start_time + target_duration)
        segments.append({
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'confidence': 0.3,
            'reason': 'Fallback: middle segment'
        })
    elif clip_type == 'teaser':
        # Multiple short segments
        segment_duration = min(15.0, target_duration / 3)
        for i in range(3):
            start_time = (i + 1) * video_duration / 4
            end_time = min(video_duration, start_time + segment_duration)
            segments.append({
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'confidence': 0.3,
                'reason': f'Fallback: teaser {i+1}'
            })
    else:
        # Summary: segments from beginning, middle, and end
        segment_duration = target_duration / 3
        positions = [0.1, 0.5, 0.8]  # 10%, 50%, 80% through video
        
        for i, pos in enumerate(positions):
            start_time = pos * video_duration
            end_time = min(video_duration, start_time + segment_duration)
            segments.append({
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'confidence': 0.3,
                'reason': f'Fallback: summary {i+1}'
            })
    
    return segments


def _validate_generation_options(options: Dict) -> None:
    """
    Validate clip generation options.
    Raises ValueError if options are invalid.
    """
    if not options:
        raise ValueError("Generation options cannot be empty")
    
    # Validate platform
    valid_platforms = ['tiktok', 'youtube', 'instagram', 'instagram_stories', 'twitter', 'linkedin', 'facebook', 'general']
    platform = options.get('platform')
    if not platform or platform not in valid_platforms:
        raise ValueError(f"Invalid platform. Must be one of: {', '.join(valid_platforms)}")
    
    # Validate clip_type
    valid_clip_types = ['highlight', 'summary', 'custom']
    clip_type = options.get('clip_type')
    if not clip_type or clip_type not in valid_clip_types:
        raise ValueError(f"Invalid clip_type. Must be one of: {', '.join(valid_clip_types)}")
    
    # Validate duration if provided (check both 'duration' and 'target_duration')
    duration = options.get('duration') or options.get('target_duration')
    if duration is not None:
        if not isinstance(duration, (int, float)) or duration <= 0:
            raise ValueError("Duration must be a positive number")
        if duration > 3600:  # 1 hour max
            raise ValueError("Duration cannot exceed 3600 seconds")
    
    # Validate max_clips if provided
    max_clips = options.get('max_clips')
    if max_clips is not None:
        if not isinstance(max_clips, int) or max_clips <= 0:
            raise ValueError("max_clips must be a positive integer")
        if max_clips > 50:  # Reasonable limit
            raise ValueError("max_clips cannot exceed 50")


def _get_platform_config(platform: str) -> Dict:
    """
    Get platform-specific video processing configuration.
    """
    configs = {
        'tiktok': {
            'aspect_ratio': '9:16',
            'resolution': '1080x1920',
            'fps': 30,
            'bitrate': '2500k',
            'audio_bitrate': '128k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 180,  # 3 minutes
            'filters': [
                'scale=1080:1920:force_original_aspect_ratio=increase',
                'crop=1080:1920'
            ]
        },
        'youtube': {
            'aspect_ratio': '16:9',
            'resolution': '1920x1080',
            'fps': 30,
            'bitrate': '5000k',
            'audio_bitrate': '192k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 3600,  # 1 hour
            'filters': [
                'scale=1920:1080:force_original_aspect_ratio=decrease',
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black'
            ]
        },
        'instagram': {
            'aspect_ratio': '1:1',
            'resolution': '1080x1080',
            'fps': 30,
            'bitrate': '3500k',
            'audio_bitrate': '128k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 60,  # 1 minute
            'filters': [
                'scale=1080:1080:force_original_aspect_ratio=increase',
                'crop=1080:1080'
            ]
        },
        'instagram_feed': {
            'aspect_ratio': '1:1',
            'resolution': '1080x1080',
            'fps': 30,
            'bitrate': '3500k',
            'audio_bitrate': '128k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 60,  # 1 minute
            'filters': [
                'scale=1080:1080:force_original_aspect_ratio=increase',
                'crop=1080:1080'
            ]
        },
        'instagram_stories': {
            'aspect_ratio': '9:16',
            'resolution': '1080x1920',
            'fps': 30,
            'bitrate': '2500k',
            'audio_bitrate': '128k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 15,  # 15 seconds
            'filters': [
                'scale=1080:1920:force_original_aspect_ratio=increase',
                'crop=1080:1920'
            ]
        },
        'twitter': {
            'aspect_ratio': '16:9',
            'resolution': '1280x720',
            'fps': 30,
            'bitrate': '2000k',
            'audio_bitrate': '128k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 140,  # 2:20
            'filters': [
                'scale=1280:720:force_original_aspect_ratio=decrease',
                'pad=1280:720:(ow-iw)/2:(oh-ih)/2:black'
            ]
        },
        'linkedin': {
            'aspect_ratio': '16:9',
            'resolution': '1920x1080',
            'fps': 30,
            'bitrate': '4000k',
            'audio_bitrate': '192k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 600,  # 10 minutes
            'filters': [
                'scale=1920:1080:force_original_aspect_ratio=decrease',
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black'
            ]
        },
        'facebook': {
            'aspect_ratio': '16:9',
            'resolution': '1920x1080',
            'fps': 30,
            'bitrate': '4000k',
            'audio_bitrate': '192k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 1800,  # 30 minutes
            'filters': [
                'scale=1920:1080:force_original_aspect_ratio=decrease',
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black'
            ]
        },
        'general': {
            'aspect_ratio': '16:9',
            'resolution': '1920x1080',
            'fps': 30,
            'bitrate': '3000k',
            'audio_bitrate': '128k',
            'format': 'mp4',
            'codec': 'libx264',
            'audio_codec': 'aac',
            'max_duration': 300,  # 5 minutes
            'filters': [
                'scale=1920:1080:force_original_aspect_ratio=decrease',
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black'
            ]
        }
    }
    
    return configs.get(platform, configs['general'])


async def _generate_single_clip(
    video_path: str,
    output_path: str,
    segment: Dict,
    platform_config: Dict,
    progress_callback=None
) -> str:
    """
    Generate a single clip using enhanced FFmpeg processing with GPU acceleration,
    memory management, and industry-standard error handling.
    Returns the output file path on success.
    """
    import psutil
    import asyncio
    from pathlib import Path
    
    start_time = segment['start_time']
    duration = segment['duration']
    
    # Memory check before processing
    memory_usage = psutil.virtual_memory().percent
    if memory_usage > 85:
        logger.warning(f"High memory usage ({memory_usage}%) before clip generation")
        # Force garbage collection
        import gc
        gc.collect()
    
    # Create temporary directory for processing
    temp_dir = Path(output_path).parent / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # Build enhanced FFmpeg command with GPU acceleration support
    cmd = [
        'ffmpeg', '-y',  # Overwrite output files
        '-hide_banner', '-loglevel', 'info',  # Cleaner output
        '-ss', str(start_time),  # Start time (input seeking for efficiency)
        '-i', video_path,  # Input file
        '-t', str(duration),  # Duration
    ]
    
    # Add GPU acceleration if available (NVIDIA)
    try:
        # Check for NVIDIA GPU support
        gpu_check = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'], 
            capture_output=True, text=True, timeout=10
        )
        if 'h264_nvenc' in gpu_check.stdout:
            cmd.extend([
                '-c:v', 'h264_nvenc',  # NVIDIA GPU encoder
                '-preset', 'p4',  # High quality preset
                '-tune', 'hq',  # High quality tuning
                '-rc', 'vbr',  # Variable bitrate
                '-cq', '23',  # Constant quality
                '-b:v', platform_config['bitrate'],
                '-maxrate', str(int(platform_config['bitrate'].replace('k', '')) * 1.5) + 'k',
                '-bufsize', str(int(platform_config['bitrate'].replace('k', '')) * 2) + 'k'
            ])
            logger.info("Using NVIDIA GPU acceleration for encoding")
        else:
            # Fallback to CPU encoding with optimized settings
            cmd.extend([
                '-c:v', platform_config['codec'],
                '-preset', 'faster',  # Faster preset for CPU
                '-crf', '23',
                '-b:v', platform_config['bitrate']
            ])
    except Exception as gpu_error:
        logger.debug(f"GPU check failed, using CPU encoding: {gpu_error}")
        cmd.extend([
            '-c:v', platform_config['codec'],
            '-preset', 'faster',
            '-crf', '23',
            '-b:v', platform_config['bitrate']
        ])
    
    # Audio encoding settings
    cmd.extend([
        '-c:a', platform_config['audio_codec'],
        '-b:a', platform_config['audio_bitrate'],
        '-ar', '44100',  # Standard sample rate
    ])
    
    # Frame rate and optimization
    cmd.extend([
        '-r', str(platform_config['fps']),
        '-movflags', '+faststart',  # Web optimization
        '-fflags', '+genpts',  # Generate presentation timestamps
    ])
    
    # Add enhanced video filters
    filters = []
    if platform_config.get('filters'):
        filters.extend(platform_config['filters'])
    
    # Add automatic quality enhancement filters
    filters.extend([
        'scale=trunc(iw/2)*2:trunc(ih/2)*2',  # Ensure even dimensions
        'format=yuv420p'  # Ensure compatibility
    ])
    
    if filters:
        cmd.extend(['-vf', ','.join(filters)])
    
    # Add output file
    cmd.append(output_path)
    
    logger.info(f"Starting enhanced clip generation: {' '.join(cmd[:10])}...")
    
    try:
        # Start FFmpeg process with enhanced monitoring
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=temp_dir
        )
        
        start_time_proc = time.time()
        stderr_lines = []
        
        # Enhanced progress monitoring with timeout
        async def monitor_progress():
            nonlocal stderr_lines
            try:
                while True:
                    line = await asyncio.wait_for(
                        process.stderr.readline(), timeout=30.0
                    )
                    if not line:
                        break
                    
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    stderr_lines.append(line_str)
                    
                    # Parse FFmpeg progress
                    if 'time=' in line_str and progress_callback:
                        try:
                            time_str = line_str.split('time=')[1].split()[0]
                            if ':' in time_str:
                                time_parts = time_str.split(':')
                                current_seconds = (
                                    float(time_parts[0]) * 3600 +
                                    float(time_parts[1]) * 60 +
                                    float(time_parts[2])
                                )
                                progress = min(100, (current_seconds / duration) * 100)
                                if asyncio.iscoroutinefunction(progress_callback):
                                    await progress_callback(progress)
                                else:
                                    progress_callback(progress)
                        except Exception as e:
                            logger.debug(f"Error parsing FFmpeg progress: {e}")
                            
            except asyncio.TimeoutError:
                logger.warning("FFmpeg progress monitoring timed out")
            except Exception as e:
                logger.error(f"Error monitoring FFmpeg progress: {e}")
        
        # Run progress monitoring and wait for completion
        monitor_task = asyncio.create_task(monitor_progress())
        
        try:
            # Wait for process completion with timeout
            await asyncio.wait_for(process.wait(), timeout=600)  # 10 minutes max
        except asyncio.TimeoutError:
            process.terminate()
            await asyncio.sleep(2)
            if process.returncode is None:
                process.kill()
            raise TimeoutError("Clip generation timed out after 10 minutes")
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        
        # Check process result
        if process.returncode != 0:
            error_msg = '\n'.join(stderr_lines[-10:])  # Last 10 lines
            raise subprocess.CalledProcessError(
                process.returncode, cmd, stderr=error_msg
            )
        
        # Verify output file
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Output file not created: {output_path}")
        
        file_size = os.path.getsize(output_path)
        if file_size == 0:
            raise ValueError(f"Output file is empty: {output_path}")
        
        # Verify video integrity
        try:
            verify_cmd = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=duration', '-of', 'csv=p=0',
                output_path
            ]
            verify_result = subprocess.run(
                verify_cmd, capture_output=True, text=True, timeout=30
            )
            if verify_result.returncode != 0:
                logger.warning(f"Video verification failed: {verify_result.stderr}")
        except Exception as verify_error:
            logger.warning(f"Could not verify video integrity: {verify_error}")
        
        processing_time = time.time() - start_time_proc
        
        # Generate thumbnail
        thumbnail_path = await _generate_thumbnail(
            video_path, start_time + duration/2, output_path
        )
        
        # Cleanup temp directory
        try:
            if temp_dir.exists() and temp_dir != Path(output_path).parent:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            logger.debug(f"Temp cleanup warning: {cleanup_error}")
        
        logger.info(
            f"Clip generated successfully: {output_path} "
            f"(size: {file_size} bytes, time: {processing_time:.2f}s)"
        )
        return output_path
        
    except Exception as e:
        # Enhanced cleanup on failure
        cleanup_files = [output_path]
        if thumbnail_path := output_path.replace('.mp4', '_thumbnail.jpg'):
            cleanup_files.append(thumbnail_path)
        
        for file_path in cleanup_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.debug(f"Cleaned up failed file: {file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Could not cleanup file {file_path}: {cleanup_error}")
        
        # Cleanup temp directory
        try:
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        
        logger.error(f"Enhanced clip generation failed: {e}")
        raise e


async def _generate_thumbnail(video_path: str, timestamp: float, clip_path: str) -> str:
    """
    Generate a thumbnail for the clip at the specified timestamp.
    """
    try:
        # Create thumbnail filename based on clip path
        clip_dir = os.path.dirname(clip_path)
        clip_name = os.path.splitext(os.path.basename(clip_path))[0]
        thumbnail_path = os.path.join(clip_dir, f"{clip_name}_thumbnail.jpg")
        
        # FFmpeg command to extract thumbnail
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(timestamp),
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',  # High quality
            '-vf', 'scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2:black',
            thumbnail_path
        ]
        
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if process.returncode == 0 and os.path.exists(thumbnail_path):
            logger.debug(f"Thumbnail generated: {thumbnail_path}")
            return thumbnail_path
        else:
            logger.warning(f"Thumbnail generation failed: {process.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        return None


def cleanup_clip_resources(clip_id: str):
    """
    Clean up temporary files and resources for a clip generation job.
    """
    import os
    import glob
    import shutil
    
    try:
        # Clean up temporary files
        temp_patterns = [
            f"/tmp/clip_{clip_id}_*",
            f"/tmp/video_{clip_id}_*",
            f"./temp/clip_{clip_id}_*",
            f"./temp/video_{clip_id}_*"
        ]
        
        for pattern in temp_patterns:
            for file_path in glob.glob(pattern):
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logger.debug(f"Cleaned up temp file: {file_path}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        logger.debug(f"Cleaned up temp directory: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {file_path}: {e}")
        
        # Clean up any clip-specific cache
        cache_dirs = [
            f"./cache/clips/{clip_id}",
            f"/tmp/cache/clips/{clip_id}"
        ]
        
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                try:
                    shutil.rmtree(cache_dir)
                    logger.debug(f"Cleaned up cache directory: {cache_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up cache {cache_dir}: {e}")
        
        logger.info(f"Resource cleanup completed for clip {clip_id}")
        
    except Exception as e:
        logger.error(f"Error during resource cleanup for clip {clip_id}: {e}")


def _validate_clip_generation_input(clip_id: str, generation_options: dict) -> Dict:
    """
    Validate input parameters for clip generation.
    """
    errors = []
    
    # Validate clip_id
    if not clip_id or not isinstance(clip_id, str):
        errors.append("Invalid clip_id: must be a non-empty string")
    
    # Validate generation_options
    if not isinstance(generation_options, dict):
        errors.append("Invalid generation_options: must be a dictionary")
        return {'valid': False, 'errors': errors}
    
    # Validate platform
    platform = generation_options.get('platform', 'general')
    valid_platforms = [
        'tiktok', 'youtube', 'instagram', 'instagram_stories',
        'twitter', 'linkedin', 'facebook', 'general'
    ]
    if platform not in valid_platforms:
        errors.append(f"Invalid platform: {platform}. Must be one of {valid_platforms}")
    
    # Validate clip_type
    clip_type = generation_options.get('clip_type', 'highlight')
    valid_types = ['highlight', 'teaser', 'summary']
    if clip_type not in valid_types:
        errors.append(f"Invalid clip_type: {clip_type}. Must be one of {valid_types}")
    
    # Validate target_duration
    target_duration = generation_options.get('target_duration', 30.0)
    if not isinstance(target_duration, (int, float)) or target_duration <= 0:
        errors.append("Invalid target_duration: must be a positive number")
    elif target_duration > 1800:  # 30 minutes max
        errors.append("Invalid target_duration: maximum 1800 seconds (30 minutes)")
    
    # Validate manual times if provided
    start_time = generation_options.get('start_time')
    end_time = generation_options.get('end_time')
    
    if start_time is not None:
        if not isinstance(start_time, (int, float)) or start_time < 0:
            errors.append("Invalid start_time: must be a non-negative number")
    
    if end_time is not None:
        if not isinstance(end_time, (int, float)) or end_time < 0:
            errors.append("Invalid end_time: must be a non-negative number")
        
        if start_time is not None and end_time <= start_time:
            errors.append("Invalid time range: end_time must be greater than start_time")
    
    # Validate quality settings
    quality = generation_options.get('quality', 'medium')
    valid_qualities = ['low', 'medium', 'high', 'ultra']
    if quality not in valid_qualities:
        errors.append(f"Invalid quality: {quality}. Must be one of {valid_qualities}")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'normalized_options': {
            'platform': platform,
            'clip_type': clip_type,
            'target_duration': float(target_duration),
            'quality': quality,
            'start_time': float(start_time) if start_time is not None else None,
            'end_time': float(end_time) if end_time is not None else None
        }
    }


def _extract_transcript_segment(transcript: str, start_time: float, end_time: float) -> str:
    """
    Extract a segment of transcript based on time range.
    This is a simplified implementation - in a real system, you'd need
    timestamp-aligned transcript data.
    """
    if not transcript:
        return ""
    
    # Simple approximation: assume transcript is evenly distributed over time
    # In a real implementation, you'd use timestamp-aligned transcript data
    words = transcript.split()
    total_words = len(words)
    
    if total_words == 0:
        return ""
    
    # Estimate words per second (rough approximation)
    # Average speaking rate is about 150-160 words per minute
    words_per_second = 2.5
    
    start_word_index = int(start_time * words_per_second)
    end_word_index = int(end_time * words_per_second)
    
    # Ensure indices are within bounds
    start_word_index = max(0, min(start_word_index, total_words - 1))
    end_word_index = max(start_word_index, min(end_word_index, total_words))
    
    # Extract the segment
    segment_words = words[start_word_index:end_word_index]
    
    return " ".join(segment_words)