import pytest
import asyncio
import jwt
import json
from unittest.mock import patch, AsyncMock, Mock
from fastapi.testclient import TestClient
from api.main import app

# Sample JWT payload for testing
SAMPLE_JWT_PAYLOAD = {
    "uid": "test-user-123",
    "email": "test@example.com",
    "aud": "authenticated",
    "role": "authenticated",
    "iat": 1640995200,
    "exp": 9999999999
}

# Create a proper JWT token that starts with 'eyJ'
def create_test_jwt_token():
    """Create a valid JWT token for testing"""
    # Use a simple secret for testing
    secret = "test-secret-key"
    token = jwt.encode(SAMPLE_JWT_PAYLOAD, secret, algorithm="HS256")
    return token

def test_clips_endpoint_with_mocked_auth():
    """Test that clips endpoint works with mocked authentication"""
    # Mock both the auth function and the Supabase client creation
    with patch('api.middleware.auth.get_supabase_client_with_auth') as mock_client, \
         patch('api.middleware.auth.get_supabase_token_info_from_auth_middleware', return_value=SAMPLE_JWT_PAYLOAD):
        
        # Mock the Supabase client to return a valid user response
        mock_supabase_client = Mock()
        mock_user_response = Mock()
        mock_user_response.user = Mock()
        mock_user_response.user.id = "test-user-id"
        mock_user_response.user.email = "test@example.com"
        mock_user_response.user.user_metadata = {}
        mock_supabase_client.auth.get_user.return_value = mock_user_response
        mock_client.return_value = mock_supabase_client
        
        client = TestClient(app)
        # Use a proper JWT token format
        test_token = create_test_jwt_token()
        response = client.get(
            "/api/v1/clips/",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        # Should not return 401 if authentication is properly mocked
        assert response.status_code != 401, f"Expected non-401 status, got {response.status_code}: {response.text}"

def test_clips_generation_with_mocked_auth():
    """Test that clips generation endpoint works with mocked authentication"""
    # Mock both the auth function and the Supabase client creation
    with patch('api.middleware.auth.get_supabase_client_with_auth') as mock_client, \
         patch('api.middleware.auth.get_supabase_token_info_from_auth_middleware', return_value=SAMPLE_JWT_PAYLOAD):
        
        # Mock the Supabase client to return a valid user response
        mock_supabase_client = Mock()
        mock_user_response = Mock()
        mock_user_response.user = Mock()
        mock_user_response.user.id = "test-user-id"
        mock_user_response.user.email = "test@example.com"
        mock_user_response.user.user_metadata = {}
        mock_supabase_client.auth.get_user.return_value = mock_user_response
        mock_client.return_value = mock_supabase_client
        
        client = TestClient(app)
        # Use a proper JWT token format
        test_token = create_test_jwt_token()
        response = client.post(
            "/api/v1/clips/",
            headers={"Authorization": f"Bearer {test_token}"},
            json={
                "video_id": 1,
                "clip_type": "highlight",
                "start_time": 10.0,
                "end_time": 40.0
            }
        )
        # Should not return 401 if authentication is properly mocked
        assert response.status_code != 401, f"Expected non-401 status, got {response.status_code}: {response.text}"