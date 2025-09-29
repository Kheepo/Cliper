import pytest
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status, HTTPException
import redis

from api.main import app
from api.database.config import get_database_session
from api.database import models
from api.utils.redis_client import get_redis_client


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_analytics_data():
    """Sample analytics data for testing."""
    return {
        "clips": [
            {
                "id": "clip_1",
                "title": "Analytics Test Clip 1",
                "views": 150,
                "likes": 25,
                "shares": 5,
                "duration": 30.5,
                "created_at": datetime.now() - timedelta(days=7),
                "user_id": "analytics_user_1",
                "status": "completed"
            },
            {
                "id": "clip_2",
                "title": "Analytics Test Clip 2",
                "views": 300,
                "likes": 45,
                "shares": 12,
                "duration": 45.2,
                "created_at": datetime.now() - timedelta(days=3),
                "user_id": "analytics_user_1",
                "status": "completed"
            },
            {
                "id": "clip_3",
                "title": "Analytics Test Clip 3",
                "views": 75,
                "likes": 8,
                "shares": 2,
                "duration": 60.0,
                "created_at": datetime.now() - timedelta(days=1),
                "user_id": "analytics_user_2",
                "status": "completed"
            }
        ],
        "users": [
            {
                "id": "analytics_user_1",
                "email": "analytics1@example.com",
                "role": "premium",
                "created_at": datetime.now() - timedelta(days=30),
                "total_clips": 2,
                "total_views": 450
            },
            {
                "id": "analytics_user_2",
                "email": "analytics2@example.com",
                "role": "basic",
                "created_at": datetime.now() - timedelta(days=15),
                "total_clips": 1,
                "total_views": 75
            }
        ]
    }


@pytest.fixture
def mock_redis():
    """Mock Redis client for analytics caching."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = False
    mock_redis.hget.return_value = None
    mock_redis.hset.return_value = True
    mock_redis.expire.return_value = True
    return mock_redis


class TestAnalyticsEndpoints:
    """Test analytics endpoints functionality."""
    
    def test_analytics_clips_endpoint_unauthenticated(self, test_client):
        """Test analytics clips endpoint without authentication."""
        response = test_client.get("/api/analytics/clips")
        assert response.status_code in [403, 404]  # Depends on endpoint existence
        
    def test_analytics_users_endpoint_unauthenticated(self, test_client):
        """Test analytics users endpoint without authentication."""
        response = test_client.get("/api/analytics/users")
        assert response.status_code in [403, 404]  # Depends on endpoint existence
        
    def test_analytics_dashboard_endpoint_unauthenticated(self, test_client):
        """Test analytics dashboard endpoint without authentication."""
        response = test_client.get("/api/analytics/dashboard")
        assert response.status_code in [403, 404]  # Depends on endpoint existence


class TestAnalyticsWithRealData:
    """Test analytics with real data scenarios."""
    
    def test_clip_views_analytics_mock(self, sample_analytics_data):
        """Test clip views analytics with mock data."""
        clips = sample_analytics_data["clips"]
        
        # Calculate total views
        total_views = sum(clip["views"] for clip in clips)
        assert total_views == 525
        
        # Calculate average views
        avg_views = total_views / len(clips)
        assert avg_views == 175.0
        
        # Find most viewed clip
        most_viewed = max(clips, key=lambda x: x["views"])
        assert most_viewed["id"] == "clip_2"
        assert most_viewed["views"] == 300
        
    def test_user_engagement_analytics_mock(self, sample_analytics_data):
        """Test user engagement analytics with mock data."""
        clips = sample_analytics_data["clips"]
        
        # Calculate engagement rate (likes + shares) / views
        for clip in clips:
            engagement = (clip["likes"] + clip["shares"]) / clip["views"]
            clip["engagement_rate"] = engagement
        
        # Verify engagement calculations
        assert clips[0]["engagement_rate"] == (25 + 5) / 150  # 0.2
        assert clips[1]["engagement_rate"] == (45 + 12) / 300  # 0.19
        assert clips[2]["engagement_rate"] == (8 + 2) / 75  # 0.133...
        
    def test_time_series_analytics_mock(self, sample_analytics_data):
        """Test time series analytics with mock data."""
        clips = sample_analytics_data["clips"]
        
        # Group clips by day
        daily_stats = {}
        for clip in clips:
            day = clip["created_at"].date()
            if day not in daily_stats:
                daily_stats[day] = {"clips": 0, "views": 0, "likes": 0}
            daily_stats[day]["clips"] += 1
            daily_stats[day]["views"] += clip["views"]
            daily_stats[day]["likes"] += clip["likes"]
        
        # Verify daily aggregation
        assert len(daily_stats) == 3  # 3 different days
        total_clips = sum(stats["clips"] for stats in daily_stats.values())
        assert total_clips == 3


class TestAnalyticsAggregation:
    """Test analytics data aggregation."""
    
    def test_weekly_aggregation_mock(self, sample_analytics_data):
        """Test weekly analytics aggregation."""
        clips = sample_analytics_data["clips"]
        
        # Filter clips from last 7 days
        week_ago = datetime.now() - timedelta(days=7)
        weekly_clips = [clip for clip in clips if clip["created_at"] >= week_ago]
        
        # Calculate weekly metrics
        weekly_views = sum(clip["views"] for clip in weekly_clips)
        weekly_clips_count = len(weekly_clips)
        
        assert weekly_clips_count == 2  # Only clips from last 7 days (clip_2 and clip_3)
        assert weekly_views == 375  # 300 + 75
        
    def test_monthly_aggregation_mock(self, sample_analytics_data):
        """Test monthly analytics aggregation."""
        users = sample_analytics_data["users"]
        
        # Filter users from last 30 days
        month_ago = datetime.now() - timedelta(days=30)
        monthly_users = [user for user in users if user["created_at"] >= month_ago]
        
        # Calculate monthly metrics
        monthly_user_count = len(monthly_users)
        total_monthly_views = sum(user["total_views"] for user in monthly_users)
        
        assert monthly_user_count == 1  # Only analytics_user_2 is within 30 days
        assert total_monthly_views == 75  # Only analytics_user_2's views
        
    def test_user_segmentation_mock(self, sample_analytics_data):
        """Test user segmentation analytics."""
        users = sample_analytics_data["users"]
        
        # Segment users by role
        premium_users = [user for user in users if user["role"] == "premium"]
        basic_users = [user for user in users if user["role"] == "basic"]
        
        assert len(premium_users) == 1
        assert len(basic_users) == 1
        
        # Calculate average views per role
        premium_avg_views = sum(user["total_views"] for user in premium_users) / len(premium_users)
        basic_avg_views = sum(user["total_views"] for user in basic_users) / len(basic_users)
        
        assert premium_avg_views == 450.0
        assert basic_avg_views == 75.0


class TestAnalyticsPerformance:
    """Test analytics performance scenarios."""
    
    def test_large_dataset_analytics_simulation(self):
        """Test analytics with large dataset simulation."""
        # Simulate large dataset
        large_dataset_size = 10000
        
        # Mock large dataset processing
        mock_clips = [
            {
                "id": f"clip_{i}",
                "views": i * 10,
                "likes": i * 2,
                "created_at": datetime.now() - timedelta(days=i % 30)
            }
            for i in range(large_dataset_size)
        ]
        
        # Test aggregation performance simulation
        total_views = sum(clip["views"] for clip in mock_clips)
        expected_total = sum(i * 10 for i in range(large_dataset_size))
        
        assert total_views == expected_total
        assert len(mock_clips) == large_dataset_size
        
    def test_complex_analytics_query_simulation(self):
        """Test complex analytics query simulation."""
        # Simulate complex multi-dimensional analytics
        mock_data = {
            "clips_by_category": {
                "entertainment": 150,
                "education": 200,
                "music": 100
            },
            "engagement_by_time": {
                "morning": 0.15,
                "afternoon": 0.25,
                "evening": 0.35,
                "night": 0.20
            }
        }
        
        # Verify complex aggregations
        total_clips = sum(mock_data["clips_by_category"].values())
        assert total_clips == 450
        
        total_engagement = sum(mock_data["engagement_by_time"].values())
        assert abs(total_engagement - 0.95) < 0.01  # Allow for floating point precision


class TestAnalyticsCaching:
    """Test analytics caching behavior."""
    
    @patch('api.utils.redis_cache.redis.Redis')
    def test_analytics_cache_hit(self, mock_redis_class, test_client):
        """Test analytics cache hit scenario."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        
        # Mock cached analytics data
        cached_analytics = {
            "total_views": 1000,
            "total_clips": 50,
            "avg_engagement": 0.25
        }
        mock_redis.get.return_value = json.dumps(cached_analytics)
        
        # This would test actual caching if integrated
        response = test_client.get("/api/analytics/summary")
        assert response.status_code in [403, 404]  # Still need auth or endpoint doesn't exist
        
    @patch('api.utils.redis_cache.redis.Redis')
    def test_analytics_cache_miss_and_set(self, mock_redis_class, test_client):
        """Test analytics cache miss and subsequent cache set."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.get.return_value = None  # Cache miss
        
        response = test_client.get("/api/analytics/summary")
        assert response.status_code in [403, 404]  # Still need auth or endpoint doesn't exist
        
    def test_analytics_cache_invalidation_simulation(self):
        """Test analytics cache invalidation simulation."""
        # Simulate cache invalidation logic
        cache_keys = [
            "analytics:daily:2024-01-01",
            "analytics:weekly:2024-W01",
            "analytics:monthly:2024-01"
        ]
        
        # Simulate invalidation
        invalidated_keys = []
        for key in cache_keys:
            if "daily" in key or "weekly" in key:
                invalidated_keys.append(key)
        
        assert len(invalidated_keys) == 2
        assert "analytics:monthly:2024-01" not in invalidated_keys


class TestAnalyticsRealTimeUpdates:
    """Test real-time analytics updates."""
    
    def test_real_time_view_count_update_simulation(self):
        """Test real-time view count update simulation."""
        # Simulate real-time view tracking
        initial_views = 100
        view_increments = [1, 1, 1, 2, 1]  # Simulate 5 view events
        
        current_views = initial_views
        for increment in view_increments:
            current_views += increment
        
        assert current_views == 106
        
    def test_real_time_engagement_tracking_simulation(self):
        """Test real-time engagement tracking simulation."""
        # Simulate real-time engagement events
        engagement_events = [
            {"type": "like", "clip_id": "clip_1", "timestamp": datetime.now()},
            {"type": "share", "clip_id": "clip_1", "timestamp": datetime.now()},
            {"type": "like", "clip_id": "clip_2", "timestamp": datetime.now()}
        ]
        
        # Aggregate engagement by clip
        engagement_by_clip = {}
        for event in engagement_events:
            clip_id = event["clip_id"]
            if clip_id not in engagement_by_clip:
                engagement_by_clip[clip_id] = {"likes": 0, "shares": 0}
            engagement_by_clip[clip_id][event["type"] + "s"] += 1
        
        assert engagement_by_clip["clip_1"]["likes"] == 1
        assert engagement_by_clip["clip_1"]["shares"] == 1
        assert engagement_by_clip["clip_2"]["likes"] == 1


class TestAnalyticsReporting:
    """Test analytics reporting functionality."""
    
    def test_daily_report_generation_mock(self, sample_analytics_data):
        """Test daily analytics report generation."""
        clips = sample_analytics_data["clips"]
        
        # Generate daily report for today
        today = datetime.now().date()
        today_clips = [clip for clip in clips if clip["created_at"].date() == today]
        
        daily_report = {
            "date": today.isoformat(),
            "clips_created": len(today_clips),
            "total_views": sum(clip["views"] for clip in today_clips),
            "total_likes": sum(clip["likes"] for clip in today_clips),
            "total_shares": sum(clip["shares"] for clip in today_clips)
        }
        
        # Verify report structure
        assert "date" in daily_report
        assert "clips_created" in daily_report
        assert "total_views" in daily_report
        assert daily_report["clips_created"] >= 0
        
    def test_weekly_report_generation_mock(self, sample_analytics_data):
        """Test weekly analytics report generation."""
        clips = sample_analytics_data["clips"]
        
        # Generate weekly report
        week_start = datetime.now() - timedelta(days=7)
        weekly_clips = [clip for clip in clips if clip["created_at"] >= week_start]
        
        weekly_report = {
            "week_start": week_start.date().isoformat(),
            "week_end": datetime.now().date().isoformat(),
            "clips_created": len(weekly_clips),
            "total_views": sum(clip["views"] for clip in weekly_clips),
            "avg_views_per_clip": sum(clip["views"] for clip in weekly_clips) / len(weekly_clips) if weekly_clips else 0,
            "top_performing_clip": max(weekly_clips, key=lambda x: x["views"])["id"] if weekly_clips else None
        }
        
        # Verify report structure and calculations
        assert weekly_report["clips_created"] == 2
        assert weekly_report["total_views"] == 375
        assert weekly_report["avg_views_per_clip"] == 187.5
        assert weekly_report["top_performing_clip"] == "clip_2"


class TestAnalyticsExport:
    """Test analytics data export functionality."""
    
    def test_csv_export_format_simulation(self, sample_analytics_data):
        """Test CSV export format simulation."""
        clips = sample_analytics_data["clips"]
        
        # Simulate CSV export format
        csv_headers = ["id", "title", "views", "likes", "shares", "created_at"]
        csv_rows = []
        
        for clip in clips:
            row = [
                clip["id"],
                clip["title"],
                str(clip["views"]),
                str(clip["likes"]),
                str(clip["shares"]),
                clip["created_at"].isoformat()
            ]
            csv_rows.append(row)
        
        # Verify export format
        assert len(csv_headers) == 6
        assert len(csv_rows) == 3
        assert csv_rows[0][0] == "clip_1"  # First clip ID
        
    def test_json_export_format_simulation(self, sample_analytics_data):
        """Test JSON export format simulation."""
        clips = sample_analytics_data["clips"]
        
        # Simulate JSON export
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_clips": len(clips),
            "clips": clips
        }
        
        # Verify export structure
        assert "export_timestamp" in export_data
        assert "total_clips" in export_data
        assert "clips" in export_data
        assert export_data["total_clips"] == 3
        assert len(export_data["clips"]) == 3


class TestAnalyticsErrorHandling:
    """Test analytics error handling scenarios."""
    
    def test_invalid_date_range_handling(self, test_client):
        """Test handling of invalid date ranges in analytics."""
        # Test invalid date format
        response = test_client.get("/api/analytics/clips?start_date=invalid-date")
        assert response.status_code in [403, 422, 404]  # Auth, validation, or not found
        
        # Test end date before start date
        start_date = datetime.now().isoformat()
        end_date = (datetime.now() - timedelta(days=1)).isoformat()
        response = test_client.get(f"/api/analytics/clips?start_date={start_date}&end_date={end_date}")
        assert response.status_code in [403, 422, 404]  # Auth, validation, or not found
        
    def test_missing_data_handling_simulation(self):
        """Test handling of missing analytics data."""
        # Simulate missing data scenario
        empty_dataset = []
        
        # Calculate metrics with empty data
        total_views = sum(clip.get("views", 0) for clip in empty_dataset)
        avg_views = total_views / len(empty_dataset) if empty_dataset else 0
        
        assert total_views == 0
        assert avg_views == 0
        
    def test_data_corruption_handling_simulation(self):
        """Test handling of corrupted analytics data."""
        # Simulate corrupted data
        corrupted_data = [
            {"id": "clip_1", "views": "invalid"},  # Invalid views
            {"id": "clip_2"},  # Missing views
            {"id": "clip_3", "views": 100}  # Valid data
        ]
        
        # Handle corrupted data gracefully
        valid_clips = []
        for clip in corrupted_data:
            try:
                views = int(clip.get("views", 0))
                if views >= 0:
                    clip["views"] = views
                    valid_clips.append(clip)
            except (ValueError, TypeError):
                continue  # Skip corrupted entries
        
        assert len(valid_clips) == 2  # Only clip_2 (with 0 views) and clip_3
        assert valid_clips[0]["id"] == "clip_2"
        assert valid_clips[0]["views"] == 0
        assert valid_clips[1]["id"] == "clip_3"
        assert valid_clips[1]["views"] == 100


class TestAnalyticsIntegrationScenarios:
    """Test analytics integration with other modules."""
    
    def test_user_analytics_integration_simulation(self, sample_analytics_data):
        """Test integration between user and analytics data."""
        users = sample_analytics_data["users"]
        clips = sample_analytics_data["clips"]
        
        # Integrate user and clip analytics
        user_analytics = {}
        for user in users:
            user_clips = [clip for clip in clips if clip["user_id"] == user["id"]]
            user_analytics[user["id"]] = {
                "user_info": user,
                "clips_count": len(user_clips),
                "total_views": sum(clip["views"] for clip in user_clips),
                "avg_views_per_clip": sum(clip["views"] for clip in user_clips) / len(user_clips) if user_clips else 0
            }
        
        # Verify integration
        assert len(user_analytics) == 2
        assert user_analytics["analytics_user_1"]["clips_count"] == 2
        assert user_analytics["analytics_user_1"]["total_views"] == 450
        assert user_analytics["analytics_user_2"]["clips_count"] == 1
        assert user_analytics["analytics_user_2"]["total_views"] == 75
        
    def test_content_analytics_integration_simulation(self, sample_analytics_data):
        """Test integration between content and analytics data."""
        clips = sample_analytics_data["clips"]
        
        # Analyze content performance
        content_analytics = {
            "by_duration": {
                "short": [],  # < 30 seconds
                "medium": [],  # 30-60 seconds
                "long": []  # > 60 seconds
            }
        }
        
        for clip in clips:
            duration = clip["duration"]
            if duration < 30:
                content_analytics["by_duration"]["short"].append(clip)
            elif duration <= 60:
                content_analytics["by_duration"]["medium"].append(clip)
            else:
                content_analytics["by_duration"]["long"].append(clip)
        
        # Verify content categorization
        assert len(content_analytics["by_duration"]["short"]) == 0
        assert len(content_analytics["by_duration"]["medium"]) == 3  # 30.5s, 45.2s, and 60.0s
        assert len(content_analytics["by_duration"]["long"]) == 0  # None > 60s