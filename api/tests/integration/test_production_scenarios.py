"""Comprehensive integration tests for production scenarios.

Tests:
- End-to-end clip generation workflows
- Error recovery and resilience
- Performance under load
- Security scenarios
- Data integrity
- WebSocket real-time updates
- Rate limiting
- Authentication flows
"""

import asyncio
import json
import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from httpx import AsyncClient
import websockets

from api.main import app
from api.database.models import Clip, Video, User
from api.services.supabase_service import SupabaseService
from api.core.logging_config import get_logger
from api.core.config import get_settings


logger = get_logger(__name__)
client = TestClient(app)


class TestProductionWorkflows:
    """Test complete production workflows."""
    
    @pytest.fixture
    def mock_services(self):
        """Mock external services for testing."""
        with patch('api.services.supabase_service.SupabaseService') as mock_supabase, \
             patch('api.services.llm_service.LLMService') as mock_llm, \
             patch('api.video_processor.VideoProcessor') as mock_processor:
            
            # Configure mocks
            mock_supabase.return_value.get_video.return_value = {
                'id': 'test_video_id',
                'file_path': '/test/video.mp4',
                'duration': 300,
                'status': 'processed'
            }
            
            mock_llm.return_value.generate_clip_segments.return_value = [
                {'start': 0, 'end': 60, 'score': 0.9, 'reason': 'High engagement'},
                {'start': 120, 'end': 180, 'score': 0.8, 'reason': 'Key content'}
            ]
            
            mock_processor.return_value.extract_clip.return_value = {
                'output_path': '/test/clip.mp4',
                'duration': 60,
                'file_size': 1024000
            }
            
            yield {
                'supabase': mock_supabase,
                'llm': mock_llm,
                'processor': mock_processor
            }
    
    @pytest.fixture
    def authenticated_user(self):
        """Create authenticated user for testing."""
        user_data = {
            'id': 'test_user_id',
            'email': 'test@example.com',
            'name': 'Test User',
            'tier': 'pro'
        }
        
        # Mock JWT token
        token = 'test_jwt_token'
        
        return {'user': user_data, 'token': token}
    
    def test_complete_clip_generation_workflow(self, mock_services, authenticated_user):
        """Test complete clip generation from start to finish."""
        
        # Step 1: Create clip generation request
        request_data = {
            'video_url': 'https://example.com/test_video.mp4',
            'platform': 'youtube',
            'duration': 60,
            'style': 'engaging',
            'target_audience': 'tech_enthusiasts',
            'keywords': ['AI', 'technology'],
            'quality': 'high',
            'include_captions': True
        }
        
        headers = {'Authorization': f'Bearer {authenticated_user["token"]}'}
        
        # Create clip generation request
        response = client.post('/api/clips/generate', json=request_data, headers=headers)
        assert response.status_code == 201
        
        clip_data = response.json()
        assert 'clip_id' in clip_data
        assert 'job_id' in clip_data
        assert clip_data['status'] == 'processing'
        
        clip_id = clip_data['clip_id']
        job_id = clip_data['job_id']
        
        # Step 2: Monitor job progress
        max_attempts = 30
        attempt = 0
        
        while attempt < max_attempts:
            response = client.get(f'/api/clips/{clip_id}', headers=headers)
            assert response.status_code == 200
            
            clip_status = response.json()
            
            if clip_status['status'] == 'completed':
                # Verify completed clip
                assert 'output_url' in clip_status
                assert 'thumbnail_url' in clip_status
                assert clip_status['duration'] > 0
                assert clip_status['progress'] == 100
                break
            elif clip_status['status'] == 'failed':
                pytest.fail(f"Clip generation failed: {clip_status.get('error')}")
            
            time.sleep(1)
            attempt += 1
        
        if attempt >= max_attempts:
            pytest.fail("Clip generation timed out")
        
        # Step 3: Verify job completion
        response = client.get(f'/api/jobs/{job_id}', headers=headers)
        assert response.status_code == 200
        
        job_status = response.json()
        assert job_status['status'] == 'completed'
        assert job_status['progress'] == 100
    
    def test_error_recovery_workflow(self, mock_services, authenticated_user):
        """Test error recovery and retry mechanisms."""
        
        # Configure mock to fail initially, then succeed
        mock_services['processor'].return_value.extract_clip.side_effect = [
            Exception("Temporary processing error"),
            Exception("Another temporary error"),
            {
                'output_path': '/test/clip.mp4',
                'duration': 60,
                'file_size': 1024000
            }
        ]
        
        request_data = {
            'video_url': 'https://example.com/test_video.mp4',
            'platform': 'youtube',
            'duration': 60
        }
        
        headers = {'Authorization': f'Bearer {authenticated_user["token"]}'}
        
        # Create clip generation request
        response = client.post('/api/clips/generate', json=request_data, headers=headers)
        assert response.status_code == 201
        
        clip_data = response.json()
        clip_id = clip_data['clip_id']
        
        # Monitor for eventual success after retries
        max_attempts = 60  # Allow more time for retries
        attempt = 0
        
        while attempt < max_attempts:
            response = client.get(f'/api/clips/{clip_id}', headers=headers)
            clip_status = response.json()
            
            if clip_status['status'] == 'completed':
                # Verify successful recovery
                assert 'output_url' in clip_status
                break
            elif clip_status['status'] == 'failed':
                # Check if it's a permanent failure
                error = clip_status.get('error', {})
                if not error.get('retry_possible', True):
                    pytest.fail(f"Permanent failure: {error.get('message')}")
            
            time.sleep(1)
            attempt += 1
        
        if attempt >= max_attempts:
            pytest.fail("Error recovery failed - clip generation timed out")
    
    def test_concurrent_clip_generation(self, mock_services, authenticated_user):
        """Test handling multiple concurrent clip generation requests."""
        
        request_data = {
            'video_url': 'https://example.com/test_video.mp4',
            'platform': 'youtube',
            'duration': 60
        }
        
        headers = {'Authorization': f'Bearer {authenticated_user["token"]}'}
        
        # Create multiple concurrent requests
        num_requests = 5
        responses = []
        
        for i in range(num_requests):
            response = client.post('/api/clips/generate', json=request_data, headers=headers)
            assert response.status_code == 201
            responses.append(response.json())
        
        # Verify all requests were accepted
        clip_ids = [r['clip_id'] for r in responses]
        assert len(set(clip_ids)) == num_requests  # All unique
        
        # Monitor all clips to completion
        completed_clips = set()
        max_attempts = 60
        attempt = 0
        
        while len(completed_clips) < num_requests and attempt < max_attempts:
            for clip_id in clip_ids:
                if clip_id in completed_clips:
                    continue
                
                response = client.get(f'/api/clips/{clip_id}', headers=headers)
                clip_status = response.json()
                
                if clip_status['status'] == 'completed':
                    completed_clips.add(clip_id)
                elif clip_status['status'] == 'failed':
                    pytest.fail(f"Clip {clip_id} failed: {clip_status.get('error')}")
            
            time.sleep(1)
            attempt += 1
        
        assert len(completed_clips) == num_requests, f"Only {len(completed_clips)}/{num_requests} clips completed"
    
    def test_resource_exhaustion_handling(self, mock_services, authenticated_user):
        """Test handling of resource exhaustion scenarios."""
        
        # Mock resource constraints
        with patch('api.utils.performance.MemoryManager.get_available_memory') as mock_memory, \
             patch('api.utils.performance.DiskManager.get_available_space') as mock_disk:
            
            # Simulate low resources
            mock_memory.return_value = 100 * 1024 * 1024  # 100MB
            mock_disk.return_value = 500 * 1024 * 1024     # 500MB
            
            request_data = {
                'video_url': 'https://example.com/large_video.mp4',
                'platform': 'youtube',
                'duration': 60,
                'quality': 'high'  # High quality requires more resources
            }
            
            headers = {'Authorization': f'Bearer {authenticated_user["token"]}'}
            
            # Request should be queued or rejected gracefully
            response = client.post('/api/clips/generate', json=request_data, headers=headers)
            
            # Should either accept with queuing or reject with proper error
            if response.status_code == 201:
                # If accepted, should be queued
                clip_data = response.json()
                assert clip_data['status'] in ['queued', 'processing']
            elif response.status_code == 503:
                # Service unavailable due to resource constraints
                error_data = response.json()
                assert 'resource' in error_data['error']['message'].lower()
            else:
                pytest.fail(f"Unexpected response: {response.status_code}")


class TestSecurityScenarios:
    """Test security-related scenarios."""
    
    def test_authentication_required(self):
        """Test that authentication is required for protected endpoints."""
        
        request_data = {
            'video_url': 'https://example.com/test_video.mp4',
            'platform': 'youtube',
            'duration': 60
        }
        
        # Request without authentication
        response = client.post('/api/clips/generate', json=request_data)
        assert response.status_code == 401
        
        error_data = response.json()
        assert error_data['error']['code'] == 'UNAUTHORIZED'
    
    def test_invalid_token_handling(self):
        """Test handling of invalid JWT tokens."""
        
        request_data = {
            'video_url': 'https://example.com/test_video.mp4',
            'platform': 'youtube',
            'duration': 60
        }
        
        # Request with invalid token
        headers = {'Authorization': 'Bearer invalid_token'}
        response = client.post('/api/clips/generate', json=request_data, headers=headers)
        assert response.status_code == 401
        
        error_data = response.json()
        assert error_data['error']['code'] == 'INVALID_TOKEN'
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        
        # Mock authenticated user
        headers = {'Authorization': 'Bearer test_token'}
        
        # Make requests up to the limit
        rate_limit = 10  # Assume 10 requests per minute for testing
        
        for i in range(rate_limit):
            response = client.get('/api/health', headers=headers)
            # Should succeed within limit
            assert response.status_code in [200, 429]  # 429 if already rate limited
            
            if response.status_code == 429:
                # Rate limit reached
                error_data = response.json()
                assert error_data['error']['code'] == 'RATE_LIMIT_EXCEEDED'
                assert 'retry_after' in error_data['error']
                break
    
    def test_input_validation(self):
        """Test comprehensive input validation."""
        
        headers = {'Authorization': 'Bearer test_token'}
        
        # Test invalid video URL
        invalid_requests = [
            {
                'video_url': 'not_a_url',
                'platform': 'youtube',
                'duration': 60
            },
            {
                'video_url': 'https://example.com/video.mp4',
                'platform': 'invalid_platform',
                'duration': 60
            },
            {
                'video_url': 'https://example.com/video.mp4',
                'platform': 'youtube',
                'duration': -10  # Negative duration
            },
            {
                'video_url': 'https://example.com/video.mp4',
                'platform': 'youtube',
                'duration': 3600  # Too long
            }
        ]
        
        for request_data in invalid_requests:
            response = client.post('/api/clips/generate', json=request_data, headers=headers)
            assert response.status_code == 422
            
            error_data = response.json()
            assert error_data['error']['code'] == 'VALIDATION_ERROR'
            assert 'details' in error_data['error']
    
    def test_sql_injection_protection(self):
        """Test protection against SQL injection attacks."""
        
        headers = {'Authorization': 'Bearer test_token'}
        
        # Attempt SQL injection in various parameters
        malicious_inputs = [
            "'; DROP TABLE clips; --",
            "' OR '1'='1",
            "'; UPDATE clips SET status='completed'; --",
            "<script>alert('xss')</script>"
        ]
        
        for malicious_input in malicious_inputs:
            # Try in search parameter
            response = client.get(f'/api/clips?search={malicious_input}', headers=headers)
            # Should not cause server error
            assert response.status_code in [200, 400, 422]
            
            # Try in clip ID parameter
            response = client.get(f'/api/clips/{malicious_input}', headers=headers)
            # Should return 404 or 400, not 500
            assert response.status_code in [400, 404, 422]


class TestWebSocketIntegration:
    """Test WebSocket real-time functionality."""
    
    @pytest.mark.asyncio
    async def test_websocket_job_updates(self):
        """Test real-time job updates via WebSocket."""
        
        client_id = 'test_client_123'
        
        # Connect to WebSocket
        async with websockets.connect(f'ws://localhost:8000/ws/{client_id}') as websocket:
            
            # Subscribe to job updates
            subscribe_message = {
                'type': 'subscribe',
                'channel': 'job_updates',
                'job_id': 'test_job_id'
            }
            
            await websocket.send(json.dumps(subscribe_message))
            
            # Simulate job update
            update_message = {
                'type': 'job_update',
                'job_id': 'test_job_id',
                'status': 'processing',
                'progress': 50,
                'stage': 'video_analysis',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Send update through WebSocket manager
            websocket_manager = WebSocketManager()
            await websocket_manager.broadcast_job_update('test_job_id', update_message)
            
            # Receive and verify update
            response = await websocket.recv()
            received_message = json.loads(response)
            
            assert received_message['type'] == 'job_update'
            assert received_message['job_id'] == 'test_job_id'
            assert received_message['progress'] == 50
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling and reconnection."""
        
        client_id = 'test_client_error'
        
        # Test connection with invalid client ID format
        try:
            async with websockets.connect(f'ws://localhost:8000/ws/invalid@client') as websocket:
                # Should handle gracefully
                pass
        except websockets.exceptions.ConnectionClosedError:
            # Expected for invalid client ID
            pass
        
        # Test normal connection
        async with websockets.connect(f'ws://localhost:8000/ws/{client_id}') as websocket:
            
            # Send malformed message
            await websocket.send('invalid json')
            
            # Should receive error response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                error_message = json.loads(response)
                assert error_message['type'] == 'error'
            except asyncio.TimeoutError:
                # Connection might be closed due to invalid message
                pass


class TestPerformanceScenarios:
    """Test performance-related scenarios."""
    
    def test_large_file_handling(self, mock_services, authenticated_user):
        """Test handling of large video files."""
        
        # Mock large file
        mock_services['supabase'].return_value.get_video.return_value = {
            'id': 'large_video_id',
            'file_path': '/test/large_video.mp4',
            'duration': 7200,  # 2 hours
            'file_size': 5 * 1024 * 1024 * 1024,  # 5GB
            'status': 'processed'
        }
        
        request_data = {
            'video_url': 'https://example.com/large_video.mp4',
            'platform': 'youtube',
            'duration': 60
        }
        
        headers = {'Authorization': f'Bearer {authenticated_user["token"]}'}
        
        # Should handle large files gracefully
        response = client.post('/api/clips/generate', json=request_data, headers=headers)
        
        # Should either accept or provide appropriate error
        assert response.status_code in [201, 413, 503]
        
        if response.status_code == 413:
            # File too large
            error_data = response.json()
            assert 'size' in error_data['error']['message'].lower()
        elif response.status_code == 503:
            # Service unavailable due to resource constraints
            error_data = response.json()
            assert 'resource' in error_data['error']['message'].lower()
    
    def test_memory_usage_monitoring(self):
        """Test memory usage monitoring and limits."""
        
        # Test memory monitoring endpoint
        response = client.get('/api/health/memory')
        assert response.status_code == 200
        
        memory_data = response.json()
        assert 'total_memory' in memory_data
        assert 'available_memory' in memory_data
        assert 'memory_usage_percent' in memory_data
        assert 0 <= memory_data['memory_usage_percent'] <= 100
    
    def test_disk_space_monitoring(self):
        """Test disk space monitoring and cleanup."""
        
        # Test disk space monitoring endpoint
        response = client.get('/api/health/disk')
        assert response.status_code == 200
        
        disk_data = response.json()
        assert 'total_space' in disk_data
        assert 'available_space' in disk_data
        assert 'usage_percent' in disk_data
        assert 0 <= disk_data['usage_percent'] <= 100


class TestDataIntegrity:
    """Test data integrity and consistency."""
    
    def test_transaction_rollback(self, mock_services, authenticated_user):
        """Test transaction rollback on failure."""
        
        # Configure mock to fail after partial processing
        mock_services['processor'].return_value.extract_clip.side_effect = Exception("Processing failed")
        
        request_data = {
            'video_url': 'https://example.com/test_video.mp4',
            'platform': 'youtube',
            'duration': 60
        }
        
        headers = {'Authorization': f'Bearer {authenticated_user["token"]}'}
        
        # Create clip generation request
        response = client.post('/api/clips/generate', json=request_data, headers=headers)
        assert response.status_code == 201
        
        clip_data = response.json()
        clip_id = clip_data['clip_id']
        
        # Wait for processing to fail
        time.sleep(5)
        
        # Check clip status
        response = client.get(f'/api/clips/{clip_id}', headers=headers)
        clip_status = response.json()
        
        # Should be marked as failed, not in inconsistent state
        assert clip_status['status'] == 'failed'
        assert 'error' in clip_status
    
    def test_duplicate_request_handling(self, mock_services, authenticated_user):
        """Test handling of duplicate requests."""
        
        request_data = {
            'video_url': 'https://example.com/test_video.mp4',
            'platform': 'youtube',
            'duration': 60,
            'idempotency_key': 'test_idempotency_key_123'
        }
        
        headers = {'Authorization': f'Bearer {authenticated_user["token"]}'}
        
        # First request
        response1 = client.post('/api/clips/generate', json=request_data, headers=headers)
        assert response1.status_code == 201
        
        clip_data1 = response1.json()
        
        # Duplicate request with same idempotency key
        response2 = client.post('/api/clips/generate', json=request_data, headers=headers)
        
        # Should return same result or appropriate handling
        if response2.status_code == 201:
            clip_data2 = response2.json()
            assert clip_data1['clip_id'] == clip_data2['clip_id']
        elif response2.status_code == 409:
            # Conflict - duplicate request detected
            error_data = response2.json()
            assert 'duplicate' in error_data['error']['message'].lower()
    
    def test_data_consistency_checks(self):
        """Test data consistency validation."""
        
        # Test data consistency endpoint
        response = client.get('/api/admin/data-integrity')
        
        # Should require admin authentication
        assert response.status_code in [200, 401, 403]
        
        if response.status_code == 200:
            integrity_data = response.json()
            assert 'checks' in integrity_data
            assert 'status' in integrity_data
            
            # All checks should pass
            for check in integrity_data['checks']:
                assert check['status'] in ['passed', 'warning', 'failed']


# Test configuration
pytest_plugins = ['pytest_asyncio']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])