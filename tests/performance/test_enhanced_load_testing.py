import pytest
import asyncio
import time
import random
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import psutil
import statistics
from typing import List, Dict, Any

from api.main import app
from api.models.user import User
from api.models.video import Video, VideoStatus
from api.models.clip import GeneratedClip, ClipStatus
from api.core.database import get_db


class LoadTestMetrics:
    """Collect and analyze load test metrics."""
    
    def __init__(self):
        self.response_times = []
        self.success_count = 0
        self.error_count = 0
        self.start_time = None
        self.end_time = None
        self.memory_usage = []
        self.cpu_usage = []
        self.concurrent_requests = 0
        self.max_concurrent = 0
        
    def start_test(self):
        """Start metrics collection."""
        self.start_time = time.time()
        
    def end_test(self):
        """End metrics collection."""
        self.end_time = time.time()
        
    def record_request(self, response_time: float, success: bool):
        """Record individual request metrics."""
        self.response_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            
    def record_system_metrics(self):
        """Record system resource usage."""
        self.memory_usage.append(psutil.virtual_memory().percent)
        self.cpu_usage.append(psutil.cpu_percent())
        
    def increment_concurrent(self):
        """Track concurrent request count."""
        self.concurrent_requests += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent_requests)
        
    def decrement_concurrent(self):
        """Decrease concurrent request count."""
        self.concurrent_requests = max(0, self.concurrent_requests - 1)
        
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary statistics."""
        total_time = self.end_time - self.start_time if self.end_time else 0
        total_requests = self.success_count + self.error_count
        
        return {
            "total_requests": total_requests,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate": (self.success_count / total_requests * 100) if total_requests > 0 else 0,
            "total_time": total_time,
            "requests_per_second": total_requests / total_time if total_time > 0 else 0,
            "avg_response_time": statistics.mean(self.response_times) if self.response_times else 0,
            "median_response_time": statistics.median(self.response_times) if self.response_times else 0,
            "p95_response_time": self._percentile(self.response_times, 95) if self.response_times else 0,
            "p99_response_time": self._percentile(self.response_times, 99) if self.response_times else 0,
            "max_concurrent_requests": self.max_concurrent,
            "avg_memory_usage": statistics.mean(self.memory_usage) if self.memory_usage else 0,
            "max_memory_usage": max(self.memory_usage) if self.memory_usage else 0,
            "avg_cpu_usage": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
            "max_cpu_usage": max(self.cpu_usage) if self.cpu_usage else 0
        }
        
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


class EnhancedLoadTester:
    """Enhanced load testing for clip generation with realistic scenarios."""
    
    def __init__(self):
        self.client = TestClient(app)
        self.metrics = LoadTestMetrics()
        self.test_users = self._create_test_users()
        self.test_videos = self._create_test_videos()
        
    def _create_test_users(self) -> List[User]:
        """Create test users with different subscription tiers."""
        users = []
        
        # Free tier users (limited)
        for i in range(20):
            user = MagicMock(spec=User)
            user.id = f"free_user_{i}"
            user.subscription_tier = "free"
            user.credits = random.randint(1, 10)
            user.monthly_clip_limit = 10
            user.clips_generated_this_month = random.randint(0, 8)
            users.append(user)
            
        # Premium users (moderate limits)
        for i in range(15):
            user = MagicMock(spec=User)
            user.id = f"premium_user_{i}"
            user.subscription_tier = "premium"
            user.credits = random.randint(50, 200)
            user.monthly_clip_limit = 100
            user.clips_generated_this_month = random.randint(0, 80)
            users.append(user)
            
        # Enterprise users (high limits)
        for i in range(5):
            user = MagicMock(spec=User)
            user.id = f"enterprise_user_{i}"
            user.subscription_tier = "enterprise"
            user.credits = random.randint(500, 1000)
            user.monthly_clip_limit = 1000
            user.clips_generated_this_month = random.randint(0, 500)
            users.append(user)
            
        return users
        
    def _create_test_videos(self) -> List[Video]:
        """Create test videos with varying characteristics."""
        videos = []
        
        for i in range(100):
            video = MagicMock(spec=Video)
            video.id = f"test_video_{i}"
            video.user_id = random.choice(self.test_users).id
            video.title = f"Test Video {i}"
            video.duration = random.randint(60, 3600)  # 1 minute to 1 hour
            video.file_size = random.randint(10_000_000, 500_000_000)  # 10MB to 500MB
            video.status = VideoStatus.PROCESSED
            video.created_at = datetime.utcnow() - timedelta(days=random.randint(0, 30))
            videos.append(video)
            
        return videos
        
    def _create_realistic_clip_request(self, user: User, video: Video) -> Dict[str, Any]:
        """Create realistic clip generation request based on user tier and video."""
        platforms = ["youtube", "tiktok", "instagram", "twitter"]
        content_types = ["educational", "entertainment", "promotional", "tutorial"]
        
        # Adjust request complexity based on subscription tier
        if user.subscription_tier == "free":
            max_clips = random.randint(1, 2)
            customizations = False
        elif user.subscription_tier == "premium":
            max_clips = random.randint(2, 5)
            customizations = random.choice([True, False])
        else:  # enterprise
            max_clips = random.randint(3, 10)
            customizations = True
            
        request = {
            "video_id": video.id,
            "platform": random.choice(platforms),
            "max_clips": max_clips,
            "min_duration": random.randint(15, 30),
            "max_duration": random.randint(60, min(120, video.duration)),
            "content_type": random.choice(content_types),
            "target_audience": random.choice(["general", "teens", "adults", "professionals"])
        }
        
        if customizations:
            request.update({
                "add_captions": random.choice([True, False]),
                "add_music": random.choice([True, False]),
                "color_grading": random.choice(["natural", "vibrant", "cinematic"]),
                "aspect_ratio": "9:16" if request["platform"] in ["tiktok", "instagram"] else "16:9"
            })
            
        return request
        
    def _simulate_clip_generation(self, user: User, video: Video) -> Dict[str, Any]:
        """Simulate clip generation request with realistic timing."""
        start_time = time.time()
        self.metrics.increment_concurrent()
        
        try:
            # Create request
            clip_request = self._create_realistic_clip_request(user, video)
            
            # Simulate processing time based on complexity
            processing_time = self._calculate_processing_time(clip_request, video)
            
            # Mock the actual API call
            with patch('api.services.user_service.get_user_by_id', return_value=user), \
                 patch('api.services.video_service.get_video_by_id', return_value=video), \
                 patch('api.services.video_processor.VideoProcessor.find_best_segments') as mock_segments, \
                 patch('api.services.clip_service.create_clip') as mock_create:
                
                # Mock segment finding with realistic delay
                mock_segments.return_value = self._generate_mock_segments(clip_request["max_clips"])
                
                # Mock clip creation
                created_clips = []
                for i in range(clip_request["max_clips"]):
                    clip = MagicMock(spec=GeneratedClip)
                    clip.id = f"load_test_clip_{user.id}_{video.id}_{i}"
                    clip.status = ClipStatus.PROCESSING
                    created_clips.append(clip)
                    
                mock_create.side_effect = created_clips
                
                # Simulate API call
                response = self.client.post(
                    "/api/clips/generate",
                    json=clip_request,
                    headers={"Authorization": f"Bearer {user.id}_token"}
                )
                
                # Simulate processing delay
                time.sleep(processing_time / 1000)  # Convert to seconds
                
                success = response.status_code in [200, 202]
                response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                self.metrics.record_request(response_time, success)
                
                return {
                    "success": success,
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "clips_requested": clip_request["max_clips"],
                    "user_tier": user.subscription_tier,
                    "video_duration": video.duration
                }
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.metrics.record_request(response_time, False)
            return {
                "success": False,
                "response_time": response_time,
                "error": str(e)
            }
        finally:
            self.metrics.decrement_concurrent()
            
    def _calculate_processing_time(self, request: Dict[str, Any], video: Video) -> float:
        """Calculate realistic processing time based on request complexity."""
        base_time = 100  # Base 100ms
        
        # Factor in video duration
        duration_factor = min(video.duration / 300, 5)  # Cap at 5x for very long videos
        
        # Factor in number of clips
        clips_factor = request["max_clips"] * 0.5
        
        # Factor in customizations
        customization_factor = 1
        if request.get("add_captions"):
            customization_factor += 0.3
        if request.get("add_music"):
            customization_factor += 0.2
        if request.get("color_grading"):
            customization_factor += 0.1
            
        total_time = base_time * duration_factor * clips_factor * customization_factor
        
        # Add some randomness
        return total_time * random.uniform(0.8, 1.2)
        
    def _generate_mock_segments(self, count: int) -> List[Dict[str, Any]]:
        """Generate mock video segments for testing."""
        segments = []
        for i in range(count):
            start_time = random.uniform(0, 200)
            duration = random.uniform(30, 90)
            segments.append({
                "start_time": start_time,
                "end_time": start_time + duration,
                "score": random.uniform(0.7, 0.95),
                "reason": f"Mock segment {i + 1}",
                "tags": ["test", "load"]
            })
        return segments
        
    def run_concurrent_load_test(self, concurrent_users: int, duration_seconds: int) -> Dict[str, Any]:
        """Run concurrent load test with specified parameters."""
        print(f"Starting load test: {concurrent_users} concurrent users for {duration_seconds} seconds")
        
        self.metrics.start_test()
        results = []
        
        # System monitoring thread
        def monitor_system():
            while time.time() - self.metrics.start_time < duration_seconds:
                self.metrics.record_system_metrics()
                time.sleep(1)
                
        monitor_thread = threading.Thread(target=monitor_system)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Run concurrent requests
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = []
            
            end_time = time.time() + duration_seconds
            
            while time.time() < end_time:
                # Submit requests up to concurrent limit
                while len(futures) < concurrent_users and time.time() < end_time:
                    user = random.choice(self.test_users)
                    video = random.choice([v for v in self.test_videos if v.user_id == user.id] or self.test_videos[:5])
                    
                    future = executor.submit(self._simulate_clip_generation, user, video)
                    futures.append(future)
                    
                # Process completed requests
                completed_futures = []
                for future in futures:
                    if future.done():
                        try:
                            result = future.result()
                            results.append(result)
                        except Exception as e:
                            results.append({"success": False, "error": str(e)})
                        completed_futures.append(future)
                        
                # Remove completed futures
                for future in completed_futures:
                    futures.remove(future)
                    
                time.sleep(0.1)  # Small delay to prevent tight loop
                
            # Wait for remaining requests to complete
            for future in as_completed(futures, timeout=30):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({"success": False, "error": str(e)})
                    
        self.metrics.end_test()
        
        return {
            "test_config": {
                "concurrent_users": concurrent_users,
                "duration_seconds": duration_seconds,
                "total_test_users": len(self.test_users),
                "total_test_videos": len(self.test_videos)
            },
            "metrics": self.metrics.get_summary(),
            "detailed_results": results
        }


class TestEnhancedLoadTesting:
    """Enhanced load testing scenarios for clip generation."""
    
    def setup_method(self):
        """Setup load testing environment."""
        self.load_tester = EnhancedLoadTester()
        
    def test_light_load_scenario(self):
        """Test light load scenario - typical off-peak usage."""
        results = self.load_tester.run_concurrent_load_test(
            concurrent_users=5,
            duration_seconds=30
        )
        
        metrics = results["metrics"]
        
        # Assertions for light load
        assert metrics["success_rate"] >= 95.0, f"Success rate too low: {metrics['success_rate']}%"
        assert metrics["avg_response_time"] <= 2000, f"Average response time too high: {metrics['avg_response_time']}ms"
        assert metrics["p95_response_time"] <= 5000, f"P95 response time too high: {metrics['p95_response_time']}ms"
        assert metrics["max_memory_usage"] <= 80, f"Memory usage too high: {metrics['max_memory_usage']}%"
        
        print(f"Light load test completed: {metrics['total_requests']} requests, {metrics['success_rate']:.1f}% success rate")
        
    def test_moderate_load_scenario(self):
        """Test moderate load scenario - typical peak usage."""
        results = self.load_tester.run_concurrent_load_test(
            concurrent_users=15,
            duration_seconds=60
        )
        
        metrics = results["metrics"]
        
        # Assertions for moderate load
        assert metrics["success_rate"] >= 90.0, f"Success rate too low: {metrics['success_rate']}%"
        assert metrics["avg_response_time"] <= 3000, f"Average response time too high: {metrics['avg_response_time']}ms"
        assert metrics["p95_response_time"] <= 8000, f"P95 response time too high: {metrics['p95_response_time']}ms"
        assert metrics["requests_per_second"] >= 5, f"Throughput too low: {metrics['requests_per_second']} RPS"
        
        print(f"Moderate load test completed: {metrics['total_requests']} requests, {metrics['success_rate']:.1f}% success rate")
        
    def test_heavy_load_scenario(self):
        """Test heavy load scenario - stress testing."""
        results = self.load_tester.run_concurrent_load_test(
            concurrent_users=30,
            duration_seconds=90
        )
        
        metrics = results["metrics"]
        
        # Assertions for heavy load (more lenient)
        assert metrics["success_rate"] >= 80.0, f"Success rate too low: {metrics['success_rate']}%"
        assert metrics["avg_response_time"] <= 5000, f"Average response time too high: {metrics['avg_response_time']}ms"
        assert metrics["p99_response_time"] <= 15000, f"P99 response time too high: {metrics['p99_response_time']}ms"
        
        print(f"Heavy load test completed: {metrics['total_requests']} requests, {metrics['success_rate']:.1f}% success rate")
        
    def test_burst_load_scenario(self):
        """Test burst load scenario - sudden traffic spikes."""
        # Start with low load
        print("Starting burst test with low baseline load...")
        baseline_results = self.load_tester.run_concurrent_load_test(
            concurrent_users=5,
            duration_seconds=20
        )
        
        # Burst to high load
        print("Bursting to high load...")
        burst_results = self.load_tester.run_concurrent_load_test(
            concurrent_users=25,
            duration_seconds=30
        )
        
        # Return to baseline
        print("Returning to baseline load...")
        recovery_results = self.load_tester.run_concurrent_load_test(
            concurrent_users=5,
            duration_seconds=20
        )
        
        # Analyze burst impact
        baseline_metrics = baseline_results["metrics"]
        burst_metrics = burst_results["metrics"]
        recovery_metrics = recovery_results["metrics"]
        
        # System should handle burst reasonably
        assert burst_metrics["success_rate"] >= 70.0, f"Burst success rate too low: {burst_metrics['success_rate']}%"
        
        # System should recover after burst
        assert recovery_metrics["success_rate"] >= baseline_metrics["success_rate"] - 5, "System did not recover properly after burst"
        
        print(f"Burst test completed - Baseline: {baseline_metrics['success_rate']:.1f}%, Burst: {burst_metrics['success_rate']:.1f}%, Recovery: {recovery_metrics['success_rate']:.1f}%")
        
    def test_subscription_tier_load_distribution(self):
        """Test load distribution across different subscription tiers."""
        results = self.load_tester.run_concurrent_load_test(
            concurrent_users=20,
            duration_seconds=60
        )
        
        # Analyze results by subscription tier
        tier_results = {"free": [], "premium": [], "enterprise": []}
        
        for result in results["detailed_results"]:
            if "user_tier" in result:
                tier_results[result["user_tier"]].append(result)
                
        # Verify each tier performed reasonably
        for tier, tier_data in tier_results.items():
            if tier_data:
                success_rate = sum(1 for r in tier_data if r.get("success", False)) / len(tier_data) * 100
                avg_response_time = sum(r.get("response_time", 0) for r in tier_data) / len(tier_data)
                
                print(f"{tier.capitalize()} tier: {len(tier_data)} requests, {success_rate:.1f}% success, {avg_response_time:.1f}ms avg response")
                
                # Different expectations for different tiers
                if tier == "enterprise":
                    assert success_rate >= 95.0, f"{tier} tier success rate too low: {success_rate}%"
                elif tier == "premium":
                    assert success_rate >= 90.0, f"{tier} tier success rate too low: {success_rate}%"
                else:  # free
                    assert success_rate >= 80.0, f"{tier} tier success rate too low: {success_rate}%"
                    
    def test_long_duration_stability(self):
        """Test system stability over extended period."""
        results = self.load_tester.run_concurrent_load_test(
            concurrent_users=10,
            duration_seconds=300  # 5 minutes
        )
        
        metrics = results["metrics"]
        
        # System should remain stable over time
        assert metrics["success_rate"] >= 90.0, f"Long-term success rate too low: {metrics['success_rate']}%"
        assert metrics["max_memory_usage"] <= 85, f"Memory usage grew too high: {metrics['max_memory_usage']}%"
        
        # Check for memory leaks (simplified)
        memory_readings = self.load_tester.metrics.memory_usage
        if len(memory_readings) >= 10:
            early_avg = sum(memory_readings[:10]) / 10
            late_avg = sum(memory_readings[-10:]) / 10
            memory_growth = late_avg - early_avg
            
            assert memory_growth <= 10, f"Potential memory leak detected: {memory_growth}% growth"
            
        print(f"Stability test completed: {metrics['total_requests']} requests over {metrics['total_time']:.1f}s")
        
    def test_error_rate_under_load(self):
        """Test error handling and recovery under load."""
        # Inject some failures to test error handling
        with patch('api.services.video_processor.VideoProcessor.find_best_segments') as mock_segments:
            # Make 20% of requests fail
            def failing_segments(*args, **kwargs):
                if random.random() < 0.2:
                    raise Exception("Simulated processing failure")
                return self.load_tester._generate_mock_segments(3)
                
            mock_segments.side_effect = failing_segments
            
            results = self.load_tester.run_concurrent_load_test(
                concurrent_users=15,
                duration_seconds=45
            )
            
            metrics = results["metrics"]
            
            # Even with injected failures, system should handle gracefully
            assert metrics["success_rate"] >= 75.0, f"Success rate with failures too low: {metrics['success_rate']}%"
            assert metrics["error_count"] > 0, "No errors recorded despite injected failures"
            
            print(f"Error handling test: {metrics['error_count']} errors out of {metrics['total_requests']} requests")