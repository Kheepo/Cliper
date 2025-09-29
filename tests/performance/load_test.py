"""Load testing configuration using Locust for performance validation."""

import random
import json
import time
from typing import Dict, Any, List
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseUser(HttpUser):
    """Base user class with common functionality."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_token = None
        self.user_id = None
        self.session_data = {}
    
    def on_start(self):
        """Called when a user starts."""
        self.login()
    
    def login(self):
        """Authenticate user and get token."""
        login_data = {
            "email": f"test_user_{random.randint(1, 10000)}@example.com",
            "password": "test_password_123"
        }
        
        with self.client.post("/api/auth/login", json=login_data, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.user_id = data.get("user_id")
                self.client.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                response.success()
            else:
                response.failure(f"Login failed: {response.status_code}")
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

class WebsiteUser(BaseUser):
    """Simulates regular website users."""
    
    wait_time = between(1, 3)
    weight = 3
    
    @task(10)
    def view_homepage(self):
        """View the homepage."""
        self.client.get("/")
    
    @task(8)
    def view_dashboard(self):
        """View user dashboard."""
        self.client.get("/api/dashboard", headers=self.get_headers())
    
    @task(6)
    def search_videos(self):
        """Search for videos."""
        search_terms = ["tutorial", "demo", "presentation", "meeting", "webinar"]
        query = random.choice(search_terms)
        
        self.client.get(
            f"/api/videos/search?q={query}&limit=20",
            headers=self.get_headers()
        )
    
    @task(5)
    def view_video_list(self):
        """View list of videos."""
        page = random.randint(1, 5)
        self.client.get(
            f"/api/videos?page={page}&limit=20",
            headers=self.get_headers()
        )
    
    @task(4)
    def view_video_details(self):
        """View specific video details."""
        video_id = f"video_{random.randint(1, 1000)}"
        self.client.get(
            f"/api/videos/{video_id}",
            headers=self.get_headers()
        )
    
    @task(3)
    def view_profile(self):
        """View user profile."""
        self.client.get("/api/profile", headers=self.get_headers())
    
    @task(2)
    def update_profile(self):
        """Update user profile."""
        profile_data = {
            "name": f"Test User {random.randint(1, 1000)}",
            "bio": "Updated bio from load test",
            "preferences": {
                "theme": random.choice(["light", "dark"]),
                "notifications": random.choice([True, False])
            }
        }
        
        self.client.put(
            "/api/profile",
            json=profile_data,
            headers=self.get_headers()
        )

class VideoProcessingUser(BaseUser):
    """Simulates users uploading and processing videos."""
    
    wait_time = between(2, 8)
    weight = 1
    
    @task(5)
    def upload_video(self):
        """Simulate video upload."""
        # Simulate file upload metadata
        upload_data = {
            "filename": f"test_video_{random.randint(1, 1000)}.mp4",
            "size": random.randint(1000000, 100000000),  # 1MB to 100MB
            "duration": random.randint(30, 3600),  # 30 seconds to 1 hour
            "format": "mp4",
            "title": f"Test Video {random.randint(1, 1000)}",
            "description": "Test video uploaded during load testing"
        }
        
        with self.client.post(
            "/api/videos/upload",
            json=upload_data,
            headers=self.get_headers(),
            catch_response=True
        ) as response:
            if response.status_code in [200, 201, 202]:
                response.success()
                # Store video ID for later operations
                if response.status_code in [200, 201]:
                    data = response.json()
                    video_id = data.get("video_id")
                    if video_id:
                        self.session_data["last_video_id"] = video_id
            else:
                response.failure(f"Upload failed: {response.status_code}")
    
    @task(3)
    def check_processing_status(self):
        """Check video processing status."""
        video_id = self.session_data.get("last_video_id", f"video_{random.randint(1, 100)}")
        
        self.client.get(
            f"/api/videos/{video_id}/status",
            headers=self.get_headers()
        )
    
    @task(2)
    def start_ai_analysis(self):
        """Start AI analysis on a video."""
        video_id = self.session_data.get("last_video_id", f"video_{random.randint(1, 100)}")
        
        analysis_data = {
            "analysis_type": random.choice(["transcription", "summary", "sentiment", "topics"]),
            "options": {
                "language": "en",
                "confidence_threshold": 0.8
            }
        }
        
        self.client.post(
            f"/api/videos/{video_id}/analyze",
            json=analysis_data,
            headers=self.get_headers()
        )
    
    @task(2)
    def download_results(self):
        """Download analysis results."""
        video_id = self.session_data.get("last_video_id", f"video_{random.randint(1, 100)}")
        
        self.client.get(
            f"/api/videos/{video_id}/results",
            headers=self.get_headers()
        )

class APIUser(BaseUser):
    """Simulates API-only users."""
    
    wait_time = between(0.5, 2)
    weight = 2
    
    @task(10)
    def health_check(self):
        """Check API health."""
        self.client.get("/api/health")
    
    @task(8)
    def get_metrics(self):
        """Get system metrics."""
        self.client.get("/api/metrics", headers=self.get_headers())
    
    @task(6)
    def list_videos_api(self):
        """List videos via API."""
        params = {
            "limit": random.randint(10, 50),
            "offset": random.randint(0, 100),
            "sort": random.choice(["created_at", "title", "duration"])
        }
        
        self.client.get(
            "/api/v1/videos",
            params=params,
            headers=self.get_headers()
        )
    
    @task(5)
    def create_video_metadata(self):
        """Create video metadata via API."""
        metadata = {
            "title": f"API Video {random.randint(1, 1000)}",
            "description": "Video created via API during load testing",
            "tags": ["test", "api", "load-test"],
            "category": random.choice(["education", "business", "entertainment"]),
            "privacy": random.choice(["public", "private", "unlisted"])
        }
        
        self.client.post(
            "/api/v1/videos",
            json=metadata,
            headers=self.get_headers()
        )
    
    @task(4)
    def update_video_metadata(self):
        """Update video metadata via API."""
        video_id = f"video_{random.randint(1, 100)}"
        
        update_data = {
            "title": f"Updated API Video {random.randint(1, 1000)}",
            "tags": ["updated", "api", "test"]
        }
        
        self.client.patch(
            f"/api/v1/videos/{video_id}",
            json=update_data,
            headers=self.get_headers()
        )
    
    @task(3)
    def delete_video(self):
        """Delete video via API."""
        video_id = f"video_{random.randint(1, 100)}"
        
        self.client.delete(
            f"/api/v1/videos/{video_id}",
            headers=self.get_headers()
        )

class AdminUser(BaseUser):
    """Simulates admin users with elevated permissions."""
    
    wait_time = between(3, 10)
    weight = 1
    
    def login(self):
        """Admin login with special credentials."""
        login_data = {
            "email": "admin@example.com",
            "password": "admin_password_123"
        }
        
        with self.client.post("/api/auth/admin/login", json=login_data, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.user_id = data.get("user_id")
                self.client.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                response.success()
            else:
                response.failure(f"Admin login failed: {response.status_code}")
    
    @task(5)
    def view_admin_dashboard(self):
        """View admin dashboard."""
        self.client.get("/api/admin/dashboard", headers=self.get_headers())
    
    @task(4)
    def view_system_stats(self):
        """View system statistics."""
        self.client.get("/api/admin/stats", headers=self.get_headers())
    
    @task(3)
    def manage_users(self):
        """Manage users."""
        self.client.get("/api/admin/users", headers=self.get_headers())
    
    @task(2)
    def view_logs(self):
        """View system logs."""
        params = {
            "level": random.choice(["INFO", "WARNING", "ERROR"]),
            "limit": 100
        }
        
        self.client.get(
            "/api/admin/logs",
            params=params,
            headers=self.get_headers()
        )
    
    @task(1)
    def system_maintenance(self):
        """Perform system maintenance tasks."""
        maintenance_data = {
            "action": random.choice(["cleanup", "optimize", "backup"]),
            "target": random.choice(["database", "cache", "storage"])
        }
        
        self.client.post(
            "/api/admin/maintenance",
            json=maintenance_data,
            headers=self.get_headers()
        )

# Event handlers for custom metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Custom request event handler."""
    if exception:
        logger.error(f"Request failed: {name} - {exception}")
    elif response_time > 5000:  # Log slow requests (>5s)
        logger.warning(f"Slow request: {name} - {response_time}ms")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    logger.info(f"Load test started at {datetime.now()}")
    logger.info(f"Target host: {environment.host}")
    
    if isinstance(environment.runner, MasterRunner):
        logger.info("Running in master mode")
    elif isinstance(environment.runner, WorkerRunner):
        logger.info("Running in worker mode")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    logger.info(f"Load test stopped at {datetime.now()}")
    
    # Generate performance report
    stats = environment.runner.stats
    
    report = {
        "total_requests": stats.total.num_requests,
        "total_failures": stats.total.num_failures,
        "average_response_time": stats.total.avg_response_time,
        "min_response_time": stats.total.min_response_time,
        "max_response_time": stats.total.max_response_time,
        "requests_per_second": stats.total.current_rps,
        "failure_rate": stats.total.fail_ratio
    }
    
    logger.info(f"Performance Report: {json.dumps(report, indent=2)}")
    
    # Save report to file
    report_file = f"load_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Report saved to {report_file}")

# Custom load test scenarios
class StressTestUser(BaseUser):
    """High-intensity stress testing user."""
    
    wait_time = between(0.1, 0.5)
    weight = 1
    
    @task
    def rapid_requests(self):
        """Make rapid requests to stress test the system."""
        endpoints = [
            "/api/health",
            "/api/metrics",
            "/api/videos",
            "/api/dashboard"
        ]
        
        endpoint = random.choice(endpoints)
        self.client.get(endpoint, headers=self.get_headers())

class SpikeTestUser(BaseUser):
    """Simulates traffic spikes."""
    
    wait_time = between(0.1, 1)
    weight = 1
    
    @task
    def spike_traffic(self):
        """Generate spike traffic patterns."""
        # Simulate burst of requests
        for _ in range(random.randint(1, 5)):
            self.client.get("/api/health")
            time.sleep(0.1)

# Configuration for different test scenarios
TEST_SCENARIOS = {
    "normal_load": {
        "users": [WebsiteUser, APIUser],
        "spawn_rate": 2,
        "max_users": 50
    },
    "high_load": {
        "users": [WebsiteUser, APIUser, VideoProcessingUser],
        "spawn_rate": 5,
        "max_users": 200
    },
    "stress_test": {
        "users": [StressTestUser, WebsiteUser, APIUser],
        "spawn_rate": 10,
        "max_users": 500
    },
    "spike_test": {
        "users": [SpikeTestUser, WebsiteUser],
        "spawn_rate": 20,
        "max_users": 100
    }
}

if __name__ == "__main__":
    # This allows running specific scenarios
    scenario = os.getenv("LOAD_TEST_SCENARIO", "normal_load")
    logger.info(f"Running load test scenario: {scenario}")