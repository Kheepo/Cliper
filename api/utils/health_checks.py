"""Production-ready health check system for clip generation service.

This module provides:
- Comprehensive health checks for all system components
- Graceful shutdown mechanisms
- Service readiness and liveness probes
- Dependency health monitoring
- Performance metrics collection
- Circuit breaker integration
"""

import asyncio
import time
import psutil
import platform
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from contextlib import asynccontextmanager
import signal
import sys
import os

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

from .logging_config import get_logger
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .enhanced_retry import EnhancedRetry, RetryConfig, BackoffStrategy

logger = get_logger('health_checks')


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'


class ComponentType(Enum):
    """Types of system components."""
    DATABASE = 'database'
    CACHE = 'cache'
    STORAGE = 'storage'
    EXTERNAL_API = 'external_api'
    QUEUE = 'queue'
    FILESYSTEM = 'filesystem'
    NETWORK = 'network'
    MEMORY = 'memory'
    CPU = 'cpu'
    DISK = 'disk'


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    component: str
    component_type: ComponentType
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'component': self.component,
            'component_type': self.component_type.value,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'response_time_ms': self.response_time_ms,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'error': self.error
        }


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    components: List[HealthCheckResult]
    summary: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'summary': self.summary,
            'components': [component.to_dict() for component in self.components]
        }


class HealthChecker:
    """Base class for health checkers."""
    
    def __init__(self, name: str, component_type: ComponentType, timeout: float = 5.0):
        self.name = name
        self.component_type = component_type
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30.0,
                expected_exception=Exception
            )
        )
    
    async def check(self) -> HealthCheckResult:
        """Perform health check."""
        start_time = time.time()
        
        try:
            async with asyncio.timeout(self.timeout):
                async with self.circuit_breaker:
                    result = await self._perform_check()
                    
            response_time = (time.time() - start_time) * 1000
            result.response_time_ms = response_time
            return result
        
        except asyncio.TimeoutError:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout}s",
                response_time_ms=(time.time() - start_time) * 1000,
                error="timeout"
            )
        
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    async def _perform_check(self) -> HealthCheckResult:
        """Override this method to implement specific health check logic."""
        raise NotImplementedError


class DatabaseHealthChecker(HealthChecker):
    """Health checker for Supabase database."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        super().__init__("database", ComponentType.DATABASE)
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client: Optional[Client] = None
        
        if SUPABASE_AVAILABLE:
            self.client = create_client(supabase_url, supabase_key)
    
    async def _perform_check(self) -> HealthCheckResult:
        """Check database connectivity and basic operations."""
        if not SUPABASE_AVAILABLE or not self.client:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message="Supabase client not available",
                error="supabase_unavailable"
            )
        
        try:
            # Simple query to test connectivity
            result = self.client.table('clips').select('id').limit(1).execute()
            
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                details={
                    'url': self.supabase_url,
                    'query_executed': True
                }
            )
        
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                error=str(e)
            )


class RedisHealthChecker(HealthChecker):
    """Health checker for Redis cache."""
    
    def __init__(self, redis_url: str):
        super().__init__("redis", ComponentType.CACHE)
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        
        if REDIS_AVAILABLE:
            self.redis_client = redis.from_url(redis_url)
    
    async def _perform_check(self) -> HealthCheckResult:
        """Check Redis connectivity and basic operations."""
        if not REDIS_AVAILABLE or not self.redis_client:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.DEGRADED,
                message="Redis not available, using fallback",
                details={'fallback_mode': True}
            )
        
        try:
            # Test basic operations
            await self.redis_client.ping()
            
            # Test set/get operations
            test_key = f"health_check:{int(time.time())}"
            await self.redis_client.set(test_key, "test_value", ex=60)
            value = await self.redis_client.get(test_key)
            await self.redis_client.delete(test_key)
            
            if value != b"test_value":
                raise Exception("Redis set/get test failed")
            
            # Get Redis info
            info = await self.redis_client.info()
            
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.HEALTHY,
                message="Redis connection and operations successful",
                details={
                    'url': self.redis_url,
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory': info.get('used_memory_human', 'unknown'),
                    'uptime_seconds': info.get('uptime_in_seconds', 0)
                }
            )
        
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                error=str(e)
            )


class FilesystemHealthChecker(HealthChecker):
    """Health checker for filesystem and storage."""
    
    def __init__(self, paths: List[str], min_free_space_gb: float = 1.0):
        super().__init__("filesystem", ComponentType.FILESYSTEM)
        self.paths = paths
        self.min_free_space_gb = min_free_space_gb
    
    async def _perform_check(self) -> HealthCheckResult:
        """Check filesystem health and available space."""
        try:
            path_details = {}
            overall_status = HealthStatus.HEALTHY
            issues = []
            
            for path in self.paths:
                if not os.path.exists(path):
                    issues.append(f"Path does not exist: {path}")
                    overall_status = HealthStatus.UNHEALTHY
                    continue
                
                # Check disk space
                usage = psutil.disk_usage(path)
                free_gb = usage.free / (1024**3)
                total_gb = usage.total / (1024**3)
                used_percent = (usage.used / usage.total) * 100
                
                path_details[path] = {
                    'total_gb': round(total_gb, 2),
                    'free_gb': round(free_gb, 2),
                    'used_percent': round(used_percent, 2),
                    'accessible': os.access(path, os.R_OK | os.W_OK)
                }
                
                if free_gb < self.min_free_space_gb:
                    issues.append(f"Low disk space on {path}: {free_gb:.2f}GB free")
                    overall_status = HealthStatus.DEGRADED
                
                if not os.access(path, os.R_OK | os.W_OK):
                    issues.append(f"No read/write access to {path}")
                    overall_status = HealthStatus.UNHEALTHY
            
            message = "Filesystem checks passed" if not issues else f"Issues found: {'; '.join(issues)}"
            
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=overall_status,
                message=message,
                details={
                    'paths': path_details,
                    'min_free_space_gb': self.min_free_space_gb,
                    'issues': issues
                }
            )
        
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Filesystem check failed: {str(e)}",
                error=str(e)
            )


class SystemResourcesHealthChecker(HealthChecker):
    """Health checker for system resources (CPU, memory, disk)."""
    
    def __init__(self, 
                 max_cpu_percent: float = 90.0,
                 max_memory_percent: float = 90.0,
                 max_disk_percent: float = 90.0):
        super().__init__("system_resources", ComponentType.MEMORY)
        self.max_cpu_percent = max_cpu_percent
        self.max_memory_percent = max_memory_percent
        self.max_disk_percent = max_disk_percent
    
    async def _perform_check(self) -> HealthCheckResult:
        """Check system resource utilization."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage (root partition)
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Load average (Unix-like systems)
            load_avg = None
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()
            
            # Determine overall status
            status = HealthStatus.HEALTHY
            issues = []
            
            if cpu_percent > self.max_cpu_percent:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
                status = HealthStatus.DEGRADED
            
            if memory_percent > self.max_memory_percent:
                issues.append(f"High memory usage: {memory_percent:.1f}%")
                status = HealthStatus.DEGRADED
            
            if disk_percent > self.max_disk_percent:
                issues.append(f"High disk usage: {disk_percent:.1f}%")
                status = HealthStatus.DEGRADED
            
            details = {
                'cpu': {
                    'percent': round(cpu_percent, 1),
                    'count': psutil.cpu_count(),
                    'load_avg': load_avg
                },
                'memory': {
                    'percent': round(memory_percent, 1),
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2)
                },
                'disk': {
                    'percent': round(disk_percent, 1),
                    'total_gb': round(disk.total / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2)
                },
                'thresholds': {
                    'max_cpu_percent': self.max_cpu_percent,
                    'max_memory_percent': self.max_memory_percent,
                    'max_disk_percent': self.max_disk_percent
                },
                'issues': issues
            }
            
            message = "System resources within normal limits" if not issues else f"Resource issues: {'; '.join(issues)}"
            
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=status,
                message=message,
                details=details
            )
        
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"System resources check failed: {str(e)}",
                error=str(e)
            )


class FFmpegHealthChecker(HealthChecker):
    """Health checker for FFmpeg availability and functionality."""
    
    def __init__(self, ffmpeg_path: str = 'ffmpeg'):
        super().__init__("ffmpeg", ComponentType.EXTERNAL_API)
        self.ffmpeg_path = ffmpeg_path
    
    async def _perform_check(self) -> HealthCheckResult:
        """Check FFmpeg availability and basic functionality."""
        try:
            # Check if FFmpeg is available
            process = await asyncio.create_subprocess_exec(
                self.ffmpeg_path, '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return HealthCheckResult(
                    component=self.name,
                    component_type=self.component_type,
                    status=HealthStatus.UNHEALTHY,
                    message=f"FFmpeg execution failed with return code {process.returncode}",
                    error=stderr.decode() if stderr else "Unknown error"
                )
            
            # Parse version info
            version_output = stdout.decode()
            version_line = version_output.split('\n')[0] if version_output else "Unknown version"
            
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.HEALTHY,
                message="FFmpeg is available and functional",
                details={
                    'path': self.ffmpeg_path,
                    'version': version_line,
                    'return_code': process.returncode
                }
            )
        
        except FileNotFoundError:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"FFmpeg not found at path: {self.ffmpeg_path}",
                error="ffmpeg_not_found"
            )
        
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"FFmpeg health check failed: {str(e)}",
                error=str(e)
            )


class HealthCheckManager:
    """Manager for coordinating health checks across all system components."""
    
    def __init__(self):
        self.checkers: List[HealthChecker] = []
        self.last_check_time: Optional[datetime] = None
        self.last_results: List[HealthCheckResult] = []
        self.check_interval = 30  # seconds
        self.background_task: Optional[asyncio.Task] = None
        self.running = False
    
    def add_checker(self, checker: HealthChecker):
        """Add a health checker to the manager."""
        self.checkers.append(checker)
        logger.info(f"Added health checker: {checker.name}")
    
    def remove_checker(self, name: str) -> bool:
        """Remove a health checker by name."""
        for i, checker in enumerate(self.checkers):
            if checker.name == name:
                del self.checkers[i]
                logger.info(f"Removed health checker: {name}")
                return True
        return False
    
    async def check_all(self) -> SystemHealth:
        """Perform health checks on all registered components."""
        if not self.checkers:
            return SystemHealth(
                status=HealthStatus.UNKNOWN,
                components=[],
                summary={'message': 'No health checkers configured'}
            )
        
        # Run all health checks concurrently
        tasks = [checker.check() for checker in self.checkers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        health_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle exceptions from health checks
                health_results.append(HealthCheckResult(
                    component=self.checkers[i].name,
                    component_type=self.checkers[i].component_type,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check exception: {str(result)}",
                    error=str(result)
                ))
            else:
                health_results.append(result)
        
        # Determine overall system health
        overall_status = self._determine_overall_status(health_results)
        
        # Generate summary
        summary = self._generate_summary(health_results)
        
        # Store results
        self.last_check_time = datetime.utcnow()
        self.last_results = health_results
        
        return SystemHealth(
            status=overall_status,
            components=health_results,
            summary=summary
        )
    
    def _determine_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """Determine overall system health based on component results."""
        if not results:
            return HealthStatus.UNKNOWN
        
        statuses = [result.status for result in results]
        
        # If any component is unhealthy, system is unhealthy
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        
        # If any component is degraded, system is degraded
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        
        # If all components are healthy, system is healthy
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        
        # Default to unknown
        return HealthStatus.UNKNOWN
    
    def _generate_summary(self, results: List[HealthCheckResult]) -> Dict[str, Any]:
        """Generate summary statistics from health check results."""
        if not results:
            return {'message': 'No health check results'}
        
        status_counts = {}
        for status in HealthStatus:
            status_counts[status.value] = sum(1 for r in results if r.status == status)
        
        avg_response_time = sum(r.response_time_ms for r in results) / len(results)
        
        failed_components = [r.component for r in results if r.status == HealthStatus.UNHEALTHY]
        degraded_components = [r.component for r in results if r.status == HealthStatus.DEGRADED]
        
        return {
            'total_components': len(results),
            'status_counts': status_counts,
            'avg_response_time_ms': round(avg_response_time, 2),
            'failed_components': failed_components,
            'degraded_components': degraded_components,
            'last_check': self.last_check_time.isoformat() + 'Z' if self.last_check_time else None
        }
    
    async def start_background_checks(self, interval: int = 30):
        """Start background health checks."""
        if self.running:
            return
        
        self.check_interval = interval
        self.running = True
        self.background_task = asyncio.create_task(self._background_check_loop())
        logger.info(f"Started background health checks with {interval}s interval")
    
    async def stop_background_checks(self):
        """Stop background health checks."""
        if not self.running:
            return
        
        self.running = False
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped background health checks")
    
    async def _background_check_loop(self):
        """Background loop for periodic health checks."""
        while self.running:
            try:
                await asyncio.sleep(self.check_interval)
                if self.running:  # Check again after sleep
                    health = await self.check_all()
                    
                    # Log health status
                    if health.status == HealthStatus.UNHEALTHY:
                        logger.error(f"System health check failed: {health.summary}")
                    elif health.status == HealthStatus.DEGRADED:
                        logger.warning(f"System health degraded: {health.summary}")
                    else:
                        logger.debug(f"System health check passed: {health.summary}")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background health check loop: {e}", exc_info=True)
    
    def get_last_results(self) -> Optional[SystemHealth]:
        """Get the last health check results."""
        if not self.last_results or not self.last_check_time:
            return None
        
        overall_status = self._determine_overall_status(self.last_results)
        summary = self._generate_summary(self.last_results)
        
        return SystemHealth(
            status=overall_status,
            components=self.last_results,
            summary=summary,
            timestamp=self.last_check_time
        )


class GracefulShutdownManager:
    """Manager for graceful application shutdown."""
    
    def __init__(self):
        self.shutdown_callbacks: List[Callable] = []
        self.shutdown_timeout = 30.0  # seconds
        self.shutdown_initiated = False
        self.shutdown_event = asyncio.Event()
    
    def add_shutdown_callback(self, callback: Callable):
        """Add a callback to be executed during shutdown."""
        self.shutdown_callbacks.append(callback)
        logger.debug(f"Added shutdown callback: {callback.__name__}")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        if sys.platform != 'win32':
            # Unix-like systems
            for sig in [signal.SIGTERM, signal.SIGINT]:
                signal.signal(sig, self._signal_handler)
        else:
            # Windows
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Signal handlers setup for graceful shutdown")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self.shutdown())
    
    async def shutdown(self):
        """Perform graceful shutdown."""
        if self.shutdown_initiated:
            return
        
        self.shutdown_initiated = True
        logger.info("Starting graceful shutdown...")
        
        try:
            # Execute shutdown callbacks with timeout
            async with asyncio.timeout(self.shutdown_timeout):
                for callback in reversed(self.shutdown_callbacks):  # LIFO order
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            callback()
                        logger.debug(f"Executed shutdown callback: {callback.__name__}")
                    except Exception as e:
                        logger.error(f"Error in shutdown callback {callback.__name__}: {e}")
            
            logger.info("Graceful shutdown completed")
        
        except asyncio.TimeoutError:
            logger.warning(f"Graceful shutdown timed out after {self.shutdown_timeout}s")
        
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
        
        finally:
            self.shutdown_event.set()
    
    async def wait_for_shutdown(self):
        """Wait for shutdown to complete."""
        await self.shutdown_event.wait()


# Global instances
_health_manager: Optional[HealthCheckManager] = None
_shutdown_manager: Optional[GracefulShutdownManager] = None


def get_health_manager() -> HealthCheckManager:
    """Get the global health check manager."""
    global _health_manager
    if _health_manager is None:
        _health_manager = HealthCheckManager()
    return _health_manager


def get_shutdown_manager() -> GracefulShutdownManager:
    """Get the global shutdown manager."""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdownManager()
    return _shutdown_manager


@asynccontextmanager
async def health_check_context(
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
    redis_url: Optional[str] = None,
    storage_paths: Optional[List[str]] = None,
    ffmpeg_path: str = 'ffmpeg',
    background_checks: bool = True,
    check_interval: int = 30
):
    """Context manager for health check system lifecycle."""
    manager = get_health_manager()
    
    # Add default health checkers
    if supabase_url and supabase_key:
        manager.add_checker(DatabaseHealthChecker(supabase_url, supabase_key))
    
    if redis_url:
        manager.add_checker(RedisHealthChecker(redis_url))
    
    if storage_paths:
        manager.add_checker(FilesystemHealthChecker(storage_paths))
    
    manager.add_checker(SystemResourcesHealthChecker())
    manager.add_checker(FFmpegHealthChecker(ffmpeg_path))
    
    # Start background checks if requested
    if background_checks:
        await manager.start_background_checks(check_interval)
    
    try:
        yield manager
    finally:
        if background_checks:
            await manager.stop_background_checks()


@asynccontextmanager
async def graceful_shutdown_context():
    """Context manager for graceful shutdown system."""
    manager = get_shutdown_manager()
    manager.setup_signal_handlers()
    
    try:
        yield manager
    finally:
        if not manager.shutdown_initiated:
            await manager.shutdown()