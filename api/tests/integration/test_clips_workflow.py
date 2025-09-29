import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app

class TestClipsManagementWorkflow:
    """Test complete clips management workflow integration."""
    
    @patch('api.services.supabase_service.supabase_service')
    def test_complete_clip_lifecycle_workflow(self, mock_supabase, client, auth_headers):
        """Test complete clip lifecycle from creation to deletion."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        
        # Mock user authentication
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock clip creation
        clip_data = {
            "id": "clip-123",
            "title": "Test Viral Clip",
            "description": "A test clip for viral content",
            "start_time": 10.5,
            "end_time": 25.3,
            "score": 0.95,
            "transcript": "This is a viral moment!",
            "file_path": "/clips/clip-123.mp4",
            "thumbnail_path": "/thumbnails/clip-123.jpg",
            "user_id": "user-123",
            "job_id": "job-456",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        mock_supabase_instance.create_clip.return_value = clip_data
        mock_supabase_instance.get_clip.return_value = clip_data
        mock_supabase_instance.update_clip.return_value = {**clip_data, "title": "Updated Viral Clip"}
        mock_supabase_instance.delete_clip.return_value = True
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Create a new clip
            create_response = client.post(
                "/api/clips/",
                json={
                    "title": "Test Viral Clip",
                    "description": "A test clip for viral content",
                    "start_time": 10.5,
                    "end_time": 25.3,
                    "score": 0.95,
                    "transcript": "This is a viral moment!",
                    "file_path": "/clips/clip-123.mp4",
                    "thumbnail_path": "/thumbnails/clip-123.jpg",
                    "job_id": "job-456"
                },
                headers=auth_headers
            )
            
            assert create_response.status_code == 201
            created_clip = create_response.json()
            assert created_clip["title"] == "Test Viral Clip"
            assert created_clip["score"] == 0.95
            clip_id = created_clip["id"]
            
            # Step 2: Retrieve the created clip
            get_response = client.get(
                f"/api/clips/{clip_id}",
                headers=auth_headers
            )
            
            assert get_response.status_code == 200
            retrieved_clip = get_response.json()
            assert retrieved_clip["id"] == clip_id
            assert retrieved_clip["title"] == "Test Viral Clip"
            
            # Step 3: Update the clip
            update_response = client.put(
                f"/api/clips/{clip_id}",
                json={
                    "title": "Updated Viral Clip",
                    "description": "An updated test clip"
                },
                headers=auth_headers
            )
            
            assert update_response.status_code == 200
            updated_clip = update_response.json()
            assert updated_clip["title"] == "Updated Viral Clip"
            
            # Step 4: List clips (should include our clip)
            mock_supabase_instance.get_clips.return_value = {
                "clips": [updated_clip],
                "total": 1,
                "page": 1,
                "per_page": 10
            }
            
            list_response = client.get(
                "/api/clips/",
                headers=auth_headers
            )
            
            assert list_response.status_code == 200
            clips_data = list_response.json()
            assert clips_data["total"] == 1
            assert len(clips_data["clips"]) == 1
            assert clips_data["clips"][0]["id"] == clip_id
            
            # Step 5: Delete the clip
            delete_response = client.delete(
                f"/api/clips/{clip_id}",
                headers=auth_headers
            )
            
            assert delete_response.status_code == 200
            assert delete_response.json()["message"] == "Clip deleted successfully"
            
            # Step 6: Verify clip is deleted
            mock_supabase_instance.get_clip.side_effect = Exception("Clip not found")
            
            get_deleted_response = client.get(
                f"/api/clips/{clip_id}",
                headers=auth_headers
            )
            
            assert get_deleted_response.status_code == 404
    
    @patch('api.services.supabase_service.supabase_service')
    @patch('api.tasks.generate_clips_task')
    def test_clip_generation_workflow(self, mock_task, mock_supabase, client, auth_headers):
        """Test clip generation workflow from video processing."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock job data
        job_data = {
            "id": "job-789",
            "status": "completed",
            "user_id": "user-123",
            "file_path": "/videos/test-video.mp4"
        }
        mock_supabase_instance.get_job.return_value = job_data
        
        # Mock clip generation task
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_task.delay.return_value = mock_result
        
        # Mock generated clips
        generated_clips = [
            {
                "id": "clip-001",
                "title": "Viral Moment 1",
                "start_time": 10.0,
                "end_time": 25.0,
                "score": 0.95,
                "transcript": "Amazing content here!"
            },
            {
                "id": "clip-002",
                "title": "Viral Moment 2",
                "start_time": 45.0,
                "end_time": 60.0,
                "score": 0.88,
                "transcript": "Another great moment!"
            }
        ]
        
        mock_supabase_instance.create_clips_batch.return_value = generated_clips
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Request clip generation
            generate_response = client.post(
                "/api/clips/generate",
                json={
                    "job_id": "job-789",
                    "min_score": 0.8,
                    "max_clips": 5,
                    "min_duration": 10,
                    "max_duration": 30
                },
                headers=auth_headers
            )
            
            assert generate_response.status_code == 202
            generation_data = generate_response.json()
            assert generation_data["message"] == "Clip generation started"
            assert "task_id" in generation_data
            
            # Verify task was called with correct parameters
            mock_task.delay.assert_called_once()
            call_args = mock_task.delay.call_args[0]
            assert "job-789" in call_args
            assert "user-123" in call_args
            
            # Step 2: Check generation status (simulate completion)
            mock_supabase_instance.get_clips_by_job.return_value = generated_clips
            
            clips_response = client.get(
                "/api/clips/?job_id=job-789",
                headers=auth_headers
            )
            
            assert clips_response.status_code == 200
            clips_data = clips_response.json()
            assert len(clips_data["clips"]) == 2
            assert all(clip["score"] >= 0.8 for clip in clips_data["clips"])
    
    @patch('api.services.supabase_service.supabase_service')
    def test_clips_filtering_and_search_workflow(self, mock_supabase, client, auth_headers):
        """Test clips filtering and search functionality."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock clips data
        all_clips = [
            {
                "id": "clip-001",
                "title": "Funny Cat Video",
                "score": 0.95,
                "created_at": "2024-01-01T00:00:00Z",
                "tags": ["funny", "cats"]
            },
            {
                "id": "clip-002",
                "title": "Dog Playing Fetch",
                "score": 0.88,
                "created_at": "2024-01-02T00:00:00Z",
                "tags": ["dogs", "sports"]
            },
            {
                "id": "clip-003",
                "title": "Cat and Dog Friends",
                "score": 0.92,
                "created_at": "2024-01-03T00:00:00Z",
                "tags": ["cats", "dogs", "friendship"]
            }
        ]
        
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Search by title
            mock_supabase_instance.get_clips.return_value = {
                "clips": [clip for clip in all_clips if "cat" in clip["title"].lower()],
                "total": 2,
                "page": 1,
                "per_page": 10
            }
            
            search_response = client.get(
                "/api/clips/?search=cat",
                headers=auth_headers
            )
            
            assert search_response.status_code == 200
            search_data = search_response.json()
            assert search_data["total"] == 2
            assert all("cat" in clip["title"].lower() for clip in search_data["clips"])
            
            # Step 2: Filter by minimum score
            mock_supabase_instance.get_clips.return_value = {
                "clips": [clip for clip in all_clips if clip["score"] >= 0.9],
                "total": 2,
                "page": 1,
                "per_page": 10
            }
            
            score_filter_response = client.get(
                "/api/clips/?min_score=0.9",
                headers=auth_headers
            )
            
            assert score_filter_response.status_code == 200
            score_data = score_filter_response.json()
            assert score_data["total"] == 2
            assert all(clip["score"] >= 0.9 for clip in score_data["clips"])
            
            # Step 3: Sort by creation date
            mock_supabase_instance.get_clips.return_value = {
                "clips": sorted(all_clips, key=lambda x: x["created_at"], reverse=True),
                "total": 3,
                "page": 1,
                "per_page": 10
            }
            
            sort_response = client.get(
                "/api/clips/?sort_by=created_at&sort_order=desc",
                headers=auth_headers
            )
            
            assert sort_response.status_code == 200
            sort_data = sort_response.json()
            assert sort_data["clips"][0]["id"] == "clip-003"  # Most recent
            
            # Step 4: Pagination
            mock_supabase_instance.get_clips.return_value = {
                "clips": all_clips[:2],  # First 2 clips
                "total": 3,
                "page": 1,
                "per_page": 2
            }
            
            page_response = client.get(
                "/api/clips/?page=1&per_page=2",
                headers=auth_headers
            )
            
            assert page_response.status_code == 200
            page_data = page_response.json()
            assert len(page_data["clips"]) == 2
            assert page_data["total"] == 3
            assert page_data["page"] == 1
    
    @patch('api.services.supabase_service.supabase_service')
    def test_clips_summary_workflow(self, mock_supabase, client, auth_headers):
        """Test clips summary and analytics workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock summary data
        summary_data = {
            "total_clips": 25,
            "total_duration": 450.5,
            "average_score": 0.87,
            "top_performing_clips": [
                {
                    "id": "clip-001",
                    "title": "Best Viral Moment",
                    "score": 0.98
                },
                {
                    "id": "clip-002",
                    "title": "Second Best Moment",
                    "score": 0.95
                }
            ],
            "score_distribution": {
                "0.9-1.0": 8,
                "0.8-0.9": 12,
                "0.7-0.8": 4,
                "0.6-0.7": 1
            },
            "clips_by_date": {
                "2024-01-01": 5,
                "2024-01-02": 8,
                "2024-01-03": 12
            }
        }
        
        mock_supabase_instance.get_clips_summary.return_value = summary_data
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Get clips summary
            summary_response = client.get(
                "/api/clips/summary/overview",
                headers=auth_headers
            )
            
            assert summary_response.status_code == 200
            summary = summary_response.json()
            
            # Verify summary structure
            assert summary["total_clips"] == 25
            assert summary["average_score"] == 0.87
            assert len(summary["top_performing_clips"]) == 2
            assert summary["top_performing_clips"][0]["score"] == 0.98
            
            # Verify score distribution
            assert "score_distribution" in summary
            assert summary["score_distribution"]["0.9-1.0"] == 8
            
            # Verify date analytics
            assert "clips_by_date" in summary
            assert summary["clips_by_date"]["2024-01-03"] == 12

class TestClipsPermissionsWorkflow:
    """Test clips permissions and access control workflows."""
    
    @patch('api.services.supabase_service.supabase_service')
    def test_clip_ownership_workflow(self, mock_supabase, client):
        """Test clip ownership and access control."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        
        # Mock two different users
        user1_data = {"id": "user-123", "email": "user1@example.com"}
        user2_data = {"id": "user-456", "email": "user2@example.com"}
        
        # Mock clip owned by user1
        clip_data = {
            "id": "clip-123",
            "title": "User1's Clip",
            "user_id": "user-123",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        mock_supabase_instance.get_clip.return_value = clip_data
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: User1 accesses their own clip (should succeed)
            mock_supabase_instance.get_user_from_token.return_value = user1_data
            
            owner_response = client.get(
                "/api/clips/clip-123",
                headers={"Authorization": "Bearer user1-token"}
            )
            
            assert owner_response.status_code == 200
            assert owner_response.json()["id"] == "clip-123"
            
            # Step 2: User2 tries to access user1's clip (should fail)
            mock_supabase_instance.get_user_from_token.return_value = user2_data
            
            unauthorized_response = client.get(
                "/api/clips/clip-123",
                headers={"Authorization": "Bearer user2-token"}
            )
            
            assert unauthorized_response.status_code == 403
            
            # Step 3: User2 tries to update user1's clip (should fail)
            update_response = client.put(
                "/api/clips/clip-123",
                json={"title": "Hacked Clip"},
                headers={"Authorization": "Bearer user2-token"}
            )
            
            assert update_response.status_code == 403
            
            # Step 4: User2 tries to delete user1's clip (should fail)
            delete_response = client.delete(
                "/api/clips/clip-123",
                headers={"Authorization": "Bearer user2-token"}
            )
            
            assert delete_response.status_code == 403
    
    def test_unauthenticated_access_workflow(self, client):
        """Test unauthenticated access to clips endpoints."""
        # All clips endpoints should require authentication
        endpoints = [
            ("GET", "/api/clips/"),
            ("POST", "/api/clips/"),
            ("GET", "/api/clips/clip-123"),
            ("PUT", "/api/clips/clip-123"),
            ("DELETE", "/api/clips/clip-123"),
            ("POST", "/api/clips/generate"),
            ("GET", "/api/clips/summary/overview")
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            elif method == "PUT":
                response = client.put(endpoint, json={})
            elif method == "DELETE":
                response = client.delete(endpoint)
            
            assert response.status_code == 401, f"Endpoint {method} {endpoint} should require authentication"

class TestClipsErrorHandling:
    """Test clips error handling workflows."""
    
    @patch('api.services.supabase_service.supabase_service')
    def test_database_error_handling_workflow(self, mock_supabase, client, auth_headers):
        """Test handling of database errors in clips operations."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock database failures
        mock_supabase_instance.create_clip.side_effect = Exception("Database connection failed")
        mock_supabase_instance.get_clip.side_effect = Exception("Database timeout")
        mock_supabase_instance.update_clip.side_effect = Exception("Database constraint violation")
        mock_supabase_instance.delete_clip.side_effect = Exception("Database lock timeout")
        
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Test create clip error handling
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
            assert "error" in create_response.json()
            
            # Test get clip error handling
            get_response = client.get(
                "/api/clips/clip-123",
                headers=auth_headers
            )
            
            assert get_response.status_code == 500
            
            # Test update clip error handling
            update_response = client.put(
                "/api/clips/clip-123",
                json={"title": "Updated Title"},
                headers=auth_headers
            )
            
            assert update_response.status_code == 500
            
            # Test delete clip error handling
            delete_response = client.delete(
                "/api/clips/clip-123",
                headers=auth_headers
            )
            
            assert delete_response.status_code == 500
    
    @patch('api.services.supabase_service.supabase_service')
    def test_validation_error_workflow(self, mock_supabase, client, auth_headers):
        """Test input validation error handling."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Test invalid clip data
            invalid_clips = [
                {"title": ""},  # Empty title
                {"title": "Valid Title", "start_time": -1},  # Negative start time
                {"title": "Valid Title", "start_time": 20, "end_time": 10},  # End before start
                {"title": "Valid Title", "score": 1.5},  # Score > 1
                {"title": "Valid Title", "score": -0.1},  # Negative score
            ]
            
            for invalid_clip in invalid_clips:
                response = client.post(
                    "/api/clips/",
                    json=invalid_clip,
                    headers=auth_headers
                )
                
                assert response.status_code == 422  # Validation error
                error_data = response.json()
                assert "detail" in error_data