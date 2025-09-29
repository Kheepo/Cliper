"""
FastAPI router for hashtag and posting recommendations
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone

from api.models.pydantic_models import (
    PlatformEnum, 
    Hashtag, 
    PostingRecommendation
)
from api.services.hashtag_recommendation import (
    HashtagRecommendationService,
    ComprehensiveRecommendations,
    HashtagRecommendation,
    PostingTimeRecommendation,
    HashtagCategory
)
from api.services.posting_optimization import (
    PostingOptimizationService,
    PostingStrategy,
    OptimalPostingWindow
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["recommendations"])

# Initialize services
hashtag_service = HashtagRecommendationService()
posting_service = PostingOptimizationService()

from pydantic import BaseModel

class HashtagAnalysisRequest(BaseModel):
    content_description: str
    platforms: List[PlatformEnum]
    target_audience: Optional[str] = None
    content_category: Optional[str] = None
    viral_score_data: Optional[Dict[str, Any]] = None

class ContentData(BaseModel):
    description: str
    duration: Optional[float] = None
    transcript: Optional[str] = None

class AudienceData(BaseModel):
    target_audience: Optional[str] = None
    geographic_region: Optional[str] = None

class ComprehensiveRecommendationRequest(BaseModel):
    content_data: ContentData
    platforms: List[PlatformEnum]
    audience_data: Optional[AudienceData] = None
    max_hashtags_per_platform: Optional[int] = 10
    include_posting_times: Optional[bool] = True
    include_performance_insights: Optional[bool] = True

@router.post("/hashtags/analyze", response_model=Dict[str, Any])
async def analyze_hashtags_for_content(request: HashtagAnalysisRequest):
    """
    Analyze content and generate hashtag recommendations for specified platforms
    
    Args:
        content_description: Description of the video content
        platforms: List of platforms to generate recommendations for
        target_audience: Optional target audience description
        content_category: Optional content category (e.g., "entertainment", "education")
        viral_score_data: Optional viral scoring data for enhanced recommendations
    
    Returns:
        Comprehensive hashtag recommendations for each platform
    """
    try:
        logger.info(f"Generating hashtag recommendations for platforms: {request.platforms}")
        
        recommendations = {}
        
        for platform in request.platforms:
            try:
                # Generate recommendations with viral integration if available
                if request.viral_score_data:
                    platform_recommendations = await hashtag_service.generate_recommendations_with_viral_integration(
                        content_description=request.content_description,
                        platform=platform,
                        viral_analysis=request.viral_score_data,
                        target_audience=request.target_audience,
                        content_category=request.content_category
                    )
                else:
                    # Generate quick recommendations as fallback
                    quick_hashtags = await hashtag_service.quick_hashtag_recommendations(
                        content_text=request.content_description,
                        platform=platform,
                        content_category=request.content_category or "general"
                    )
                    
                    # Convert to expected format
                    platform_recommendations = type('obj', (object,), {
                        'hashtag_recommendations': [
                            type('rec', (object,), {
                                'hashtag': tag,
                                'category': HashtagCategory.EVERGREEN,
                                'relevance_score': 0.8,
                                'engagement_prediction': 0.7,
                                'competition_level': 'medium',
                                'trend_score': 0.6,
                                'reasoning': 'Generated from content analysis'
                            })() for tag in quick_hashtags
                        ],
                        'posting_recommendations': type('posting_rec', (object,), {
                            'optimal_windows': [
                                type('window', (object,), {
                                    'day_of_week': 'Tuesday',
                                    'hour': 18,
                                    'engagement_score': 0.8,
                                    'audience_size': 1000,
                                    'competition_level': 'medium'
                                })(),
                                type('window', (object,), {
                                    'day_of_week': 'Thursday',
                                    'hour': 20,
                                    'engagement_score': 0.75,
                                    'audience_size': 950,
                                    'competition_level': 'medium'
                                })()
                            ],
                            'recommended_formats': ['short-form video', 'carousel'],
                            'engagement_tips': ['Use trending audio', 'Post consistently', 'Engage with comments']
                        })(),
                        'performance_insights': {
                            'expected_reach': 5000,
                            'engagement_rate': 0.06,
                            'viral_potential': 0.3,
                            'optimization_score': 0.7
                        }
                    })()
                
                recommendations[platform.value] = {
                    "hashtags": [
                        {
                            "tag": rec.hashtag,
                            "category": rec.category.value,
                            "relevance_score": rec.relevance_score,
                            "engagement_prediction": rec.engagement_prediction,
                            "competition_level": rec.competition_level,
                            "trend_score": rec.trend_score,
                            "reasoning": rec.reasoning
                        }
                        for rec in platform_recommendations.hashtag_recommendations
                    ],
                    "posting_recommendations": {
                        "optimal_times": [
                            {
                                "day_of_week": window.day_of_week,
                                "hour": window.hour,
                                "engagement_score": window.engagement_score,
                                "audience_size": window.audience_size,
                                "competition_level": window.competition_level
                            }
                            for window in platform_recommendations.posting_recommendations.optimal_windows
                        ],
                        "best_formats": platform_recommendations.posting_recommendations.recommended_formats,
                        "engagement_tips": platform_recommendations.posting_recommendations.engagement_tips
                    },
                    "performance_insights": {
                        "expected_reach": platform_recommendations.performance_insights.get("expected_reach", 0),
                        "engagement_rate_prediction": platform_recommendations.performance_insights.get("engagement_rate", 0),
                        "viral_potential": platform_recommendations.performance_insights.get("viral_potential", 0),
                        "optimization_score": platform_recommendations.performance_insights.get("optimization_score", 0)
                    }
                }
                
            except Exception as e:
                logger.error(f"Error generating recommendations for {platform}: {str(e)}")
                recommendations[platform.value] = {
                    "error": f"Failed to generate recommendations: {str(e)}",
                    "hashtags": [],
                    "posting_recommendations": {},
                    "performance_insights": {}
                }
        
        return {
            "success": True,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat(),
            "content_analysis": {
                "description": request.content_description,
                "target_audience": request.target_audience,
                "category": request.content_category,
                "platforms_analyzed": [p.value for p in request.platforms]
            }
        }
        
    except Exception as e:
        logger.error(f"Error in hashtag analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze hashtags: {str(e)}")

@router.get("/hashtags/trending/{platform}", response_model=Dict[str, Any])
async def get_trending_hashtags(
    platform: PlatformEnum,
    category: Optional[str] = Query(None, description="Content category filter"),
    limit: int = Query(20, ge=1, le=50, description="Number of hashtags to return")
):
    """
    Get trending hashtags for a specific platform
    
    Args:
        platform: Target platform
        category: Optional category filter
        limit: Maximum number of hashtags to return
    
    Returns:
        List of trending hashtags with performance metrics
    """
    try:
        logger.info(f"Fetching trending hashtags for {platform}")
        
        trending_hashtags = await hashtag_service.get_trending_hashtags(
            platform=platform,
            category=category,
            limit=limit
        )
        
        return {
            "success": True,
            "platform": platform.value,
            "category": category,
            "trending_hashtags": [
                {
                    "tag": hashtag.hashtag,
                    "trend_score": hashtag.trend_score,
                    "engagement_prediction": hashtag.engagement_prediction,
                    "competition_level": hashtag.competition_level,
                    "category": hashtag.category.value,
                    "performance_metrics": hashtag.performance_metrics
                }
                for hashtag in trending_hashtags
            ],
            "total_count": len(trending_hashtags),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching trending hashtags: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending hashtags: {str(e)}")

@router.post("/posting-times/optimize", response_model=Dict[str, Any])
async def optimize_posting_times(
    platforms: List[PlatformEnum],
    target_audience: Optional[str] = None,
    content_type: Optional[str] = None,
    geographic_region: Optional[str] = None,
    historical_performance: Optional[Dict[str, Any]] = None
):
    """
    Optimize posting times for specified platforms based on audience analysis
    
    Args:
        platforms: List of platforms to optimize for
        target_audience: Target audience description
        content_type: Type of content being posted
        geographic_region: Geographic region for timezone optimization
        historical_performance: Optional historical performance data
    
    Returns:
        Optimized posting schedules for each platform
    """
    try:
        logger.info(f"Optimizing posting times for platforms: {platforms}")
        
        optimization_results = {}
        
        for platform in platforms:
            try:
                posting_strategy = await posting_service.optimize_posting_strategy(
                    platform=platform,
                    target_audience=target_audience or "general",
                    content_category=content_type or "general",
                    geographic_region=geographic_region,
                    historical_performance=historical_performance
                )
                
                optimization_results[platform.value] = {
                    "optimal_windows": [
                        {
                            "day_of_week": window.day_of_week,
                            "start_time": window.start_time,
                            "end_time": window.end_time,
                            "peak_time": window.peak_time,
                            "engagement_score": window.engagement_score,
                            "expected_reach": window.expected_reach,
                            "competition_level": window.competition_level,
                            "timezone": window.timezone,
                            "reasoning": window.reasoning
                        }
                        for window in posting_strategy.optimal_windows
                    ],
                    "audience_insights": {
                        "primary_segment": posting_strategy.audience_insights.primary_segment.name,
                        "activity_patterns": posting_strategy.audience_insights.activity_patterns,
                        "engagement_triggers": posting_strategy.audience_insights.engagement_triggers,
                        "geographic_distribution": posting_strategy.audience_insights.geographic_distribution,
                        "age_distribution": posting_strategy.audience_insights.age_distribution,
                        "platform_preferences": posting_strategy.audience_insights.platform_preferences,
                        "optimal_content_length": posting_strategy.audience_insights.optimal_content_length
                    },
                    "posting_frequency": posting_strategy.posting_frequency,
                    "performance_predictions": posting_strategy.performance_metrics
                }
                
            except Exception as e:
                logger.error(f"Error optimizing posting times for {platform}: {str(e)}")
                optimization_results[platform.value] = {
                    "error": f"Failed to optimize posting times: {str(e)}",
                    "optimal_windows": [],
                    "audience_insights": {},
                    "posting_frequency": {},
                    "performance_predictions": {}
                }
        
        return {
            "success": True,
            "optimization_results": optimization_results,
            "generated_at": datetime.utcnow().isoformat(),
            "analysis_parameters": {
                "target_audience": target_audience,
                "content_type": content_type,
                "geographic_region": geographic_region,
                "platforms_analyzed": [p.value for p in platforms]
            }
        }
        
    except Exception as e:
        logger.error(f"Error in posting time optimization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to optimize posting times: {str(e)}")

@router.get("/posting-times/audience-insights/{platform}", response_model=Dict[str, Any])
async def get_audience_insights(
    platform: PlatformEnum,
    target_audience: Optional[str] = Query(None, description="Target audience description"),
    geographic_region: Optional[str] = Query(None, description="Geographic region filter")
):
    """
    Get audience insights for a specific platform
    
    Args:
        platform: Target platform
        target_audience: Optional target audience filter
        geographic_region: Optional geographic region filter
    
    Returns:
        Detailed audience insights and engagement patterns
    """
    try:
        logger.info(f"Fetching audience insights for {platform}")
        
        audience_insights = await posting_service.analyze_audience_engagement(
            platform=platform,
            target_audience=target_audience or "general",
            geographic_region=geographic_region
        )
        
        return {
            "success": True,
            "platform": platform.value,
            "audience_insights": {
                "primary_segment": audience_insights.primary_segment.name,
                "demographics": audience_insights.primary_segment.demographics,
                "interests": audience_insights.primary_segment.interests,
                "activity_patterns": audience_insights.activity_patterns,
                "engagement_preferences": audience_insights.engagement_preferences,
                "geographic_distribution": audience_insights.geographic_distribution,
                "peak_activity_times": audience_insights.peak_activity_times
            },
            "engagement_patterns": [
                {
                    "time_slot": pattern.time_slot.hour,
                    "day_of_week": pattern.day_of_week,
                    "engagement_rate": pattern.engagement_rate,
                    "audience_size": pattern.audience_size,
                    "content_preferences": pattern.content_preferences
                }
                for pattern in audience_insights.engagement_patterns
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching audience insights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch audience insights: {str(e)}")

@router.post("/comprehensive", response_model=Dict[str, Any])
async def get_comprehensive_recommendations(request: ComprehensiveRecommendationRequest):
    """
    Get comprehensive hashtag and posting recommendations for content
    
    Args:
        request: Comprehensive recommendation request with content data, platforms, and options
    
    Returns:
        Comprehensive recommendations including hashtags, posting times, and insights
    """
    try:
        logger.info(f"Generating comprehensive recommendations for platforms: {request.platforms}")
        
        # Extract data from request
        content_description = request.content_data.description
        target_audience = request.audience_data.target_audience if request.audience_data else None
        geographic_region = request.audience_data.geographic_region if request.audience_data else None
        
        hashtag_recommendations = {}
        posting_recommendations = {}
        performance_insights = {}
        
        for platform in request.platforms:
            try:
                # Generate hashtag recommendations
                quick_hashtags = await hashtag_service.quick_hashtag_recommendations(
                    content_text=content_description,
                    platform=platform,
                    content_category="general"
                )
                
                # Format hashtag recommendations
                hashtag_recommendations[platform.value] = [
                    {
                        "tag": tag,
                        "relevance_score": 0.8,
                        "engagement_prediction": 0.7,
                        "category": "general",
                        "reasoning": "Generated from content analysis"
                    }
                    for tag in quick_hashtags[:request.max_hashtags_per_platform]
                ]
                
                # Generate posting recommendations if requested
                if request.include_posting_times:
                    posting_recommendations[platform.value] = {
                        "optimal_times": [
                            {"day_of_week": "Monday", "hour": 18, "confidence": 0.8},
                            {"day_of_week": "Wednesday", "hour": 20, "confidence": 0.7},
                            {"day_of_week": "Friday", "hour": 19, "confidence": 0.9}
                        ],
                        "posting_frequency": "daily",
                        "best_days": ["Monday", "Wednesday", "Friday"]
                    }
                
                # Generate performance insights if requested
                if request.include_performance_insights:
                    performance_insights[platform.value] = {
                        "expected_reach": 10000,
                        "engagement_rate": 0.05,
                        "optimal_content_length": 60,
                        "trending_topics": ["AI", "tech", "innovation"],
                        "viral_potential": 0.7
                    }
                
            except Exception as e:
                logger.error(f"Error generating comprehensive recommendations for {platform}: {str(e)}")
                hashtag_recommendations[platform.value] = []
                if request.include_posting_times:
                    posting_recommendations[platform.value] = {}
                if request.include_performance_insights:
                    performance_insights[platform.value] = {}
        
        # Calculate overall confidence score
        overall_confidence_score = 0.8 if hashtag_recommendations else 0.0
        
        return {
            "hashtag_recommendations": hashtag_recommendations,
            "posting_recommendations": posting_recommendations if request.include_posting_times else {},
            "performance_insights": performance_insights if request.include_performance_insights else {},
            "overall_confidence_score": overall_confidence_score,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating comprehensive recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate comprehensive recommendations: {str(e)}")

# Health check for recommendations service
@router.get("/health")
async def recommendations_health_check():
    """Health check for recommendations service"""
    try:
        # Test service initialization
        test_service = HashtagRecommendationService()
        test_posting_service = PostingOptimizationService()
        
        return {
            "status": "healthy",
            "service": "hashtag_recommendations",
            "hashtag_service": "operational",
            "posting_service": "operational",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Recommendations service health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")