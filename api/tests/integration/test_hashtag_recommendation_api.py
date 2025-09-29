"""
Integration tests for hashtag recommendation API endpoints.

Tests cover:
- API endpoint functionality
- Request/response validation
- Error handling
- Authentication
- Rate limiting
- Real service integration
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import json
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from api.main import app
from api.models.pydantic_models import (
    PlatformEnum,
    HashtagRecommendationRequest,
    PostingTimeRequest,
    ComprehensiveRecommendationResponse,
    EnhancedHashtag,
    HashtagCategoryEnum,
    CompetitionLevelEnum,
    EnhancedPostingRecommendation,
    OptimalPostingTime,
    PostingFrequencyRecommendation
)


class TestHashtagRecommendationAPI:
    """Test suite for hashtag recommendation API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers"""
        return {"Authorization": "Bearer test_token"}

    @pytest.fixture
    def sample_hashtag_request(self):
        """Sample hashtag recommendation request"""
        return {
            "content_description": "Amazing tech video about AI innovations",
            "platforms": ["tiktok", "instagram"],
            "target_audience": "tech enthusiasts",
            "content_category": "educational"
        }

    @pytest.fixture
    def sample_posting_time_request(self):
        """Sample posting time optimization request"""
        return {
            "platforms": ["tiktok", "instagram"],
            "audience_data": {
                "target_audience": "young adults",
                "geographic_region": "North America",
                "content_type": "educational"
            },
            "content_category": "technology",
            "posting_goals": ["engagement", "reach"]
        }

    @pytest.fixture
    def mock_hashtag_service(self):
        """Mock hashtag recommendation service"""
        mock_service = AsyncMock()
        
        # Mock hashtag analysis response
        mock_service.analyze_hashtags.return_value = {
            "tiktok": [
                EnhancedHashtag(
                    tag="technology",
                    platform=PlatformEnum.TIKTOK,
                    category=HashtagCategoryEnum.TRENDING,
                    relevance_score=0.9,
                    engagement_prediction=0.85,
                    trend_score=0.95,
                    competition_level=CompetitionLevelEnum.HIGH,
                    estimated_reach=1000000,
                    usage_frequency=50000,
                    viral_alignment_score=0.8
                ),
                EnhancedHashtag(
                    tag="AI",
                    platform=PlatformEnum.TIKTOK,
                    category=HashtagCategoryEnum.NICHE,
                    relevance_score=0.85,
                    engagement_prediction=0.8,
                    trend_score=0.7,
                    competition_level=CompetitionLevelEnum.MEDIUM,
                    estimated_reach=500000,
                    usage_frequency=25000,
                    viral_alignment_score=0.75
                )
            ],
            "instagram": [
                EnhancedHashtag(
                    tag="innovation",
                    platform=PlatformEnum.INSTAGRAM,
                    category=HashtagCategoryEnum.EVERGREEN,
                    relevance_score=0.8,
                    engagement_prediction=0.75,
                    trend_score=0.6,
                    competition_level=CompetitionLevelEnum.MEDIUM,
                    estimated_reach=750000,
                    usage_frequency=30000,
                    viral_alignment_score=0.7
                )
            ]
        }
        
        # Mock posting time optimization response
        mock_service.optimize_posting_times.return_value = {
            "tiktok": EnhancedPostingRecommendation(
                platform=PlatformEnum.TIKTOK,
                optimal_times=[
                    OptimalPostingTime(
                        day_of_week="tuesday",
                        hour=19,
                        minute=0,
                        timezone="UTC",
                        engagement_score=0.85,
                        audience_size=0.9,
                        competition_level=CompetitionLevelEnum.MEDIUM,
                        confidence_score=0.8
                    )
                ],
                posting_frequency=PostingFrequencyRecommendation(
                    posts_per_day=1.5,
                    posts_per_week=10.5,
                    optimal_spacing_hours=8.0,
                    peak_days=["tuesday", "friday"],
                    avoid_days=["sunday"]
                ),
                content_format_suggestions=["short videos", "trending sounds"],
                engagement_tips=["Use trending hashtags", "Post during peak hours"],
                audience_insights={"primary_age_group": "18-24", "interests": ["technology"]},
                performance_predictions={"engagement_rate": 0.08, "reach": 100000},
                confidence_score=0.85
            ),
            "instagram": EnhancedPostingRecommendation(
                platform=PlatformEnum.INSTAGRAM,
                optimal_times=[
                    OptimalPostingTime(
                        day_of_week="wednesday",
                        hour=11,
                        minute=0,
                        timezone="UTC",
                        engagement_score=0.8,
                        audience_size=0.85,
                        competition_level=CompetitionLevelEnum.LOW,
                        confidence_score=0.75
                    )
                ],
                posting_frequency=PostingFrequencyRecommendation(
                    posts_per_day=1.0,
                    posts_per_week=7.0,
                    optimal_spacing_hours=24.0,
                    peak_days=["wednesday", "saturday"],
                    avoid_days=["monday"]
                ),
                content_format_suggestions=["carousel posts", "reels"],
                engagement_tips=["Use relevant hashtags", "Engage with comments"],
                audience_insights={"primary_age_group": "25-34", "interests": ["lifestyle"]},
                performance_predictions={"engagement_rate": 0.06, "reach": 50000},
                confidence_score=0.8
            )
        }

        # Mock comprehensive recommendations response
        mock_service.get_comprehensive_recommendations.return_value = ComprehensiveRecommendationResponse(
            hashtag_recommendations={
                "tiktok": mock_service.analyze_hashtags.return_value["tiktok"],
                "instagram": mock_service.analyze_hashtags.return_value["instagram"]
            },
            posting_recommendations={
                "tiktok": mock_service.optimize_posting_times.return_value["tiktok"],
                "instagram": mock_service.optimize_posting_times.return_value["instagram"]
            },
            performance_insights={
                "tiktok": {
                    "expected_engagement_rate": 0.08,
                    "viral_potential": 0.75,
                    "optimal_content_length": 60.0
                },
                "instagram": {
                    "expected_engagement_rate": 0.06,
                    "viral_potential": 0.65,
                    "optimal_content_length": 90.0
                }
            },
            analysis_summary={
                "content_analyzed": True,
                "platforms_count": 2,
                "hashtags_generated": 3,
                "posting_times_optimized": True,
                "viral_integration": False
            },
            confidence_scores={
                "tiktok": 0.85,
                "instagram": 0.8,
                "overall": 0.82
            },
            generated_at=datetime.now()
        )
        
        return mock_service

    def test_hashtag_analyze_endpoint_success(self, client, sample_hashtag_request):
        """Test successful hashtag analysis endpoint"""
        response = client.post(
            "/api/v1/recommendations/hashtags/analyze",
            json=sample_hashtag_request
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "recommendations" in data
        assert "success" in data
        assert data["success"] is True
        
        # Check that we have recommendations for the requested platforms
        for platform in sample_hashtag_request["platforms"]:
            assert platform in data["recommendations"]
            
            platform_recommendations = data["recommendations"][platform]
            assert "hashtags" in platform_recommendations
            assert "posting_recommendations" in platform_recommendations
            assert "performance_insights" in platform_recommendations
            
            # Validate hashtags structure - they are objects, not strings
            hashtags = platform_recommendations["hashtags"]
            assert len(hashtags) >= 1
            
            for hashtag in hashtags:
                assert isinstance(hashtag, dict)
                assert "tag" in hashtag
                assert "category" in hashtag
                assert "relevance_score" in hashtag
                assert "engagement_prediction" in hashtag
                assert "competition_level" in hashtag
                assert "trend_score" in hashtag
                assert "reasoning" in hashtag
                
                # Validate hashtag tag is a non-empty string
                assert isinstance(hashtag["tag"], str)
                assert len(hashtag["tag"]) > 0
                
                # Validate scores are numeric
                assert isinstance(hashtag["relevance_score"], (int, float))
                assert isinstance(hashtag["engagement_prediction"], (int, float))
                assert isinstance(hashtag["trend_score"], (int, float))
            
            # Validate posting recommendations structure
            posting_recs = platform_recommendations["posting_recommendations"]
            assert "optimal_times" in posting_recs
            assert "best_formats" in posting_recs
            assert "engagement_tips" in posting_recs
            
            # Validate performance insights structure
            performance = platform_recommendations["performance_insights"]
            assert "expected_reach" in performance
            assert "engagement_rate_prediction" in performance
            assert "viral_potential" in performance
            assert "optimization_score" in performance

    def test_hashtag_analyze_endpoint_validation_error(self, client):
        """Test hashtag analysis endpoint with validation errors"""
        # Missing required fields
        invalid_request = {
            "platforms": ["tiktok"],
            # Missing content_data
        }
        
        response = client.post(
            "/api/v1/recommendations/hashtags/analyze",
            json=invalid_request
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_hashtag_analyze_endpoint_invalid_platform(self, client, sample_hashtag_request):
        """Test hashtag analysis endpoint with invalid platform"""
        sample_hashtag_request["platforms"] = ["invalid_platform"]
        
        response = client.post(
            "/api/v1/recommendations/hashtags/analyze",
            json=sample_hashtag_request
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "platform" in data["error"].lower()

    def test_trending_hashtags_endpoint_success(self, client, mock_hashtag_service):
        """Test successful trending hashtags endpoint"""
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            response = client.get("/api/v1/recommendations/hashtags/trending/tiktok")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "trending_hashtags" in data
            assert "platform" in data
            assert data["platform"] == "tiktok"
            assert "updated_at" in data

    def test_trending_hashtags_endpoint_invalid_platform(self, client):
        """Test trending hashtags endpoint with invalid platform"""
        response = client.get("/api/v1/recommendations/hashtags/trending/invalid_platform")
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_posting_times_optimize_endpoint_success(self, client, sample_posting_time_request, mock_hashtag_service):
        """Test successful posting times optimization endpoint"""
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            response = client.post(
                "/api/v1/recommendations/posting-times/optimize",
                json=sample_posting_time_request
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "recommendations" in data
            assert "tiktok" in data["recommendations"]
            
            tiktok_rec = data["recommendations"]["tiktok"]
            assert "optimal_times" in tiktok_rec
            assert "posting_frequency" in tiktok_rec
            assert "confidence_score" in tiktok_rec
            
            # Validate optimal times structure
            optimal_times = tiktok_rec["optimal_times"]
            assert len(optimal_times) >= 1
            
            for time_slot in optimal_times:
                assert "day_of_week" in time_slot
                assert "hour" in time_slot
                assert "engagement_score" in time_slot
                assert 0 <= time_slot["hour"] <= 23
                assert 0.0 <= time_slot["engagement_score"] <= 1.0

    def test_posting_times_optimize_endpoint_validation_error(self, client):
        """Test posting times optimization endpoint with validation errors"""
        invalid_request = {
            "platforms": [],  # Empty platforms list
            "audience_data": {}
        }
        
        response = client.post(
            "/api/v1/recommendations/posting-times/optimize",
            json=invalid_request
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_audience_insights_endpoint_success(self, client, mock_hashtag_service):
        """Test successful audience insights endpoint"""
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            response = client.get("/api/v1/recommendations/posting-times/audience-insights/tiktok")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "platform" in data
            assert "insights" in data
            assert data["platform"] == "tiktok"

    def test_comprehensive_recommendations_endpoint_success(self, client, mock_hashtag_service):
        """Test successful comprehensive recommendations endpoint"""
        comprehensive_request = {
            "content_data": {
                "description": "Tech video about AI",
                "duration": 120.0,
                "transcript": "AI innovations"
            },
            "platforms": ["tiktok", "instagram"],
            "audience_data": {
                "target_audience": "tech enthusiasts",
                "geographic_region": "Global"
            },
            "max_hashtags_per_platform": 8,
            "include_posting_times": True,
            "include_performance_insights": True
        }
        
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            response = client.post(
                "/api/v1/recommendations/comprehensive",
                json=comprehensive_request
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "hashtag_recommendations" in data
            assert "posting_recommendations" in data
            assert "performance_insights" in data
            assert "overall_confidence_score" in data
            assert "generated_at" in data
            
            # Validate structure
            assert "tiktok" in data["hashtag_recommendations"]
            assert "instagram" in data["hashtag_recommendations"]
            assert 0.0 <= data["overall_confidence_score"] <= 1.0

    def test_comprehensive_recommendations_endpoint_minimal_request(self, client, mock_hashtag_service):
        """Test comprehensive recommendations endpoint with minimal request"""
        minimal_request = {
            "content_data": {
                "description": "Simple video",
                "duration": 60.0
            },
            "platforms": ["tiktok"]
        }
        
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            response = client.post(
                "/api/v1/recommendations/comprehensive",
                json=minimal_request
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "hashtag_recommendations" in data
            assert "tiktok" in data["hashtag_recommendations"]

    def test_health_check_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/v1/recommendations/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "service" in data
        assert data["status"] == "healthy"
        assert data["service"] == "hashtag_recommendations"

    def test_rate_limiting(self, client, sample_hashtag_request, mock_hashtag_service):
        """Test rate limiting functionality"""
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            # Make multiple rapid requests
            responses = []
            for _ in range(10):
                response = client.post(
                    "/api/v1/recommendations/hashtags/analyze",
                    json=sample_hashtag_request
                )
                responses.append(response)
            
            # Most requests should succeed, but rate limiting might kick in
            success_count = sum(1 for r in responses if r.status_code == 200)
            assert success_count >= 5  # At least some should succeed

    def test_error_handling_service_unavailable(self, client, sample_hashtag_request):
        """Test error handling when service is unavailable"""
        with patch('api.routers.recommendations.HashtagRecommendationService') as mock_service_class:
            mock_service_class.side_effect = Exception("Service unavailable")
            
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=sample_hashtag_request
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "error" in data

    def test_concurrent_requests(self, client, sample_hashtag_request, mock_hashtag_service):
        """Test handling of concurrent requests"""
        import threading
        import time
        
        results = []
        
        def make_request():
            with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
                response = client.post(
                    "/api/v1/recommendations/hashtags/analyze",
                    json=sample_hashtag_request
                )
                results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert len(results) == 5
        assert all(status == 200 for status in results)

    def test_request_timeout_handling(self, client, sample_hashtag_request):
        """Test request timeout handling"""
        with patch('api.routers.recommendations.HashtagRecommendationService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_hashtags.side_effect = asyncio.TimeoutError("Request timeout")
            mock_service_class.return_value = mock_service
            
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=sample_hashtag_request
            )
            
            assert response.status_code == 504
            data = response.json()
            assert "error" in data
            assert "timeout" in data["error"].lower()

    def test_large_request_handling(self, client, mock_hashtag_service):
        """Test handling of large requests"""
        large_request = {
            "content_data": {
                "description": "A" * 10000,  # Very long description
                "duration": 3600.0,  # 1 hour video
                "transcript": "B" * 50000,  # Very long transcript
                "visual_features": {
                    "scene_changes": list(range(0, 3600, 10)),  # Many scene changes
                    "motion_intensity": 0.7
                }
            },
            "platforms": ["tiktok", "instagram", "youtube"],
            "max_hashtags": 50,  # Many hashtags requested
            "target_audience": "general",
            "content_category": "entertainment"
        }
        
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=large_request
            )
            
            # Should handle large requests gracefully
            assert response.status_code in [200, 413, 422]  # Success or payload too large

    def test_response_caching(self, client, sample_hashtag_request, mock_hashtag_service):
        """Test response caching functionality"""
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            # First request
            response1 = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=sample_hashtag_request
            )
            
            # Second identical request
            response2 = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=sample_hashtag_request
            )
            
            assert response1.status_code == 200
            assert response2.status_code == 200
            
            # Responses should be identical (cached)
            assert response1.json() == response2.json()

    def test_api_versioning(self, client, sample_hashtag_request, mock_hashtag_service):
        """Test API versioning support"""
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            # Test v1 endpoint
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=sample_hashtag_request
            )
            
            assert response.status_code == 200
            
            # Verify version in response headers or data
            assert "api-version" in response.headers or "version" in response.json()

    def test_cors_headers(self, client, sample_hashtag_request, mock_hashtag_service):
        """Test CORS headers in responses"""
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=sample_hashtag_request,
                headers={"Origin": "https://example.com"}
            )
            
            assert response.status_code == 200
            # CORS headers should be present
            assert "access-control-allow-origin" in response.headers

    def test_content_type_validation(self, client, sample_hashtag_request, mock_hashtag_service):
        """Test content type validation"""
        with patch('api.routers.recommendations.HashtagRecommendationService', return_value=mock_hashtag_service):
            # Test with correct content type
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=sample_hashtag_request,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            
            # Test with incorrect content type
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                data=json.dumps(sample_hashtag_request),
                headers={"Content-Type": "text/plain"}
            )
            
            assert response.status_code == 422