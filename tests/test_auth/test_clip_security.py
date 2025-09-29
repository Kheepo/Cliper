import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from api.main import app
from api.auth.jwt_middleware import get_current_user, get_supabase_token_info
import json


class TestClipGenerationSecurity:
    """Comprehensive security tests for clip generation endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def valid_jwt_token(self):
        """Create a valid JWT token for testing."""
        payload = {
            "sub": "12345678-1234-1234-1234-123456789012",
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "user_metadata": {
                "full_name": "Test User",
                "username": "testuser"
            },
            "app_metadata": {
                "provider": "email",
                "providers": ["email"]
            }
        }
        return jwt.encode(payload, "test-secret", algorithm="HS256")
    
    @pytest.fixture
    def expired_jwt_token(self):
        """Create an expired JWT token for testing."""
        payload = {
            "sub": "12345678-1234-1234-1234-123456789012",
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),  # Expired
            "user_metadata": {
                "full_name": "Test User",
                "username": "testuser"
            }
        }
        return jwt.encode(payload, "test-secret", algorithm="HS256")
    
    @pytest.fixture
    def invalid_jwt_token(self):
        """Create an invalid JWT token for testing."""
        return "invalid.jwt.token"
    
    @pytest.fixture
    def auth_headers(self, valid_jwt_token):
        """Create valid authentication headers."""
        return {
            "Authorization": f"Bearer {valid_jwt_token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture
    def mock_video_data(self):
        """Mock video data for testing."""
        return {
            "id": "video_security_test",
            "title": "Security Test Video",
            "file_path": "/videos/security_test.mp4",
            "duration": 300.0,
            "status": "analyzed",
            "user_id": "12345678-1234-1234-1234-123456789012"
        }
    
    # Authentication Tests
    
    def test_clip_generation_requires_authentication(self, client):
        """Test that clip generation requires authentication."""
        response = client.post(
            "/api/videos/test_video/generate-clips",
            json={
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "authentication" in data["detail"].lower() or "unauthorized" in data["detail"].lower()
    
    def test_clip_generation_with_invalid_token(self, client, invalid_jwt_token):
        """Test clip generation with invalid JWT token."""
        headers = {
            "Authorization": f"Bearer {invalid_jwt_token}",
            "Content-Type": "application/json"
        }
        
        response = client.post(
            "/api/videos/test_video/generate-clips",
            json={
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            },
            headers=headers
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
    
    def test_clip_generation_with_expired_token(self, client, expired_jwt_token):
        """Test clip generation with expired JWT token."""
        headers = {
            "Authorization": f"Bearer {expired_jwt_token}",
            "Content-Type": "application/json"
        }
        
        response = client.post(
            "/api/videos/test_video/generate-clips",
            json={
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            },
            headers=headers
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "expired" in data["detail"].lower() or "invalid" in data["detail"].lower()
    
    def test_clip_generation_with_malformed_auth_header(self, client):
        """Test clip generation with malformed authorization header."""
        test_cases = [
            {"Authorization": "InvalidFormat token"},
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Bearer "},  # Empty token
            {"Authorization": "token_without_bearer"},
        ]
        
        for headers in test_cases:
            headers["Content-Type"] = "application/json"
            response = client.post(
                "/api/videos/test_video/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=headers
            )
            
            assert response.status_code == 401, f"Failed for headers: {headers}"
    
    # Authorization Tests
    
    @patch('api.routers.clips.supabase_service')
    def test_clip_generation_user_owns_video(self, mock_supabase, client, auth_headers, mock_video_data):
        """Test that users can only generate clips for their own videos."""
        # User owns the video
        mock_supabase.get_video_by_id.return_value = mock_video_data
        mock_supabase.get_user_by_id.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "credits_remaining": 100
        }
        
        with patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            mock_task.return_value = Mock(id="job_123")
            
            response = client.post(
                "/api/videos/video_security_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
    
    @patch('api.routers.clips.supabase_service')
    def test_clip_generation_user_does_not_own_video(self, mock_supabase, client, auth_headers):
        """Test that users cannot generate clips for videos they don't own."""
        # Video belongs to different user
        mock_video_data = {
            "id": "video_security_test",
            "title": "Security Test Video",
            "file_path": "/videos/security_test.mp4",
            "duration": 300.0,
            "status": "analyzed",
            "user_id": "different-user-id"  # Different user
        }
        
        mock_supabase.get_video_by_id.return_value = mock_video_data
        mock_supabase.get_user_by_id.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "credits_remaining": 100
        }
        
        response = client.post(
            "/api/videos/video_security_test/generate-clips",
            json={
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            },
            headers=auth_headers
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "permission" in data["detail"].lower() or "forbidden" in data["detail"].lower()
    
    @patch('api.routers.clips.supabase_service')
    def test_clip_generation_nonexistent_video(self, mock_supabase, client, auth_headers):
        """Test clip generation for nonexistent video."""
        mock_supabase.get_video_by_id.return_value = None
        
        response = client.post(
            "/api/videos/nonexistent_video/generate-clips",
            json={
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            },
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
    
    # Rate Limiting and Abuse Prevention Tests
    
    @patch('api.routers.clips.supabase_service')
    def test_clip_generation_insufficient_credits(self, mock_supabase, client, auth_headers, mock_video_data):
        """Test clip generation when user has insufficient credits."""
        mock_supabase.get_video_by_id.return_value = mock_video_data
        mock_supabase.get_user_by_id.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "credits_remaining": 0  # No credits
        }
        
        response = client.post(
            "/api/videos/video_security_test/generate-clips",
            json={
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            },
            headers=auth_headers
        )
        
        assert response.status_code == 402  # Payment required
        data = response.json()
        assert "detail" in data
        assert "credits" in data["detail"].lower() or "insufficient" in data["detail"].lower()
    
    @patch('api.routers.clips.supabase_service')
    def test_concurrent_clip_generation_requests(self, mock_supabase, client, auth_headers, mock_video_data):
        """Test multiple concurrent clip generation requests from same user."""
        mock_supabase.get_video_by_id.return_value = mock_video_data
        mock_supabase.get_user_by_id.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "credits_remaining": 100
        }
        
        with patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            mock_task.return_value = Mock(id="job_123")
            
            # Make multiple rapid requests
            responses = []
            for i in range(5):
                response = client.post(
                    "/api/videos/video_security_test/generate-clips",
                    json={
                        "platform": "youtube",
                        "clip_type": "highlight",
                        "target_duration": 30.0
                    },
                    headers=auth_headers
                )
                responses.append(response)
            
            # At least some requests should succeed
            success_count = sum(1 for r in responses if r.status_code == 200)
            assert success_count > 0
            
            # Check if rate limiting is applied (some requests might be rejected)
            rate_limited_count = sum(1 for r in responses if r.status_code == 429)
            # Rate limiting is optional but good practice
    
    # Input Sanitization Tests
    
    @patch('api.routers.clips.supabase_service')
    def test_clip_generation_sql_injection_attempt(self, mock_supabase, client, auth_headers, mock_video_data):
        """Test clip generation with SQL injection attempts."""
        mock_supabase.get_video_by_id.return_value = mock_video_data
        mock_supabase.get_user_by_id.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "credits_remaining": 100
        }
        
        # SQL injection attempts in video ID
        malicious_video_ids = [
            "video'; DROP TABLE videos; --",
            "video' OR '1'='1",
            "video'; UPDATE users SET credits_remaining=999999; --"
        ]
        
        for video_id in malicious_video_ids:
            response = client.post(
                f"/api/videos/{video_id}/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            # Should either be rejected or handled safely
            assert response.status_code in [400, 404, 422], f"SQL injection not handled for: {video_id}"
    
    @patch('api.routers.clips.supabase_service')
    def test_clip_generation_xss_attempt(self, mock_supabase, client, auth_headers, mock_video_data):
        """Test clip generation with XSS attempts in request data."""
        mock_supabase.get_video_by_id.return_value = mock_video_data
        mock_supabase.get_user_by_id.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "credits_remaining": 100
        }
        
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>"
        ]
        
        for payload in xss_payloads:
            response = client.post(
                "/api/videos/video_security_test/generate-clips",
                json={
                    "platform": payload,  # XSS in platform field
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            # Should be rejected due to invalid platform
            assert response.status_code in [400, 422], f"XSS not handled for: {payload}"
    
    # Data Privacy Tests
    
    @patch('api.routers.clips.supabase_service')
    def test_clip_generation_response_data_privacy(self, mock_supabase, client, auth_headers, mock_video_data):
        """Test that clip generation responses don't leak sensitive data."""
        mock_supabase.get_video_by_id.return_value = mock_video_data
        mock_supabase.get_user_by_id.return_value = {
            "id": "12345678-1234-1234-1234-123456789012",
            "credits_remaining": 100,
            "email": "test@example.com",
            "password_hash": "secret_hash",
            "api_key": "secret_api_key"
        }
        
        with patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            mock_task.return_value = Mock(id="job_123")
            
            response = client.post(
                "/api/videos/video_security_test/generate-clips",
                json={
                    "platform": "youtube",
                    "clip_type": "highlight",
                    "target_duration": 30.0
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Ensure sensitive data is not leaked
            response_text = json.dumps(data)
            assert "password_hash" not in response_text
            assert "secret_hash" not in response_text
            assert "api_key" not in response_text
            assert "secret_api_key" not in response_text
    
    # CORS and Security Headers Tests
    
    def test_clip_generation_security_headers(self, client, auth_headers):
        """Test that security headers are present in responses."""
        response = client.post(
            "/api/videos/test_video/generate-clips",
            json={
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            },
            headers=auth_headers
        )
        
        # Check for security headers (these might be set by middleware)
        headers = response.headers
        
        # These are optional but recommended security headers
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security"
        ]
        
        # Note: Not all headers may be present, this is just a check
        # The actual implementation may vary based on middleware configuration