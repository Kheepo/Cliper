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
from ..models.pydantic_models import VideoUploadResponse
from ..services.supabase_storage_service import supabase_storage_service

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

router = APIRouter(tags=["videos-simple"])

@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video_simple(
    request: Request,
    file: UploadFile = File(...),
    target_niche: Optional[str] = Form(None),
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Upload video file for processing - simplified version without ML dependencies"""
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
        
        # Create job record
        try:
            supabase = get_supabase_admin_client()
            job_data = {
                "user_id": user_id,
                "job_type": "upload",
                "status": "completed",  # Mark as completed for simple test
                "title": file.filename,
                "description": f"Simple upload test: {file.filename}",
                "video_filename": unique_filename,
                "video_url": file_url,
                "video_size": len(file_content)
            }
            
            result = supabase.table("jobs").insert(job_data).execute()
            if not result.data:
                raise Exception("Failed to create job record - no data returned")
            
            job_id = result.data[0]["id"]
            logger.info(f"Simple upload job record created with ID: {job_id}")
            
            return VideoUploadResponse(
                job_id=job_id,
                status="completed",
                message="Video uploaded successfully (simple test)",
                video_url=file_url,
                estimated_processing_time=0
            )
            
        except Exception as job_error:
            logger.error(f"Failed to create job record: {job_error}")
            # Clean up uploaded file on job creation failure
            try:
                await supabase_storage_service.delete_file(unique_filename, user_id)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup file after job creation error: {cleanup_error}")
            
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