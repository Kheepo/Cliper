from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from pydantic import BaseModel, HttpUrl, Field
import uuid
import os
import mimetypes
import tempfile
from datetime import datetime
from loguru import logger

from ..utils.supabase_client import get_supabase_admin_client
from ..middleware.auth import get_supabase_token_info_from_auth_middleware as get_supabase_token_info
from ..models.pydantic_models import AnalysisResponse, AnalysisSegment, GeneratedClip, VideoUploadResponse, URLProcessResponse
from ..services.video_downloader import video_downloader
from ..services.supabase_storage_service import supabase_storage_service
from ..services.supabase_storage_service import SupabaseStorageService
from api.tasks import process_video_task, process_video_sync
from api.celery_app import is_background_tasks_enabled, is_redis_available

# Video processing constants
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_VIDEO_TYPES = {
    'video/mp4': '.mp4',
    'video/avi': '.avi', 
    'video/mov': '.mov',
    'video/wmv': '.wmv',
    'video/flv': '.flv',
    'video/webm': '.webm',
    'video/mkv': '.mkv',
    'video/m4v': '.m4v'
}

def should_use_background_processing() -> bool:
    """Determine if background processing (Celery) should be used"""
    return is_background_tasks_enabled() and is_redis_available()

async def start_video_processing(job_id: str, video_path: str, original_filename: str, file_size: int):
    """Start video processing using either Celery or sync processing"""
    if should_use_background_processing():
        # Use Celery for background processing
        logger.info(f"Starting background processing for job {job_id}")
        task_result = process_video_task.delay(
            job_id=job_id,
            video_path=video_path,
            original_filename=original_filename,
            file_size=file_size
        )
        return task_result.id
    else:
        # Use sync processing when Celery is unavailable
        logger.info(f"Starting sync processing for job {job_id} (Celery unavailable)")
        import asyncio
        # Start sync processing in background
        asyncio.create_task(process_video_sync(
            job_id=job_id,
            video_path=video_path,
            original_filename=original_filename,
            file_size=file_size
        ))
        return f"sync-{job_id}"

router = APIRouter(tags=["videos"])

# Pydantic models
class VideoResponse(BaseModel):
    """Video information response"""
    id: str = Field(..., description="Unique video identifier")
    title: str = Field(..., description="Video title")
    description: str | None = Field(None, description="Video description")
    url: str | None = Field(None, description="Video URL if available")
    file_path: str | None = Field(None, description="File path in storage")
    duration: float | None = Field(None, description="Video duration in seconds")
    file_size: int | None = Field(None, description="File size in bytes")
    status: str = Field(..., description="Processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

class VideoAnalysisResponse(BaseModel):
    """Video analysis response"""
    id: str
    video_id: str
    viral_score: float
    segments: List[AnalysisSegment]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    target_niche: Optional[str] = Form(None),
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Upload video file for processing"""
    try:
        # Get auth ID from token
        auth_id = token_info.get('uid')
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Get user ID from users table using auth_id
        supabase = get_supabase_admin_client()
        user_result = supabase.table("users").select("id").eq("auth_id", auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user_id = user_result.data[0]["id"]
        
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Check file size (read in chunks to avoid memory issues)
        file_size = 0
        file_chunks = []
        
        # Reset file pointer
        await file.seek(0)
        
        # Read file in chunks to handle large files efficiently
        chunk_size = 8 * 1024 * 1024  # 8MB chunks
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_chunks.append(chunk)
            file_size += len(chunk)
            
            # Check size limit during reading to fail fast
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024*1024)}GB"
                )
        
        # Combine chunks
        file_content = b''.join(file_chunks)
        
        # Check file type
        content_type = file.content_type
        if content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {content_type}. Allowed types: {list(ALLOWED_VIDEO_TYPES.keys())}"
            )
        
        # Generate unique filename
        file_extension = ALLOWED_VIDEO_TYPES[content_type]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Upload to storage
        try:
            file_url = await supabase_storage_service.upload_video(
                file_content, unique_filename, user_id
            )
        except Exception as e:
            logger.error(f"Failed to upload file to storage: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to storage"
            )
        
        # Create job record with retry logic
        try:
            supabase = get_supabase_admin_client()
            job_data = {
                "user_id": user_id,
                "job_type": "upload",
                "status": "pending",
                "title": file.filename,
                "description": f"Analysis of uploaded video: {file.filename}",
                "video_filename": unique_filename,
                "video_url": file_url,
                "video_size": len(file_content)
            }
            
            try:
                result = supabase.table("jobs").insert(job_data).execute()
                if not result.data:
                    raise Exception("Failed to create job record - no data returned")
                
                job_id = result.data[0]["id"]
                logger.info(f"Job record created with ID: {job_id}")
                
            except Exception as job_error:
                logger.error(f"Failed to create job record: {job_error}")
                # Clean up uploaded file on job creation failure
                try:
                    await supabase_storage_service.delete_file(unique_filename, user_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup file after job creation error: {cleanup_error}")
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create processing job: {str(job_error)}"
                )
            
            # Start video processing (Celery or sync fallback)
            try:
                task_id = await start_video_processing(
                    job_id=job_id,
                    video_path=file_url,
                    original_filename=file.filename,
                    file_size=len(file_content)
                )
                
                logger.info(f"Video processing started for job {job_id}: {task_id}")
                
                # Update job with task ID for tracking
                job_status = 'queued' if should_use_background_processing() else 'processing'
                supabase.table('jobs').update({
                    'celery_task_id': task_id,
                    'status': job_status,
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', job_id).execute()
                
            except Exception as task_error:
                logger.error(f"Failed to start video processing for job {job_id}: {task_error}")
                
                # Update job status to failed
                try:
                    supabase.table('jobs').update({
                        'status': 'failed',
                        'status_message': f'Failed to start processing: {str(task_error)}',
                        'updated_at': datetime.utcnow().isoformat()
                    }).eq('id', job_id).execute()
                except Exception as update_error:
                    logger.error(f"Failed to update job status: {update_error}")
                
                # Clean up uploaded file on task failure
                try:
                    await supabase_storage_service.delete_file(unique_filename, user_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup file after task error: {cleanup_error}")
                
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to start video processing: {str(task_error)}"
                )
            
            return VideoUploadResponse(
                success=True,
                message="Video uploaded successfully and processing started",
                job_id=str(job_id),
                file_url=file_url,
                filename=unique_filename,
                task_id=task_id
            )
            
        except Exception as e:
            logger.error(f"Failed to create job record: {str(e)}")
            # Try to cleanup uploaded file
            try:
                await supabase_storage_service.delete_file(unique_filename, user_id)
            except:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create processing job"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in video upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during video upload"
        )

@router.post("/process-url", response_model=URLProcessResponse)
async def process_url(
    url: str = Form(...),
    target_niche: Optional[str] = Form(None),
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Process video from URL"""
    try:
        # Get auth ID from token
        auth_id = token_info.get('uid')
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Get user ID from users table using auth_id
        supabase = get_supabase_admin_client()
        user_result = supabase.table("users").select("id").eq("auth_id", auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user_id = user_result.data[0]["id"]
        
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid URL format"
            )
        
        # Create job record with retry logic
        try:
            supabase = get_supabase_admin_client()
            job_data = {
                "user_id": user_id,
                "job_type": "url",
                "status": "pending",
                "title": f"Video from URL: {url}",
                "description": f"Analysis of video from URL: {url}",
                "video_url": url
            }
            
            try:
                result = supabase.table("jobs").insert(job_data).execute()
                if not result.data:
                    raise Exception("Failed to create job record - no data returned")
                
                job_id = result.data[0]["id"]
                logger.info(f"Job record created with ID: {job_id}")
                
            except Exception as job_error:
                logger.error(f"Failed to create job record: {job_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create processing job: {str(job_error)}"
                )
            
            # Start URL processing (Celery or sync fallback)
            try:
                if should_use_background_processing():
                    from api.tasks import process_url_task
                    task_result = process_url_task.delay(
                        job_id=job_id,
                        url=url,
                        target_niche=target_niche
                    )
                    task_id = task_result.id
                    job_status = 'queued'
                else:
                     # Use sync processing when Celery is unavailable
                     from api.tasks import process_url_sync
                     import asyncio
                     asyncio.create_task(process_url_sync(
                         job_id=job_id,
                         video_url=url
                     ))
                     task_id = f"sync-{job_id}"
                     job_status = 'processing'
                
                logger.info(f"URL processing started for job {job_id}: {task_id}")
                
                # Update job with task ID
                supabase.table('jobs').update({
                    'celery_task_id': task_id,
                    'status': job_status,
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', job_id).execute()
                
            except Exception as task_error:
                logger.error(f"Failed to start Celery task for job {job_id}: {task_error}")
                
                # Update job status to failed
                try:
                    supabase.table('jobs').update({
                        'status': 'failed',
                        'status_message': f'Failed to start processing: {str(task_error)}',
                        'updated_at': datetime.utcnow().isoformat()
                    }).eq('id', job_id).execute()
                except Exception as update_error:
                    logger.error(f"Failed to update job status: {update_error}")
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start video processing: {str(task_error)}"
                )
            
            return URLProcessResponse(
                success=True,
                message="URL processing job created successfully and processing started",
                job_id=str(job_id),
                url=url
            )
            
        except Exception as e:
            logger.error(f"Failed to create URL processing job: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create URL processing job"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in URL processing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during URL processing"
        )

@router.get("/", response_model=List[VideoResponse])
async def get_user_videos(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get all user videos"""
    try:
        user_id = token_info.get('uid')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        supabase = get_supabase_admin_client()
        result = supabase.table("jobs").select("*").eq("user_id", user_id).execute()
        
        videos = []
        for job in result.data:
            videos.append(VideoResponse(
                id=str(job["id"]),
                title=job.get("title", "Untitled"),
                description=job.get("description"),
                url=job.get("video_url"),
                file_path=job.get("file_path"),
                duration=job.get("duration"),
                file_size=job.get("file_size"),
                status=job.get("status", "unknown"),
                created_at=datetime.fromisoformat(job["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(job["updated_at"].replace('Z', '+00:00'))
            ))
        
        return videos
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user videos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user videos"
        )

# Global storage for chunked upload sessions
chunk_sessions = {}

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

import asyncio
import time
from functools import wraps

def retry_on_failure(max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    """Decorator for retrying failed operations with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}: {str(e)}")
                        raise last_exception
            raise last_exception
        return wrapper
    return decorator

@router.post("/upload-chunk")
@retry_on_failure(max_retries=2, delay=0.5)
async def upload_chunk(
    chunk: UploadFile = File(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    sessionId: str = Form(...),
    fileName: str = Form(...),
    target_niche: Optional[str] = Form(None),
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Handle chunked file upload with enhanced error handling and validation"""
    try:
        user_id = token_info.get('uid')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Validate input parameters
        if not sessionId or not fileName:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required parameters: sessionId or fileName"
            )
        
        if totalChunks <= 0 or totalChunks > 1000:  # Reasonable limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid totalChunks value (must be 1-1000)"
            )
        
        if chunkIndex >= totalChunks or chunkIndex < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid chunk index"
            )
        
        # Initialize session if not exists
        if sessionId not in chunk_sessions:
            chunk_sessions[sessionId] = {
                'user_id': user_id,
                'fileName': fileName,
                'totalChunks': totalChunks,
                'uploadedChunks': set(),
                'chunks': {},
                'target_niche': target_niche,
                'created_at': time.time(),
                'last_activity': time.time()
            }
        
        session = chunk_sessions[sessionId]
        
        # Validate session ownership
        if session['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to upload session"
            )
        
        # Check for session timeout (30 minutes)
        if time.time() - session['last_activity'] > 1800:
            del chunk_sessions[sessionId]
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Upload session expired. Please restart upload."
            )
        
        # Check if chunk already uploaded (idempotency)
        if chunkIndex in session['uploadedChunks']:
            logger.info(f"Chunk {chunkIndex + 1}/{totalChunks} already uploaded for session {sessionId}")
            return {
                "success": True,
                "message": f"Chunk {chunkIndex + 1}/{totalChunks} already uploaded",
                "chunkIndex": chunkIndex,
                "totalChunks": totalChunks,
                "uploadedChunks": len(session['uploadedChunks']),
                "duplicate": True
            }
        
        # Read chunk data with size validation
        chunk_data = await chunk.read()
        chunk_size = len(chunk_data)
        
        # Validate chunk size (max 2MB per chunk)
        if chunk_size > 2 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Chunk size exceeds 2MB limit"
            )
        
        if chunk_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty chunk received"
            )
        
        # Store chunk data
        session['chunks'][chunkIndex] = chunk_data
        session['uploadedChunks'].add(chunkIndex)
        session['last_activity'] = time.time()
        
        logger.info(f"Chunk {chunkIndex + 1}/{totalChunks} uploaded for session {sessionId} (size: {chunk_size} bytes)")
        
        return {
            "success": True,
            "message": f"Chunk {chunkIndex + 1}/{totalChunks} uploaded successfully",
            "chunkIndex": chunkIndex,
            "totalChunks": totalChunks,
            "uploadedChunks": len(session['uploadedChunks']),
            "chunkSize": chunk_size,
            "progress": round((len(session['uploadedChunks']) / totalChunks) * 100, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading chunk: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload chunk"
        )

@router.post("/finalize-upload")
@retry_on_failure(max_retries=2, delay=1.0)
async def finalize_upload(
    sessionId: str = Form(...),
    fileName: str = Form(...),
    totalChunks: int = Form(...),
    target_niche: Optional[str] = Form(None),
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Finalize chunked upload and start processing with enhanced error handling"""
    temp_file_path = None
    try:
        user_id = token_info.get('uid')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Validate input parameters
        if not sessionId or not fileName:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required parameters: sessionId or fileName"
            )
        
        # Check if session exists
        if sessionId not in chunk_sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload session not found or expired"
            )
        
        session = chunk_sessions[sessionId]
        
        # Validate session ownership
        if session['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to upload session"
            )
        
        # Verify all chunks are uploaded
        if len(session['uploadedChunks']) != totalChunks:
            missing_chunks = [i for i in range(totalChunks) if i not in session['uploadedChunks']]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing chunks: {missing_chunks[:10]}{'...' if len(missing_chunks) > 10 else ''}. Expected {totalChunks}, got {len(session['uploadedChunks'])}"
            )
        
        # Validate file extension
        file_extension = os.path.splitext(fileName)[1].lower()
        if file_extension not in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_extension}"
            )
        
        # Combine chunks into final file with streaming approach
        try:
            logger.info(f"Starting file assembly for session {sessionId} with {totalChunks} chunks")
            
            # Create temporary file to combine chunks
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_path = temp_file.name
                total_size = 0
                
                # Write chunks in order with memory management
                for i in range(totalChunks):
                    if i not in session['chunks']:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Missing chunk {i}"
                        )
                    
                    chunk_data = session['chunks'][i]
                    temp_file.write(chunk_data)
                    total_size += len(chunk_data)
                    
                    # Clear chunk from memory after writing to reduce memory usage
                    del session['chunks'][i]
                    
                    # Log progress for large files
                    if (i + 1) % 50 == 0 or i == totalChunks - 1:
                        logger.info(f"Assembled {i + 1}/{totalChunks} chunks ({total_size} bytes)")
            
            # Validate final file size
            file_size = os.path.getsize(temp_file_path)
            if file_size != total_size:
                raise Exception(f"File size mismatch: expected {total_size}, got {file_size}")
            
            # Check file size limits
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size {file_size} exceeds maximum allowed size of {MAX_FILE_SIZE} bytes"
                )
            
            if file_size == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assembled file is empty"
                )
            
            logger.info(f"File assembly completed: {file_size} bytes")
            
            # Generate unique filename
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Upload to Supabase storage with streaming
            supabase_storage_service = SupabaseStorageService()
            
            try:
                with open(temp_file_path, 'rb') as file_data:
                    file_url = await supabase_storage_service.upload_file(
                        file_data.read(),
                        unique_filename,
                        user_id
                    )
                logger.info(f"File uploaded to storage: {file_url}")
            except Exception as upload_error:
                logger.error(f"Failed to upload file to storage: {upload_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload file to storage: {str(upload_error)}"
                )
            
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                temp_file_path = None
            
            # Create job record with retry logic
            supabase = get_supabase_admin_client()
            job_data = {
                "user_id": user_id,
                "job_type": "upload",
                "status": "pending",
                "title": fileName,
                "description": f"Analysis of uploaded video: {fileName}",
                "video_filename": unique_filename,
                "video_url": file_url,
                "video_size": file_size,
                "target_niche": target_niche
            }
            
            try:
                result = supabase.table("jobs").insert(job_data).execute()
                if not result.data:
                    raise Exception("Failed to create job record - no data returned")
                
                job_id = result.data[0]["id"]
                logger.info(f"Job record created with ID: {job_id}")
                
            except Exception as job_error:
                logger.error(f"Failed to create job record: {job_error}")
                # Clean up uploaded file on job creation failure
                try:
                    await supabase_storage_service.delete_file(unique_filename, user_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup file after job creation error: {cleanup_error}")
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create processing job: {str(job_error)}"
                )
            
            # Start video processing (Celery or sync fallback)
            try:
                task_id = await start_video_processing(
                    job_id=job_id,
                    video_path=file_url,
                    original_filename=fileName,
                    file_size=file_size
                )
                
                logger.info(f"Video processing started for job {job_id}: {task_id}")
                
                # Update job with task ID
                status = 'queued' if should_use_background_processing() else 'processing'
                supabase.table('jobs').update({
                    'celery_task_id': task_id,
                    'status': status,
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', job_id).execute()
                
            except Exception as task_error:
                logger.error(f"Failed to start Celery task for job {job_id}: {task_error}")
                
                # Update job status to failed
                try:
                    supabase.table('jobs').update({
                        'status': 'failed',
                        'status_message': f'Failed to start processing: {str(task_error)}',
                        'updated_at': datetime.utcnow().isoformat()
                    }).eq('id', job_id).execute()
                except Exception as update_error:
                    logger.error(f"Failed to update job status: {update_error}")
                
                # Clean up uploaded file on task failure
                try:
                    await supabase_storage_service.delete_file(unique_filename, user_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup file after task error: {cleanup_error}")
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start video processing: {str(task_error)}"
                )
            
            # Clean up session after successful processing start
            try:
                del chunk_sessions[sessionId]
            except KeyError:
                logger.warning(f"Session {sessionId} already cleaned up")
            
            logger.info(f"Chunked upload finalized successfully for job {job_id}")
            
            return {
                "success": True,
                "message": "Upload completed and processing started",
                "job_id": str(job_id),
                "file_url": file_url,
                "filename": unique_filename,
                "file_size": file_size,
                "task_id": task_id
            }
            
        except Exception as e:
            # Clean up session on error
            if sessionId in chunk_sessions:
                del chunk_sessions[sessionId]
            
            # Clean up temp file if it exists
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            
            logger.error(f"Error finalizing upload: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to finalize upload: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error finalizing upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error finalizing upload"
        )

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get specific video details"""
    try:
        user_id = token_info.get('uid')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        supabase = get_supabase_admin_client()
        result = supabase.table("jobs").select("*").eq("id", video_id).eq("user_id", user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        job = result.data[0]
        return VideoResponse(
            id=str(job["id"]),
            title=job.get("title", "Untitled"),
            description=job.get("description"),
            url=job.get("video_url"),
            file_path=job.get("file_path"),
            duration=job.get("duration"),
            file_size=job.get("file_size"),
            status=job.get("status", "unknown"),
            created_at=datetime.fromisoformat(job["created_at"].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(job["updated_at"].replace('Z', '+00:00'))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve video details"
        )

@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Delete a video and its associated data"""
    try:
        user_id = token_info.get('uid')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        supabase = get_supabase_admin_client()
        
        # Check if video exists and belongs to user
        result = supabase.table("jobs").select("*").eq("id", video_id).eq("user_id", user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        job = result.data[0]
        
        # Delete file from storage if exists
        if job.get("file_path"):
            try:
                await supabase_storage_service.delete_file(job["file_path"], user_id)
            except Exception as e:
                logger.warning(f"Failed to delete file from storage: {str(e)}")
        
        # Delete job record
        delete_result = supabase.table("jobs").delete().eq("id", video_id).eq("user_id", user_id).execute()
        
        if not delete_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete video record"
            )
        
        return {"success": True, "message": "Video deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete video"
        )

@router.get("/{video_id}/analysis", response_model=VideoAnalysisResponse)
async def get_video_analysis(
    video_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get video analysis results"""
    try:
        user_id = token_info.get('uid')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        supabase = get_supabase_admin_client()
        
        # Check if video exists and belongs to user
        video_result = supabase.table("jobs").select("*").eq("id", video_id).eq("user_id", user_id).execute()
        
        if not video_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Get analysis results
        analysis_result = supabase.table("analysis_results").select("*").eq("job_id", video_id).execute()
        
        if not analysis_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis results not found"
            )
        
        analysis = analysis_result.data[0]
        
        return VideoAnalysisResponse(
            id=str(analysis["id"]),
            video_id=video_id,
            viral_score=analysis.get("viral_score", 0.0),
            segments=analysis.get("segments", []),
            metadata=analysis.get("metadata", {}),
            created_at=datetime.fromisoformat(analysis["created_at"].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(analysis["updated_at"].replace('Z', '+00:00'))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video analysis {video_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve video analysis"
        )

@router.post("/{video_id}/clips")
async def generate_clips(
    video_id: str,
    segment_ids: List[str] = Form(...),
    platforms: List[str] = Form(...),
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Generate clips from video segments"""
    try:
        user_id = token_info.get('uid')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Check if video exists and belongs to user
        supabase = get_supabase_admin_client()
        video_result = supabase.table("jobs").select("*").eq("id", video_id).eq("user_id", user_id).execute()
        
        if not video_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # TODO: Implement clip generation logic
        # For now, return a placeholder response
        
        return {
            "success": True,
            "message": "Clip generation started",
            "video_id": video_id,
            "segment_ids": segment_ids,
            "platforms": platforms
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating clips for video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate clips"
        )