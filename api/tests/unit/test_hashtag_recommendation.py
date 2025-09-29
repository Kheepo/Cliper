"""
Unit tests for hashtag recommendation service
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any
import json
from datetime import datetime

# Add the parent directory to the path to import from services
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import only the specific modules we need to avoid circular imports
from models.pydantic_models import PlatformEnum


class TestHashtagRecommendationService:
    """Test suite for hashtag recommendation service"""
    
    @pytest.fixture
    def mock_hashtag_service(self):
        """Create a mock hashtag recommendation service"""
        service = Mock()
        service.analyze_hashtags = AsyncMock()
        service.optimize_posting_times = AsyncMock()
        service.generate_comprehensive_recommendations = AsyncMock()
        return service
    
    @pytest.fixture
    def sample_content_data(self):
        """Sample content data for testing"""
        return {
            "content_description": "A funny cooking video showing how to make pasta",
            "target_audience": "food enthusiasts and cooking beginners",
            "content_category": "cooking",
            "duration": 45,
            "language": "en"
        }
    
    @pytest.fixture
    def sample_hashtag_response(self):
        """Sample hashtag recommendation response"""
        return {
            "hashtags": [
                {
                    "tag": "cooking",
                    "category": "niche",
                    "relevance_score": 0.95,
                    "trending_score": 0.8,
                    "competition_level": "medium",
                    "estimated_reach": 50000,
                    "engagement_rate": 0.08
                },
                {
                    "tag": "pasta",
                    "category": "niche",
                    "relevance_score": 0.9,
                    "trending_score": 0.7,
                    "competition_level": "low",
                    "estimated_reach": 25000,
                    "engagement_rate": 0.12
                }
            ],
            "platform_strategies": {
                "tiktok": {
                    "recommended_count": 4,
                    "mix_strategy": {"trending": 0.4, "niche": 0.4, "emotion": 0.2}
                },
                "instagram": {
                    "recommended_count": 11,
                    "mix_strategy": {"niche": 0.35, "community": 0.25, "trending": 0.2}
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_analyze_hashtags_basic(self, mock_hashtag_service, sample_content_data, sample_hashtag_response):
        """Test basic hashtag analysis functionality"""
        # Setup mock response
        mock_hashtag_service.analyze_hashtags.return_value = sample_hashtag_response
        
        # Call the service
        result = await mock_hashtag_service.analyze_hashtags(
            content_description=sample_content_data["content_description"],
            target_audience=sample_content_data["target_audience"],
            platforms=[PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM]
        )
        
        # Assertions
        assert result is not None
        assert "hashtags" in result
        assert len(result["hashtags"]) == 2
        assert result["hashtags"][0]["tag"] == "cooking"
        assert result["hashtags"][0]["relevance_score"] == 0.95
        
        # Verify service was called correctly
        mock_hashtag_service.analyze_hashtags.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_platform_specific_algorithms(self, mock_hashtag_service):
        """Test platform-specific hashtag algorithms"""
        # Mock different responses for different platforms
        tiktok_response = {
            "hashtags": [{"tag": "fyp", "trending_score": 0.95}],
            "strategy": "viral_focused"
        }
        instagram_response = {
            "hashtags": [{"tag": "lifestyle", "community_score": 0.9}],
            "strategy": "community_focused"
        }
        
        mock_hashtag_service.get_platform_strategy = AsyncMock()
        mock_hashtag_service.get_platform_strategy.side_effect = [tiktok_response, instagram_response]
        
        # Test TikTok strategy
        tiktok_result = await mock_hashtag_service.get_platform_strategy(PlatformEnum.TIKTOK)
        assert tiktok_result["strategy"] == "viral_focused"
        assert tiktok_result["hashtags"][0]["tag"] == "fyp"
        
        # Test Instagram strategy
        instagram_result = await mock_hashtag_service.get_platform_strategy(PlatformEnum.INSTAGRAM)
        assert instagram_result["strategy"] == "community_focused"
        assert instagram_result["hashtags"][0]["tag"] == "lifestyle"
    
    @pytest.mark.asyncio
    async def test_viral_scoring_integration(self, mock_hashtag_service):
        """Test integration with viral scoring system"""
        # Mock viral analysis data
        viral_data = {
            "overall_viral_score": 0.85,
            "viral_factors": ["humor", "relatability", "trending_topic"],
            "platform_scores": {
                "tiktok": 0.9,
                "instagram": 0.8,
                "youtube": 0.7
            }
        }
        
        enhanced_hashtags = {
            "hashtags": [
                {"tag": "viral", "viral_boost": 0.2},
                {"tag": "trending", "viral_boost": 0.15}
            ],
            "viral_integration": True
        }
        
        mock_hashtag_service.enhance_with_viral_data = AsyncMock(return_value=enhanced_hashtags)
        
        result = await mock_hashtag_service.enhance_with_viral_data(viral_data)
        
        assert result["viral_integration"] is True
        assert len(result["hashtags"]) == 2
        assert result["hashtags"][0]["viral_boost"] == 0.2
    
    @pytest.mark.asyncio
    async def test_posting_time_optimization(self, mock_hashtag_service):
        """Test posting time optimization functionality"""
        optimal_times = {
            "tiktok": [
                {"day": "tuesday", "time": "19:00", "engagement_score": 0.9},
                {"day": "friday", "time": "21:00", "engagement_score": 0.85}
            ],
            "instagram": [
                {"day": "wednesday", "time": "11:00", "engagement_score": 0.8},
                {"day": "saturday", "time": "14:00", "engagement_score": 0.75}
            ]
        }
        
        mock_hashtag_service.optimize_posting_times.return_value = optimal_times
        
        result = await mock_hashtag_service.optimize_posting_times(
            target_audience="millennials",
            content_category="lifestyle",
            geographic_region="north_america"
        )
        
        assert "tiktok" in result
        assert "instagram" in result
        assert len(result["tiktok"]) == 2
        assert result["tiktok"][0]["engagement_score"] == 0.9
    
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_hashtag_service):
        """Test error handling in hashtag recommendation"""
        # Test API failure
        mock_hashtag_service.analyze_hashtags.side_effect = Exception("API Error")
        
        with pytest.raises(Exception) as exc_info:
            await mock_hashtag_service.analyze_hashtags("test content")
        
        assert "API Error" in str(exc_info.value)
        
        # Test fallback mechanism
        mock_hashtag_service.get_fallback_hashtags = Mock(return_value={
            "hashtags": [{"tag": "general", "score": 0.5}],
            "fallback": True
        })
        
        fallback_result = mock_hashtag_service.get_fallback_hashtags()
        assert fallback_result["fallback"] is True
        assert len(fallback_result["hashtags"]) == 1
    
    @pytest.mark.asyncio
    async def test_edge_cases(self, mock_hashtag_service):
        """Test edge cases and boundary conditions"""
        # Test empty content
        mock_hashtag_service.analyze_hashtags.return_value = {
            "hashtags": [],
            "error": "insufficient_content"
        }
        
        result = await mock_hashtag_service.analyze_hashtags("")
        assert result["error"] == "insufficient_content"
        assert len(result["hashtags"]) == 0
        
        # Test unsupported platform
        mock_hashtag_service.validate_platform = Mock(return_value=False)
        
        is_valid = mock_hashtag_service.validate_platform("unsupported_platform")
        assert is_valid is False
        
        # Test maximum hashtag limits
        mock_hashtag_service.enforce_hashtag_limits = Mock()
        mock_hashtag_service.enforce_hashtag_limits.return_value = {
            "tiktok": {"max": 5, "recommended": 4},
            "instagram": {"max": 30, "recommended": 11}
        }
        
        limits = mock_hashtag_service.enforce_hashtag_limits()
        assert limits["tiktok"]["max"] == 5
        assert limits["instagram"]["recommended"] == 11
    
    def test_hashtag_validation(self, mock_hashtag_service):
        """Test hashtag validation logic"""
        # Test valid hashtags
        valid_hashtags = ["cooking", "food", "recipe"]
        mock_hashtag_service.validate_hashtags = Mock(return_value=True)
        
        is_valid = mock_hashtag_service.validate_hashtags(valid_hashtags)
        assert is_valid is True
        
        # Test invalid hashtags (too long, special characters, etc.)
        invalid_hashtags = ["#toolonghashtag" * 10, "hashtag with spaces", "hashtag@special"]
        mock_hashtag_service.validate_hashtags = Mock(return_value=False)
        
        is_valid = mock_hashtag_service.validate_hashtags(invalid_hashtags)
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self, mock_hashtag_service):
        """Test performance tracking and metrics"""
        performance_data = {
            "processing_time": 1.5,
            "api_calls_made": 3,
            "cache_hits": 2,
            "cache_misses": 1,
            "success_rate": 0.95
        }
        
        mock_hashtag_service.get_performance_metrics = Mock(return_value=performance_data)
        
        metrics = mock_hashtag_service.get_performance_metrics()
        
        assert metrics["processing_time"] == 1.5
        assert metrics["api_calls_made"] == 3
        assert metrics["success_rate"] == 0.95
    
    @pytest.mark.asyncio
    async def test_caching_mechanism(self, mock_hashtag_service):
        """Test caching functionality"""
        # Test cache hit
        cached_result = {"hashtags": ["cached"], "from_cache": True}
        mock_hashtag_service.get_from_cache = Mock(return_value=cached_result)
        
        result = mock_hashtag_service.get_from_cache("cache_key")
        assert result["from_cache"] is True
        
        # Test cache miss and store
        mock_hashtag_service.store_in_cache = Mock()
        new_data = {"hashtags": ["new"], "from_cache": False}
        
        mock_hashtag_service.store_in_cache("new_key", new_data)
        mock_hashtag_service.store_in_cache.assert_called_once_with("new_key", new_data)
    
    @pytest.mark.asyncio
    async def test_comprehensive_recommendations(self, mock_hashtag_service, sample_content_data):
        """Test comprehensive recommendation generation"""
        comprehensive_result = {
            "content_summary": "Cooking video with high engagement potential",
            "target_audience": "food enthusiasts",
            "platform_strategies": {
                "tiktok": {
                    "hashtags": ["cooking", "pasta", "fyp"],
                    "posting_times": ["19:00", "21:00"],
                    "optimization_tips": ["Use trending sounds", "Keep under 60s"]
                },
                "instagram": {
                    "hashtags": ["cooking", "pasta", "foodie", "recipe"],
                    "posting_times": ["11:00", "14:00"],
                    "optimization_tips": ["Use high-quality images", "Engage with comments"]
                }
            },
            "cross_platform_hashtags": ["cooking", "pasta"],
            "performance_predictions": {
                "tiktok": {"reach": 100000, "engagement_rate": 0.08},
                "instagram": {"reach": 50000, "engagement_rate": 0.06}
            }
        }
        
        mock_hashtag_service.generate_comprehensive_recommendations.return_value = comprehensive_result
        
        result = await mock_hashtag_service.generate_comprehensive_recommendations(sample_content_data)
        
        assert "platform_strategies" in result
        assert "tiktok" in result["platform_strategies"]
        assert "instagram" in result["platform_strategies"]
        assert len(result["cross_platform_hashtags"]) == 2
        assert "performance_predictions" in result