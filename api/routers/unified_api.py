"""
Unified API Router for Cliper
Consolidates all API endpoints into a single, coherent interface
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from ..services.unified_task_processor import unified_task_processor, ProcessingOptions
from ..services.unified_ai_service import unified_ai_service
from ..services.unified_video_processor import unified_video_processor
from ..middleware.auth import get_supabase_token_info
from ..services.supabase_service import supabase_service

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class VideoUploadRequest(BaseModel):
    """Request model for video upload."""
    target_platforms: List[str] = Field(default=["tiktok", "youtube", "instagram"])
    max_clips: int = Field(default=5, ge=1, le=10)
    min_virality_score: float = Field(default=70.0, ge=0.0, le=100.0)
    generate_thumbnails: bool = Field(default=True)
    generate_hashtags: bool = Field(default=True)
    language: Optional[str] = Field(default=None)


class URLProcessingRequest(BaseModel):
    """Request model for URL processing."""
    video_url: str = Field(..., description="URL of the video to process")
    target_platforms: List[str] = Field(default=["tiktok", "youtube", "instagram"])
    max_clips: int = Field(default=5, ge=1, le=10)
    min_virality_score: float = Field(default=70.0, ge=0.0, le=100.0)
    generate_thumbnails: bool = Field(default=True)
    generate_hashtags: bool = Field(default=True)
    language: Optional[str] = Field(default=None)


class JobResponse(BaseModel):
    """Response model for job creation."""
    job_id: str
    status: str
    message: str
    estimated_time: int


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: str
    progress: int
    current_step: str
    estimated_remaining: float
    start_time: datetime
    last_update: datetime


class ClipResponse(BaseModel):
    """Response model for clip information."""
    clip_id: str
    job_id: str
    start_time: float
    end_time: float
    duration: float
    file_path: str
    thumbnail_path: Optional[str]
    virality_score: Dict[str, Any]
    title_suggestions: List[str]
    hashtags: List[str]
    description: str
    platform_optimizations: Dict[str, Any]
    file_size: int
    processing_time: float


class ProcessingStatsResponse(BaseModel):
    """Response model for processing statistics."""
    stats: Dict[str, Any]
    ai_service_status: bool
    video_processor_status: bool
    timestamp: datetime


# Health and Status Endpoints
@router.get("/health", summary="Health Check")
async def health_check():
    """Check the health of all system components."""
    try:
        health_status = await unified_task_processor.health_check()
        return JSONResponse(content=health_status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={"status": "error", "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/status", summary="System Status")
async def system_status():
    """Get detailed system status."""
    try:
        ai_health = await unified_ai_service.health_check()
        video_health = await unified_video_processor.health_check()
        stats = unified_task_processor.get_processing_stats()
        
        return JSONResponse(content={
            "ai_service": ai_health,
            "video_processor": video_health,
            "processing_stats": stats,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Video Processing Endpoints
@router.post("/videos/upload", response_model=JobResponse, summary="Upload Video for Processing")
async def upload_video(
    file: UploadFile = File(...),
    target_platforms: str = Form(default="tiktok,youtube,instagram"),
    max_clips: int = Form(default=5),
    min_virality_score: float = Form(default=70.0),
    generate_thumbnails: bool = Form(default=True),
    generate_hashtags: bool = Form(default=True),
    language: Optional[str] = Form(default=None),
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Upload a video file for AI-powered clip generation."""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file size (2GB limit)
        max_file_size = 2 * 1024 * 1024 * 1024  # 2GB
        file_content = await file.read()
        if len(file_content) > max_file_size:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 2GB.")
        
        # Reset file pointer
        await file.seek(0)
        
        # Parse target platforms
        platforms = [p.strip() for p in target_platforms.split(',')]
        valid_platforms = ['tiktok', 'youtube', 'instagram', 'twitter', 'general']
        platforms = [p for p in platforms if p in valid_platforms]
        
        if not platforms:
            platforms = ['tiktok', 'youtube', 'instagram']
        
        # Create job ID
        import uuid
        job_id = str(uuid.uuid4())
        
        # Create upload directory
        upload_dir = os.path.join("uploads", "videos", job_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save uploaded file
        video_path = os.path.join(upload_dir, file.filename)
        with open(video_path, "wb") as buffer:
            buffer.write(file_content)
        
        # Create processing options
        processing_options = ProcessingOptions(
            target_platforms=platforms,
            max_clips=max_clips,
            min_virality_score=min_virality_score,
            clip_duration_range=(15, 60),
            generate_thumbnails=generate_thumbnails,
            generate_hashtags=generate_hashtags,
            language=language
        )
        
        # Create job record
        user_id = token_info.get('user_id') or token_info.get('sub')
        job_data = {
            'id': job_id,
            'user_id': user_id,
            'filename': file.filename,
            'file_size': len(file_content),
            'file_path': video_path,
            'status': 'pending',
            'progress': 0,
            'current_step': 'Queued for processing',
            'processing_options': {
                'target_platforms': platforms,
                'max_clips': max_clips,
                'min_virality_score': min_virality_score,
                'generate_thumbnails': generate_thumbnails,
                'generate_hashtags': generate_hashtags,
                'language': language
            },
            'created_at': datetime.now().isoformat()
        }
        
        await supabase_service.create_job(job_data)
        
        # Queue background task
        from ..celery_app import process_video_unified_task
        process_video_unified_task.delay(
            job_id, video_path, file.filename, len(file_content), processing_options.__dict__
        )
        
        logger.info(f"Video upload queued: {job_id}")
        
        return JobResponse(
            job_id=job_id,
            status="pending",
            message="Video uploaded successfully and queued for processing",
            estimated_time=300  # 5 minutes estimate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/videos/process-url", response_model=JobResponse, summary="Process Video from URL")
async def process_video_url(
    request: URLProcessingRequest,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Process a video from URL for AI-powered clip generation."""
    try:
        # Create job ID
        import uuid
        job_id = str(uuid.uuid4())
        
        # Create processing options
        processing_options = ProcessingOptions(
            target_platforms=request.target_platforms,
            max_clips=request.max_clips,
            min_virality_score=request.min_virality_score,
            clip_duration_range=(15, 60),
            generate_thumbnails=request.generate_thumbnails,
            generate_hashtags=request.generate_hashtags,
            language=request.language
        )
        
        # Create job record
        user_id = token_info.get('user_id') or token_info.get('sub')
        job_data = {
            'id': job_id,
            'user_id': user_id,
            'video_url': request.video_url,
            'status': 'pending',
            'progress': 0,
            'current_step': 'Queued for URL processing',
            'processing_options': processing_options.__dict__,
            'created_at': datetime.now().isoformat()
        }
        
        await supabase_service.create_job(job_data)
        
        # Queue background task
        from ..celery_app import process_url_unified_task
        process_url_unified_task.delay(job_id, request.video_url, processing_options.__dict__)
        
        logger.info(f"URL processing queued: {job_id}")
        
        return JobResponse(
            job_id=job_id,
            status="pending",
            message="Video URL queued for processing",
            estimated_time=600  # 10 minutes estimate
        )
        
    except Exception as e:
        logger.error(f"URL processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"URL processing failed: {str(e)}")


# Job Management Endpoints
@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse, summary="Get Job Status")
async def get_job_status(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get the status of a processing job."""
    try:
        # Get job from database
        job_data = await supabase_service.get_job(job_id)
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Check if user owns the job
        user_id = token_info.get('user_id') or token_info.get('sub')
        if job_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return JobStatusResponse(
            job_id=job_id,
            status=job_data.get('status', 'unknown'),
            progress=job_data.get('progress', 0),
            current_step=job_data.get('current_step', 'Unknown'),
            estimated_remaining=job_data.get('estimated_remaining', 0.0),
            start_time=datetime.fromisoformat(job_data.get('start_time', datetime.now().isoformat())),
            last_update=datetime.fromisoformat(job_data.get('updated_at', datetime.now().isoformat()))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.get("/jobs/{job_id}/results", summary="Get Job Results")
async def get_job_results(
    job_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get the results of a completed job."""
    try:
        # Get job from database
        job_data = await supabase_service.get_job(job_id)
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Check if user owns the job
        user_id = token_info.get('user_id') or token_info.get('sub')
        if job_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get job results
        results = await supabase_service.get_job_results(job_id)
        
        return JSONResponse(content={
            "job_id": job_id,
            "status": job_data.get('status'),
            "results": results,
            "timestamp": datetime.now().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job results: {str(e)}")


@router.get("/jobs", summary="Get User Jobs")
async def get_user_jobs(
    page: int = 1,
    limit: int = 10,
    status: Optional[str] = None,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get list of user's jobs."""
    try:
        user_id = token_info.get('user_id') or token_info.get('sub')
        
        # Get jobs from database
        jobs = await supabase_service.get_user_jobs(user_id, page, limit, status)
        
        return JSONResponse(content={
            "jobs": jobs,
            "page": page,
            "limit": limit,
            "total": len(jobs),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get user jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user jobs: {str(e)}")


# Clip Management Endpoints
@router.get("/clips", summary="Get User Clips")
async def get_user_clips(
    job_id: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get list of user's generated clips."""
    try:
        user_id = token_info.get('user_id') or token_info.get('sub')
        
        # Get clips from database
        clips = await supabase_service.get_user_clips(user_id, job_id, page, limit)
        
        return JSONResponse(content={
            "clips": clips,
            "page": page,
            "limit": limit,
            "total": len(clips),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get user clips: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user clips: {str(e)}")


@router.get("/clips/{clip_id}/download", summary="Download Clip")
async def download_clip(
    clip_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Download a generated clip."""
    try:
        # Get clip from database
        clip_data = await supabase_service.get_clip(clip_id)
        
        if not clip_data:
            raise HTTPException(status_code=404, detail="Clip not found")
        
        # Check if user owns the clip
        user_id = token_info.get('user_id') or token_info.get('sub')
        if clip_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        file_path = clip_data.get('file_path')
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Clip file not found")
        
        # Return file
        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type='video/mp4'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download clip: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download clip: {str(e)}")


@router.get("/clips/{clip_id}/thumbnail", summary="Download Clip Thumbnail")
async def download_clip_thumbnail(
    clip_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Download a clip thumbnail."""
    try:
        # Get clip from database
        clip_data = await supabase_service.get_clip(clip_id)
        
        if not clip_data:
            raise HTTPException(status_code=404, detail="Clip not found")
        
        # Check if user owns the clip
        user_id = token_info.get('user_id') or token_info.get('sub')
        if clip_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        thumbnail_path = clip_data.get('thumbnail_path')
        if not thumbnail_path or not os.path.exists(thumbnail_path):
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        # Return thumbnail
        return FileResponse(
            path=thumbnail_path,
            filename=os.path.basename(thumbnail_path),
            media_type='image/jpeg'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download thumbnail: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download thumbnail: {str(e)}")


@router.delete("/clips/{clip_id}", summary="Delete Clip")
async def delete_clip(
    clip_id: str,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Delete a generated clip."""
    try:
        # Get clip from database
        clip_data = await supabase_service.get_clip(clip_id)
        
        if not clip_data:
            raise HTTPException(status_code=404, detail="Clip not found")
        
        # Check if user owns the clip
        user_id = token_info.get('user_id') or token_info.get('sub')
        if clip_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete clip files
        file_path = clip_data.get('file_path')
        thumbnail_path = clip_data.get('thumbnail_path')
        
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.unlink(thumbnail_path)
        
        # Delete from database
        await supabase_service.delete_clip(clip_id)
        
        return JSONResponse(content={
            "message": "Clip deleted successfully",
            "clip_id": clip_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete clip: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete clip: {str(e)}")


# Analytics and Statistics
@router.get("/stats", response_model=ProcessingStatsResponse, summary="Get Processing Statistics")
async def get_processing_stats(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get processing statistics."""
    try:
        stats = unified_task_processor.get_processing_stats()
        
        return ProcessingStatsResponse(
            stats=stats['stats'],
            ai_service_status=stats['ai_service_status'],
            video_processor_status=stats['video_processor_status'],
            timestamp=datetime.fromisoformat(stats['timestamp'])
        )
        
    except Exception as e:
        logger.error(f"Failed to get processing stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get processing stats: {str(e)}")


# Configuration Endpoints
@router.get("/config/platforms", summary="Get Supported Platforms")
async def get_supported_platforms():
    """Get list of supported platforms and their specifications."""
    try:
        platforms = {
            'tiktok': {
                'name': 'TikTok',
                'max_duration': 60,
                'min_duration': 15,
                'aspect_ratio': '9:16',
                'resolution': '1080x1920',
                'optimal_duration': 30,
                'engagement_factors': ['hook', 'trending', 'visual_appeal']
            },
            'youtube': {
                'name': 'YouTube Shorts',
                'max_duration': 60,
                'min_duration': 15,
                'aspect_ratio': '9:16',
                'resolution': '1080x1920',
                'optimal_duration': 45,
                'engagement_factors': ['educational', 'entertainment', 'retention']
            },
            'instagram': {
                'name': 'Instagram Reels',
                'max_duration': 90,
                'min_duration': 15,
                'aspect_ratio': '9:16',
                'resolution': '1080x1920',
                'optimal_duration': 30,
                'engagement_factors': ['aesthetic', 'lifestyle', 'shareable']
            },
            'twitter': {
                'name': 'Twitter Video',
                'max_duration': 140,
                'min_duration': 10,
                'aspect_ratio': '16:9',
                'resolution': '1280x720',
                'optimal_duration': 30,
                'engagement_factors': ['newsworthy', 'controversial', 'quotable']
            }
        }
        
        return JSONResponse(content={
            "platforms": platforms,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get platform config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get platform config: {str(e)}")


@router.get("/config/languages", summary="Get Supported Languages")
async def get_supported_languages():
    """Get list of supported languages for transcription."""
    try:
        languages = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi'
        }
        
        return JSONResponse(content={
            "languages": languages,
            "default": "en",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get language config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get language config: {str(e)}")
