"""Error recovery and cleanup mechanisms for clip generation system.

This module provides:
- Automatic error recovery strategies
- Resource cleanup and management
- Failed job recovery
- Disk space management
- Process monitoring and recovery
- Graceful degradation
"""

import os
import shutil
import psutil
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import tempfile
import threading
import signal
import subprocess
from contextlib import contextmanager
import weakref
import gc

from .logging_config import get_logger
from .monitoring import get_monitoring_system

logger = get_logger('error_recovery')


class RecoveryStrategy(Enum):
    """Error recovery strategies."""
    RETRY = 'retry'
    FALLBACK = 'fallback'
    SKIP = 'skip'
    ABORT = 'abort'
    CLEANUP_AND_RETRY = 'cleanup_and_retry'


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass
class RecoveryAction:
    """Recovery action configuration."""
    strategy: RecoveryStrategy
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    timeout: Optional[float] = None
    cleanup_function: Optional[Callable] = None
    fallback_function: Optional[Callable] = None
    condition_check: Optional[Callable] = None


@dataclass
class ErrorContext:
    """Error context information."""
    error: Exception
    operation: str
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    file_path: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CleanupTask:
    """Cleanup task definition."""
    name: str
    function: Callable
    priority: int = 0  # Higher priority runs first
    timeout: float = 30.0
    ignore_errors: bool = True
    condition: Optional[Callable] = None


class ResourceManager:
    """Manages system resources and cleanup."""
    
    def __init__(self, temp_dir: str, max_disk_usage: float = 0.8, 
                 cleanup_interval: float = 300.0):
        self.temp_dir = Path(temp_dir)
        self.max_disk_usage = max_disk_usage
        self.cleanup_interval = cleanup_interval
        self.cleanup_tasks: List[CleanupTask] = []
        self.tracked_files: Dict[str, datetime] = {}
        self.tracked_processes: Dict[int, subprocess.Popen] = {}
        self.cleanup_thread = None
        self.running = False
        self._lock = threading.Lock()
        
        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start the resource manager."""
        if self.running:
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger.logger.info("Resource manager started")
    
    def stop(self):
        """Stop the resource manager."""
        if not self.running:
            return
        
        self.running = False
        
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5.0)
        
        # Final cleanup
        self.cleanup_all()
        
        logger.logger.info("Resource manager stopped")
    
    def add_cleanup_task(self, task: CleanupTask):
        """Add a cleanup task."""
        with self._lock:
            self.cleanup_tasks.append(task)
            # Sort by priority (higher first)
            self.cleanup_tasks.sort(key=lambda t: t.priority, reverse=True)
    
    def track_file(self, file_path: str, max_age: Optional[timedelta] = None):
        """Track a file for cleanup."""
        with self._lock:
            self.tracked_files[file_path] = datetime.utcnow()
        
        # Add cleanup task if max_age specified
        if max_age:
            def cleanup_file():
                if os.path.exists(file_path):
                    file_age = datetime.utcnow() - self.tracked_files.get(file_path, datetime.utcnow())
                    if file_age > max_age:
                        os.remove(file_path)
                        logger.logger.debug(f"Cleaned up old file: {file_path}")
            
            self.add_cleanup_task(CleanupTask(
                name=f"cleanup_file_{os.path.basename(file_path)}",
                function=cleanup_file,
                priority=1
            ))
    
    def track_process(self, process: subprocess.Popen, timeout: float = 300.0):
        """Track a process for cleanup."""
        with self._lock:
            self.tracked_processes[process.pid] = process
        
        def cleanup_process():
            if process.poll() is None:  # Still running
                try:
                    process.terminate()
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                except Exception as e:
                    logger.logger.warning(f"Error terminating process {process.pid}: {e}")
        
        self.add_cleanup_task(CleanupTask(
            name=f"cleanup_process_{process.pid}",
            function=cleanup_process,
            priority=10,
            timeout=timeout
        ))
    
    def untrack_file(self, file_path: str):
        """Stop tracking a file."""
        with self._lock:
            self.tracked_files.pop(file_path, None)
    
    def untrack_process(self, process: subprocess.Popen):
        """Stop tracking a process."""
        with self._lock:
            self.tracked_processes.pop(process.pid, None)
    
    def check_disk_space(self) -> Tuple[bool, float]:
        """Check if disk space is available.
        
        Returns:
            Tuple of (has_space, usage_percent)
        """
        try:
            usage = shutil.disk_usage(self.temp_dir)
            usage_percent = (usage.used / usage.total)
            return usage_percent < self.max_disk_usage, usage_percent
        except Exception as e:
            logger.logger.error(f"Error checking disk space: {e}")
            return False, 1.0
    
    def cleanup_temp_files(self, max_age: timedelta = timedelta(hours=24)):
        """Clean up old temporary files."""
        try:
            cutoff_time = datetime.utcnow() - max_age
            cleaned_count = 0
            cleaned_size = 0
            
            for file_path in self.temp_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_time:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleaned_count += 1
                            cleaned_size += file_size
                            logger.logger.debug(f"Cleaned up temp file: {file_path}")
                    except Exception as e:
                        logger.logger.warning(f"Error cleaning temp file {file_path}: {e}")
            
            if cleaned_count > 0:
                logger.logger.info(
                    f"Cleaned up {cleaned_count} temp files, freed {cleaned_size / 1024 / 1024:.1f} MB"
                )
        
        except Exception as e:
            logger.logger.error(f"Error during temp file cleanup: {e}")
    
    def cleanup_all(self):
        """Run all cleanup tasks."""
        with self._lock:
            tasks = self.cleanup_tasks.copy()
        
        for task in tasks:
            try:
                # Check condition if specified
                if task.condition and not task.condition():
                    continue
                
                logger.logger.debug(f"Running cleanup task: {task.name}")
                task.function()
            
            except Exception as e:
                if not task.ignore_errors:
                    raise
                logger.logger.warning(f"Error in cleanup task {task.name}: {e}")
        
        # Clear completed tasks
        with self._lock:
            self.cleanup_tasks.clear()
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while self.running:
            try:
                time.sleep(self.cleanup_interval)
                
                # Check disk space
                has_space, usage = self.check_disk_space()
                if not has_space:
                    logger.logger.warning(f"Disk usage high: {usage:.1%}")
                    self.cleanup_temp_files(max_age=timedelta(hours=1))  # More aggressive cleanup
                
                # Regular cleanup
                self.cleanup_temp_files()
                
                # Clean up tracked files
                self._cleanup_tracked_files()
                
                # Clean up dead processes
                self._cleanup_dead_processes()
                
            except Exception as e:
                logger.logger.error(f"Error in cleanup loop: {e}", exc_info=True)
    
    def _cleanup_tracked_files(self):
        """Clean up tracked files that no longer exist."""
        with self._lock:
            to_remove = []
            for file_path in self.tracked_files:
                if not os.path.exists(file_path):
                    to_remove.append(file_path)
            
            for file_path in to_remove:
                del self.tracked_files[file_path]
    
    def _cleanup_dead_processes(self):
        """Clean up references to dead processes."""
        with self._lock:
            to_remove = []
            for pid, process in self.tracked_processes.items():
                if process.poll() is not None:  # Process finished
                    to_remove.append(pid)
            
            for pid in to_remove:
                del self.tracked_processes[pid]
    
    @contextmanager
    def temp_file(self, suffix: str = '', prefix: str = 'clip_', max_age: timedelta = timedelta(hours=1)):
        """Context manager for temporary files."""
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=self.temp_dir)
        os.close(fd)
        
        try:
            self.track_file(temp_path, max_age)
            yield temp_path
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                self.untrack_file(temp_path)
            except Exception as e:
                logger.logger.warning(f"Error cleaning up temp file {temp_path}: {e}")
    
    @contextmanager
    def temp_directory(self, suffix: str = '', prefix: str = 'clip_', max_age: timedelta = timedelta(hours=1)):
        """Context manager for temporary directories."""
        temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=self.temp_dir)
        
        try:
            self.track_file(temp_dir, max_age)
            yield temp_dir
        finally:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                self.untrack_file(temp_dir)
            except Exception as e:
                logger.logger.warning(f"Error cleaning up temp directory {temp_dir}: {e}")


class ErrorRecoveryManager:
    """Manages error recovery strategies."""
    
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        self.recovery_strategies: Dict[str, RecoveryAction] = {}
        self.error_history: List[ErrorContext] = []
        self.max_history = 1000
        
        # Default recovery strategies
        self._setup_default_strategies()
    
    def _setup_default_strategies(self):
        """Setup default recovery strategies."""
        # FFmpeg errors
        self.recovery_strategies['ffmpeg_error'] = RecoveryAction(
            strategy=RecoveryStrategy.CLEANUP_AND_RETRY,
            max_retries=2,
            retry_delay=2.0,
            cleanup_function=self._cleanup_ffmpeg_resources
        )
        
        # File I/O errors
        self.recovery_strategies['file_io_error'] = RecoveryAction(
            strategy=RecoveryStrategy.RETRY,
            max_retries=3,
            retry_delay=1.0,
            backoff_multiplier=1.5
        )
        
        # Memory errors
        self.recovery_strategies['memory_error'] = RecoveryAction(
            strategy=RecoveryStrategy.CLEANUP_AND_RETRY,
            max_retries=1,
            retry_delay=5.0,
            cleanup_function=self._cleanup_memory
        )
        
        # Database errors
        self.recovery_strategies['database_error'] = RecoveryAction(
            strategy=RecoveryStrategy.RETRY,
            max_retries=3,
            retry_delay=2.0,
            backoff_multiplier=2.0
        )
        
        # Network errors
        self.recovery_strategies['network_error'] = RecoveryAction(
            strategy=RecoveryStrategy.RETRY,
            max_retries=5,
            retry_delay=1.0,
            backoff_multiplier=1.5
        )
        
        # Disk space errors
        self.recovery_strategies['disk_space_error'] = RecoveryAction(
            strategy=RecoveryStrategy.CLEANUP_AND_RETRY,
            max_retries=2,
            retry_delay=5.0,
            cleanup_function=self._cleanup_disk_space
        )
    
    def add_recovery_strategy(self, error_type: str, action: RecoveryAction):
        """Add a custom recovery strategy."""
        self.recovery_strategies[error_type] = action
    
    def handle_error(self, error_context: ErrorContext) -> Tuple[bool, Any]:
        """Handle an error with appropriate recovery strategy.
        
        Returns:
            Tuple of (should_retry, result)
        """
        # Add to history
        self.error_history.append(error_context)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
        
        # Log error
        logger.logger.error(
            f"Error in {error_context.operation}: {error_context.error}",
            extra={
                'job_id': error_context.job_id,
                'user_id': error_context.user_id,
                'file_path': error_context.file_path,
                'retry_count': error_context.retry_count,
                'severity': error_context.severity.value
            },
            exc_info=error_context.error
        )
        
        # Determine error type
        error_type = self._classify_error(error_context.error)
        
        # Get recovery strategy
        strategy = self.recovery_strategies.get(error_type)
        if not strategy:
            logger.logger.warning(f"No recovery strategy for error type: {error_type}")
            return False, None
        
        # Check if we should retry
        if error_context.retry_count >= strategy.max_retries:
            logger.logger.error(
                f"Max retries ({strategy.max_retries}) exceeded for {error_context.operation}"
            )
            return False, None
        
        # Execute recovery strategy
        return self._execute_recovery_strategy(strategy, error_context)
    
    def _classify_error(self, error: Exception) -> str:
        """Classify error type for recovery strategy selection."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # FFmpeg errors
        if 'ffmpeg' in error_str or 'codec' in error_str or 'format' in error_str:
            return 'ffmpeg_error'
        
        # File I/O errors
        if isinstance(error, (FileNotFoundError, PermissionError, OSError)):
            return 'file_io_error'
        
        # Memory errors
        if isinstance(error, MemoryError) or 'memory' in error_str:
            return 'memory_error'
        
        # Database errors
        if 'database' in error_str or 'connection' in error_str or 'supabase' in error_str:
            return 'database_error'
        
        # Network errors
        if 'network' in error_str or 'timeout' in error_str or 'connection' in error_str:
            return 'network_error'
        
        # Disk space errors
        if 'disk' in error_str or 'space' in error_str or 'no space left' in error_str:
            return 'disk_space_error'
        
        return 'unknown_error'
    
    def _execute_recovery_strategy(self, strategy: RecoveryAction, 
                                 error_context: ErrorContext) -> Tuple[bool, Any]:
        """Execute a recovery strategy."""
        try:
            if strategy.strategy == RecoveryStrategy.RETRY:
                return self._retry_strategy(strategy, error_context)
            
            elif strategy.strategy == RecoveryStrategy.CLEANUP_AND_RETRY:
                return self._cleanup_and_retry_strategy(strategy, error_context)
            
            elif strategy.strategy == RecoveryStrategy.FALLBACK:
                return self._fallback_strategy(strategy, error_context)
            
            elif strategy.strategy == RecoveryStrategy.SKIP:
                logger.logger.info(f"Skipping operation: {error_context.operation}")
                return False, None
            
            elif strategy.strategy == RecoveryStrategy.ABORT:
                logger.logger.error(f"Aborting operation: {error_context.operation}")
                return False, None
            
            else:
                logger.logger.warning(f"Unknown recovery strategy: {strategy.strategy}")
                return False, None
        
        except Exception as e:
            logger.logger.error(f"Error executing recovery strategy: {e}", exc_info=True)
            return False, None
    
    def _retry_strategy(self, strategy: RecoveryAction, error_context: ErrorContext) -> Tuple[bool, Any]:
        """Execute retry strategy."""
        # Calculate delay with backoff
        delay = strategy.retry_delay * (strategy.backoff_multiplier ** error_context.retry_count)
        
        logger.logger.info(
            f"Retrying {error_context.operation} in {delay:.1f}s (attempt {error_context.retry_count + 1}/{strategy.max_retries})"
        )
        
        time.sleep(delay)
        return True, None
    
    def _cleanup_and_retry_strategy(self, strategy: RecoveryAction, 
                                  error_context: ErrorContext) -> Tuple[bool, Any]:
        """Execute cleanup and retry strategy."""
        # Run cleanup function
        if strategy.cleanup_function:
            try:
                logger.logger.info(f"Running cleanup for {error_context.operation}")
                strategy.cleanup_function(error_context)
            except Exception as e:
                logger.logger.warning(f"Cleanup failed: {e}")
        
        # Then retry
        return self._retry_strategy(strategy, error_context)
    
    def _fallback_strategy(self, strategy: RecoveryAction, error_context: ErrorContext) -> Tuple[bool, Any]:
        """Execute fallback strategy."""
        if strategy.fallback_function:
            try:
                logger.logger.info(f"Using fallback for {error_context.operation}")
                result = strategy.fallback_function(error_context)
                return False, result
            except Exception as e:
                logger.logger.error(f"Fallback failed: {e}", exc_info=True)
        
        return False, None
    
    def _cleanup_ffmpeg_resources(self, error_context: ErrorContext):
        """Cleanup FFmpeg resources."""
        # Kill any running FFmpeg processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'ffmpeg' in proc.info['name'].lower():
                    proc.terminate()
                    proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
        
        # Clean up temporary files
        if error_context.file_path:
            temp_dir = os.path.dirname(error_context.file_path)
            for file in os.listdir(temp_dir):
                if file.startswith('ffmpeg_') or file.endswith('.tmp'):
                    try:
                        os.remove(os.path.join(temp_dir, file))
                    except Exception:
                        pass
    
    def _cleanup_memory(self, error_context: ErrorContext):
        """Cleanup memory resources."""
        # Force garbage collection
        gc.collect()
        
        # Clear any large objects from memory
        # This is application-specific and should be customized
        
        logger.logger.info("Memory cleanup completed")
    
    def _cleanup_disk_space(self, error_context: ErrorContext):
        """Cleanup disk space."""
        # Run aggressive temp file cleanup
        self.resource_manager.cleanup_temp_files(max_age=timedelta(minutes=30))
        
        # Check if space is now available
        has_space, usage = self.resource_manager.check_disk_space()
        logger.logger.info(f"Disk cleanup completed, usage: {usage:.1%}")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        if not self.error_history:
            return {'total_errors': 0}
        
        # Count errors by type
        error_types = {}
        severity_counts = {s.value: 0 for s in ErrorSeverity}
        recent_errors = 0
        
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        for error_context in self.error_history:
            error_type = self._classify_error(error_context.error)
            error_types[error_type] = error_types.get(error_type, 0) + 1
            severity_counts[error_context.severity.value] += 1
            
            if error_context.timestamp > cutoff_time:
                recent_errors += 1
        
        return {
            'total_errors': len(self.error_history),
            'recent_errors': recent_errors,
            'error_types': error_types,
            'severity_counts': severity_counts,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }


# Global instances
resource_manager = ResourceManager(
    temp_dir=os.path.join(tempfile.gettempdir(), 'cliper'),
    max_disk_usage=0.8,
    cleanup_interval=300.0
)

error_recovery_manager = ErrorRecoveryManager(resource_manager)


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance."""
    return resource_manager


def get_error_recovery_manager() -> ErrorRecoveryManager:
    """Get the global error recovery manager instance."""
    return error_recovery_manager


# Convenience functions
def handle_error(error: Exception, operation: str, job_id: Optional[str] = None, 
                user_id: Optional[str] = None, file_path: Optional[str] = None, 
                retry_count: int = 0, severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> Tuple[bool, Any]:
    """Handle an error with recovery."""
    error_context = ErrorContext(
        error=error,
        operation=operation,
        job_id=job_id,
        user_id=user_id,
        file_path=file_path,
        retry_count=retry_count,
        severity=severity
    )
    
    return error_recovery_manager.handle_error(error_context)


@contextmanager
def error_recovery_context(operation: str, job_id: Optional[str] = None, 
                          user_id: Optional[str] = None, max_retries: int = 3):
    """Context manager for automatic error recovery."""
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            yield
            break  # Success, exit loop
        
        except Exception as e:
            should_retry, result = handle_error(
                error=e,
                operation=operation,
                job_id=job_id,
                user_id=user_id,
                retry_count=retry_count
            )
            
            if not should_retry or retry_count >= max_retries:
                raise  # Re-raise the exception
            
            retry_count += 1


# Initialize managers on import
resource_manager.start()


# Cleanup on exit
import atexit
atexit.register(resource_manager.stop)