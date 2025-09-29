from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from datetime import datetime

from ..utils.supabase_client import get_supabase_admin_client
from ..middleware.auth import get_supabase_token_info_from_auth_middleware as get_supabase_token_info

router = APIRouter(tags=["analysis"])

# Pydantic models
class AnalysisResultResponse(BaseModel):
    id: int
    video_id: int
    user_id: int
    analysis_type: str
    analysis_data: dict
    confidence_score: float | None = None
    processing_time_ms: int | None = None
    created_at: str
    updated_at: str

class AnalysisResultCreate(BaseModel):
    video_id: int
    analysis_type: str
    analysis_data: dict
    confidence_score: float | None = None
    processing_time_ms: int | None = None

class AnalysisResultUpdate(BaseModel):
    analysis_data: dict | None = None
    confidence_score: float | None = None
    processing_time_ms: int | None = None

class AnalysisSummary(BaseModel):
    total_analyses: int
    analysis_types: List[str]
    average_confidence: float | None
    recent_analyses: List[AnalysisResultResponse]

@router.post("/", response_model=AnalysisResultResponse)
async def create_analysis_result(
    analysis_data: AnalysisResultCreate,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Create a new analysis result"""
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
        
        # Verify video belongs to user (assuming video_id refers to a job)
        video_check = supabase.table('jobs').select('id, user_id').eq('id', analysis_data.video_id).eq('user_id', user_id).execute()
        if not video_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found or access denied"
            )
        
        # Create analysis result
        result_data = {
            'video_id': analysis_data.video_id,
            'user_id': user_id,
            'analysis_type': analysis_data.analysis_type,
            'analysis_data': analysis_data.analysis_data,
            'confidence_score': analysis_data.confidence_score,
            'processing_time_ms': analysis_data.processing_time_ms,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('analysis_results').insert(result_data).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create analysis result"
            )
        
        return AnalysisResultResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating analysis result: {str(e)}"
        )

@router.get("/", response_model=List[AnalysisResultResponse])
async def get_analysis_results(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    video_id: Optional[int] = Query(None),
    analysis_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0)
):
    """Get user's analysis results with filtering"""
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
        query = supabase.table('analysis_results').select('*').eq('user_id', user_id)
        
        # Apply filters
        if video_id:
            query = query.eq('video_id', video_id)
        if analysis_type:
            query = query.eq('analysis_type', analysis_type)
        
        # Apply pagination and ordering
        results = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        
        return [AnalysisResultResponse(**result) for result in results.data]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving analysis results: {str(e)}"
        )

@router.get("/{analysis_id}", response_model=AnalysisResultResponse)
async def get_analysis_result(
    analysis_id: int,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get a specific analysis result"""
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
        
        # Get analysis result
        result = supabase.table('analysis_results').select('*').eq('id', analysis_id).eq('user_id', user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis result not found"
            )
        
        return AnalysisResultResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving analysis result: {str(e)}"
        )

@router.put("/{analysis_id}", response_model=AnalysisResultResponse)
async def update_analysis_result(
    analysis_id: int,
    update_data: AnalysisResultUpdate,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Update an analysis result"""
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
        
        # Check if analysis result exists and belongs to user
        existing = supabase.table('analysis_results').select('*').eq('id', analysis_id).eq('user_id', user_id).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis result not found"
            )
        
        # Prepare update data
        update_fields = {}
        if update_data.analysis_data is not None:
            update_fields['analysis_data'] = update_data.analysis_data
        if update_data.confidence_score is not None:
            update_fields['confidence_score'] = update_data.confidence_score
        if update_data.processing_time_ms is not None:
            update_fields['processing_time_ms'] = update_data.processing_time_ms
        
        update_fields['updated_at'] = datetime.utcnow().isoformat()
        
        # Update analysis result
        result = supabase.table('analysis_results').update(update_fields).eq('id', analysis_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update analysis result"
            )
        
        return AnalysisResultResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating analysis result: {str(e)}"
        )

@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis_result(
    analysis_id: int,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Delete an analysis result"""
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
        
        # Check if analysis result exists and belongs to user
        existing = supabase.table('analysis_results').select('id').eq('id', analysis_id).eq('user_id', user_id).execute()
        
        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis result not found"
            )
        
        # Delete analysis result
        supabase.table('analysis_results').delete().eq('id', analysis_id).execute()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting analysis result: {str(e)}"
        )

@router.get("/summary/overview", response_model=AnalysisSummary)
async def get_analysis_summary(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    days: int = Query(30, ge=1, le=365)
):
    """Get analysis summary for user"""
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
        
        # Get all analysis results for the user
        results = supabase.table('analysis_results').select('*').eq('user_id', user_id).execute()
        
        # Calculate summary statistics
        total_analyses = len(results.data)
        analysis_types = list(set(result['analysis_type'] for result in results.data))
        
        confidence_scores = [result['confidence_score'] for result in results.data if result['confidence_score'] is not None]
        average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else None
        
        # Get recent analyses (last 5)
        recent_results = supabase.table('analysis_results').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(5).execute()
        recent_analyses = [AnalysisResultResponse(**result) for result in recent_results.data]
        
        return AnalysisSummary(
            total_analyses=total_analyses,
            analysis_types=analysis_types,
            average_confidence=average_confidence,
            recent_analyses=recent_analyses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving analysis summary: {str(e)}"
        )