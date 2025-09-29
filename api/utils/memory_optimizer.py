"""Enhanced memory optimization and resource management utilities.

Provides:
- Advanced memory monitoring and cleanup
- Resource lifecycle management
- Memory leak detection
- Automatic garbage collection optimization
- Resource pooling and reuse
- Memory pressure handling
"""

import os
import gc
import sys
import time
import psutil
import threading
import weakref
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from contextlib import contextmanager
from functools import wraps
import logging
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

@dataclass
class MemoryStats:
    """Memory usage statistics."""
    rss_mb: float
    vms_mb: float
    percent: float
    available_mb: float
    total_mb: float
    gc_objects: int
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class ResourceInfo:
    """Resource tracking information."""
    resource_id: str
    resource_type: str
    created_at: datetime
    last_accessed: datetime
    size_mb: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

class MemoryPressureLevel:
    """Memory pressure levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class EnhancedMemoryOptimizer:
    """Enhanced memory optimizer with advanced features."""
    
    def __init__(self, 
                 warning_threshold_mb: int = 1024,
                 critical_threshold_mb: int = 2048,
                 monitoring_interval: float = 30.0):
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self.monitoring_interval = monitoring_interval
        
        # Memory tracking
        self._memory_history: deque = deque(maxlen=100)
        self._resource_registry: Dict[str, ResourceInfo] = {}
        self._cleanup_callbacks: List[Callable] = []
        self._weak_refs: Set[weakref.ref] = set()
        
        # Monitoring state
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._last_cleanup = datetime.utcnow()
        self._cleanup_stats = defaultdict(int)
        
        # Memory pressure handling
        self._pressure_handlers = {
            MemoryPressureLevel.MEDIUM: self._handle_medium_pressure,
            MemoryPressureLevel.HIGH: self._handle_high_pressure,
            MemoryPressureLevel.CRITICAL: self._handle_critical_pressure
        }
        
        # Start monitoring
        self.start_monitoring()
    
    def start_monitoring(self):
        """Start memory monitoring thread."""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self._monitor_thread.start()
            logger.info("Memory monitoring started")
    
    def stop_monitoring(self):
        """Stop memory monitoring thread."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Memory monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Get current memory stats
                stats = self.get_memory_stats()
                self._memory_history.append(stats)
                
                # Check memory pressure
                pressure_level = self._assess_memory_pressure(stats)
                if pressure_level != MemoryPressureLevel.LOW:
                    self._handle_memory_pressure(pressure_level)
                
                # Clean up dead weak references
                self._cleanup_weak_refs()
                
                # Periodic resource cleanup
                if (datetime.utcnow() - self._last_cleanup).total_seconds() > 300:  # 5 minutes
                    self._periodic_cleanup()
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in memory monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            virtual_memory = psutil.virtual_memory()
            
            return MemoryStats(
                rss_mb=memory_info.rss / 1024 / 1024,
                vms_mb=memory_info.vms / 1024 / 1024,
                percent=process.memory_percent(),
                available_mb=virtual_memory.available / 1024 / 1024,
                total_mb=virtual_memory.total / 1024 / 1024,
                gc_objects=len(gc.get_objects())
            )
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return MemoryStats(0, 0, 0, 0, 0, 0)
    
    def _assess_memory_pressure(self, stats: MemoryStats) -> str:
        """Assess current memory pressure level."""
        if stats.rss_mb > self.critical_threshold_mb or stats.percent > 90:
            return MemoryPressureLevel.CRITICAL
        elif stats.rss_mb > self.warning_threshold_mb or stats.percent > 80:
            return MemoryPressureLevel.HIGH
        elif stats.percent > 70 or stats.available_mb < 512:
            return MemoryPressureLevel.MEDIUM
        else:
            return MemoryPressureLevel.LOW
    
    def _handle_memory_pressure(self, level: str):
        """Handle memory pressure based on level."""
        handler = self._pressure_handlers.get(level)
        if handler:
            try:
                handler()
            except Exception as e:
                logger.error(f"Error handling {level} memory pressure: {e}")
    
    def _handle_medium_pressure(self):
        """Handle medium memory pressure."""
        logger.info("Medium memory pressure detected - performing light cleanup")
        self.force_garbage_collection()
        self._cleanup_expired_resources()
    
    def _handle_high_pressure(self):
        """Handle high memory pressure."""
        logger.warning("High memory pressure detected - performing aggressive cleanup")
        self.emergency_cleanup()
        self._clear_caches()
    
    def _handle_critical_pressure(self):
        """Handle critical memory pressure."""
        logger.critical("Critical memory pressure detected - performing emergency cleanup")
        self.emergency_cleanup()
        self._clear_caches()
        self._unload_optional_modules()
        
        # Execute all cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Cleanup callback failed: {e}")
    
    def register_resource(self, resource_id: str, resource_type: str, 
                         size_mb: float = 0.0, metadata: Dict[str, Any] = None) -> str:
        """Register a resource for tracking."""
        info = ResourceInfo(
            resource_id=resource_id,
            resource_type=resource_type,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            size_mb=size_mb,
            metadata=metadata or {}
        )
        self._resource_registry[resource_id] = info
        return resource_id
    
    def unregister_resource(self, resource_id: str):
        """Unregister a resource."""
        if resource_id in self._resource_registry:
            del self._resource_registry[resource_id]
    
    def track_object(self, obj: Any, cleanup_callback: Optional[Callable] = None) -> str:
        """Track an object with weak reference."""
        obj_id = f"obj_{id(obj)}"
        
        def cleanup_wrapper(ref):
            self._weak_refs.discard(ref)
            if cleanup_callback:
                try:
                    cleanup_callback()
                except Exception as e:
                    logger.error(f"Object cleanup callback failed: {e}")
        
        weak_ref = weakref.ref(obj, cleanup_wrapper)
        self._weak_refs.add(weak_ref)
        
        return obj_id
    
    def register_cleanup_callback(self, callback: Callable):
        """Register a cleanup callback for emergency situations."""
        self._cleanup_callbacks.append(callback)
    
    def force_garbage_collection(self) -> Dict[str, Any]:
        """Force comprehensive garbage collection."""
        before_stats = self.get_memory_stats()
        
        # Collect all generations
        collected = []
        for generation in range(3):
            count = gc.collect(generation)
            collected.append(count)
        
        # Final collection
        final_count = gc.collect()
        
        after_stats = self.get_memory_stats()
        
        results = {
            "collected_by_generation": collected,
            "final_collected": final_count,
            "total_collected": sum(collected) + final_count,
            "memory_freed_mb": before_stats.rss_mb - after_stats.rss_mb,
            "objects_before": before_stats.gc_objects,
            "objects_after": after_stats.gc_objects
        }
        
        self._cleanup_stats["gc_runs"] += 1
        self._cleanup_stats["objects_collected"] += results["total_collected"]
        
        logger.debug(f"Garbage collection results: {results}")
        return results
    
    def emergency_cleanup(self) -> Dict[str, Any]:
        """Perform emergency memory cleanup."""
        logger.warning("Performing emergency memory cleanup")
        
        cleanup_results = {
            "gc_results": {},
            "resources_cleaned": 0,
            "caches_cleared": 0,
            "memory_freed_mb": 0,
            "success": False
        }
        
        try:
            before_stats = self.get_memory_stats()
            
            # Force garbage collection
            cleanup_results["gc_results"] = self.force_garbage_collection()
            
            # Clean up expired resources
            cleanup_results["resources_cleaned"] = self._cleanup_expired_resources()
            
            # Clear caches
            cleanup_results["caches_cleared"] = self._clear_caches()
            
            # Unload optional modules
            self._unload_optional_modules()
            
            after_stats = self.get_memory_stats()
            cleanup_results["memory_freed_mb"] = before_stats.rss_mb - after_stats.rss_mb
            cleanup_results["success"] = True
            
            self._cleanup_stats["emergency_cleanups"] += 1
            self._last_cleanup = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
            cleanup_results["error"] = str(e)
        
        return cleanup_results
    
    def _cleanup_expired_resources(self) -> int:
        """Clean up expired resources."""
        cleaned_count = 0
        current_time = datetime.utcnow()
        expired_threshold = timedelta(hours=1)
        
        expired_resources = []
        for resource_id, info in self._resource_registry.items():
            if current_time - info.last_accessed > expired_threshold:
                expired_resources.append(resource_id)
        
        for resource_id in expired_resources:
            try:
                del self._resource_registry[resource_id]
                cleaned_count += 1
            except Exception as e:
                logger.error(f"Error cleaning expired resource {resource_id}: {e}")
        
        return cleaned_count
    
    def _clear_caches(self) -> int:
        """Clear various caches."""
        cleared_count = 0
        
        try:
            # Clear function caches
            for obj in gc.get_objects():
                if hasattr(obj, 'cache_clear'):
                    try:
                        obj.cache_clear()
                        cleared_count += 1
                    except Exception:
                        pass
            
            # Clear sys.modules cache for unused modules
            unused_modules = []
            for module_name, module in sys.modules.items():
                if module and hasattr(module, '__file__') and module.__file__:
                    # Check if module is from temp directory or cache
                    if 'temp' in module.__file__.lower() or 'cache' in module.__file__.lower():
                        unused_modules.append(module_name)
            
            for module_name in unused_modules:
                try:
                    del sys.modules[module_name]
                    cleared_count += 1
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error(f"Error clearing caches: {e}")
        
        return cleared_count
    
    def _unload_optional_modules(self):
        """Unload optional heavy modules to free memory."""
        optional_modules = [
            'torch', 'tensorflow', 'cv2', 'numpy', 'scipy',
            'matplotlib', 'PIL', 'whisper'
        ]
        
        for module_name in optional_modules:
            if module_name in sys.modules:
                try:
                    # Clear CUDA cache if it's torch
                    if module_name == 'torch' and hasattr(sys.modules[module_name], 'cuda'):
                        sys.modules[module_name].cuda.empty_cache()
                    
                    # Remove from sys.modules
                    del sys.modules[module_name]
                    logger.debug(f"Unloaded optional module: {module_name}")
                    
                except Exception as e:
                    logger.debug(f"Could not unload module {module_name}: {e}")
    
    def _cleanup_weak_refs(self):
        """Clean up dead weak references."""
        dead_refs = [ref for ref in self._weak_refs if ref() is None]
        for ref in dead_refs:
            self._weak_refs.discard(ref)
    
    def _periodic_cleanup(self):
        """Perform periodic maintenance cleanup."""
        logger.debug("Performing periodic cleanup")
        
        # Light garbage collection
        gc.collect(0)  # Only generation 0
        
        # Clean up expired resources
        self._cleanup_expired_resources()
        
        # Clean up weak references
        self._cleanup_weak_refs()
        
        self._last_cleanup = datetime.utcnow()
    
    def get_memory_trend(self) -> Dict[str, Any]:
        """Analyze memory usage trends."""
        if len(self._memory_history) < 2:
            return {"trend": "insufficient_data"}
        
        recent_stats = list(self._memory_history)[-10:]  # Last 10 measurements
        
        rss_values = [stat.rss_mb for stat in recent_stats]
        percent_values = [stat.percent for stat in recent_stats]
        
        # Calculate trend
        if len(rss_values) >= 2:
            trend = "increasing" if rss_values[-1] > rss_values[0] else "decreasing"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "current_rss_mb": rss_values[-1] if rss_values else 0,
            "avg_rss_mb": sum(rss_values) / len(rss_values) if rss_values else 0,
            "max_rss_mb": max(rss_values) if rss_values else 0,
            "min_rss_mb": min(rss_values) if rss_values else 0,
            "avg_percent": sum(percent_values) / len(percent_values) if percent_values else 0,
            "measurements": len(recent_stats)
        }
    
    def get_cleanup_stats(self) -> Dict[str, Any]:
        """Get cleanup statistics."""
        return dict(self._cleanup_stats)
    
    def get_resource_summary(self) -> Dict[str, Any]:
        """Get resource usage summary."""
        resource_types = defaultdict(int)
        total_size = 0
        
        for info in self._resource_registry.values():
            resource_types[info.resource_type] += 1
            total_size += info.size_mb
        
        return {
            "total_resources": len(self._resource_registry),
            "resource_types": dict(resource_types),
            "total_size_mb": total_size,
            "tracked_objects": len(self._weak_refs)
        }
    
    @contextmanager
    def memory_context(self, operation_name: str = "operation"):
        """Context manager for memory monitoring during operations."""
        start_stats = self.get_memory_stats()
        start_time = time.time()
        
        logger.debug(f"Starting {operation_name} - Memory: {start_stats.rss_mb:.2f}MB")
        
        try:
            yield
        finally:
            end_stats = self.get_memory_stats()
            duration = time.time() - start_time
            memory_diff = end_stats.rss_mb - start_stats.rss_mb
            
            logger.debug(
                f"Finished {operation_name} - "
                f"Duration: {duration:.2f}s, "
                f"Memory: {end_stats.rss_mb:.2f}MB (Δ{memory_diff:+.2f}MB)"
            )
            
            # Trigger cleanup if memory usage increased significantly
            if memory_diff > 100:  # More than 100MB increase
                logger.warning(f"{operation_name} used {memory_diff:.2f}MB - triggering cleanup")
                self.force_garbage_collection()
    
    def memory_monitor_decorator(self, func):
        """Decorator for monitoring function memory usage."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.memory_context(func.__name__):
                return func(*args, **kwargs)
        return wrapper

# Global instance
enhanced_memory_optimizer = EnhancedMemoryOptimizer()