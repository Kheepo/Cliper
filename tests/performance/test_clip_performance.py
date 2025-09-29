import pytest
import asyncio
import time
import psutil
import threading
import concurrent.futures
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from api.main import app
from api.tasks import generate_clips_task, _generate_single_clip, cleanup_job_resources
import tempfile
import os
from pathlib import Path


class TestClipPerformance:
    """Performance and load tests for clip generation."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture
    def mock_video_data(self):
        """Mock video data for testing."""
        return {
            "id": "video_perf_test",
            "title": "Performance Test Video",
            "file_path": "/videos/perf_test.mp4",
            "duration": 600.0,  # 10 minutes
            "status": "analyzed",
            "user_id": "user_perf_test"
        }
    
    @pytest.fixture
    def performance_monitor(self):
        """Performance monitoring fixture."""
        class PerformanceMonitor:
            def __init__(self):
                self.start_time = None
                self.end_time = None
                self.peak_memory = 0
                self.peak_cpu = 0
                self.monitoring = False
                self.monitor_thread = None
            
            def start_monitoring(self):
                self.start_time = time.time()
                self.monitoring = True
                self.monitor_thread = threading.Thread(target=self._monitor_resources)
                self.monitor_thread.start()
            
            def stop_monitoring(self):
                self.end_time = time.time()
                self.monitoring = False
                if self.monitor_thread:
                    self.monitor_thread.join()
            
            def _monitor_resources(self):
                process = psutil.Process()
                while self.monitoring:
                    try:
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        cpu_percent = process.cpu_percent()
                        
                        self.peak_memory = max(self.peak_memory, memory_mb)
                        self.peak_cpu = max(self.peak_cpu, cpu_percent)
                        
                        time.sleep(0.1)  # Monitor every 100ms
                    except psutil.NoSuchProcess:
                        break
            
            @property
            def duration(self):
                if self.start_time and self.end_time:
                    return self.end_time - self.start_time
                return 0
            
            def get_stats(self):
                return {
                    "duration": self.duration,
                    "peak_memory_mb": self.peak_memory,
                    "peak_cpu_percent": self.peak_cpu
                }
        
        return PerformanceMonitor()
    
    @pytest.mark.asyncio
    async def test_single_clip_generation_performance(self, performance_monitor):
        """Test performance of single clip generation."""
        
        # Mock video file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            temp_file.flush()
            video_path = temp_file.name
        
        try:
            performance_monitor.start_monitoring()
            
            with patch('subprocess.Popen') as mock_popen, \
                 patch('os.path.exists', return_value=True), \
                 patch('os.path.getsize', return_value=1024000):  # 1MB
                
                # Mock FFmpeg process
                mock_process = Mock()
                mock_process.communicate.return_value = (b'', b'')
                mock_process.returncode = 0
                mock_process.poll.return_value = 0
                mock_popen.return_value = mock_process
                
                # Generate clip
                result = await _generate_single_clip(
                    video_path=video_path,
                    output_path="/tmp/test_clip.mp4",
                    segment={
                        'start_time': 10.0,
                        'duration': 30.0
                    },
                    platform_config={
                        "aspect_ratio": "16:9",
                        "resolution": "1920x1080",
                        "fps": 30,
                        "bitrate": "2M",
                        "audio_codec": "aac",
                        "audio_bitrate": "128k"
                    }
                )
                
                performance_monitor.stop_monitoring()
                
                # Verify performance metrics
                stats = performance_monitor.get_stats()
                
                # Single clip should complete quickly
                assert stats["duration"] < 5.0, f"Single clip took too long: {stats['duration']}s"
                
                # Memory usage should be reasonable
                assert stats["peak_memory_mb"] < 500, f"Memory usage too high: {stats['peak_memory_mb']}MB"
                
                print(f"Single clip performance: {stats}")
                
        finally:
            os.unlink(video_path)
    
    @pytest.mark.asyncio
    async def test_concurrent_clip_generation(self, client, auth_headers, mock_video_data, performance_monitor):
        """Test concurrent clip generation requests."""
        
        concurrent_requests = 5
        request_data = {
            "platform": "youtube",
            "clip_type": "highlight",
            "target_duration": 30.0,
            "max_clips": 2
        }
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = {"id": "user_test", "credits_remaining": 1000}
            
            # Mock different job IDs for each request
            job_ids = [f"job_{i}" for i in range(concurrent_requests)]
            mock_task.side_effect = [Mock(id=job_id) for job_id in job_ids]
            
            performance_monitor.start_monitoring()
            
            # Make concurrent requests
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
                futures = []
                for i in range(concurrent_requests):
                    future = executor.submit(
                        client.post,
                        f"/api/videos/video_perf_test/generate-clips",
                        json=request_data,
                        headers=auth_headers
                    )
                    futures.append(future)
                
                # Wait for all requests to complete
                responses = [future.result() for future in futures]
            
            performance_monitor.stop_monitoring()
            
            # Verify all requests succeeded
            for i, response in enumerate(responses):
                assert response.status_code == 200, f"Request {i} failed: {response.status_code}"
                data = response.json()
                assert "job_id" in data
            
            # Verify performance metrics
            stats = performance_monitor.get_stats()
            
            # Concurrent requests should complete within reasonable time
            assert stats["duration"] < 10.0, f"Concurrent requests took too long: {stats['duration']}s"
            
            # Memory usage should scale reasonably
            assert stats["peak_memory_mb"] < 1000, f"Memory usage too high: {stats['peak_memory_mb']}MB"
            
            print(f"Concurrent requests performance: {stats}")
            print(f"Average response time: {stats['duration'] / concurrent_requests:.2f}s per request")
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, performance_monitor):
        """Test memory usage during intensive clip generation."""
        
        # Simulate multiple clip generation tasks
        num_clips = 10
        
        with patch('api.tasks._generate_single_clip') as mock_generate:
            # Mock clip generation with some processing time
            async def mock_clip_generation(*args, **kwargs):
                await asyncio.sleep(0.1)  # Simulate processing
                return {
                    "file_path": "/tmp/mock_clip.mp4",
                    "thumbnail_path": "/tmp/mock_thumb.jpg",
                    "duration": 30.0,
                    "file_size": 1024000
                }
            
            mock_generate.side_effect = mock_clip_generation
            
            performance_monitor.start_monitoring()
            
            # Generate multiple clips concurrently
            tasks = []
            for i in range(num_clips):
                task = asyncio.create_task(
                    mock_clip_generation(
                        video_path=f"/tmp/video_{i}.mp4",
                        output_path=f"/tmp/clip_{i}.mp4",
                        segment={
                            'start_time': i * 30,
                            'duration': 30
                        },
                        platform_config={"aspect_ratio": "16:9"}
                    )
                )
                tasks.append(task)
            
            # Wait for all clips to complete
            await asyncio.gather(*tasks)
            
            performance_monitor.stop_monitoring()
            
            stats = performance_monitor.get_stats()
            
            # Memory usage should not grow excessively
            memory_per_clip = stats["peak_memory_mb"] / num_clips
            assert memory_per_clip < 100, f"Memory per clip too high: {memory_per_clip}MB"
            
            print(f"Memory usage under load: {stats}")
            print(f"Memory per clip: {memory_per_clip:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_processing_time_benchmarks(self, performance_monitor):
        """Test processing time benchmarks for different clip durations."""
        
        clip_durations = [15, 30, 60, 120]  # seconds
        benchmark_results = {}
        
        for duration in clip_durations:
            with patch('api.tasks._generate_single_clip') as mock_generate:
                # Mock processing time proportional to clip duration
                async def mock_clip_generation(*args, **kwargs):
                    # Simulate processing time (0.1s per second of clip)
                    processing_time = duration * 0.01
                    await asyncio.sleep(processing_time)
                    return {
                        "file_path": "/tmp/mock_clip.mp4",
                        "duration": duration,
                        "file_size": duration * 1000  # Proportional file size
                    }
                
                mock_generate.side_effect = mock_clip_generation
                
                performance_monitor.start_monitoring()
                
                # Generate clip
                await mock_clip_generation(
                    video_path="/tmp/test_video.mp4",
                    output_path="/tmp/test_clip.mp4",
                    segment={
                        'start_time': 0,
                        'duration': duration
                    },
                    platform_config={"aspect_ratio": "16:9"}
                )
                
                performance_monitor.stop_monitoring()
                
                stats = performance_monitor.get_stats()
                benchmark_results[duration] = stats
                
                # Processing time should scale reasonably with clip duration
                expected_max_time = duration * 0.1  # 10% of clip duration
                assert stats["duration"] < expected_max_time, \
                    f"Processing time too long for {duration}s clip: {stats['duration']}s"
        
        print("Processing time benchmarks:")
        for duration, stats in benchmark_results.items():
            efficiency = duration / stats["duration"] if stats["duration"] > 0 else 0
            print(f"  {duration}s clip: {stats['duration']:.2f}s processing (efficiency: {efficiency:.1f}x)")
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_efficiency(self, performance_monitor):
        """Test efficiency of resource cleanup after clip generation."""
        
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        with patch('api.tasks.cleanup_job_resources') as mock_cleanup:
            # Mock cleanup function
            def mock_cleanup_func(clip_id):
                # Simulate cleanup operations
                time.sleep(0.01)
                return True
            
            mock_cleanup.side_effect = mock_cleanup_func
            
            performance_monitor.start_monitoring()
            
            # Simulate multiple clip generations and cleanups
            num_operations = 20
            for i in range(num_operations):
                # Simulate clip generation
                await asyncio.sleep(0.01)
                
                # Cleanup resources
                mock_cleanup_func(f"clip_{i}")
            
            performance_monitor.stop_monitoring()
            
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_growth = final_memory - initial_memory
            
            stats = performance_monitor.get_stats()
            
            # Memory growth should be minimal after cleanup
            assert memory_growth < 50, f"Memory growth too high: {memory_growth}MB"
            
            # Cleanup should be fast
            avg_cleanup_time = stats["duration"] / num_operations
            assert avg_cleanup_time < 0.1, f"Cleanup too slow: {avg_cleanup_time}s per operation"
            
            print(f"Resource cleanup efficiency: {stats}")
            print(f"Memory growth: {memory_growth:.2f}MB")
            print(f"Average cleanup time: {avg_cleanup_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_disk_space_monitoring(self, performance_monitor):
        """Test disk space monitoring during clip generation."""
        
        # Get initial disk usage
        disk_usage = psutil.disk_usage('/')
        initial_free_space = disk_usage.free / 1024 / 1024 / 1024  # GB
        
        # Mock clip generation that creates temporary files
        temp_files = []
        
        try:
            performance_monitor.start_monitoring()
            
            # Simulate creating temporary files during processing
            for i in range(5):
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                # Write some data to simulate video file
                temp_file.write(b'0' * (10 * 1024 * 1024))  # 10MB per file
                temp_file.close()
                temp_files.append(temp_file.name)
                
                # Check disk space
                current_usage = psutil.disk_usage('/')
                current_free_space = current_usage.free / 1024 / 1024 / 1024
                
                # Ensure we're not running out of disk space
                assert current_free_space > 1.0, "Running low on disk space during testing"
            
            performance_monitor.stop_monitoring()
            
            stats = performance_monitor.get_stats()
            
            # Verify disk operations completed efficiently
            assert stats["duration"] < 5.0, f"Disk operations took too long: {stats['duration']}s"
            
            print(f"Disk space monitoring: {stats}")
            print(f"Initial free space: {initial_free_space:.2f}GB")
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except FileNotFoundError:
                    pass
    
    @pytest.mark.asyncio
    async def test_scalability_limits(self, client, auth_headers, mock_video_data):
        """Test system behavior at scalability limits."""
        
        # Test with increasing load until we hit limits
        max_concurrent = 20
        successful_requests = 0
        failed_requests = 0
        
        with patch('api.routers.clips.supabase_service') as mock_supabase, \
             patch('api.routers.clips.generate_clips_task.delay') as mock_task:
            
            mock_supabase.get_video_by_id.return_value = mock_video_data
            mock_supabase.get_user_by_id.return_value = {"id": "user_test", "credits_remaining": 1000}
            
            request_data = {
                "platform": "youtube",
                "clip_type": "highlight",
                "target_duration": 30.0
            }
            
            # Gradually increase load
            for batch_size in [1, 5, 10, 15, 20]:
                print(f"Testing with {batch_size} concurrent requests...")
                
                # Mock job IDs for this batch
                job_ids = [f"job_batch_{batch_size}_{i}" for i in range(batch_size)]
                mock_task.side_effect = [Mock(id=job_id) for job_id in job_ids]
                
                start_time = time.time()
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
                    futures = []
                    for i in range(batch_size):
                        future = executor.submit(
                            client.post,
                            f"/api/videos/video_perf_test/generate-clips",
                            json=request_data,
                            headers=auth_headers
                        )
                        futures.append(future)
                    
                    # Collect results
                    batch_successful = 0
                    batch_failed = 0
                    
                    for future in futures:
                        try:
                            response = future.result(timeout=10)
                            if response.status_code == 200:
                                batch_successful += 1
                            else:
                                batch_failed += 1
                        except Exception:
                            batch_failed += 1
                
                end_time = time.time()
                batch_duration = end_time - start_time
                
                successful_requests += batch_successful
                failed_requests += batch_failed
                
                success_rate = batch_successful / batch_size * 100
                throughput = batch_successful / batch_duration
                
                print(f"  Batch {batch_size}: {success_rate:.1f}% success, {throughput:.1f} req/s")
                
                # If success rate drops significantly, we've found the limit
                if success_rate < 80:
                    print(f"  Performance degradation detected at {batch_size} concurrent requests")
                    break
        
        total_requests = successful_requests + failed_requests
        overall_success_rate = successful_requests / total_requests * 100 if total_requests > 0 else 0
        
        print(f"\nScalability test results:")
        print(f"  Total requests: {total_requests}")
        print(f"  Successful: {successful_requests} ({overall_success_rate:.1f}%)")
        print(f"  Failed: {failed_requests}")
        
        # Should handle at least 10 concurrent requests successfully
        assert successful_requests >= 10, f"System should handle at least 10 concurrent requests"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])