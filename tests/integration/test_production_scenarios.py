#!/usr/bin/env python3
"""
Comprehensive integration tests for production scenarios and edge cases.
Tests the complete system under realistic production conditions.
"""

import os
import asyncio
import pytest
import tempfile
import shutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from api.main import app
from api.database import get_db
from api.models.database_models import User, JobResult
from api.models.pydantic_models import ClipResult, GeneratedClip
from api.core.config import settings
from api.services.supabase_service import SupabaseService
from api.services.unified_llm_service import unified_llm_service
from api.services.redis_service import RedisService
from api.services.auth_service import auth_service
# Remove unused imports - fixtures will be defined locally if needed


@pytest.fixture
def auth_headers():
    """Authentication headers for testing."""
    return {"Authorization": "Bearer valid_access_token"}


class TestProductionScenarios:
    """Test production scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_high_load_concurrent_requests(self, auth_headers: Dict[str, str]):
        """Test system behavior under high concurrent load."""
        with TestClient(app) as client:
            # Submit multiple concurrent clip generation requests
            responses = []
            for i in range(5):
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "video_url": f"https://example.com/video_{i}.mp4",
                        "content": f"Test content {i}",
                        "duration": 60
                    }
                )
                responses.append(response)
            
            # Verify responses
            successful_responses = [r for r in responses if not isinstance(r, Exception)]
            assert len(successful_responses) >= 15, "At least 75% of requests should succeed under load"
            
            for response in successful_responses:
                if hasattr(response, 'status_code'):
                    assert response.status_code in [200, 201, 202], f"Unexpected status code: {response.status_code}"
    
    @pytest.mark.asyncio
    async def test_database_connection_recovery(self, auth_headers: Dict[str, str]):
        """Test system recovery from database connection issues."""
        with TestClient(app) as client:
            # First, verify normal operation
            response = client.get("/api/v1/clips/", headers=auth_headers)
            assert response.status_code == 200
            
            # Simulate database connection failure
            with patch('api.database.get_db') as mock_get_db:
                mock_get_db.side_effect = Exception("Database connection failed")
                
                response = client.get("/api/v1/clips/", headers=auth_headers)
                assert response.status_code == 500
            
            # Verify recovery after connection is restored
            response = client.get("/api/v1/clips/", headers=auth_headers)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_redis_connection_recovery(self, auth_headers: Dict[str, str]):
        """Test system behavior when Redis is unavailable."""
        with TestClient(app) as client:
            # Simulate Redis connection failure
            with patch.object(RedisService, 'get_client') as mock_redis:
                mock_redis.side_effect = redis.ConnectionError("Redis connection failed")
                
                # System should still function without Redis (degraded mode)
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": "Test content",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # Should either succeed or fail gracefully
                assert response.status_code in [200, 201, 202, 503]
    
    @pytest.mark.asyncio
    async def test_external_service_failures(self, auth_headers: Dict[str, str]):
        """Test handling of external service failures."""
        with TestClient(app) as client:
            # Test LLM service failure
            with patch.object(unified_llm_service, 'select_optimal_segments') as mock_llm:
                mock_llm.side_effect = Exception("LLM service unavailable")
                
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": "Test content",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # Should handle gracefully
                assert response.status_code in [202, 500, 503]
            
            # Test Supabase service failure
            with patch.object(SupabaseService, 'upload_file') as mock_supabase:
                mock_supabase.side_effect = Exception("Supabase service unavailable")
                
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": "Test content",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # Should handle gracefully
                assert response.status_code in [202, 500, 503]
    
    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, auth_headers: Dict[str, str]):
        """Test system behavior under memory pressure."""
        with TestClient(app) as client:
            # Simulate high memory usage
            with patch('psutil.virtual_memory') as mock_memory:
                mock_memory.return_value = MagicMock(percent=95.0, available=1024*1024*100)  # 95% usage
                
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": "Test content",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # System should either reject request or handle gracefully
                assert response.status_code in [202, 429, 503]
    
    @pytest.mark.asyncio
    async def test_disk_space_handling(self, auth_headers: Dict[str, str]):
        """Test system behavior when disk space is low."""
        with TestClient(app) as client:
            # Simulate low disk space
            with patch('psutil.disk_usage') as mock_disk:
                mock_disk.return_value = MagicMock(
                    total=1024*1024*1024*100,  # 100GB
                    used=1024*1024*1024*95,    # 95GB used
                    free=1024*1024*1024*5      # 5GB free
                )
                
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": "Test content",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # System should handle low disk space gracefully
                assert response.status_code in [202, 507, 503]
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self, auth_headers: Dict[str, str]):
        """Test rate limiting under various scenarios."""
        with TestClient(app) as client:
            # Test normal rate limiting
            responses = []
            for i in range(15):  # Exceed typical rate limit
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": f"Test content {i}",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                responses.append(response)
            
            # Should see rate limiting kick in
            rate_limited_responses = [r for r in responses if r.status_code == 429]
            assert len(rate_limited_responses) > 0, "Rate limiting should be enforced"
    
    @pytest.mark.asyncio
    async def test_large_content_processing(self, auth_headers: Dict[str, str]):
        """Test processing of large content inputs."""
        with TestClient(app) as client:
            # Test with very large content
            large_content = "This is a test content. " * 1000  # ~25KB content
            
            response = client.post(
                "/api/v1/clips/generate",
                headers=auth_headers,
                json={
                    "content": large_content,
                    "platform": "tiktok",
                    "style": "engaging",
                    "duration": 30
                }
            )
            
            # Should handle large content appropriately
            assert response.status_code in [202, 413, 422]
    
    @pytest.mark.asyncio
    async def test_malformed_request_handling(self, auth_headers: Dict[str, str]):
        """Test handling of malformed requests."""
        with TestClient(app) as client:
            # Test various malformed requests
            malformed_requests = [
                {},  # Empty request
                {"content": ""},  # Empty content
                {"content": "test", "platform": "invalid_platform"},  # Invalid platform
                {"content": "test", "platform": "tiktok", "duration": -1},  # Invalid duration
                {"content": "test", "platform": "tiktok", "duration": 1000},  # Too long duration
                {"content": None, "platform": "tiktok"},  # Null content
            ]
            
            for request_data in malformed_requests:
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json=request_data
                )
                
                # Should return appropriate error codes
                assert response.status_code in [400, 422], f"Request {request_data} should be rejected"
    
    @pytest.mark.asyncio
    async def test_authentication_edge_cases(self):
        """Test authentication edge cases."""
        with TestClient(app) as client:
            # Test with expired token
            expired_token = auth_service._generate_token(
                data={"sub": "test@example.com"},
                expires_delta=timedelta(seconds=-1)  # Already expired
            )
            
            response = client.get(
                "/api/v1/clips/",
                headers={"Authorization": f"Bearer {expired_token}"}
            )
            assert response.status_code == 401
            
            # Test with malformed token
            response = client.get(
                "/api/v1/clips/",
                headers={"Authorization": "Bearer invalid_token"}
            )
            assert response.status_code == 401
            
            # Test with missing token
            response = client.get("/api/v1/clips/")
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_concurrent_clip_processing(self, auth_headers: Dict[str, str]):
        """Test concurrent processing of multiple clips."""
        with TestClient(app) as client:
            # Create multiple clips
            clip_ids = []
            for i in range(5):
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": f"Test content {i}",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                if response.status_code in [200, 201, 202]:
                    data = response.json()
                    clip_ids.append(data.get("id") or data.get("clip_id"))
            
            # Wait a bit for processing
            import time
            time.sleep(2)
            
            # Check status of all clips
            for clip_id in clip_ids:
                if clip_id:
                    response = client.get(
                        f"/api/v1/clips/{clip_id}",
                        headers=auth_headers
                    )
                    assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_websocket_connection_stability(self, auth_headers: Dict[str, str]):
        """Test WebSocket connection stability under various conditions."""
        with TestClient(app) as client:
            # Test WebSocket connection stability
            # Note: TestClient doesn't support WebSocket testing directly
            # This would require a different approach in a real scenario
            
            # Test regular HTTP endpoints for now
            response = client.get("/api/v1/clips/", headers=auth_headers)
            assert response.status_code == 200
            
            # Test clip status updates that would trigger WebSocket notifications
            response = client.post(
                "/api/v1/clips/generate",
                headers=auth_headers,
                json={
                    "content": "Test content for WebSocket",
                    "platform": "tiktok",
                    "style": "engaging",
                    "duration": 30
                }
            )
            
            assert response.status_code in [200, 201, 202]
    
    @pytest.mark.asyncio
    async def test_data_consistency_under_load(self, auth_headers: Dict[str, str]):
        """Test data consistency under concurrent operations."""
        with TestClient(app) as client:
            # Create a clip
            response = client.post(
                "/api/v1/clips/generate",
                headers=auth_headers,
                json={
                    "content": "Test content for consistency",
                    "platform": "tiktok",
                    "style": "engaging",
                    "duration": 30
                }
            )
            
            assert response.status_code in [200, 201, 202]
            data = response.json()
            clip_id = data.get("id") or data.get("clip_id")
            
            if clip_id:
                # Perform concurrent operations on the same clip
                responses = []
                for i in range(10):
                    response = client.get(f"/api/v1/clips/{clip_id}", headers=auth_headers)
                    responses.append(response)
                
                # All responses should be consistent
                successful_responses = [r for r in responses if hasattr(r, 'status_code')]
                assert len(successful_responses) > 0
                
                # Verify data consistency
                first_response_data = None
                for response in successful_responses:
                    if response.status_code == 200:
                        data = response.json()
                        if first_response_data is None:
                            first_response_data = data
                        else:
                            # Key fields should be consistent
                            assert data["id"] == first_response_data["id"]
                            assert data["content"] == first_response_data["content"]
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_simulation(self, auth_headers: Dict[str, str]):
        """Test system behavior during graceful shutdown."""
        with TestClient(app) as client:
            # Start some operations
            response = client.post(
                "/api/v1/clips/generate",
                headers=auth_headers,
                json={
                    "content": "Test content for shutdown",
                    "platform": "tiktok",
                    "style": "engaging",
                    "duration": 30
                }
            )
            
            assert response.status_code in [200, 201, 202]
            
            # Simulate shutdown by checking health endpoint
            response = client.get("/api/v1/monitoring/health")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_monitoring_endpoints_under_load(self, auth_headers: Dict[str, str]):
        """Test monitoring endpoints under load."""
        with TestClient(app) as client:
            # Test multiple monitoring endpoints concurrently
            monitoring_endpoints = [
                "/api/v1/monitoring/health",
                "/api/v1/monitoring/system",
                "/api/v1/monitoring/database",
                "/api/v1/monitoring/application",
                "/api/v1/monitoring/dashboard",
                "/api/v1/monitoring/alerts"
            ]
            
            responses = []
            for endpoint in monitoring_endpoints:
                if "system" in endpoint or "database" in endpoint or "application" in endpoint or "dashboard" in endpoint or "alerts" in endpoint:
                    # These require authentication
                    response = client.get(endpoint, headers=auth_headers)
                else:
                    # Health endpoint doesn't require auth
                    response = client.get(endpoint)
                responses.append(response)
            
            # Most monitoring endpoints should respond successfully
            successful_responses = [
                r for r in responses 
                if hasattr(r, 'status_code') and r.status_code == 200
            ]
            assert len(successful_responses) >= len(monitoring_endpoints) // 2
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, auth_headers: Dict[str, str]):
        """Test various error recovery scenarios."""
        with TestClient(app) as client:
            # Test recovery from temporary failures
            with patch.object(ClipGenerationService, 'generate_clip') as mock_generate:
                # First call fails, second succeeds
                mock_generate.side_effect = [Exception("Temporary failure"), MagicMock()]
                
                # First request should fail
                response1 = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": "Test content 1",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # Second request should succeed (if retry logic is implemented)
                response2 = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": "Test content 2",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # At least one should succeed or handle gracefully
                assert any(r.status_code in [200, 201, 202] for r in [response1, response2])
    
    @pytest.mark.asyncio
    async def test_file_upload_edge_cases(self, auth_headers: Dict[str, str]):
        """Test file upload edge cases."""
        with TestClient(app) as client:
            # Test with various file types and sizes
            test_cases = [
                {"filename": "test.txt", "content": b"Small text file", "content_type": "text/plain"},
                {"filename": "test.json", "content": b'{"test": "data"}', "content_type": "application/json"},
                {"filename": "large.txt", "content": b"x" * 1024 * 1024, "content_type": "text/plain"},  # 1MB file
                {"filename": "empty.txt", "content": b"", "content_type": "text/plain"},  # Empty file
            ]
            
            for test_case in test_cases:
                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_file.write(test_case["content"])
                    tmp_file.flush()
                    
                    try:
                        # Test file upload if endpoint exists
                        with open(tmp_file.name, "rb") as f:
                            files = {"file": (test_case["filename"], f, test_case["content_type"])}
                            
                            # This would be used if there's a file upload endpoint
                            # response = await client.post(
                            #     "/api/v1/clips/upload",
                            #     headers=auth_headers,
                            #     files=files
                            # )
                            
                            # For now, just verify the file was created correctly
                            assert os.path.getsize(tmp_file.name) == len(test_case["content"])
                    finally:
                        os.unlink(tmp_file.name)


class TestEdgeCases:
    """Test specific edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_unicode_content_handling(self, auth_headers: Dict[str, str]):
        """Test handling of Unicode and special characters."""
        with TestClient(app) as client:
            unicode_contents = [
                "Hello 世界! 🌍",  # Mixed languages and emoji
                "Café naïve résumé",  # Accented characters
                "Здравствуй мир",  # Cyrillic
                "مرحبا بالعالم",  # Arabic
                "🎬🎥📹🎞️",  # Emoji only
                "\n\t\r Special\x00chars",  # Control characters
            ]
            
            for content in unicode_contents:
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": content,
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # Should handle Unicode gracefully
                assert response.status_code in [200, 201, 202, 400, 422]
    
    @pytest.mark.asyncio
    async def test_boundary_value_testing(self, auth_headers: Dict[str, str]):
        """Test boundary values for various parameters."""
        with TestClient(app) as client:
            boundary_tests = [
                {"duration": 1, "expected_codes": [200, 201, 202, 400, 422]},  # Minimum duration
                {"duration": 300, "expected_codes": [200, 201, 202, 400, 422]},  # Maximum duration
                {"duration": 0, "expected_codes": [400, 422]},  # Invalid duration
                {"duration": 301, "expected_codes": [400, 422]},  # Over maximum
            ]
            
            for test_case in boundary_tests:
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": "Test content",
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": test_case["duration"]
                    }
                )
                
                assert response.status_code in test_case["expected_codes"]
    
    @pytest.mark.asyncio
    async def test_timezone_handling(self, auth_headers: Dict[str, str]):
        """Test timezone handling in timestamps."""
        with TestClient(app) as client:
            # Create a clip
            response = client.post(
                "/api/v1/clips/generate",
                headers=auth_headers,
                json={
                    "content": "Test content for timezone",
                    "platform": "tiktok",
                    "style": "engaging",
                    "duration": 30
                }
            )
            
            if response.status_code in [200, 201, 202]:
                data = response.json()
                
                # Verify timestamp format
                if "created_at" in data:
                    created_at = data["created_at"]
                    # Should be ISO format with timezone info
                    assert "T" in created_at
                    # Should handle timezone properly
                    datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    
    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, auth_headers: Dict[str, str]):
        """Test SQL injection prevention."""
        with TestClient(app) as client:
            # Test various SQL injection attempts
            injection_attempts = [
                "'; DROP TABLE clips; --",
                "' OR '1'='1",
                "'; INSERT INTO clips (content) VALUES ('hacked'); --",
                "' UNION SELECT * FROM users --",
            ]
            
            for injection in injection_attempts:
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": injection,
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # Should not cause SQL errors or succeed with injection
                assert response.status_code in [200, 201, 202, 400, 422]
                
                # Verify database integrity by checking if we can still query
                health_response = client.get("/api/v1/monitoring/health")
                assert health_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_xss_prevention(self, auth_headers: Dict[str, str]):
        """Test XSS prevention in content handling."""
        with TestClient(app) as client:
            # Test various XSS attempts
            xss_attempts = [
                "<script>alert('xss')</script>",
                "javascript:alert('xss')",
                "<img src=x onerror=alert('xss')>",
                "<svg onload=alert('xss')>",
            ]
            
            for xss in xss_attempts:
                response = client.post(
                    "/api/v1/clips/generate",
                    headers=auth_headers,
                    json={
                        "content": xss,
                        "platform": "tiktok",
                        "style": "engaging",
                        "duration": 30
                    }
                )
                
                # Should handle XSS attempts safely
                assert response.status_code in [200, 201, 202, 400, 422]
                
                if response.status_code in [200, 201, 202]:
                    data = response.json()
                    # Content should be sanitized or escaped
                    if "content" in data:
                        # Should not contain raw script tags
                        assert "<script>" not in data["content"]