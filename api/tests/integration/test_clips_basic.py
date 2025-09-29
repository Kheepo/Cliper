import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from api.main import app


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_clips():
    """Sample clips data for testing."""
    return [
        {
            "id": "clip_1",
            "title": "Test Clip 1",
            "description": "First test clip",
            "video_url": "https://example.com/video1.mp4",
            "thumbnail_url": "https://example.com/thumb1.jpg",
            "duration": 30.5,
            "created_at": datetime.now() - timedelta(days=1),
            "user_id": "test_user_id",
            "status": "completed"
        },
        {
            "id": "clip_2",
            "title": "Test Clip 2",
            "description": "Second test clip",
            "video_url": "https://example.com/video2.mp4",
            "thumbnail_url": "https://example.com/thumb2.jpg",
            "duration": 45.2,
            "created_at": datetime.now() - timedelta(hours=12),
            "user_id": "test_user_id",
            "status": "completed"
        },
        {
            "id": "clip_3",
            "title": "Test Clip 3",
            "description": "Third test clip",
            "video_url": "https://example.com/video3.mp4",
            "thumbnail_url": "https://example.com/thumb3.jpg",
            "duration": 60.0,
            "created_at": datetime.now() - timedelta(hours=6),
            "user_id": "test_user_id",
            "status": "completed"
        }
    ]


class TestClipsBasic:
    """Basic clips endpoint tests."""
    
    def test_clips_endpoint_exists(self, test_client):
        """Test that the clips endpoint exists and returns proper error for unauthenticated requests."""
        response = test_client.get("/api/clips")
        
        # Should return 403 for unauthenticated requests
        assert response.status_code == 403
        
    def test_clips_endpoint_with_params(self, test_client):
        """Test clips endpoint with query parameters."""
        response = test_client.get("/api/clips?limit=10&offset=0")
        
        # Should still return 403 for unauthenticated requests
        assert response.status_code == 403
        
    @patch('api.utils.supabase_client.get_supabase_client_with_auth')
    @patch('api.utils.supabase_client.get_supabase_admin_client')
    def test_clips_with_mock_auth(self, mock_supabase_admin, mock_supabase_auth, test_client, sample_clips):
        """Test clips endpoint with mocked authentication."""
        # Mock Supabase auth client
        mock_auth_client = MagicMock()
        mock_supabase_auth.return_value = mock_auth_client
        
        # Mock user authentication response
        mock_user = MagicMock()
        mock_user.id = 'test_user_id'
        mock_user.email = 'test@example.com'
        mock_user.user_metadata = {}
        
        mock_user_response = MagicMock()
        mock_user_response.user = mock_user
        
        mock_auth_client.auth.get_user.return_value = mock_user_response
        
        # Mock Supabase admin client
        mock_admin_client = MagicMock()
        mock_supabase_admin.return_value = mock_admin_client
        
        # Mock user lookup
        mock_user_lookup_response = MagicMock()
        mock_user_lookup_response.data = [{'id': 'test_user_id'}]
        
        # Mock clips query
        mock_clips_response = MagicMock()
        mock_clips_response.data = sample_clips[:2]
        mock_clips_response.count = 3
        
        # Setup the mock chain for user lookup
        mock_admin_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_user_lookup_response
        
        # Setup the mock chain for clips query
        mock_admin_client.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_clips_response
        
        # Make request with auth header
        headers = {"Authorization": "Bearer test_token"}
        response = test_client.get("/api/clips?limit=2&offset=0", headers=headers)
        
        # Debug: Print response details
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        # Should succeed with mocked auth
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 2