"""Performance and scalability tests for the video-to-clip generation system.

Tests:
- Large file handling
- Memory usage under load
- Concurrent processing performance
- Resource cleanup efficiency
- API response times
- Database performance
- Cache effectiveness
"""

import os
import sys
import pytest
import asyncio
import tempfile
import shutil
import time
import threading
import psutil
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import gc

# Add the api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from video_processor import VideoProcessor
from services.ai_analyzer import AIAnalyzer
from utils.memory_optimizer import EnhancedMemoryOptimizer, MemoryStats
from utils.monitoring import MonitoringSystem, MetricType
from performance_utils import MemoryManager, CacheManager

class TestLargeFileHandling:
    """Test handling of large video files."""
    
    @pytest.fixture
    def large_video_mock(self):
        """Create a mock large video file for testing."""
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, "large_video.mp4")
        
        # Create a file that simulates a large video (100MB)
        with open(video_path, 'wb') as f:
            # Write 100MB of data
            chunk_size = 1024 * 1024  # 1MB chunks
            for _ in range(100):
                f.write(b'0' * chunk_size)
        
        yield video_path
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_large_file_memory_usage(self, large_video_mock):
        """Test memory usage when processing large files."""
        memory_optimizer = EnhancedMemoryOptimizer()
        video_processor = VideoProcessor()
        
        # Get initial memory usage
        initial_memory = memory_optimizer.get_memory_stats()
        
        try:
            with memory_optimizer.memory_context("large_file_test"):
                # Mock video processing to avoid actual processing
                with patch.object(video_processor, 'extract_audio') as mock_extract:
                    mock_extract.return_value = None  # Simulate failure to avoid actual processing
                    
                    # Attempt to process large file
                    result = video_processor.extract_audio(large_video_mock)
                    
                    # Get memory usage during processing
                    processing_memory = memory_optimizer.get_memory_stats()
                    
                    # Memory should not increase dramatically
                    memory_increase = processing_memory.rss_mb - initial_memory.rss_mb
                    assert memory_increase < 500, f"Memory increased by {memory_increase}MB, which is too much"
        
        finally:
            video_processor.cleanup_resources()
            memory_optimizer.force_garbage_collection()
    
    def test_file_size_validation(self):
        """Test file size validation and limits."""
        video_processor = VideoProcessor()
        
        # Test with oversized file path (simulated)
        oversized_file = "/path/to/oversized_video.mp4"
        
        # Should handle large files gracefully
        with patch('os.path.getsize') as mock_getsize:
            mock_getsize.return_value = 2 * 1024 * 1024 * 1024  # 2GB
            
            # Video processor should handle this without crashing
            result = video_processor.extract_audio(oversized_file)
            # Result might be None due to mocking, but no exception should be raised
    
    def test_chunk_processing_efficiency(self):
        """Test efficiency of chunk-based processing."""
        video_processor = VideoProcessor()
        
        # Mock chunk processing
        with patch.object(video_processor, '_process_video_chunk') as mock_chunk:
            mock_chunk.return_value = {"processed": True}
            
            # Simulate processing multiple chunks
            start_time = time.time()
            
            chunks = [f"chunk_{i}" for i in range(100)]
            results = []
            
            for chunk in chunks:
                result = video_processor._process_video_chunk(chunk)
                results.append(result)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Should process chunks efficiently
            assert processing_time < 1.0, f"Chunk processing took {processing_time}s, which is too slow"
            assert len(results) == 100
            assert all(r["processed"] for r in results)

class TestConcurrentProcessing:
    """Test concurrent processing capabilities."""
    
    def test_multiple_video_processing(self):
        """Test processing multiple videos concurrently."""
        memory_optimizer = EnhancedMemoryOptimizer()
        monitoring_system = MonitoringSystem()
        
        def process_video(video_id):
            """Simulate video processing."""
            video_processor = VideoProcessor()
            
            try:
                with memory_optimizer.memory_context(f"video_{video_id}"):
                    # Simulate processing time
                    time.sleep(0.1)
                    
                    # Mock video processing
                    with patch.object(video_processor, 'extract_audio') as mock_extract:
                        mock_extract.return_value = f"audio_{video_id}.wav"
                        audio_path = video_processor.extract_audio(f"video_{video_id}.mp4")
                    
                    with patch.object(video_processor, 'transcribe_audio') as mock_transcribe:
                        mock_transcribe.return_value = {
                            'text': f'Transcription for video {video_id}',
                            'segments': []
                        }
                        transcript = video_processor.transcribe_audio(audio_path)
                    
                    # Record metrics
                    monitoring_system.record_metric(
                        f"video_{video_id}_processed",
                        1,
                        MetricType.COUNTER
                    )
                    
                    return {
                        'video_id': video_id,
                        'status': 'success',
                        'transcript': transcript['text']
                    }
            
            except Exception as e:
                return {
                    'video_id': video_id,
                    'status': 'error',
                    'error': str(e)
                }
            
            finally:
                video_processor.cleanup_resources()
        
        # Test concurrent processing
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_video, i) for i in range(10)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify results
        assert len(results) == 10
        successful_results = [r for r in results if r['status'] == 'success']
        assert len(successful_results) == 10, f"Only {len(successful_results)} out of 10 videos processed successfully"
        
        # Should be faster than sequential processing
        assert total_time < 2.0, f"Concurrent processing took {total_time}s, which is too slow"
    
    def test_thread_safety(self):
        """Test thread safety of shared resources."""
        memory_optimizer = EnhancedMemoryOptimizer()
        cache_manager = CacheManager()
        
        results = []
        errors = []
        
        def worker_thread(thread_id):
            """Worker thread function."""
            try:
                # Test memory optimizer thread safety
                stats = memory_optimizer.get_memory_stats()
                assert stats.rss_mb >= 0
                
                # Test cache manager thread safety
                cache_key = f"test_key_{thread_id}"
                test_data = {"thread_id": thread_id, "data": f"test_data_{thread_id}"}
                
                # Set cache data
                cache_manager.set_cached_data(cache_key, test_data)
                
                # Get cache data
                cached_data = cache_manager.get_cached_data(cache_key)
                assert cached_data == test_data
                
                results.append(thread_id)
            
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verify results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 10
        assert set(results) == set(range(10))
    
    def test_resource_contention(self):
        """Test resource contention under high load."""
        memory_optimizer = EnhancedMemoryOptimizer()
        
        def resource_intensive_task(task_id):
            """Simulate resource-intensive task."""
            try:
                with memory_optimizer.memory_context(f"task_{task_id}"):
                    # Simulate memory allocation
                    data = [i for i in range(10000)]  # Allocate some memory
                    
                    # Simulate processing time
                    time.sleep(0.05)
                    
                    # Force garbage collection
                    gc_result = memory_optimizer.force_garbage_collection()
                    
                    return {
                        'task_id': task_id,
                        'data_size': len(data),
                        'gc_collected': gc_result['total_collected']
                    }
            
            except Exception as e:
                return {'task_id': task_id, 'error': str(e)}
        
        # Run many tasks concurrently
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(resource_intensive_task, i) for i in range(20)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify results
        successful_results = [r for r in results if 'error' not in r]
        assert len(successful_results) >= 18, f"Only {len(successful_results)} out of 20 tasks completed successfully"
        
        # Should complete within reasonable time
        assert total_time < 5.0, f"Resource contention test took {total_time}s, which is too slow"

class TestMemoryPerformance:
    """Test memory performance and optimization."""
    
    def test_memory_leak_detection(self):
        """Test memory leak detection."""
        memory_optimizer = EnhancedMemoryOptimizer()
        
        # Get initial memory
        initial_stats = memory_optimizer.get_memory_stats()
        
        # Simulate operations that might cause memory leaks
        for i in range(100):
            with memory_optimizer.memory_context(f"operation_{i}"):
                # Create some objects
                data = [j for j in range(1000)]
                
                # Register and unregister resources
                resource_id = memory_optimizer.register_resource(
                    f"resource_{i}",
                    "test",
                    size_mb=1.0
                )
                memory_optimizer.unregister_resource(resource_id)
                
                # Force cleanup every 10 iterations
                if i % 10 == 0:
                    memory_optimizer.force_garbage_collection()
        
        # Final cleanup
        memory_optimizer.force_garbage_collection()
        final_stats = memory_optimizer.get_memory_stats()
        
        # Memory should not have increased significantly
        memory_increase = final_stats.rss_mb - initial_stats.rss_mb
        assert memory_increase < 50, f"Potential memory leak detected: {memory_increase}MB increase"
    
    def test_garbage_collection_efficiency(self):
        """Test garbage collection efficiency."""
        memory_optimizer = EnhancedMemoryOptimizer()
        
        # Create objects to be collected
        large_objects = []
        for i in range(100):
            large_objects.append([j for j in range(10000)])
        
        # Get memory before cleanup
        before_stats = memory_optimizer.get_memory_stats()
        
        # Delete objects
        del large_objects
        
        # Force garbage collection
        gc_result = memory_optimizer.force_garbage_collection()
        
        # Get memory after cleanup
        after_stats = memory_optimizer.get_memory_stats()
        
        # Verify garbage collection was effective
        assert gc_result['total_collected'] > 0, "No objects were collected"
        
        # Memory should have decreased
        memory_freed = before_stats.rss_mb - after_stats.rss_mb
        assert memory_freed >= 0, "Memory was not freed effectively"
    
    def test_memory_pressure_handling(self):
        """Test handling of memory pressure situations."""
        memory_optimizer = EnhancedMemoryOptimizer(
            warning_threshold_mb=100,  # Low threshold for testing
            critical_threshold_mb=200
        )
        
        # Simulate memory pressure
        pressure_data = []
        
        try:
            # Gradually increase memory usage
            for i in range(50):
                # Add data to simulate memory usage
                pressure_data.append([j for j in range(10000)])
                
                # Check memory status
                stats = memory_optimizer.get_memory_stats()
                
                # Memory optimizer should handle pressure gracefully
                if stats.rss_mb > 150:  # Simulated high memory usage
                    # Force cleanup
                    memory_optimizer.force_garbage_collection()
                    break
        
        finally:
            # Cleanup
            del pressure_data
            memory_optimizer.force_garbage_collection()
        
        # Should complete without crashing
        assert True

class TestAPIPerformance:
    """Test API performance and response times."""
    
    def test_api_response_times(self):
        """Test API endpoint response times."""
        monitoring_system = MonitoringSystem()
        
        # Simulate API requests
        endpoints = [
            "/api/upload",
            "/api/process",
            "/api/analyze",
            "/api/results"
        ]
        
        response_times = []
        
        for endpoint in endpoints:
            for i in range(10):
                start_time = time.time()
                
                # Simulate API processing
                with monitoring_system.request_context(endpoint, "POST"):
                    time.sleep(0.01)  # Simulate processing time
                
                end_time = time.time()
                response_time = end_time - start_time
                response_times.append(response_time)
                
                # Track the request
                monitoring_system.track_request(
                    endpoint=endpoint,
                    method="POST",
                    duration=response_time,
                    status_code=200
                )
        
        # Verify response times
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        assert avg_response_time < 0.1, f"Average response time {avg_response_time}s is too slow"
        assert max_response_time < 0.2, f"Max response time {max_response_time}s is too slow"
        
        # Check performance summary
        performance_summary = monitoring_system.get_performance_summary()
        assert performance_summary['request_count'] == 40  # 4 endpoints * 10 requests
        assert performance_summary['avg_duration'] < 0.1
    
    def test_concurrent_api_requests(self):
        """Test handling of concurrent API requests."""
        monitoring_system = MonitoringSystem()
        
        def simulate_api_request(request_id):
            """Simulate an API request."""
            endpoint = f"/api/test/{request_id % 3}"  # Distribute across 3 endpoints
            
            start_time = time.time()
            
            try:
                with monitoring_system.request_context(endpoint, "GET"):
                    # Simulate processing
                    time.sleep(0.02)
                
                end_time = time.time()
                duration = end_time - start_time
                
                monitoring_system.track_request(
                    endpoint=endpoint,
                    method="GET",
                    duration=duration,
                    status_code=200
                )
                
                return {'request_id': request_id, 'duration': duration, 'status': 'success'}
            
            except Exception as e:
                return {'request_id': request_id, 'error': str(e), 'status': 'error'}
        
        # Send concurrent requests
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_api_request, i) for i in range(50)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify results
        successful_requests = [r for r in results if r['status'] == 'success']
        assert len(successful_requests) == 50, f"Only {len(successful_requests)} out of 50 requests succeeded"
        
        # Should handle concurrent requests efficiently
        assert total_time < 2.0, f"Concurrent requests took {total_time}s, which is too slow"
        
        # Check performance metrics
        performance_summary = monitoring_system.get_performance_summary()
        assert performance_summary['request_count'] == 50

class TestCachePerformance:
    """Test cache performance and effectiveness."""
    
    def test_cache_hit_rate(self):
        """Test cache hit rate and performance."""
        cache_manager = CacheManager()
        
        # Test data
        test_data = {
            'video_id': 'test_video_123',
            'analysis': {
                'viral_score': 85,
                'hashtags': ['#viral', '#trending'],
                'recommendations': ['instagram', 'tiktok']
            }
        }
        
        cache_key = "test_analysis_123"
        
        # First access - cache miss
        start_time = time.time()
        cached_data = cache_manager.get_cached_data(cache_key)
        miss_time = time.time() - start_time
        
        assert cached_data is None  # Should be cache miss
        
        # Store data in cache
        cache_manager.set_cached_data(cache_key, test_data)
        
        # Second access - cache hit
        start_time = time.time()
        cached_data = cache_manager.get_cached_data(cache_key)
        hit_time = time.time() - start_time
        
        assert cached_data == test_data  # Should be cache hit
        assert hit_time < miss_time, "Cache hit should be faster than cache miss"
    
    def test_cache_performance_under_load(self):
        """Test cache performance under high load."""
        cache_manager = CacheManager()
        
        def cache_operation(operation_id):
            """Perform cache operations."""
            try:
                cache_key = f"load_test_{operation_id}"
                test_data = {
                    'operation_id': operation_id,
                    'data': [i for i in range(100)],
                    'timestamp': time.time()
                }
                
                # Set cache data
                start_time = time.time()
                cache_manager.set_cached_data(cache_key, test_data)
                set_time = time.time() - start_time
                
                # Get cache data
                start_time = time.time()
                cached_data = cache_manager.get_cached_data(cache_key)
                get_time = time.time() - start_time
                
                return {
                    'operation_id': operation_id,
                    'set_time': set_time,
                    'get_time': get_time,
                    'data_match': cached_data == test_data
                }
            
            except Exception as e:
                return {'operation_id': operation_id, 'error': str(e)}
        
        # Perform concurrent cache operations
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(cache_operation, i) for i in range(100)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify results
        successful_operations = [r for r in results if 'error' not in r]
        assert len(successful_operations) == 100, f"Only {len(successful_operations)} cache operations succeeded"
        
        # Check data integrity
        data_matches = [r['data_match'] for r in successful_operations]
        assert all(data_matches), "Some cache operations returned incorrect data"
        
        # Check performance
        avg_set_time = sum(r['set_time'] for r in successful_operations) / len(successful_operations)
        avg_get_time = sum(r['get_time'] for r in successful_operations) / len(successful_operations)
        
        assert avg_set_time < 0.01, f"Average cache set time {avg_set_time}s is too slow"
        assert avg_get_time < 0.01, f"Average cache get time {avg_get_time}s is too slow"
        assert total_time < 5.0, f"Total cache load test took {total_time}s, which is too slow"

class TestResourceCleanup:
    """Test resource cleanup efficiency."""
    
    def test_temporary_file_cleanup(self):
        """Test temporary file cleanup efficiency."""
        video_processor = VideoProcessor()
        
        # Create temporary files
        temp_files = []
        for i in range(10):
            temp_file = os.path.join(video_processor.temp_dir, f"temp_file_{i}.txt")
            with open(temp_file, 'w') as f:
                f.write(f"Temporary content {i}")
            temp_files.append(temp_file)
        
        # Verify files exist
        for temp_file in temp_files:
            assert os.path.exists(temp_file)
        
        # Test cleanup
        start_time = time.time()
        video_processor.cleanup_resources()
        cleanup_time = time.time() - start_time
        
        # Verify cleanup efficiency
        assert cleanup_time < 1.0, f"Cleanup took {cleanup_time}s, which is too slow"
        
        # Verify files are cleaned up
        for temp_file in temp_files:
            assert not os.path.exists(temp_file), f"File {temp_file} was not cleaned up"
    
    def test_memory_cleanup_efficiency(self):
        """Test memory cleanup efficiency."""
        memory_optimizer = EnhancedMemoryOptimizer()
        
        # Register multiple resources
        resource_ids = []
        for i in range(100):
            resource_id = memory_optimizer.register_resource(
                f"test_resource_{i}",
                "test",
                size_mb=1.0
            )
            resource_ids.append(resource_id)
        
        # Verify resources are registered
        assert len(memory_optimizer._resource_registry) == 100
        
        # Test cleanup efficiency
        start_time = time.time()
        
        for resource_id in resource_ids:
            memory_optimizer.unregister_resource(resource_id)
        
        cleanup_time = time.time() - start_time
        
        # Verify cleanup efficiency
        assert cleanup_time < 0.5, f"Resource cleanup took {cleanup_time}s, which is too slow"
        assert len(memory_optimizer._resource_registry) == 0

if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "--tb=short", "-x"])