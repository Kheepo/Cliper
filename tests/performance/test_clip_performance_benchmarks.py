import pytest
import time
import asyncio
import psutil
import statistics
from typing import Dict, List, Any
from dataclasses import dataclass, field
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.main import app
from api.database import get_db
from api.models.video import Video
from api.models.clip import Clip
from api.models.user import User
from api.services.clip_generation import ClipGenerationService
from api.core.config import settings


@dataclass
class PerformanceBenchmark:
    """Performance benchmark thresholds and metrics."""
    max_response_time: float  # seconds
    max_memory_usage: float   # MB
    max_cpu_usage: float      # percentage
    min_throughput: float     # requests per second
    max_error_rate: float     # percentage
    

@dataclass
class PerformanceMetrics:
    """Collected performance metrics."""
    response_times: List[float] = field(default_factory=list)
    memory_usage: List[float] = field(default_factory=list)
    cpu_usage: List[float] = field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    start_time: float = 0
    end_time: float = 0
    
    @property
    def avg_response_time(self) -> float:
        return statistics.mean(self.response_times) if self.response_times else 0
    
    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[index]
    
    @property
    def p99_response_time(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        index = int(0.99 * len(sorted_times))
        return sorted_times[index]
    
    @property
    def max_memory_usage(self) -> float:
        return max(self.memory_usage) if self.memory_usage else 0
    
    @property
    def avg_cpu_usage(self) -> float:
        return statistics.mean(self.cpu_usage) if self.cpu_usage else 0
    
    @property
    def throughput(self) -> float:
        duration = self.end_time - self.start_time
        return (self.success_count + self.error_count) / duration if duration > 0 else 0
    
    @property
    def error_rate(self) -> float:
        total = self.success_count + self.error_count
        return (self.error_count / total * 100) if total > 0 else 0


class PerformanceMonitor:
    """Monitor system performance during tests."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.metrics = PerformanceMetrics()
        self.monitoring = False
    
    async def start_monitoring(self):
        """Start performance monitoring."""
        self.monitoring = True
        self.metrics.start_time = time.time()
        
        # Start background monitoring task
        asyncio.create_task(self._monitor_system())
    
    async def stop_monitoring(self):
        """Stop performance monitoring."""
        self.monitoring = False
        self.metrics.end_time = time.time()
    
    async def _monitor_system(self):
        """Monitor system resources in background."""
        while self.monitoring:
            try:
                # Memory usage in MB
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                self.metrics.memory_usage.append(memory_mb)
                
                # CPU usage percentage
                cpu_percent = self.process.cpu_percent()
                self.metrics.cpu_usage.append(cpu_percent)
                
                await asyncio.sleep(0.1)  # Monitor every 100ms
            except Exception:
                # Continue monitoring even if individual measurements fail
                pass
    
    def record_request(self, response_time: float, success: bool):
        """Record a request's performance metrics."""
        self.metrics.response_times.append(response_time)
        if success:
            self.metrics.success_count += 1
        else:
            self.metrics.error_count += 1


class TestClipPerformanceBenchmarks:
    """Performance benchmarking tests for clip generation."""
    
    # Performance benchmarks for different scenarios
    BENCHMARKS = {
        'single_clip': PerformanceBenchmark(
            max_response_time=5.0,
            max_memory_usage=500.0,
            max_cpu_usage=80.0,
            min_throughput=0.2,
            max_error_rate=1.0
        ),
        'concurrent_clips': PerformanceBenchmark(
            max_response_time=10.0,
            max_memory_usage=1000.0,
            max_cpu_usage=90.0,
            min_throughput=1.0,
            max_error_rate=5.0
        ),
        'bulk_processing': PerformanceBenchmark(
            max_response_time=30.0,
            max_memory_usage=2000.0,
            max_cpu_usage=95.0,
            min_throughput=5.0,
            max_error_rate=2.0
        ),
        'stress_test': PerformanceBenchmark(
            max_response_time=60.0,
            max_memory_usage=4000.0,
            max_cpu_usage=98.0,
            min_throughput=10.0,
            max_error_rate=10.0
        )
    }
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer valid_jwt_token"}
    
    @pytest.fixture
    def performance_monitor(self):
        return PerformanceMonitor()
    
    @pytest.fixture
    def mock_user(self, db_session):
        user = User(
            id="user123",
            email="test@example.com",
            credits=1000,
            subscription_tier="premium"
        )
        db_session.add(user)
        db_session.commit()
        return user
    
    @pytest.fixture
    def mock_videos(self, db_session, mock_user):
        videos = []
        for i in range(10):
            video = Video(
                id=f"video{i}",
                user_id=mock_user.id,
                filename=f"test_video_{i}.mp4",
                file_path=f"/storage/videos/test_video_{i}.mp4",
                duration=120.0,
                status="processed"
            )
            videos.append(video)
            db_session.add(video)
        db_session.commit()
        return videos
    
    def assert_benchmark_compliance(self, metrics: PerformanceMetrics, benchmark: PerformanceBenchmark, test_name: str):
        """Assert that metrics comply with benchmark thresholds."""
        print(f"\n=== Performance Benchmark Results for {test_name} ===")
        print(f"Average Response Time: {metrics.avg_response_time:.2f}s (max: {benchmark.max_response_time}s)")
        print(f"P95 Response Time: {metrics.p95_response_time:.2f}s")
        print(f"P99 Response Time: {metrics.p99_response_time:.2f}s")
        print(f"Max Memory Usage: {metrics.max_memory_usage:.2f}MB (max: {benchmark.max_memory_usage}MB)")
        print(f"Average CPU Usage: {metrics.avg_cpu_usage:.2f}% (max: {benchmark.max_cpu_usage}%)")
        print(f"Throughput: {metrics.throughput:.2f} req/s (min: {benchmark.min_throughput} req/s)")
        print(f"Error Rate: {metrics.error_rate:.2f}% (max: {benchmark.max_error_rate}%)")
        print(f"Total Requests: {metrics.success_count + metrics.error_count}")
        print(f"Successful Requests: {metrics.success_count}")
        print(f"Failed Requests: {metrics.error_count}")
        
        # Assert benchmark compliance
        assert metrics.avg_response_time <= benchmark.max_response_time, \
            f"Average response time {metrics.avg_response_time:.2f}s exceeds benchmark {benchmark.max_response_time}s"
        
        assert metrics.max_memory_usage <= benchmark.max_memory_usage, \
            f"Max memory usage {metrics.max_memory_usage:.2f}MB exceeds benchmark {benchmark.max_memory_usage}MB"
        
        assert metrics.avg_cpu_usage <= benchmark.max_cpu_usage, \
            f"Average CPU usage {metrics.avg_cpu_usage:.2f}% exceeds benchmark {benchmark.max_cpu_usage}%"
        
        assert metrics.throughput >= benchmark.min_throughput, \
            f"Throughput {metrics.throughput:.2f} req/s below benchmark {benchmark.min_throughput} req/s"
        
        assert metrics.error_rate <= benchmark.max_error_rate, \
            f"Error rate {metrics.error_rate:.2f}% exceeds benchmark {benchmark.max_error_rate}%"
    
    @pytest.mark.asyncio
    async def test_single_clip_generation_benchmark(self, client, auth_headers, mock_videos, performance_monitor):
        """Benchmark single clip generation performance."""
        await performance_monitor.start_monitoring()
        
        with patch('api.services.ffmpeg_service.FFmpegService.extract_clip') as mock_ffmpeg, \
             patch('api.services.storage_service.StorageService.upload_file') as mock_storage:
            
            mock_ffmpeg.return_value = "/tmp/clip.mp4"
            mock_storage.return_value = "https://storage.example.com/clips/clip.mp4"
            
            # Perform single clip generation
            start_time = time.time()
            response = client.post(
                f"/api/v1/videos/{mock_videos[0].id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                }
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            success = response.status_code == 201
            performance_monitor.record_request(response_time, success)
        
        await performance_monitor.stop_monitoring()
        
        # Assert benchmark compliance
        benchmark = self.BENCHMARKS['single_clip']
        self.assert_benchmark_compliance(performance_monitor.metrics, benchmark, "Single Clip Generation")
    
    @pytest.mark.asyncio
    async def test_concurrent_clip_generation_benchmark(self, client, auth_headers, mock_videos, performance_monitor):
        """Benchmark concurrent clip generation performance."""
        await performance_monitor.start_monitoring()
        
        with patch('api.services.ffmpeg_service.FFmpegService.extract_clip') as mock_ffmpeg, \
             patch('api.services.storage_service.StorageService.upload_file') as mock_storage:
            
            mock_ffmpeg.return_value = "/tmp/clip.mp4"
            mock_storage.return_value = "https://storage.example.com/clips/clip.mp4"
            
            # Simulate concurrent requests
            async def generate_clip(video_id: str):
                start_time = time.time()
                response = client.post(
                    f"/api/v1/videos/{video_id}/clips",
                    headers=auth_headers,
                    json={
                        "start_time": 10.0,
                        "duration": 30.0,
                        "platform": "youtube"
                    }
                )
                end_time = time.time()
                
                response_time = end_time - start_time
                success = response.status_code == 201
                performance_monitor.record_request(response_time, success)
                return response
            
            # Generate 5 concurrent clips
            tasks = [generate_clip(video.id) for video in mock_videos[:5]]
            await asyncio.gather(*tasks)
        
        await performance_monitor.stop_monitoring()
        
        # Assert benchmark compliance
        benchmark = self.BENCHMARKS['concurrent_clips']
        self.assert_benchmark_compliance(performance_monitor.metrics, benchmark, "Concurrent Clip Generation")
    
    @pytest.mark.asyncio
    async def test_bulk_processing_benchmark(self, client, auth_headers, mock_videos, performance_monitor):
        """Benchmark bulk clip processing performance."""
        await performance_monitor.start_monitoring()
        
        with patch('api.services.ffmpeg_service.FFmpegService.extract_clip') as mock_ffmpeg, \
             patch('api.services.storage_service.StorageService.upload_file') as mock_storage:
            
            mock_ffmpeg.return_value = "/tmp/clip.mp4"
            mock_storage.return_value = "https://storage.example.com/clips/clip.mp4"
            
            # Bulk clip generation request
            start_time = time.time()
            response = client.post(
                "/api/v1/clips/bulk",
                headers=auth_headers,
                json={
                    "clips": [
                        {
                            "video_id": video.id,
                            "start_time": 10.0,
                            "duration": 30.0,
                            "platform": "youtube"
                        } for video in mock_videos
                    ]
                }
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            success = response.status_code == 201
            performance_monitor.record_request(response_time, success)
        
        await performance_monitor.stop_monitoring()
        
        # Assert benchmark compliance
        benchmark = self.BENCHMARKS['bulk_processing']
        self.assert_benchmark_compliance(performance_monitor.metrics, benchmark, "Bulk Processing")
    
    @pytest.mark.asyncio
    async def test_stress_test_benchmark(self, client, auth_headers, mock_videos, performance_monitor):
        """Stress test benchmark with high load."""
        await performance_monitor.start_monitoring()
        
        with patch('api.services.ffmpeg_service.FFmpegService.extract_clip') as mock_ffmpeg, \
             patch('api.services.storage_service.StorageService.upload_file') as mock_storage:
            
            mock_ffmpeg.return_value = "/tmp/clip.mp4"
            mock_storage.return_value = "https://storage.example.com/clips/clip.mp4"
            
            # High-load stress test
            async def stress_request():
                start_time = time.time()
                try:
                    response = client.post(
                        f"/api/v1/videos/{mock_videos[0].id}/clips",
                        headers=auth_headers,
                        json={
                            "start_time": 10.0,
                            "duration": 30.0,
                            "platform": "youtube"
                        }
                    )
                    end_time = time.time()
                    response_time = end_time - start_time
                    success = response.status_code == 201
                except Exception:
                    end_time = time.time()
                    response_time = end_time - start_time
                    success = False
                
                performance_monitor.record_request(response_time, success)
            
            # Generate 50 rapid requests
            tasks = [stress_request() for _ in range(50)]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        await performance_monitor.stop_monitoring()
        
        # Assert benchmark compliance
        benchmark = self.BENCHMARKS['stress_test']
        self.assert_benchmark_compliance(performance_monitor.metrics, benchmark, "Stress Test")
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, client, auth_headers, mock_videos):
        """Test for memory leaks during extended operation."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        with patch('api.services.ffmpeg_service.FFmpegService.extract_clip') as mock_ffmpeg, \
             patch('api.services.storage_service.StorageService.upload_file') as mock_storage:
            
            mock_ffmpeg.return_value = "/tmp/clip.mp4"
            mock_storage.return_value = "https://storage.example.com/clips/clip.mp4"
            
            # Perform many operations to detect memory leaks
            for i in range(100):
                response = client.post(
                    f"/api/v1/videos/{mock_videos[i % len(mock_videos)].id}/clips",
                    headers=auth_headers,
                    json={
                        "start_time": 10.0,
                        "duration": 30.0,
                        "platform": "youtube"
                    }
                )
                
                # Check memory every 10 operations
                if i % 10 == 0:
                    current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    memory_increase = current_memory - initial_memory
                    
                    # Memory increase should be reasonable (less than 100MB per 10 operations)
                    assert memory_increase < 100, f"Potential memory leak detected: {memory_increase:.2f}MB increase"
    
    @pytest.mark.asyncio
    async def test_database_performance_benchmark(self, client, auth_headers, mock_videos, performance_monitor):
        """Benchmark database operations performance."""
        await performance_monitor.start_monitoring()
        
        # Test database query performance
        async def database_operation():
            start_time = time.time()
            
            # Simulate database-heavy operations
            response = client.get(
                f"/api/v1/videos/{mock_videos[0].id}/clips",
                headers=auth_headers
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            success = response.status_code == 200
            performance_monitor.record_request(response_time, success)
        
        # Perform multiple database operations
        tasks = [database_operation() for _ in range(20)]
        await asyncio.gather(*tasks)
        
        await performance_monitor.stop_monitoring()
        
        # Database operations should be fast (< 1 second average)
        assert performance_monitor.metrics.avg_response_time < 1.0, \
            f"Database operations too slow: {performance_monitor.metrics.avg_response_time:.2f}s average"
    
    @pytest.mark.asyncio
    async def test_api_rate_limiting_performance(self, client, auth_headers, mock_videos, performance_monitor):
        """Test API rate limiting performance impact."""
        await performance_monitor.start_monitoring()
        
        # Test rate limiting behavior
        async def rate_limited_request():
            start_time = time.time()
            
            response = client.post(
                f"/api/v1/videos/{mock_videos[0].id}/clips",
                headers=auth_headers,
                json={
                    "start_time": 10.0,
                    "duration": 30.0,
                    "platform": "youtube"
                }
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            success = response.status_code in [201, 429]  # Accept rate limit responses
            performance_monitor.record_request(response_time, success)
            
            return response.status_code
        
        # Send rapid requests to trigger rate limiting
        tasks = [rate_limited_request() for _ in range(30)]
        status_codes = await asyncio.gather(*tasks)
        
        await performance_monitor.stop_monitoring()
        
        # Verify rate limiting is working
        rate_limited_count = sum(1 for code in status_codes if code == 429)
        assert rate_limited_count > 0, "Rate limiting should be triggered with rapid requests"
        
        # Rate limiting should not significantly impact performance
        assert performance_monitor.metrics.avg_response_time < 2.0, \
            f"Rate limiting causing performance degradation: {performance_monitor.metrics.avg_response_time:.2f}s average"
    
    def test_performance_regression_detection(self):
        """Test for performance regression detection."""
        # This would typically compare against historical benchmarks
        # stored in a database or file system
        
        historical_benchmarks = {
            'avg_response_time': 2.5,
            'p95_response_time': 4.0,
            'max_memory_usage': 300.0,
            'avg_cpu_usage': 60.0
        }
        
        # Simulate current performance metrics
        current_metrics = {
            'avg_response_time': 2.8,  # 12% increase
            'p95_response_time': 4.2,  # 5% increase
            'max_memory_usage': 350.0,  # 16.7% increase
            'avg_cpu_usage': 65.0      # 8.3% increase
        }
        
        # Check for significant regressions (> 15% increase)
        for metric, current_value in current_metrics.items():
            historical_value = historical_benchmarks[metric]
            increase_percentage = ((current_value - historical_value) / historical_value) * 100
            
            if increase_percentage > 15:
                pytest.fail(f"Performance regression detected in {metric}: "
                          f"{increase_percentage:.1f}% increase from {historical_value} to {current_value}")
        
        print("\n=== Performance Regression Check Passed ===")
        for metric, current_value in current_metrics.items():
            historical_value = historical_benchmarks[metric]
            change = ((current_value - historical_value) / historical_value) * 100
            print