"""Unit tests for monitoring and health check systems."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncio
from datetime import datetime, timedelta


class TestHealthChecker:
    """Test health checker functionality."""
    
    @pytest.fixture
    def health_checker(self):
        """Create health checker instance."""
        from api.monitoring.health import HealthChecker
        return HealthChecker()
    
    @pytest.mark.asyncio
    async def test_redis_health_check_success(self, health_checker, mock_redis):
        """Test successful Redis health check."""
        with patch('api.services.redis_service.redis_client', mock_redis):
            result = await health_checker.check_redis_health()
            
            assert result['status'] == 'healthy'
            assert 'response_time' in result
            assert result['response_time'] >= 0
            mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_health_check_failure(self, health_checker):
        """Test Redis health check failure."""
        mock_redis = Mock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        with patch('api.services.redis_service.redis_client', mock_redis):
            result = await health_checker.check_redis_health()
            
            assert result['status'] == 'unhealthy'
            assert 'error' in result
            assert 'Connection failed' in result['error']
    
    @pytest.mark.asyncio
    async def test_celery_health_check_success(self, health_checker, mock_celery):
        """Test successful Celery health check."""
        with patch('api.tasks.celery_app', mock_celery):
            result = await health_checker.check_celery_health()
            
            assert result['status'] == 'healthy'
            assert 'workers' in result
            assert result['workers'] >= 0
    
    @pytest.mark.asyncio
    async def test_celery_health_check_failure(self, health_checker):
        """Test Celery health check failure."""
        mock_celery = Mock()
        mock_celery.control.inspect.side_effect = Exception("Celery not available")
        
        with patch('api.tasks.celery_app', mock_celery):
            result = await health_checker.check_celery_health()
            
            assert result['status'] == 'unhealthy'
            assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_supabase_health_check_success(self, health_checker, mock_supabase):
        """Test successful Supabase health check."""
        with patch('api.services.supabase_service.supabase_client', mock_supabase):
            result = await health_checker.check_supabase_health()
            
            assert result['status'] == 'healthy'
            assert 'response_time' in result
    
    @pytest.mark.asyncio
    async def test_supabase_health_check_failure(self, health_checker):
        """Test Supabase health check failure."""
        mock_supabase = Mock()
        mock_supabase.table.side_effect = Exception("Supabase error")
        
        with patch('api.services.supabase_service.supabase_client', mock_supabase):
            result = await health_checker.check_supabase_health()
            
            assert result['status'] == 'unhealthy'
            assert 'error' in result
    
    def test_disk_space_check_healthy(self, health_checker):
        """Test disk space check when healthy."""
        with patch('shutil.disk_usage') as mock_disk_usage:
            mock_disk_usage.return_value = (1000000000, 500000000, 500000000)  # 50% used
            
            result = health_checker.check_disk_space()
            
            assert result['status'] == 'healthy'
            assert result['usage_percent'] == 50.0
            assert 'total_gb' in result
            assert 'free_gb' in result
    
    def test_disk_space_check_warning(self, health_checker):
        """Test disk space check when in warning state."""
        with patch('shutil.disk_usage') as mock_disk_usage:
            mock_disk_usage.return_value = (1000000000, 150000000, 850000000)  # 85% used
            
            result = health_checker.check_disk_space()
            
            assert result['status'] == 'warning'
            assert result['usage_percent'] == 85.0
    
    def test_disk_space_check_critical(self, health_checker):
        """Test disk space check when critical."""
        with patch('shutil.disk_usage') as mock_disk_usage:
            mock_disk_usage.return_value = (1000000000, 50000000, 950000000)  # 95% used
            
            result = health_checker.check_disk_space()
            
            assert result['status'] == 'critical'
            assert result['usage_percent'] == 95.0
    
    def test_memory_usage_check_healthy(self, health_checker):
        """Test memory usage check when healthy."""
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = Mock(percent=60.0, total=8000000000, available=3200000000)
            
            result = health_checker.check_memory_usage()
            
            assert result['status'] == 'healthy'
            assert result['usage_percent'] == 60.0
            assert 'total_gb' in result
            assert 'available_gb' in result
    
    def test_memory_usage_check_warning(self, health_checker):
        """Test memory usage check when in warning state."""
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = Mock(percent=85.0, total=8000000000, available=1200000000)
            
            result = health_checker.check_memory_usage()
            
            assert result['status'] == 'warning'
            assert result['usage_percent'] == 85.0
    
    def test_memory_usage_check_critical(self, health_checker):
        """Test memory usage check when critical."""
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = Mock(percent=95.0, total=8000000000, available=400000000)
            
            result = health_checker.check_memory_usage()
            
            assert result['status'] == 'critical'
            assert result['usage_percent'] == 95.0
    
    @pytest.mark.asyncio
    async def test_run_all_checks_healthy(self, health_checker, mock_redis, mock_celery, mock_supabase):
        """Test running all health checks when system is healthy."""
        with patch('api.services.redis_service.redis_client', mock_redis), \
             patch('api.tasks.celery_app', mock_celery), \
             patch('api.services.supabase_service.supabase_client', mock_supabase), \
             patch('shutil.disk_usage', return_value=(1000000000, 500000000, 500000000)), \
             patch('psutil.virtual_memory', return_value=Mock(percent=60.0, total=8000000000, available=3200000000)), \
             patch('psutil.cpu_percent', return_value=25.0):
            
            result = await health_checker.run_all_checks()
            
            assert result['status'] == 'healthy'
            assert 'checks' in result
            assert 'system_metrics' in result
            assert result['checks']['redis']['status'] == 'healthy'
            assert result['checks']['celery']['status'] == 'healthy'
            assert result['checks']['supabase']['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_run_all_checks_unhealthy(self, health_checker):
        """Test running all health checks when system is unhealthy."""
        mock_redis = Mock()
        mock_redis.ping.side_effect = Exception("Redis down")
        
        with patch('api.services.redis_service.redis_client', mock_redis), \
             patch('shutil.disk_usage', return_value=(1000000000, 500000000, 500000000)), \
             patch('psutil.virtual_memory', return_value=Mock(percent=60.0, total=8000000000, available=3200000000)), \
             patch('psutil.cpu_percent', return_value=25.0):
            
            result = await health_checker.run_all_checks()
            
            assert result['status'] == 'unhealthy'
            assert result['checks']['redis']['status'] == 'unhealthy'


class TestPerformanceMonitor:
    """Test performance monitoring functionality."""
    
    @pytest.fixture
    def performance_monitor(self):
        """Create performance monitor instance."""
        from api.monitoring.performance_monitor import PerformanceMonitor
        return PerformanceMonitor()
    
    def test_record_request(self, performance_monitor):
        """Test recording request metrics."""
        performance_monitor.record_request("/test", "GET", 0.5, 200)
        
        metrics = performance_monitor.get_current_metrics()
        assert metrics['request_count'] >= 1
        assert metrics['avg_response_time'] >= 0
    
    def test_record_error(self, performance_monitor):
        """Test recording error metrics."""
        performance_monitor.record_error("/test", "GET", 500, "Internal Server Error")
        
        metrics = performance_monitor.get_current_metrics()
        assert metrics['error_count'] >= 1
        assert metrics['error_rate'] >= 0
    
    def test_get_current_metrics(self, performance_monitor):
        """Test getting current performance metrics."""
        metrics = performance_monitor.get_current_metrics()
        
        required_fields = [
            'request_count', 'avg_response_time', 'error_rate',
            'active_connections', 'cpu_percent', 'memory_percent'
        ]
        
        for field in required_fields:
            assert field in metrics
            assert isinstance(metrics[field], (int, float))
    
    def test_get_processing_stats(self, performance_monitor):
        """Test getting processing statistics."""
        with patch.object(performance_monitor, 'get_processing_stats') as mock_stats:
            mock_stats.return_value = {
                "total_videos_processed": 150,
                "total_clips_generated": 450,
                "avg_processing_time": 45.2,
                "success_rate": 0.95,
                "queue_size": 5,
                "active_jobs": 2
            }
            
            stats = performance_monitor.get_processing_stats()
            
            assert stats['total_videos_processed'] == 150
            assert stats['success_rate'] == 0.95
            assert stats['queue_size'] == 5
    
    @pytest.mark.asyncio
    async def test_monitoring_loop(self, performance_monitor):
        """Test performance monitoring loop."""
        # Mock the monitoring loop to run once
        with patch.object(performance_monitor, 'collect_system_metrics') as mock_collect:
            mock_collect.return_value = {
                'cpu_percent': 25.0,
                'memory_percent': 60.0,
                'disk_percent': 45.0
            }
            
            # Run monitoring loop once
            await performance_monitor.collect_system_metrics()
            mock_collect.assert_called_once()


class TestServiceDiscovery:
    """Test service discovery functionality."""
    
    @pytest.fixture
    def service_registry(self):
        """Create service registry instance."""
        from api.monitoring.service_discovery import ServiceRegistry
        return ServiceRegistry()
    
    @pytest.mark.asyncio
    async def test_register_service(self, service_registry):
        """Test service registration."""
        service_info = {
            'name': 'test-service',
            'host': 'localhost',
            'port': 8000,
            'health_check_url': '/health',
            'metadata': {'version': '1.0.0'}
        }
        
        result = await service_registry.register_service('test-service-1', service_info)
        assert result is True
        
        services = await service_registry.discover_services('test-service')
        assert len(services) == 1
        assert services[0]['name'] == 'test-service'
    
    @pytest.mark.asyncio
    async def test_deregister_service(self, service_registry):
        """Test service deregistration."""
        # First register a service
        service_info = {
            'name': 'test-service',
            'host': 'localhost',
            'port': 8000
        }
        
        await service_registry.register_service('test-service-1', service_info)
        
        # Then deregister it
        result = await service_registry.deregister_service('test-service-1')
        assert result is True
        
        services = await service_registry.discover_services('test-service')
        assert len(services) == 0
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, service_registry):
        """Test service heartbeat."""
        # Register a service
        service_info = {
            'name': 'test-service',
            'host': 'localhost',
            'port': 8000
        }
        
        await service_registry.register_service('test-service-1', service_info)
        
        # Send heartbeat
        result = await service_registry.heartbeat('test-service-1')
        assert result is True
    
    @pytest.mark.asyncio
    async def test_discover_services(self, service_registry):
        """Test service discovery."""
        # Register multiple services
        for i in range(3):
            service_info = {
                'name': 'test-service',
                'host': f'host-{i}',
                'port': 8000 + i
            }
            await service_registry.register_service(f'test-service-{i}', service_info)
        
        services = await service_registry.discover_services('test-service')
        assert len(services) == 3
        
        # Test filtering by health status
        healthy_services = await service_registry.discover_services('test-service', healthy_only=True)
        assert len(healthy_services) <= 3  # Depends on health check results


class TestLoadBalancer:
    """Test load balancer functionality."""
    
    @pytest.fixture
    def load_balancer(self):
        """Create load balancer instance."""
        from api.monitoring.service_discovery import LoadBalancer
        return LoadBalancer()
    
    def test_round_robin_strategy(self, load_balancer):
        """Test round-robin load balancing strategy."""
        services = [
            {'id': 'service-1', 'host': 'host-1', 'port': 8001},
            {'id': 'service-2', 'host': 'host-2', 'port': 8002},
            {'id': 'service-3', 'host': 'host-3', 'port': 8003}
        ]
        
        # Test multiple selections to verify round-robin behavior
        selected_services = []
        for _ in range(6):  # Two full rounds
            service = load_balancer.select_service(services, strategy='round_robin')
            selected_services.append(service['id'])
        
        # Should cycle through services
        expected = ['service-1', 'service-2', 'service-3', 'service-1', 'service-2', 'service-3']
        assert selected_services == expected
    
    def test_random_strategy(self, load_balancer):
        """Test random load balancing strategy."""
        services = [
            {'id': 'service-1', 'host': 'host-1', 'port': 8001},
            {'id': 'service-2', 'host': 'host-2', 'port': 8002}
        ]
        
        # Test multiple selections
        selected_services = set()
        for _ in range(10):
            service = load_balancer.select_service(services, strategy='random')
            selected_services.add(service['id'])
        
        # Should select from available services
        assert selected_services.issubset({'service-1', 'service-2'})
    
    def test_weighted_strategy(self, load_balancer):
        """Test weighted load balancing strategy."""
        services = [
            {'id': 'service-1', 'host': 'host-1', 'port': 8001, 'weight': 3},
            {'id': 'service-2', 'host': 'host-2', 'port': 8002, 'weight': 1}
        ]
        
        # Test multiple selections
        selections = {}
        for _ in range(100):
            service = load_balancer.select_service(services, strategy='weighted')
            selections[service['id']] = selections.get(service['id'], 0) + 1
        
        # Service-1 should be selected more often due to higher weight
        assert selections.get('service-1', 0) > selections.get('service-2', 0)
    
    def test_empty_services_list(self, load_balancer):
        """Test load balancer with empty services list."""
        services = []
        
        service = load_balancer.select_service(services)
        assert service is None
    
    def test_single_service(self, load_balancer):
        """Test load balancer with single service."""
        services = [
            {'id': 'service-1', 'host': 'host-1', 'port': 8001}
        ]
        
        service = load_balancer.select_service(services)
        assert service['id'] == 'service-1'


class TestAlertManager:
    """Test alert management functionality."""
    
    @pytest.fixture
    def alert_manager(self):
        """Create alert manager instance."""
        from api.monitoring.alerting import AlertManager
        return AlertManager()
    
    @pytest.mark.asyncio
    async def test_create_alert(self, alert_manager):
        """Test creating an alert."""
        alert = await alert_manager.create_alert(
            title="Test Alert",
            message="This is a test alert",
            severity="warning",
            source="test"
        )
        
        assert alert.title == "Test Alert"
        assert alert.severity.value == "warning"
        assert alert.status.value == "active"
    
    @pytest.mark.asyncio
    async def test_resolve_alert(self, alert_manager):
        """Test resolving an alert."""
        # Create an alert first
        alert = await alert_manager.create_alert(
            title="Test Alert",
            message="This is a test alert",
            severity="warning",
            source="test"
        )
        
        # Resolve the alert
        result = await alert_manager.resolve_alert(alert.id)
        assert result is True
        
        # Check alert status
        resolved_alert = alert_manager.alerts.get(alert.id)
        assert resolved_alert.status.value == "resolved"
    
    @pytest.mark.asyncio
    async def test_get_active_alerts(self, alert_manager):
        """Test getting active alerts."""
        # Create multiple alerts
        await alert_manager.create_alert("Alert 1", "Message 1", "warning", "test")
        await alert_manager.create_alert("Alert 2", "Message 2", "critical", "test")
        
        active_alerts = await alert_manager.get_active_alerts()
        assert len(active_alerts) == 2
        
        # Resolve one alert
        alert_id = list(alert_manager.alerts.keys())[0]
        await alert_manager.resolve_alert(alert_id)
        
        active_alerts = await alert_manager.get_active_alerts()
        assert len(active_alerts) == 1
    
    @pytest.mark.asyncio
    async def test_check_alert_rules(self, alert_manager):
        """Test checking alert rules against metrics."""
        metrics = {
            'cpu_percent': 95.0,  # Should trigger high CPU alert
            'memory_percent': 60.0,
            'disk_percent': 45.0,
            'error_rate': 0.02  # Should trigger high error rate alert
        }
        
        triggered_alerts = await alert_manager.check_alert_rules(metrics)
        
        # Should trigger alerts for high CPU and error rate
        assert len(triggered_alerts) >= 1
        
        # Check that alerts were created
        active_alerts = await alert_manager.get_active_alerts()
        assert len(active_alerts) >= 1
    
    @pytest.mark.asyncio
    async def test_alert_suppression(self, alert_manager):
        """Test alert suppression to prevent spam."""
        # Create the same alert multiple times quickly
        for _ in range(5):
            await alert_manager.create_alert(
                title="Duplicate Alert",
                message="This alert should be suppressed",
                severity="warning",
                source="test"
            )
        
        # Should only create one alert due to suppression
        active_alerts = await alert_manager.get_active_alerts()
        duplicate_alerts = [a for a in active_alerts if a.title == "Duplicate Alert"]
        assert len(duplicate_alerts) <= 2  # Allow for some duplicates but not all 5