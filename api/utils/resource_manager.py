#!/usr/bin/env python3
"""
Resource management module for monitoring and controlling system resources.
Provides memory monitoring, disk space checks, processing limits, and cleanup mechanisms.
"""

import os
import psutil
import asyncio
import threading
import time
import shutil
import tempfile
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import weakref
import gc
import signal
import sys
from contextlib import asynccontextmanager, contextmanager

from api.core.config import get_settings
from api.utils.structured_logger import get_logger, LogCategory


class ResourceType(Enum):
    """Resource type enumeration."""
    MEMORY = "memory"
    DISK = "disk"
    CPU = "cpu"
    NETWORK = "network"
    FILE_HANDLES = "file_handles"
    THREADS = "threads"
    PROCESSES = "processes"


class AlertLevel(Enum):
    """Alert level enumeration."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ResourceThresholds:
    """Resource threshold configuration."""
    memory_warning_percent: float = 80.0
    memory_critical_percent: float = 90.0
    memory_emergency_percent: float = 95.0
    
    disk_warning_percent: float = 80.0
    disk_critical_percent: float = 90.0
    disk_emergency_percent: float = 95.0
    
    cpu_warning_percent: float = 80.0
    cpu_critical_percent: float = 90.0
    cpu_emergency_percent: float = 95.0
    
    max_file_handles: int = 1000
    max_threads: int = 100
    max_processes: int = 50
    
    cleanup_interval_seconds: int = 300  # 5 minutes
    monitoring_interval_seconds: int = 30  # 30 seconds


@dataclass
class ResourceUsage:
    """Current resource usage information."""
    timestamp: datetime
    memory_percent: float
    memory_available_mb: float
    memory_used_mb: float
    memory_total_mb: float
    
    disk_percent: float
    disk_free_gb: float
    disk_used_gb: float
    disk_total_gb: float
    
    cpu_percent: float
    cpu_count: int
    load_average: Tuple[float, float, float]
    
    file_handles: int
    thread_count: int
    process_count: int
    
    network_connections: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'memory': {
                'percent': self.memory_percent,
                'available_mb': self.memory_available_mb,
                'used_mb': self.memory_used_mb,
                'total_mb': self.memory_total_mb
            },
            'disk': {
                'percent': self.disk_percent,
                'free_gb': self.disk_free_gb,
                'used_gb': self.disk_used_gb,
                'total_gb': self.disk_total_gb
            },
            'cpu': {
                'percent': self.cpu_percent,
                'count': self.cpu_count,
                'load_average': self.load_average
            },
            'handles': {
                'files': self.file_handles,
                'threads': self.thread_count,
                'processes': self.process_count,
                'network_connections': self.network_connections
            }
        }


@dataclass
class ResourceAlert:
    """Resource alert information."""
    resource_type: ResourceType
    level: AlertLevel
    message: str
    current_value: float
    threshold_value: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResourceMonitor:
    """System resource monitor."""
    
    def __init__(self, thresholds: Optional[ResourceThresholds] = None):
        self.thresholds = thresholds or ResourceThresholds()
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        self._usage_history: List[ResourceUsage] = []
        self._max_history_size = 1000
        
        self._alert_callbacks: List[Callable[[ResourceAlert], None]] = []
        self._cleanup_callbacks: List[Callable[[], None]] = []
        
        # Track managed resources
        self._managed_files: weakref.WeakSet = weakref.WeakSet()
        self._managed_processes: List[psutil.Process] = []
        self._temp_directories: List[Path] = []
        
        # Performance tracking
        self._performance_metrics: Dict[str, List[float]] = {
            'memory_usage': [],
            'cpu_usage': [],
            'disk_usage': [],
            'response_times': []
        }
    
    def get_current_usage(self) -> ResourceUsage:
        """Get current system resource usage."""
        try:
            # Memory information
            memory = psutil.virtual_memory()
            
            # Disk information (for current working directory)
            disk = psutil.disk_usage('.')
            
            # CPU information
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Load average (Unix-like systems)
            try:
                load_avg = os.getloadavg()
            except (OSError, AttributeError):
                load_avg = (0.0, 0.0, 0.0)
            
            # Process information
            current_process = psutil.Process()
            
            try:
                file_handles = len(current_process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                file_handles = 0
            
            try:
                thread_count = current_process.num_threads()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                thread_count = 0
            
            # System-wide process count
            try:
                process_count = len(psutil.pids())
            except psutil.AccessDenied:
                process_count = 0
            
            # Network connections
            try:
                network_connections = len(psutil.net_connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                network_connections = 0
            
            return ResourceUsage(
                timestamp=datetime.now(),
                memory_percent=memory.percent,
                memory_available_mb=memory.available / (1024 * 1024),
                memory_used_mb=memory.used / (1024 * 1024),
                memory_total_mb=memory.total / (1024 * 1024),
                
                disk_percent=(disk.used / disk.total) * 100,
                disk_free_gb=disk.free / (1024 * 1024 * 1024),
                disk_used_gb=disk.used / (1024 * 1024 * 1024),
                disk_total_gb=disk.total / (1024 * 1024 * 1024),
                
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                load_average=load_avg,
                
                file_handles=file_handles,
                thread_count=thread_count,
                process_count=process_count,
                network_connections=network_connections
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get resource usage: {e}", 
                            category=LogCategory.SYSTEM, error=e)
            raise
    
    def check_thresholds(self, usage: ResourceUsage) -> List[ResourceAlert]:
        """Check resource usage against thresholds."""
        alerts = []
        
        # Memory checks
        if usage.memory_percent >= self.thresholds.memory_emergency_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.MEMORY,
                level=AlertLevel.EMERGENCY,
                message=f"Memory usage critical: {usage.memory_percent:.1f}%",
                current_value=usage.memory_percent,
                threshold_value=self.thresholds.memory_emergency_percent,
                timestamp=usage.timestamp
            ))
        elif usage.memory_percent >= self.thresholds.memory_critical_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.MEMORY,
                level=AlertLevel.CRITICAL,
                message=f"Memory usage high: {usage.memory_percent:.1f}%",
                current_value=usage.memory_percent,
                threshold_value=self.thresholds.memory_critical_percent,
                timestamp=usage.timestamp
            ))
        elif usage.memory_percent >= self.thresholds.memory_warning_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.MEMORY,
                level=AlertLevel.WARNING,
                message=f"Memory usage elevated: {usage.memory_percent:.1f}%",
                current_value=usage.memory_percent,
                threshold_value=self.thresholds.memory_warning_percent,
                timestamp=usage.timestamp
            ))
        
        # Disk checks
        if usage.disk_percent >= self.thresholds.disk_emergency_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.DISK,
                level=AlertLevel.EMERGENCY,
                message=f"Disk usage critical: {usage.disk_percent:.1f}%",
                current_value=usage.disk_percent,
                threshold_value=self.thresholds.disk_emergency_percent,
                timestamp=usage.timestamp
            ))
        elif usage.disk_percent >= self.thresholds.disk_critical_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.DISK,
                level=AlertLevel.CRITICAL,
                message=f"Disk usage high: {usage.disk_percent:.1f}%",
                current_value=usage.disk_percent,
                threshold_value=self.thresholds.disk_critical_percent,
                timestamp=usage.timestamp
            ))
        elif usage.disk_percent >= self.thresholds.disk_warning_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.DISK,
                level=AlertLevel.WARNING,
                message=f"Disk usage elevated: {usage.disk_percent:.1f}%",
                current_value=usage.disk_percent,
                threshold_value=self.thresholds.disk_warning_percent,
                timestamp=usage.timestamp
            ))
        
        # CPU checks
        if usage.cpu_percent >= self.thresholds.cpu_emergency_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.CPU,
                level=AlertLevel.EMERGENCY,
                message=f"CPU usage critical: {usage.cpu_percent:.1f}%",
                current_value=usage.cpu_percent,
                threshold_value=self.thresholds.cpu_emergency_percent,
                timestamp=usage.timestamp
            ))
        elif usage.cpu_percent >= self.thresholds.cpu_critical_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.CPU,
                level=AlertLevel.CRITICAL,
                message=f"CPU usage high: {usage.cpu_percent:.1f}%",
                current_value=usage.cpu_percent,
                threshold_value=self.thresholds.cpu_critical_percent,
                timestamp=usage.timestamp
            ))
        elif usage.cpu_percent >= self.thresholds.cpu_warning_percent:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.CPU,
                level=AlertLevel.WARNING,
                message=f"CPU usage elevated: {usage.cpu_percent:.1f}%",
                current_value=usage.cpu_percent,
                threshold_value=self.thresholds.cpu_warning_percent,
                timestamp=usage.timestamp
            ))
        
        # File handle checks
        if usage.file_handles >= self.thresholds.max_file_handles:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.FILE_HANDLES,
                level=AlertLevel.CRITICAL,
                message=f"Too many file handles: {usage.file_handles}",
                current_value=usage.file_handles,
                threshold_value=self.thresholds.max_file_handles,
                timestamp=usage.timestamp
            ))
        
        # Thread count checks
        if usage.thread_count >= self.thresholds.max_threads:
            alerts.append(ResourceAlert(
                resource_type=ResourceType.THREADS,
                level=AlertLevel.CRITICAL,
                message=f"Too many threads: {usage.thread_count}",
                current_value=usage.thread_count,
                threshold_value=self.thresholds.max_threads,
                timestamp=usage.timestamp
            ))
        
        return alerts
    
    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]):
        """Add alert callback."""
        self._alert_callbacks.append(callback)
    
    def add_cleanup_callback(self, callback: Callable[[], None]):
        """Add cleanup callback."""
        self._cleanup_callbacks.append(callback)
    
    def _handle_alerts(self, alerts: List[ResourceAlert]):
        """Handle resource alerts."""
        for alert in alerts:
            # Log alert
            log_level = {
                AlertLevel.INFO: 'info',
                AlertLevel.WARNING: 'warning',
                AlertLevel.CRITICAL: 'error',
                AlertLevel.EMERGENCY: 'critical'
            }[alert.level]
            
            getattr(self.logger, log_level)(
                alert.message,
                category=LogCategory.SYSTEM,
                tags=['resource_alert', alert.resource_type.value, alert.level.value],
                resource_type=alert.resource_type.value,
                alert_level=alert.level.value,
                current_value=alert.current_value,
                threshold_value=alert.threshold_value
            )
            
            # Call alert callbacks
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Alert callback failed: {e}", 
                                    category=LogCategory.SYSTEM, error=e)
            
            # Emergency actions
            if alert.level == AlertLevel.EMERGENCY:
                self._handle_emergency(alert)
    
    def _handle_emergency(self, alert: ResourceAlert):
        """Handle emergency resource situations."""
        self.logger.critical(
            f"Emergency resource situation: {alert.message}",
            category=LogCategory.SYSTEM,
            tags=['emergency', 'resource_critical']
        )
        
        if alert.resource_type == ResourceType.MEMORY:
            # Force garbage collection
            gc.collect()
            
            # Run cleanup
            self._run_cleanup()
            
            # If still critical, consider more drastic measures
            current_usage = self.get_current_usage()
            if current_usage.memory_percent >= self.thresholds.memory_emergency_percent:
                self.logger.critical(
                    "Memory still critical after cleanup, consider process restart",
                    category=LogCategory.SYSTEM
                )
        
        elif alert.resource_type == ResourceType.DISK:
            # Run disk cleanup
            self._cleanup_disk_space()
        
        elif alert.resource_type == ResourceType.CPU:
            # Log high CPU usage for investigation
            self.logger.critical(
                "High CPU usage detected, check for runaway processes",
                category=LogCategory.SYSTEM
            )
    
    async def start_monitoring(self):
        """Start resource monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self.logger.info("Starting resource monitoring", category=LogCategory.SYSTEM)
        
        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_monitoring(self):
        """Stop resource monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        self.logger.info("Stopping resource monitoring", category=LogCategory.SYSTEM)
        
        # Cancel tasks
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                # Get current usage
                usage = self.get_current_usage()
                
                # Add to history
                self._usage_history.append(usage)
                if len(self._usage_history) > self._max_history_size:
                    self._usage_history.pop(0)
                
                # Check thresholds
                alerts = self.check_thresholds(usage)
                if alerts:
                    self._handle_alerts(alerts)
                
                # Update performance metrics
                self._update_performance_metrics(usage)
                
                # Log periodic status
                if len(self._usage_history) % 10 == 0:  # Every 10 intervals
                    self.logger.info(
                        f"Resource status - Memory: {usage.memory_percent:.1f}%, "
                        f"Disk: {usage.disk_percent:.1f}%, CPU: {usage.cpu_percent:.1f}%",
                        category=LogCategory.SYSTEM,
                        performance_metrics=usage.to_dict()
                    )
                
                await asyncio.sleep(self.thresholds.monitoring_interval_seconds)
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}", 
                                category=LogCategory.SYSTEM, error=e)
                await asyncio.sleep(5)  # Short delay before retry
    
    async def _cleanup_loop(self):
        """Cleanup loop."""
        while self._monitoring:
            try:
                await asyncio.sleep(self.thresholds.cleanup_interval_seconds)
                self._run_cleanup()
                
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {e}", 
                                category=LogCategory.SYSTEM, error=e)
    
    def _run_cleanup(self):
        """Run cleanup operations."""
        self.logger.debug("Running resource cleanup", category=LogCategory.SYSTEM)
        
        # Force garbage collection
        collected = gc.collect()
        if collected > 0:
            self.logger.debug(f"Garbage collected {collected} objects", 
                            category=LogCategory.SYSTEM)
        
        # Clean up temporary files
        self._cleanup_temp_files()
        
        # Clean up managed processes
        self._cleanup_processes()
        
        # Call cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Cleanup callback failed: {e}", 
                              category=LogCategory.SYSTEM, error=e)
    
    def _cleanup_temp_files(self):
        """Clean up temporary files and directories."""
        # Clean up tracked temporary directories
        for temp_dir in self._temp_directories[:]:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    self.logger.debug(f"Cleaned up temp directory: {temp_dir}", 
                                    category=LogCategory.SYSTEM)
                self._temp_directories.remove(temp_dir)
            except Exception as e:
                self.logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}", 
                                  category=LogCategory.SYSTEM)
        
        # Clean up system temp directory
        temp_dir = Path(tempfile.gettempdir())
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        try:
            for item in temp_dir.iterdir():
                if item.name.startswith('clip_') or item.name.startswith('tmp'):
                    try:
                        stat = item.stat()
                        if datetime.fromtimestamp(stat.st_mtime) < cutoff_time:
                            if item.is_file():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
                            self.logger.debug(f"Cleaned up old temp file: {item}", 
                                            category=LogCategory.SYSTEM)
                    except Exception:
                        pass  # Ignore errors for individual files
        except Exception as e:
            self.logger.warning(f"Failed to clean temp directory: {e}", 
                              category=LogCategory.SYSTEM)
    
    def _cleanup_processes(self):
        """Clean up managed processes."""
        for process in self._managed_processes[:]:
            try:
                if process.is_running():
                    # Check if process should be terminated
                    create_time = datetime.fromtimestamp(process.create_time())
                    if datetime.now() - create_time > timedelta(hours=1):
                        process.terminate()
                        self.logger.info(f"Terminated long-running process: {process.pid}", 
                                       category=LogCategory.SYSTEM)
                else:
                    self._managed_processes.remove(process)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._managed_processes.remove(process)
    
    def _cleanup_disk_space(self):
        """Clean up disk space."""
        self.logger.info("Running disk space cleanup", category=LogCategory.SYSTEM)
        
        # Clean up log files older than 7 days
        log_dir = Path("logs")
        if log_dir.exists():
            cutoff_time = datetime.now() - timedelta(days=7)
            for log_file in log_dir.glob("*.log*"):
                try:
                    if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff_time:
                        log_file.unlink()
                        self.logger.debug(f"Cleaned up old log file: {log_file}", 
                                        category=LogCategory.SYSTEM)
                except Exception:
                    pass
        
        # Clean up cache directories
        cache_dirs = ["cache", "tmp", ".cache"]
        for cache_dir_name in cache_dirs:
            cache_dir = Path(cache_dir_name)
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                    cache_dir.mkdir(exist_ok=True)
                    self.logger.debug(f"Cleaned up cache directory: {cache_dir}", 
                                    category=LogCategory.SYSTEM)
                except Exception as e:
                    self.logger.warning(f"Failed to clean cache directory {cache_dir}: {e}", 
                                      category=LogCategory.SYSTEM)
    
    def _update_performance_metrics(self, usage: ResourceUsage):
        """Update performance metrics."""
        max_metrics = 100  # Keep last 100 measurements
        
        self._performance_metrics['memory_usage'].append(usage.memory_percent)
        self._performance_metrics['cpu_usage'].append(usage.cpu_percent)
        self._performance_metrics['disk_usage'].append(usage.disk_percent)
        
        # Trim metrics
        for metric_list in self._performance_metrics.values():
            if len(metric_list) > max_metrics:
                metric_list.pop(0)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        summary = {}
        
        for metric_name, values in self._performance_metrics.items():
            if values:
                summary[metric_name] = {
                    'current': values[-1],
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'count': len(values)
                }
        
        return summary
    
    def register_temp_directory(self, path: Path):
        """Register a temporary directory for cleanup."""
        self._temp_directories.append(path)
    
    def register_process(self, process: psutil.Process):
        """Register a process for monitoring."""
        self._managed_processes.append(process)
    
    @contextmanager
    def monitor_memory_usage(self, operation_name: str):
        """Context manager to monitor memory usage of an operation."""
        start_usage = self.get_current_usage()
        start_time = time.time()
        
        try:
            yield
        finally:
            end_usage = self.get_current_usage()
            duration = time.time() - start_time
            
            memory_delta = end_usage.memory_used_mb - start_usage.memory_used_mb
            
            self.logger.info(
                f"Operation {operation_name} completed",
                category=LogCategory.PERFORMANCE,
                performance_metrics={
                    'duration_seconds': duration,
                    'memory_delta_mb': memory_delta,
                    'memory_start_mb': start_usage.memory_used_mb,
                    'memory_end_mb': end_usage.memory_used_mb
                },
                tags=['memory_monitoring']
            )
    
    @asynccontextmanager
    async def monitor_async_operation(self, operation_name: str):
        """Async context manager to monitor resource usage of an operation."""
        start_usage = self.get_current_usage()
        start_time = time.time()
        
        try:
            yield
        finally:
            end_usage = self.get_current_usage()
            duration = time.time() - start_time
            
            memory_delta = end_usage.memory_used_mb - start_usage.memory_used_mb
            cpu_avg = (start_usage.cpu_percent + end_usage.cpu_percent) / 2
            
            self.logger.info(
                f"Async operation {operation_name} completed",
                category=LogCategory.PERFORMANCE,
                performance_metrics={
                    'duration_seconds': duration,
                    'memory_delta_mb': memory_delta,
                    'cpu_average_percent': cpu_avg,
                    'memory_start_mb': start_usage.memory_used_mb,
                    'memory_end_mb': end_usage.memory_used_mb
                },
                tags=['async_monitoring']
            )


class ResourceLimiter:
    """Resource usage limiter."""
    
    def __init__(self, monitor: ResourceMonitor):
        self.monitor = monitor
        self.logger = get_logger(__name__)
        
        self._active_operations = 0
        self._max_concurrent_operations = 10
        self._operation_lock = asyncio.Semaphore(self._max_concurrent_operations)
    
    async def check_resources_available(self) -> bool:
        """Check if resources are available for new operations."""
        usage = self.monitor.get_current_usage()
        
        # Check memory
        if usage.memory_percent > self.monitor.thresholds.memory_critical_percent:
            self.logger.warning(
                "Memory usage too high for new operations",
                category=LogCategory.SYSTEM,
                current_memory_percent=usage.memory_percent
            )
            return False
        
        # Check disk
        if usage.disk_percent > self.monitor.thresholds.disk_critical_percent:
            self.logger.warning(
                "Disk usage too high for new operations",
                category=LogCategory.SYSTEM,
                current_disk_percent=usage.disk_percent
            )
            return False
        
        # Check CPU
        if usage.cpu_percent > self.monitor.thresholds.cpu_critical_percent:
            self.logger.warning(
                "CPU usage too high for new operations",
                category=LogCategory.SYSTEM,
                current_cpu_percent=usage.cpu_percent
            )
            return False
        
        return True
    
    @asynccontextmanager
    async def limit_operation(self, operation_name: str):
        """Context manager to limit concurrent operations."""
        # Check if resources are available
        if not await self.check_resources_available():
            raise RuntimeError("Insufficient resources for operation")
        
        # Acquire semaphore
        async with self._operation_lock:
            self._active_operations += 1
            
            try:
                self.logger.debug(
                    f"Starting limited operation: {operation_name}",
                    category=LogCategory.SYSTEM,
                    active_operations=self._active_operations
                )
                
                async with self.monitor.monitor_async_operation(operation_name):
                    yield
                    
            finally:
                self._active_operations -= 1
                self.logger.debug(
                    f"Completed limited operation: {operation_name}",
                    category=LogCategory.SYSTEM,
                    active_operations=self._active_operations
                )


# Global resource monitor instance
_resource_monitor: Optional[ResourceMonitor] = None
_resource_limiter: Optional[ResourceLimiter] = None


def get_resource_monitor() -> ResourceMonitor:
    """Get global resource monitor instance."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


def get_resource_limiter() -> ResourceLimiter:
    """Get global resource limiter instance."""
    global _resource_limiter
    if _resource_limiter is None:
        _resource_limiter = ResourceLimiter(get_resource_monitor())
    return _resource_limiter


# Signal handlers for graceful shutdown
def _signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger = get_logger(__name__)
    logger.info(f"Received signal {signum}, initiating graceful shutdown", 
               category=LogCategory.SYSTEM)
    
    # Run cleanup
    monitor = get_resource_monitor()
    monitor._run_cleanup()
    
    # Exit
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)