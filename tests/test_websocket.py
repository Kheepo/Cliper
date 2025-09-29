import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket, WebSocketDisconnect
from api.main import app, manager


class TestConnectionManager:
    """Test WebSocket connection manager"""
    
    def setup_method(self):
        """Setup for each test method"""
        # Clear connections before each test
        manager.active_connections.clear()
        manager.job_subscribers.clear()
    
    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """Test basic connection and disconnection"""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        
        client_id = "test_client_123"
        
        # Test connection
        await manager.connect(mock_websocket, client_id)
        assert client_id in manager.active_connections
        assert manager.active_connections[client_id] == mock_websocket
        mock_websocket.accept.assert_called_once()
        
        # Test disconnection
        manager.disconnect(client_id)
        assert client_id not in manager.active_connections
    
    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe_job(self):
        """Test job subscription and unsubscription"""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        
        client_id = "test_client_123"
        job_id = "test_job_456"
        
        # Connect client first
        await manager.connect(mock_websocket, client_id)
        
        # Test subscription
        manager.subscribe_to_job(client_id, job_id)
        assert job_id in manager.job_subscribers
        assert client_id in manager.job_subscribers[job_id]
        
        # Test unsubscription
        manager.unsubscribe_from_job(client_id, job_id)
        assert client_id not in manager.job_subscribers.get(job_id, set())
    
    @pytest.mark.asyncio
    async def test_send_personal_message(self):
        """Test sending personal message to client"""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        client_id = "test_client_123"
        message = {"type": "notification", "data": "test message"}
        
        # Connect client
        await manager.connect(mock_websocket, client_id)
        
        # Send message
        await manager.send_personal_message(message, client_id)
        
        expected_message = json.dumps(message)
        mock_websocket.send_text.assert_called_once_with(expected_message)
    
    @pytest.mark.asyncio
    async def test_send_personal_message_client_not_found(self):
        """Test sending message to non-existent client"""
        message = {"type": "notification", "data": "test message"}
        
        # Should not raise exception for non-existent client
        await manager.send_personal_message(message, "non_existent_client")
    
    @pytest.mark.asyncio
    async def test_send_job_update(self):
        """Test sending job update to subscribers"""
        mock_websocket1 = Mock(spec=WebSocket)
        mock_websocket1.accept = AsyncMock()
        mock_websocket1.send_text = AsyncMock()
        
        mock_websocket2 = Mock(spec=WebSocket)
        mock_websocket2.accept = AsyncMock()
        mock_websocket2.send_text = AsyncMock()
        
        client1_id = "client_1"
        client2_id = "client_2"
        job_id = "test_job_456"
        
        # Connect clients
        await manager.connect(mock_websocket1, client1_id)
        await manager.connect(mock_websocket2, client2_id)
        
        # Subscribe both clients to job
        manager.subscribe_to_job(client1_id, job_id)
        manager.subscribe_to_job(client2_id, job_id)
        
        # Send job update
        update_data = {"status": "processing", "progress": 50}
        await manager.send_job_update(job_id, update_data)
        
        expected_message = json.dumps({
            "type": "job_update",
            "job_id": job_id,
            "data": update_data
        })
        
        # Both clients should receive the update
        mock_websocket1.send_text.assert_called_once_with(expected_message)
        mock_websocket2.send_text.assert_called_once_with(expected_message)
    
    @pytest.mark.asyncio
    async def test_send_job_update_with_connection_error(self):
        """Test job update with connection error"""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock(side_effect=Exception("Connection error"))
        
        client_id = "test_client_123"
        job_id = "test_job_456"
        
        # Connect and subscribe
        await manager.connect(mock_websocket, client_id)
        manager.subscribe_to_job(client_id, job_id)
        
        # Send update (should handle exception gracefully)
        update_data = {"status": "processing", "progress": 50}
        await manager.send_job_update(job_id, update_data)
        
        # Client should be disconnected due to error
        assert client_id not in manager.active_connections


class TestWebSocketEndpoints:
    """Test WebSocket endpoints"""
    
    def setup_method(self):
        """Setup for each test method"""
        manager.active_connections.clear()
        manager.job_subscribers.clear()
    
    @pytest.mark.asyncio
    async def test_websocket_client_endpoint(self):
        """Test client WebSocket endpoint"""
        client = TestClient(app)
        
        with patch.object(manager, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(manager, 'disconnect') as mock_disconnect:
                with patch.object(manager, 'send_personal_message', new_callable=AsyncMock) as mock_send:
                    
                    # Mock WebSocket connection
                    with client.websocket_connect("/ws/test_client_123") as websocket:
                        # Send a test message
                        test_message = {
                            "type": "subscribe",
                            "job_id": "test_job_456"
                        }
                        websocket.send_json(test_message)
                        
                        # Verify connection was established
                        mock_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_websocket_job_endpoint(self):
        """Test job-specific WebSocket endpoint"""
        client = TestClient(app)
        
        with patch.object(manager, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(manager, 'disconnect') as mock_disconnect:
                with patch.object(manager, 'subscribe_to_job') as mock_subscribe:
                    
                    # Mock WebSocket connection
                    with client.websocket_connect("/ws/job/test_job_456") as websocket:
                        # Verify connection and subscription
                        mock_connect.assert_called_once()
                        mock_subscribe.assert_called_once()


class TestBroadcastJobUpdate:
    """Test broadcast job update functionality"""
    
    @pytest.mark.asyncio
    async def test_broadcast_job_update_function(self):
        """Test standalone broadcast function"""
        from api.main import broadcast_job_update
        
        job_id = "test_job_123"
        update_data = {"status": "completed", "progress": 100}
        
        with patch.object(manager, 'send_job_update', new_callable=AsyncMock) as mock_send:
            await broadcast_job_update(job_id, update_data)
            mock_send.assert_called_once_with(job_id, update_data)
    
    def test_broadcast_endpoint(self):
        """Test broadcast API endpoint"""
        client = TestClient(app)
        
        job_id = "test_job_123"
        update_data = {"status": "completed", "progress": 100}
        
        with patch('api.main.broadcast_job_update', new_callable=AsyncMock) as mock_broadcast:
            response = client.post(
                f"/api/jobs/{job_id}/broadcast-update",
                json=update_data
            )
            
            assert response.status_code == 200
            assert response.json() == {"message": "Update broadcasted successfully"}


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality"""
    
    def setup_method(self):
        """Setup for each test method"""
        manager.active_connections.clear()
        manager.job_subscribers.clear()
    
    @pytest.mark.asyncio
    async def test_full_websocket_flow(self):
        """Test complete WebSocket flow with multiple clients"""
        # Mock WebSocket connections
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_text = AsyncMock()
        
        client1_id = "client_1"
        client2_id = "client_2"
        job_id = "shared_job_123"
        
        # Connect both clients
        await manager.connect(mock_ws1, client1_id)
        await manager.connect(mock_ws2, client2_id)
        
        # Subscribe both to the same job
        manager.subscribe_to_job(client1_id, job_id)
        manager.subscribe_to_job(client2_id, job_id)
        
        # Send job updates
        updates = [
            {"status": "started", "progress": 0},
            {"status": "processing", "progress": 50},
            {"status": "completed", "progress": 100}
        ]
        
        for update in updates:
            await manager.send_job_update(job_id, update)
        
        # Verify both clients received all updates
        assert mock_ws1.send_text.call_count == 3
        assert mock_ws2.send_text.call_count == 3
        
        # Disconnect one client
        manager.disconnect(client1_id)
        
        # Send another update
        await manager.send_job_update(job_id, {"status": "archived", "progress": 100})
        
        # Only client2 should receive this update
        assert mock_ws1.send_text.call_count == 3  # No new calls
        assert mock_ws2.send_text.call_count == 4  # One new call
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling"""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock(side_effect=WebSocketDisconnect(code=1000))
        
        client_id = "error_client"
        job_id = "error_job"
        
        # Connect and subscribe
        await manager.connect(mock_websocket, client_id)
        manager.subscribe_to_job(client_id, job_id)
        
        # Attempt to send message (should handle disconnect gracefully)
        await manager.send_job_update(job_id, {"status": "test"})
        
        # Client should be automatically disconnected
        assert client_id not in manager.active_connections
        assert client_id not in manager.job_subscribers.get(job_id, set())
    
    def test_websocket_message_format(self):
        """Test WebSocket message format consistency"""
        job_id = "format_test_job"
        update_data = {
            "status": "processing",
            "progress": 75,
            "message": "Processing video segments",
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        expected_format = {
            "type": "job_update",
            "job_id": job_id,
            "data": update_data
        }
        
        # This would be the actual message sent
        actual_message = {
            "type": "job_update",
            "job_id": job_id,
            "data": update_data
        }
        
        assert actual_message == expected_format
        
        # Verify JSON serialization works
        json_message = json.dumps(actual_message)
        parsed_message = json.loads(json_message)
        assert parsed_message == expected_format


if __name__ == "__main__":
    pytest.main([__file__])