from locust import HttpUser, task, between
import json
import random
import string
from typing import Dict, Any


class ClipGenerationUser(HttpUser):
    """Load test user for clip generation API."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup user session."""
        self.api_key = "test-api-key"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.task_ids = []
    
    def generate_random_string(self, length: int = 10) -> str:
        """Generate random string for test data."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def create_test_clip_request(self) -> Dict[str, Any]:
        """Create test clip generation request."""
        platforms = ["youtube", "tiktok", "instagram", "twitter"]
        topics = ["technology", "business", "entertainment", "education", "sports"]
        
        return {
            "title": f"Test Clip {self.generate_random_string(8)}",
            "description": f"Test description for load testing {self.generate_random_string(20)}",
            "platform": random.choice(platforms),
            "topic": random.choice(topics),
            "duration": random.randint(15, 300),
            "style": random.choice(["professional", "casual", "energetic", "calm"]),
            "target_audience": random.choice(["general", "teens", "adults", "professionals"]),
            "requirements": {
                "include_captions": random.choice([True, False]),
                "include_music": random.choice([True, False]),
                "include_effects": random.choice([True, False]),
                "quality": random.choice(["720p", "1080p", "4k"])
            }
        }
    
    @task(3)
    def generate_clip(self):
        """Test clip generation endpoint."""
        clip_data = self.create_test_clip_request()
        
        with self.client.post(
            "/api/v1/clips/generate",
            json=clip_data,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 202:
                result = response.json()
                task_id = result.get("task_id")
                if task_id:
                    self.task_ids.append(task_id)
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def check_task_status(self):
        """Test task status endpoint."""
        if not self.task_ids:
            return
        
        task_id = random.choice(self.task_ids)
        
        with self.client.get(
            f"/api/v1/clips/status/{task_id}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()
                status = result.get("status")
                if status in ["pending", "processing", "completed", "failed"]:
                    response.success()
                else:
                    response.failure(f"Invalid status: {status}")
            elif response.status_code == 404:
                # Remove invalid task ID
                self.task_ids.remove(task_id)
                response.failure("Task not found")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def list_clips(self):
        """Test clip listing endpoint."""
        params = {
            "limit": random.randint(5, 20),
            "offset": random.randint(0, 50),
            "status": random.choice(["all", "completed", "processing", "failed"])
        }
        
        with self.client.get(
            "/api/v1/clips",
            params=params,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if "clips" in result and "total" in result:
                    response.success()
                else:
                    response.failure("Invalid response format")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def get_health_status(self):
        """Test health endpoint."""
        with self.client.get(
            "/health",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "healthy":
                    response.success()
                else:
                    response.failure(f"Unhealthy status: {result.get('status')}")
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(1)
    def get_metrics(self):
        """Test metrics endpoint."""
        with self.client.get(
            "/api/v1/monitoring/metrics",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if "metrics" in result:
                    response.success()
                else:
                    response.failure("Invalid metrics format")
            else:
                response.failure(f"Metrics failed: {response.status_code}")
    
    @task(1)
    def cancel_task(self):
        """Test task cancellation."""
        if not self.task_ids:
            return
        
        # Only cancel some tasks to avoid cancelling all
        if random.random() < 0.1:  # 10% chance
            task_id = random.choice(self.task_ids)
            
            with self.client.post(
                f"/api/v1/clips/cancel/{task_id}",
                headers=self.headers,
                catch_response=True
            ) as response:
                if response.status_code in [200, 404]:
                    response.success()
                    if task_id in self.task_ids:
                        self.task_ids.remove(task_id)
                else:
                    response.failure(f"Cancel failed: {response.status_code}")


class AdminUser(HttpUser):
    """Admin user for testing admin endpoints."""
    
    wait_time = between(2, 5)
    weight = 1  # Lower weight than regular users
    
    def on_start(self):
        """Setup admin session."""
        self.api_key = "admin-api-key"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    @task(2)
    def get_system_metrics(self):
        """Test system metrics endpoint."""
        with self.client.get(
            "/api/v1/monitoring/system",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if "cpu_usage" in result and "memory_usage" in result:
                    response.success()
                else:
                    response.failure("Invalid system metrics")
            else:
                response.failure(f"System metrics failed: {response.status_code}")
    
    @task(1)
    def get_alerts(self):
        """Test alerts endpoint."""
        with self.client.get(
            "/api/v1/monitoring/alerts",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if "alerts" in result:
                    response.success()
                else:
                    response.failure("Invalid alerts format")
            else:
                response.failure(f"Alerts failed: {response.status_code}")
    
    @task(1)
    def get_dashboard_data(self):
        """Test dashboard data endpoint."""
        with self.client.get(
            "/api/v1/monitoring/dashboard/system",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if "widgets" in result:
                    response.success()
                else:
                    response.failure("Invalid dashboard format")
            else:
                response.failure(f"Dashboard failed: {response.status_code}")


class WebSocketUser(HttpUser):
    """User for testing WebSocket connections."""
    
    wait_time = between(5, 10)
    weight = 1  # Lower weight
    
    def on_start(self):
        """Setup WebSocket connection."""
        self.api_key = "test-api-key"
    
    @task
    def websocket_connection(self):
        """Test WebSocket connection and messaging."""
        try:
            import websocket
            import threading
            import time
            
            def on_message(ws, message):
                data = json.loads(message)
                if data.get("type") in ["task_status", "task_completed", "task_failed"]:
                    print(f"Received: {data}")
            
            def on_error(ws, error):
                print(f"WebSocket error: {error}")
            
            def on_close(ws, close_status_code, close_msg):
                print("WebSocket closed")
            
            def on_open(ws):
                # Send authentication
                auth_msg = {
                    "type": "auth",
                    "token": self.api_key
                }
                ws.send(json.dumps(auth_msg))
                
                # Subscribe to updates
                subscribe_msg = {
                    "type": "subscribe",
                    "events": ["task_status", "task_completed", "task_failed"]
                }
                ws.send(json.dumps(subscribe_msg))
            
            ws_url = f"ws://{self.host.replace('http://', '').replace('https://', '')}/ws"
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # Run for 30 seconds
            def run_ws():
                ws.run_forever()
            
            ws_thread = threading.Thread(target=run_ws)
            ws_thread.daemon = True
            ws_thread.start()
            
            time.sleep(30)
            ws.close()
            
        except ImportError:
            print("websocket-client not installed, skipping WebSocket test")
        except Exception as e:
            print(f"WebSocket test failed: {e}")


class StressTestUser(HttpUser):
    """High-intensity stress test user."""
    
    wait_time = between(0.1, 0.5)  # Very short wait time
    weight = 2
    
    def on_start(self):
        """Setup stress test session."""
        self.api_key = "stress-test-key"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.request_count = 0
    
    @task(5)
    def rapid_fire_requests(self):
        """Send rapid requests to test system limits."""
        self.request_count += 1
        
        # Alternate between different endpoints
        endpoints = [
            ("/health", "GET", None),
            ("/api/v1/clips", "GET", {"limit": 5}),
            ("/api/v1/monitoring/metrics", "GET", None),
        ]
        
        endpoint, method, params = random.choice(endpoints)
        
        if method == "GET":
            with self.client.get(
                endpoint,
                params=params,
                headers=self.headers,
                catch_response=True
            ) as response:
                if response.status_code in [200, 429]:
                    response.success()
                else:
                    response.failure(f"Unexpected: {response.status_code}")
    
    @task(1)
    def memory_intensive_request(self):
        """Send requests that might consume more memory."""
        large_data = {
            "title": "Large Test Clip",
            "description": "A" * 1000,  # Large description
            "platform": "youtube",
            "topic": "technology",
            "duration": 300,
            "requirements": {
                "include_captions": True,
                "include_music": True,
                "include_effects": True,
                "quality": "4k",
                "custom_data": "B" * 500  # Additional large data
            }
        }
        
        with self.client.post(
            "/api/v1/clips/generate",
            json=large_data,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [202, 429, 413]:  # Include payload too large
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code}")