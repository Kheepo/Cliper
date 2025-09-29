import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from api.services.unified_llm_service import unified_llm_service, LLMProvider, TaskType
from api.models.pydantic_models import ViralityScore, Hashtag, PostingRecommendation


class TestUnifiedLLMService:
    """Test suite for UnifiedLLMService."""
    
    @pytest.fixture
    def llm_service(self):
        """Get unified LLM service instance for testing."""
        return unified_llm_service
    
    @pytest.fixture
    def sample_transcript(self):
        """Sample transcript data for testing."""
        return {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Welcome to this amazing tutorial!"
                },
                {
                    "start": 5.0,
                    "end": 10.0,
                    "text": "Today we'll learn something incredible."
                }
            ]
        }
    
    @pytest.fixture
    def sample_video_features(self):
        """Sample video features for testing."""
        return {
            "duration": 60.0,
            "resolution": "1920x1080",
            "fps": 30,
            "audio_quality": "high",
            "visual_complexity": 0.7
        }
    
    @pytest.fixture
    def sample_analysis_results(self):
        """Sample analysis results for testing."""
        return {
            'transcript': 'This is a sample video transcript with exciting content.',
            'summary': 'Video about exciting content with climax moments.',
            'keywords': ['exciting', 'content', 'climax', 'moments'],
            'sentiment': 'positive',
            'topics': ['entertainment', 'education']
        }
    
    def test_llm_service_initialization(self, llm_service):
        """Test UnifiedLLMService initialization."""
        assert llm_service is not None
        assert hasattr(llm_service, 'cache')
        assert hasattr(llm_service, 'provider_preferences')
        assert hasattr(llm_service, 'cache_ttl')
        assert isinstance(llm_service.cache, dict)
        assert isinstance(llm_service.provider_preferences, dict)
    
    def test_llm_service_with_custom_config(self, llm_service):
        """Test UnifiedLLMService with custom configuration."""
        # Test that the service has proper provider preferences
        assert hasattr(llm_service, 'provider_preferences')
        assert isinstance(llm_service.provider_preferences, dict)
        
        # Test that we can modify provider preferences
        original_prefs = llm_service.provider_preferences.copy()
        llm_service.provider_preferences[TaskType.VIRALITY_ANALYSIS] = LLMProvider.GEMINI
        assert llm_service.provider_preferences[TaskType.VIRALITY_ANALYSIS] == LLMProvider.GEMINI
        
        # Restore original preferences
        llm_service.provider_preferences = original_prefs
    
    @pytest.mark.asyncio
    async def test_service_status(self, llm_service):
        """Test service status check."""
        status = llm_service.get_service_status()
        
        assert "openai_available" in status
        assert "gemini_available" in status
        assert "cache_size" in status
        assert "provider_preferences" in status
        assert isinstance(status["openai_available"], bool)
        assert isinstance(status["gemini_available"], bool)
        assert isinstance(status["cache_size"], int)
        assert isinstance(status["provider_preferences"], dict)

    @pytest.mark.asyncio
    async def test_analyze_virality_success(self, llm_service, sample_transcript, sample_video_features):
        """Test successful virality analysis."""
        with patch.object(llm_service, '_execute_with_fallback') as mock_execute:
            mock_execute.return_value = Mock(
                success=True,
                data='[{"niche": "Entertainment/Comedy", "score": 0.8, "explanation": "High entertainment value"}]'
            )
            
            result = await llm_service.analyze_virality(sample_transcript, sample_video_features)
            
            assert len(result) == 1
            assert result[0].niche == "Entertainment/Comedy"
            assert result[0].score == 0.8
            assert "entertainment" in result[0].explanation.lower()

    @pytest.mark.asyncio
    async def test_analyze_virality_fallback(self, llm_service, sample_transcript, sample_video_features):
        """Test virality analysis fallback."""
        with patch.object(llm_service, '_execute_with_fallback') as mock_execute:
            mock_execute.return_value = Mock(success=False)
            
            result = await llm_service.analyze_virality(sample_transcript, sample_video_features)
            
            assert len(result) == 3  # Fallback returns 3 default scores
            assert all(isinstance(score, ViralityScore) for score in result)
            assert result[0].niche == "Entertainment/Comedy"
            assert result[0].score == 0.6

    @pytest.mark.asyncio
    async def test_generate_hashtags_success(self, llm_service, sample_transcript):
        """Test successful hashtag generation."""
        with patch.object(llm_service, '_execute_with_fallback') as mock_execute:
            mock_execute.return_value = Mock(
                success=True,
                data='{"hashtags": [{"tag": "#viral", "platform": "instagram", "relevance_score": 0.9}, {"tag": "#content", "platform": "instagram", "relevance_score": 0.8}]}'
            )
            
            result = await llm_service.generate_hashtags(sample_transcript, ["entertainment"], "instagram")
            
            assert len(result) == 2
            assert all(isinstance(tag, Hashtag) for tag in result)
            assert result[0].tag == "#viral"
            assert result[0].platform == "instagram"
            assert result[0].relevance_score == 0.9

    @pytest.mark.asyncio
    async def test_generate_posting_recommendations_success(self, llm_service, sample_transcript):
        """Test successful posting recommendations generation."""
        with patch.object(llm_service, '_execute_with_fallback') as mock_execute:
            mock_execute.return_value = Mock(
                success=True,
                data='{"recommendations": [{"platform": "youtube", "optimal_times": ["6PM-8PM"], "format_suggestions": {"title": "Engaging title", "description": "Great description"}}]}'
            )
            
            result = await llm_service.generate_posting_recommendations(sample_transcript, ["entertainment"], "youtube")
            
            assert len(result) == 1
            assert all(isinstance(rec, PostingRecommendation) for rec in result)
            assert result[0].platform == "youtube"
            assert "6PM-8PM" in result[0].optimal_times
            assert result[0].format_suggestions["title"] == "Engaging title"

    @pytest.mark.asyncio
    async def test_cache_functionality(self, llm_service, sample_transcript, sample_video_features):
        """Test caching functionality."""
        # Clear cache first
        llm_service.clear_cache()
        initial_cache_size = len(llm_service.cache)
        
        with patch.object(llm_service, '_call_openai') as mock_openai, \
             patch.object(llm_service, '_call_gemini') as mock_gemini:
            
            # Mock successful response
            mock_response = {
                "content": '[{"niche": "Entertainment/Comedy", "score": 0.8, "explanation": "Cached result"}]',
                "tokens_used": 100
            }
            mock_openai.return_value = mock_response
            mock_gemini.return_value = mock_response
            
            # First call should hit the API and cache the result
            result1 = await llm_service.analyze_virality(sample_transcript, sample_video_features)
            assert len(llm_service.cache) > initial_cache_size  # Cache should have new entry
            
            # Second call should use cache (no additional API calls)
            api_call_count = mock_openai.call_count + mock_gemini.call_count
            result2 = await llm_service.analyze_virality(sample_transcript, sample_video_features)
            assert mock_openai.call_count + mock_gemini.call_count == api_call_count  # No additional calls
            
            assert result1[0].explanation == result2[0].explanation
    
    @pytest.mark.asyncio
    async def test_provider_fallback(self, llm_service, sample_transcript, sample_video_features):
        """Test provider fallback mechanism."""
        # Clear cache to avoid interference from other tests
        llm_service.clear_cache()
        
        # Mock OpenAI to fail, Gemini to succeed
        mock_gemini_response = {
            "content": '[{"niche": "Entertainment/Comedy", "score": 0.7, "explanation": "Gemini fallback response"}]',
            "tokens_used": None
        }
        
        with patch.object(llm_service, '_call_openai') as mock_openai, \
             patch.object(llm_service, '_call_gemini') as mock_gemini:
            
            # Mock OpenAI to fail
            mock_openai.side_effect = Exception("OpenAI API error")
            
            # Mock Gemini to succeed
            mock_gemini.return_value = mock_gemini_response
            
            result = await llm_service.analyze_virality(sample_transcript, sample_video_features)
            
            assert len(result) == 1
            assert result[0].niche == "Entertainment/Comedy"
            assert result[0].score == 0.7
            assert "Gemini fallback response" in result[0].explanation

    def test_clear_cache(self, llm_service):
        """Test cache clearing functionality."""
        # Add something to cache first
        llm_service.cache["test_key"] = "test_value"
        
        # Clear cache
        llm_service.clear_cache()
        
        # Verify cache is empty
        assert len(llm_service.cache) == 0
        
        # Verify cache size is reset
        status = llm_service.get_service_status()
        assert status["cache_size"] == 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, llm_service, sample_transcript, sample_video_features):
        """Test comprehensive error handling."""
        # Test with empty transcript
        result = await llm_service.analyze_virality("", sample_video_features)
        assert isinstance(result, list)
        assert len(result) > 0  # Should return fallback scores
        
        # Test with None transcript
        result = await llm_service.analyze_virality(None, sample_video_features)
        assert isinstance(result, list)
        assert len(result) > 0  # Should return fallback scores
    
    @pytest.mark.asyncio
    async def test_multiple_platforms_posting_recommendations(self, llm_service, sample_transcript):
        """Test posting recommendations for multiple platforms."""
        with patch.object(llm_service, '_execute_with_fallback') as mock_execute:
            mock_execute.return_value = Mock(
                success=True,
                data='{"recommendations": [{"platform": "instagram", "optimal_times": ["6:00 PM"], "format_suggestions": {"format": "vertical", "style": "engaging"}}, {"platform": "tiktok", "optimal_times": ["7:00 PM"], "format_suggestions": {"audio": "trending sounds", "duration": "15-30 seconds"}}]}'
            )
            
            result = await llm_service.generate_posting_recommendations(sample_transcript, ["entertainment"], "instagram")
            
            assert isinstance(result, list)
            assert len(result) == 2
            
            platforms = [rec.platform for rec in result]
            assert "instagram" in platforms
            assert "tiktok" in platforms
            
            for rec in result:
                assert isinstance(rec, PostingRecommendation)
                assert len(rec.optimal_times) > 0
                assert isinstance(rec.format_suggestions, dict)
    



if __name__ == "__main__":
    pytest.main([__file__])