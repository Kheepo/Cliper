"""
End-to-end tests for hashtag recommendation system.

Tests cover:
- Complete workflow from content upload to recommendations
- Integration with viral scoring system
- Real API endpoint testing
- User journey simulation
- Cross-platform recommendation consistency
- Performance in realistic scenarios
"""

import pytest
import asyncio
import json
import tempfile
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from main import app
from models.pydantic_models import PlatformEnum


class TestHashtagRecommendationE2E:
    """End-to-end test suite for hashtag recommendation system"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_video_file(self):
        """Create a mock video file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            # Write some dummy video data
            f.write(b'fake_video_data' * 1000)
            f.flush()
            yield f.name
        os.unlink(f.name)

    @pytest.fixture
    def mock_services(self):
        """Mock all external services for E2E testing"""
        mocks = {}
        
        # Mock LLM Service
        mock_llm = AsyncMock()
        mock_llm.analyze_content.return_value = {
            "topics": ["technology", "innovation", "AI", "future"],
            "sentiment": "positive",
            "keywords": ["amazing", "breakthrough", "revolutionary", "cutting-edge"],
            "content_category": "educational",
            "engagement_hooks": ["question", "surprise", "call_to_action"],
            "emotional_tone": "excited"
        }
        mock_llm.generate_hashtags.return_value = {
            "hashtags": [
                {"tag": "technology", "relevance": 0.95, "category": "trending", "engagement_potential": 0.9},
                {"tag": "AI", "relevance": 0.92, "category": "niche", "engagement_potential": 0.85},
                {"tag": "innovation", "relevance": 0.88, "category": "evergreen", "engagement_potential": 0.8},
                {"tag": "future", "relevance": 0.85, "category": "trending", "engagement_potential": 0.82},
                {"tag": "tech", "relevance": 0.83, "category": "broad", "engagement_potential": 0.75}
            ]
        }
        mocks['llm'] = mock_llm
        
        # Mock Viral Scoring Service
        mock_viral = AsyncMock()
        mock_viral.analyze_viral_potential.return_value = {
            "overall_score": 0.87,
            "viral_factors": [
                {"type": "engagement_hooks", "score": 0.9, "weight": 0.3, "description": "Strong opening question"},
                {"type": "trend_alignment", "score": 0.85, "weight": 0.25, "description": "Aligns with AI trends"},
                {"type": "emotional_impact", "score": 0.8, "weight": 0.2, "description": "Positive excitement"},
                {"type": "shareability", "score": 0.9, "weight": 0.25, "description": "Highly shareable content"}
            ],
            "platform_scores": {
                "tiktok": {"score": 0.92, "confidence": 0.88, "reasoning": "Perfect for TikTok's algorithm"},
                "instagram": {"score": 0.85, "confidence": 0.82, "reasoning": "Good visual appeal"},
                "youtube": {"score": 0.83, "confidence": 0.8, "reasoning": "Educational content performs well"}
            },
            "viral_moments": [
                {"start_time": 5.0, "end_time": 12.0, "intensity": 0.95, "type": "hook"},
                {"start_time": 45.0, "end_time": 52.0, "intensity": 0.88, "type": "revelation"},
                {"start_time": 108.0, "end_time": 115.0, "intensity": 0.92, "type": "call_to_action"}
            ],
            "optimization_suggestions": [
                "Enhance the opening hook for better retention",
                "Add more visual elements during explanation",
                "Strengthen the call-to-action at the end"
            ]
        }
        mocks['viral'] = mock_viral
        
        # Mock Posting Optimization Service
        mock_posting = AsyncMock()
        mock_posting.analyze_optimal_times.return_value = {
            "optimal_times": [
                {"day": "tuesday", "hour": 19, "minute": 0, "engagement_score": 0.92, "audience_activity": 0.95},
                {"day": "wednesday", "hour": 20, "minute": 30, "engagement_score": 0.89, "audience_activity": 0.91},
                {"day": "thursday", "hour": 18, "minute": 45, "engagement_score": 0.87, "audience_activity": 0.88},
                {"day": "saturday", "hour": 14, "minute": 15, "engagement_score": 0.85, "audience_activity": 0.86}
            ],
            "frequency_recommendation": {
                "posts_per_day": 1.2,
                "posts_per_week": 8.4,
                "optimal_spacing_hours": 20.0,
                "consistency_importance": 0.85
            },
            "audience_insights": {
                "peak_activity_hours": [18, 19, 20, 21],
                "engagement_patterns": {
                    "weekday": 0.82,
                    "weekend": 0.68,
                    "morning": 0.45,
                    "afternoon": 0.72,
                    "evening": 0.95,
                    "night": 0.38
                },
                "demographic_preferences": {
                    "age_18_24": {"peak_hours": [20, 21, 22], "engagement": 0.9},
                    "age_25_34": {"peak_hours": [19, 20, 21], "engagement": 0.85},
                    "age_35_44": {"peak_hours": [18, 19, 20], "engagement": 0.75}
                }
            }
        }
        mocks['posting'] = mock_posting
        
        return mocks

    @pytest.fixture
    def sample_user_journey_data(self):
        """Sample data for complete user journey testing"""
        return {
            "video_metadata": {
                "title": "Revolutionary AI Technology That Will Change Everything",
                "description": "Discover the latest breakthrough in artificial intelligence that's revolutionizing how we think about technology and innovation. This cutting-edge development will transform industries and create new possibilities for the future.",
                "duration": 125.5,
                "file_size": 45678901,
                "resolution": "1920x1080",
                "fps": 30
            },
            "content_analysis": {
                "transcript": "Welcome to today's video where we're diving deep into the most revolutionary AI technology that's about to change everything. This breakthrough innovation represents a quantum leap in artificial intelligence capabilities. Throughout this video, we'll explore how this technology works, its potential applications, and what it means for the future of innovation. The implications are truly mind-blowing and will transform how we approach problem-solving in every industry.",
                "visual_features": {
                    "scene_changes": [0.0, 15.5, 32.8, 48.2, 67.9, 85.1, 102.3, 118.7],
                    "motion_intensity": 0.72,
                    "color_palette": ["#1a1a1a", "#ffffff", "#0066cc", "#ff6600"],
                    "text_overlays": ["Revolutionary AI", "Game Changer", "Future Tech", "Innovation"],
                    "face_detection": [{"start": 5.0, "end": 25.0, "confidence": 0.95}]
                },
                "audio_features": {
                    "volume_levels": [0.8, 0.9, 0.85, 0.92, 0.88, 0.9, 0.87, 0.85],
                    "silence_ratio": 0.08,
                    "speech_rate": 165,  # words per minute
                    "background_music": True,
                    "sound_effects": ["whoosh", "beep", "notification"]
                }
            },
            "user_preferences": {
                "target_platforms": ["tiktok", "instagram", "youtube"],
                "target_audience": "tech enthusiasts and early adopters",
                "geographic_region": "North America and Europe",
                "content_goals": ["education", "engagement", "brand_awareness"],
                "posting_frequency": "daily",
                "brand_voice": "innovative and approachable"
            }
        }

    @pytest.mark.asyncio
    async def test_complete_user_journey(self, client, sample_user_journey_data, mock_services):
        """Test complete user journey from content upload to recommendations"""
        with patch('services.hashtag_recommendation.UnifiedLLMService', return_value=mock_services['llm']), \
             patch('services.hashtag_recommendation.ViralScoringService', return_value=mock_services['viral']), \
             patch('services.hashtag_recommendation.PostingOptimizationService', return_value=mock_services['posting']):
            
            # Step 1: Get comprehensive recommendations
            comprehensive_request = {
                "content_data": {
                    "description": sample_user_journey_data["video_metadata"]["description"],
                    "duration": sample_user_journey_data["video_metadata"]["duration"],
                    "transcript": sample_user_journey_data["content_analysis"]["transcript"],
                    "visual_features": sample_user_journey_data["content_analysis"]["visual_features"],
                    "audio_features": sample_user_journey_data["content_analysis"]["audio_features"]
                },
                "platforms": sample_user_journey_data["user_preferences"]["target_platforms"],
                "audience_data": {
                    "target_audience": sample_user_journey_data["user_preferences"]["target_audience"],
                    "geographic_region": sample_user_journey_data["user_preferences"]["geographic_region"],
                    "content_type": "educational"
                },
                "max_hashtags_per_platform": 10,
                "include_posting_times": True,
                "include_performance_insights": True
            }
            
            response = client.post(
                "/api/v1/recommendations/comprehensive",
                json=comprehensive_request
            )
            
            assert response.status_code == 200
            recommendations = response.json()
            
            # Validate comprehensive response structure
            assert "hashtag_recommendations" in recommendations
            assert "posting_recommendations" in recommendations
            assert "performance_insights" in recommendations
            assert "overall_confidence_score" in recommendations
            assert "generated_at" in recommendations
            
            # Step 2: Validate hashtag recommendations for each platform
            for platform in sample_user_journey_data["user_preferences"]["target_platforms"]:
                assert platform in recommendations["hashtag_recommendations"]
                
                platform_hashtags = recommendations["hashtag_recommendations"][platform]
                assert len(platform_hashtags) > 0
                assert len(platform_hashtags) <= 10
                
                # Validate hashtag structure
                for hashtag in platform_hashtags:
                    assert "tag" in hashtag
                    assert "platform" in hashtag
                    assert "category" in hashtag
                    assert "relevance_score" in hashtag
                    assert "engagement_prediction" in hashtag
                    assert "trend_score" in hashtag
                    assert "competition_level" in hashtag
                    
                    # Validate score ranges
                    assert 0.0 <= hashtag["relevance_score"] <= 1.0
                    assert 0.0 <= hashtag["engagement_prediction"] <= 1.0
                    assert 0.0 <= hashtag["trend_score"] <= 1.0
            
            # Step 3: Validate posting recommendations
            for platform in sample_user_journey_data["user_preferences"]["target_platforms"]:
                if platform in recommendations["posting_recommendations"]:
                    posting_rec = recommendations["posting_recommendations"][platform]
                    
                    assert "optimal_times" in posting_rec
                    assert "posting_frequency" in posting_rec
                    assert "confidence_score" in posting_rec
                    
                    # Validate optimal times
                    optimal_times = posting_rec["optimal_times"]
                    assert len(optimal_times) > 0
                    
                    for time_slot in optimal_times:
                        assert "day_of_week" in time_slot
                        assert "hour" in time_slot
                        assert "engagement_score" in time_slot
                        assert 0 <= time_slot["hour"] <= 23
                        assert 0.0 <= time_slot["engagement_score"] <= 1.0
            
            # Step 4: Validate performance insights
            performance_insights = recommendations["performance_insights"]
            assert "expected_engagement_rate" in performance_insights
            assert "viral_potential" in performance_insights
            
            # Step 5: Test individual platform analysis
            for platform in ["tiktok", "instagram"]:
                hashtag_request = {
                    "content_data": comprehensive_request["content_data"],
                    "platforms": [platform],
                    "max_hashtags": 8,
                    "target_audience": sample_user_journey_data["user_preferences"]["target_audience"]
                }
                
                response = client.post(
                    "/api/v1/recommendations/hashtags/analyze",
                    json=hashtag_request
                )
                
                assert response.status_code == 200
                platform_data = response.json()
                
                assert "recommendations" in platform_data
                assert platform in platform_data["recommendations"]
                
                platform_hashtags = platform_data["recommendations"][platform]
                assert len(platform_hashtags) <= 8
                
                # Verify hashtags are relevant to content
                hashtag_tags = [h["tag"].lower() for h in platform_hashtags]
                content_keywords = ["technology", "ai", "innovation", "future"]
                
                # At least some hashtags should relate to content
                relevant_count = sum(1 for tag in hashtag_tags 
                                   if any(keyword in tag for keyword in content_keywords))
                assert relevant_count >= 2

    @pytest.mark.asyncio
    async def test_cross_platform_consistency(self, client, sample_user_journey_data, mock_services):
        """Test consistency of recommendations across platforms"""
        with patch('services.hashtag_recommendation.UnifiedLLMService', return_value=mock_services['llm']), \
             patch('services.hashtag_recommendation.ViralScoringService', return_value=mock_services['viral']), \
             patch('services.hashtag_recommendation.PostingOptimizationService', return_value=mock_services['posting']):
            
            platforms = ["tiktok", "instagram", "youtube"]
            platform_recommendations = {}
            
            # Get recommendations for each platform individually
            for platform in platforms:
                request_data = {
                    "content_data": {
                        "description": sample_user_journey_data["video_metadata"]["description"],
                        "duration": sample_user_journey_data["video_metadata"]["duration"],
                        "transcript": sample_user_journey_data["content_analysis"]["transcript"]
                    },
                    "platforms": [platform],
                    "max_hashtags": 10,
                    "target_audience": "tech enthusiasts"
                }
                
                response = client.post(
                    "/api/v1/recommendations/hashtags/analyze",
                    json=request_data
                )
                
                assert response.status_code == 200
                data = response.json()
                platform_recommendations[platform] = data["recommendations"][platform]
            
            # Analyze cross-platform consistency
            all_hashtags = {}
            for platform, hashtags in platform_recommendations.items():
                for hashtag in hashtags:
                    tag = hashtag["tag"]
                    if tag not in all_hashtags:
                        all_hashtags[tag] = []
                    all_hashtags[tag].append({
                        "platform": platform,
                        "relevance": hashtag["relevance_score"],
                        "engagement": hashtag["engagement_prediction"]
                    })
            
            # Check for common hashtags across platforms
            common_hashtags = {tag: platforms for tag, platforms in all_hashtags.items() 
                             if len(platforms) >= 2}
            
            # Should have some common hashtags for similar content
            assert len(common_hashtags) >= 2
            
            # Verify relevance scores are consistent for common hashtags
            for tag, platform_data in common_hashtags.items():
                relevance_scores = [p["relevance"] for p in platform_data]
                score_variance = max(relevance_scores) - min(relevance_scores)
                
                # Relevance scores shouldn't vary too much across platforms for same content
                assert score_variance <= 0.3

    @pytest.mark.asyncio
    async def test_viral_scoring_integration(self, client, sample_user_journey_data, mock_services):
        """Test integration with viral scoring system"""
        with patch('services.hashtag_recommendation.UnifiedLLMService', return_value=mock_services['llm']), \
             patch('services.hashtag_recommendation.ViralScoringService', return_value=mock_services['viral']), \
             patch('services.hashtag_recommendation.PostingOptimizationService', return_value=mock_services['posting']):
            
            request_data = {
                "content_data": {
                    "description": sample_user_journey_data["video_metadata"]["description"],
                    "duration": sample_user_journey_data["video_metadata"]["duration"],
                    "transcript": sample_user_journey_data["content_analysis"]["transcript"],
                    "visual_features": sample_user_journey_data["content_analysis"]["visual_features"],
                    "audio_features": sample_user_journey_data["content_analysis"]["audio_features"]
                },
                "platforms": ["tiktok"],
                "max_hashtags": 8,
                "target_audience": "tech enthusiasts"
            }
            
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            hashtags = data["recommendations"]["tiktok"]
            
            # Verify viral scoring integration
            for hashtag in hashtags:
                # Should have viral alignment score
                if "viral_alignment_score" in hashtag:
                    assert 0.0 <= hashtag["viral_alignment_score"] <= 1.0
                
                # High viral potential content should have trending hashtags
                if hashtag["category"] == "trending":
                    assert hashtag["trend_score"] >= 0.7
            
            # Verify that viral factors influence hashtag selection
            trending_count = sum(1 for h in hashtags if h["category"] == "trending")
            assert trending_count >= 2  # Should have multiple trending hashtags for viral content

    @pytest.mark.asyncio
    async def test_posting_time_optimization_workflow(self, client, sample_user_journey_data, mock_services):
        """Test complete posting time optimization workflow"""
        with patch('services.hashtag_recommendation.UnifiedLLMService', return_value=mock_services['llm']), \
             patch('services.hashtag_recommendation.ViralScoringService', return_value=mock_services['viral']), \
             patch('services.hashtag_recommendation.PostingOptimizationService', return_value=mock_services['posting']):
            
            # Step 1: Get posting time recommendations
            posting_request = {
                "platforms": ["tiktok", "instagram"],
                "audience_data": {
                    "target_audience": sample_user_journey_data["user_preferences"]["target_audience"],
                    "geographic_region": sample_user_journey_data["user_preferences"]["geographic_region"],
                    "content_type": "educational"
                },
                "content_category": "technology",
                "posting_goals": ["engagement", "reach"]
            }
            
            response = client.post(
                "/api/v1/recommendations/posting-times/optimize",
                json=posting_request
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "recommendations" in data
            
            # Step 2: Validate posting recommendations structure
            for platform in ["tiktok", "instagram"]:
                if platform in data["recommendations"]:
                    platform_rec = data["recommendations"][platform]
                    
                    assert "optimal_times" in platform_rec
                    assert "posting_frequency" in platform_rec
                    assert "audience_insights" in platform_rec
                    assert "confidence_score" in platform_rec
                    
                    # Validate optimal times
                    optimal_times = platform_rec["optimal_times"]
                    assert len(optimal_times) >= 1
                    
                    for time_slot in optimal_times:
                        assert "day_of_week" in time_slot
                        assert "hour" in time_slot
                        assert "engagement_score" in time_slot
                        assert time_slot["day_of_week"] in [
                            "monday", "tuesday", "wednesday", "thursday", 
                            "friday", "saturday", "sunday"
                        ]
                        assert 0 <= time_slot["hour"] <= 23
                    
                    # Validate posting frequency
                    frequency = platform_rec["posting_frequency"]
                    assert "posts_per_day" in frequency
                    assert "posts_per_week" in frequency
                    assert frequency["posts_per_day"] > 0
                    assert frequency["posts_per_week"] > 0
            
            # Step 3: Get audience insights
            for platform in ["tiktok", "instagram"]:
                response = client.get(f"/api/v1/recommendations/posting-times/audience-insights/{platform}")
                
                assert response.status_code == 200
                insights_data = response.json()
                
                assert "platform" in insights_data
                assert "insights" in insights_data
                assert insights_data["platform"] == platform

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, client, sample_user_journey_data):
        """Test error handling and recovery mechanisms"""
        
        # Test 1: Invalid platform
        invalid_request = {
            "content_data": {
                "description": "Test content",
                "duration": 60.0
            },
            "platforms": ["invalid_platform"],
            "max_hashtags": 5
        }
        
        response = client.post(
            "/api/v1/recommendations/hashtags/analyze",
            json=invalid_request
        )
        
        assert response.status_code == 400
        error_data = response.json()
        assert "error" in error_data
        
        # Test 2: Missing required fields
        incomplete_request = {
            "platforms": ["tiktok"]
            # Missing content_data
        }
        
        response = client.post(
            "/api/v1/recommendations/hashtags/analyze",
            json=incomplete_request
        )
        
        assert response.status_code == 422
        
        # Test 3: Service failure simulation
        with patch('services.hashtag_recommendation.HashtagRecommendationService') as mock_service:
            mock_service.side_effect = Exception("Service temporarily unavailable")
            
            valid_request = {
                "content_data": {
                    "description": "Test content",
                    "duration": 60.0
                },
                "platforms": ["tiktok"],
                "max_hashtags": 5
            }
            
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=valid_request
            )
            
            assert response.status_code == 500
            error_data = response.json()
            assert "error" in error_data

    @pytest.mark.asyncio
    async def test_performance_in_realistic_scenario(self, client, sample_user_journey_data, mock_services):
        """Test performance with realistic content and usage patterns"""
        with patch('services.hashtag_recommendation.UnifiedLLMService', return_value=mock_services['llm']), \
             patch('services.hashtag_recommendation.ViralScoringService', return_value=mock_services['viral']), \
             patch('services.hashtag_recommendation.PostingOptimizationService', return_value=mock_services['posting']):
            
            import time
            
            # Simulate realistic user workflow
            start_time = time.time()
            
            # Step 1: Comprehensive analysis
            comprehensive_request = {
                "content_data": {
                    "description": sample_user_journey_data["video_metadata"]["description"],
                    "duration": sample_user_journey_data["video_metadata"]["duration"],
                    "transcript": sample_user_journey_data["content_analysis"]["transcript"],
                    "visual_features": sample_user_journey_data["content_analysis"]["visual_features"],
                    "audio_features": sample_user_journey_data["content_analysis"]["audio_features"]
                },
                "platforms": ["tiktok", "instagram", "youtube"],
                "audience_data": {
                    "target_audience": sample_user_journey_data["user_preferences"]["target_audience"],
                    "geographic_region": sample_user_journey_data["user_preferences"]["geographic_region"],
                    "content_type": "educational"
                },
                "max_hashtags_per_platform": 12,
                "include_posting_times": True,
                "include_performance_insights": True
            }
            
            response = client.post(
                "/api/v1/recommendations/comprehensive",
                json=comprehensive_request
            )
            
            comprehensive_time = time.time() - start_time
            
            assert response.status_code == 200
            assert comprehensive_time < 5.0  # Should complete within 5 seconds
            
            # Step 2: Individual platform refinements
            platform_times = []
            
            for platform in ["tiktok", "instagram"]:
                start_time = time.time()
                
                platform_request = {
                    "content_data": comprehensive_request["content_data"],
                    "platforms": [platform],
                    "max_hashtags": 8,
                    "target_audience": sample_user_journey_data["user_preferences"]["target_audience"]
                }
                
                response = client.post(
                    "/api/v1/recommendations/hashtags/analyze",
                    json=platform_request
                )
                
                platform_time = time.time() - start_time
                platform_times.append(platform_time)
                
                assert response.status_code == 200
                assert platform_time < 2.0  # Individual platform analysis should be faster
            
            # Step 3: Posting time optimization
            start_time = time.time()
            
            posting_request = {
                "platforms": ["tiktok", "instagram"],
                "audience_data": comprehensive_request["audience_data"],
                "content_category": "technology"
            }
            
            response = client.post(
                "/api/v1/recommendations/posting-times/optimize",
                json=posting_request
            )
            
            posting_time = time.time() - start_time
            
            assert response.status_code == 200
            assert posting_time < 3.0  # Posting optimization should complete quickly
            
            print(f"Performance Results:")
            print(f"Comprehensive analysis: {comprehensive_time:.3f}s")
            print(f"Platform analysis (avg): {sum(platform_times)/len(platform_times):.3f}s")
            print(f"Posting optimization: {posting_time:.3f}s")

    @pytest.mark.asyncio
    async def test_recommendation_quality_validation(self, client, sample_user_journey_data, mock_services):
        """Test the quality and relevance of generated recommendations"""
        with patch('services.hashtag_recommendation.UnifiedLLMService', return_value=mock_services['llm']), \
             patch('services.hashtag_recommendation.ViralScoringService', return_value=mock_services['viral']), \
             patch('services.hashtag_recommendation.PostingOptimizationService', return_value=mock_services['posting']):
            
            request_data = {
                "content_data": {
                    "description": sample_user_journey_data["video_metadata"]["description"],
                    "duration": sample_user_journey_data["video_metadata"]["duration"],
                    "transcript": sample_user_journey_data["content_analysis"]["transcript"]
                },
                "platforms": ["tiktok", "instagram"],
                "max_hashtags": 10,
                "target_audience": "tech enthusiasts and early adopters"
            }
            
            response = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Quality validation for each platform
            for platform in ["tiktok", "instagram"]:
                hashtags = data["recommendations"][platform]
                
                # 1. Relevance validation
                content_keywords = ["technology", "ai", "innovation", "future", "revolutionary"]
                relevant_hashtags = []
                
                for hashtag in hashtags:
                    tag_lower = hashtag["tag"].lower()
                    if any(keyword in tag_lower for keyword in content_keywords):
                        relevant_hashtags.append(hashtag)
                
                # At least 40% of hashtags should be directly relevant
                relevance_ratio = len(relevant_hashtags) / len(hashtags)
                assert relevance_ratio >= 0.4
                
                # 2. Score distribution validation
                relevance_scores = [h["relevance_score"] for h in hashtags]
                engagement_scores = [h["engagement_prediction"] for h in hashtags]
                
                # Scores should be well-distributed and not all the same
                assert max(relevance_scores) - min(relevance_scores) >= 0.1
                assert max(engagement_scores) - min(engagement_scores) >= 0.1
                
                # Top hashtags should have high scores
                top_hashtags = sorted(hashtags, key=lambda x: x["relevance_score"], reverse=True)[:3]
                for hashtag in top_hashtags:
                    assert hashtag["relevance_score"] >= 0.7
                
                # 3. Category diversity validation
                categories = [h["category"] for h in hashtags]
                unique_categories = set(categories)
                
                # Should have at least 2 different categories for diversity
                assert len(unique_categories) >= 2
                
                # 4. Platform-specific validation
                if platform == "tiktok":
                    # TikTok should prioritize trending hashtags
                    trending_count = sum(1 for h in hashtags if h["category"] == "trending")
                    assert trending_count >= 2
                
                elif platform == "instagram":
                    # Instagram should have a good mix of categories
                    assert len(unique_categories) >= 2

    @pytest.mark.asyncio
    async def test_caching_and_consistency(self, client, sample_user_journey_data, mock_services):
        """Test caching behavior and response consistency"""
        with patch('services.hashtag_recommendation.UnifiedLLMService', return_value=mock_services['llm']), \
             patch('services.hashtag_recommendation.ViralScoringService', return_value=mock_services['viral']), \
             patch('services.hashtag_recommendation.PostingOptimizationService', return_value=mock_services['posting']):
            
            request_data = {
                "content_data": {
                    "description": sample_user_journey_data["video_metadata"]["description"],
                    "duration": sample_user_journey_data["video_metadata"]["duration"],
                    "transcript": sample_user_journey_data["content_analysis"]["transcript"]
                },
                "platforms": ["tiktok"],
                "max_hashtags": 8,
                "target_audience": "tech enthusiasts"
            }
            
            # First request
            response1 = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=request_data
            )
            
            assert response1.status_code == 200
            data1 = response1.json()
            
            # Second identical request (should use cache)
            response2 = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=request_data
            )
            
            assert response2.status_code == 200
            data2 = response2.json()
            
            # Responses should be identical due to caching
            assert data1 == data2
            
            # Third request with slight modification (should not use cache)
            modified_request = request_data.copy()
            modified_request["max_hashtags"] = 6
            
            response3 = client.post(
                "/api/v1/recommendations/hashtags/analyze",
                json=modified_request
            )
            
            assert response3.status_code == 200
            data3 = response3.json()
            
            # Should be different from cached response
            hashtags1 = data1["recommendations"]["tiktok"]
            hashtags3 = data3["recommendations"]["tiktok"]
            
            assert len(hashtags1) != len(hashtags3) or hashtags1 != hashtags3

    def test_health_check_and_monitoring(self, client):
        """Test health check and monitoring endpoints"""
        
        # Test main health check
        response = client.get("/api/v1/recommendations/health")
        
        assert response.status_code == 200
        health_data = response.json()
        
        assert "status" in health_data
        assert "service" in health_data
        assert health_data["status"] == "healthy"
        assert health_data["service"] == "hashtag_recommendations"
        
        # Verify timestamp is recent
        if "timestamp" in health_data:
            from datetime import datetime
            timestamp = datetime.fromisoformat(health_data["timestamp"].replace('Z', '+00:00'))
            now = datetime.now(timestamp.tzinfo)
            time_diff = abs((now - timestamp).total_seconds())
            assert time_diff < 60  # Should be within