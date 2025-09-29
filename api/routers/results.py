from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from datetime import datetime, timedelta

from ..utils.supabase_client import get_supabase_admin_client
from ..middleware.auth import get_supabase_token_info_from_auth_middleware as get_supabase_token_info

router = APIRouter(tags=["results"])

# Pydantic models
class ResultSummary(BaseModel):
    id: int
    job_id: int
    job_title: str
    virality_score: float | None = None
    processing_time_seconds: float | None = None
    created_at: str

class DetailedResult(BaseModel):
    id: int
    job_id: int
    job_title: str
    job_description: str | None = None
    virality_score: float | None = None
    engagement_metrics: dict | None = None
    content_analysis: dict | None = None
    recommendations: dict | None = None
    processing_time_seconds: float | None = None
    created_at: str

class AnalyticsResponse(BaseModel):
    total_results: int
    average_virality_score: float | None
    total_processing_time: float
    score_distribution: dict
    recent_trends: List[dict]

class ComparisonResponse(BaseModel):
    results: List[DetailedResult]
    comparison_metrics: dict

@router.get("/", response_model=List[ResultSummary])
async def get_results(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    sort_by: str = Query("created_at", regex="^(created_at|virality_score|processing_time)$")
):
    """Get user's job results with filtering and sorting"""
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
        
        # Build query for job results with job information
        query = supabase.table('job_results').select(
            'id, job_id, virality_score, processing_time_seconds, created_at, jobs!inner(title, user_id, status)'
        ).eq('jobs.user_id', user_id).eq('jobs.status', 'completed')
        
        # Apply score filters
        if min_score is not None:
            query = query.gte('virality_score', min_score)
        if max_score is not None:
            query = query.lte('virality_score', max_score)
        
        # Apply sorting
        if sort_by == "virality_score":
            query = query.order('virality_score', desc=True)
        elif sort_by == "processing_time":
            query = query.order('processing_time_seconds', desc=True)
        else:  # created_at
            query = query.order('created_at', desc=True)
        
        # Apply pagination
        results = query.range(offset, offset + limit - 1).execute()
        
        return [
            ResultSummary(
                id=result["id"],
                job_id=result["job_id"],
                job_title=result["jobs"]["title"],
                virality_score=result["virality_score"],
                processing_time_seconds=result["processing_time_seconds"],
                created_at=result["created_at"]
            )
            for result in results.data
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving results: {str(e)}"
        )

@router.get("/{result_id}", response_model=DetailedResult)
async def get_result_detail(
    result_id: int,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get detailed information about a specific result"""
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
        
        # Query with job information
        result_data = supabase.table('job_results').select(
            'id, job_id, virality_score, engagement_metrics, content_analysis, recommendations, processing_time_seconds, created_at, jobs!inner(title, description, user_id)'
        ).eq('id', result_id).eq('jobs.user_id', user_id).execute()
        
        if not result_data.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Result not found"
            )
        
        result = result_data.data[0]
        
        return DetailedResult(
            id=result["id"],
            job_id=result["job_id"],
            job_title=result["jobs"]["title"],
            job_description=result["jobs"]["description"],
            virality_score=result["virality_score"],
            engagement_metrics=result["engagement_metrics"],
            content_analysis=result["content_analysis"],
            recommendations=result["recommendations"],
            processing_time_seconds=result["processing_time_seconds"],
            created_at=result["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving result detail: {str(e)}"
        )

@router.get("/analytics/overview", response_model=AnalyticsResponse)
async def get_analytics_overview(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    days: int = Query(30, ge=1, le=365)
):
    """Get analytics overview for user's results"""
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
        
        # Date filter
        since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # Get all results for the user within the date range
        results_data = supabase.table('job_results').select(
            'id, virality_score, processing_time_seconds, created_at, jobs!inner(user_id)'
        ).eq('jobs.user_id', user_id).gte('created_at', since_date).execute()
        
        results = results_data.data
        
        # Calculate basic statistics
        total_results = len(results)
        scores = [r['virality_score'] for r in results if r['virality_score'] is not None]
        processing_times = [r['processing_time_seconds'] for r in results if r['processing_time_seconds'] is not None]
        
        avg_score = sum(scores) / len(scores) if scores else None
        total_time = sum(processing_times) if processing_times else 0
        
        # Score distribution (0-20, 20-40, 40-60, 60-80, 80-100)
        score_ranges = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
        score_distribution = {}
        
        for min_score, max_score in score_ranges:
            count = len([s for s in scores if min_score <= s < max_score])
            score_distribution[f"{min_score}-{max_score}"] = count
        
        # Recent trends (daily averages for the last 7 days)
        recent_trends = []
        for i in range(7):
            day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_results = [
                r for r in results 
                if day_start.isoformat() <= r['created_at'] < day_end.isoformat()
            ]
            
            day_scores = [r['virality_score'] for r in day_results if r['virality_score'] is not None]
            
            recent_trends.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "average_score": sum(day_scores) / len(day_scores) if day_scores else 0,
                "count": len(day_results)
            })
        
        return AnalyticsResponse(
            total_results=total_results,
            average_virality_score=avg_score,
            total_processing_time=total_time,
            score_distribution=score_distribution,
            recent_trends=list(reversed(recent_trends))  # Oldest to newest
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving analytics: {str(e)}"
        )

@router.get("/top-performing")
async def get_top_performing_results(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    limit: int = Query(10, le=50),
    days: int = Query(30, ge=1, le=365)
):
    """Get top performing results by virality score"""
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
        since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        results = supabase.table('job_results').select(
            'id, job_id, virality_score, engagement_metrics, created_at, jobs!inner(title, user_id)'
        ).eq('jobs.user_id', user_id).gte('created_at', since_date).not_.is_('virality_score', 'null').order('virality_score', desc=True).limit(limit).execute()
        
        return [
            {
                "id": result["id"],
                "job_id": result["job_id"],
                "title": result["jobs"]["title"],
                "virality_score": result["virality_score"],
                "engagement_metrics": result["engagement_metrics"],
                "created_at": result["created_at"]
            }
            for result in results.data
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving top performing results: {str(e)}"
        )

@router.post("/compare", response_model=ComparisonResponse)
async def compare_results(
    result_ids: List[int],
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Compare multiple results side by side"""
    try:
        if len(result_ids) < 2 or len(result_ids) > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only compare between 2 and 5 results"
            )
        
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
        
        # Get results with job information
        results_data = supabase.table('job_results').select(
            'id, job_id, virality_score, engagement_metrics, content_analysis, recommendations, processing_time_seconds, created_at, jobs!inner(title, description, user_id)'
        ).in_('id', result_ids).eq('jobs.user_id', user_id).execute()
        
        if len(results_data.data) != len(result_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more results not found"
            )
        
        # Build detailed results
        detailed_results = []
        scores = []
        processing_times = []
        
        for result in results_data.data:
            detailed_results.append(DetailedResult(
                id=result["id"],
                job_id=result["job_id"],
                job_title=result["jobs"]["title"],
                job_description=result["jobs"]["description"],
                virality_score=result["virality_score"],
                engagement_metrics=result["engagement_metrics"],
                content_analysis=result["content_analysis"],
                recommendations=result["recommendations"],
                processing_time_seconds=result["processing_time_seconds"],
                created_at=result["created_at"]
            ))
            
            if result["virality_score"] is not None:
                scores.append(result["virality_score"])
            if result["processing_time_seconds"] is not None:
                processing_times.append(result["processing_time_seconds"])
        
        # Calculate comparison metrics
        comparison_metrics = {
            "score_range": {
                "min": min(scores) if scores else None,
                "max": max(scores) if scores else None,
                "average": sum(scores) / len(scores) if scores else None
            },
            "processing_time_range": {
                "min": min(processing_times) if processing_times else None,
                "max": max(processing_times) if processing_times else None,
                "average": sum(processing_times) / len(processing_times) if processing_times else None
            },
            "best_performing": {
                "result_id": max(results_data.data, key=lambda x: x["virality_score"] or 0)["id"] if scores else None,
                "score": max(scores) if scores else None
            }
        }
        
        return ComparisonResponse(
            results=detailed_results,
            comparison_metrics=comparison_metrics
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error comparing results: {str(e)}"
        )

@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_result(
    result_id: int,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Delete a specific result"""
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
        
        # Check if result exists and belongs to user
        result = supabase.table('job_results').select(
            'id, jobs!inner(user_id)'
        ).eq('id', result_id).eq('jobs.user_id', user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Result not found"
            )
        
        # Delete the result
        supabase.table('job_results').delete().eq('id', result_id).execute()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting result: {str(e)}"
        )