"""
Performance tests for hashtag recommendation system.

Tests cover:
- Response time benchmarks
- Throughput testing
- Memory usage monitoring
- Concurrent request handling
- Load testing scenarios
- Caching performance
"""

import pytest
import asyncio
import time
import psutil
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, AsyncMock
import json

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from api.services.hashtag_recommendation import HashtagRecommendationService
from api.models.pydantic_models import PlatformEnum, EnhancedHashtag, HashtagCategoryEnum, CompetitionLevelEnum


class TestHashtagRecommendationPerformance:
    """Performance test suite for hashtag recommendation system"""

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service with realistic response times"""
        mock_service = AsyncMock()
        
        async def mock_analyze_content(*args, **kwargs):
            # Simulate realistic LLM response time
            await asyncio.sleep(0.1)  # 100ms
            return {
                "topics": ["technology", "innovation", "AI"],
                "sentiment": "positive",
                "keywords": ["amazing", "latest", "trends"],
                "content_category": "educational"
            }
        
        async def mock_generate_hashtags(*args, **kwargs):
            # Simulate hashtag generation time
            await asyncio.sleep(0.05)  # 50ms
            return {
                "hashtags": [
                    {"tag": f"hashtag{i}", "relevance": 0.9 - i*0.1, "category": "trending"}
                    for i in range(10)
                ]
            }
        
        mock_service.analyze_content = mock_analyze_content
        mock_service.generate_hashtags = mock_generate_hashtags
        return mock_service

    @pytest.fixture
    def mock_viral_service(self):
        """Mock viral scoring service with realistic response times"""
        mock_service = AsyncMock()
        
        async def mock_analyze_viral_potential(*args, **kwargs):
            await asyncio.sleep(0.08)  # 80ms
            return {
                "overall_score": 0.85,
                "viral_factors": [
                    {"type": "engagement_hooks", "score": 0.9, "weight": 0.3}
                ],
                "platform_scores": {
                    "tiktok": {"score": 0.9, "confidence": 0.85}
                }
            }
        
        mock_service.analyze_viral_potential = mock_analyze_viral_potential
        return mock_service

    @pytest.fixture
    def mock_posting_service(self):
        """Mock posting optimization service with realistic response times"""
        mock_service = AsyncMock()
        
        async def mock_analyze_optimal_times(*args, **kwargs):
            await asyncio.sleep(0.06)  # 60ms
            return {
                "optimal_times": [
                    {"day": "tuesday", "hour": 19, "engagement_score": 0.85}
                ],
                "frequency_recommendation": {
                    "posts_per_day": 1.5,
                    "posts_per_week": 10.5
                }
            }
        
        mock_service.analyze_optimal_times = mock_analyze_optimal_times
        return mock_service

    @pytest.fixture
    def hashtag_service(self, mock_llm_service, mock_viral_service, mock_posting_service):
        """Create hashtag recommendation service with mocked dependencies"""
        with patch('api.services.hashtag_recommendation.UnifiedLLMService', return_value=mock_llm_service), \
             patch('api.services.hashtag_recommendation.ViralScoringService', return_value=mock_viral_service):
            return HashtagRecommendationService()

    @pytest.fixture
    def sample_content_data(self):
        """Sample content data for performance testing"""
        return {
            "description": "Amazing tech video about AI innovations and future trends",
            "duration": 120.0,
            "transcript": "This video explores the latest AI innovations and their impact on technology",
            "visual_features": {
                "scene_changes": [10.0, 30.0, 60.0, 90.0],
                "motion_intensity": 0.7
            },
            "audio_features": {
                "volume_levels": [0.8, 0.9, 0.7, 0.85],
                "silence_ratio": 0.1
            }
        }

    @pytest.mark.asyncio
    async def test_single_request_response_time(self, hashtag_service, sample_content_data):
        """Test response time for a single hashtag analysis request"""
        platform = PlatformEnum.TIKTOK
        
        start_time = time.time()
        
        result = await hashtag_service.quick_hashtag_recommendations(
            content_text=sample_content_data["description"],
            platform=platform,
            content_category="technology"
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Assert response time is under acceptable threshold
        assert response_time < 1.0  # Should complete within 1 second
        assert isinstance(result, list)
        assert len(result) > 0
        
        print(f"Single request response time: {response_time:.3f}s")

    @pytest.mark.asyncio
    async def test_concurrent_requests_performance(self, hashtag_service, sample_content_data):
        """Test performance with concurrent requests"""
        platforms = [PlatformEnum.TIKTOK]
        num_concurrent_requests = 10
        
        async def make_request():
            start_time = time.time()
            result = await hashtag_service.analyze_hashtags(
                content_data=sample_content_data,
                platforms=platforms,
                max_hashtags=5
            )
            end_time = time.time()
            return end_time - start_time, result
        
        # Execute concurrent requests
        start_time = time.time()
        tasks = [make_request() for _ in range(num_concurrent_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze results
        response_times = [r[0] for r in results]
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        # Assertions
        assert len(results) == num_concurrent_requests
        assert all(isinstance(r[1], dict) for r in results)
        assert avg_response_time < 2.0  # Average should be under 2 seconds
        assert max_response_time < 3.0  # Max should be under 3 seconds
        
        # Calculate throughput
        throughput = num_concurrent_requests / total_time
        
        print(f"Concurrent requests: {num_concurrent_requests}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Min response time: {min_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        print(f"Throughput: {throughput:.2f} requests/second")

    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self, hashtag_service, sample_content_data):
        """Test memory usage during hashtag analysis"""
        platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM]
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform multiple requests to test memory usage
        for i in range(20):
            await hashtag_service.analyze_hashtags(
                content_data=sample_content_data,
                platforms=platforms,
                max_hashtags=8
            )
            
            # Check memory every 5 requests
            if i % 5 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = current_memory - initial_memory
                
                # Memory increase should be reasonable
                assert memory_increase < 100  # Less than 100MB increase
                
                print(f"Request {i+1}: Memory usage: {current_memory:.2f}MB (+{memory_increase:.2f}MB)")

    @pytest.mark.asyncio
    async def test_caching_performance(self, hashtag_service, sample_content_data):
        """Test caching performance improvement"""
        platforms = [PlatformEnum.TIKTOK]
        
        # First request (cache miss)
        start_time = time.time()
        result1 = await hashtag_service.analyze_hashtags(
            content_data=sample_content_data,
            platforms=platforms,
            max_hashtags=5
        )
        first_request_time = time.time() - start_time
        
        # Second identical request (cache hit)
        start_time = time.time()
        result2 = await hashtag_service.analyze_hashtags(
            content_data=sample_content_data,
            platforms=platforms,
            max_hashtags=5
        )
        second_request_time = time.time() - start_time
        
        # Cache should significantly improve performance
        cache_improvement = first_request_time / second_request_time
        
        assert result1 == result2  # Results should be identical
        assert cache_improvement > 2.0  # At least 2x improvement
        assert second_request_time < 0.1  # Cached request should be very fast
        
        print(f"First request (cache miss): {first_request_time:.3f}s")
        print(f"Second request (cache hit): {second_request_time:.3f}s")
        print(f"Cache improvement: {cache_improvement:.1f}x")

    @pytest.mark.asyncio
    async def test_large_content_performance(self, hashtag_service):
        """Test performance with large content data"""
        # Create large content data
        large_content_data = {
            "description": "A" * 5000,  # 5KB description
            "duration": 3600.0,  # 1 hour video
            "transcript": "B" * 50000,  # 50KB transcript
            "visual_features": {
                "scene_changes": list(range(0, 3600, 5)),  # Many scene changes
                "motion_intensity": 0.7
            },
            "audio_features": {
                "volume_levels": [0.8] * 720,  # Many data points
                "silence_ratio": 0.1
            }
        }
        
        platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM]
        
        start_time = time.time()
        
        result = await hashtag_service.analyze_hashtags(
            content_data=large_content_data,
            platforms=platforms,
            max_hashtags=10
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Should handle large content within reasonable time
        assert response_time < 5.0  # Should complete within 5 seconds
        assert isinstance(result, dict)
        assert len(result) == len(platforms)
        
        print(f"Large content response time: {response_time:.3f}s")

    @pytest.mark.asyncio
    async def test_platform_scaling_performance(self, hashtag_service, sample_content_data):
        """Test performance scaling with multiple platforms"""
        all_platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM, PlatformEnum.YOUTUBE]
        
        # Test with increasing number of platforms
        for num_platforms in range(1, len(all_platforms) + 1):
            platforms = all_platforms[:num_platforms]
            
            start_time = time.time()
            
            result = await hashtag_service.analyze_hashtags(
                content_data=sample_content_data,
                platforms=platforms,
                max_hashtags=8
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Response time should scale reasonably
            expected_max_time = num_platforms * 0.5  # 0.5s per platform
            assert response_time < expected_max_time
            assert len(result) == num_platforms
            
            print(f"{num_platforms} platform(s): {response_time:.3f}s")

    @pytest.mark.asyncio
    async def test_hashtag_count_scaling_performance(self, hashtag_service, sample_content_data):
        """Test performance scaling with different hashtag counts"""
        platforms = [PlatformEnum.TIKTOK]
        hashtag_counts = [5, 10, 20, 30]
        
        for max_hashtags in hashtag_counts:
            start_time = time.time()
            
            result = await hashtag_service.analyze_hashtags(
                content_data=sample_content_data,
                platforms=platforms,
                max_hashtags=max_hashtags
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Response time should not increase significantly with hashtag count
            assert response_time < 2.0  # Should stay under 2 seconds
            
            hashtags = result[PlatformEnum.TIKTOK.value]
            assert len(hashtags) <= max_hashtags
            
            print(f"{max_hashtags} hashtags: {response_time:.3f}s, got {len(hashtags)} hashtags")

    @pytest.mark.asyncio
    async def test_comprehensive_recommendations_performance(self, hashtag_service, sample_content_data):
        """Test performance of comprehensive recommendations"""
        platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM]
        audience_data = {
            "target_audience": "tech enthusiasts",
            "geographic_region": "Global",
            "content_type": "educational"
        }
        
        start_time = time.time()
        
        result = await hashtag_service.get_comprehensive_recommendations(
            content_data=sample_content_data,
            platforms=platforms,
            audience_data=audience_data,
            max_hashtags_per_platform=8
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Comprehensive recommendations should complete within reasonable time
        assert response_time < 3.0  # Should complete within 3 seconds
        assert result is not None
        assert len(result.hashtag_recommendations) == len(platforms)
        assert len(result.posting_recommendations) == len(platforms)
        
        print(f"Comprehensive recommendations: {response_time:.3f}s")

    @pytest.mark.asyncio
    async def test_error_handling_performance(self, hashtag_service, sample_content_data):
        """Test performance when handling errors"""
        platforms = [PlatformEnum.TIKTOK]
        
        # Mock LLM service to raise an exception
        with patch.object(hashtag_service.llm_service, 'analyze_content', side_effect=Exception("Service error")):
            start_time = time.time()
            
            # Should fall back gracefully
            result = await hashtag_service.analyze_hashtags(
                content_data=sample_content_data,
                platforms=platforms,
                max_hashtags=5
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Error handling should be fast
            assert response_time < 1.0  # Should complete within 1 second
            assert isinstance(result, dict)
            assert PlatformEnum.TIKTOK.value in result
            
            print(f"Error handling response time: {response_time:.3f}s")

    def test_load_testing_simulation(self, hashtag_service, sample_content_data):
        """Simulate load testing with multiple threads"""
        platforms = [PlatformEnum.TIKTOK]
        num_threads = 5
        requests_per_thread = 10
        
        def make_requests():
            """Make multiple requests in a thread"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def async_requests():
                response_times = []
                for _ in range(requests_per_thread):
                    start_time = time.time()
                    
                    result = await hashtag_service.analyze_hashtags(
                        content_data=sample_content_data,
                        platforms=platforms,
                        max_hashtags=5
                    )
                    
                    end_time = time.time()
                    response_times.append(end_time - start_time)
                    
                    # Small delay between requests
                    await asyncio.sleep(0.1)
                
                return response_times
            
            return loop.run_until_complete(async_requests())
        
        # Execute load test
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_requests) for _ in range(num_threads)]
            all_response_times = []
            
            for future in as_completed(futures):
                thread_response_times = future.result()
                all_response_times.extend(thread_response_times)
        
        total_time = time.time() - start_time
        total_requests = num_threads * requests_per_thread
        
        # Analyze results
        avg_response_time = statistics.mean(all_response_times)
        max_response_time = max(all_response_times)
        throughput = total_requests / total_time
        
        # Assertions
        assert len(all_response_times) == total_requests
        assert avg_response_time < 3.0  # Average should be reasonable
        assert throughput > 1.0  # Should handle at least 1 request per second
        
        print(f"Load test results:")
        print(f"Total requests: {total_requests}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        print(f"Throughput: {throughput:.2f} requests/second")

    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, hashtag_service, sample_content_data):
        """Test for memory leaks during extended usage"""
        platforms = [PlatformEnum.TIKTOK]
        process = psutil.Process()
        
        # Record initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_readings = [initial_memory]
        
        # Perform many requests
        for i in range(50):
            await hashtag_service.analyze_hashtags(
                content_data=sample_content_data,
                platforms=platforms,
                max_hashtags=5
            )
            
            # Record memory every 10 requests
            if i % 10 == 9:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_readings.append(current_memory)
        
        # Check for memory leaks
        final_memory = memory_readings[-1]
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (not a significant leak)
        assert memory_increase < 50  # Less than 50MB increase
        
        # Check that memory doesn't continuously grow
        if len(memory_readings) >= 3:
            recent_growth = memory_readings[-1] - memory_readings[-3]
            assert recent_growth < 20  # Recent growth should be minimal
        
        print(f"Memory usage over time: {memory_readings}")
        print(f"Total memory increase: {memory_increase:.2f}MB")

    @pytest.mark.asyncio
    async def test_cpu_usage_monitoring(self, hashtag_service, sample_content_data):
        """Test CPU usage during hashtag analysis"""
        platforms = [PlatformEnum.TIKTOK, PlatformEnum.INSTAGRAM]
        process = psutil.Process()
        
        # Monitor CPU usage during requests
        cpu_percentages = []
        
        for i in range(10):
            cpu_before = process.cpu_percent()
            
            await hashtag_service.analyze_hashtags(
                content_data=sample_content_data,
                platforms=platforms,
                max_hashtags=8
            )
            
            cpu_after = process.cpu_percent()
            cpu_percentages.append(max(cpu_before, cpu_after))
            
            # Small delay to get accurate CPU readings
            await asyncio.sleep(0.1)
        
        avg_cpu = statistics.mean(cpu_percentages)
        max_cpu = max(cpu_percentages)
        
        # CPU usage should be reasonable
        assert avg_cpu < 80.0  # Average CPU should be under 80%
        assert max_cpu < 95.0  # Max CPU should be under 95%
        
        print(f"Average CPU usage: {avg_cpu:.1f}%")
        print(f"Max CPU usage: {max_cpu:.1f}%")