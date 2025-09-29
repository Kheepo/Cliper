import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from api.services.supabase_service import SupabaseService


class TestSupabaseService:
    """Test suite for SupabaseService."""
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        mock_client = Mock()
        mock_client.table.return_value = mock_client
        mock_client.select.return_value = mock_client
        mock_client.insert.return_value = mock_client
        mock_client.update.return_value = mock_client
        mock_client.delete.return_value = mock_client
        mock_client.eq.return_value = mock_client
        mock_client.neq.return_value = mock_client
        mock_client.in_.return_value = mock_client
        mock_client.order.return_value = mock_client
        mock_client.limit.return_value = mock_client
        mock_client.execute.return_value = Mock(data=[])
        return mock_client
    
    @pytest.fixture
    def supabase_service(self, mock_supabase_client):
        """Create SupabaseService instance with mocked client."""
        with patch('api.services.supabase_service.create_client') as mock_create:
            mock_create.return_value = mock_supabase_client
            service = SupabaseService()
            service.client = mock_supabase_client
            return service
    
    @pytest.fixture
    def sample_clip_data(self):
        """Sample clip data for testing."""
        return {
            'original_video_id': 'video_123',
            'user_id': 'user_456',
            'clip_url': 'https://example.com/clip.mp4',
            'thumbnail_path': 'https://example.com/thumb.jpg',
            'start_time': 10.5,
            'end_time': 40.5,
            'duration': 30.0,
            'platform': 'youtube',
            'clip_type': 'highlight',
            'title': 'Amazing Clip',
            'description': 'This is an amazing clip',
            'status': 'completed',
            'file_size': 1024000,
            'resolution': '1920x1080',
            'bitrate': 2000,
            'format': 'mp4'
        }
    
    def test_supabase_service_initialization(self, supabase_service):
        """Test SupabaseService initialization."""
        assert supabase_service is not None
        assert hasattr(supabase_service, 'client')
    
    def test_create_generated_clip_success(self, supabase_service, mock_supabase_client, sample_clip_data):
        """Test successful clip creation."""
        # Mock successful response
        mock_response = Mock()
        mock_response.data = [{'id': 'clip_789', **sample_clip_data}]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.create_generated_clip(sample_clip_data)
        
        assert result is not None
        assert result['id'] == 'clip_789'
        mock_supabase_client.table.assert_called_with('generated_clips')
        mock_supabase_client.insert.assert_called_with(sample_clip_data)
    
    def test_create_generated_clip_failure(self, supabase_service, mock_supabase_client, sample_clip_data):
        """Test clip creation failure."""
        # Mock failed response
        mock_response = Mock()
        mock_response.data = []
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.create_generated_clip(sample_clip_data)
        
        assert result is None
    
    def test_get_generated_clip_success(self, supabase_service, mock_supabase_client, sample_clip_data):
        """Test successful clip retrieval."""
        clip_id = 'clip_789'
        mock_response = Mock()
        mock_response.data = [{'id': clip_id, **sample_clip_data}]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.get_generated_clip(clip_id)
        
        assert result is not None
        assert result['id'] == clip_id
        mock_supabase_client.table.assert_called_with('generated_clips')
        mock_supabase_client.eq.assert_called_with('id', clip_id)
    
    def test_get_generated_clip_not_found(self, supabase_service, mock_supabase_client):
        """Test clip retrieval when not found."""
        clip_id = 'nonexistent_clip'
        mock_response = Mock()
        mock_response.data = []
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.get_generated_clip(clip_id)
        
        assert result is None
    
    def test_update_generated_clip_status_success(self, supabase_service, mock_supabase_client):
        """Test successful clip status update."""
        clip_id = 'clip_789'
        new_status = 'processing'
        mock_response = Mock()
        mock_response.data = [{'id': clip_id, 'status': new_status}]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.update_generated_clip_status(clip_id, new_status)
        
        assert result is True
        mock_supabase_client.table.assert_called_with('generated_clips')
        mock_supabase_client.eq.assert_called_with('id', clip_id)
    
    def test_update_generated_clip_status_failure(self, supabase_service, mock_supabase_client):
        """Test clip status update failure."""
        clip_id = 'nonexistent_clip'
        new_status = 'processing'
        mock_response = Mock()
        mock_response.data = []
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.update_generated_clip_status(clip_id, new_status)
        
        assert result is False
    
    def test_update_generated_clip_data_success(self, supabase_service, mock_supabase_client):
        """Test successful clip data update."""
        clip_id = 'clip_789'
        update_data = {
            'clip_url': 'https://example.com/new_clip.mp4',
            'file_size': 2048000,
            'status': 'completed'
        }
        mock_response = Mock()
        mock_response.data = [{'id': clip_id, **update_data}]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.update_generated_clip_data(clip_id, update_data)
        
        assert result is not None
        assert result['id'] == clip_id
        mock_supabase_client.update.assert_called_with(update_data)
    
    def test_get_generated_clips_by_video_id(self, supabase_service, mock_supabase_client, sample_clip_data):
        """Test retrieving clips by video ID."""
        video_id = 'video_123'
        mock_response = Mock()
        mock_response.data = [
            {'id': 'clip_1', **sample_clip_data},
            {'id': 'clip_2', **sample_clip_data}
        ]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.get_generated_clips_by_video_id(video_id)
        
        assert len(result) == 2
        assert result[0]['id'] == 'clip_1'
        assert result[1]['id'] == 'clip_2'
        mock_supabase_client.eq.assert_called_with('original_video_id', video_id)
    
    def test_get_generated_clips_by_user_id(self, supabase_service, mock_supabase_client, sample_clip_data):
        """Test retrieving clips by user ID."""
        user_id = 'user_456'
        mock_response = Mock()
        mock_response.data = [
            {'id': 'clip_1', **sample_clip_data},
            {'id': 'clip_2', **sample_clip_data}
        ]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.get_generated_clips_by_user_id(user_id, limit=10)
        
        assert len(result) == 2
        mock_supabase_client.eq.assert_called_with('user_id', user_id)
        mock_supabase_client.limit.assert_called_with(10)
    
    def test_get_failed_generated_clips(self, supabase_service, mock_supabase_client, sample_clip_data):
        """Test retrieving failed clips."""
        failed_clip_data = {**sample_clip_data, 'status': 'failed'}
        mock_response = Mock()
        mock_response.data = [{'id': 'failed_clip', **failed_clip_data}]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.get_failed_generated_clips(limit=5)
        
        assert len(result) == 1
        assert result[0]['status'] == 'failed'
        mock_supabase_client.eq.assert_called_with('status', 'failed')
        mock_supabase_client.limit.assert_called_with(5)
    
    def test_delete_generated_clip_success(self, supabase_service, mock_supabase_client):
        """Test successful clip deletion."""
        clip_id = 'clip_789'
        mock_response = Mock()
        mock_response.data = [{'id': clip_id}]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.delete_generated_clip(clip_id)
        
        assert result is True
        mock_supabase_client.table.assert_called_with('generated_clips')
        mock_supabase_client.eq.assert_called_with('id', clip_id)
        mock_supabase_client.delete.assert_called_once()
    
    def test_delete_generated_clip_failure(self, supabase_service, mock_supabase_client):
        """Test clip deletion failure."""
        clip_id = 'nonexistent_clip'
        mock_response = Mock()
        mock_response.data = []
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.delete_generated_clip(clip_id)
        
        assert result is False
    
    def test_get_video_info_success(self, supabase_service, mock_supabase_client):
        """Test successful video info retrieval."""
        video_id = 'video_123'
        video_data = {
            'id': video_id,
            'title': 'Test Video',
            'duration': 300.0,
            'file_path': '/path/to/video.mp4',
            'status': 'processed'
        }
        mock_response = Mock()
        mock_response.data = [video_data]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.get_video_info(video_id)
        
        assert result is not None
        assert result['id'] == video_id
        assert result['title'] == 'Test Video'
        mock_supabase_client.table.assert_called_with('videos')
    
    def test_get_analysis_results_success(self, supabase_service, mock_supabase_client):
        """Test successful analysis results retrieval."""
        video_id = 'video_123'
        analysis_data = {
            'video_id': video_id,
            'transcript': 'Video transcript here',
            'summary': 'Video summary',
            'keywords': ['keyword1', 'keyword2'],
            'sentiment': 'positive'
        }
        mock_response = Mock()
        mock_response.data = [analysis_data]
        mock_supabase_client.execute.return_value = mock_response
        
        result = supabase_service.get_analysis_results(video_id)
        
        assert result is not None
        assert result['video_id'] == video_id
        assert 'transcript' in result
        mock_supabase_client.table.assert_called_with('video_analysis')
    
    def test_exception_handling(self, supabase_service, mock_supabase_client):
        """Test exception handling in service methods."""
        # Mock exception during database operation
        mock_supabase_client.execute.side_effect = Exception("Database error")
        
        # Test that exceptions are handled gracefully
        result = supabase_service.get_generated_clip('clip_123')
        assert result is None
        
        result = supabase_service.create_generated_clip({'test': 'data'})
        assert result is None
        
        result = supabase_service.update_generated_clip_status('clip_123', 'failed')
        assert result is False
    
    def test_get_clips_with_status_filter(self, supabase_service, mock_supabase_client, sample_clip_data):
        """Test retrieving clips with status filter."""
        status = 'processing'
        mock_response = Mock()
        mock_response.data = [{'id': 'clip_1', 'status': status, **sample_clip_data}]
        mock_supabase_client.execute.return_value = mock_response
        
        # Test getting clips by user with status filter
        result = supabase_service.get_generated_clips_by_user_id('user_456', status=status)
        
        assert len(result) == 1
        assert result[0]['status'] == status
    
    def test_bulk_update_clip_status(self, supabase_service, mock_supabase_client):
        """Test bulk status update for multiple clips."""
        clip_ids = ['clip_1', 'clip_2', 'clip_3']
        new_status = 'failed'
        mock_response = Mock()
        mock_response.data = [{'id': cid, 'status': new_status} for cid in clip_ids]
        mock_supabase_client.execute.return_value = mock_response
        
        # Simulate bulk update by calling update for each clip
        results = []
        for clip_id in clip_ids:
            result = supabase_service.update_generated_clip_status(clip_id, new_status)
            results.append(result)
        
        assert all(results)  # All updates should succeed
        assert mock_supabase_client.execute.call_count == len(clip_ids)
    
    def test_pagination_support(self, supabase_service, mock_supabase_client, sample_clip_data):
        """Test pagination support in clip retrieval."""
        user_id = 'user_456'
        limit = 5
        offset = 10
        
        # Mock paginated response
        mock_response = Mock()
        mock_response.data = [{'id': f'clip_{i}', **sample_clip_data} for i in range(limit)]
        mock_supabase_client.execute.return_value = mock_response
        
        # Add offset support to the service method (if implemented)
        result = supabase_service.get_generated_clips_by_user_id(user_id, limit=limit)
        
        assert len(result) == limit
        mock_supabase_client.limit.assert_called_with(limit)


if __name__ == "__main__":
    pytest.main([__file__])