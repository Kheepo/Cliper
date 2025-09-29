import pytest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app

class TestVideoProcessingWorkflow:
    """Test complete video processing workflow integration."""
    
    @patch('api.tasks.process_video_task')
    @patch('api.services.supabase_service.supabase_service')
    @patch('api.services.video_processor.VideoProcessor')
    def test_complete_video_upload_and_processing_workflow(self, 
                                                          mock_video_processor,
                                                          mock_supabase, 
                                                          mock_task, 
                                                          client, 
                                                          valid_video_file):
        """Test the complete video upload and processing workflow."""
        # Setup mocks
        job_id = "test-job-123"
        task_id = "test-task-456"
        
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.create_job.return_value = job_id
        mock_supabase_instance.get_job.return_value = {
            "id": job_id,
            "status": "processing",
            "progress": 0,
            "current_step": "uploading",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        mock_supabase_instance.update_job_status.return_value = True
        mock_supabase.return_value = mock_supabase_instance
        
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = task_id
        mock_task.delay.return_value = mock_result
        
        # Mock video processor
        mock_processor_instance = Mock()
        mock_processor_instance.process_video.return_value = {
            "clips": [
                {
                    "start_time": 10.5,
                    "end_time": 25.3,
                    "score": 0.95,
                    "transcript": "This is a viral moment!",
                    "file_path": "/tmp/clip_1.mp4"
                }
            ],
            "metadata": {
                "duration": 120.0,
                "resolution": "1920x1080",
                "fps": 30
            }
        }
        mock_video_processor.return_value = mock_processor_instance
        
        filename, content, content_type = valid_video_file
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Upload video
            upload_response = client.post(
                "/api/videos/upload",
                files={"file": (filename, content, content_type)},
                data={"user_id": "test-user-123"}
            )
            
            assert upload_response.status_code == 200
            upload_data = upload_response.json()
            assert upload_data["job_id"] == job_id
            assert upload_data["status"] == "processing"
            
            # Step 2: Check initial job status
            status_response = client.get(f"/api/jobs/{job_id}/status")
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["job_id"] == job_id
            assert status_data["status"] == "processing"
            
            # Step 3: Simulate job progress updates
            progress_updates = [
                {"status": "processing", "progress": 25, "current_step": "extracting_audio"},
                {"status": "processing", "progress": 50, "current_step": "transcribing"},
                {"status": "processing", "progress": 75, "current_step": "analyzing_content"},
                {"status": "completed", "progress": 100, "current_step": "finished"}
            ]
            
            for update in progress_updates:
                mock_supabase_instance.get_job.return_value.update(update)
                
                status_response = client.get(f"/api/jobs/{job_id}/status")
                assert status_response.status_code == 200
                status_data = status_response.json()
                assert status_data["progress"] == update["progress"]
                assert status_data["current_step"] == update["current_step"]
            
            # Verify task was called with correct parameters
            mock_task.delay.assert_called_once()
            call_args = mock_task.delay.call_args[0]
            assert job_id in call_args
            assert "test-user-123" in call_args
    
    @patch('api.tasks.process_url_task')
    @patch('api.services.supabase_service.supabase_service')
    def test_url_processing_workflow(self, mock_supabase, mock_task, client):
        """Test URL processing workflow."""
        job_id = "url-job-123"
        
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.create_job.return_value = job_id
        mock_supabase_instance.get_job.return_value = {
            "id": job_id,
            "status": "processing",
            "progress": 0,
            "current_step": "downloading",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = "url-task-456"
        mock_task.delay.return_value = mock_result
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Submit URL for processing
            url_response = client.post(
                "/api/process-url",
                json={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "user_id": "test-user-123"
                }
            )
            
            assert url_response.status_code == 200
            url_data = url_response.json()
            assert url_data["job_id"] == job_id
            assert url_data["status"] == "processing"
            
            # Step 2: Check job status
            status_response = client.get(f"/api/jobs/{job_id}/status")
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["current_step"] == "downloading"
            
            # Verify task was called
            mock_task.delay.assert_called_once()
    
    @patch('api.services.supabase_service.supabase_service')
    def test_job_cancellation_workflow(self, mock_supabase, client):
        """Test job cancellation workflow."""
        job_id = "cancel-job-123"
        
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_job.return_value = {
            "id": job_id,
            "status": "processing",
            "progress": 30,
            "current_step": "transcribing"
        }
        mock_supabase_instance.update_job_status.return_value = True
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Check job exists and is processing
            status_response = client.get(f"/api/jobs/{job_id}/status")
            assert status_response.status_code == 200
            assert status_response.json()["status"] == "processing"
            
            # Step 2: Cancel the job
            cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
            assert cancel_response.status_code == 200
            cancel_data = cancel_response.json()
            assert cancel_data["success"] is True
            
            # Step 3: Verify job status updated
            mock_supabase_instance.update_job_status.assert_called_with(
                job_id, "cancelled"
            )

class TestWebSocketIntegration:
    """Test WebSocket integration for real-time updates."""
    
    def test_websocket_job_updates(self, client):
        """Test WebSocket job update notifications."""
        client_id = "test-client-123"
        job_id = "ws-job-456"
        
        with client.websocket_connect(f"/ws/{client_id}") as websocket:
            # Subscribe to job updates
            websocket.send_json({
                "action": "subscribe",
                "job_id": job_id
            })
            
            # Should receive subscription confirmation
            response = websocket.receive_json()
            assert response["type"] == "subscription_confirmed"
            assert response["job_id"] == job_id
            
            # Simulate job update (this would normally come from Celery task)
            update_message = {
                "type": "job_update",
                "job_id": job_id,
                "status": "processing",
                "progress": 50,
                "current_step": "analyzing_content"
            }
            
            # In a real scenario, this would be sent by the background task
            # For testing, we'll simulate receiving it
            websocket.send_json(update_message)
            
            # Client should receive the update
            received = websocket.receive_json()
            assert received["type"] == "job_update"
            assert received["job_id"] == job_id
            assert received["progress"] == 50
    
    def test_websocket_multiple_clients(self, client):
        """Test WebSocket with multiple clients."""
        client1_id = "client-1"
        client2_id = "client-2"
        job_id = "shared-job-789"
        
        with client.websocket_connect(f"/ws/{client1_id}") as ws1, \
             client.websocket_connect(f"/ws/{client2_id}") as ws2:
            
            # Both clients subscribe to the same job
            for ws in [ws1, ws2]:
                ws.send_json({
                    "action": "subscribe",
                    "job_id": job_id
                })
                
                response = ws.receive_json()
                assert response["type"] == "subscription_confirmed"
            
            # Send update to one client
            update = {
                "type": "job_update",
                "job_id": job_id,
                "status": "completed",
                "progress": 100
            }
            
            ws1.send_json(update)
            
            # Both clients should receive the update
            for ws in [ws1, ws2]:
                received = ws.receive_json()
                assert received["type"] == "job_update"
                assert received["status"] == "completed"

class TestErrorRecoveryWorkflow:
    """Test error handling and recovery workflows."""
    
    @patch('api.services.supabase_service.SupabaseService')
    def test_database_failure_recovery(self, mock_supabase, client):
        """Test recovery from database failures."""
        # Mock Supabase to fail initially, then recover
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_job.side_effect = [
            Exception("Database connection failed"),  # First call fails
            {"id": "recovery-job", "status": "processing"}  # Second call succeeds
        ]
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # First request should fail
            response1 = client.get("/api/jobs/recovery-job/status")
            assert response1.status_code == 500
            
            # Second request should succeed (simulating recovery)
            response2 = client.get("/api/jobs/recovery-job/status")
            assert response2.status_code == 200
    
    @patch('api.tasks.process_video_task')
    @patch('api.services.supabase_service.SupabaseService')
    def test_task_failure_handling(self, mock_supabase, mock_task, client, valid_video_file):
        """Test handling of background task failures."""
        job_id = "failing-job-123"
        
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.create_job.return_value = job_id
        mock_supabase_instance.get_job.return_value = {
            "id": job_id,
            "status": "failed",
            "error": "Video processing failed: Unsupported format",
            "progress": 25
        }
        mock_supabase.return_value = mock_supabase_instance
        
        # Mock task to fail
        mock_task.delay.side_effect = Exception("Celery worker unavailable")
        
        filename, content, content_type = valid_video_file
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Upload should handle task failure gracefully
            response = client.post(
                "/api/videos/upload",
                files={"file": (filename, content, content_type)},
                data={"user_id": "test-user-123"}
            )
            
            # Should return error status but not crash
            assert response.status_code in [500, 503]  # Server error or service unavailable
            
            # Job status should reflect the failure
            status_response = client.get(f"/api/jobs/{job_id}/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                assert status_data["status"] == "failed"
                assert "error" in status_data

class TestPerformanceWorkflow:
    """Test performance-related workflows."""
    
    def test_concurrent_uploads(self, client, valid_video_file):
        """Test handling of concurrent video uploads."""
        import threading
        import queue
        
        filename, content, content_type = valid_video_file
        results = queue.Queue()
        
        def upload_video(user_id):
            """Upload video in separate thread."""
            try:
                response = client.post(
                    "/api/videos/upload",
                    files={"file": (f"video_{user_id}.mp4", content, content_type)},
                    data={"user_id": f"user-{user_id}"}
                )
                results.put((user_id, response.status_code, response.json()))
            except Exception as e:
                results.put((user_id, 500, {"error": str(e)}))
        
        # Start multiple concurrent uploads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=upload_video, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all uploads to complete
        for thread in threads:
            thread.join(timeout=30)  # 30 second timeout
        
        # Collect results
        upload_results = []
        while not results.empty():
            upload_results.append(results.get())
        
        assert len(upload_results) == 5
        
        # At least some uploads should succeed
        successful_uploads = [r for r in upload_results if r[1] == 200]
        assert len(successful_uploads) > 0
    
    def test_large_file_handling(self, client, large_video_file):
        """Test handling of large file uploads."""
        filename, content, content_type = large_video_file
        
        # This should be rejected due to size limits
        response = client.post(
            "/api/videos/upload",
            files={"file": (filename, content, content_type)},
            data={"user_id": "test-user-123"}
        )
        
        # Should reject large files
        assert response.status_code in [413, 422]
    
    def test_system_metrics_under_load(self, client):
        """Test system metrics endpoint under load."""
        import threading
        
        results = []
        
        def get_metrics():
            """Get system metrics in separate thread."""
            response = client.get("/api/performance/system")
            results.append(response.status_code)
        
        # Make concurrent requests to metrics endpoint
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_metrics)
            threads.append(thread)
            thread.start()
        
        # Wait for all requests to complete
        for thread in threads:
            thread.join(timeout=10)
        
        # All requests should succeed
        assert len(results) == 10
        assert all(status == 200 for status in results)

class TestSecurityWorkflow:
    """Test security-related workflows."""
    
    def test_rate_limiting_workflow(self, client):
        """Test rate limiting across multiple requests."""
        # Make requests rapidly to trigger rate limiting
        responses = []
        for i in range(20):
            response = client.get("/api/health")
            responses.append(response.status_code)
            time.sleep(0.1)  # Small delay between requests
        
        # Some requests should be rate limited
        rate_limited = [status for status in responses if status == 429]
        successful = [status for status in responses if status == 200]
        
        # Should have both successful and rate-limited requests
        assert len(successful) > 0
        assert len(rate_limited) > 0
    
    def test_input_sanitization_workflow(self, client):
        """Test input sanitization across different endpoints."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "javascript:alert('xss')"
        ]
        
        for malicious_input in malicious_inputs:
            # Test URL processing endpoint
            response = client.post(
                "/api/process-url",
                json={
                    "url": f"https://example.com?q={malicious_input}",
                    "user_id": malicious_input
                }
            )
            
            # Should either reject or sanitize
            if response.status_code == 200:
                # If accepted, ensure response is sanitized
                response_text = response.text.lower()
                assert "<script>" not in response_text
                assert "drop table" not in response_text
                assert "javascript:" not in response_text
            else:
                # Should be rejected with appropriate error code
                assert response.status_code in [400, 422]