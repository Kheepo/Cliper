"""Comprehensive tests for production monitoring and middleware.

Tests:
- Production monitoring system
- Alert rules and notifications
- Performance analysis
- Request tracking middleware
- Memory monitoring
- Security checks
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import Response

from ..utils.production_monitoring import (
    ProductionMonitor,
    AlertRule,
    Alert,
    AlertSeverity,
    AlertStatus,
    MetricType,
    PerformanceInsight,
    get_production_monitor
)
from ..middleware.production_middleware import (
    RequestTrackingMiddleware,
    HealthCheckMiddleware,
    MemoryMonitoringMiddleware,
    setup_production_middleware,
    production_lifespan
)


class TestProductionMonitor:
    """Test production monitoring system."""
    
    @pytest.fixture
    def monitor(self):
        """Create a fresh production monitor for testing."""
        return ProductionMonitor()
    
    def test_monitor_initialization(self, monitor):
        """Test monitor initializes with default alert rules."""
        assert not monitor.running
        assert monitor.check_interval == 60
        assert len(monitor.alert_rules) > 0
        assert "high_cpu_usage" in monitor.alert_rules
        assert "high_memory_usage" in monitor.alert_rules
        assert "disk_space_low" in monitor.alert_rules
    
    def test_alert_rule_creation(self, monitor):
        """Test creating custom alert rules."""
        rule = AlertRule(
            name="test_rule",
            metric_name="test_metric",
            metric_type=MetricType.APPLICATION,
            threshold=100.0,
            operator=">",
            severity=AlertSeverity.HIGH,
            description="Test alert rule"
        )
        
        monitor.alert_rules["test_rule"] = rule
        assert "test_rule" in monitor.alert_rules
        assert monitor.alert_rules["test_rule"].threshold == 100.0
    
    def test_condition_evaluation(self, monitor):
        """Test alert condition evaluation."""
        assert monitor._evaluate_condition(90, 80, ">") is True
        assert monitor._evaluate_condition(70, 80, ">") is False
        assert monitor._evaluate_condition(80, 80, ">=") is True
        assert monitor._evaluate_condition(80, 80, "==") is True
        assert monitor._evaluate_condition(80, 90, "<") is True
    
    @pytest.mark.asyncio
    async def test_alert_triggering(self, monitor):
        """Test alert triggering and resolution."""
        # Create a test rule
        rule = AlertRule(
            name="test_alert",
            metric_name="test_value",
            metric_type=MetricType.SYSTEM,
            threshold=50.0,
            operator=">",
            severity=AlertSeverity.HIGH,
            description="Test alert",
            resolve_threshold=30.0
        )
        monitor.alert_rules["test_alert"] = rule
        
        # Mock metrics that should trigger alert
        metrics = {
            "system": {"test_value": 60.0}
        }
        
        # Check alert rules
        await monitor._check_alert_rules(metrics)
        
        # Verify alert was triggered
        assert "test_alert" in monitor.active_alerts
        alert = monitor.active_alerts["test_alert"]
        assert alert.status == AlertStatus.ACTIVE
        assert alert.current_value == 60.0
        
        # Test alert resolution
        metrics["system"]["test_value"] = 25.0
        await monitor._check_alert_rules(metrics)
        
        # Verify alert was resolved
        assert "test_alert" not in monitor.active_alerts
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, monitor):
        """Test metrics collection."""
        with patch('psutil.cpu_percent', return_value=45.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Mock memory and disk usage
            mock_memory.return_value.percent = 60.0
            mock_disk.return_value.percent = 70.0
            
            metrics = await monitor._collect_all_metrics()
            
            assert "system" in metrics
            assert metrics["system"]["cpu_percent"] == 45.0
            assert metrics["system"]["memory_percent"] == 60.0
            assert metrics["system"]["disk_percent"] == 70.0
    
    @pytest.mark.asyncio
    async def test_performance_analysis(self, monitor):
        """Test performance analysis and insights generation."""
        # Add some mock metrics history
        monitor.metrics_history["memory"] = [
            {"timestamp": datetime.utcnow(), "current_usage_mb": 900},
            {"timestamp": datetime.utcnow(), "current_usage_mb": 950},
            {"timestamp": datetime.utcnow(), "current_usage_mb": 1000}
        ]
        
        insights = await monitor._analyze_performance()
        
        # Should generate high memory usage insight
        memory_insights = [i for i in insights if i.category == "memory"]
        assert len(memory_insights) > 0
        assert memory_insights[0].severity == "medium"
    
    def test_alert_acknowledgment(self, monitor):
        """Test alert acknowledgment."""
        # Create a mock active alert
        alert = Alert(
            id="test_alert_1",
            rule_name="test_rule",
            metric_name="test_metric",
            current_value=100.0,
            threshold=80.0,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.ACTIVE,
            message="Test alert",
            triggered_at=datetime.utcnow()
        )
        monitor.active_alerts["test_rule"] = alert
        
        # Acknowledge the alert
        result = monitor.acknowledge_alert("test_rule", "test_user")
        
        assert result is True
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "test_user"
        assert alert.acknowledged_at is not None
    
    def test_monitoring_status(self, monitor):
        """Test monitoring status reporting."""
        status = monitor.get_monitoring_status()
        
        assert "running" in status
        assert "check_interval_seconds" in status
        assert "active_alerts" in status
        assert "alert_rules" in status
        assert status["check_interval_seconds"] == 60


class TestRequestTrackingMiddleware:
    """Test request tracking middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app with middleware."""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        @app.get("/error")
        async def error_endpoint():
            raise Exception("Test error")
        
        @app.get("/slow")
        async def slow_endpoint():
            await asyncio.sleep(0.1)
            return {"message": "slow"}
        
        app.add_middleware(RequestTrackingMiddleware)
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)
    
    def test_successful_request_tracking(self, client):
        """Test tracking of successful requests."""
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert response.json() == {"message": "test"}
    
    def test_error_request_tracking(self, client):
        """Test tracking of error requests."""
        response = client.get("/error")
        
        assert response.status_code == 500
        assert "X-Correlation-ID" in response.headers
        assert "error" in response.json()
        assert "correlation_id" in response.json()
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        middleware = RequestTrackingMiddleware(None)
        
        # Simulate multiple requests from same IP
        client_ip = "192.168.1.1"
        path = "/test"
        
        # First 100 requests should pass
        for i in range(100):
            assert not middleware._check_rate_limit(client_ip, path)
        
        # 101st request should be rate limited
        assert middleware._check_rate_limit(client_ip, path)
    
    def test_security_checks(self):
        """Test security issue detection."""
        middleware = RequestTrackingMiddleware(None)
        
        # Mock request with suspicious user agent
        request = Mock()
        request.url.query = ""
        request.url.path = "/test"
        request.headers = {"content-length": "1000"}
        
        # Test suspicious user agent
        issues = asyncio.run(middleware._check_security(
            request, "192.168.1.1", "sqlmap/1.0"
        ))
        assert "suspicious_user_agent" in issues
        
        # Test SQL injection in query
        request.url.query = "id=1 UNION SELECT * FROM users"
        issues = asyncio.run(middleware._check_security(
            request, "192.168.1.1", "Mozilla/5.0"
        ))
        assert "potential_injection_attempt" in issues
        
        # Test path traversal
        request.url.path = "/test/../../../etc/passwd"
        issues = asyncio.run(middleware._check_security(
            request, "192.168.1.1", "Mozilla/5.0"
        ))
        assert "path_traversal_attempt" in issues
    
    def test_metrics_collection(self):
        """Test request metrics collection."""
        middleware = RequestTrackingMiddleware(None)
        
        # Simulate some requests
        middleware._update_metrics("GET", "/test", 100.0, False)
        middleware._update_metrics("GET", "/test", 150.0, False)
        middleware._update_metrics("GET", "/test", 200.0, True)  # Error
        
        summary = middleware.get_metrics_summary()
        
        assert summary["total_requests"] == 3
        assert summary["total_errors"] == 1
        assert "GET /test" in summary["endpoints"]
        
        endpoint_metrics = summary["endpoints"]["GET /test"]
        assert endpoint_metrics["requests"] == 3
        assert endpoint_metrics["errors"] == 1
        assert endpoint_metrics["error_rate"] == 33.33333333333333


class TestMemoryMonitoringMiddleware:
    """Test memory monitoring middleware."""
    
    @pytest.fixture
    def middleware(self):
        """Create memory monitoring middleware."""
        return MemoryMonitoringMiddleware(None)
    
    @pytest.mark.asyncio
    async def test_memory_monitoring(self, middleware):
        """Test memory usage monitoring during requests."""
        # Mock request and response
        request = Mock()
        request.url.path = "/test"
        
        response = Mock()
        
        async def mock_call_next(req):
            return response
        
        with patch('psutil.Process') as mock_process:
            # Mock memory info
            mock_memory_info = Mock()
            mock_memory_info.rss = 500 * 1024 * 1024  # 500MB
            mock_process.return_value.memory_info.return_value = mock_memory_info
            
            result = await middleware.dispatch(request, mock_call_next)
            
            assert result == response
            assert mock_process.called
    
    @pytest.mark.asyncio
    async def test_memory_cleanup_trigger(self, middleware):
        """Test memory cleanup triggering."""
        # Set request count to trigger cleanup
        middleware.request_count = 99
        middleware.memory_threshold_mb = 100  # Low threshold for testing
        
        request = Mock()
        request.url.path = "/test"
        response = Mock()
        
        async def mock_call_next(req):
            return response
        
        with patch('psutil.Process') as mock_process, \
             patch.object(middleware, '_cleanup_memory') as mock_cleanup:
            
            # Mock high memory usage
            mock_memory_info = Mock()
            mock_memory_info.rss = 200 * 1024 * 1024  # 200MB (above threshold)
            mock_process.return_value.memory_info.return_value = mock_memory_info
            
            await middleware.dispatch(request, mock_call_next)
            
            # Should trigger cleanup on 100th request
            assert middleware.request_count == 100


class TestHealthCheckMiddleware:
    """Test health check middleware."""
    
    @pytest.fixture
    def middleware(self):
        """Create health check middleware."""
        return HealthCheckMiddleware(None)
    
    @pytest.mark.asyncio
    async def test_health_check_bypass(self, middleware):
        """Test that health check endpoints bypass detailed tracking."""
        request = Mock()
        request.url.path = "/health"
        
        response = Mock()
        call_next_called = False
        
        async def mock_call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return response
        
        result = await middleware.dispatch(request, mock_call_next)
        
        assert result == response
        assert call_next_called
    
    @pytest.mark.asyncio
    async def test_non_health_check_passthrough(self, middleware):
        """Test that non-health check endpoints pass through normally."""
        request = Mock()
        request.url.path = "/api/test"
        
        response = Mock()
        call_next_called = False
        
        async def mock_call_next(req):
            nonlocal call_next_called
            call_next_called = True
            return response
        
        result = await middleware.dispatch(request, mock_call_next)
        
        assert result == response
        assert call_next_called


class TestProductionLifespan:
    """Test production lifespan management."""
    
    @pytest.mark.asyncio
    async def test_lifespan_startup_shutdown(self):
        """Test production lifespan startup and shutdown."""
        app = FastAPI()
        
        with patch('asyncio.create_task') as mock_task, \
             patch.object(get_production_monitor(), 'start_monitoring') as mock_start, \
             patch.object(get_production_monitor(), 'stop_monitoring') as mock_stop:
            
            # Test lifespan context manager
            async with production_lifespan(app):
                # Verify startup tasks
                assert mock_task.called
            
            # Verify shutdown tasks
            assert mock_stop.called


class TestIntegration:
    """Integration tests for production monitoring."""
    
    @pytest.fixture
    def production_app(self):
        """Create production-ready app with all middleware."""
        app = FastAPI(lifespan=production_lifespan)
        
        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}
        
        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}
        
        return setup_production_middleware(app)
    
    def test_production_app_setup(self, production_app):
        """Test that production app is properly configured."""
        client = TestClient(production_app)
        
        # Test regular endpoint
        response = client.get("/api/test")
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_end_to_end_monitoring(self):
        """Test end-to-end monitoring functionality."""
        monitor = ProductionMonitor()
        
        # Start monitoring briefly
        monitor.running = True
        
        try:
            # Collect metrics
            with patch.object(monitor, '_collect_all_metrics') as mock_collect:
                mock_collect.return_value = {
                    "system": {
                        "cpu_percent": 95.0,  # High CPU to trigger alert
                        "memory_percent": 60.0,
                        "disk_percent": 50.0
                    }
                }
                
                # Check alert rules
                await monitor._check_alert_rules(await mock_collect())
                
                # Verify high CPU alert was triggered
                assert "high_cpu_usage" in monitor.active_alerts
                
        finally:
            monitor.running = False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])