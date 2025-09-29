from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

from ..utils.supabase_client import get_supabase_admin_client
from ..middleware.auth import get_supabase_token_info_from_auth_middleware as get_supabase_token_info
from ..services.viral_scoring import ViralScoringService
from ..models.pydantic_models import ViralityScore, Hashtag, PostingRecommendation

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

# Viral Scoring Models
class ViralScoringRequest(BaseModel):
    video_id: int
    clip_segments: Optional[List[Dict[str, Any]]] = None
    platforms: Optional[List[str]] = ["tiktok", "instagram", "youtube"]
    include_insights: bool = True

class ViralScoringResponse(BaseModel):
    video_id: int
    overall_score: float
    confidence: float
    platform_scores: Dict[str, float]
    viral_moments: List[ViralityScore]
    hashtags: List[Hashtag]
    posting_recommendations: List[PostingRecommendation]
    insights: List[str]
    processing_time_ms: int
    created_at: str

class ViralAnalysisStatus(BaseModel):
    video_id: int
    status: str  # "pending", "processing", "completed", "failed"
    progress: float  # 0.0 to 1.0
    estimated_completion: Optional[str] = None
    error_message: Optional[str] = None

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

# ===== VIRAL SCORING ENDPOINTS =====

@router.post("/viral-scoring", response_model=ViralScoringResponse)
async def analyze_viral_potential(
    request: ViralScoringRequest,
    background_tasks: BackgroundTasks,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Analyze viral potential of a video or clip segments"""
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
        video_check = supabase.table('jobs').select('id, user_id, video_url, status').eq('id', request.video_id).eq('user_id', user_id).execute()
        if not video_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found or access denied"
            )
        
        video_data = video_check.data[0]
        
        # Initialize viral scoring service
        viral_service = ViralScoringService()
        
        start_time = datetime.utcnow()
        
        # Perform viral analysis
        analysis_result = await viral_service.analyze_comprehensive_viral_potential(
            video_url=video_data['video_url'],
            clip_segments=request.clip_segments,
            platforms=request.platforms,
            include_insights=request.include_insights
        )
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Store analysis result in database
        analysis_data = {
            'video_id': request.video_id,
            'user_id': user_id,
            'analysis_type': 'viral_scoring',
            'analysis_data': {
                'overall_score': analysis_result.overall_score,
                'confidence': analysis_result.confidence,
                'platform_scores': analysis_result.platform_scores,
                'viral_moments': [moment.dict() for moment in analysis_result.viral_moments],
                'hashtags': [hashtag.dict() for hashtag in analysis_result.hashtags],
                'posting_recommendations': [rec.dict() for rec in analysis_result.posting_recommendations],
                'insights': analysis_result.insights
            },
            'confidence_score': analysis_result.confidence,
            'processing_time_ms': processing_time,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Store in analysis_results table
        supabase.table('analysis_results').insert(analysis_data).execute()
        
        # Return response
        return ViralScoringResponse(
            video_id=request.video_id,
            overall_score=analysis_result.overall_score,
            confidence=analysis_result.confidence,
            platform_scores=analysis_result.platform_scores,
            viral_moments=analysis_result.viral_moments,
            hashtags=analysis_result.hashtags,
            posting_recommendations=analysis_result.posting_recommendations,
            insights=analysis_result.insights,
            processing_time_ms=processing_time,
            created_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing viral potential: {str(e)}"
        )

@router.get("/viral-scoring/{video_id}", response_model=ViralScoringResponse)
async def get_viral_analysis(
    video_id: int,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get existing viral analysis for a video"""
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
        
        # Get viral analysis result
        result = supabase.table('analysis_results').select('*').eq('video_id', video_id).eq('user_id', user_id).eq('analysis_type', 'viral_scoring').order('created_at', desc=True).limit(1).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Viral analysis not found for this video"
            )
        
        analysis = result.data[0]
        analysis_data = analysis['analysis_data']
        
        return ViralScoringResponse(
            video_id=video_id,
            overall_score=analysis_data['overall_score'],
            confidence=analysis_data['confidence'],
            platform_scores=analysis_data['platform_scores'],
            viral_moments=[ViralityScore(**moment) for moment in analysis_data['viral_moments']],
            hashtags=[Hashtag(**hashtag) for hashtag in analysis_data['hashtags']],
            posting_recommendations=[PostingRecommendation(**rec) for rec in analysis_data['posting_recommendations']],
            insights=analysis_data['insights'],
            processing_time_ms=analysis['processing_time_ms'],
            created_at=analysis['created_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving viral analysis: {str(e)}"
        )

@router.get("/viral-scoring/{video_id}/status", response_model=ViralAnalysisStatus)
async def get_viral_analysis_status(
    video_id: int,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get status of viral analysis for a video"""
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
        
        # Check if analysis exists
        result = supabase.table('analysis_results').select('*').eq('video_id', video_id).eq('user_id', user_id).eq('analysis_type', 'viral_scoring').order('created_at', desc=True).limit(1).execute()
        
        if result.data:
            return ViralAnalysisStatus(
                video_id=video_id,
                status="completed",
                progress=1.0,
                estimated_completion=None,
                error_message=None
            )
        else:
            # Check if video exists
            video_check = supabase.table('jobs').select('id, status').eq('id', video_id).eq('user_id', user_id).execute()
            if not video_check.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )
            
            return ViralAnalysisStatus(
                video_id=video_id,
                status="pending",
                progress=0.0,
                estimated_completion=None,
                error_message=None
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking viral analysis status: {str(e)}"
        )

@router.post("/viral-scoring/batch", response_model=List[ViralScoringResponse])
async def analyze_batch_viral_potential(
    video_ids: List[int],
    platforms: Optional[List[str]] = ["tiktok", "instagram", "youtube"],
    include_insights: bool = True,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Analyze viral potential for multiple videos in batch"""
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
        
        # Limit batch size
        if len(video_ids) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch size limited to 10 videos"
            )
        
        results = []
        viral_service = ViralScoringService()
        
        for video_id in video_ids:
            try:
                # Verify video belongs to user
                video_check = supabase.table('jobs').select('id, user_id, video_url').eq('id', video_id).eq('user_id', user_id).execute()
                if not video_check.data:
                    continue  # Skip videos that don't belong to user
                
                video_data = video_check.data[0]
                start_time = datetime.utcnow()
                
                # Perform viral analysis
                analysis_result = await viral_service.analyze_comprehensive_viral_potential(
                    video_url=video_data['video_url'],
                    platforms=platforms,
                    include_insights=include_insights
                )
                
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                # Store analysis result
                analysis_data = {
                    'video_id': video_id,
                    'user_id': user_id,
                    'analysis_type': 'viral_scoring',
                    'analysis_data': {
                        'overall_score': analysis_result.overall_score,
                        'confidence': analysis_result.confidence,
                        'platform_scores': analysis_result.platform_scores,
                        'viral_moments': [moment.dict() for moment in analysis_result.viral_moments],
                        'hashtags': [hashtag.dict() for hashtag in analysis_result.hashtags],
                        'posting_recommendations': [rec.dict() for rec in analysis_result.posting_recommendations],
                        'insights': analysis_result.insights
                    },
                    'confidence_score': analysis_result.confidence,
                    'processing_time_ms': processing_time,
                    'created_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                }
                
                supabase.table('analysis_results').insert(analysis_data).execute()
                
                results.append(ViralScoringResponse(
                    video_id=video_id,
                    overall_score=analysis_result.overall_score,
                    confidence=analysis_result.confidence,
                    platform_scores=analysis_result.platform_scores,
                    viral_moments=analysis_result.viral_moments,
                    hashtags=analysis_result.hashtags,
                    posting_recommendations=analysis_result.posting_recommendations,
                    insights=analysis_result.insights,
                    processing_time_ms=processing_time,
                    created_at=datetime.utcnow().isoformat()
                ))
                
            except Exception as e:
                # Log error but continue with other videos
                print(f"Error analyzing video {video_id}: {str(e)}")
                continue
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in batch viral analysis: {str(e)}"
        )