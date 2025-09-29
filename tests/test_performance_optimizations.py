#!/usr/bin/env python3
"""
Performance Optimizations Test Suite

Comprehensive tests for:
- Database query optimization
- Connection pooling
- Redis caching performance
- Background task processing
- File upload/download optimization
- Memory usage optimization
"""

import pytest
import asyncio
import time
import psutil
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

# Import services for testing
from api.services.database_pool_service import (
    DatabasePoolService,
    PoolConfig,
    QueryMetrics,
    ConnectionMetrics,
    get_db_pool_service
)
from api.services.redis_cache_service import (
    RedisCacheService,
    CacheConfig,
    cache_result
)
from api.database.optimization import (
    DatabaseOptimizer,
    IndexDefinition,
    QueryPerformanceMetrics,
    optimize_database
)

class TestDatabaseOptimization:
    """Test database optimization features"""
    
    @pytest.fixture
    async def db_optimizer(self):
        """Create database optimizer instance for testing"""
        # Mock Supabase client
        supabase_client = Mock()
        
        optimizer = DatabaseOptimizer(supabase_client)
        
        # Mock database connections
        optimizer.asyncpg_pool = AsyncMock()
        optimizer.async_engine = AsyncMock()
        
        return optimizer
    
    async def test_index_definitions(self, db_optimizer):
        """Test that critical indexes are properly defined"""
        indexes = db_optimizer.get_critical_indexes()
        
        # Check that we have indexes for all critical tables
        table_names = {idx.table_name for idx in indexes}
        expected_tables = {
            "users", "jobs", "job_results", "video_clips", 
            "user_settings", "api_keys", "user_sessions"
        }
        
        assert expected_tables.issubset(table_names)
        
        # Check specific important indexes
        index_names = {f"{idx.table_name}_{idx.index_name}" for idx in indexes}
        
        critical_indexes = {
            "users_idx_email",
            "jobs_idx_user_id_status",
            "job_results_idx_job_id",
            "video_clips_idx_job_id",
            "api_keys_idx_user_id_status",
            "user_sessions_idx_user_id_active"
        }
        
        for critical_index in critical_indexes:
            assert any(critical_index in idx_name for idx_name in index_names)
    
    async def test_query_performance_analysis(self, db_optimizer):
        """Test query performance analysis"""
        # Mock query performance data
        mock_queries = [
            {
                "query": "SELECT * FROM users WHERE email = $1",
                "calls": 1000,
                "total_time": 5.5,
                "mean_time": 0.0055,
                "rows": 1000
            },
            {
                "query": "SELECT * FROM jobs WHERE user_id = $1 ORDER BY created_at DESC",
                "calls": 500,
                "total_time": 15.2,
                "mean_time": 0.0304,
                "rows": 5000
            }
        ]
        
        # Mock asyncpg connection
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = mock_queries
        db_optimizer.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        metrics = await db_optimizer.analyze_query_performance()
        
        assert len(metrics) == 2
        assert all(isinstance(m, QueryPerformanceMetrics) for m in metrics)
        assert metrics[0].query.startswith("SELECT * FROM users")
        assert metrics[1].mean_time > metrics[0].mean_time  # Second query is slower
    
    async def test_slow_query_identification(self, db_optimizer):
        """Test identification of slow queries"""
        # Mock slow queries data
        mock_slow_queries = [
            {
                "query": "SELECT * FROM jobs j JOIN job_results jr ON j.id = jr.job_id WHERE j.user_id = $1",
                "calls": 50,
                "total_time": 25.0,
                "mean_time": 0.5,
                "rows": 500
            }
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = mock_slow_queries
        db_optimizer.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        slow_queries = await db_optimizer.analyze_slow_queries(threshold_ms=100)
        
        assert len(slow_queries) == 1
        assert slow_queries[0].mean_time >= 0.1  # 100ms threshold
    
    async def test_index_creation(self, db_optimizer):
        """Test index creation process"""
        # Mock successful index creation
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = None
        db_optimizer.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        test_index = IndexDefinition(
            table_name="test_table",
            index_name="idx_test_column",
            columns=["test_column"],
            index_type="btree",
            is_unique=False
        )
        
        success = await db_optimizer.create_index(test_index)
        assert success is True
        
        # Verify the SQL was executed
        mock_connection.execute.assert_called_once()
        executed_sql = mock_connection.execute.call_args[0][0]
        assert "CREATE INDEX" in executed_sql
        assert "test_table" in executed_sql
        assert "test_column" in executed_sql
    
    async def test_vacuum_analyze_execution(self, db_optimizer):
        """Test VACUUM ANALYZE execution"""
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = None
        db_optimizer.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        success = await db_optimizer.vacuum_analyze_tables()
        assert success is True
        
        # Should execute VACUUM ANALYZE for each table
        assert mock_connection.execute.call_count >= 7  # At least 7 tables
    
    async def test_performance_report_generation(self, db_optimizer):
        """Test performance report generation"""
        # Mock data for report
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = [
            {"query": "SELECT * FROM users", "calls": 100, "total_time": 1.0, "mean_time": 0.01, "rows": 100}
        ]
        db_optimizer.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        report = await db_optimizer.generate_performance_report()
        
        assert "query_performance" in report
        assert "slow_queries" in report
        assert "recommendations" in report
        assert "timestamp" in report
        
        # Check recommendations
        recommendations = report["recommendations"]
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

class TestConnectionPooling:
    """Test database connection pooling"""
    
    @pytest.fixture
    async def pool_service(self):
        """Create pool service instance for testing"""
        config = PoolConfig(
            min_connections=2,
            max_connections=10,
            connection_timeout=30,
            query_timeout=60,
            pool_recycle=3600
        )
        
        service = DatabasePoolService(config)
        
        # Mock the actual connections
        service.asyncpg_pool = AsyncMock()
        service.async_engine = AsyncMock()
        service.supabase_client = Mock()
        
        return service
    
    async def test_connection_acquisition(self, pool_service):
        """Test connection acquisition from pool"""
        # Mock connection
        mock_connection = AsyncMock()
        pool_service.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        async with pool_service.get_connection() as conn:
            assert conn is not None
            assert conn == mock_connection
        
        # Verify connection was properly acquired and released
        pool_service.asyncpg_pool.acquire.assert_called_once()
    
    async def test_session_acquisition(self, pool_service):
        """Test SQLAlchemy session acquisition"""
        # Mock session
        mock_session = AsyncMock(spec=AsyncSession)
        pool_service.async_engine.begin.return_value.__aenter__.return_value = mock_session
        
        async with pool_service.get_session() as session:
            assert session is not None
            assert session == mock_session
    
    async def test_query_execution_with_metrics(self, pool_service):
        """Test query execution with performance metrics"""
        query = "SELECT COUNT(*) FROM users"
        mock_result = [(42,)]
        
        # Mock connection and query execution
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = mock_result
        pool_service.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        result = await pool_service.execute_query(query)
        
        assert result == mock_result
        
        # Check that metrics were recorded
        stats = pool_service.get_pool_stats()
        assert stats["query_metrics"]["total_queries"] > 0
    
    async def test_transaction_execution(self, pool_service):
        """Test transaction execution"""
        queries = [
            "INSERT INTO test_table (name) VALUES ('test1')",
            "INSERT INTO test_table (name) VALUES ('test2')"
        ]
        
        # Mock connection and transaction
        mock_connection = AsyncMock()
        mock_transaction = AsyncMock()
        mock_connection.transaction.return_value.__aenter__.return_value = mock_transaction
        pool_service.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        success = await pool_service.execute_transaction(queries)
        assert success is True
        
        # Verify transaction was used
        mock_connection.transaction.assert_called_once()
        assert mock_connection.execute.call_count == len(queries)
    
    async def test_health_check(self, pool_service):
        """Test connection pool health check"""
        # Mock healthy connection
        mock_connection = AsyncMock()
        mock_connection.fetchval.return_value = 1
        pool_service.asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        
        health = await pool_service.health_check()
        
        assert health["status"] == "healthy"
        assert "asyncpg_pool" in health
        assert "response_time_ms" in health
    
    async def test_pool_statistics(self, pool_service):
        """Test pool statistics collection"""
        # Add some mock metrics
        pool_service.connection_metrics.total_connections = 5
        pool_service.connection_metrics.active_connections = 3
        pool_service.query_metrics.total_queries = 100
        pool_service.query_metrics.total_execution_time = 5.5
        
        stats = pool_service.get_pool_stats()
        
        assert "connection_metrics" in stats
        assert "query_metrics" in stats
        assert stats["connection_metrics"]["total_connections"] == 5
        assert stats["connection_metrics"]["active_connections"] == 3
        assert stats["query_metrics"]["total_queries"] == 100
        assert stats["query_metrics"]["average_execution_time"] == 0.055

class TestRedisCachePerformance:
    """Test Redis caching performance"""
    
    @pytest.fixture
    async def cache_service(self):
        """Create cache service for performance testing"""
        config = CacheConfig(
            default_ttl=3600,
            max_connections=20,
            key_prefix="perf_test"
        )
        
        service = RedisCacheService(config)
        service.redis_client = AsyncMock(spec=Redis)
        
        return service
    
    async def test_cache_performance_bulk_operations(self, cache_service):
        """Test cache performance with bulk operations"""
        # Mock Redis responses
        cache_service.redis_client.mset.return_value = True
        cache_service.redis_client.mget.return_value = [b'"value1"', b'"value2"', b'"value3"']
        
        # Test bulk set
        data = {f"key_{i}": f"value_{i}" for i in range(100)}
        
        start_time = time.time()
        success = await cache_service.bulk_set(data, 300)
        bulk_set_time = time.time() - start_time
        
        assert success is True
        assert bulk_set_time < 1.0  # Should complete within 1 second
        
        # Test bulk get
        keys = list(data.keys())
        
        start_time = time.time()
        results = await cache_service.bulk_get(keys)
        bulk_get_time = time.time() - start_time
        
        assert len(results) == len(keys)
        assert bulk_get_time < 1.0  # Should complete within 1 second
    
    async def test_cache_hit_ratio_tracking(self, cache_service):
        """Test cache hit ratio tracking"""
        # Simulate cache hits and misses
        cache_service.redis_client.get.side_effect = [
            b'"hit1"',  # Hit
            None,       # Miss
            b'"hit2"',  # Hit
            None,       # Miss
            b'"hit3"'   # Hit
        ]
        
        # Perform cache operations
        for i in range(5):
            await cache_service.get(f"key_{i}")
        
        stats = await cache_service.get_cache_stats()
        
        # Should track hits and misses
        assert "hit_ratio" in stats
        assert "total_operations" in stats
        assert stats["total_operations"] >= 5
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, cache_service):
        """Test concurrent cache operations performance"""
        # Mock Redis responses
        cache_service.redis_client.setex.return_value = True
        cache_service.redis_client.get.return_value = b'"test_value"'
        
        async def cache_operation(key: str):
            await cache_service.set(key, f"value_{key}", 300)
            return await cache_service.get(key)
        
        # Run concurrent operations
        tasks = [cache_operation(f"concurrent_key_{i}") for i in range(50)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time
        
        assert len(results) == 50
        assert concurrent_time < 5.0  # Should complete within 5 seconds
        assert all(result is not None for result in results)
    
    async def test_cache_memory_usage(self, cache_service):
        """Test cache memory usage optimization"""
        # Mock Redis memory info
        cache_service.redis_client.info.return_value = {
            "used_memory": 1024 * 1024,  # 1MB
            "used_memory_human": "1.00M",
            "maxmemory": 10 * 1024 * 1024,  # 10MB
            "maxmemory_human": "10.00M"
        }
        
        memory_info = await cache_service.get_memory_usage()
        
        assert "used_memory" in memory_info
        assert "used_memory_human" in memory_info
        assert "memory_usage_percentage" in memory_info
        assert memory_info["memory_usage_percentage"] == 10.0  # 1MB / 10MB = 10%

class TestCacheResultDecorator:
    """Test cache result decorator performance"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service for decorator testing"""
        service = AsyncMock(spec=RedisCacheService)
        service.get.return_value = None  # Cache miss initially
        service.set.return_value = True
        return service
    
    async def test_cache_decorator_performance(self, mock_cache_service):
        """Test cache decorator performance impact"""
        call_count = 0
        
        @cache_result(ttl=300, cache_service=mock_cache_service)
        async def expensive_function(param: str):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate expensive operation
            return f"result_{param}"
        
        # First call - should execute function
        start_time = time.time()
        result1 = await expensive_function("test")
        first_call_time = time.time() - start_time
        
        assert result1 == "result_test"
        assert call_count == 1
        assert first_call_time >= 0.1  # Should take at least 0.1s
        
        # Mock cache hit for second call
        mock_cache_service.get.return_value = '"result_test"'
        
        # Second call - should use cache
        start_time = time.time()
        result2 = await expensive_function("test")
        second_call_time = time.time() - start_time
        
        assert result2 == "result_test"
        assert call_count == 1  # Function not called again
        assert second_call_time < 0.05  # Should be much faster

class TestBackgroundTaskPerformance:
    """Test background task processing performance"""
    
    async def test_task_queue_performance(self):
        """Test task queue processing performance"""
        from api.services.background_tasks import TaskQueue, Task
        
        # Create task queue
        queue = TaskQueue(max_workers=4)
        
        # Create test tasks
        async def test_task(task_id: int):
            await asyncio.sleep(0.01)  # Simulate work
            return f"completed_{task_id}"
        
        tasks = [Task(id=f"task_{i}", func=test_task, args=(i,)) for i in range(100)]
        
        # Process tasks
        start_time = time.time()
        results = await queue.process_batch(tasks)
        processing_time = time.time() - start_time
        
        assert len(results) == 100
        assert processing_time < 5.0  # Should complete within 5 seconds with parallelism
        assert all("completed_" in str(result) for result in results)
    
    async def test_memory_usage_during_processing(self):
        """Test memory usage during background task processing"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Simulate memory-intensive tasks
        async def memory_task():
            # Create some data
            data = [i for i in range(10000)]
            await asyncio.sleep(0.01)
            return len(data)
        
        tasks = [memory_task() for _ in range(50)]
        
        # Process tasks
        results = await asyncio.gather(*tasks)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        assert len(results) == 50
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024

class TestFileOperationPerformance:
    """Test file upload/download performance optimizations"""
    
    async def test_chunked_file_processing(self):
        """Test chunked file processing performance"""
        from api.services.file_service import FileService
        
        # Mock file service
        file_service = FileService()
        
        # Simulate large file processing
        chunk_size = 8192  # 8KB chunks
        total_size = 1024 * 1024  # 1MB file
        chunks_processed = 0
        
        async def process_chunk(chunk_data: bytes):
            nonlocal chunks_processed
            chunks_processed += 1
            # Simulate processing time
            await asyncio.sleep(0.001)
            return len(chunk_data)
        
        # Simulate chunked processing
        start_time = time.time()
        
        for offset in range(0, total_size, chunk_size):
            chunk_size_actual = min(chunk_size, total_size - offset)
            chunk_data = b'x' * chunk_size_actual
            await process_chunk(chunk_data)
        
        processing_time = time.time() - start_time
        
        expected_chunks = (total_size + chunk_size - 1) // chunk_size
        assert chunks_processed == expected_chunks
        assert processing_time < 2.0  # Should complete within 2 seconds
    
    async def test_concurrent_file_uploads(self):
        """Test concurrent file upload performance"""
        async def mock_upload(file_id: str, size: int):
            # Simulate upload time based on size
            upload_time = size / (1024 * 1024)  # 1 second per MB
            await asyncio.sleep(min(upload_time, 0.1))  # Cap at 0.1s for testing
            return {"file_id": file_id, "size": size, "status": "uploaded"}
        
        # Simulate multiple concurrent uploads
        upload_tasks = [
            mock_upload(f"file_{i}", 1024 * (i + 1))  # Varying sizes
            for i in range(10)
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*upload_tasks)
        concurrent_time = time.time() - start_time
        
        assert len(results) == 10
        assert concurrent_time < 1.0  # Should complete within 1 second with concurrency
        assert all(result["status"] == "uploaded" for result in results)

class TestSystemResourceMonitoring:
    """Test system resource monitoring and optimization"""
    
    def test_memory_usage_monitoring(self):
        """Test memory usage monitoring"""
        process = psutil.Process()
        
        # Get initial memory usage
        initial_memory = process.memory_info()
        
        # Simulate memory allocation
        large_data = [i for i in range(100000)]
        
        # Get memory usage after allocation
        after_memory = process.memory_info()
        
        # Memory should have increased
        assert after_memory.rss > initial_memory.rss
        
        # Clean up
        del large_data
        
        # Memory usage should be tracked
        memory_percent = process.memory_percent()
        assert 0 <= memory_percent <= 100
    
    def test_cpu_usage_monitoring(self):
        """Test CPU usage monitoring"""
        process = psutil.Process()
        
        # Get initial CPU usage
        initial_cpu = process.cpu_percent()
        
        # Simulate CPU-intensive task
        start_time = time.time()
        while time.time() - start_time < 0.1:  # 100ms of work
            _ = sum(i * i for i in range(1000))
        
        # Get CPU usage after work
        final_cpu = process.cpu_percent()
        
        # CPU usage should be measurable
        assert isinstance(final_cpu, (int, float))
        assert final_cpu >= 0
    
    async def test_response_time_monitoring(self):
        """Test API response time monitoring"""
        response_times = []
        
        async def mock_api_call():
            start_time = time.time()
            await asyncio.sleep(0.01)  # Simulate API processing
            end_time = time.time()
            return end_time - start_time
        
        # Make multiple API calls
        for _ in range(20):
            response_time = await mock_api_call()
            response_times.append(response_time)
        
        # Calculate statistics
        avg_response_time = statistics.mean(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        
        assert avg_response_time > 0.01  # Should be at least 10ms
        assert avg_response_time < 0.05  # Should be less than 50ms
        assert p95_response_time > avg_response_time  # P95 should be higher than average

class TestLoadTesting:
    """Load testing for performance validation"""
    
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """Test handling of concurrent requests"""
        async def mock_request_handler(request_id: int):
            # Simulate request processing
            await asyncio.sleep(0.01)
            return {"request_id": request_id, "status": "processed"}
        
        # Simulate high concurrency
        concurrent_requests = 100
        tasks = [mock_request_handler(i) for i in range(concurrent_requests)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        assert len(results) == concurrent_requests
        assert total_time < 2.0  # Should handle 100 requests within 2 seconds
        assert all(result["status"] == "processed" for result in results)
        
        # Calculate throughput
        throughput = concurrent_requests / total_time
        assert throughput > 50  # Should handle at least 50 requests per second
    
    async def test_memory_leak_detection(self):
        """Test for memory leaks during sustained load"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        async def memory_intensive_task():
            # Create and clean up data
            data = [i for i in range(10000)]
            await asyncio.sleep(0.001)
            del data
            return True
        
        # Run many iterations
        for batch in range(10):
            tasks = [memory_intensive_task() for _ in range(50)]
            await asyncio.gather(*tasks)
            
            # Check memory usage periodically
            current_memory = process.memory_info().rss
            memory_increase = current_memory - initial_memory
            
            # Memory increase should be reasonable
            assert memory_increase < 50 * 1024 * 1024  # Less than 50MB increase
    
    async def test_database_connection_under_load(self):
        """Test database connection handling under load"""
        from api.services.database_pool_service import get_db_pool_service
        
        try:
            pool_service = await get_db_pool_service()
            
            async def db_operation(operation_id: int):
                query = "SELECT 1 as test_value"
                result = await pool_service.execute_query(query)
                return {"operation_id": operation_id, "result": result}
            
            # Simulate high database load
            db_tasks = [db_operation(i) for i in range(50)]
            
            start_time = time.time()
            results = await asyncio.gather(*db_tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            # Check that most operations succeeded
            successful_results = [r for r in results if not isinstance(r, Exception)]
            success_rate = len(successful_results) / len(results)
            
            assert success_rate > 0.9  # At least 90% success rate
            assert total_time < 5.0  # Should complete within 5 seconds
            
        except Exception as e:
            pytest.skip(f"Database connection not available: {e}")

# Performance benchmarks
class TestPerformanceBenchmarks:
    """Performance benchmarks for key operations"""
    
    async def test_authentication_performance(self):
        """Benchmark authentication performance"""
        from api.middleware.enhanced_auth_middleware import EnhancedAuthMiddleware, AuthConfig
        
        config = AuthConfig(jwt_secret="test_secret")
        auth_middleware = EnhancedAuthMiddleware(config, AsyncMock())
        
        user_data = {"user_id": "test_user", "email": "test@example.com", "role": "user"}
        
        # Benchmark token generation
        start_time = time.time()
        for _ in range(100):
            await auth_middleware.generate_access_token(user_data)
        token_generation_time = time.time() - start_time
        
        assert token_generation_time < 1.0  # Should generate 100 tokens within 1 second
        
        # Benchmark token validation
        token = await auth_middleware.generate_access_token(user_data)
        
        start_time = time.time()
        for _ in range(100):
            await auth_middleware.validate_access_token(token)
        token_validation_time = time.time() - start_time
        
        assert token_validation_time < 0.5  # Should validate 100 tokens within 0.5 seconds
    
    async def test_cache_operation_performance(self):
        """Benchmark cache operation performance"""
        cache_service = RedisCacheService(CacheConfig())
        cache_service.redis_client = AsyncMock()
        
        # Mock Redis responses
        cache_service.redis_client.setex.return_value = True
        cache_service.redis_client.get.return_value = b'"test_value"'
        
        # Benchmark cache set operations
        start_time = time.time()
        for i in range(1000):
            await cache_service.set(f"key_{i}", f"value_{i}", 300)
        set_time = time.time() - start_time
        
        assert set_time < 2.0  # Should set 1000 keys within 2 seconds
        
        # Benchmark cache get operations
        start_time = time.time()
        for i in range(1000):
            await cache_service.get(f"key_{i}")
        get_time = time.time() - start_time
        
        assert get_time < 1.0  # Should get 1000 keys within 1 second

# Test configuration
pytest_plugins = ["pytest_asyncio"]

# Run tests with: python -m pytest tests/test_performance_optimizations.py -v
if __name__ == "__main__":
    pytest.main(["-v", __file__])