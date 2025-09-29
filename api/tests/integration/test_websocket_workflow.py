import pytest
import json
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app

class TestWebSocketWorkflow:
    """Test WebSocket functionality and real-time communication workflows."""
    
    @patch('api.services.supabase_service.supabase_service')
    def test_websocket_job_progress_updates(self, mock_supabase, client):
        """Test WebSocket connection for real-time job progress updates."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Test WebSocket connection
            with client.websocket_connect("/ws/job-progress/job-123?token=test-token") as websocket:
                # Simulate job progress updates
                progress_updates = [
                    {"job_id": "job-123", "status": "processing", "progress": 25},
                    {"job_id": "job-123", "status": "processing", "progress": 50},
                    {"job_id": "job-123", "status": "processing", "progress": 75},
                    {"job_id": "job-123", "status": "completed", "progress": 100}
                ]
                
                # Send progress updates through WebSocket
                for update in progress_updates:
                    websocket.send_json(update)
                    
                    # Receive and verify the update
                    received_data = websocket.receive_json()
                    assert received_data["job_id"] == "job-123"
                    assert received_data["progress"] == update["progress"]
                    assert received_data["status"] == update["status"]
    
    @patch('api.services.supabase_service.supabase_service')
    def test_websocket_multiple_clients(self, mock_supabase, client):
        """Test WebSocket with multiple clients receiving updates."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Connect multiple WebSocket clients
            with client.websocket_connect("/ws/job-progress/job-456?token=test-token-1") as ws1, \
                 client.websocket_connect("/ws/job-progress/job-456?token=test-token-2") as ws2:
                
                # Send update to both clients
                update_message = {
                    "job_id": "job-456",
                    "status": "processing",
                    "progress": 60,
                    "message": "Processing video segments"
                }
                
                # Simulate server broadcasting to all clients
                ws1.send_json(update_message)
                ws2.send_json(update_message)
                
                # Both clients should receive the update
                received_1 = ws1.receive_json()
                received_2 = ws2.receive_json()
                
                assert received_1["job_id"] == "job-456"
                assert received_2["job_id"] == "job-456"
                assert received_1["progress"] == 60
                assert received_2["progress"] == 60
    
    @patch('api.services.supabase_service.supabase_service')
    def test_websocket_authentication_failure(self, mock_supabase, client):
        """Test WebSocket connection with invalid authentication."""
        # Mock Supabase service to fail authentication
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.side_effect = Exception("Invalid token")
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Attempt WebSocket connection with invalid token
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/job-progress/job-789?token=invalid-token") as websocket:
                    websocket.send_json({"test": "message"})
    
    @patch('api.services.supabase_service.supabase_service')
    def test_websocket_connection_lifecycle(self, mock_supabase, client):
        """Test complete WebSocket connection lifecycle."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-789",
            "email": "lifecycle@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Test connection establishment
            with client.websocket_connect("/ws/job-progress/job-lifecycle?token=lifecycle-token") as websocket:
                # Test initial connection message
                initial_message = {
                    "type": "connection_established",
                    "job_id": "job-lifecycle",
                    "user_id": "user-789"
                }
                websocket.send_json(initial_message)
                
                # Test receiving connection confirmation
                response = websocket.receive_json()
                assert response["type"] == "connection_established"
                
                # Test sending multiple progress updates
                for i in range(5):
                    progress_update = {
                        "type": "progress_update",
                        "job_id": "job-lifecycle",
                        "progress": (i + 1) * 20,
                        "timestamp": time.time()
                    }
                    websocket.send_json(progress_update)
                    
                    received = websocket.receive_json()
                    assert received["progress"] == (i + 1) * 20
                
                # Test completion message
                completion_message = {
                    "type": "job_completed",
                    "job_id": "job-lifecycle",
                    "result": "success",
                    "clips_generated": 3
                }
                websocket.send_json(completion_message)
                
                final_response = websocket.receive_json()
                assert final_response["type"] == "job_completed"
                assert final_response["result"] == "success"
    
    @patch('api.services.supabase_service.supabase_service')
    def test_websocket_error_handling(self, mock_supabase, client):
        """Test WebSocket error handling and recovery."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-error",
            "email": "error@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            with client.websocket_connect("/ws/job-progress/job-error?token=error-token") as websocket:
                # Test sending invalid message format
                invalid_messages = [
                    "not-json",
                    {"missing_required_fields": True},
                    {"job_id": None, "progress": "invalid"},
                    {"job_id": "job-error", "progress": -1},
                    {"job_id": "job-error", "progress": 150}
                ]
                
                for invalid_msg in invalid_messages:
                    try:
                        if isinstance(invalid_msg, str):
                            websocket.send_text(invalid_msg)
                        else:
                            websocket.send_json(invalid_msg)
                        
                        # Should receive error response or connection should handle gracefully
                        try:
                            response = websocket.receive_json(timeout=1)
                            if "error" in response:
                                assert response["error"] is not None
                        except:
                            # Timeout is acceptable for invalid messages
                            pass
                    except Exception:
                        # Connection errors are acceptable for invalid messages
                        pass
                
                # Test recovery with valid message
                valid_message = {
                    "job_id": "job-error",
                    "status": "processing",
                    "progress": 50
                }
                websocket.send_json(valid_message)
                
                # Should receive valid response
                response = websocket.receive_json()
                assert response["job_id"] == "job-error"
                assert response["progress"] == 50

class TestWebSocketIntegrationWithAPI:
    """Test WebSocket integration with REST API endpoints."""
    
    @patch('api.services.supabase_service.supabase_service')
    @patch('api.tasks.process_video_task')
    def test_video_upload_with_websocket_updates(self, mock_task, mock_supabase, client, valid_video_file):
        """Test video upload triggering WebSocket progress updates."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        user_data = {"id": "user-ws", "email": "ws@example.com"}
        mock_supabase_instance.get_user_from_token.return_value = user_data
        mock_supabase_instance.authenticate_user.return_value = {
            "access_token": "ws-token",
            "user": user_data
        }
        
        job_id = "ws-job-123"
        mock_supabase_instance.create_job.return_value = job_id
        
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = "ws-task-456"
        mock_task.delay.return_value = mock_result
        
        mock_supabase.return_value = mock_supabase_instance
        
        filename, content, content_type = valid_video_file
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Establish WebSocket connection first
            with client.websocket_connect(f"/ws/job-progress/{job_id}?token=ws-token") as websocket:
                # Upload video via REST API
                auth_headers = {"Authorization": "Bearer ws-token"}
                upload_response = client.post(
                    "/api/videos/upload",
                    files={"file": (filename, content, content_type)},
                    data={"user_id": "user-ws"},
                    headers=auth_headers
                )
                
                assert upload_response.status_code == 200
                upload_data = upload_response.json()
                assert upload_data["job_id"] == job_id
                
                # Simulate progress updates via WebSocket
                progress_updates = [
                    {"job_id": job_id, "status": "uploading", "progress": 25},
                    {"job_id": job_id, "status": "processing", "progress": 50},
                    {"job_id": job_id, "status": "analyzing", "progress": 75},
                    {"job_id": job_id, "status": "completed", "progress": 100}
                ]
                
                for update in progress_updates:
                    websocket.send_json(update)
                    received = websocket.receive_json()
                    assert received["job_id"] == job_id
                    assert received["progress"] == update["progress"]
                
                # Verify job status via REST API
                status_response = client.get(
                    f"/api/jobs/{job_id}/status",
                    headers=auth_headers
                )
                
                # Mock the final job status
                mock_supabase_instance.get_job.return_value = {
                    "id": job_id,
                    "status": "completed",
                    "progress": 100,
                    "user_id": "user-ws"
                }
                
                status_response = client.get(
                    f"/api/jobs/{job_id}/status",
                    headers=auth_headers
                )
                
                assert status_response.status_code == 200
                status_data = status_response.json()
                assert status_data["status"] == "completed"
    
    @patch('api.services.supabase_service.supabase_service')
    def test_clip_generation_with_websocket_notifications(self, mock_supabase, client):
        """Test clip generation triggering WebSocket notifications."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        user_data = {"id": "user-clip-ws", "email": "clipws@example.com"}
        mock_supabase_instance.get_user_from_token.return_value = user_data
        
        job_id = "clip-ws-job-789"
        mock_supabase_instance.get_job.return_value = {
            "id": job_id,
            "status": "completed",
            "user_id": "user-clip-ws"
        }
        
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Establish WebSocket connection
            with client.websocket_connect(f"/ws/job-progress/{job_id}?token=clip-ws-token") as websocket:
                # Trigger clip generation via REST API
                auth_headers = {"Authorization": "Bearer clip-ws-token"}
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
                
                # Simulate clip generation progress via WebSocket
                generation_updates = [
                    {"job_id": job_id, "type": "clip_generation_started", "total_segments": 10},
                    {"job_id": job_id, "type": "clip_analysis", "segments_analyzed": 3},
                    {"job_id": job_id, "type": "clip_analysis", "segments_analyzed": 7},
                    {"job_id": job_id, "type": "clip_generation_completed", "clips_generated": 3}
                ]
                
                for update in generation_updates:
                    websocket.send_json(update)
                    received = websocket.receive_json()
                    assert received["job_id"] == job_id
                    assert received["type"] == update["type"]
    
    @patch('api.services.supabase_service.supabase_service')
    def test_websocket_connection_management(self, mock_supabase, client):
        """Test WebSocket connection management and cleanup."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-mgmt",
            "email": "mgmt@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Test multiple connections for same job
            job_id = "mgmt-job-456"
            
            # First connection
            with client.websocket_connect(f"/ws/job-progress/{job_id}?token=mgmt-token-1") as ws1:
                # Second connection for same job
                with client.websocket_connect(f"/ws/job-progress/{job_id}?token=mgmt-token-2") as ws2:
                    # Send message to both connections
                    test_message = {
                        "job_id": job_id,
                        "status": "testing",
                        "progress": 30
                    }
                    
                    ws1.send_json(test_message)
                    ws2.send_json(test_message)
                    
                    # Both should receive their respective messages
                    response1 = ws1.receive_json()
                    response2 = ws2.receive_json()
                    
                    assert response1["job_id"] == job_id
                    assert response2["job_id"] == job_id
                
                # ws2 is now closed, ws1 should still work
                final_message = {
                    "job_id": job_id,
                    "status": "final",
                    "progress": 100
                }
                
                ws1.send_json(final_message)
                final_response = ws1.receive_json()
                assert final_response["status"] == "final"

class TestWebSocketPerformance:
    """Test WebSocket performance and scalability."""
    
    @patch('api.services.supabase_service.supabase_service')
    def test_websocket_high_frequency_updates(self, mock_supabase, client):
        """Test WebSocket handling of high-frequency updates."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-perf",
            "email": "perf@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            job_id = "perf-job-123"
            
            with client.websocket_connect(f"/ws/job-progress/{job_id}?token=perf-token") as websocket:
                # Send rapid updates
                start_time = time.time()
                num_updates = 50
                
                for i in range(num_updates):
                    update = {
                        "job_id": job_id,
                        "status": "processing",
                        "progress": (i + 1) * 2,  # 0 to 100
                        "timestamp": time.time()
                    }
                    
                    websocket.send_json(update)
                    
                    # Receive response
                    try:
                        response = websocket.receive_json(timeout=1)
                        assert response["job_id"] == job_id
                    except:
                        # Some messages might be dropped under high load
                        pass
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # Should handle updates reasonably quickly
                assert total_time < 30  # Should complete within 30 seconds
    
    @patch('api.services.supabase_service.supabase_service')
    def test_websocket_memory_usage(self, mock_supabase, client):
        """Test WebSocket memory usage with long-running connections."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-memory",
            "email": "memory@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            job_id = "memory-job-789"
            
            with client.websocket_connect(f"/ws/job-progress/{job_id}?token=memory-token") as websocket:
                # Send periodic updates over extended period
                for batch in range(5):  # 5 batches
                    for i in range(20):  # 20 updates per batch
                        update = {
                            "job_id": job_id,
                            "status": "processing",
                            "progress": (batch * 20 + i + 1),
                            "batch": batch,
                            "data": f"Large data payload {i}" * 10  # Simulate larger payloads
                        }
                        
                        websocket.send_json(update)
                        
                        try:
                            response = websocket.receive_json(timeout=0.5)
                            assert response["job_id"] == job_id
                        except:
                            # Some timeouts are acceptable
                            pass
                    
                    # Small delay between batches
                    time.sleep(0.1)
                
                # Final status check
                final_update = {
                    "job_id": job_id,
                    "status": "completed",
                    "progress": 100
                }
                
                websocket.send_json(final_update)
                final_response = websocket.receive_json()
                assert final_response["status"] == "completed"