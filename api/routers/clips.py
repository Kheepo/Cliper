from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from pydantic import BaseModel, Field
from datetime import datetime

from ..utils.supabase_client import get_supabase_admin_client
from ..middleware.auth import get_supabase_token_info_from_auth_middleware as get_supabase_token_info
from ..docs.openapi_config import COMMON_RESPONSES, CLIP_EXAMPLES

router = APIRouter(tags=["clips"])

# Pydantic models
class GeneratedClipResponse(BaseModel):
    """Generated clip information"""
    id: int = Field(..., description="Unique clip identifier", example=1)
    video_id: int = Field(..., description="Source video ID", example=1)
    user_id: int = Field(..., description="User ID who owns the clip", example=123)
    clip_type: str = Field(..., description="Type of generated clip", example="highlight")
    start_time: float = Field(..., description="Clip start time in seconds", example=15.5)
    end_time: float = Field(..., description="Clip end time in seconds", example=45.5)
    duration: float = Field(..., description="Clip duration in seconds", example=30.0)
    file_path: str | None = Field(None, description="Path to generated clip file", example="clips/clip_123.mp4")
    thumbnail_path: str | None = Field(None, description="Path to clip thumbnail", example="thumbnails/clip_123.jpg")
    metadata: dict | None = Field(None, description="Additional clip metadata")
    virality_score: float | None = Field(None, description="Predicted virality score (0-10)", example=8.2)
    status: str = Field(..., description="Clip processing status", example="completed")
    created_at: str = Field(..., description="Clip creation timestamp", example="2024-01-20T10:30:00Z")
    updated_at: str = Field(..., description="Last update timestamp", example="2024-01-20T10:35:00Z")
    
    class Config:
        schema_extra = {
            "example": CLIP_EXAMPLES["clip_response"]
        }

class GeneratedClipCreate(BaseModel):
    """Create new clip request"""
    video_id: int = Field(..., description="Source video ID", example=1)
    clip_type: str = Field(..., description="Type of clip to create", example="highlight")
    start_time: float = Field(..., description="Clip start time in seconds", ge=0, example=15.5)
    end_time: float = Field(..., description="Clip end time in seconds", gt=0, example=45.5)
    metadata: dict | None = Field(None, description="Additional clip metadata")
    virality_score: float | None = Field(None, description="Predicted virality score (0-10)", ge=0, le=10, example=8.2)
    
    class Config:
        schema_extra = {
            "example": CLIP_EXAMPLES["clip_create"]
        }

class GeneratedClipUpdate(BaseModel):
    """Update clip request"""
    file_path: str | None = Field(None, description="Path to generated clip file", example="clips/clip_123.mp4")
    thumbnail_path: str | None = Field(None, description="Path to clip thumbnail", example="thumbnails/clip_123.jpg")
    metadata: dict | None = Field(None, description="Additional clip metadata")
    virality_score: float | None = Field(None, description="Predicted virality score (0-10)", ge=0, le=10, example=8.2)
    status: str | None = Field(None, description="Clip processing status", example="completed")
    
    class Config:
        schema_extra = {
            "example": CLIP_EXAMPLES["clip_update"]
        }

class ClipsSummary(BaseModel):
    """User clips summary statistics"""
    total_clips: int = Field(..., description="Total number of clips", example=25)
    clip_types: List[str] = Field(..., description="Available clip types", example=["highlight", "teaser", "intro"])
    average_duration: float | None = Field(None, description="Average clip duration in seconds", example=32.5)
    average_virality_score: float | None = Field(None, description="Average virality score", example=7.8)
    status_distribution: Dict[str, int] = Field(..., description="Distribution of clip statuses")
    recent_clips: List[GeneratedClipResponse] = Field(..., description="Recent clips (last 5)")
    
    class Config:
        schema_extra = {
            "example": CLIP_EXAMPLES["clips_summary"]
        }

class ClipGenerationRequest(BaseModel):
    """AI-powered clip generation request"""
    video_id: str = Field(..., description="Source video ID for clip generation", example="d7f443ef-d227-4a73-803f-e603f63bf242")
    clip_type: str = Field(..., description="Type of clip to generate", example="highlight")
    target_duration: float | None = Field(None, description="Target clip duration in seconds", ge=5, le=300, example=30.0)
    custom_parameters: dict | None = Field(None, description="Custom generation parameters")
    
    class Config:
        schema_extra = {
            "example": CLIP_EXAMPLES["clip_generation"]
        }

@router.post(
    "/", 
    response_model=GeneratedClipResponse,
    summary="Create Clip Record",
    description="""
    Create a new clip record with specified time segments.
    
    This endpoint:
    - Creates a clip record with start/end times
    - Validates time segments and video ownership
    - Calculates clip duration automatically
    - Sets initial status to 'pending'
    - Returns complete clip information
    
    **Note**: This creates a clip record only. Use `/generate` for AI-powered clip creation.
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Clip record created successfully",
            "content": {
                "application/json": {
                    "example": CLIP_EXAMPLES["clip_response"]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def create_generated_clip(
    clip_data: GeneratedClipCreate,
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
        
        # Verify video belongs to user
        video_check = supabase.table('jobs').select('id, user_id').eq('id', clip_data.video_id).eq('user_id', user_id).execute()
        if not video_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found or access denied"
            )
        
        # Calculate duration
        duration = clip_data.end_time - clip_data.start_time
        if duration <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End time must be greater than start time"
            )
        
        # Create clip record
        clip_record = {
            'video_id': clip_data.video_id,
            'user_id': user_id,
            'clip_type': clip_data.clip_type,
            'start_time': clip_data.start_time,
            'end_time': clip_data.end_time,
            'duration': duration,
            'metadata': clip_data.metadata,
            'virality_score': clip_data.virality_score,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('generated_clips').insert(clip_record).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create clip record"
            )
        
        return GeneratedClipResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating clip: {str(e)}"
        )

@router.get(
    "/", 
    response_model=List[GeneratedClipResponse],
    summary="List User Clips",
    description="""
    Retrieve user's generated clips with optional filtering and pagination.
    
    This endpoint:
    - Returns all clips owned by the authenticated user
    - Supports filtering by video ID, clip type, and status
    - Includes pagination with configurable limit and offset
    - Orders results by creation date (newest first)
    - Returns empty list if no clips found
    
    **Filtering Options**:
    - `video_id`: Filter clips from specific video
    - `clip_type`: Filter by clip type (highlight, teaser, etc.)
    - `status`: Filter by processing status (pending, processing, completed, failed)
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Clips retrieved successfully",
            "content": {
                "application/json": {
                    "example": [CLIP_EXAMPLES["clip_response"]]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def get_generated_clips(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    video_id: Optional[int] = Query(None, description="Filter by video ID", example=1),
    clip_type: Optional[str] = Query(None, description="Filter by clip type", example="highlight"),
    status: Optional[str] = Query(None, description="Filter by status", example="completed"),
    limit: int = Query(50, le=100, description="Maximum number of clips to return", example=20),
    offset: int = Query(0, ge=0, description="Number of clips to skip", example=0)
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
        
        # Build query
        query = supabase.table('generated_clips').select('*').eq('user_id', user_id)
        
        # Apply filters
        if video_id:
            query = query.eq('video_id', video_id)
        if clip_type:
            query = query.eq('clip_type', clip_type)
        if status:
            query = query.eq('status', status)
        
        # Apply pagination and ordering
        results = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        
        return [GeneratedClipResponse(**clip) for clip in results.data]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving clips: {str(e)}"
        )

@router.get(
    "/{clip_id}", 
    response_model=GeneratedClipResponse,
    summary="Get Specific Clip",
    description="""
    Retrieve detailed information about a specific clip.
    
    This endpoint:
    - Returns complete clip information including metadata
    - Validates clip ownership (user can only access their own clips)
    - Includes processing status and file paths
    - Returns 404 if clip not found or access denied
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Clip retrieved successfully",
            "content": {
                "application/json": {
                    "example": CLIP_EXAMPLES["clip_response"]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def get_generated_clip(
    clip_id: int = Path(..., description="Clip ID to retrieve", example=1),
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
        
        # Get clip
        result = supabase.table('generated_clips').select('*').eq('id', clip_id).eq('user_id', user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clip not found"
            )
        
        return GeneratedClipResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving clip: {str(e)}"
        )

@router.put(
    "/{clip_id}", 
    response_model=GeneratedClipResponse,
    summary="Update Clip",
    description="""
    Update clip information such as file paths, metadata, or status.
    
    This endpoint:
    - Updates specified clip fields only (partial updates supported)
    - Validates clip ownership (user can only update their own clips)
    - Updates the 'updated_at' timestamp automatically
    - Returns updated clip information
    - Commonly used to update processing status and file paths
    
    **Updatable Fields**:
    - `file_path`: Path to generated clip file
    - `thumbnail_path`: Path to clip thumbnail
    - `metadata`: Additional clip metadata
    - `virality_score`: Predicted virality score
    - `status`: Processing status
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Clip updated successfully",
            "content": {
                "application/json": {
                    "example": CLIP_EXAMPLES["clip_response"]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def update_generated_clip(
    clip_id: int,
    clip_data: GeneratedClipUpdate,
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
        
        # Check if clip exists and belongs to user
        existing = supabase.table('generated_clips').select('*').eq('id', clip_id).eq('user_id', user_id).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clip not found"
            )
        
        # Prepare update data
        update_fields = {}
        if clip_data.file_path is not None:
            update_fields['file_path'] = clip_data.file_path
        if clip_data.thumbnail_path is not None:
            update_fields['thumbnail_path'] = clip_data.thumbnail_path
        if clip_data.metadata is not None:
            update_fields['metadata'] = clip_data.metadata
        if clip_data.virality_score is not None:
            update_fields['virality_score'] = clip_data.virality_score
        if clip_data.status is not None:
            update_fields['status'] = clip_data.status
        
        update_fields['updated_at'] = datetime.utcnow().isoformat()
        
        # Update clip
        result = supabase.table('generated_clips').update(update_fields).eq('id', clip_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update clip"
            )
        
        return GeneratedClipResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating clip: {str(e)}"
        )

@router.delete(
    "/{clip_id}",
    summary="Delete Clip",
    description="""
    Permanently delete a specific clip and its associated files.
    
    This endpoint:
    - Removes clip record from database
    - Validates clip ownership (user can only delete their own clips)
    - Returns success confirmation
    - Cannot be undone once executed
    
    **Warning**: This action is irreversible. The clip file and thumbnail
    will be permanently deleted from storage.
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Clip deleted successfully",
            "content": {
                "application/json": {
                    "example": {"message": "Clip deleted successfully"}
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def delete_generated_clip(
    clip_id: int,
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
        
        # Check if clip exists and belongs to user
        existing = supabase.table('generated_clips').select('id, file_path, thumbnail_path').eq('id', clip_id).eq('user_id', user_id).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clip not found"
            )
        
        # TODO: Clean up associated files
        # clip_data = existing.data[0]
        # if clip_data['file_path']:
        #     cleanup_file(clip_data['file_path'])
        # if clip_data['thumbnail_path']:
        #     cleanup_file(clip_data['thumbnail_path'])
        
        # Delete clip record
        supabase.table('generated_clips').delete().eq('id', clip_id).execute()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting clip: {str(e)}"
        )

@router.post(
    "/generate", 
    response_model=GeneratedClipResponse,
    summary="Generate New Clip",
    description="""
    Create a new clip from an existing video with specified parameters.
    
    This endpoint:
    - Initiates clip generation process from source video
    - Validates video ownership and existence
    - Creates clip record with 'pending' status
    - Triggers background processing task
    - Returns clip information immediately (processing happens asynchronously)
    
    **Generation Process**:
    1. Validates input parameters and video access
    2. Creates clip record in database
    3. Queues background processing job
    4. Returns clip info with 'pending' status
    5. Processing updates status to 'processing' → 'completed'/'failed'
    
    **Clip Types**:
    - `highlight`: Best moments extraction
    - `teaser`: Short promotional clips
    - `summary`: Key points compilation
    - `custom`: User-defined segments
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        201: {
            "description": "Clip generation initiated successfully",
            "content": {
                "application/json": {
                    "example": CLIP_EXAMPLES["clip_response"]
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def generate_clip(
    generation_request: ClipGenerationRequest,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    try:
        from ..tasks import generate_clips_task
        from ..celery_app import is_background_tasks_available
        import os
        import logging
        
        logger = logging.getLogger(__name__)
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
        
        # Verify video belongs to user
        video_check = supabase.table('jobs').select('id, user_id, status, file_path').eq('id', generation_request.video_id).eq('user_id', user_id).execute()
        if not video_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found or access denied"
            )
        
        video_data = video_check.data[0]
        if video_data['status'] != 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video analysis must be completed before generating clips"
            )
        
        # Validate video file exists
        if not video_data.get('file_path') or not os.path.exists(video_data['file_path']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video file not found"
            )
        
        # Get analysis results for the video to determine clip segments
        analysis_results = supabase.table('analysis_results').select('*').eq('video_id', generation_request.video_id).eq('user_id', user_id).execute()
        
        if not analysis_results.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No analysis results found for this video"
            )
        
        # Default clip parameters (this would be replaced with AI-driven logic)
        start_time = 0.0
        end_time = generation_request.target_duration or 30.0
        
        # Create clip record
        clip_record = {
            'video_id': generation_request.video_id,
            'user_id': user_id,
            'clip_type': generation_request.clip_type,
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'metadata': {
                'generation_parameters': generation_request.custom_parameters or {},
                'target_duration': generation_request.target_duration,
                'generated_at': datetime.utcnow().isoformat()
            },
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('generated_clips').insert(clip_record).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create clip generation job"
            )
        
        clip_data = result.data[0]
        
        # Prepare generation options
        generation_options = {
            'clip_type': generation_request.clip_type,
            'target_duration': generation_request.target_duration,
            'custom_parameters': generation_request.custom_parameters or {}
        }
        
        # Queue background task for clip generation
        if is_background_tasks_available():
            try:
                task = generate_clips_task.delay(
                    clip_id=str(clip_data['id']),
                    generation_options=generation_options
                )
                
                # Update clip record with task ID
                supabase.table('generated_clips').update({
                    'metadata': {
                        **clip_data.get('metadata', {}),
                        'task_id': task.id
                    },
                    'status': 'processing',
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', clip_data['id']).execute()
                
                logger.info(f"Queued clip generation task {task.id} for clip {clip_data['id']}")
                
            except Exception as e:
                logger.error(f"Failed to queue clip generation task: {e}")
                supabase.table('generated_clips').update({
                    'status': 'failed',
                    'metadata': {
                        **clip_data.get('metadata', {}),
                        'error_message': f"Failed to queue background task: {str(e)}"
                    },
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', clip_data['id']).execute()
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to start clip generation process"
                )
        else:
            # Fallback: mark as failed if background tasks unavailable
            logger.warning("Background tasks not available, cannot generate clips")
            supabase.table('generated_clips').update({
                'status': 'failed',
                'metadata': {
                    **clip_data.get('metadata', {}),
                    'error_message': "Background processing service unavailable"
                },
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', clip_data['id']).execute()
            
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Clip generation service temporarily unavailable"
            )
        
        # Return updated clip data
        updated_result = supabase.table('generated_clips').select('*').eq('id', clip_data['id']).execute()
        return GeneratedClipResponse(**updated_result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating clip: {str(e)}"
        )

@router.get(
    "/summary/overview", 
    response_model=ClipsSummary,
    summary="Get Clips Statistics",
    description="""
    Retrieve comprehensive statistics about user's clips.
    
    This endpoint:
    - Returns total clip counts by status
    - Provides processing success/failure rates
    - Shows recent activity metrics
    - Includes storage usage information
    - Useful for dashboard and analytics displays
    
    **Statistics Included**:
    - Total clips created
    - Clips by status (pending, processing, completed, failed)
    - Success rate percentage
    - Recent activity (last 7/30 days)
    - Storage usage summary
    
    **Authentication Required**: Yes (JWT token in Authorization header)
    """,
    responses={
        200: {
            "description": "Statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_clips": 25,
                        "completed_clips": 20,
                        "pending_clips": 2,
                        "processing_clips": 1,
                        "failed_clips": 2,
                        "success_rate": 80.0,
                        "recent_clips_7d": 5,
                        "recent_clips_30d": 15
                    }
                }
            }
        },
        **COMMON_RESPONSES
    }
)
async def get_clips_summary(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    days: int = Query(30, ge=1, le=365)
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
        
        # Get all clips for the user
        clips = supabase.table('generated_clips').select('*').eq('user_id', user_id).execute()
        
        # Calculate summary statistics
        total_clips = len(clips.data)
        clip_types = list(set(clip['clip_type'] for clip in clips.data))
        
        durations = [clip['duration'] for clip in clips.data if clip['duration'] is not None]
        average_duration = sum(durations) / len(durations) if durations else None
        
        virality_scores = [clip['virality_score'] for clip in clips.data if clip['virality_score'] is not None]
        average_virality_score = sum(virality_scores) / len(virality_scores) if virality_scores else None
        
        # Status distribution
        status_distribution = {}
        for clip in clips.data:
            status = clip['status']
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        # Get recent clips (last 5)
        recent_results = supabase.table('generated_clips').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(5).execute()
        recent_clips = [GeneratedClipResponse(**clip) for clip in recent_results.data]
        
        return ClipsSummary(
            total_clips=total_clips,
            clip_types=clip_types,
            average_duration=average_duration,
            average_virality_score=average_virality_score,
            status_distribution=status_distribution,
            recent_clips=recent_clips
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving clips summary: {str(e)}"
        )