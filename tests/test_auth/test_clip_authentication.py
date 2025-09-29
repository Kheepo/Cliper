import pytest
import jwt
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

from api.main import app
from api.models.user import User
from api.models.video import Video
from api.models.clip import GeneratedClip
from api.core.config import settings


class TestClipAuthenticationEndpoints:
    """Comprehensive authentication tests for clip generation endpoints."""
    
    def setup_method(self):
        """Setup test client and common test data."""
        self.client = TestClient(app)
        self.test_user_id = "test_user_123"
        self.test_video_id = "test_video_456"
        self.secret_key = settings.SECRET_KEY
        
        # Valid JWT payload
        self.valid_payload = {
            "sub": self.test_user_id,
            "email": "test@example.com",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
            "aud": "cliper-app",
            "iss": "cliper-auth"
        }
        
        # Generate valid token
        self.valid_token = jwt.encode(
            self.valid_payload, 
            self.secret_key, 
            algorithm="HS256"
        )
        
        self.auth_headers = {"Authorization": f"Bearer {self.valid_token}"}
        
        # Mock video data
        self.mock_video_data = {
            "title": "Test Video",
            "platform": "youtube",
            "duration": 300,
            "file_path": "/test/video.mp4"
        }
        
        # Mock clip generation request
        self.clip_request = {
            "video_id": self.test_video_id,
            "platform": "youtube",
            "max_clips": 3,
            "min_duration": 30,
            "max_duration": 60
        }
    
    def test_generate_clip_with_valid_jwt(self):
        """Test clip generation with valid JWT token."""
        with patch('api.services.user_service.get_user_by_id') as mock_get_user, \
             patch('api.services.video_service.get_video_by_id') as mock_get_video, \
             patch('api.services.clip_service.generate_clip') as mock_generate:
            
            # Setup mocks
            mock_user = MagicMock(spec=User)
            mock_user.id = self.test_user_id
            mock_user.credits = 100
            mock_get_user.return_value = mock_user
            
            mock_video = MagicMock(spec=Video)
            mock_video.id = self.test_video_id
            mock_video.user_id = self.test_user_id
            mock_get_video.return_value = mock_video
            
            mock_clip = MagicMock(spec=GeneratedClip)
            mock_clip.id = "clip_123"
            mock_generate.return_value = mock_clip
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            mock_get_user.assert_called_once_with(self.test_user_id)
            mock_generate.assert_called_once()
    
    def test_generate_clip_without_authorization_header(self):
        """Test clip generation without Authorization header."""
        response = self.client.post(
            "/api/clips/generate",
            json=self.clip_request
        )
        
        assert response.status_code == 401
        assert "Authorization header missing" in response.json()["detail"]
    
    def test_generate_clip_with_malformed_authorization_header(self):
        """Test clip generation with malformed Authorization header."""
        malformed_headers = [
            {"Authorization": "InvalidFormat"},
            {"Authorization": "Bearer"},
            {"Authorization": "Basic dGVzdA=="},
            {"Authorization": f"Token {self.valid_token}"}
        ]
        
        for headers in malformed_headers:
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=headers
            )
            
            assert response.status_code == 401
            assert "Invalid authorization format" in response.json()["detail"]
    
    def test_generate_clip_with_invalid_jwt_token(self):
        """Test clip generation with invalid JWT token."""
        invalid_tokens = [
            "invalid.jwt.token",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid",
            "",
            "null"
        ]
        
        for token in invalid_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=headers
            )
            
            assert response.status_code == 401
            assert "Invalid token" in response.json()["detail"]
    
    def test_generate_clip_with_expired_jwt_token(self):
        """Test clip generation with expired JWT token."""
        expired_payload = self.valid_payload.copy()
        expired_payload["exp"] = datetime.utcnow() - timedelta(hours=1)
        
        expired_token = jwt.encode(
            expired_payload,
            self.secret_key,
            algorithm="HS256"
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = self.client.post(
            "/api/clips/generate",
            json=self.clip_request,
            headers=headers
        )
        
        assert response.status_code == 401
        assert "Token expired" in response.json()["detail"]
    
    def test_generate_clip_with_wrong_secret_key(self):
        """Test clip generation with token signed with wrong secret."""
        wrong_secret_token = jwt.encode(
            self.valid_payload,
            "wrong_secret_key",
            algorithm="HS256"
        )
        
        headers = {"Authorization": f"Bearer {wrong_secret_token}"}
        response = self.client.post(
            "/api/clips/generate",
            json=self.clip_request,
            headers=headers
        )
        
        assert response.status_code == 401
        assert "Invalid token signature" in response.json()["detail"]
    
    def test_generate_clip_with_missing_required_claims(self):
        """Test clip generation with JWT missing required claims."""
        missing_claims_payloads = [
            {"email": "test@example.com"},  # Missing sub
            {"sub": self.test_user_id},  # Missing email
            {"sub": self.test_user_id, "email": "test@example.com"},  # Missing exp
            {"sub": self.test_user_id, "email": "test@example.com", "exp": datetime.utcnow() + timedelta(hours=1)}  # Missing aud
        ]
        
        for payload in missing_claims_payloads:
            token = jwt.encode(payload, self.secret_key, algorithm="HS256")
            headers = {"Authorization": f"Bearer {token}"}
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=headers
            )
            
            assert response.status_code == 401
            assert "Missing required claims" in response.json()["detail"]
    
    def test_generate_clip_with_invalid_audience(self):
        """Test clip generation with invalid audience claim."""
        invalid_aud_payload = self.valid_payload.copy()
        invalid_aud_payload["aud"] = "wrong-audience"
        
        invalid_aud_token = jwt.encode(
            invalid_aud_payload,
            self.secret_key,
            algorithm="HS256"
        )
        
        headers = {"Authorization": f"Bearer {invalid_aud_token}"}
        response = self.client.post(
            "/api/clips/generate",
            json=self.clip_request,
            headers=headers
        )
        
        assert response.status_code == 401
        assert "Invalid audience" in response.json()["detail"]
    
    def test_generate_clip_with_nonexistent_user(self):
        """Test clip generation when user doesn't exist in database."""
        with patch('api.services.user_service.get_user_by_id') as mock_get_user:
            mock_get_user.return_value = None
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 404
            assert "User not found" in response.json()["detail"]
    
    def test_generate_clip_with_insufficient_credits(self):
        """Test clip generation when user has insufficient credits."""
        with patch('api.services.user_service.get_user_by_id') as mock_get_user:
            mock_user = MagicMock(spec=User)
            mock_user.id = self.test_user_id
            mock_user.credits = 0  # No credits
            mock_get_user.return_value = mock_user
            
            response = self.client.post(
                "/api/clips/generate",
                json=self.clip_request,
                headers=self.auth_headers
            )
            
            assert response.status_code == 402
            assert "Insufficient credits" in response.json()["detail"]
    
    def test_get_clip_with_valid_authentication(self):
        """Test retrieving clip with valid authentication."""
        clip_id = "test_clip_123"
        
        with patch('api.services.user_service.get_user_by_id') as mock_get_user, \
             patch('api.services.clip_service.get_clip_by_id') as mock_get_clip:
            
            mock_user = MagicMock(spec=User)
            mock_user.id = self.test_user_id
            mock_get_user.return_value = mock_user
            
            mock_clip = MagicMock(spec=GeneratedClip)
            mock_clip.id = clip_id
            mock_clip.user_id = self.test_user_id
            mock_get_clip.return_value = mock_clip
            
            response = self.client.get(
                f"/api/clips/{clip_id}",
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            mock_get_user.assert_called_once_with(self.test_user_id)
            mock_get_clip.assert_called_once_with(clip_id)
    
    def test_get_clip_without_authentication(self):
        """Test retrieving clip without authentication."""
        clip_id = "test_clip_123"
        
        response = self.client.get(f"/api/clips/{clip_id}")
        
        assert response.status_code == 401
        assert "Authorization header missing" in response.json()["detail"]
    
    def test_list_user_clips_with_valid_authentication(self):
        """Test listing user clips with valid authentication."""
        with patch('api.services.user_service.get_user_by_id') as mock_get_user, \
             patch('api.services.clip_service.get_clips_by_user_id') as mock_get_clips:
            
            mock_user = MagicMock(spec=User)
            mock_user.id = self.test_user_id
            mock_get_user.return_value = mock_user
            
            mock_clips = [MagicMock(spec=GeneratedClip) for _ in range(3)]
            mock_get_clips.return_value = mock_clips
            
            response = self.client.get(
                "/api/clips/user/me",
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            mock_get_user.assert_called_once_with(self.test_user_id)
            mock_get_clips.assert_called_once_with(self.test_user_id)
    
    def test_delete_clip_with_valid_authentication(self):
        """Test deleting clip with valid authentication."""
        clip_id = "test_clip_123"
        
        with patch('api.services.user_service.get_user_by_id') as mock_get_user, \
             patch('api.services.clip_service.get_clip_by_id') as mock_get_clip, \
             patch('api.services.clip_service.delete_clip') as mock_delete:
            
            mock_user = MagicMock(spec=User)
            mock_user.id = self.test_user_id
            mock_get_user.return_value = mock_user
            
            mock_clip = MagicMock(spec=GeneratedClip)
            mock_clip.id = clip_id
            mock_clip.user_id = self.test_user_id
            mock_get_clip.return_value = mock_clip
            
            response = self.client.delete(
                f"/api/clips/{clip_id}",
                headers=self.auth_headers
            )
            
            assert response.status_code == 204
            mock_delete.assert_called_once_with(clip_id)
    
    def test_jwt_token_refresh_scenario(self):
        """Test scenario where token is refreshed during operation."""
        # Create a token that expires soon
        soon_expire_payload = self.valid_payload.copy()
        soon_expire_payload["exp"] = datetime.utcnow() + timedelta(seconds=30)
        
        soon_expire_token = jwt.encode(
            soon_expire_payload,
            self.secret_key,
            algorithm="HS256"
        )
        
        headers = {"Authorization": f"Bearer {soon_expire_token}"}
        
        with patch('api.services.user_service.get_user_by_id') as mock_get_user:
            mock_user = MagicMock(spec=User)
            mock_user.id = self.test_user_id
            mock_user.credits = 100
            mock_get_user.return_value = mock_user
            
            # First request should work
            response = self.client.get(
                "/api/clips/user/me",
                headers=headers
            )
            
            assert response.status_code == 200
    
    def test_concurrent_authentication_requests(self):
        """Test multiple concurrent requests with same token."""
        import threading
        import time
        
        results = []
        
        def make_request():
            with patch('api.services.user_service.get_user_by_id') as mock_get_user:
                mock_user = MagicMock(spec=User)
                mock_user.id = self.test_user_id
                mock_get_user.return_value = mock_user
                
                response = self.client.get(
                    "/api/clips/user/me",
                    headers=self.auth_headers
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
        assert all(status == 200 for status in results)
        assert len(results) == 5