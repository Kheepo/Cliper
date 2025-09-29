import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from api.main import app

class TestHealthEndpoints:
    """Test health check and system monitoring endpoints."""
    
    def test_root_endpoint(self, client):
        """Test the root endpoint returns correct response."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Virality Clipper API"
        assert data["status"] == "running"
    
    def test_health_check(self, client):
        """Test the health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "ok"
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.Process')
    def test_system_metrics(self, mock_process, mock_disk, mock_memory, mock_cpu, client):
        """Test system metrics endpoint."""
        # Mock system metrics
        mock_cpu.return_value = 45.2
        
        mock_memory_obj = Mock()
        mock_memory_obj.total = 8589934592  # 8GB
        mock_memory_obj.available = 4294967296  # 4GB
        mock_memory_obj.percent = 50.0
        mock_memory_obj.used = 4294967296  # 4GB
        mock_memory.return_value = mock_memory_obj
        
        mock_disk_obj = Mock()
        mock_disk_obj.total = 1000000000000  # 1TB
        mock_disk_obj.used = 500000000000   # 500GB
        mock_disk_obj.free = 500000000000   # 500GB
        mock_disk.return_value = mock_disk_obj
        
        mock_process_obj = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 134217728  # 128MB
        mock_memory_info.vms = 268435456  # 256MB
        mock_process_obj.memory_info.return_value = mock_memory_info
        mock_process_obj.cpu_percent.return_value = 15.5
        mock_process.return_value = mock_process_obj
        
        response = client.get("/api/performance/system")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        assert data["cpu"]["percent"] == 45.2
        assert data["memory"]["percent"] == 50.0
        assert data["process"]["cpu_percent"] == 15.5

class TestVideoUploadEndpoints:
    """Test video upload and processing endpoints."""
    
    @patch('api.tasks.process_video_task')
    @patch('api.services.supabase_service.supabase_service')
    def test_video_upload_success(self, mock_supabase, mock_task, client, valid_video_file):
        """Test successful video upload."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.create_job.return_value = "test-job-123"
        mock_supabase.return_value = mock_supabase_instance
        
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = "test-task-123"
        mock_task.delay.return_value = mock_result
        
        filename, content, content_type = valid_video_file
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            response = client.post(
                "/api/videos/upload",
                files={"file": (filename, content, content_type)},
                data={"user_id": "test-user-123"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "processing"
    
    def test_video_upload_no_file(self, client):
        """Test video upload without file."""
        response = client.post(
            "/api/videos/upload",
            data={"user_id": "test-user-123"}
        )
        assert response.status_code == 422  # Validation error
    
    def test_video_upload_invalid_file_type(self, client, invalid_video_file):
        """Test video upload with invalid file type."""
        filename, content, content_type = invalid_video_file
        
        response = client.post(
            "/api/videos/upload",
            files={"file": (filename, content, content_type)},
            data={"user_id": "test-user-123"}
        )
        
        # Should either reject or handle gracefully
        assert response.status_code in [400, 415, 422]
    
    def test_video_upload_large_file(self, client, large_video_file):
        """Test video upload with file exceeding size limit."""
        filename, content, content_type = large_video_file
        
        response = client.post(
            "/api/videos/upload",
            files={"file": (filename, content, content_type)},
            data={"user_id": "test-user-123"}
        )
        
        # Should reject large files
        assert response.status_code in [413, 422]

class TestJobManagementEndpoints:
    """Test job management endpoints."""
    
    @patch('api.services.supabase_service.SupabaseService')
    def test_get_job_status_success(self, mock_supabase, client):
        """Test successful job status retrieval."""
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_job.return_value = {
            "id": "test-job-123",
            "status": "processing",
            "progress": 50,
            "current_step": "transcribing",
            "estimated_remaining": 120.5,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:05:00Z"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            response = client.get("/api/jobs/test-job-123/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-123"
        assert data["status"] == "processing"
        assert data["progress"] == 50
    
    @patch('api.services.supabase_service.SupabaseService')
    def test_get_job_status_not_found(self, mock_supabase, client):
        """Test job status retrieval for non-existent job."""
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_job.return_value = None
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            response = client.get("/api/jobs/non-existent-job/status")
        
        assert response.status_code == 404
    
    @patch('api.services.supabase_service.SupabaseService')
    def test_cancel_job_success(self, mock_supabase, client):
        """Test successful job cancellation."""
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_job.return_value = {
            "id": "test-job-123",
            "status": "processing"
        }
        mock_supabase_instance.update_job_status.return_value = True
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            response = client.post("/api/jobs/test-job-123/cancel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cancelled" in data["message"].lower()

class TestURLProcessingEndpoints:
    """Test URL processing endpoints."""
    
    @patch('api.tasks.process_url_task')
    @patch('api.services.supabase_service.SupabaseService')
    def test_process_url_success(self, mock_supabase, mock_task, client):
        """Test successful URL processing."""
        mock_supabase_instance = Mock()
        mock_supabase_instance.create_job.return_value = "test-job-123"
        mock_supabase.return_value = mock_supabase_instance
        
        mock_result = Mock()
        mock_result.id = "test-task-123"
        mock_task.delay.return_value = mock_result
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            response = client.post(
                "/api/process-url",
                json={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "user_id": "test-user-123"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "processing"
    
    def test_process_url_invalid_url(self, client):
        """Test URL processing with invalid URL."""
        response = client.post(
            "/api/process-url",
            json={
                "url": "not-a-valid-url",
                "user_id": "test-user-123"
            }
        )
        
        assert response.status_code in [400, 422]
    
    def test_process_url_missing_user_id(self, client):
        """Test URL processing without user ID."""
        response = client.post(
            "/api/process-url",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            }
        )
        
        assert response.status_code == 422

class TestWebSocketEndpoints:
    """Test WebSocket endpoints."""
    
    def test_websocket_connection(self, client):
        """Test WebSocket connection establishment."""
        with client.websocket_connect("/ws/test-client-123") as websocket:
            # Connection should be established successfully
            assert websocket is not None
    
    def test_websocket_job_subscription(self, client):
        """Test WebSocket job subscription."""
        with client.websocket_connect("/ws/test-client-123") as websocket:
            # Send subscription message
            websocket.send_json({
                "action": "subscribe",
                "job_id": "test-job-123"
            })
            
            # Should receive confirmation
            response = websocket.receive_json()
            assert response["type"] == "subscription_confirmed"

class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_404_endpoint(self, client):
        """Test non-existent endpoint returns 404."""
        response = client.get("/api/non-existent-endpoint")
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test wrong HTTP method returns 405."""
        response = client.delete("/api/health")
        assert response.status_code == 405
    
    @patch('api.services.supabase_service.supabase_service')
    def test_internal_server_error_handling(self, mock_supabase, client):
        """Test internal server error handling."""
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_job.side_effect = Exception("Database connection failed")
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            response = client.get("/api/jobs/test-job-123/status")
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data or "detail" in data

class TestRequestValidation:
    """Test request validation and sanitization."""
    
    def test_request_size_limit(self, client):
        """Test request size limits are enforced."""
        large_data = "x" * (10 * 1024 * 1024)  # 10MB of data
        
        response = client.post(
            "/api/process-url",
            json={"url": "https://example.com", "data": large_data}
        )
        
        # Should reject large requests
        assert response.status_code in [413, 422]
    
    def test_malicious_input_sanitization(self, client, malicious_payloads):
        """Test that malicious inputs are properly sanitized."""
        for payload in malicious_payloads:
            response = client.post(
                "/api/process-url",
                json={
                    "url": f"https://example.com?q={payload}",
                    "user_id": payload
                }
            )
            
            # Should either reject or sanitize the input
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                # If accepted, ensure payload is sanitized in response
                data = response.json()
                response_text = json.dumps(data)
                assert "<script>" not in response_text
                assert "DROP TABLE" not in response_text