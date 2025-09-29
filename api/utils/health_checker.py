"""Comprehensive health check system for monitoring application health.

Provides:
- Application health monitoring
- Service dependency checks
- Database connectivity verification
- External service health checks
- Performance metrics collection
- Health status reporting
- Alerting and notifications
"""

import asyncio
import time
import aiohttp
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict, deque

from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger
from api.config.production import get_settings
from api.utils.resource_manager import get_resource_manager, ResourceType


logger = get_logger(__name__)
settings = get_settings()


class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """Types of health checks."""
    DATABASE = "database"
    REDIS = "redis"
    EXTERNAL_API = "external_api"
    FILE_SYSTEM = "file_system"
    MEMORY = "memory"
    CPU = "cpu"
    DISK = "disk"
    NETWORK = "network"
    CUSTOM = "custom"


class Severity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""
    name: str
    check_type: CheckType
    enabled: bool = True
    interval: float = 30.0  # seconds
    timeout: float = 10.0  # seconds
    retries: int = 3
    retry_delay: float = 1.0  # seconds
    warning_threshold: float = 5.0  # seconds
    critical_threshold: float = 10.0  # seconds
    
    # Type-specific configurations
    url: Optional[str] = None  # For external API checks
    query: Optional[str] = None  # For database checks
    path: Optional[str] = None  # For file system checks
    expected_response: Optional[Any] = None
    headers: Optional[Dict[str, str]] = None


class HealthCheckResult(BaseModel):
    """Result of a health check."""
    name: str
    check_type: CheckType
    status: HealthStatus
    response_time: float  # seconds
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Additional information
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    # Metrics
    success_rate: float = 100.0  # percentage
    average_response_time: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    
    def is_healthy(self) -> bool:
        """Check if the result indicates healthy status."""
        return self.status in [HealthStatus.HEALTHY, HealthStatus.WARNING]
    
    def get_severity(self) -> Severity:
        """Get alert severity based on status."""
        if self.status == HealthStatus.CRITICAL:
            return Severity.CRITICAL
        elif self.status == HealthStatus.UNHEALTHY:
            return Severity.HIGH
        elif self.status == HealthStatus.WARNING:
            return Severity.MEDIUM
        else:
            return Severity.LOW


class HealthAlert(BaseModel):
    """Health check alert."""
    check_name: str
    status: HealthStatus
    severity: Severity
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'check_name': self.check_name,
            'status': self.status.value,
            'severity': self.severity.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved,
            'resolution_time': self.resolution_time.isoformat() if self.resolution_time else None
        }


class BaseHealthCheck:
    """Base class for health checks."""
    
    def __init__(self, config: HealthCheckConfig):
        self.config = config
        self.history: deque = deque(maxlen=100)
        self.last_result: Optional[HealthCheckResult] = None
        self.consecutive_failures = 0
        self.total_checks = 0
        self.successful_checks = 0
        
    async def check(self) -> HealthCheckResult:
        """Perform the health check."""
        start_time = time.time()
        
        try:
            # Perform the actual check with timeout
            result = await asyncio.wait_for(
                self._perform_check(),
                timeout=self.config.timeout
            )
            
            response_time = time.time() - start_time
            
            # Determine status based on response time
            if response_time > self.config.critical_threshold:
                status = HealthStatus.CRITICAL
            elif response_time > self.config.warning_threshold:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY
            
            # Create result
            health_result = HealthCheckResult(
                name=self.config.name,
                check_type=self.config.check_type,
                status=status,
                response_time=response_time,
                message=result.get('message', 'Check completed successfully'),
                details=result.get('details', {})
            )
            
            # Update statistics
            self.total_checks += 1
            self.successful_checks += 1
            self.consecutive_failures = 0
            
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            health_result = HealthCheckResult(
                name=self.config.name,
                check_type=self.config.check_type,
                status=HealthStatus.CRITICAL,
                response_time=response_time,
                message=f"Check timed out after {self.config.timeout}s",
                error="Timeout"
            )
            
            self.total_checks += 1
            self.consecutive_failures += 1
            
        except Exception as e:
            response_time = time.time() - start_time
            health_result = HealthCheckResult(
                name=self.config.name,
                check_type=self.config.check_type,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Check failed: {str(e)}",
                error=str(e)
            )
            
            self.total_checks += 1
            self.consecutive_failures += 1
        
        # Update result with statistics
        health_result.success_rate = (self.successful_checks / self.total_checks * 100) if self.total_checks > 0 else 0
        health_result.consecutive_failures = self.consecutive_failures
        
        if self.history:
            health_result.average_response_time = sum(r.response_time for r in self.history) / len(self.history)
        
        if health_result.is_healthy():
            health_result.last_success = health_result.timestamp
        else:
            health_result.last_failure = health_result.timestamp
        
        # Store result
        self.history.append(health_result)
        self.last_result = health_result
        
        return health_result
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Perform the actual health check. Override in subclasses."""
        raise NotImplementedError
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get health check metrics."""
        return {
            'name': self.config.name,
            'type': self.config.check_type.value,
            'total_checks': self.total_checks,
            'successful_checks': self.successful_checks,
            'success_rate': (self.successful_checks / self.total_checks * 100) if self.total_checks > 0 else 0,
            'consecutive_failures': self.consecutive_failures,
            'last_result': self.last_result.dict() if self.last_result else None,
            'average_response_time': sum(r.response_time for r in self.history) / len(self.history) if self.history else 0
        }


class DatabaseHealthCheck(BaseHealthCheck):
    """Database connectivity health check."""
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            # Import here to avoid circular imports
            from api.services.supabase_service import SupabaseService
            
            supabase_service = SupabaseService()
            
            # Simple query to test connectivity
            query = self.config.query or "SELECT 1"
            result = await supabase_service.execute_query(query)
            
            return {
                'message': 'Database connection successful',
                'details': {
                    'query': query,
                    'result_count': len(result) if result else 0
                }
            }
            
        except Exception as e:
            raise Exception(f"Database check failed: {e}")


class RedisHealthCheck(BaseHealthCheck):
    """Redis connectivity health check."""
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check Redis connectivity."""
        try:
            # Import here to avoid circular imports
            from api.utils.redis_client import get_redis_client
            
            redis_client = get_redis_client()
            
            # Test Redis with ping
            await redis_client.ping()
            
            # Test set/get operation
            test_key = f"health_check_{int(time.time())}"
            await redis_client.set(test_key, "test_value", ex=60)
            value = await redis_client.get(test_key)
            await redis_client.delete(test_key)
            
            if value != "test_value":
                raise Exception("Redis set/get test failed")
            
            # Get Redis info
            info = await redis_client.info()
            
            return {
                'message': 'Redis connection successful',
                'details': {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory': info.get('used_memory_human', 'unknown'),
                    'uptime': info.get('uptime_in_seconds', 0)
                }
            }
            
        except Exception as e:
            raise Exception(f"Redis check failed: {e}")


class ExternalAPIHealthCheck(BaseHealthCheck):
    """External API health check."""
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check external API availability."""
        if not self.config.url:
            raise Exception("URL not configured for external API check")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = self.config.headers or {}
                
                async with session.get(
                    self.config.url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    
                    status_code = response.status
                    response_text = await response.text()
                    
                    if status_code >= 400:
                        raise Exception(f"API returned status {status_code}: {response_text[:200]}")
                    
                    # Check expected response if configured
                    if self.config.expected_response:
                        if self.config.expected_response not in response_text:
                            raise Exception(f"Expected response not found in API response")
                    
                    return {
                        'message': f'External API check successful (status: {status_code})',
                        'details': {
                            'url': self.config.url,
                            'status_code': status_code,
                            'response_length': len(response_text)
                        }
                    }
                    
        except Exception as e:
            raise Exception(f"External API check failed: {e}")


class FileSystemHealthCheck(BaseHealthCheck):
    """File system health check."""
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check file system availability and space."""
        path = self.config.path or "."
        
        try:
            path_obj = Path(path)
            
            # Check if path exists and is accessible
            if not path_obj.exists():
                raise Exception(f"Path does not exist: {path}")
            
            # Test write access
            test_file = path_obj / f"health_check_{int(time.time())}.tmp"
            test_file.write_text("health check test")
            content = test_file.read_text()
            test_file.unlink()
            
            if content != "health check test":
                raise Exception("File system read/write test failed")
            
            # Get disk usage
            import shutil
            disk_usage = shutil.disk_usage(path)
            free_space_gb = disk_usage.free / (1024**3)
            total_space_gb = disk_usage.total / (1024**3)
            usage_percent = ((disk_usage.total - disk_usage.free) / disk_usage.total) * 100
            
            return {
                'message': f'File system check successful',
                'details': {
                    'path': str(path_obj.absolute()),
                    'free_space_gb': round(free_space_gb, 2),
                    'total_space_gb': round(total_space_gb, 2),
                    'usage_percent': round(usage_percent, 2)
                }
            }
            
        except Exception as e:
            raise Exception(f"File system check failed: {e}")


class ResourceHealthCheck(BaseHealthCheck):
    """System resource health check."""
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            resource_manager = get_resource_manager()
            
            if self.config.check_type == CheckType.MEMORY:
                usage = await resource_manager.memory_manager.get_memory_usage()
                usage_percent = usage.get_usage_percentage()
                
                return {
                    'message': f'Memory usage: {usage_percent:.1f}%',
                    'details': {
                        'usage_percent': usage_percent,
                        'current_mb': usage.current_usage,
                        'available_mb': usage.available,
                        'peak_mb': usage.peak_usage
                    }
                }
                
            elif self.config.check_type == CheckType.CPU:
                usage = resource_manager.process_manager.get_cpu_usage()
                
                return {
                    'message': f'CPU usage: {usage.current_usage:.1f}%',
                    'details': {
                        'usage_percent': usage.current_usage,
                        'available_percent': usage.available
                    }
                }
                
            elif self.config.check_type == CheckType.DISK:
                path = self.config.path or "."
                usage = resource_manager.disk_manager.get_disk_usage(path)
                
                return {
                    'message': f'Disk usage: {usage.get_usage_percentage():.1f}%',
                    'details': {
                        'path': path,
                        'usage_percent': usage.get_usage_percentage(),
                        'available_gb': usage.available
                    }
                }
            
            else:
                raise Exception(f"Unsupported resource check type: {self.config.check_type}")
                
        except Exception as e:
            raise Exception(f"Resource check failed: {e}")


class CustomHealthCheck(BaseHealthCheck):
    """Custom health check with user-defined function."""
    
    def __init__(self, config: HealthCheckConfig, check_function: Callable):
        super().__init__(config)
        self.check_function = check_function
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Execute custom check function."""
        try:
            if asyncio.iscoroutinefunction(self.check_function):
                result = await self.check_function()
            else:
                result = self.check_function()
            
            if isinstance(result, dict):
                return result
            else:
                return {
                    'message': 'Custom check completed',
                    'details': {'result': result}
                }
                
        except Exception as e:
            raise Exception(f"Custom check failed: {e}")


class HealthChecker:
    """Main health checker coordinating all health checks."""
    
    def __init__(self):
        self.checks: Dict[str, BaseHealthCheck] = {}
        self.alerts: List[HealthAlert] = []
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.alert_callbacks: List[Callable] = []
        
        # Default health checks
        self._setup_default_checks()
        
        logger.info("Health checker initialized")
    
    def _setup_default_checks(self):
        """Setup default health checks."""
        # Database check
        self.add_check(HealthCheckConfig(
            name="database",
            check_type=CheckType.DATABASE,
            interval=60.0,
            timeout=10.0
        ))
        
        # Redis check
        self.add_check(HealthCheckConfig(
            name="redis",
            check_type=CheckType.REDIS,
            interval=60.0,
            timeout=5.0
        ))
        
        # Memory check
        self.add_check(HealthCheckConfig(
            name="memory",
            check_type=CheckType.MEMORY,
            interval=30.0,
            warning_threshold=70.0,
            critical_threshold=90.0
        ))
        
        # CPU check
        self.add_check(HealthCheckConfig(
            name="cpu",
            check_type=CheckType.CPU,
            interval=30.0,
            warning_threshold=70.0,
            critical_threshold=90.0
        ))
        
        # Disk check
        self.add_check(HealthCheckConfig(
            name="disk",
            check_type=CheckType.DISK,
            interval=120.0,
            path=".",
            warning_threshold=80.0,
            critical_threshold=95.0
        ))
        
        # File system check
        self.add_check(HealthCheckConfig(
            name="filesystem",
            check_type=CheckType.FILE_SYSTEM,
            interval=300.0,
            path="./logs"
        ))
    
    def add_check(self, config: HealthCheckConfig, check_function: Optional[Callable] = None):
        """Add a health check."""
        if config.check_type == CheckType.DATABASE:
            check = DatabaseHealthCheck(config)
        elif config.check_type == CheckType.REDIS:
            check = RedisHealthCheck(config)
        elif config.check_type == CheckType.EXTERNAL_API:
            check = ExternalAPIHealthCheck(config)
        elif config.check_type == CheckType.FILE_SYSTEM:
            check = FileSystemHealthCheck(config)
        elif config.check_type in [CheckType.MEMORY, CheckType.CPU, CheckType.DISK]:
            check = ResourceHealthCheck(config)
        elif config.check_type == CheckType.CUSTOM:
            if not check_function:
                raise ValueError("Custom health check requires check_function")
            check = CustomHealthCheck(config, check_function)
        else:
            raise ValueError(f"Unsupported check type: {config.check_type}")
        
        self.checks[config.name] = check
        
        # Start monitoring if enabled
        if config.enabled:
            self.start_monitoring(config.name)
        
        logger.info(f"Added health check: {config.name} ({config.check_type.value})")
    
    def remove_check(self, name: str):
        """Remove a health check."""
        if name in self.checks:
            self.stop_monitoring(name)
            del self.checks[name]
            logger.info(f"Removed health check: {name}")
    
    def start_monitoring(self, name: str):
        """Start monitoring for a health check."""
        if name not in self.checks:
            raise ValueError(f"Health check not found: {name}")
        
        if name in self.monitoring_tasks:
            self.stop_monitoring(name)
        
        self.monitoring_tasks[name] = asyncio.create_task(
            self._monitoring_loop(name)
        )
        
        logger.info(f"Started monitoring for health check: {name}")
    
    def stop_monitoring(self, name: str):
        """Stop monitoring for a health check."""
        if name in self.monitoring_tasks:
            self.monitoring_tasks[name].cancel()
            del self.monitoring_tasks[name]
            logger.info(f"Stopped monitoring for health check: {name}")
    
    async def _monitoring_loop(self, name: str):
        """Background monitoring loop for a health check."""
        check = self.checks[name]
        
        while True:
            try:
                await asyncio.sleep(check.config.interval)
                
                result = await check.check()
                
                # Check for alerts
                await self._process_alert(result)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop for {name}: {e}")
    
    async def _process_alert(self, result: HealthCheckResult):
        """Process health check result for alerts."""
        # Check if we need to create an alert
        if not result.is_healthy():
            # Check if there's already an active alert for this check
            active_alert = next(
                (alert for alert in self.alerts 
                 if alert.check_name == result.name and not alert.resolved),
                None
            )
            
            if not active_alert:
                # Create new alert
                alert = HealthAlert(
                    check_name=result.name,
                    status=result.status,
                    severity=result.get_severity(),
                    message=f"{result.name} health check failed: {result.message}"
                )
                
                self.alerts.append(alert)
                
                # Notify alert callbacks
                for callback in self.alert_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(alert)
                        else:
                            callback(alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")
                
                logger.warning(f"Health alert created: {alert.message}")
        
        else:
            # Check if we need to resolve an alert
            active_alert = next(
                (alert for alert in self.alerts 
                 if alert.check_name == result.name and not alert.resolved),
                None
            )
            
            if active_alert:
                active_alert.resolved = True
                active_alert.resolution_time = datetime.utcnow()
                logger.info(f"Health alert resolved: {result.name}")
    
    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks once."""
        results = {}
        
        for name, check in self.checks.items():
            if check.config.enabled:
                try:
                    result = await check.check()
                    results[name] = result
                except Exception as e:
                    logger.error(f"Health check {name} failed: {e}")
                    results[name] = HealthCheckResult(
                        name=name,
                        check_type=check.config.check_type,
                        status=HealthStatus.UNKNOWN,
                        response_time=0.0,
                        message=f"Check execution failed: {e}",
                        error=str(e)
                    )
        
        return results
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        results = await self.check_all()
        
        # Determine overall status
        statuses = [result.status for result in results.values()]
        
        if HealthStatus.CRITICAL in statuses:
            overall_status = HealthStatus.CRITICAL
        elif HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.WARNING in statuses:
            overall_status = HealthStatus.WARNING
        elif HealthStatus.UNKNOWN in statuses:
            overall_status = HealthStatus.UNKNOWN
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Get active alerts
        active_alerts = [alert for alert in self.alerts if not alert.resolved]
        
        return {
            'overall_status': overall_status.value,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {name: result.dict() for name, result in results.items()},
            'active_alerts': [alert.to_dict() for alert in active_alerts],
            'alert_history': [alert.to_dict() for alert in self.alerts[-10:]],  # Last 10 alerts
            'metrics': {
                'total_checks': len(self.checks),
                'enabled_checks': len([c for c in self.checks.values() if c.config.enabled]),
                'healthy_checks': len([r for r in results.values() if r.status == HealthStatus.HEALTHY]),
                'unhealthy_checks': len([r for r in results.values() if not r.is_healthy()])
            }
        }
    
    def add_alert_callback(self, callback: Callable):
        """Add callback for health alerts."""
        self.alert_callbacks.append(callback)
        logger.info("Added health alert callback")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive health metrics."""
        return {
            'checks': {name: check.get_metrics() for name, check in self.checks.items()},
            'alerts': {
                'total': len(self.alerts),
                'active': len([a for a in self.alerts if not a.resolved]),
                'resolved': len([a for a in self.alerts if a.resolved])
            },
            'monitoring': {
                'active_tasks': len(self.monitoring_tasks),
                'task_names': list(self.monitoring_tasks.keys())
            }
        }
    
    async def close(self):
        """Close health checker and cleanup."""
        # Stop all monitoring tasks
        for name in list(self.monitoring_tasks.keys()):
            self.stop_monitoring(name)
        
        # Wait for tasks to complete
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        logger.info("Health checker closed")


# Global health checker instance
health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """Get the global health checker."""
    return health_checker


# Utility functions
async def check_health() -> Dict[str, Any]:
    """Quick health status check."""
    return await health_checker.get_health_status()


async def check_service_health(service_name: str) -> Optional[HealthCheckResult]:
    """Check health of a specific service."""
    if service_name in health_checker.checks:
        return await health_checker.checks[service_name].check()
    return None


def add_custom_health_check(name: str, check_function: Callable, **kwargs):
    """Add a custom health check."""
    config = HealthCheckConfig(
        name=name,
        check_type=CheckType.CUSTOM,
        **kwargs
    )
    health_checker.add_check(config, check_function)


# Health check decorators
def health_check(name: str, **config_kwargs):
    """Decorator to register a function as a health check."""
    def decorator(func):
        add_custom_health_check(name, func, **config_kwargs)
        return func
    return decorator