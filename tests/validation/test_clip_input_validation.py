import pytest
import json
from typing import Dict, Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.main import app
from api.database import get_db
from api.models.video import Video
from api.models.user import User
from api.schemas.clip import ClipCreateRequest, ClipBulkCreateRequest
from api.core.config import settings


class TestClipInputValidation:
    """Comprehensive input validation tests for clip generation parameters."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer valid_jwt_token"}
    
    @pytest.fixture
    def mock_user(self, db_session):
        user = User(
            id="user123",
            email="test@example.com",
            credits=100,
            subscription_tier="premium"
        )
        db_session.add(user)
        db_session.commit()
        return user
    
    @pytest.fixture
    def mock_video(self, db_session, mock_user):
        video = Video(
            id="video123",
            user_id=mock_user.id,
            filename="test_video.mp4",
            file_path="/storage/videos/test_video.mp4",
            duration=120.0,
            status="processed"
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    @pytest.fixture
    def valid_clip_data(self):
        return {
            "start_time": 10.0,
            "duration": 30.0,
            "platform": "youtube",
            "title": "Test Clip",
            "description": "A test clip for validation"
        }
    
    # Start Time Validation Tests
    
    def test_start_time_negative_value(self, client, auth_headers, mock_video):
        """Test validation of negative start_time values."""
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": -5.0,
                "duration": 30.0,
                "platform": "youtube"
            }
        )
        
        assert response.status_code == 422
        error_detail = response.json()['detail']
        assert any("start_time" in str(error).lower() for error in error_detail)
        assert any("negative" in str(error).lower() or "greater" in str(error).lower() for error in error_detail)
    
    def test_start_time_exceeds_video_duration(self, client, auth_headers, mock_video):
        """Test validation when start_time exceeds video duration."""
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 150.0,  # Video duration is 120.0
                "duration": 30.0,
                "platform": "youtube"
            }
        )
        
        assert response.status_code == 422
        error_detail = response.json()['detail']
        assert any("start_time" in str(error).lower() for error in error_detail)
    
    def test_start_time_invalid_type(self, client, auth_headers, mock_video):
        """Test validation of invalid start_time data types."""
        invalid_values = ["not_a_number", None, [], {}, True]
        
        for invalid_value in invalid_values:
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json={
                    "start_time": invalid_value,
                    "duration": 30.0,
                    "platform": "youtube"
                }
            )
            
            assert response.status_code == 422, f"Failed for start_time value: {invalid_value}"
    
    def test_start_time_precision_validation(self, client, auth_headers, mock_video):
        """Test validation of start_time precision."""
        # Test extremely high precision (should be accepted but rounded)
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 10.123456789,
                "duration": 30.0,
                "platform": "youtube"
            }
        )
        
        # Should accept high precision values
        assert response.status_code in [201, 202]
    
    # Duration Validation Tests
    
    def test_duration_negative_value(self, client, auth_headers, mock_video):
        """Test validation of negative duration values."""
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 10.0,
                "duration": -5.0,
                "platform": "youtube"
            }
        )
        
        assert response.status_code == 422
        error_detail = response.json()['detail']
        assert any("duration" in str(error).lower() for error in error_detail)
    
    def test_duration_zero_value(self, client, auth_headers, mock_video):
        """Test validation of zero duration."""
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 10.0,
                "duration": 0.0,
                "platform": "youtube"
            }
        )
        
        assert response.status_code == 422
        error_detail = response.json()['detail']
        assert any("duration" in str(error).lower() for error in error_detail)
    
    def test_duration_exceeds_maximum(self, client, auth_headers, mock_video):
        """Test validation of duration exceeding maximum allowed."""
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 10.0,
                "duration": 3600.0,  # 1 hour, likely exceeds max
                "platform": "youtube"
            }
        )
        
        # Should either accept or reject based on platform limits
        assert response.status_code in [201, 202, 422]
    
    def test_duration_exceeds_remaining_video(self, client, auth_headers, mock_video):
        """Test validation when start_time + duration exceeds video length."""
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 100.0,
                "duration": 50.0,  # 100 + 50 = 150, video is 120 seconds
                "platform": "youtube"
            }
        )
        
        assert response.status_code == 422
        error_detail = response.json()['detail']
        assert any("duration" in str(error).lower() or "exceeds" in str(error).lower() for error in error_detail)
    
    # Platform Validation Tests
    
    def test_platform_invalid_values(self, client, auth_headers, mock_video):
        """Test validation of invalid platform values."""
        invalid_platforms = [
            "invalid_platform",
            "YOUTUBE",  # Case sensitivity
            "tiktok_invalid",
            "",
            " ",
            "youtube ",  # Trailing space
            123,
            None,
            [],
            {}
        ]
        
        for invalid_platform in invalid_platforms:
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": invalid_platform
                }
            )
            
            assert response.status_code == 422, f"Failed for platform value: {invalid_platform}"
    
    def test_platform_valid_values(self, client, auth_headers, mock_video):
        """Test validation of valid platform values."""
        valid_platforms = ["youtube", "tiktok", "instagram", "twitter", "facebook"]
        
        for platform in valid_platforms:
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": platform
                }
            )
            
            # Should accept valid platforms
            assert response.status_code in [201, 202], f"Failed for valid platform: {platform}"
    
    # Title and Description Validation Tests
    
    def test_title_length_validation(self, client, auth_headers, mock_video):
        """Test validation of title length limits."""
        # Test empty title
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube",
                "title": ""
            }
        )
        assert response.status_code == 422
        
        # Test extremely long title
        long_title = "A" * 1000
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube",
                "title": long_title
            }
        )
        assert response.status_code == 422
    
    def test_title_special_characters(self, client, auth_headers, mock_video):
        """Test validation of special characters in title."""
        special_titles = [
            "Title with <script>alert('xss')</script>",
            "Title with SQL'; DROP TABLE clips; --",
            "Title with unicode: 🎬🎥📹",
            "Title with newlines\n\r\t",
            "Title with quotes: \"single\" and 'double'"
        ]
        
        for title in special_titles:
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube",
                    "title": title
                }
            )
            
            # Should either sanitize or reject malicious content
            if "<script>" in title or "DROP TABLE" in title:
                assert response.status_code == 422, f"Should reject malicious title: {title}"
            else:
                assert response.status_code in [201, 202, 422], f"Failed for title: {title}"
    
    def test_description_length_validation(self, client, auth_headers, mock_video):
        """Test validation of description length limits."""
        # Test extremely long description
        long_description = "A" * 5000
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube",
                "description": long_description
            }
        )
        
        # Should reject overly long descriptions
        assert response.status_code == 422
    
    # Video ID Validation Tests
    
    def test_nonexistent_video_id(self, client, auth_headers):
        """Test validation with nonexistent video ID."""
        response = client.post(
            "/api/v1/videos/nonexistent_video/clips",
            headers=auth_headers,
            json={
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube"
            }
        )
        
        assert response.status_code == 404
        error_detail = response.json()['detail']
        assert "video" in error_detail.lower() and "not found" in error_detail.lower()
    
    def test_invalid_video_id_format(self, client, auth_headers):
        """Test validation with invalid video ID formats."""
        invalid_ids = [
            "",
            " ",
            "../../../etc/passwd",
            "<script>alert('xss')</script>",
            "video'; DROP TABLE videos; --",
            "video\x00null",
            "video\n\r\t"
        ]
        
        for invalid_id in invalid_ids:
            response = client.post(
                f"/api/v1/videos/{invalid_id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                }
            )
            
            assert response.status_code in [400, 404, 422], f"Failed for video ID: {repr(invalid_id)}"
    
    # JSON Structure Validation Tests
    
    def test_missing_required_fields(self, client, auth_headers, mock_video):
        """Test validation when required fields are missing."""
        required_fields = ["start_time", "duration", "platform"]
        
        for field_to_remove in required_fields:
            data = {
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube"
            }
            del data[field_to_remove]
            
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json=data
            )
            
            assert response.status_code == 422, f"Failed when missing field: {field_to_remove}"
            error_detail = response.json()['detail']
            assert any(field_to_remove in str(error).lower() for error in error_detail)
    
    def test_extra_fields_handling(self, client, auth_headers, mock_video):
        """Test handling of extra/unknown fields."""
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json={
                "start_time": 10.0,
                "duration": 30.0,
                "platform": "youtube",
                "unknown_field": "should_be_ignored",
                "malicious_field": "<script>alert('xss')</script>"
            }
        )
        
        # Should either ignore extra fields or reject the request
        assert response.status_code in [201, 202, 422]
    
    def test_malformed_json(self, client, auth_headers, mock_video):
        """Test handling of malformed JSON."""
        malformed_json_strings = [
            '{"start_time": 10.0, "duration": 30.0, "platform": "youtube"',  # Missing closing brace
            '{"start_time": 10.0, "duration": 30.0, "platform": "youtube",}',  # Trailing comma
            '{start_time: 10.0, duration: 30.0, platform: "youtube"}',  # Unquoted keys
            'not_json_at_all'
        ]
        
        for malformed_json in malformed_json_strings:
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                data=malformed_json,
                headers={**auth_headers, "Content-Type": "application/json"}
            )
            
            assert response.status_code == 422, f"Failed for malformed JSON: {malformed_json}"
    
    # Bulk Operations Validation Tests
    
    def test_bulk_clips_validation(self, client, auth_headers, mock_video):
        """Test validation for bulk clip creation."""
        # Test empty bulk request
        response = client.post(
            "/api/v1/clips/bulk",
            headers=auth_headers,
            json={"clips": []}
        )
        assert response.status_code == 422
        
        # Test bulk request with too many clips
        large_bulk_request = {
            "clips": [
                {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                }
            ] * 1000  # Assuming 1000 is over the limit
        }
        
        response = client.post(
            "/api/v1/clips/bulk",
            headers=auth_headers,
            json=large_bulk_request
        )
        assert response.status_code == 422
    
    def test_bulk_clips_mixed_validation(self, client, auth_headers, mock_video):
        """Test bulk request with mix of valid and invalid clips."""
        mixed_clips = {
            "clips": [
                {
                    "video_id": mock_video.id,
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                },
                {
                    "video_id": mock_video.id,
                    "start_time": -5.0,  # Invalid
                    "duration": 30.0,
                    "platform": "youtube"
                },
                {
                    "video_id": "nonexistent",  # Invalid
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                }
            ]
        }
        
        response = client.post(
            "/api/v1/clips/bulk",
            headers=auth_headers,
            json=mixed_clips
        )
        
        # Should reject the entire batch if any clip is invalid
        assert response.status_code == 422
    
    # Advanced Validation Tests
    
    def test_unicode_handling(self, client, auth_headers, mock_video):
        """Test handling of Unicode characters in input."""
        unicode_data = {
            "start_time": 10.0,
            "duration": 30.0,
            "platform": "youtube",
            "title": "测试视频 🎬 العنوان русский título",
            "description": "Description with émojis 🎥📹 and spëcial characters"
        }
        
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json=unicode_data
        )
        
        # Should handle Unicode properly
        assert response.status_code in [201, 202]
    
    def test_boundary_value_testing(self, client, auth_headers, mock_video):
        """Test boundary values for numeric fields."""
        boundary_tests = [
            {"start_time": 0.0, "duration": 0.1},  # Minimum values
            {"start_time": 119.9, "duration": 0.1},  # Maximum start_time
            {"start_time": 0.0, "duration": 120.0},  # Maximum duration
            {"start_time": 60.0, "duration": 60.0},  # Exact video length
        ]
        
        for test_data in boundary_tests:
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json={
                    **test_data,
                    "platform": "youtube"
                }
            )
            
            # Boundary values should be handled appropriately
            assert response.status_code in [201, 202, 422], f"Failed for boundary test: {test_data}"
    
    def test_concurrent_validation_requests(self, client, auth_headers, mock_video):
        """Test validation under concurrent request load."""
        import asyncio
        import aiohttp
        
        async def make_request():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://testserver/api/v1/videos/{mock_video.id}/clips",
                    headers=auth_headers,
                    json={
                        "start_time": 10.0,
                        "duration": 30.0,
                        "platform": "youtube"
                    }
                ) as response:
                    return response.status
        
        # This test would need to be run with pytest-asyncio
        # For now, we'll test sequential requests to simulate load
        responses = []
        for _ in range(10):
            response = client.post(
                f"/api/v1/videos/{mock_video.id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                }
            )
            responses.append(response.status_code)
        
        # All requests should be validated consistently
        assert all(status in [201, 202, 422, 429] for status in responses)
    
    def test_schema_version_compatibility(self, client, auth_headers, mock_video):
        """Test backward compatibility with different schema versions."""
        # Test old schema format (if applicable)
        old_format_data = {
            "startTime": 10.0,  # camelCase instead of snake_case
            "duration": 30.0,
            "platform": "youtube"
        }
        
        response = client.post(
            f"/api/v1/videos/{mock_video.id}/clips",
            headers=auth_headers,
            json=old_format_data
        )
        
        # Should either accept with conversion or reject with clear error
        if response.status_code == 422:
            error_detail = response.json()['detail']
            assert any("start_time" in str(error).lower() for error in error_detail)
        else:
            assert response.status_code in [201, 202]