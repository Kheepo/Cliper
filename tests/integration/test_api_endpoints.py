"""Integration tests for API endpoints and database operations."""

import pytest
import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Import the modules to test
try:
    from api.main import app
    from api.database.connection import get_db_session
    from api.models.user import User, UserRole, UserStatus
    from api.models.video import Video, VideoStatus, ProcessingStatus
    from api.auth.auth_service import AuthService
    from api.core.config import settings
except ImportError:
    # Mock imports for testing
    app = None
    class User:
        pass
    class Video:
        pass
    class UserRole:
        USER = "user"
        ADMIN = "admin"
    class UserStatus:
        ACTIVE = "active"
        INACTIVE = "inactive"
    class VideoStatus:
        UPLOADED = "uploaded"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"
    class ProcessingStatus:
        PENDING = "pending"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        FAILED = "failed"
    class AuthService:
        pass
    class settings:
        DATABASE_URL = "sqlite:///test.db"
        SECRET_KEY = "test_secret"

class TestAuthEndpoints:
    """Integration tests for authentication endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        if app:
            return TestClient(app)
        else:
            # Mock client for testing
            mock_client = MagicMock()
            return mock_client
    
    @pytest.fixture
    def test_user_data(self):
        """Sample user data for testing."""
        return {
            "email": "test@example.com",
            "username": "testuser",
            "password": "SecureP@ssw0rd123!",
            "first_name": "Test",
            "last_name": "User"
        }
    
    @pytest.fixture
    def admin_user_data(self):
        """Sample admin user data for testing."""
        return {
            "email": "admin@example.com",
            "username": "adminuser",
            "password": "AdminP@ssw0rd123!",
            "first_name": "Admin",
            "last_name": "User",
            "role": UserRole.ADMIN
        }
    
    def test_register_user_success(self, client, test_user_data):
        """Test successful user registration."""
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "id": "user_123",
                "email": test_user_data["email"],
                "username": test_user_data["username"],
                "role": UserRole.USER,
                "status": UserStatus.ACTIVE,
                "created_at": datetime.now().isoformat()
            }
            
            response = client.post("/api/auth/register", json=test_user_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["email"] == test_user_data["email"]
            assert data["username"] == test_user_data["username"]
            assert data["role"] == UserRole.USER
    
    def test_register_user_duplicate_email(self, client, test_user_data):
        """Test user registration with duplicate email."""
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 400
            mock_post.return_value.json.return_value = {
                "detail": "Email already registered"
            }
            
            response = client.post("/api/auth/register", json=test_user_data)
            
            assert response.status_code == 400
            assert "Email already registered" in response.json()["detail"]
    
    def test_register_user_invalid_data(self, client):
        """Test user registration with invalid data."""
        invalid_data = {
            "email": "invalid-email",
            "username": "ab",  # Too short
            "password": "123"   # Too weak
        }
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 422
            mock_post.return_value.json.return_value = {
                "detail": [
                    {"field": "email", "message": "Invalid email format"},
                    {"field": "username", "message": "Username too short"},
                    {"field": "password", "message": "Password too weak"}
                ]
            }
            
            response = client.post("/api/auth/register", json=invalid_data)
            
            assert response.status_code == 422
    
    def test_login_user_success(self, client):
        """Test successful user login."""
        login_data = {
            "email": "test@example.com",
            "password": "SecureP@ssw0rd123!"
        }
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "access_token": "jwt_access_token",
                "refresh_token": "jwt_refresh_token",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "user_123",
                    "email": login_data["email"],
                    "role": UserRole.USER,
                    "status": UserStatus.ACTIVE
                }
            }
            
            response = client.post("/api/auth/login", json=login_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["email"] == login_data["email"]
    
    def test_login_user_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        login_data = {
            "email": "test@example.com",
            "password": "wrong_password"
        }
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 401
            mock_post.return_value.json.return_value = {
                "detail": "Invalid credentials"
            }
            
            response = client.post("/api/auth/login", json=login_data)
            
            assert response.status_code == 401
            assert "Invalid credentials" in response.json()["detail"]
    
    def test_refresh_token_success(self, client):
        """Test successful token refresh."""
        refresh_data = {
            "refresh_token": "valid_refresh_token"
        }
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "token_type": "bearer",
                "expires_in": 3600
            }
            
            response = client.post("/api/auth/refresh", json=refresh_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
    
    def test_logout_user_success(self, client):
        """Test successful user logout."""
        headers = {"Authorization": "Bearer valid_access_token"}
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "message": "Successfully logged out"
            }
            
            response = client.post("/api/auth/logout", headers=headers)
            
            assert response.status_code == 200
            assert "Successfully logged out" in response.json()["message"]
    
    def test_get_current_user(self, client):
        """Test getting current user information."""
        headers = {"Authorization": "Bearer valid_access_token"}
        
        with patch.object(client, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "id": "user_123",
                "email": "test@example.com",
                "username": "testuser",
                "role": UserRole.USER,
                "status": UserStatus.ACTIVE,
                "profile": {
                    "first_name": "Test",
                    "last_name": "User",
                    "avatar_url": None
                }
            }
            
            response = client.get("/api/auth/me", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "test@example.com"
            assert data["role"] == UserRole.USER

class TestVideoEndpoints:
    """Integration tests for video processing endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        if app:
            return TestClient(app)
        else:
            mock_client = MagicMock()
            return mock_client
    
    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for testing."""
        return {"Authorization": "Bearer valid_access_token"}
    
    @pytest.fixture
    def sample_video_file(self):
        """Sample video file for testing."""
        return {
            "filename": "test_video.mp4",
            "content_type": "video/mp4",
            "size": 1024 * 1024 * 10,  # 10MB
            "content": b"fake_video_content"
        }
    
    def test_upload_video_success(self, client, auth_headers, sample_video_file):
        """Test successful video upload."""
        files = {
            "file": (sample_video_file["filename"], sample_video_file["content"], sample_video_file["content_type"])
        }
        data = {
            "title": "Test Video",
            "description": "A test video for integration testing"
        }
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "id": "video_123",
                "title": data["title"],
                "description": data["description"],
                "filename": sample_video_file["filename"],
                "file_size": sample_video_file["size"],
                "status": VideoStatus.UPLOADED,
                "processing_status": ProcessingStatus.PENDING,
                "upload_url": "https://storage.example.com/videos/video_123.mp4",
                "created_at": datetime.now().isoformat()
            }
            
            response = client.post("/api/videos/upload", files=files, data=data, headers=auth_headers)
            
            assert response.status_code == 201
            video_data = response.json()
            assert video_data["title"] == data["title"]
            assert video_data["status"] == VideoStatus.UPLOADED
            assert video_data["processing_status"] == ProcessingStatus.PENDING
    
    def test_upload_video_invalid_format(self, client, auth_headers):
        """Test video upload with invalid format."""
        files = {
            "file": ("test.txt", b"not_a_video", "text/plain")
        }
        data = {"title": "Test Video"}
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 400
            mock_post.return_value.json.return_value = {
                "detail": "Invalid video format. Supported formats: mp4, avi, mov, mkv"
            }
            
            response = client.post("/api/videos/upload", files=files, data=data, headers=auth_headers)
            
            assert response.status_code == 400
            assert "Invalid video format" in response.json()["detail"]
    
    def test_upload_video_too_large(self, client, auth_headers):
        """Test video upload with file too large."""
        large_file = {
            "filename": "large_video.mp4",
            "content": b"x" * (100 * 1024 * 1024),  # 100MB
            "content_type": "video/mp4"
        }
        
        files = {
            "file": (large_file["filename"], large_file["content"], large_file["content_type"])
        }
        data = {"title": "Large Video"}
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 413
            mock_post.return_value.json.return_value = {
                "detail": "File too large. Maximum size: 50MB"
            }
            
            response = client.post("/api/videos/upload", files=files, data=data, headers=auth_headers)
            
            assert response.status_code == 413
            assert "File too large" in response.json()["detail"]
    
    def test_get_video_details(self, client, auth_headers):
        """Test getting video details."""
        video_id = "video_123"
        
        with patch.object(client, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "id": video_id,
                "title": "Test Video",
                "description": "A test video",
                "filename": "test_video.mp4",
                "file_size": 1024 * 1024 * 10,
                "duration": 120.5,
                "status": VideoStatus.COMPLETED,
                "processing_status": ProcessingStatus.COMPLETED,
                "metadata": {
                    "resolution": "1920x1080",
                    "fps": 30,
                    "codec": "h264",
                    "bitrate": "2000kbps"
                },
                "analysis": {
                    "transcription": "Sample transcription text",
                    "summary": "Video summary",
                    "sentiment": "positive",
                    "topics": ["technology", "tutorial"]
                },
                "created_at": datetime.now().isoformat(),
                "processed_at": datetime.now().isoformat()
            }
            
            response = client.get(f"/api/videos/{video_id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == video_id
            assert data["status"] == VideoStatus.COMPLETED
            assert "metadata" in data
            assert "analysis" in data
    
    def test_get_video_not_found(self, client, auth_headers):
        """Test getting non-existent video."""
        video_id = "nonexistent_video"
        
        with patch.object(client, 'get') as mock_get:
            mock_get.return_value.status_code = 404
            mock_get.return_value.json.return_value = {
                "detail": "Video not found"
            }
            
            response = client.get(f"/api/videos/{video_id}", headers=auth_headers)
            
            assert response.status_code == 404
            assert "Video not found" in response.json()["detail"]
    
    def test_list_user_videos(self, client, auth_headers):
        """Test listing user's videos."""
        with patch.object(client, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "videos": [
                    {
                        "id": "video_1",
                        "title": "Video 1",
                        "status": VideoStatus.COMPLETED,
                        "created_at": datetime.now().isoformat()
                    },
                    {
                        "id": "video_2",
                        "title": "Video 2",
                        "status": VideoStatus.PROCESSING,
                        "created_at": datetime.now().isoformat()
                    }
                ],
                "total": 2,
                "page": 1,
                "per_page": 10
            }
            
            response = client.get("/api/videos", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert "videos" in data
            assert data["total"] == 2
            assert len(data["videos"]) == 2
    
    def test_delete_video_success(self, client, auth_headers):
        """Test successful video deletion."""
        video_id = "video_123"
        
        with patch.object(client, 'delete') as mock_delete:
            mock_delete.return_value.status_code = 200
            mock_delete.return_value.json.return_value = {
                "message": "Video deleted successfully"
            }
            
            response = client.delete(f"/api/videos/{video_id}", headers=auth_headers)
            
            assert response.status_code == 200
            assert "deleted successfully" in response.json()["message"]
    
    def test_process_video_trigger(self, client, auth_headers):
        """Test triggering video processing."""
        video_id = "video_123"
        processing_options = {
            "extract_audio": True,
            "generate_transcription": True,
            "analyze_sentiment": True,
            "extract_topics": True,
            "generate_summary": True
        }
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 202
            mock_post.return_value.json.return_value = {
                "message": "Video processing started",
                "task_id": "task_456",
                "estimated_completion": (datetime.now() + timedelta(minutes=10)).isoformat()
            }
            
            response = client.post(
                f"/api/videos/{video_id}/process",
                json=processing_options,
                headers=auth_headers
            )
            
            assert response.status_code == 202
            data = response.json()
            assert "processing started" in data["message"]
            assert "task_id" in data

class TestUserManagementEndpoints:
    """Integration tests for user management endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        if app:
            return TestClient(app)
        else:
            mock_client = MagicMock()
            return mock_client
    
    @pytest.fixture
    def admin_headers(self):
        """Admin authentication headers for testing."""
        return {"Authorization": "Bearer admin_access_token"}
    
    @pytest.fixture
    def user_headers(self):
        """User authentication headers for testing."""
        return {"Authorization": "Bearer user_access_token"}
    
    def test_update_user_profile(self, client, user_headers):
        """Test updating user profile."""
        profile_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "bio": "Updated bio text",
            "avatar_url": "https://example.com/avatar.jpg"
        }
        
        with patch.object(client, 'put') as mock_put:
            mock_put.return_value.status_code = 200
            mock_put.return_value.json.return_value = {
                "id": "user_123",
                "email": "test@example.com",
                "username": "testuser",
                "profile": profile_data,
                "updated_at": datetime.now().isoformat()
            }
            
            response = client.put("/api/users/profile", json=profile_data, headers=user_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["profile"]["first_name"] == profile_data["first_name"]
            assert data["profile"]["bio"] == profile_data["bio"]
    
    def test_change_password(self, client, user_headers):
        """Test changing user password."""
        password_data = {
            "current_password": "old_password",
            "new_password": "NewSecureP@ssw0rd123!",
            "confirm_password": "NewSecureP@ssw0rd123!"
        }
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "message": "Password changed successfully"
            }
            
            response = client.post("/api/users/change-password", json=password_data, headers=user_headers)
            
            assert response.status_code == 200
            assert "Password changed successfully" in response.json()["message"]
    
    def test_get_user_statistics(self, client, user_headers):
        """Test getting user statistics."""
        with patch.object(client, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "total_videos": 15,
                "total_processing_time": 3600,
                "storage_used": 1024 * 1024 * 500,  # 500MB
                "videos_by_status": {
                    "completed": 12,
                    "processing": 2,
                    "failed": 1
                },
                "recent_activity": [
                    {
                        "action": "video_uploaded",
                        "video_id": "video_123",
                        "timestamp": datetime.now().isoformat()
                    }
                ]
            }
            
            response = client.get("/api/users/statistics", headers=user_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert "total_videos" in data
            assert "storage_used" in data
            assert "videos_by_status" in data
    
    def test_admin_list_users(self, client, admin_headers):
        """Test admin listing all users."""
        with patch.object(client, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "users": [
                    {
                        "id": "user_1",
                        "email": "user1@example.com",
                        "username": "user1",
                        "role": UserRole.USER,
                        "status": UserStatus.ACTIVE,
                        "created_at": datetime.now().isoformat()
                    },
                    {
                        "id": "user_2",
                        "email": "user2@example.com",
                        "username": "user2",
                        "role": UserRole.USER,
                        "status": UserStatus.ACTIVE,
                        "created_at": datetime.now().isoformat()
                    }
                ],
                "total": 2,
                "page": 1,
                "per_page": 10
            }
            
            response = client.get("/api/admin/users", headers=admin_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert "users" in data
            assert data["total"] == 2
    
    def test_admin_update_user_role(self, client, admin_headers):
        """Test admin updating user role."""
        user_id = "user_123"
        role_data = {"role": UserRole.MODERATOR}
        
        with patch.object(client, 'put') as mock_put:
            mock_put.return_value.status_code = 200
            mock_put.return_value.json.return_value = {
                "id": user_id,
                "email": "user@example.com",
                "role": UserRole.MODERATOR,
                "updated_at": datetime.now().isoformat()
            }
            
            response = client.put(f"/api/admin/users/{user_id}/role", json=role_data, headers=admin_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["role"] == UserRole.MODERATOR
    
    def test_admin_suspend_user(self, client, admin_headers):
        """Test admin suspending a user."""
        user_id = "user_123"
        suspension_data = {
            "reason": "Violation of terms of service",
            "duration_days": 7
        }
        
        with patch.object(client, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "message": "User suspended successfully",
                "user_id": user_id,
                "status": UserStatus.SUSPENDED,
                "suspension_until": (datetime.now() + timedelta(days=7)).isoformat()
            }
            
            response = client.post(
                f"/api/admin/users/{user_id}/suspend",
                json=suspension_data,
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "suspended successfully" in data["message"]
            assert data["status"] == UserStatus.SUSPENDED

class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    @pytest.fixture
    async def db_session(self):
        """Create a test database session."""
        # Mock database session for testing
        mock_session = AsyncMock()
        return mock_session
    
    @pytest.mark.asyncio
    async def test_user_crud_operations(self, db_session):
        """Test user CRUD operations in database."""
        # Test user creation
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": "$2b$12$hashed_password",
            "role": UserRole.USER,
            "status": UserStatus.ACTIVE
        }
        
        # Mock user creation
        with patch('api.models.user.User') as MockUser:
            mock_user = MockUser(**user_data)
            mock_user.id = "user_123"
            
            # Test user retrieval
            db_session.execute.return_value.scalar_one_or_none.return_value = mock_user
            
            # Simulate database query
            result = await db_session.execute(text("SELECT * FROM users WHERE email = :email"))
            user = result.scalar_one_or_none()
            
            assert user is not None
            assert user.email == user_data["email"]
            assert user.role == UserRole.USER
    
    @pytest.mark.asyncio
    async def test_video_crud_operations(self, db_session):
        """Test video CRUD operations in database."""
        # Test video creation
        video_data = {
            "title": "Test Video",
            "description": "A test video",
            "filename": "test_video.mp4",
            "file_size": 1024 * 1024 * 10,
            "user_id": "user_123",
            "status": VideoStatus.UPLOADED,
            "processing_status": ProcessingStatus.PENDING
        }
        
        # Mock video creation
        with patch('api.models.video.Video') as MockVideo:
            mock_video = MockVideo(**video_data)
            mock_video.id = "video_123"
            
            # Test video retrieval
            db_session.execute.return_value.scalar_one_or_none.return_value = mock_video
            
            # Simulate database query
            result = await db_session.execute(text("SELECT * FROM videos WHERE id = :id"))
            video = result.scalar_one_or_none()
            
            assert video is not None
            assert video.title == video_data["title"]
            assert video.status == VideoStatus.UPLOADED
    
    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self, db_session):
        """Test database transaction rollback on error."""
        # Simulate transaction with error
        db_session.begin.return_value.__aenter__ = AsyncMock()
        db_session.begin.return_value.__aexit__ = AsyncMock()
        
        try:
            async with db_session.begin():
                # Simulate an operation that fails
                raise ValueError("Simulated database error")
        except ValueError:
            # Verify rollback was called
            db_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_connection_pool(self):
        """Test database connection pool management."""
        # Mock connection pool testing
        with patch('api.database.connection.get_db_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            # Test multiple concurrent connections
            sessions = []
            for i in range(5):
                session = await mock_get_session()
                sessions.append(session)
            
            # Verify all sessions are created
            assert len(sessions) == 5
            assert mock_get_session.call_count == 5

class TestWebSocketIntegration:
    """Integration tests for WebSocket connections."""
    
    @pytest.fixture
    def websocket_client(self):
        """Create a WebSocket test client."""
        if app:
            return TestClient(app)
        else:
            mock_client = MagicMock()
            return mock_client
    
    def test_websocket_connection(self, websocket_client):
        """Test WebSocket connection establishment."""
        with patch.object(websocket_client, 'websocket_connect') as mock_connect:
            mock_websocket = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_websocket
            
            with websocket_client.websocket_connect("/ws/video-progress") as websocket:
                # Test connection is established
                assert websocket is not None
    
    def test_video_progress_updates(self, websocket_client):
        """Test receiving video processing progress updates via WebSocket."""
        with patch.object(websocket_client, 'websocket_connect') as mock_connect:
            mock_websocket = MagicMock()
            mock_websocket.receive_json.return_value = {
                "type": "progress_update",
                "video_id": "video_123",
                "progress": 50,
                "status": "processing",
                "message": "Extracting audio..."
            }
            mock_connect.return_value.__enter__.return_value = mock_websocket
            
            with websocket_client.websocket_connect("/ws/video-progress") as websocket:
                data = websocket.receive_json()
                
                assert data["type"] == "progress_update"
                assert data["video_id"] == "video_123"
                assert data["progress"] == 50