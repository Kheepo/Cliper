import pytest
import json
from unittest.mock import Mock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

class TestAnalyticsWorkflow:
    """Test complete analytics workflow integration."""
    
    @patch('api.middleware.auth.get_current_user')
    @patch('api.routers.analytics.get_current_user_analytics')
    def test_user_analytics_workflow(self, mock_get_user_analytics, mock_get_current_user):
        """Test complete user analytics workflow"""
        # Mock authentication
        mock_user = {
            'id': 'test-user-id',
            'email': 'test@example.com',
            'role': 'user'
        }
        mock_get_current_user.return_value = mock_user
        
        # Mock analytics data
        analytics_data = {
            "total_videos": 15,
            "total_clips": 45,
            "total_processing_time": 3600,
            "average_clip_score": 0.78,
            "clips_by_score_range": {
                "0.9-1.0": 8,
                "0.8-0.9": 12,
                "0.7-0.8": 15,
                "0.6-0.7": 8,
                "below_0.6": 2
            },
            "processing_stats": {
                "successful_jobs": 14,
                "failed_jobs": 1,
                "average_processing_time": 240
            },
            "monthly_activity": [
                {"month": "2024-01", "videos": 5, "clips": 15},
                {"month": "2024-02", "videos": 7, "clips": 21},
                {"month": "2024-03", "videos": 3, "clips": 9}
            ]
        }
        
        mock_get_user_analytics.return_value = analytics_data
        
        # Step 1: Get user analytics
        response = client.get(
            "/api/analytics/user",
            headers={'Authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify analytics structure
        assert data["total_videos"] == 15
        assert data["total_clips"] == 45
        assert data["average_clip_score"] == 0.78
        assert "clips_by_score_range" in data
        assert "processing_stats" in data
        assert "monthly_activity" in data
        
        # Verify score distribution
        score_ranges = data["clips_by_score_range"]
        assert score_ranges["0.9-1.0"] == 8
        assert score_ranges["0.8-0.9"] == 12
        
        # Verify processing stats
        processing = data["processing_stats"]
        assert processing["successful_jobs"] == 14
        assert processing["failed_jobs"] == 1
        
        # Verify monthly activity
        monthly = data["monthly_activity"]
        assert len(monthly) == 3
        assert monthly[0]["month"] == "2024-01"
    
    @patch('api.middleware.auth.get_current_user')
    @patch('api.routers.analytics.get_job_analytics')
    def test_job_analytics_workflow(self, mock_get_job_analytics, mock_get_current_user):
        """Test job analytics workflow"""
        job_id = "job-123"
        
        # Mock authentication
        mock_user = {
            'id': 'test-user-id',
            'email': 'test@example.com',
            'role': 'user'
        }
        mock_get_current_user.return_value = mock_user
        
        # Mock job analytics data
        job_analytics = {
            "job_id": job_id,
            "processing_time": 180,
            "clips_generated": 8,
            "highest_score": 0.95,
            "lowest_score": 0.65,
            "average_score": 0.82,
            "video_metadata": {
                "duration": 300,
                "resolution": "1920x1080",
                "fps": 30,
                "file_size": 52428800
            },
            "processing_stages": [
                {"stage": "upload", "duration": 15, "status": "completed"},
                {"stage": "audio_extraction", "duration": 30, "status": "completed"},
                {"stage": "transcription", "duration": 90, "status": "completed"},
                {"stage": "analysis", "duration": 45, "status": "completed"}
            ],
            "clip_distribution": {
                "0-60s": 3,
                "60-120s": 2,
                "120-180s": 2,
                "180s+": 1
            }
        }
        
        mock_get_job_analytics.return_value = job_analytics
        
        # Step 1: Get job analytics
        response = client.get(
            f"/api/analytics/job/{job_id}",
            headers={'Authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify job analytics structure
        assert data["job_id"] == job_id
        assert data["processing_time"] == 180
        assert data["clips_generated"] == 8
        assert data["highest_score"] == 0.95
        assert data["average_score"] == 0.82
        
        # Verify video metadata
        metadata = data["video_metadata"]
        assert metadata["duration"] == 300
        assert metadata["resolution"] == "1920x1080"
        
        # Verify processing stages
        stages = data["processing_stages"]
        assert len(stages) == 4
        assert stages[0]["stage"] == "upload"
        assert all(stage["status"] == "completed" for stage in stages)
        
        # Verify clip distribution
        distribution = data["clip_distribution"]
        assert distribution["0-60s"] == 3
        assert distribution["60-120s"] == 2
    
    @patch('api.middleware.auth.get_current_user')
    @patch('api.routers.analytics.get_system_metrics')
    def test_system_analytics_workflow(self, mock_get_system_analytics, mock_get_current_user):
        """Test system analytics workflow"""
        # Mock authentication
        mock_user = {
            'id': 'test-user-id',
            'email': 'test@example.com',
            'role': 'admin'
        }
        mock_get_current_user.return_value = mock_user
        
        # Mock system analytics data
        system_analytics = {
            "total_users": 1250,
            "active_users_30d": 890,
            "total_videos_processed": 5420,
            "total_clips_generated": 18750,
            "average_processing_time": 195,
            "system_performance": {
                "cpu_usage_avg": 65.2,
                "memory_usage_avg": 78.5,
                "disk_usage": 45.8,
                "queue_length_avg": 12
            },
            "error_rates": {
                "upload_failures": 2.1,
                "processing_failures": 1.8,
                "timeout_errors": 0.5
            },
            "popular_video_types": {
                "mp4": 4200,
                "mov": 890,
                "avi": 330
            },
            "daily_stats": [
                {"date": "2024-03-01", "videos": 45, "clips": 156},
                {"date": "2024-03-02", "videos": 52, "clips": 178},
                {"date": "2024-03-03", "videos": 38, "clips": 142}
            ]
        }
        
        mock_get_system_analytics.return_value = system_analytics
        
        # Step 1: Get system analytics (admin only)
        response = client.get(
            "/api/analytics/system",
            headers={'Authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify system analytics structure
        assert data["total_users"] == 1250
        assert data["active_users_30d"] == 890
        assert data["total_videos_processed"] == 5420
        assert data["total_clips_generated"] == 18750
        
        # Verify system performance metrics
        performance = data["system_performance"]
        assert performance["cpu_usage_avg"] == 65.2
        assert performance["memory_usage_avg"] == 78.5
        
        # Verify error rates
        errors = data["error_rates"]
        assert errors["upload_failures"] == 2.1
        assert errors["processing_failures"] == 1.8
        
        # Verify popular video types
        video_types = data["popular_video_types"]
        assert video_types["mp4"] == 4200
        assert video_types["mov"] == 890
        
        # Verify daily stats
        daily = data["daily_stats"]
        assert len(daily) == 3
        assert daily[0]["date"] == "2024-03-01"
    
    @patch('api.middleware.auth.get_current_user')
    @patch('api.routers.analytics.get_current_user_analytics')
    def test_analytics_filtering_workflow(self, mock_get_user_analytics, mock_get_current_user):
        """Test analytics with filtering parameters"""
        # Mock authentication
        mock_user = {
            'id': 'test-user-id',
            'email': 'test@example.com',
            'role': 'user'
        }
        mock_get_current_user.return_value = mock_user
        
        # Mock filtered analytics data
        filtered_data = {
            "total_videos": 5,
            "total_clips": 18,
            "average_clip_score": 0.85,
            "date_range": {
                "start": "2024-01-01",
                "end": "2024-01-31"
            }
        }
        
        mock_get_user_analytics.return_value = filtered_data
        
        # Test with date range filtering
        response = client.get(
            "/api/analytics/user?start_date=2024-01-01&end_date=2024-01-31",
            headers={'Authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify filtered results
        assert data["total_videos"] == 5
        assert data["total_clips"] == 18
        assert data["average_clip_score"] == 0.85
        assert "date_range" in data
    
    @patch('api.middleware.auth.get_current_user')
    @patch('api.routers.analytics.export_analytics')
    def test_analytics_export_workflow(self, mock_create_export, mock_get_current_user):
        """Test analytics export functionality"""
        # Mock authentication
        mock_user = {
            'id': 'test-user-id',
            'email': 'test@example.com',
            'role': 'user'
        }
        mock_get_current_user.return_value = mock_user
        
        # Mock export response
        export_data = {
            "export_id": "export-123",
            "status": "processing",
            "created_at": "2024-03-15T10:00:00Z",
            "estimated_completion": "2024-03-15T10:05:00Z"
        }
        
        mock_create_export.return_value = export_data
        
        # Test export creation
        export_request = {
            "format": "csv",
            "include_clips": True,
            "date_range": {
                "start": "2024-01-01",
                "end": "2024-03-15"
            }
        }
        
        response = client.post(
            "/api/analytics/export",
            json=export_request,
            headers={'Authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 202
        data = response.json()
        
        # Verify export response
        assert data["export_id"] == "export-123"
        assert data["status"] == "processing"
        assert "created_at" in data
        assert "estimated_completion" in data
    
    @patch('api.middleware.auth.get_current_user')
    def test_analytics_invalid_date_range(self, mock_get_current_user):
        """Test analytics with invalid date range"""
        # Mock authentication
        mock_user = {
            'id': 'test-user-id',
            'email': 'test@example.com',
            'role': 'user'
        }
        mock_get_current_user.return_value = mock_user
        
        # Test with invalid date range (end before start)
        response = client.get(
            "/api/analytics/user?start_date=2024-03-01&end_date=2024-01-01",
            headers={'Authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data
    
    @patch('api.middleware.auth.get_current_user')
    def test_analytics_nonexistent_job(self, mock_get_current_user):
        """Test analytics for non-existent job"""
        # Mock authentication
        mock_user = {
            'id': 'test-user-id',
            'email': 'test@example.com',
            'role': 'user'
        }
        mock_get_current_user.return_value = mock_user
        
        # Test with non-existent job ID
        response = client.get(
            "/api/analytics/job/nonexistent-job-id",
            headers={'Authorization': 'Bearer test-token'}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data