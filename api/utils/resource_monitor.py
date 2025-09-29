"""Resource monitoring and management system.

Provides:
- Real-time resource monitoring (CPU, memory, disk, network)
- Resource usage alerts and thresholds
- Automatic resource cleanup
- Resource pool management
- Performance optimization recommendations
- Resource usage analytics
"""

import asyncio
import psutil
import time
import gc
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from pathlib import Path
import statistics
import threading

from pydantic import BaseModel

from api.utils.enhanced_logging import get_logger, PerformanceMetrics
from api.config.production import get_settings


logger = get_logger(__name__)
settings = get_settings()


class ResourceType(str, Enum):
    """Types of system resources."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    FILE_DESCRIPTORS = "file_descriptors"
    THREADS = "threads"
    PROCESSES = "processes"


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ResourceStatus(str, Enum):
    """Resource status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


@dataclass
class ResourceThresholds:
    """Resource usage thresholds."""
    warning_threshold: float = 0.7  # 70%
    critical_threshold: float = 0.85  # 85%
    emergency_threshold: float = 0.95  # 95%
    check_interval: float = 5.0  # seconds


@dataclass
class ResourceUsage:
    """Resource usage snapshot."""
    resource_type: ResourceType
    current_usage: float
    max_usage: float
    percentage: float
    timestamp: datetime
    status: ResourceStatus
    details: Dict[str, Any] = field(default_factory=dict)


class ResourceAlert(BaseModel):
    """Resource usage alert."""
    resource_type: ResourceType
    level: AlertLevel
    message: str
    current_usage: float
    threshold: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class SystemMetrics(BaseModel):
    """System-wide metrics."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    file_descriptors: int
    thread_count: int
    process_count: int
    load_average: List[float]
    uptime: float
    timestamp: datetime


class ProcessMetrics(BaseModel):
    """Process-specific metrics."""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_rss: int
    memory_vms: int
    num_threads: int
    num_fds: int
    create_time: float
    status: str
    timestamp: datetime


class ResourceMonitor:
    """System resource monitor."""
    
    def __init__(self, check_interval: float = 5.0):
        self.check_interval = check_interval
        self.thresholds: Dict[ResourceType, ResourceThresholds] = {
            ResourceType.CPU: ResourceThresholds(0.8, 0.9, 0.95),
            ResourceType.MEMORY: ResourceThresholds(0.8, 0.9, 0.95),
            ResourceType.DISK: ResourceThresholds(0.8, 0.9, 0.95),
            ResourceType.FILE_DESCRIPTORS: ResourceThresholds(0.8, 0.9, 0.95),
        }
        
        # Monitoring data
        self.usage_history: Dict[ResourceType, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self.alerts: List[ResourceAlert] = []
        self.active_alerts: Dict[ResourceType, ResourceAlert] = {}
        
        # Monitoring task
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        
        # Callbacks
        self.alert_callbacks: List[Callable[[ResourceAlert], None]] = []
        self.cleanup_callbacks: List[Callable[[], None]] = []
        
        # Process monitoring
        self.current_process = psutil.Process()
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        logger.info("Resource monitor initialized")
    
    def set_threshold(self, resource_type: ResourceType, thresholds: ResourceThresholds):
        """Set resource thresholds."""
        self.thresholds[resource_type] = thresholds
        logger.info(f"Updated thresholds for {resource_type}: {thresholds}")
    
    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]):
        """Add alert callback."""
        self.alert_callbacks.append(callback)
    
    def add_cleanup_callback(self, callback: Callable[[], None]):
        """Add cleanup callback."""
        self.cleanup_callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start resource monitoring."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Resource monitoring started")
    
    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Resource monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                await self._check_resources()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_resources(self):
        """Check all system resources."""
        timestamp = datetime.utcnow()
        
        # Check CPU usage
        cpu_usage = await self._get_cpu_usage()
        await self._process_resource_usage(
            ResourceType.CPU, cpu_usage, 100.0, timestamp
        )
        
        # Check memory usage
        memory_usage = await self._get_memory_usage()
        await self._process_resource_usage(
            ResourceType.MEMORY, memory_usage['used'], memory_usage['total'], timestamp
        )
        
        # Check disk usage
        disk_usage = await self._get_disk_usage()
        await self._process_resource_usage(
            ResourceType.DISK, disk_usage['used'], disk_usage['total'], timestamp
        )
        
        # Check file descriptors
        fd_usage = await self._get_file_descriptor_usage()
        if fd_usage:
            await self._process_resource_usage(
                ResourceType.FILE_DESCRIPTORS, fd_usage['used'], fd_usage['max'], timestamp
            )
    
    async def _get_cpu_usage(self) -> float:
        """Get CPU usage percentage."""
        # Get CPU usage over a short interval
        return psutil.cpu_percent(interval=0.1)
    
    async def _get_memory_usage(self) -> Dict[str, float]:
        """Get memory usage information."""
        memory = psutil.virtual_memory()
        return {
            'total': memory.total,
            'used': memory.used,
            'available': memory.available,
            'percent': memory.percent
        }
    
    async def _get_disk_usage(self) -> Dict[str, float]:
        """Get disk usage information."""
        # Get usage for root directory
        disk = psutil.disk_usage('/')
        return {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': (disk.used / disk.total) * 100
        }
    
    async def _get_file_descriptor_usage(self) -> Optional[Dict[str, int]]:
        """Get file descriptor usage."""
        try:
            # Get current process file descriptors
            num_fds = self.current_process.num_fds()
            
            # Try to get system limit
            try:
                import resource
                soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
                max_fds = soft_limit
            except:
                # Fallback to a reasonable estimate
                max_fds = 1024
            
            return {
                'used': num_fds,
                'max': max_fds
            }
        except:
            return None
    
    async def _process_resource_usage(self, resource_type: ResourceType, 
                                    current_usage: float, max_usage: float, 
                                    timestamp: datetime):
        """Process resource usage and generate alerts if needed."""
        percentage = (current_usage / max_usage) * 100 if max_usage > 0 else 0
        
        # Determine status
        thresholds = self.thresholds.get(resource_type, ResourceThresholds())
        if percentage >= thresholds.emergency_threshold * 100:
            status = ResourceStatus.EXHAUSTED
            alert_level = AlertLevel.EMERGENCY
        elif percentage >= thresholds.critical_threshold * 100:
            status = ResourceStatus.CRITICAL
            alert_level = AlertLevel.CRITICAL
        elif percentage >= thresholds.warning_threshold * 100:
            status = ResourceStatus.WARNING
            alert_level = AlertLevel.WARNING
        else:
            status = ResourceStatus.HEALTHY
            alert_level = None
        
        # Create usage record
        usage = ResourceUsage(
            resource_type=resource_type,
            current_usage=current_usage,
            max_usage=max_usage,
            percentage=percentage,
            timestamp=timestamp,
            status=status
        )
        
        # Store in history
        with self._lock:
            self.usage_history[resource_type].append(usage)
        
        # Handle alerts
        if alert_level and resource_type not in self.active_alerts:
            await self._create_alert(resource_type, alert_level, usage)
        elif not alert_level and resource_type in self.active_alerts:
            await self._resolve_alert(resource_type)
        
        # Trigger cleanup if critical
        if status in [ResourceStatus.CRITICAL, ResourceStatus.EXHAUSTED]:
            await self._trigger_cleanup(resource_type, usage)
    
    async def _create_alert(self, resource_type: ResourceType, level: AlertLevel, 
                          usage: ResourceUsage):
        """Create a new alert."""
        threshold = self.thresholds.get(resource_type, ResourceThresholds())
        threshold_value = {
            AlertLevel.WARNING: threshold.warning_threshold,
            AlertLevel.CRITICAL: threshold.critical_threshold,
            AlertLevel.EMERGENCY: threshold.emergency_threshold
        }.get(level, 0.0)
        
        alert = ResourceAlert(
            resource_type=resource_type,
            level=level,
            message=f"{resource_type.value} usage is {usage.percentage:.1f}% (threshold: {threshold_value*100:.1f}%)",
            current_usage=usage.percentage,
            threshold=threshold_value * 100,
            timestamp=usage.timestamp
        )
        
        with self._lock:
            self.alerts.append(alert)
            self.active_alerts[resource_type] = alert
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
        
        logger.warning(f"Resource alert: {alert.message}")
    
    async def _resolve_alert(self, resource_type: ResourceType):
        """Resolve an active alert."""
        with self._lock:
            if resource_type in self.active_alerts:
                alert = self.active_alerts[resource_type]
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                del self.active_alerts[resource_type]
                
                logger.info(f"Resource alert resolved: {resource_type.value}")
    
    async def _trigger_cleanup(self, resource_type: ResourceType, usage: ResourceUsage):
        """Trigger resource cleanup."""
        logger.warning(f"Triggering cleanup for {resource_type.value} (usage: {usage.percentage:.1f}%)")
        
        # Run cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in cleanup callback: {e}")
        
        # Built-in cleanup actions
        if resource_type == ResourceType.MEMORY:
            await self._cleanup_memory()
        elif resource_type == ResourceType.DISK:
            await self._cleanup_disk()
    
    async def _cleanup_memory(self):
        """Perform memory cleanup."""
        logger.info("Performing memory cleanup")
        
        # Force garbage collection
        gc.collect()
        
        # Clear caches if available
        try:
            from api.utils.caching import get_cache
            cache = get_cache()
            if hasattr(cache, 'clear'):
                cache.clear()
                logger.info("Cleared application cache")
        except Exception as e:
            logger.debug(f"Could not clear cache: {e}")
    
    async def _cleanup_disk(self):
        """Perform disk cleanup."""
        logger.info("Performing disk cleanup")
        
        # Clean temporary files
        temp_dirs = ['/tmp', '/var/tmp', settings.TEMP_DIR if hasattr(settings, 'TEMP_DIR') else None]
        
        for temp_dir in temp_dirs:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    await self._clean_temp_directory(temp_dir)
                except Exception as e:
                    logger.error(f"Error cleaning {temp_dir}: {e}")
    
    async def _clean_temp_directory(self, directory: str, max_age_hours: int = 24):
        """Clean old files from temporary directory."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_files = 0
        freed_space = 0
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    stat = os.stat(file_path)
                    if stat.st_mtime < cutoff_time:
                        file_size = stat.st_size
                        os.remove(file_path)
                        cleaned_files += 1
                        freed_space += file_size
                except Exception as e:
                    logger.debug(f"Could not remove {file_path}: {e}")
        
        if cleaned_files > 0:
            logger.info(f"Cleaned {cleaned_files} files, freed {freed_space / 1024 / 1024:.1f} MB")
    
    async def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory
        memory = psutil.virtual_memory()
        
        # Disk
        disk = psutil.disk_usage('/')
        
        # Network
        network = psutil.net_io_counters()
        network_io = {
            'bytes_sent': network.bytes_sent,
            'bytes_recv': network.bytes_recv,
            'packets_sent': network.packets_sent,
            'packets_recv': network.packets_recv
        }
        
        # File descriptors
        try:
            file_descriptors = self.current_process.num_fds()
        except:
            file_descriptors = 0
        
        # Threads and processes
        thread_count = threading.active_count()
        process_count = len(psutil.pids())
        
        # Load average
        try:
            load_average = list(psutil.getloadavg())
        except:
            load_average = [0.0, 0.0, 0.0]
        
        # Uptime
        uptime = time.time() - psutil.boot_time()
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=(disk.used / disk.total) * 100,
            network_io=network_io,
            file_descriptors=file_descriptors,
            thread_count=thread_count,
            process_count=process_count,
            load_average=load_average,
            uptime=uptime,
            timestamp=datetime.utcnow()
        )
    
    async def get_process_metrics(self) -> ProcessMetrics:
        """Get current process metrics."""
        process = self.current_process
        
        return ProcessMetrics(
            pid=process.pid,
            name=process.name(),
            cpu_percent=process.cpu_percent(),
            memory_percent=process.memory_percent(),
            memory_rss=process.memory_info().rss,
            memory_vms=process.memory_info().vms,
            num_threads=process.num_threads(),
            num_fds=process.num_fds() if hasattr(process, 'num_fds') else 0,
            create_time=process.create_time(),
            status=process.status(),
            timestamp=datetime.utcnow()
        )
    
    async def get_resource_usage_history(self, resource_type: ResourceType, 
                                       hours: int = 1) -> List[ResourceUsage]:
        """Get resource usage history."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            history = list(self.usage_history[resource_type])
        
        return [usage for usage in history if usage.timestamp >= cutoff_time]
    
    async def get_resource_statistics(self, resource_type: ResourceType, 
                                    hours: int = 1) -> Dict[str, float]:
        """Get resource usage statistics."""
        history = await self.get_resource_usage_history(resource_type, hours)
        
        if not history:
            return {}
        
        percentages = [usage.percentage for usage in history]
        
        return {
            'min': min(percentages),
            'max': max(percentages),
            'avg': statistics.mean(percentages),
            'median': statistics.median(percentages),
            'std_dev': statistics.stdev(percentages) if len(percentages) > 1 else 0.0,
            'current': percentages[-1] if percentages else 0.0,
            'samples': len(percentages)
        }
    
    async def get_active_alerts(self) -> List[ResourceAlert]:
        """Get active alerts."""
        with self._lock:
            return list(self.active_alerts.values())
    
    async def get_alert_history(self, hours: int = 24) -> List[ResourceAlert]:
        """Get alert history."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            return [alert for alert in self.alerts if alert.timestamp >= cutoff_time]
    
    async def check_resource_health(self) -> Dict[str, Any]:
        """Check overall resource health."""
        health_status = {
            'overall_status': ResourceStatus.HEALTHY,
            'resources': {},
            'active_alerts': len(self.active_alerts),
            'recommendations': []
        }
        
        # Check each resource type
        for resource_type in ResourceType:
            if resource_type in self.usage_history:
                with self._lock:
                    recent_usage = list(self.usage_history[resource_type])[-10:]
                
                if recent_usage:
                    latest_usage = recent_usage[-1]
                    avg_usage = statistics.mean([u.percentage for u in recent_usage])
                    
                    health_status['resources'][resource_type.value] = {
                        'status': latest_usage.status,
                        'current_usage': latest_usage.percentage,
                        'avg_usage': avg_usage,
                        'trend': self._calculate_trend(recent_usage)
                    }
                    
                    # Update overall status
                    if latest_usage.status == ResourceStatus.EXHAUSTED:
                        health_status['overall_status'] = ResourceStatus.EXHAUSTED
                    elif (latest_usage.status == ResourceStatus.CRITICAL and 
                          health_status['overall_status'] != ResourceStatus.EXHAUSTED):
                        health_status['overall_status'] = ResourceStatus.CRITICAL
                    elif (latest_usage.status == ResourceStatus.WARNING and 
                          health_status['overall_status'] == ResourceStatus.HEALTHY):
                        health_status['overall_status'] = ResourceStatus.WARNING
        
        # Generate recommendations
        health_status['recommendations'] = await self._generate_recommendations(health_status)
        
        return health_status
    
    def _calculate_trend(self, usage_history: List[ResourceUsage]) -> str:
        """Calculate usage trend."""
        if len(usage_history) < 2:
            return "stable"
        
        percentages = [u.percentage for u in usage_history]
        
        # Simple linear trend
        x = list(range(len(percentages)))
        n = len(x)
        
        if n < 2:
            return "stable"
        
        # Calculate slope
        sum_x = sum(x)
        sum_y = sum(percentages)
        sum_xy = sum(x[i] * percentages[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        
        if slope > 1.0:
            return "increasing"
        elif slope < -1.0:
            return "decreasing"
        else:
            return "stable"
    
    async def _generate_recommendations(self, health_status: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        for resource_name, resource_info in health_status['resources'].items():
            if resource_info['status'] in [ResourceStatus.WARNING, ResourceStatus.CRITICAL]:
                if resource_name == 'memory':
                    recommendations.append("Consider increasing memory allocation or optimizing memory usage")
                elif resource_name == 'cpu':
                    recommendations.append("Consider scaling horizontally or optimizing CPU-intensive operations")
                elif resource_name == 'disk':
                    recommendations.append("Clean up temporary files or increase disk space")
                elif resource_name == 'file_descriptors':
                    recommendations.append("Check for file descriptor leaks or increase limits")
            
            if resource_info['trend'] == 'increasing':
                recommendations.append(f"{resource_name} usage is trending upward - monitor closely")
        
        return recommendations


class ResourcePool:
    """Generic resource pool with monitoring."""
    
    def __init__(self, name: str, max_size: int = 10, 
                 create_func: Optional[Callable] = None,
                 destroy_func: Optional[Callable] = None,
                 health_check_func: Optional[Callable] = None):
        self.name = name
        self.max_size = max_size
        self.create_func = create_func
        self.destroy_func = destroy_func
        self.health_check_func = health_check_func
        
        self.pool: List[Any] = []
        self.in_use: set = set()
        self.created_count = 0
        self.destroyed_count = 0
        self.borrowed_count = 0
        self.returned_count = 0
        
        self._lock = asyncio.Lock()
        
        logger.info(f"Resource pool '{name}' initialized with max size {max_size}")
    
    async def borrow(self) -> Any:
        """Borrow a resource from the pool."""
        async with self._lock:
            # Try to get from pool
            if self.pool:
                resource = self.pool.pop()
                
                # Health check if available
                if self.health_check_func:
                    try:
                        if not await self.health_check_func(resource):
                            # Resource is unhealthy, destroy and create new
                            if self.destroy_func:
                                await self.destroy_func(resource)
                            self.destroyed_count += 1
                            resource = await self._create_resource()
                    except Exception as e:
                        logger.warning(f"Health check failed for resource in pool '{self.name}': {e}")
                        resource = await self._create_resource()
            else:
                # Create new resource
                resource = await self._create_resource()
            
            self.in_use.add(id(resource))
            self.borrowed_count += 1
            return resource
    
    async def return_resource(self, resource: Any):
        """Return a resource to the pool."""
        async with self._lock:
            resource_id = id(resource)
            
            if resource_id not in self.in_use:
                logger.warning(f"Attempting to return unknown resource to pool '{self.name}'")
                return
            
            self.in_use.remove(resource_id)
            self.returned_count += 1
            
            # Add back to pool if not at capacity
            if len(self.pool) < self.max_size:
                self.pool.append(resource)
            else:
                # Pool is full, destroy resource
                if self.destroy_func:
                    try:
                        await self.destroy_func(resource)
                    except Exception as e:
                        logger.error(f"Error destroying resource in pool '{self.name}': {e}")
                self.destroyed_count += 1
    
    async def _create_resource(self) -> Any:
        """Create a new resource."""
        if self.create_func:
            try:
                resource = await self.create_func()
                self.created_count += 1
                return resource
            except Exception as e:
                logger.error(f"Error creating resource in pool '{self.name}': {e}")
                raise
        else:
            raise NotImplementedError("No create function provided")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get pool metrics."""
        async with self._lock:
            return {
                'name': self.name,
                'max_size': self.max_size,
                'available': len(self.pool),
                'in_use': len(self.in_use),
                'created_count': self.created_count,
                'destroyed_count': self.destroyed_count,
                'borrowed_count': self.borrowed_count,
                'returned_count': self.returned_count,
                'utilization': len(self.in_use) / self.max_size if self.max_size > 0 else 0.0
            }
    
    async def cleanup(self):
        """Clean up all resources in the pool."""
        async with self._lock:
            if self.destroy_func:
                for resource in self.pool:
                    try:
                        await self.destroy_func(resource)
                        self.destroyed_count += 1
                    except Exception as e:
                        logger.error(f"Error destroying resource during cleanup: {e}")
            
            self.pool.clear()
            self.in_use.clear()


# Global resource monitor
resource_monitor = ResourceMonitor()


def get_resource_monitor() -> ResourceMonitor:
    """Get the global resource monitor."""
    return resource_monitor


# Context manager for resource monitoring
class resource_context:
    """Context manager for monitoring resource usage during operations."""
    
    def __init__(self, operation_name: str, monitor: Optional[ResourceMonitor] = None):
        self.operation_name = operation_name
        self.monitor = monitor or resource_monitor
        self.start_metrics: Optional[SystemMetrics] = None
        self.end_metrics: Optional[SystemMetrics] = None
    
    async def __aenter__(self):
        self.start_metrics = await self.monitor.get_system_metrics()
        logger.debug(f"Starting resource monitoring for operation: {self.operation_name}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_metrics = await self.monitor.get_system_metrics()
        
        # Calculate resource usage during operation
        if self.start_metrics and self.end_metrics:
            cpu_diff = self.end_metrics.cpu_percent - self.start_metrics.cpu_percent
            memory_diff = self.end_metrics.memory_percent - self.start_metrics.memory_percent
            
            logger.info(
                f"Operation '{self.operation_name}' completed. "
                f"CPU change: {cpu_diff:+.1f}%, Memory change: {memory_diff:+.1f}%"
            )
    
    def get_resource_usage(self) -> Optional[Dict[str, float]]:
        """Get resource usage during the operation."""
        if not (self.start_metrics and self.end_metrics):
            return None
        
        return {
            'cpu_change': self.end_metrics.cpu_percent - self.start_metrics.cpu_percent,
            'memory_change': self.end_metrics.memory_percent - self.start_metrics.memory_percent,
            'duration': (self.end_metrics.timestamp - self.start_metrics.timestamp).total_seconds()
        }