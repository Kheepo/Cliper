from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, HttpUrl, Field
import uuid
import os
import mimetypes
from datetime import datetime
from loguru import logger

from ..utils.supabase_client import get_supabase_admin_client
from ..middleware.auth import get_supabase_token_info_from_auth_middleware as get_supabase_token_info
from ..models.pydantic_models import AnalysisResponse, AnalysisSegment, GeneratedClip, ClipGenerationRequest
from ..services.video_downloader import video_downloader
from ..services.supabase_storage_service import supabase_storage_service
from ..docs.openapi_config import COMMON_RESPONSES, JOB_EXAMPLES

# Video processing constants
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB in bytes
SUPPORTED_VIDEO_FORMATS = {
    'video/mp4': ['.mp4'],
    'video/quicktime': ['.mov', '.qt'],
    'video/x-msvideo': ['.avi'],
    'video/avi': ['.avi'],
    'video/x-ms-wmv': ['.wmv'],
    'video/webm': ['.webm'],
    'video/x-flv': ['.flv'],
    'video/3gpp': ['.3gp'],
    'video/x-matroska': ['.mkv']
}

ALLOWED_EXTENSIONS = {ext for exts in SUPPORTED_VIDEO_FORMATS.values() for ext in exts}

def validate_video_file(file: UploadFile, content: bytes) -> Dict[str, Any]:
    """Validate video file format, size, and other constraints"""
    validation_result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'file_info': {}
    }
    
    # Check file size
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        validation_result['valid'] = False
        validation_result['errors'].append(
            f"File size ({file_size / (1024*1024):.1f}MB) exceeds maximum allowed size (500MB)"
        )
    
    # Check file extension
    if file.filename:
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            validation_result['valid'] = False
            validation_result['errors'].append(
                f"Unsupported file extension: {file_extension}. Supported formats: {', '.join(ALLOWED_EXTENSIONS)}"
            )
    
    # Check MIME type
    if file.content_type:
        if file.content_type not in SUPPORTED_VIDEO_FORMATS:
            validation_result['valid'] = False
            validation_result['errors'].append(
                f"Unsupported MIME type: {file.content_type}. Supported types: {', '.join(SUPPORTED_VIDEO_FORMATS.keys())}"
            )
    else:
        validation_result['warnings'].append("No MIME type provided, relying on file extension")
    
    # Additional validation for video duration (placeholder for future implementation)
    validation_result['file_info'] = {
        'size_bytes': file_size,
        'size_mb': round(file_size / (1024*1024), 2),
        'filename': file.filename,
        'content_type': file.content_type,
        'extension': file_extension if file.filename else None
    }
    
    return validation_result

router = APIRouter(tags=["jobs"])

# Pydantic models
class JobResponse(BaseModel):
    """Job information response"""
    id: str = Field(..., description="Unique job identifier", example="739c34db-dc6b-496d-8ec2-fe5ce2f07e6b")
    user_id: str = Field(..., description="User ID who created the job", example="ac81901b-0b86-441f-aab2-c8915a3ce718")
    job_type: str = Field(..., description="Type of job processing", example="video_analysis")
    status: str = Field(..., description="Current job status", example="processing")
    title: str = Field(..., description="Job title", example="Marketing Video Analysis")
    description: str | None = Field(None, description="Job description", example="Analyze marketing video for viral potential")
    video_url: str | None = Field(None, description="Video URL if available", example="https://storage.example.com/videos/video123.mp4")
    file_path: str | None = Field(None, description="File path in storage", example="videos/video123.mp4")
    created_at: str = Field(..., description="Job creation timestamp", example="2024-01-20T10:30:00Z")
    updated_at: str = Field(..., description="Last update timestamp", example="2024-01-20T10:35:00Z")
    
    class Config:
        schema_extra = {
            "example": JOB_EXAMPLES["job_response"]
        }

class JobCreate(BaseModel):
    """Job creation request"""
    title: str = Field(..., description="Job title", min_length=1, max_length=200, example="Marketing Video Analysis")
    description: str | None = Field(None, description="Job description", max_length=1000, example="Analyze marketing video for viral potential and generate clips")
    job_type: str = Field("video_analysis", description="Type of job processing", example="video_analysis")
    
    class Config:
        schema_extra = {
            "example": JOB_EXAMPLES["job_create"]
        }

class JobUrlCreate(JobCreate):
    """Job creation with video URL"""
    video_url: HttpUrl = Field(..., description="Video URL to process", example="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    
    class Config:
        schema_extra = {
            "example": JOB_EXAMPLES["job_url_create"]
        }

class JobResultResponse(BaseModel):
    """Job processing result"""
    id: str = Field(..., description="Result ID", example="result-uuid-123")
    job_id: str = Field(..., description="Associated job ID", example="job-uuid-456")
    virality_score: float | None = Field(None, description="Predicted virality score (0-10)", example=8.5)
    engagement_metrics: dict | None = Field(None, description="Predicted engagement metrics")
    content_analysis: dict | None = Field(None, description="Content analysis results")
    recommendations: dict | None = Field(None, description="Optimization recommendations")
    processing_time_seconds: float | None = Field(None, description="Processing time in seconds", example=45.2)
    created_at: str = Field(..., description="Result creation timestamp", example="2024-01-20T10:35:00Z")
    
    class Config:
        schema_extra = {
            "example": JOB_EXAMPLES["job_result"]
        }

class JobLogResponse(BaseModel):
    """Job processing log entry"""
    id: str = Field(..., description="Log entry ID", example="log-uuid-123")
    job_id: str = Field(..., description="Associated job ID", example="job-uuid-456")
    level: str = Field(..., description="Log level", example="info")
    message: str = Field(..., description="Log message", example="Video analysis started")
    details: dict | None = Field(None, description="Additional log details")
    created_at: str = Field(..., description="Log timestamp", example="2024-01-20T10:30:00Z")

@router.post(
    "/upload", 
    response_model=JobResponse,
    summary="Upload Video for Analysis",
    description="""
    Upload a video file to create a new analysis job.
    
    This endpoint:
    - Accepts video file uploads up to 500MB
    - Validates file format and size
    - Stores the file securely in cloud storage
    - Creates a processing job for analysis
    - Returns job information for tracking
    
    **Supported formats**: MP4, MOV, AVI, WMV, WebM, FLV, 3GP, MKV
    **Maximum file size**: 500MB
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Job created successfully",
            "content": {
                "application/json": {
                    "example": JOB_EXAMPLES["job_response"]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def create_upload_job(
    title: str = Form(..., description="Job title", example="Marketing Video Analysis"),
    description: str = Form(None, description="Job description", example="Analyze marketing video for viral potential"),
    file: UploadFile = File(..., description="Video file to upload"),
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Read file content for validation
        content = await file.read()
        
        # Validate video file
        validation = validate_video_file(file, content)
        
        if not validation['valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "File validation failed",
                    "errors": validation['errors'],
                    "warnings": validation['warnings']
                }
            )
        
        # Generate unique filename with proper extension
        file_extension = validation['file_info']['extension'] or '.mp4'
        unique_filename = supabase_storage_service.generate_unique_filename(file.filename or f"video{file_extension}")
        
        # Upload file to Supabase Storage
        storage_path = f"videos/{unique_filename}"
        public_url = await supabase_storage_service.upload_file_content(
            file_content=content,
            destination_path=storage_path,
            content_type=file.content_type or 'video/mp4'
        )
        
        # Use storage path as file_path for database record
        file_path = storage_path
        
        # Create job record
        job_data = {
            'user_id': user_id,
            'job_type': 'upload',
            'status': 'pending',
            'title': title,
            'description': description,
            'file_path': file_path,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        job_result = supabase.table('jobs').insert(job_data).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create job"
            )
        
        job = job_result.data[0]
        
        # Create initial log with enhanced file information
        log_data = {
            'job_id': job['id'],
            'level': 'info',
            'message': 'Job created successfully',
            'details': {
                **validation['file_info'],
                'validation_warnings': validation['warnings'],
                'upload_timestamp': datetime.utcnow().isoformat()
            },
            'created_at': datetime.utcnow().isoformat()
        }
        
        supabase.table('job_logs').insert(log_data).execute()
        
        return JobResponse(**job)
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up file if it was uploaded to Supabase Storage
        if 'storage_path' in locals():
            try:
                await supabase_storage_service.delete_file(storage_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup uploaded file {storage_path}: {cleanup_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating upload job: {str(e)}"
        )

# URL validation constants
SUPPORTED_PLATFORMS = {
    'youtube.com': {'name': 'YouTube', 'patterns': [r'youtube\.com/watch\?v=', r'youtu\.be/']},
    'vimeo.com': {'name': 'Vimeo', 'patterns': [r'vimeo\.com/\d+']},
    'tiktok.com': {'name': 'TikTok', 'patterns': [r'tiktok\.com/@[^/]+/video/\d+']},
    'instagram.com': {'name': 'Instagram', 'patterns': [r'instagram\.com/p/', r'instagram\.com/reel/']},
    'twitter.com': {'name': 'Twitter', 'patterns': [r'twitter\.com/[^/]+/status/\d+']},
    'x.com': {'name': 'X (Twitter)', 'patterns': [r'x\.com/[^/]+/status/\d+']}
}

def validate_video_url(url: str) -> Dict[str, Any]:
    """Validate video URL and detect platform"""
    import re
    
    validation_result = {
        'valid': True,
        'platform': None,
        'platform_name': None,
        'errors': [],
        'warnings': []
    }
    
    url_lower = url.lower()
    
    # Check if URL matches any supported platform
    platform_found = False
    for domain, platform_info in SUPPORTED_PLATFORMS.items():
        if domain in url_lower:
            for pattern in platform_info['patterns']:
                if re.search(pattern, url_lower):
                    validation_result['platform'] = domain
                    validation_result['platform_name'] = platform_info['name']
                    platform_found = True
                    break
            if platform_found:
                break
    
    if not platform_found:
        validation_result['valid'] = False
        validation_result['errors'].append(
            f"Unsupported platform or invalid URL format. Supported platforms: {', '.join([info['name'] for info in SUPPORTED_PLATFORMS.values()])}"
        )
    
    return validation_result

@router.post("/url", response_model=JobResponse)
async def create_url_job(
    job_data: JobUrlCreate,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Create a new job by providing a video URL"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Validate video URL
        url_validation = validate_video_url(str(job_data.video_url))
        
        if not url_validation['valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "URL validation failed",
                    "errors": url_validation['errors'],
                    "warnings": url_validation['warnings']
                }
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Download video from URL
        download_result = await video_downloader.download_video(
            str(job_data.video_url), 
            url_validation['platform']
        )
        
        if not download_result['success']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Failed to download video from URL",
                    "error": download_result['error']
                }
            )
        
        # Create job record with downloaded file path
        job_record = {
            'user_id': user_id,
            'job_type': 'video_analysis',
            'status': 'pending',
            'title': job_data.title,
            'description': job_data.description,
            'video_url': str(job_data.video_url),
            'file_path': download_result['file_path'],
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        job_result = supabase.table('jobs').insert(job_record).execute()
        
        if not job_result.data:
            # Clean up downloaded file if job creation fails
            video_downloader.cleanup_file(download_result['file_path'])
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create job"
            )
        
        job = job_result.data[0]
        
        # Create initial log with platform and download information
        log_data = {
            'job_id': job['id'],
            'user_id': user_id,
            'level': 'INFO',
            'message': 'URL job created and video downloaded successfully',
            'details': {
                'video_url': str(job_data.video_url),
                'platform': url_validation['platform'],
                'platform_name': url_validation['platform_name'],
                'validation_warnings': url_validation['warnings'],
                'download_info': download_result['file_info'],
                'file_path': download_result['file_path'],
                'created_timestamp': datetime.utcnow().isoformat()
            },
            'created_at': datetime.utcnow().isoformat()
        }
        
        supabase.table('job_logs').insert(log_data).execute()
        
        return JobResponse(**job)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating URL job: {str(e)}"
        )

@router.get("/", response_model=List[JobResponse])
async def get_user_jobs(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get user's jobs with optional filtering"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Build query
        query = supabase.table('jobs').select('*').eq('user_id', user_id)
        
        if status_filter:
            # Validate status filter
            valid_statuses = ['pending', 'processing', 'completed', 'failed', 'cancelled']
            if status_filter.lower() not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}. Valid options: {', '.join(valid_statuses)}"
                )
            query = query.eq('status', status_filter.lower())
        
        # Execute query with ordering and pagination
        jobs_result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        
        return [JobResponse(**job) for job in jobs_result.data]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving jobs: {str(e)}"
        )

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get a specific job by ID"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Get job
        job_result = supabase.table('jobs').select('*').eq('id', job_id).eq('user_id', user_id).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        return JobResponse(**job_result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving job: {str(e)}"
        )

@router.get("/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get the result of a completed job"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Verify job ownership
        job_result = supabase.table('jobs').select('id').eq('id', job_id).eq('user_id', user_id).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Get job result
        result_query = supabase.table('job_results').select('*').eq('job_id', job_id).execute()
        
        if not result_query.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job result not found"
            )
        
        return JobResultResponse(**result_query.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving job result: {str(e)}"
        )

@router.get("/{job_id}/logs", response_model=List[JobLogResponse])
async def get_job_logs(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    limit: int = 100
):
    """Get logs for a specific job"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Verify job ownership
        job_result = supabase.table('jobs').select('id').eq('id', job_id).eq('user_id', user_id).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Get job logs
        logs_result = supabase.table('job_logs').select('*').eq('job_id', job_id).order('created_at', desc=True).limit(limit).execute()
        
        return [JobLogResponse(**log) for log in logs_result.data]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving job logs: {str(e)}"
        )

@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Delete a job and its associated data"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Verify job ownership and get job details
        job_result = supabase.table('jobs').select('*').eq('id', job_id).eq('user_id', user_id).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        job = job_result.data[0]
        
        # Don't allow deletion of processing jobs
        if job["status"] == "processing":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a job that is currently processing"
            )
        
        # Clean up file if it exists
        if job.get("file_path") and os.path.exists(job["file_path"]):
            os.remove(job["file_path"])
        
        # Delete associated data first (due to foreign key constraints)
        supabase.table('job_logs').delete().eq('job_id', job_id).execute()
        supabase.table('job_results').delete().eq('job_id', job_id).execute()
        
        # Delete the job
        supabase.table('jobs').delete().eq('id', job_id).execute()
        
        return {"message": "Job deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting job: {str(e)}"
        )

@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Cancel a pending or processing job"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Verify job ownership and get job details
        job_result = supabase.table('jobs').select('*').eq('id', job_id).eq('user_id', user_id).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        job = job_result.data[0]
        
        # Only allow cancellation of pending or processing jobs
        if job["status"] not in ["pending", "processing"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job with status: {job['status']}"
            )
        
        # Update job status
        supabase.table('jobs').update({
            'status': 'cancelled',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', job_id).execute()
        
        # Add cancellation log
        log_data = {
            'job_id': job_id,
            'user_id': user_id,
            'level': 'INFO',
            'message': 'Job cancelled by user',
            'created_at': datetime.utcnow().isoformat()
        }
        
        supabase.table('job_logs').insert(log_data).execute()
        
        return {"message": "Job cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling job: {str(e)}"
        )

@router.get("/{job_id}/analysis", response_model=AnalysisResponse)
async def get_job_analysis(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get detailed analysis results for a completed job"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Verify job ownership
        job_result = supabase.table('jobs').select('id, status').eq('id', job_id).eq('user_id', user_id).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        job = job_result.data[0]
        
        # Check if job is completed
        if job['status'] != 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Analysis not available for job with status: {job['status']}"
            )
        
        # Get analysis results
        analysis_result = supabase.table('analysis_results').select('*').eq('video_id', job_id).execute()
        
        if not analysis_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis results not found"
            )
        
        analysis = analysis_result.data[0]
        
        # Get analysis segments
        segments_result = supabase.table('analysis_segments').select('*').eq('analysis_id', analysis['id']).order('start_time').execute()
        
        segments = [AnalysisSegment(**segment) for segment in segments_result.data]
        
        # Build response
        response_data = {
            'id': analysis['id'],
            'job_id': job_id,  # Use the job_id parameter since analysis table has video_id
            'overall_virality_score': analysis.get('confidence_score', 0.0),  # Map confidence_score to virality_score
            'emotion_analysis': analysis.get('analysis_data', {}).get('emotion_analysis', {}),
            'face_detection_summary': analysis.get('analysis_data', {}).get('face_detection_summary', {}),
            'scene_analysis': analysis.get('analysis_data', {}).get('scene_analysis', {}),
            'transcript_summary': analysis.get('analysis_data', {}).get('transcript_summary', ''),
            'key_moments': analysis.get('analysis_data', {}).get('key_moments', []),
            'segments': segments,
            'processing_time': analysis.get('processing_time_ms', 0),
            'created_at': analysis['created_at'],
            'updated_at': analysis['updated_at']
        }
        
        return AnalysisResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving analysis: {str(e)}"
        )

@router.post("/{job_id}/generate-clips")
async def generate_clips(
    job_id: str,
    clip_request: ClipGenerationRequest,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Generate a new clip from a completed job"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Verify job ownership and status
        job_result = supabase.table('jobs').select('id, status, file_path').eq('id', job_id).eq('user_id', user_id).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        job = job_result.data[0]
        
        if job['status'] != 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate clips for job with status: {job['status']}"
            )
        
        # Validate clip timing
        if clip_request.start_time >= clip_request.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be less than end time"
            )
        
        duration = clip_request.end_time - clip_request.start_time
        if duration > 300:  # 5 minutes max
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clip duration cannot exceed 5 minutes"
            )
        
        # Create clip record
        clip_data = {
            'original_video_id': job_id,
            'title': clip_request.title,
            'description': clip_request.description or '',
            'start_time': clip_request.start_time,
            'end_time': clip_request.end_time,
            'duration': duration,
            'file_path': f"/clips/{job_id}_{int(clip_request.start_time)}_{int(clip_request.end_time)}.mp4",
            'virality_score': 0.0,  # Will be calculated during processing
            'hashtags': [],
            'posting_recommendations': {},
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        }
        
        clip_result = supabase.table('generated_clips').insert(clip_data).execute()
        
        if not clip_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create clip record"
            )
        
        # TODO: Add clip generation to processing queue
        # For now, we'll just return the clip ID
        
        return {
            "message": "Clip generation started",
            "clip_id": clip_result.data[0]['id'],
            "estimated_time": int(duration * 2)  # Rough estimate: 2 seconds per second of video
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating clip: {str(e)}"
        )

@router.get("/{job_id}/clips", response_model=List[GeneratedClip])
async def get_job_clips(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get all generated clips for a job"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Verify job ownership
        job_result = supabase.table('jobs').select('id').eq('id', job_id).eq('user_id', user_id).execute()
        
        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Get clips for this job
        clips_result = supabase.table('generated_clips').select('*').eq('original_video_id', job_id).order('created_at', desc=True).execute()
        
        # Map database fields to Pydantic model fields
        clips = []
        for clip_data in clips_result.data:
            clip = {
                'id': int(clip_data['id']) if isinstance(clip_data['id'], str) and clip_data['id'].isdigit() else hash(clip_data['id']) % (10**9),  # Convert UUID to int
                'job_id': job_id,  # Use job_id parameter since database has original_video_id
                'title': clip_data.get('title', ''),
                'description': clip_data.get('description', ''),
                'file_path': clip_data.get('file_path', ''),
                'virality_score': clip_data.get('virality_score', 0.0),
                'hashtags': clip_data.get('hashtags', []),
                'posting_recommendations': clip_data.get('posting_recommendations', {}),
                'start_time': clip_data.get('start_time', 0.0),
                'end_time': clip_data.get('end_time', 0.0),
                'duration': clip_data.get('duration', 0.0),
                'status': clip_data.get('status', 'pending'),
                'created_at': clip_data.get('created_at'),
                'updated_at': clip_data.get('updated_at')
            }
            clips.append(GeneratedClip(**clip))
        
        return clips
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving clips: {str(e)}"
        )