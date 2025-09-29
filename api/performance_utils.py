import os
import gc
import psutil
import hashlib
import pickle
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import cv2
import numpy as np
from moviepy.editor import VideoFileClip
import logging
from functools import wraps
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class MemoryManager:
    """Enhanced memory management utilities with better monitoring and cleanup"""
    
    def __init__(self, memory_threshold_mb: int = 1024, critical_threshold_mb: int = 2048):
        self.memory_threshold_mb = memory_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self.logger = logging.getLogger(__name__)
        self._cleanup_callbacks = []
        self._memory_history = []
        self._max_history = 100
        
        # Enable garbage collection debugging in development
        if os.getenv('DEBUG_MEMORY', 'false').lower() == 'true':
            gc.set_debug(gc.DEBUG_STATS)
    
    def register_cleanup_callback(self, callback):
        """Register a cleanup callback for emergency memory situations"""
        self._cleanup_callbacks.append(callback)
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics with enhanced metrics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            virtual_memory = psutil.virtual_memory()
            
            stats = {
                "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
                "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
                "percent": process.memory_percent(),
                "available_mb": virtual_memory.available / 1024 / 1024,
                "total_mb": virtual_memory.total / 1024 / 1024,
                "used_mb": virtual_memory.used / 1024 / 1024,
                "gc_objects": len(gc.get_objects()),
                "gc_stats": gc.get_stats()
            }
            
            # Track memory history
            import time
            self._memory_history.append({
                "timestamp": time.time(),
                "rss_mb": stats["rss_mb"],
                "percent": stats["percent"]
            })
            
            # Keep only recent history
            if len(self._memory_history) > self._max_history:
                self._memory_history = self._memory_history[-self._max_history:]
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting memory usage: {e}")
            return {"error": str(e)}
    
    def get_memory_trend(self) -> Dict[str, Any]:
        """Analyze memory usage trends"""
        if len(self._memory_history) < 2:
            return {"trend": "insufficient_data"}
        
        recent = self._memory_history[-10:]  # Last 10 measurements
        
        rss_values = [entry["rss_mb"] for entry in recent]
        percent_values = [entry["percent"] for entry in recent]
        
        return {
            "trend": "increasing" if rss_values[-1] > rss_values[0] else "decreasing",
            "avg_rss_mb": sum(rss_values) / len(rss_values),
            "max_rss_mb": max(rss_values),
            "min_rss_mb": min(rss_values),
            "avg_percent": sum(percent_values) / len(percent_values),
            "measurements": len(recent)
        }
    
    def is_memory_critical(self) -> bool:
        """Check if memory usage is critical with enhanced detection"""
        try:
            memory_stats = self.get_memory_usage()
            
            # Check multiple criteria
            rss_critical = memory_stats.get("rss_mb", 0) > self.critical_threshold_mb
            percent_critical = memory_stats.get("percent", 0) > 85
            available_critical = memory_stats.get("available_mb", float('inf')) < 512
            
            return rss_critical or percent_critical or available_critical
            
        except Exception as e:
            self.logger.error(f"Error checking memory critical state: {e}")
            return False
    
    def is_memory_warning(self) -> bool:
        """Check if memory usage is at warning level"""
        try:
            memory_stats = self.get_memory_usage()
            
            rss_warning = memory_stats.get("rss_mb", 0) > self.memory_threshold_mb
            percent_warning = memory_stats.get("percent", 0) > 70
            available_warning = memory_stats.get("available_mb", float('inf')) < 1024
            
            return rss_warning or percent_warning or available_warning
            
        except Exception as e:
            self.logger.error(f"Error checking memory warning state: {e}")
            return False
    
    def emergency_cleanup(self) -> Dict[str, Any]:
        """Perform emergency memory cleanup"""
        self.logger.warning("Performing emergency memory cleanup")
        
        cleanup_results = {
            "callbacks_executed": 0,
            "gc_results": {},
            "memory_before": {},
            "memory_after": {},
            "success": False
        }
        
        try:
            cleanup_results["memory_before"] = self.get_memory_usage()
            
            # Execute registered cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback()
                    cleanup_results["callbacks_executed"] += 1
                except Exception as e:
                    self.logger.error(f"Cleanup callback failed: {e}")
            
            # Force aggressive garbage collection
            cleanup_results["gc_results"] = self.force_garbage_collection()
            
            # Clear caches if available
            try:
                import functools
                # Clear lru_cache decorated functions
                for obj in gc.get_objects():
                    if hasattr(obj, 'cache_clear'):
                        obj.cache_clear()
            except Exception as e:
                self.logger.debug(f"Cache clearing failed: {e}")
            
            cleanup_results["memory_after"] = self.get_memory_usage()
            cleanup_results["success"] = True
            
            self.logger.info(f"Emergency cleanup completed: {cleanup_results}")
            
        except Exception as e:
            self.logger.error(f"Emergency cleanup failed: {e}")
            cleanup_results["error"] = str(e)
        
        return cleanup_results
    
    def force_garbage_collection(self) -> Dict[str, Any]:
        """Enhanced garbage collection with detailed statistics"""
        try:
            before_stats = self.get_memory_usage()
            before_objects = len(gc.get_objects())
            
            # Force garbage collection for all generations
            collected_total = 0
            generation_results = []
            
            for generation in range(3):
                collected = gc.collect(generation)
                collected_total += collected
                generation_results.append({
                    "generation": generation,
                    "collected": collected
                })
            
            # Final collection pass
            final_collected = gc.collect()
            collected_total += final_collected
            
            after_stats = self.get_memory_usage()
            after_objects = len(gc.get_objects())
            
            results = {
                "collected_objects": collected_total,
                "objects_before": before_objects,
                "objects_after": after_objects,
                "objects_freed": before_objects - after_objects,
                "memory_freed_mb": before_stats.get("rss_mb", 0) - after_stats.get("rss_mb", 0),
                "before_mb": before_stats.get("rss_mb", 0),
                "after_mb": after_stats.get("rss_mb", 0),
                "generation_results": generation_results,
                "final_collected": final_collected,
                "gc_stats": gc.get_stats()
            }
            
            self.logger.debug(f"Garbage collection results: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error during garbage collection: {e}")
            return {"error": str(e), "collected_objects": 0}
    
    def memory_monitor(self, func):
        """Decorator to monitor memory usage of functions"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            initial_memory = self.get_memory_usage()
            logger.info(f"Starting {func.__name__} - Memory: {initial_memory['rss_mb']:.2f}MB")
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                final_memory = self.get_memory_usage()
                memory_diff = final_memory['rss_mb'] - initial_memory['rss_mb']
                logger.info(f"Finished {func.__name__} - Memory: {final_memory['rss_mb']:.2f}MB (Δ{memory_diff:+.2f}MB)")
                
                if self.is_memory_critical():
                    logger.warning("Memory usage critical, forcing garbage collection")
                    self.force_garbage_collection()
        
        return wrapper

class VideoCompressor:
    """Video compression utilities"""
    
    def __init__(self):
        self.memory_manager = MemoryManager()
    
    @staticmethod
    def get_video_info(video_path: str) -> Dict[str, Any]:
        """Get video information"""
        try:
            with VideoFileClip(video_path) as clip:
                return {
                    "duration": clip.duration,
                    "fps": clip.fps,
                    "size": clip.size,
                    "width": clip.w,
                    "height": clip.h,
                    "file_size_mb": os.path.getsize(video_path) / 1024 / 1024
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return {}
    
    def compress_video(
        self, 
        input_path: str, 
        output_path: str, 
        target_size_mb: Optional[float] = None,
        quality: str = "medium"
    ) -> Dict[str, Any]:
        """Compress video with specified quality or target size"""
        try:
            video_info = self.get_video_info(input_path)
            original_size = video_info.get("file_size_mb", 0)
            
            # Quality presets
            quality_settings = {
                "low": {"crf": 28, "preset": "fast", "scale": 0.7},
                "medium": {"crf": 23, "preset": "medium", "scale": 0.85},
                "high": {"crf": 18, "preset": "slow", "scale": 1.0}
            }
            
            settings = quality_settings.get(quality, quality_settings["medium"])
            
            with VideoFileClip(input_path) as clip:
                # Scale video if needed
                if settings["scale"] < 1.0:
                    new_width = int(clip.w * settings["scale"])
                    new_height = int(clip.h * settings["scale"])
                    clip = clip.resize((new_width, new_height))
                
                # Write compressed video
                clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    temp_audiofile='temp-audio.m4a',
                    remove_temp=True,
                    preset=settings["preset"],
                    ffmpeg_params=["-crf", str(settings["crf"])]
                )
            
            # Get compressed file info
            compressed_size = os.path.getsize(output_path) / 1024 / 1024
            compression_ratio = (original_size - compressed_size) / original_size * 100
            
            return {
                "success": True,
                "original_size_mb": original_size,
                "compressed_size_mb": compressed_size,
                "compression_ratio_percent": compression_ratio,
                "output_path": output_path
            }
            
        except Exception as e:
            logger.error(f"Error compressing video: {e}")
            return {"success": False, "error": str(e)}

class ThumbnailGenerator:
    """Thumbnail generation utilities"""
    
    def __init__(self):
        self.memory_manager = MemoryManager()
    
    def generate_thumbnail(
        self, 
        video_path: str, 
        output_path: str, 
        timestamp: float = None,
        size: Tuple[int, int] = (320, 180)
    ) -> Dict[str, Any]:
        """Generate thumbnail from video at specified timestamp"""
        try:
            with VideoFileClip(video_path) as clip:
                # Use middle of video if no timestamp specified
                if timestamp is None:
                    timestamp = clip.duration / 2
                
                # Ensure timestamp is within video duration
                timestamp = min(timestamp, clip.duration - 0.1)
                
                # Extract frame
                frame = clip.get_frame(timestamp)
                
                # Resize frame
                frame_resized = cv2.resize(frame, size)
                
                # Convert RGB to BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame_resized, cv2.COLOR_RGB2BGR)
                
                # Save thumbnail
                cv2.imwrite(output_path, frame_bgr)
                
                return {
                    "success": True,
                    "thumbnail_path": output_path,
                    "timestamp": timestamp,
                    "size": size
                }
                
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return {"success": False, "error": str(e)}
    
    def generate_multiple_thumbnails(
        self, 
        video_path: str, 
        output_dir: str, 
        count: int = 5,
        size: Tuple[int, int] = (320, 180)
    ) -> Dict[str, Any]:
        """Generate multiple thumbnails at different timestamps"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            with VideoFileClip(video_path) as clip:
                duration = clip.duration
                timestamps = [duration * i / (count + 1) for i in range(1, count + 1)]
                
                thumbnails = []
                for i, timestamp in enumerate(timestamps):
                    output_path = os.path.join(output_dir, f"thumbnail_{i+1}.jpg")
                    result = self.generate_thumbnail(video_path, output_path, timestamp, size)
                    if result["success"]:
                        thumbnails.append({
                            "index": i + 1,
                            "path": output_path,
                            "timestamp": timestamp
                        })
                
                return {
                    "success": True,
                    "thumbnails": thumbnails,
                    "count": len(thumbnails)
                }
                
        except Exception as e:
            logger.error(f"Error generating multiple thumbnails: {e}")
            return {"success": False, "error": str(e)}

class CacheManager:
    """Caching utilities for video analysis results"""
    
    def __init__(self, cache_dir: str = "cache", max_age_hours: int = 24):
        self.cache_dir = cache_dir
        self.max_age_hours = max_age_hours
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, data: Any) -> str:
        """Generate cache key from data"""
        if isinstance(data, str):
            return hashlib.md5(data.encode()).hexdigest()
        else:
            return hashlib.md5(str(data).encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get cache file path"""
        return os.path.join(self.cache_dir, f"{cache_key}.cache")
    
    def _is_cache_valid(self, cache_path: str) -> bool:
        """Check if cache file is still valid"""
        if not os.path.exists(cache_path):
            return False
        
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        max_age = datetime.now() - timedelta(hours=self.max_age_hours)
        
        return file_time > max_age
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached data"""
        try:
            cache_key = self._get_cache_key(key)
            cache_path = self._get_cache_path(cache_key)
            
            if self._is_cache_valid(cache_path):
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            
            return None
            
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
            return None
    
    def set(self, key: str, data: Any) -> bool:
        """Set cached data"""
        try:
            cache_key = self._get_cache_key(key)
            cache_path = self._get_cache_path(cache_key)
            
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing cache: {e}")
            return False
    
    def clear_expired(self) -> int:
        """Clear expired cache files"""
        cleared_count = 0
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    cache_path = os.path.join(self.cache_dir, filename)
                    if not self._is_cache_valid(cache_path):
                        os.remove(cache_path)
                        cleared_count += 1
            
            logger.info(f"Cleared {cleared_count} expired cache files")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0
    
    def clear_all(self) -> int:
        """Clear all cache files"""
        cleared_count = 0
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    cache_path = os.path.join(self.cache_dir, filename)
                    os.remove(cache_path)
                    cleared_count += 1
            
            logger.info(f"Cleared all {cleared_count} cache files")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Error clearing all cache: {e}")
            return 0

# Global instances
memory_manager = MemoryManager()
video_compressor = VideoCompressor()
thumbnail_generator = ThumbnailGenerator()
cache_manager = CacheManager()

# Async wrapper for CPU-intensive operations
executor = ThreadPoolExecutor(max_workers=2)

async def async_compress_video(*args, **kwargs):
    """Async wrapper for video compression"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, video_compressor.compress_video, *args, **kwargs)

async def async_generate_thumbnail(*args, **kwargs):
    """Async wrapper for thumbnail generation"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, thumbnail_generator.generate_thumbnail, *args, **kwargs)

async def async_generate_multiple_thumbnails(*args, **kwargs):
    """Async wrapper for multiple thumbnail generation"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, thumbnail_generator.generate_multiple_thumbnails, *args, **kwargs)