"""
Unit tests for the viral scoring service.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from api.services.viral_scoring import (
    ViralScoringService, 
    ViralFactor, 
    ViralMoment, 
    PlatformViralScore,
    ComprehensiveViralAnalysis,
    ViralFactorType
)
from api.models.pydantic_models import PlatformEnum


class TestViralScoringService:
    """Test cases for ViralScoringService"""

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service for testing"""
        mock = Mock()
        mock.analyze_content = AsyncMock()
        return mock

    @pytest.fixture
    def viral_scoring_service(self, mock_llm_service):
        """Create ViralScoringService instance with mocked dependencies"""
        service = ViralScoringService()
        service.llm_service = mock_llm_service
        return service

    @pytest.fixture
    def sample_transcript(self):
        """Sample transcript for testing"""
        return [
            {"start": 0.0, "end": 5.0, "text": "Welcome to this amazing tutorial!"},
            {"start": 5.0, "end": 10.0, "text": "Today we're going to learn something incredible."},
            {"start": 10.0, "end": 15.0, "text": "This will blow your mind!"},
            {"start": 15.0, "end": 20.0, "text": "Let's get started with the basics."},
        ]

    @pytest.fixture
    def sample_segment(self):
        """Sample video segment for testing"""
        return {
            "start_time": 0.0,
            "end_time": 20.0,
            "duration": 20.0,
            "title": "Amazing Tutorial Intro",
            "description": "Introduction to an amazing tutorial"
        }

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response for viral analysis"""
        return {
            "viral_factors": [
                {
                    "factor": "emotional_hook",
                    "score": 8.5,
                    "confidence": 0.9,
                    "explanation": "Strong emotional opening with excitement"
                },
                {
                    "factor": "curiosity_gap",
                    "score": 7.8,
                    "confidence": 0.85,
                    "explanation": "Creates anticipation for what's coming"
                }
            ],
            "viral_moments": [
                {
                    "timestamp": 10.0,
                    "intensity": 9.2,
                    "description": "Peak excitement moment",
                    "factors": ["emotional_hook", "surprise"]
                }
            ],
            "platform_scores": {
                "tiktok": {"score": 8.7, "confidence": 0.88},
                "youtube_shorts": {"score": 8.3, "confidence": 0.82},
                "instagram_reels": {"score": 8.5, "confidence": 0.85},
                "twitter": {"score": 7.9, "confidence": 0.79}
            },
            "overall_score": 8.4,
            "confidence": 0.86,
            "insights": [
                "Strong emotional opening creates immediate engagement",
                "Curiosity gap maintains viewer attention",
                "Content structure is optimized for short-form platforms"
            ]
        }

    @pytest.mark.asyncio
    async def test_analyze_viral_potential_success(self, viral_scoring_service, mock_llm_service, 
                                                 sample_segment, sample_transcript, mock_llm_response):
        """Test successful viral potential analysis"""
        # Setup mock
        mock_llm_service.generate_response.return_value = Mock(
            content='{"viral_factors": [{"factor_type": "emotional_hook", "score": 0.85, "confidence": 0.9, "reasoning": "Strong emotional content"}]}',
            success=True
        )
        
        # Execute
        result = await viral_scoring_service.analyze_viral_potential(
            transcription={"segments": sample_transcript},
            target_platforms=[PlatformEnum.TIKTOK]
        )
        
        # Verify
        assert isinstance(result, ComprehensiveViralAnalysis)
        assert result.overall_viral_score >= 0.0
        assert result.confidence >= 0.0
        assert len(result.viral_factors) >= 0
        assert len(result.platform_scores) == 1
        assert PlatformEnum.TIKTOK.value in result.platform_scores

    @pytest.mark.asyncio
    async def test_analyze_viral_potential_with_platform_optimization(self, viral_scoring_service, 
                                                                    mock_llm_service, sample_segment, 
                                                                    sample_transcript, mock_llm_response):
        """Test viral analysis with platform-specific optimization"""
        mock_llm_service.generate_response.return_value = Mock(
            content='{"viral_factors": [{"factor_type": "visual_appeal", "score": 0.75, "confidence": 0.8, "reasoning": "Good visual content"}]}',
            success=True
        )
        
        result = await viral_scoring_service.analyze_viral_potential(
            transcription={"segments": sample_transcript},
            target_platforms=[PlatformEnum.YOUTUBE]
        )
        
        # Verify result contains platform scores
        assert PlatformEnum.YOUTUBE.value in result.platform_scores
        assert result.platform_scores[PlatformEnum.YOUTUBE.value].score >= 0.0

    @pytest.mark.asyncio
    async def test_analyze_viral_potential_llm_error(self, viral_scoring_service, mock_llm_service, 
                                                   sample_segment, sample_transcript):
        """Test handling of LLM service errors"""
        # Setup mock to raise exception
        mock_llm_service.generate_response.side_effect = Exception("LLM service error")
        
        # Execute - should return fallback analysis instead of raising
        result = await viral_scoring_service.analyze_viral_potential(
            transcription={"segments": sample_transcript},
            target_platforms=[PlatformEnum.TIKTOK]
        )
        
        # Verify fallback analysis is returned
        assert isinstance(result, ComprehensiveViralAnalysis)
        assert result.confidence <= 0.5  # Fallback should have low confidence

    @pytest.mark.asyncio
    async def test_analyze_viral_potential_invalid_response(self, viral_scoring_service, mock_llm_service, 
                                                          sample_segment, sample_transcript):
        """Test handling of invalid LLM response"""
        # Setup mock with invalid response
        mock_llm_service.generate_response.return_value = Mock(
            content='{"invalid": "response"}',
            success=True
        )
        
        # Execute - should return fallback analysis for invalid response
        result = await viral_scoring_service.analyze_viral_potential(
            transcription={"segments": sample_transcript},
            target_platforms=[PlatformEnum.TIKTOK]
        )
        
        # Verify fallback analysis is returned
        assert isinstance(result, ComprehensiveViralAnalysis)
        assert result.confidence <= 0.5  # Fallback should have low confidence

    def test_extract_content_features(self, viral_scoring_service, sample_transcript):
        """Test content feature extraction"""
        transcription = {"segments": sample_transcript}
        
        features = viral_scoring_service._extract_content_features(
            transcription=transcription,
            scenes=None,
            emotions=None,
            video_metadata={"duration": 20.0}
        )
        
        assert isinstance(features, dict)
        assert "duration" in features
        assert "word_count" in features
        assert "speaking_pace" in features
        assert features["duration"] == 20.0

    def test_calculate_overall_score(self, viral_scoring_service):
        """Test overall score calculation"""
        platform_scores = {
            "tiktok": PlatformViralScore(
                platform=PlatformEnum.TIKTOK,
                score=0.85,
                confidence=0.9,
                optimization_suggestions=[],
                ideal_duration=(15, 60),
                key_factors=[]
            ),
            "instagram": PlatformViralScore(
                platform=PlatformEnum.INSTAGRAM,
                score=0.75,
                confidence=0.8,
                optimization_suggestions=[],
                ideal_duration=(15, 90),
                key_factors=[]
            )
        }
        
        viral_factors = [
            ViralFactor(
                factor_type=ViralFactorType.EMOTIONAL_HOOK,
                score=0.8,
                confidence=0.9,
                reasoning="Strong emotional content"
            )
        ]
        
        overall_score = viral_scoring_service._calculate_overall_score(platform_scores, viral_factors)
        
        assert isinstance(overall_score, float)
        assert 0.0 <= overall_score <= 1.0

    def test_calculate_confidence(self, viral_scoring_service):
        """Test confidence calculation"""
        viral_factors = [
            ViralFactor(
                factor_type=ViralFactorType.EMOTIONAL_HOOK,
                score=0.8,
                confidence=0.9,
                reasoning="Strong emotional content"
            ),
            ViralFactor(
                factor_type=ViralFactorType.VISUAL_APPEAL,
                score=0.7,
                confidence=0.8,
                reasoning="Good visual content"
            )
        ]
        
        platform_scores = {
            "tiktok": PlatformViralScore(
                platform=PlatformEnum.TIKTOK,
                score=0.85,
                confidence=0.9,
                optimization_suggestions=[],
                ideal_duration=(15, 60),
                key_factors=[]
            )
        }
        
        confidence = viral_scoring_service._calculate_confidence(viral_factors, platform_scores)
        
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    @pytest.mark.asyncio
    async def test_analyze_viral_potential_with_empty_transcript(self, viral_scoring_service, 
                                                               mock_llm_service):
        """Test viral analysis with empty transcript"""
        mock_llm_service.generate_response.return_value = Mock(
            content='{"viral_factors": []}',
            success=True
        )
        
        result = await viral_scoring_service.analyze_viral_potential(
            transcription={"segments": []},
            target_platforms=[PlatformEnum.TIKTOK]
        )
        
        # Should still work but return fallback analysis
        assert isinstance(result, ComprehensiveViralAnalysis)
        assert result.confidence <= 0.5  # Should have low confidence for empty transcript

    @pytest.mark.asyncio
    async def test_analyze_viral_potential_performance(self, viral_scoring_service, mock_llm_service, 
                                                     sample_transcript):
        """Test performance of viral analysis"""
        import time
        
        mock_llm_service.generate_response.return_value = Mock(
            content='{"viral_factors": [{"factor_type": "emotional_hook", "score": 0.8, "confidence": 0.9, "reasoning": "test"}]}',
            success=True
        )
        
        start_time = time.time()
        result = await viral_scoring_service.analyze_viral_potential(
            transcription={"segments": sample_transcript},
            target_platforms=[PlatformEnum.TIKTOK]
        )
        end_time = time.time()
        
        # Should complete within reasonable time (< 5 seconds for mock)
        assert (end_time - start_time) < 5.0
        assert isinstance(result, ComprehensiveViralAnalysis)