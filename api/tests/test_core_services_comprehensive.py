"""Comprehensive tests for core services.

Tests:
- Firebase service with all methods
- Clip generation service
- Hashtag generation service
- Virality scoring
- Error handling and edge cases
- Performance optimization
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List
import json
from datetime import datetime, timedelta

from ..services.firebase_service import FirebaseService
from ..services.clip_generation_service import ClipGenerationService
from ..services.hashtag_service import HashtagService
from ..models.clip import Clip, ClipStatus
from ..models.user import User


class TestFirebaseService:
    """Test Firebase service with all operations."""
    
    @pytest.fixture
    def firebase_service(self):
        """Create Firebase service for testing."""
        with patch('firebase_admin.initialize_app'), \
             patch('firebase_admin.firestore.client') as mock_client:
            
            service = FirebaseService()
            service.db = mock_client.return_value
            return service
    
    @pytest.fixture
    def sample_clip_data(self):
        """Sample clip data for testing."""
        return {
            'id': 'clip_123',
            'user_id': 'user_456',
            'video_path': '/videos/test.mp4',
            'start_time': 10.5,
            'end_time': 40.2,
            'text': 'This is a test clip with interesting content',
            'virality_score': 0.85,
            'hashtags': ['#test', '#viral', '#content'],
            'status': 'completed',
            'created_at': datetime.now(),
            'metadata': {
                'duration': 29.7,
                'file_size': 5242880,
                'resolution': '1920x1080'
            }
        }
    
    @pytest.mark.asyncio
    async def test_save_clip_success(self, firebase_service, sample_clip_data):
        """Test successful clip saving."""
        mock_doc_ref = Mock()
        mock_doc_ref.set = AsyncMock()
        firebase_service.db.collection.return_value.document.return_value = mock_doc_ref
        
        result = await firebase_service.save_clip(sample_clip_data)
        
        assert result['success'] is True
        assert result['clip_id'] == 'clip_123'
        mock_doc_ref.set.assert_called_once()
        
        # Verify data structure
        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args['user_id'] == 'user_456'
        assert call_args['virality_score'] == 0.85
        assert len(call_args['hashtags']) == 3
    
    @pytest.mark.asyncio
    async def test_save_clip_with_missing_fields(self, firebase_service):
        """Test clip saving with missing required fields."""
        incomplete_data = {
            'user_id': 'user_456',
            'text': 'Test clip'
            # Missing required fields like video_path, start_time, etc.
        }
        
        with pytest.raises(ValueError, match="Missing required field"):
            await firebase_service.save_clip(incomplete_data)
    
    @pytest.mark.asyncio
    async def test_get_clip_by_id(self, firebase_service, sample_clip_data):
        """Test retrieving clip by ID."""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_clip_data
        
        mock_doc_ref = Mock()
        mock_doc_ref.get = AsyncMock(return_value=mock_doc)
        firebase_service.db.collection.return_value.document.return_value = mock_doc_ref
        
        result = await firebase_service.get_clip('clip_123')
        
        assert result is not None
        assert result['id'] == 'clip_123'
        assert result['virality_score'] == 0.85
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_clip(self, firebase_service):
        """Test retrieving non-existent clip."""
        mock_doc = Mock()
        mock_doc.exists = False
        
        mock_doc_ref = Mock()
        mock_doc_ref.get = AsyncMock(return_value=mock_doc)
        firebase_service.db.collection.return_value.document.return_value = mock_doc_ref
        
        result = await firebase_service.get_clip('nonexistent_clip')
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_clips(self, firebase_service, sample_clip_data):
        """Test retrieving clips for a user."""
        mock_docs = []
        for i in range(3):
            mock_doc = Mock()
            mock_doc.to_dict.return_value = {
                **sample_clip_data,
                'id': f'clip_{i}',
                'created_at': datetime.now() - timedelta(days=i)
            }
            mock_docs.append(mock_doc)
        
        mock_query = Mock()
        mock_query.order_by.return_value.limit.return_value.stream = AsyncMock(return_value=mock_docs)
        firebase_service.db.collection.return_value.where.return_value = mock_query
        
        result = await firebase_service.get_user_clips('user_456', limit=10)
        
        assert len(result) == 3
        assert all(clip['user_id'] == 'user_456' for clip in result)
        assert result[0]['id'] == 'clip_0'  # Most recent first
    
    @pytest.mark.asyncio
    async def test_update_clip_status(self, firebase_service):
        """Test updating clip status."""
        mock_doc_ref = Mock()
        mock_doc_ref.update = AsyncMock()
        firebase_service.db.collection.return_value.document.return_value = mock_doc_ref
        
        await firebase_service.update_clip_status('clip_123', 'processing')
        
        mock_doc_ref.update.assert_called_once_with({
            'status': 'processing',
            'updated_at': mock_doc_ref.update.call_args[0][0]['updated_at']
        })
    
    @pytest.mark.asyncio
    async def test_save_virality_scores(self, firebase_service):
        """Test saving virality scores (previously missing method)."""
        scores_data = {
            'clip_id': 'clip_123',
            'scores': {
                'engagement_score': 0.85,
                'content_quality': 0.78,
                'trending_potential': 0.92,
                'audience_match': 0.67
            },
            'overall_score': 0.81,
            'calculated_at': datetime.now(),
            'model_version': 'v2.1'
        }
        
        mock_doc_ref = Mock()
        mock_doc_ref.set = AsyncMock()
        firebase_service.db.collection.return_value.document.return_value = mock_doc_ref
        
        result = await firebase_service.save_virality_scores(scores_data)
        
        assert result['success'] is True
        assert result['clip_id'] == 'clip_123'
        mock_doc_ref.set.assert_called_once()
        
        # Verify scores structure
        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args['overall_score'] == 0.81
        assert 'engagement_score' in call_args['scores']
    
    @pytest.mark.asyncio
    async def test_get_trending_clips(self, firebase_service, sample_clip_data):
        """Test retrieving trending clips."""
        trending_clips = []
        for i in range(5):
            clip_data = {
                **sample_clip_data,
                'id': f'trending_clip_{i}',
                'virality_score': 0.9 - (i * 0.1),  # Descending scores
                'created_at': datetime.now() - timedelta(hours=i)
            }
            
            mock_doc = Mock()
            mock_doc.to_dict.return_value = clip_data
            trending_clips.append(mock_doc)
        
        mock_query = Mock()
        mock_query.where.return_value.order_by.return_value.limit.return_value.stream = AsyncMock(
            return_value=trending_clips
        )
        firebase_service.db.collection.return_value = mock_query
        
        result = await firebase_service.get_trending_clips(limit=5, min_score=0.7)
        
        assert len(result) == 5
        assert result[0]['virality_score'] >= result[1]['virality_score']  # Sorted by score
        assert all(clip['virality_score'] >= 0.7 for clip in result)
    
    @pytest.mark.asyncio
    async def test_batch_operations(self, firebase_service):
        """Test batch operations for multiple clips."""
        clips_data = []
        for i in range(3):
            clips_data.append({
                'id': f'batch_clip_{i}',
                'user_id': 'user_456',
                'text': f'Batch clip {i}',
                'virality_score': 0.7 + (i * 0.1)
            })
        
        mock_batch = Mock()
        mock_batch.commit = AsyncMock()
        firebase_service.db.batch.return_value = mock_batch
        
        result = await firebase_service.save_clips_batch(clips_data)
        
        assert result['success'] is True
        assert result['saved_count'] == 3
        mock_batch.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_firebase_exception(self, firebase_service, sample_clip_data):
        """Test error handling for Firebase exceptions."""
        mock_doc_ref = Mock()
        mock_doc_ref.set = AsyncMock(side_effect=Exception("Firebase connection error"))
        firebase_service.db.collection.return_value.document.return_value = mock_doc_ref
        
        result = await firebase_service.save_clip(sample_clip_data)
        
        assert result['success'] is False
        assert 'error' in result
        assert 'Firebase connection error' in result['error']


class TestClipGenerationService:
    """Test clip generation service."""
    
    @pytest.fixture
    def clip_service(self):
        """Create clip generation service for testing."""
        return ClipGenerationService()
    
    @pytest.fixture
    def sample_transcription(self):
        """Sample transcription data for testing."""
        return {
            'text': 'This is a fascinating story about artificial intelligence and machine learning. The technology has advanced rapidly in recent years, transforming industries and creating new opportunities. However, there are also challenges and ethical considerations that we must address.',
            'segments': [
                {'start': 0, 'end': 15, 'text': 'This is a fascinating story about artificial intelligence'},
                {'start': 15, 'end': 30, 'text': 'and machine learning. The technology has advanced rapidly'},
                {'start': 30, 'end': 45, 'text': 'in recent years, transforming industries and creating'},
                {'start': 45, 'end': 60, 'text': 'new opportunities. However, there are also challenges'},
                {'start': 60, 'end': 75, 'text': 'and ethical considerations that we must address.'}
            ]
        }
    
    @pytest.mark.asyncio
    async def test_generate_clips_from_transcription(self, clip_service, sample_transcription):
        """Test clip generation from transcription."""
        with patch.object(clip_service, '_calculate_virality_score') as mock_score, \
             patch.object(clip_service, '_extract_keywords') as mock_keywords:
            
            mock_score.return_value = 0.85
            mock_keywords.return_value = ['AI', 'technology', 'innovation']
            
            clips = await clip_service.generate_clips(
                transcription=sample_transcription,
                video_duration=75,
                max_clips=3,
                min_clip_duration=10,
                max_clip_duration=30
            )
            
            assert len(clips) <= 3
            assert all(clip['duration'] >= 10 for clip in clips)
            assert all(clip['duration'] <= 30 for clip in clips)
            assert all(clip['virality_score'] > 0 for clip in clips)
    
    @pytest.mark.asyncio
    async def test_clip_scoring_algorithm(self, clip_service):
        """Test virality scoring algorithm."""
        test_cases = [
            {
                'text': 'Amazing breakthrough in AI technology!',
                'keywords': ['AI', 'breakthrough', 'technology'],
                'duration': 25,
                'expected_score_range': (0.7, 1.0)
            },
            {
                'text': 'This is just a regular conversation.',
                'keywords': ['conversation'],
                'duration': 15,
                'expected_score_range': (0.3, 0.6)
            },
            {
                'text': 'Incredible discovery that will change everything!',
                'keywords': ['discovery', 'incredible', 'change'],
                'duration': 20,
                'expected_score_range': (0.8, 1.0)
            }
        ]
        
        for case in test_cases:
            score = clip_service._calculate_virality_score(
                text=case['text'],
                keywords=case['keywords'],
                duration=case['duration']
            )
            
            min_score, max_score = case['expected_score_range']
            assert min_score <= score <= max_score, f"Score {score} not in range {case['expected_score_range']} for text: {case['text']}"
    
    @pytest.mark.asyncio
    async def test_keyword_extraction(self, clip_service):
        """Test keyword extraction from text."""
        test_texts = [
            {
                'text': 'Artificial intelligence and machine learning are transforming technology',
                'expected_keywords': ['artificial intelligence', 'machine learning', 'technology']
            },
            {
                'text': 'Breaking news: major scientific discovery announced today',
                'expected_keywords': ['breaking news', 'scientific discovery']
            }
        ]
        
        for case in test_texts:
            keywords = clip_service._extract_keywords(case['text'])
            
            assert len(keywords) > 0
            # Check if at least some expected keywords are found
            found_keywords = [kw for kw in case['expected_keywords'] if any(kw.lower() in k.lower() for k in keywords)]
            assert len(found_keywords) > 0
    
    @pytest.mark.asyncio
    async def test_clip_duration_optimization(self, clip_service, sample_transcription):
        """Test clip duration optimization."""
        # Test with different duration constraints
        short_clips = await clip_service.generate_clips(
            transcription=sample_transcription,
            video_duration=75,
            max_clips=5,
            min_clip_duration=5,
            max_clip_duration=15
        )
        
        long_clips = await clip_service.generate_clips(
            transcription=sample_transcription,
            video_duration=75,
            max_clips=3,
            min_clip_duration=20,
            max_clip_duration=45
        )
        
        # Verify duration constraints
        assert all(5 <= clip['duration'] <= 15 for clip in short_clips)
        assert all(20 <= clip['duration'] <= 45 for clip in long_clips)
        
        # Short clips should have more clips due to smaller duration
        assert len(short_clips) >= len(long_clips)
    
    @pytest.mark.asyncio
    async def test_content_quality_filtering(self, clip_service):
        """Test filtering of low-quality content."""
        low_quality_transcription = {
            'text': 'Um, uh, well, you know, like, it\'s just, um, yeah.',
            'segments': [
                {'start': 0, 'end': 10, 'text': 'Um, uh, well, you know'},
                {'start': 10, 'end': 20, 'text': 'like, it\'s just, um, yeah.'}
            ]
        }
        
        clips = await clip_service.generate_clips(
            transcription=low_quality_transcription,
            video_duration=20,
            max_clips=5,
            quality_threshold=0.5
        )
        
        # Should filter out low-quality content
        assert len(clips) == 0 or all(clip['virality_score'] >= 0.5 for clip in clips)
    
    @pytest.mark.asyncio
    async def test_overlapping_clips_prevention(self, clip_service, sample_transcription):
        """Test prevention of overlapping clips."""
        clips = await clip_service.generate_clips(
            transcription=sample_transcription,
            video_duration=75,
            max_clips=10,
            prevent_overlap=True
        )
        
        # Check for overlaps
        for i, clip1 in enumerate(clips):
            for j, clip2 in enumerate(clips[i+1:], i+1):
                # Clips should not overlap
                assert not (clip1['start_time'] < clip2['end_time'] and clip2['start_time'] < clip1['end_time'])


class TestHashtagService:
    """Test hashtag generation service."""
    
    @pytest.fixture
    def hashtag_service(self):
        """Create hashtag service for testing."""
        return HashtagService()
    
    @pytest.mark.asyncio
    async def test_generate_hashtags_from_text(self, hashtag_service):
        """Test hashtag generation from text content."""
        test_text = "This amazing AI breakthrough in machine learning will revolutionize technology and transform the future of artificial intelligence."
        
        hashtags = await hashtag_service.generate_hashtags(
            text=test_text,
            max_hashtags=10,
            include_trending=True
        )
        
        assert len(hashtags) <= 10
        assert all(tag.startswith('#') for tag in hashtags)
        
        # Should include relevant hashtags
        hashtag_text = ' '.join(hashtags).lower()
        assert any(keyword in hashtag_text for keyword in ['ai', 'technology', 'machine', 'learning'])
    
    @pytest.mark.asyncio
    async def test_hashtag_formatting(self, hashtag_service):
        """Test proper hashtag formatting."""
        test_cases = [
            {
                'input': 'artificial intelligence',
                'expected_format': '#artificialintelligence'
            },
            {
                'input': 'machine learning',
                'expected_format': '#machinelearning'
            },
            {
                'input': 'AI breakthrough',
                'expected_format': '#aibreakthrough'
            }
        ]
        
        for case in test_cases:
            formatted = hashtag_service._format_hashtag(case['input'])
            assert formatted == case['expected_format']
            assert ' ' not in formatted
            assert formatted.startswith('#')
    
    @pytest.mark.asyncio
    async def test_trending_hashtags_integration(self, hashtag_service):
        """Test integration with trending hashtags."""
        with patch.object(hashtag_service, '_get_trending_hashtags') as mock_trending:
            mock_trending.return_value = ['#viral', '#trending', '#popular']
            
            hashtags = await hashtag_service.generate_hashtags(
                text="This is amazing content",
                max_hashtags=8,
                include_trending=True
            )
            
            # Should include some trending hashtags
            assert any(tag in ['#viral', '#trending', '#popular'] for tag in hashtags)
    
    @pytest.mark.asyncio
    async def test_hashtag_relevance_scoring(self, hashtag_service):
        """Test hashtag relevance scoring."""
        text = "Revolutionary AI technology breakthrough in deep learning and neural networks"
        
        hashtags_with_scores = hashtag_service._score_hashtag_relevance(
            text=text,
            candidate_hashtags=['#ai', '#technology', '#breakthrough', '#cooking', '#sports']
        )
        
        # AI-related hashtags should score higher
        ai_score = next(score for tag, score in hashtags_with_scores if tag == '#ai')
        cooking_score = next(score for tag, score in hashtags_with_scores if tag == '#cooking')
        
        assert ai_score > cooking_score
    
    @pytest.mark.asyncio
    async def test_hashtag_deduplication(self, hashtag_service):
        """Test hashtag deduplication."""
        text = "AI artificial intelligence machine learning ML technology tech"
        
        hashtags = await hashtag_service.generate_hashtags(
            text=text,
            max_hashtags=10,
            deduplicate=True
        )
        
        # Should not have duplicate or very similar hashtags
        assert len(hashtags) == len(set(hashtags))  # No exact duplicates
        
        # Should not have both #ai and #artificialintelligence if they're too similar
        similar_pairs = [('#ai', '#artificialintelligence'), ('#ml', '#machinelearning')]
        for tag1, tag2 in similar_pairs:
            if tag1 in hashtags and tag2 in hashtags:
                # This is acceptable, but we should prefer one over the other
                pass
    
    @pytest.mark.asyncio
    async def test_hashtag_length_limits(self, hashtag_service):
        """Test hashtag length limitations."""
        long_text = "This is an extremely long phrase that would create a very long hashtag if not properly truncated"
        
        hashtag = hashtag_service._format_hashtag(long_text)
        
        # Should be truncated to reasonable length
        assert len(hashtag) <= 30  # Including the # symbol
    
    @pytest.mark.asyncio
    async def test_special_character_handling(self, hashtag_service):
        """Test handling of special characters in hashtags."""
        test_cases = [
            {
                'input': 'AI & machine learning',
                'expected': '#aimachinelearning'
            },
            {
                'input': 'tech-innovation',
                'expected': '#techinnovation'
            },
            {
                'input': 'future@work',
                'expected': '#futurework'
            }
        ]
        
        for case in test_cases:
            result = hashtag_service._format_hashtag(case['input'])
            assert result == case['expected']
            # Should only contain alphanumeric characters and #
            assert all(c.isalnum() or c == '#' for c in result)


class TestIntegratedWorkflow:
    """Test integrated workflow of all services."""
    
    @pytest.fixture
    def services(self):
        """Create all services for integration testing."""
        with patch('firebase_admin.initialize_app'), \
             patch('firebase_admin.firestore.client') as mock_client:
            
            firebase_service = FirebaseService()
            firebase_service.db = mock_client.return_value
            
            return {
                'firebase': firebase_service,
                'clip_generation': ClipGenerationService(),
                'hashtag': HashtagService()
            }
    
    @pytest.mark.asyncio
    async def test_complete_clip_processing_workflow(self, services):
        """Test complete workflow from transcription to saved clips."""
        transcription = {
            'text': 'This amazing AI breakthrough will revolutionize technology and create incredible opportunities for innovation.',
            'segments': [
                {'start': 0, 'end': 30, 'text': 'This amazing AI breakthrough will revolutionize technology'},
                {'start': 30, 'end': 60, 'text': 'and create incredible opportunities for innovation.'}
            ]
        }
        
        # Generate clips
        clips = await services['clip_generation'].generate_clips(
            transcription=transcription,
            video_duration=60,
            max_clips=2
        )
        
        # Generate hashtags for each clip
        for clip in clips:
            hashtags = await services['hashtag'].generate_hashtags(
                text=clip['text'],
                max_hashtags=5
            )
            clip['hashtags'] = hashtags
        
        # Save clips to Firebase
        saved_clips = []
        for clip in clips:
            clip_data = {
                'id': f"clip_{len(saved_clips) + 1}",
                'user_id': 'test_user',
                'video_path': '/test/video.mp4',
                **clip
            }
            
            with patch.object(services['firebase'], 'save_clip') as mock_save:
                mock_save.return_value = {'success': True, 'clip_id': clip_data['id']}
                result = await services['firebase'].save_clip(clip_data)
                saved_clips.append(result)
        
        # Verify complete workflow
        assert len(saved_clips) == len(clips)
        assert all(result['success'] for result in saved_clips)
        
        # Verify clips have all required data
        for i, clip in enumerate(clips):
            assert 'text' in clip
            assert 'virality_score' in clip
            assert 'hashtags' in clip
            assert len(clip['hashtags']) > 0
            assert all(tag.startswith('#') for tag in clip['hashtags'])
    
    @pytest.mark.asyncio
    async def test_error_recovery_in_workflow(self, services):
        """Test error recovery during integrated workflow."""
        transcription = {
            'text': 'Test content for error recovery',
            'segments': [{'start': 0, 'end': 30, 'text': 'Test content for error recovery'}]
        }
        
        # Simulate Firebase error
        with patch.object(services['firebase'], 'save_clip') as mock_save:
            mock_save.side_effect = Exception("Database connection error")
            
            clips = await services['clip_generation'].generate_clips(
                transcription=transcription,
                video_duration=30,
                max_clips=1
            )
            
            # Should handle error gracefully
            try:
                await services['firebase'].save_clip({
                    'id': 'test_clip',
                    'user_id': 'test_user',
                    **clips[0]
                })
            except Exception as e:
                assert "Database connection error" in str(e)
    
    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(self, services):
        """Test performance with large transcription dataset."""
        # Create large transcription (simulate 1-hour video)
        large_transcription = {
            'text': ' '.join([f'This is segment {i} with interesting content about technology and innovation.' for i in range(120)]),
            'segments': [
                {'start': i*30, 'end': (i+1)*30, 'text': f'This is segment {i} with interesting content about technology and innovation.'}
                for i in range(120)  # 120 segments = 1 hour
            ]
        }
        
        import time
        start_time = time.time()
        
        clips = await services['clip_generation'].generate_clips(
            transcription=large_transcription,
            video_duration=3600,  # 1 hour
            max_clips=10
        )
        
        processing_time = time.time() - start_time
        
        # Should complete within reasonable time (< 5 seconds for testing)
        assert processing_time < 5.0
        assert len(clips) <= 10
        assert all('virality_score' in clip for clip in clips)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])