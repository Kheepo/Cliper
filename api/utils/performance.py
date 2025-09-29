"""Performance optimization utilities for clip generation system.

This module provides:
- Memory management and monitoring
- Disk space checks and management
- Processing limits and throttling
- Resource allocation optimization
- Performance metrics collection
- Queue management and prioritization
"""

import os
import psutil
import time
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple, NamedTuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import queue
import weakref
import gc
import resource
import tempfile
from contextlib import contextmanager
from collections import deque, defaultdict
import json

from .logging_config import get_logger
from .monitoring import get_monitoring_system

logger = get_logger('performance')


class Priority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class ResourceType(Enum):
    """System resource types."""
    CPU = 'cpu'
    MEMORY = 'memory'
    DISK = 'disk'
    NETWORK = 'network'
    GPU = 'gpu'


@dataclass
class ResourceLimits:
    """Resource usage limits."""
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 85.0
    max_disk_percent: float = 90.0
    max_concurrent_jobs: int = 4
    max_file_size_mb: int = 1000
    max_video_duration_seconds: int = 3600
    max_clips_per_video: int = 20
    max_queue_size: int = 100


@dataclass
class PerformanceMetrics:
    """Performance metrics data."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    active_jobs: int = 0
    queue_size: int = 0
    processing_time: float = 0.0
    throughput: float = 0.0  # clips per minute
    error_rate: float = 0.0
    resource_efficiency: float = 0.0


class ResourceUsage(NamedTuple):
    """Current resource usage."""
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_percent: float
    disk_free_gb: float
    load_average: float
    active_processes: int


@dataclass
class ProcessingJob:
    """Processing job information."""
    job_id: str
    user_id: str
    priority: Priority
    estimated_duration: float
    estimated_memory_mb: float
    file_size_mb: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """Manages memory usage and optimization."""
    
    def __init__(self, max_memory_percent: float = 85.0):
        self.max_memory_percent = max_memory_percent
        self.memory_threshold_mb = self._get_memory_threshold()
        self.tracked_objects: Dict[str, weakref.ref] = {}
        self.memory_history: deque = deque(maxlen=100)
        self._lock = threading.Lock()
    
    def _get_memory_threshold(self) -> float:
        """Calculate memory threshold in MB."""
        total_memory = psutil.virtual_memory().total
        return (total_memory * self.max_memory_percent / 100) / (1024 * 1024)
    
    def get_memory_usage(self) -> Tuple[float, float]:
        """Get current memory usage.
        
        Returns:
            Tuple of (used_percent, used_mb)
        """
        memory = psutil.virtual_memory()
        used_percent = memory.percent
        used_mb = memory.used / (1024 * 1024)
        
        # Track history
        with self._lock:
            self.memory_history.append({
                'timestamp': datetime.utcnow(),
                'percent': used_percent,
                'mb': used_mb
            })
        
        return used_percent, used_mb
    
    def is_memory_available(self, required_mb: float) -> bool:
        """Check if required memory is available."""
        _, current_mb = self.get_memory_usage()
        return (current_mb + required_mb) <= self.memory_threshold_mb
    
    def estimate_memory_usage(self, file_size_mb: float, operation: str = 'clip_generation') -> float:
        """Estimate memory usage for an operation."""
        # Base memory usage estimates
        estimates = {
            'clip_generation': file_size_mb * 2.5,  # Video processing overhead
            'thumbnail_generation': file_size_mb * 0.5,
            'analysis': file_size_mb * 1.2,
            'upload': file_size_mb * 0.3
        }
        
        base_estimate = estimates.get(operation, file_size_mb)
        
        # Add safety margin
        return base_estimate * 1.2
    
    def optimize_memory(self) -> bool:
        """Optimize memory usage.
        
        Returns:
            True if optimization was successful
        """
        try:
            # Force garbage collection
            collected = gc.collect()
            
            # Clean up tracked objects
            self._cleanup_tracked_objects()
            
            # Check if optimization helped
            percent_after, _ = self.get_memory_usage()
            
            logger.logger.info(
                f"Memory optimization completed: collected {collected} objects, "
                f"current usage: {percent_after:.1f}%"
            )
            
            return percent_after < self.max_memory_percent
        
        except Exception as e:
            logger.logger.error(f"Memory optimization failed: {e}")
            return False
    
    def track_object(self, obj_id: str, obj: Any):
        """Track an object for memory management."""
        with self._lock:
            self.tracked_objects[obj_id] = weakref.ref(obj)
    
    def untrack_object(self, obj_id: str):
        """Stop tracking an object."""
        with self._lock:
            self.tracked_objects.pop(obj_id, None)
    
    def _cleanup_tracked_objects(self):
        """Clean up dead object references."""
        with self._lock:
            dead_refs = []
            for obj_id, ref in self.tracked_objects.items():
                if ref() is None:
                    dead_refs.append(obj_id)
            
            for obj_id in dead_refs:
                del self.tracked_objects[obj_id]
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        percent, mb = self.get_memory_usage()
        
        # Calculate trends from history
        trend = 0.0
        if len(self.memory_history) >= 2:
            recent = list(self.memory_history)[-10:]  # Last 10 measurements
            if len(recent) >= 2:
                trend = (recent[-1]['percent'] - recent[0]['percent']) / len(recent)
        
        return {
            'current_percent': percent,
            'current_mb': mb,
            'threshold_mb': self.memory_threshold_mb,
            'available_mb': self.memory_threshold_mb - mb,
            'trend_percent_per_measurement': trend,
            'tracked_objects': len(self.tracked_objects),
            'history_size': len(self.memory_history)
        }


class DiskManager:
    """Manages disk space and I/O optimization."""
    
    def __init__(self, temp_dir: str, max_disk_percent: float = 90.0):
        self.temp_dir = Path(temp_dir)
        self.max_disk_percent = max_disk_percent
        self.disk_history: deque = deque(maxlen=100)
        self._lock = threading.Lock()
        
        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def get_disk_usage(self) -> Tuple[float, float]:
        """Get current disk usage.
        
        Returns:
            Tuple of (used_percent, free_gb)
        """
        try:
            usage = psutil.disk_usage(self.temp_dir)
            used_percent = (usage.used / usage.total) * 100
            free_gb = usage.free / (1024 * 1024 * 1024)
            
            # Track history
            with self._lock:
                self.disk_history.append({
                    'timestamp': datetime.utcnow(),
                    'percent': used_percent,
                    'free_gb': free_gb
                })
            
            return used_percent, free_gb
        
        except Exception as e:
            logger.logger.error(f"Error getting disk usage: {e}")
            return 100.0, 0.0
    
    def is_disk_space_available(self, required_gb: float) -> bool:
        """Check if required disk space is available."""
        _, free_gb = self.get_disk_usage()
        return free_gb >= (required_gb + 1.0)  # 1GB safety margin
    
    def estimate_disk_usage(self, file_size_mb: float, operation: str = 'clip_generation') -> float:
        """Estimate disk usage for an operation in GB."""
        # Convert to GB
        file_size_gb = file_size_mb / 1024
        
        # Operation-specific multipliers
        multipliers = {
            'clip_generation': 3.0,  # Original + clips + temp files
            'thumbnail_generation': 1.1,
            'analysis': 1.2,
            'upload': 1.0
        }
        
        multiplier = multipliers.get(operation, 2.0)
        return file_size_gb * multiplier
    
    def cleanup_temp_files(self, max_age_hours: float = 24.0) -> Tuple[int, float]:
        """Clean up old temporary files.
        
        Returns:
            Tuple of (files_cleaned, gb_freed)
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            files_cleaned = 0
            bytes_freed = 0
            
            for file_path in self.temp_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_time:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            files_cleaned += 1
                            bytes_freed += file_size
                    except Exception as e:
                        logger.logger.warning(f"Error cleaning file {file_path}: {e}")
            
            gb_freed = bytes_freed / (1024 * 1024 * 1024)
            
            if files_cleaned > 0:
                logger.logger.info(f"Cleaned {files_cleaned} files, freed {gb_freed:.2f} GB")
            
            return files_cleaned, gb_freed
        
        except Exception as e:
            logger.logger.error(f"Error during cleanup: {e}")
            return 0, 0.0
    
    def get_disk_stats(self) -> Dict[str, Any]:
        """Get disk statistics."""
        percent, free_gb = self.get_disk_usage()
        
        # Calculate I/O statistics
        try:
            disk_io = psutil.disk_io_counters()
            io_stats = {
                'read_mb': disk_io.read_bytes / (1024 * 1024),
                'write_mb': disk_io.write_bytes / (1024 * 1024),
                'read_count': disk_io.read_count,
                'write_count': disk_io.write_count
            }
        except Exception:
            io_stats = {}
        
        return {
            'used_percent': percent,
            'free_gb': free_gb,
            'temp_dir': str(self.temp_dir),
            'io_stats': io_stats,
            'history_size': len(self.disk_history)
        }


class ProcessingQueue:
    """Manages job queue with priority and resource-aware scheduling."""
    
    def __init__(self, max_size: int = 100, max_concurrent: int = 4):
        self.max_size = max_size
        self.max_concurrent = max_concurrent
        self.queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=max_size)
        self.active_jobs: Dict[str, ProcessingJob] = {}
        self.completed_jobs: deque = deque(maxlen=1000)
        self.job_counter = 0
        self._lock = threading.Lock()
    
    def add_job(self, job: ProcessingJob) -> bool:
        """Add a job to the queue.
        
        Returns:
            True if job was added successfully
        """
        try:
            # Create priority tuple (lower number = higher priority)
            priority_value = (5 - job.priority.value, self.job_counter)
            self.job_counter += 1
            
            # Add to queue
            self.queue.put((priority_value, job), block=False)
            
            logger.logger.info(
                f"Job {job.job_id} added to queue with priority {job.priority.name}"
            )
            
            return True
        
        except queue.Full:
            logger.logger.warning(f"Queue full, cannot add job {job.job_id}")
            return False
        except Exception as e:
            logger.logger.error(f"Error adding job to queue: {e}")
            return False
    
    def get_next_job(self, timeout: float = 1.0) -> Optional[ProcessingJob]:
        """Get the next job from the queue.
        
        Returns:
            Next job or None if queue is empty or timeout
        """
        try:
            # Check if we can start more jobs
            with self._lock:
                if len(self.active_jobs) >= self.max_concurrent:
                    return None
            
            # Get job from queue
            priority_tuple, job = self.queue.get(timeout=timeout)
            
            # Mark as active
            with self._lock:
                job.started_at = datetime.utcnow()
                self.active_jobs[job.job_id] = job
            
            logger.logger.info(f"Starting job {job.job_id}")
            return job
        
        except queue.Empty:
            return None
        except Exception as e:
            logger.logger.error(f"Error getting job from queue: {e}")
            return None
    
    def complete_job(self, job_id: str, success: bool = True):
        """Mark a job as completed."""
        with self._lock:
            job = self.active_jobs.pop(job_id, None)
            if job:
                job.completed_at = datetime.utcnow()
                job.metadata['success'] = success
                self.completed_jobs.append(job)
                
                duration = (job.completed_at - job.started_at).total_seconds()
                logger.logger.info(
                    f"Job {job_id} completed in {duration:.1f}s (success: {success})"
                )
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            active_count = len(self.active_jobs)
            completed_count = len(self.completed_jobs)
        
        # Calculate success rate
        if completed_count > 0:
            successful = sum(1 for job in self.completed_jobs if job.metadata.get('success', False))
            success_rate = successful / completed_count
        else:
            success_rate = 0.0
        
        # Calculate average processing time
        if completed_count > 0:
            total_time = sum(
                (job.completed_at - job.started_at).total_seconds()
                for job in self.completed_jobs
                if job.started_at and job.completed_at
            )
            avg_processing_time = total_time / completed_count
        else:
            avg_processing_time = 0.0
        
        return {
            'queue_size': self.queue.qsize(),
            'active_jobs': active_count,
            'completed_jobs': completed_count,
            'max_concurrent': self.max_concurrent,
            'success_rate': success_rate,
            'avg_processing_time': avg_processing_time
        }


class PerformanceOptimizer:
    """Main performance optimization coordinator."""
    
    def __init__(self, limits: ResourceLimits, temp_dir: str):
        self.limits = limits
        self.memory_manager = MemoryManager(limits.max_memory_percent)
        self.disk_manager = DiskManager(temp_dir, limits.max_disk_percent)
        self.processing_queue = ProcessingQueue(limits.max_queue_size, limits.max_concurrent_jobs)
        self.metrics_history: deque = deque(maxlen=1000)
        self.running = False
        self.monitor_thread = None
        self._lock = threading.Lock()
    
    def start(self):
        """Start the performance optimizer."""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.logger.info("Performance optimizer started")
    
    def stop(self):
        """Stop the performance optimizer."""
        if not self.running:
            return
        
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        
        logger.logger.info("Performance optimizer stopped")
    
    def can_process_job(self, job: ProcessingJob) -> Tuple[bool, str]:
        """Check if a job can be processed given current resources.
        
        Returns:
            Tuple of (can_process, reason)
        """
        # Check memory
        if not self.memory_manager.is_memory_available(job.estimated_memory_mb):
            return False, "Insufficient memory"
        
        # Check disk space
        required_disk_gb = self.disk_manager.estimate_disk_usage(
            job.file_size_mb, 'clip_generation'
        )
        if not self.disk_manager.is_disk_space_available(required_disk_gb):
            return False, "Insufficient disk space"
        
        # Check file size limits
        if job.file_size_mb > self.limits.max_file_size_mb:
            return False, f"File too large ({job.file_size_mb}MB > {self.limits.max_file_size_mb}MB)"
        
        # Check queue capacity
        if self.processing_queue.queue.qsize() >= self.limits.max_queue_size:
            return False, "Queue full"
        
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        if cpu_percent > self.limits.max_cpu_percent:
            return False, f"High CPU usage ({cpu_percent:.1f}%)"
        
        return True, "OK"
    
    def optimize_resources(self) -> Dict[str, Any]:
        """Optimize system resources.
        
        Returns:
            Optimization results
        """
        results = {
            'memory_optimized': False,
            'disk_cleaned': False,
            'files_cleaned': 0,
            'gb_freed': 0.0
        }
        
        try:
            # Check if optimization is needed
            memory_percent, _ = self.memory_manager.get_memory_usage()
            disk_percent, _ = self.disk_manager.get_disk_usage()
            
            # Optimize memory if needed
            if memory_percent > self.limits.max_memory_percent * 0.9:  # 90% of limit
                results['memory_optimized'] = self.memory_manager.optimize_memory()
            
            # Clean disk if needed
            if disk_percent > self.limits.max_disk_percent * 0.9:  # 90% of limit
                files_cleaned, gb_freed = self.disk_manager.cleanup_temp_files(max_age_hours=1.0)
                results['disk_cleaned'] = files_cleaned > 0
                results['files_cleaned'] = files_cleaned
                results['gb_freed'] = gb_freed
            
            logger.logger.info(f"Resource optimization completed: {results}")
            
        except Exception as e:
            logger.logger.error(f"Error during resource optimization: {e}")
        
        return results
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        try:
            # Get resource usage
            memory_percent, _ = self.memory_manager.get_memory_usage()
            disk_percent, _ = self.disk_manager.get_disk_usage()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Get queue stats
            queue_stats = self.processing_queue.get_queue_stats()
            
            # Calculate throughput (clips per minute)
            throughput = 0.0
            if len(self.metrics_history) >= 2:
                recent_metrics = list(self.metrics_history)[-10:]  # Last 10 measurements
                if len(recent_metrics) >= 2:
                    time_span = (recent_metrics[-1].timestamp - recent_metrics[0].timestamp).total_seconds() / 60
                    if time_span > 0:
                        completed_jobs = sum(m.active_jobs for m in recent_metrics)
                        throughput = completed_jobs / time_span
            
            metrics = PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                active_jobs=queue_stats['active_jobs'],
                queue_size=queue_stats['queue_size'],
                processing_time=queue_stats['avg_processing_time'],
                throughput=throughput,
                error_rate=1.0 - queue_stats['success_rate'],
                resource_efficiency=self._calculate_efficiency(cpu_percent, memory_percent, disk_percent)
            )
            
            # Add to history
            with self._lock:
                self.metrics_history.append(metrics)
            
            return metrics
        
        except Exception as e:
            logger.logger.error(f"Error getting performance metrics: {e}")
            return PerformanceMetrics()
    
    def _calculate_efficiency(self, cpu: float, memory: float, disk: float) -> float:
        """Calculate resource efficiency score (0-1)."""
        # Efficiency is higher when resources are well-utilized but not overloaded
        target_usage = 70.0  # Target 70% usage for optimal efficiency
        
        cpu_efficiency = 1.0 - abs(cpu - target_usage) / 100.0
        memory_efficiency = 1.0 - abs(memory - target_usage) / 100.0
        disk_efficiency = 1.0 - abs(disk - target_usage) / 100.0
        
        # Weight CPU and memory more heavily
        efficiency = (cpu_efficiency * 0.4 + memory_efficiency * 0.4 + disk_efficiency * 0.2)
        return max(0.0, min(1.0, efficiency))
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            try:
                # Collect metrics
                metrics = self.get_current_metrics()
                
                # Check if optimization is needed
                if (metrics.memory_percent > self.limits.max_memory_percent * 0.9 or
                    metrics.disk_percent > self.limits.max_disk_percent * 0.9):
                    self.optimize_resources()
                
                # Sleep before next check
                time.sleep(30.0)  # Check every 30 seconds
                
            except Exception as e:
                logger.logger.error(f"Error in performance monitor loop: {e}")
                time.sleep(60.0)  # Longer sleep on error
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        current_metrics = self.get_current_metrics()
        memory_stats = self.memory_manager.get_memory_stats()
        disk_stats = self.disk_manager.get_disk_stats()
        queue_stats = self.processing_queue.get_queue_stats()
        
        return {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'current_metrics': {
                'cpu_percent': current_metrics.cpu_percent,
                'memory_percent': current_metrics.memory_percent,
                'disk_percent': current_metrics.disk_percent,
                'active_jobs': current_metrics.active_jobs,
                'queue_size': current_metrics.queue_size,
                'throughput': current_metrics.throughput,
                'error_rate': current_metrics.error_rate,
                'efficiency': current_metrics.resource_efficiency
            },
            'memory_stats': memory_stats,
            'disk_stats': disk_stats,
            'queue_stats': queue_stats,
            'limits': {
                'max_cpu_percent': self.limits.max_cpu_percent,
                'max_memory_percent': self.limits.max_memory_percent,
                'max_disk_percent': self.limits.max_disk_percent,
                'max_concurrent_jobs': self.limits.max_concurrent_jobs,
                'max_file_size_mb': self.limits.max_file_size_mb
            }
        }


# Global instances
default_limits = ResourceLimits()
performance_optimizer = PerformanceOptimizer(
    limits=default_limits,
    temp_dir=os.path.join(tempfile.gettempdir(), 'cliper')
)


def get_performance_optimizer() -> PerformanceOptimizer:
    """Get the global performance optimizer instance."""
    return performance_optimizer


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    return performance_optimizer.memory_manager


def get_disk_manager() -> DiskManager:
    """Get the global disk manager instance."""
    return performance_optimizer.disk_manager


def get_processing_queue() -> ProcessingQueue:
    """Get the global processing queue instance."""
    return performance_optimizer.processing_queue


# Convenience functions
@contextmanager
def memory_tracking(operation_id: str, estimated_mb: float):
    """Context manager for memory tracking."""
    memory_manager = get_memory_manager()
    
    # Check if memory is available
    if not memory_manager.is_memory_available(estimated_mb):
        raise MemoryError(f"Insufficient memory for operation {operation_id}")
    
    # Track memory usage
    start_percent, start_mb = memory_manager.get_memory_usage()
    memory_manager.track_object(operation_id, {'start_mb': start_mb})
    
    try:
        yield
    finally:
        end_percent, end_mb = memory_manager.get_memory_usage()
        memory_manager.untrack_object(operation_id)
        
        actual_usage = end_mb - start_mb
        logger.logger.debug(
            f"Memory usage for {operation_id}: estimated {estimated_mb:.1f}MB, "
            f"actual {actual_usage:.1f}MB"
        )


@contextmanager
def disk_space_check(operation_id: str, estimated_gb: float):
    """Context manager for disk space checking."""
    disk_manager = get_disk_manager()
    
    # Check if disk space is available
    if not disk_manager.is_disk_space_available(estimated_gb):
        raise OSError(f"Insufficient disk space for operation {operation_id}")
    
    try:
        yield
    finally:
        # Log disk usage after operation
        percent, free_gb = disk_manager.get_disk_usage()
        logger.logger.debug(
            f"Disk usage after {operation_id}: {percent:.1f}% used, {free_gb:.1f}GB free"
        )


# Initialize optimizer on import
performance_optimizer.start()


# Cleanup on exit
import atexit
atexit.register(performance_optimizer.stop)