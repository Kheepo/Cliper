#!/usr/bin/env python3
"""
Comprehensive resource management module for production environments.
Handles memory monitoring, disk space checks, processing limits, and cleanup mechanisms.
"""

import asyncio
import psutil
import gc
import os
import shutil
import time
import threading
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import weakref
from contextlib import asynccontextmanager, contextmanager
import tempfile
import signal
import sys
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing

from sqlalchemy.orm import Session
from redis import Redis

from .config import get_settings
from .logging_config import get_logger
from ..database.connection import get_db
from ..services.redis_service import get_redis


class ResourceType(Enum):
    """Resource type enumeration."""
    MEMORY = "memory"
    DISK = "disk"
    CPU = "cpu"
    NETWORK = "network"
    DATABASE = "database"
    REDIS = "redis"
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
class ResourceThreshold:
    """Resource threshold configuration."""
    warning_level: float
    critical_level: float
    emergency_level: float
    unit: str = "%"
    enabled: bool = True


@dataclass
class ResourceUsage:
    """Current resource usage information."""
    resource_type: ResourceType
    current_value: float
    max_value: float
    percentage: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceAlert:
    """Resource alert information."""
    resource_type: ResourceType
    level: AlertLevel
    message: str
    current_value: float
    threshold_value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None


class ResourceMonitor:
    """Comprehensive resource monitoring system."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.monitoring_active = False
        self.monitoring_task = None
        self.alerts: List[ResourceAlert] = []
        self.usage_history: Dict[ResourceType, List[ResourceUsage]] = {}
        self.callbacks: Dict[ResourceType, List[Callable]] = {}
        self.cleanup_tasks: List[Callable] = []
        self.max_history_size = 1000
        
        # Default thresholds
        self.thresholds = {
            ResourceType.MEMORY: ResourceThreshold(70.0, 85.0, 95.0),
            ResourceType.DISK: ResourceThreshold(80.0, 90.0, 95.0),
            ResourceType.CPU: ResourceThreshold(80.0, 90.0, 95.0),
            ResourceType.DATABASE: ResourceThreshold(80.0, 90.0, 95.0),
            ResourceType.REDIS: ResourceThreshold(80.0, 90.0, 95.0),
            ResourceType.FILE_HANDLES: ResourceThreshold(80.0, 90.0, 95.0),
            ResourceType.THREADS: ResourceThreshold(80.0, 90.0, 95.0),
        }
        
        # Resource limits
        self.limits = {
            'max_memory_mb': self.settings.MAX_MEMORY_MB,
            'max_disk_usage_gb': self.settings.MAX_DISK_USAGE_GB,
            'max_concurrent_tasks': self.settings.MAX_CONCURRENT_TASKS,
            'max_file_handles': 1000,
            'max_threads': 100,
            'max_processes': multiprocessing.cpu_count() * 2
        }
        
        # Active resource tracking
        self.active_tasks = set()
        self.active_files = weakref.WeakSet()
        self.active_connections = weakref.WeakSet()
        
        # Cleanup configuration
        self.cleanup_config = {
            'temp_files_max_age_hours': 24,
            'log_files_max_age_days': 7,
            'cache_files_max_age_hours': 6,
            'failed_tasks_max_age_hours': 48,
            'completed_tasks_max_age_days': 30
        }
    
    def set_threshold(self, resource_type: ResourceType, threshold: ResourceThreshold):
        """Set resource threshold."""
        self.thresholds[resource_type] = threshold
        self.logger.info(
            f"Resource threshold updated for {resource_type.value}",
            resource_type=resource_type.value,
            threshold=threshold.__dict__
        )
    
    def add_callback(self, resource_type: ResourceType, callback: Callable):
        """Add callback for resource alerts."""
        if resource_type not in self.callbacks:
            self.callbacks[resource_type] = []
        self.callbacks[resource_type].append(callback)
    
    def add_cleanup_task(self, task: Callable):
        """Add cleanup task."""
        self.cleanup_tasks.append(task)
    
    async def start_monitoring(self, interval_seconds: int = 30):
        """Start resource monitoring."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )
        
        self.logger.info(
            "Resource monitoring started",
            interval_seconds=interval_seconds
        )
    
    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Resource monitoring stopped")
    
    async def _monitoring_loop(self, interval_seconds: int):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                await self._check_all_resources()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    "Error in resource monitoring loop",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    exc_info=True
                )
                await asyncio.sleep(interval_seconds)
    
    async def _check_all_resources(self):
        """Check all monitored resources."""
        tasks = [
            self._check_memory(),
            self._check_disk(),
            self._check_cpu(),
            self._check_database(),
            self._check_redis(),
            self._check_file_handles(),
            self._check_threads()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(
                    f"Error checking resource {i}",
                    error_type=type(result).__name__,
                    error_message=str(result)
                )
    
    async def _check_memory(self) -> ResourceUsage:
        """Check memory usage."""
        memory = psutil.virtual_memory()
        
        usage = ResourceUsage(
            resource_type=ResourceType.MEMORY,
            current_value=memory.used / (1024 * 1024),  # MB
            max_value=memory.total / (1024 * 1024),  # MB
            percentage=memory.percent,
            unit="MB",
            details={
                'available_mb': memory.available / (1024 * 1024),
                'cached_mb': memory.cached / (1024 * 1024) if hasattr(memory, 'cached') else 0,
                'buffers_mb': memory.buffers / (1024 * 1024) if hasattr(memory, 'buffers') else 0
            }
        )
        
        await self._process_usage(usage)
        return usage
    
    async def _check_disk(self) -> ResourceUsage:
        """Check disk usage."""
        disk = psutil.disk_usage('/')
        
        usage = ResourceUsage(
            resource_type=ResourceType.DISK,
            current_value=disk.used / (1024 * 1024 * 1024),  # GB
            max_value=disk.total / (1024 * 1024 * 1024),  # GB
            percentage=(disk.used / disk.total) * 100,
            unit="GB",
            details={
                'free_gb': disk.free / (1024 * 1024 * 1024),
                'temp_dir_size_mb': await self._get_directory_size(tempfile.gettempdir()) / (1024 * 1024)
            }
        )
        
        await self._process_usage(usage)
        return usage
    
    async def _check_cpu(self) -> ResourceUsage:
        """Check CPU usage."""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            current_value=cpu_percent,
            max_value=100.0,
            percentage=cpu_percent,
            unit="%",
            details={
                'cpu_count': cpu_count,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None,
                'per_cpu': psutil.cpu_percent(percpu=True)
            }
        )
        
        await self._process_usage(usage)
        return usage
    
    async def _check_database(self) -> ResourceUsage:
        """Check database connection usage."""
        try:
            # This would need to be implemented based on your database setup
            # For now, we'll simulate it
            active_connections = 10  # Replace with actual query
            max_connections = 100    # Replace with actual limit
            
            usage = ResourceUsage(
                resource_type=ResourceType.DATABASE,
                current_value=active_connections,
                max_value=max_connections,
                percentage=(active_connections / max_connections) * 100,
                unit="connections",
                details={
                    'idle_connections': max_connections - active_connections,
                    'pool_size': max_connections
                }
            )
            
            await self._process_usage(usage)
            return usage
            
        except Exception as e:
            self.logger.error(
                "Error checking database usage",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            return None
    
    async def _check_redis(self) -> ResourceUsage:
        """Check Redis memory usage."""
        try:
            redis_client = get_redis()
            info = redis_client.info('memory')
            
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0) or (1024 * 1024 * 1024)  # Default 1GB
            
            usage = ResourceUsage(
                resource_type=ResourceType.REDIS,
                current_value=used_memory / (1024 * 1024),  # MB
                max_value=max_memory / (1024 * 1024),  # MB
                percentage=(used_memory / max_memory) * 100,
                unit="MB",
                details={
                    'peak_memory_mb': info.get('used_memory_peak', 0) / (1024 * 1024),
                    'fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
                    'connected_clients': redis_client.info('clients').get('connected_clients', 0)
                }
            )
            
            await self._process_usage(usage)
            return usage
            
        except Exception as e:
            self.logger.error(
                "Error checking Redis usage",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            return None
    
    async def _check_file_handles(self) -> ResourceUsage:
        """Check file handle usage."""
        try:
            process = psutil.Process()
            open_files = len(process.open_files())
            max_files = self.limits['max_file_handles']
            
            usage = ResourceUsage(
                resource_type=ResourceType.FILE_HANDLES,
                current_value=open_files,
                max_value=max_files,
                percentage=(open_files / max_files) * 100,
                unit="handles",
                details={
                    'process_id': process.pid,
                    'file_descriptors': open_files
                }
            )
            
            await self._process_usage(usage)
            return usage
            
        except Exception as e:
            self.logger.error(
                "Error checking file handles",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            return None
    
    async def _check_threads(self) -> ResourceUsage:
        """Check thread usage."""
        try:
            thread_count = threading.active_count()
            max_threads = self.limits['max_threads']
            
            usage = ResourceUsage(
                resource_type=ResourceType.THREADS,
                current_value=thread_count,
                max_value=max_threads,
                percentage=(thread_count / max_threads) * 100,
                unit="threads",
                details={
                    'main_thread': threading.main_thread().name,
                    'current_thread': threading.current_thread().name
                }
            )
            
            await self._process_usage(usage)
            return usage
            
        except Exception as e:
            self.logger.error(
                "Error checking threads",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            return None
    
    async def _process_usage(self, usage: ResourceUsage):
        """Process resource usage and generate alerts if needed."""
        if not usage:
            return
        
        # Store usage history
        if usage.resource_type not in self.usage_history:
            self.usage_history[usage.resource_type] = []
        
        self.usage_history[usage.resource_type].append(usage)
        
        # Limit history size
        if len(self.usage_history[usage.resource_type]) > self.max_history_size:
            self.usage_history[usage.resource_type] = \
                self.usage_history[usage.resource_type][-self.max_history_size:]
        
        # Check thresholds and generate alerts
        await self._check_thresholds(usage)
    
    async def _check_thresholds(self, usage: ResourceUsage):
        """Check resource thresholds and generate alerts."""
        threshold = self.thresholds.get(usage.resource_type)
        if not threshold or not threshold.enabled:
            return
        
        alert_level = None
        threshold_value = None
        
        if usage.percentage >= threshold.emergency_level:
            alert_level = AlertLevel.EMERGENCY
            threshold_value = threshold.emergency_level
        elif usage.percentage >= threshold.critical_level:
            alert_level = AlertLevel.CRITICAL
            threshold_value = threshold.critical_level
        elif usage.percentage >= threshold.warning_level:
            alert_level = AlertLevel.WARNING
            threshold_value = threshold.warning_level
        
        if alert_level:
            await self._generate_alert(usage, alert_level, threshold_value)
    
    async def _generate_alert(self, usage: ResourceUsage, level: AlertLevel, threshold_value: float):
        """Generate resource alert."""
        alert = ResourceAlert(
            resource_type=usage.resource_type,
            level=level,
            message=f"{usage.resource_type.value.title()} usage at {usage.percentage:.1f}% (threshold: {threshold_value}%)",
            current_value=usage.percentage,
            threshold_value=threshold_value
        )
        
        self.alerts.append(alert)
        
        # Log alert
        log_method = {
            AlertLevel.INFO: self.logger.info,
            AlertLevel.WARNING: self.logger.warning,
            AlertLevel.CRITICAL: self.logger.error,
            AlertLevel.EMERGENCY: self.logger.critical
        }[level]
        
        log_method(
            alert.message,
            event_type='resource_alert',
            resource_type=usage.resource_type.value,
            alert_level=level.value,
            current_value=usage.current_value,
            percentage=usage.percentage,
            threshold=threshold_value,
            details=usage.details
        )
        
        # Execute callbacks
        callbacks = self.callbacks.get(usage.resource_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                self.logger.error(
                    "Error executing resource alert callback",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    callback=str(callback)
                )
        
        # Trigger emergency actions for critical alerts
        if level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]:
            await self._handle_critical_alert(alert)
    
    async def _handle_critical_alert(self, alert: ResourceAlert):
        """Handle critical resource alerts."""
        if alert.resource_type == ResourceType.MEMORY:
            await self._emergency_memory_cleanup()
        elif alert.resource_type == ResourceType.DISK:
            await self._emergency_disk_cleanup()
        elif alert.resource_type == ResourceType.CPU:
            await self._throttle_processing()
    
    async def _emergency_memory_cleanup(self):
        """Emergency memory cleanup."""
        self.logger.warning("Executing emergency memory cleanup")
        
        # Force garbage collection
        gc.collect()
        
        # Clear caches if available
        try:
            # Clear any application caches here
            pass
        except Exception as e:
            self.logger.error("Error during cache cleanup", exc_info=True)
    
    async def _emergency_disk_cleanup(self):
        """Emergency disk cleanup."""
        self.logger.warning("Executing emergency disk cleanup")
        
        # Clean temporary files
        await self.cleanup_temp_files()
        
        # Clean old log files
        await self.cleanup_old_logs()
    
    async def _throttle_processing(self):
        """Throttle processing to reduce CPU load."""
        self.logger.warning("Throttling processing due to high CPU usage")
        
        # Implement processing throttling logic here
        # This could involve reducing concurrent tasks, adding delays, etc.
    
    async def _get_directory_size(self, path: str) -> int:
        """Get directory size in bytes."""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        continue
        except (OSError, PermissionError):
            pass
        return total_size
    
    def get_current_usage(self, resource_type: ResourceType) -> Optional[ResourceUsage]:
        """Get current usage for a resource type."""
        history = self.usage_history.get(resource_type, [])
        return history[-1] if history else None
    
    def get_usage_history(self, resource_type: ResourceType, 
                         hours: int = 24) -> List[ResourceUsage]: