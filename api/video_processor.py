import os
import cv2
import numpy as np
from moviepy.editor import VideoFileClip
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None

try:
    import vosk
    import json as vosk_json
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    vosk = None
from typing import Dict, Any, List, Tuple, Optional, Union
import logging
import tempfile
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import gc
import psutil
import weakref
from contextlib import contextmanager
import re
import asyncio
import hashlib
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
# Advanced analysis imports
import librosa
import scipy.signal
from scipy.stats import zscore
from sklearn.cluster import KMeans
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
# import face_recognition  # Removed due to build issues
import matplotlib.pyplot as plt
from collections import defaultdict
from .performance_utils import (
    memory_manager, video_compressor, thumbnail_generator, cache_manager,
    async_compress_video, async_generate_thumbnail, async_generate_multiple_thumbnails
)

# Industry-standard retry and timeout configurations
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import speech_recognition as sr

# Industry-standard enums and configurations
class ProcessingStatus(Enum):
    """Processing status enumeration for better state management"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    GENERATING_CLIPS = "generating_clips"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class TranscriptionMethod(Enum):
    """Available transcription methods in priority order"""
    WHISPER_V3 = "whisper_v3"
    WHISPER_BASE = "whisper_base"
    GOOGLE_SPEECH = "google_speech"
    VOSK_OFFLINE = "vosk_offline"
    FALLBACK = "fallback"

@dataclass
class ProcessingConfig:
    """Industry-standard processing configuration"""
    max_memory_usage_percent: int = 80
    chunk_duration_seconds: int = 60
    max_processing_time_minutes: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    enable_gpu_acceleration: bool = True
    enable_distributed_processing: bool = True
    transcription_timeout_seconds: int = 300
    clip_generation_timeout_seconds: int = 600
    enable_caching: bool = True
    cache_ttl_hours: int = 24

@dataclass
class TranscriptionResult:
    """Structured transcription result with metadata"""
    text: str
    confidence: float
    method: TranscriptionMethod
    processing_time: float
    segments: List[Dict[str, Any]]
    language: Optional[str] = None
    error: Optional[str] = None

# Enhanced logging configuration for video processing
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG to INFO for production
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
)
logger = logging.getLogger(__name__)

# Create specialized loggers for different components
speech_logger = logging.getLogger('speech_recognition_processor')
audio_logger = logging.getLogger('audio_processor')
memory_logger = logging.getLogger('memory_manager')
performance_logger = logging.getLogger('performance_monitor')
transcription_logger = logging.getLogger('transcription_processor')
clip_generation_logger = logging.getLogger('clip_generation')

class VideoProcessor:
    """Industry-standard video processing pipeline for clip extraction and analysis"""
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        """Initialize video processor with industry-standard configuration"""
        self.config = config or ProcessingConfig()
        self.recognizer = sr.Recognizer()
        self.temp_dir = tempfile.mkdtemp(prefix="virality_clipper_")
        
        # Enhanced memory management and resource tracking
        self._temp_files = []  # Track temporary files for cleanup
        self._video_clips = weakref.WeakSet()  # Track video clips for cleanup
        self._processing_status = ProcessingStatus.PENDING
        self._current_task_id = None
        self._start_time = None
        
        # Performance metrics tracking
        self._metrics = {
            "total_processing_time": 0.0,
            "transcription_time": 0.0,
            "analysis_time": 0.0,
            "clip_generation_time": 0.0,
            "memory_peak_usage": 0.0,
            "files_processed": 0,
            "clips_generated": 0,
            "errors_encountered": 0
        }
        
        # Initialize memory manager from global instance with fallback
        try:
            self.memory_manager = memory_manager
            if self.memory_manager is None:
                raise AttributeError("Global memory_manager is None")
        except (AttributeError, NameError) as e:
            logger.warning(f"Global memory_manager not available: {e}, creating local instance")
            from .performance_utils import MemoryManager
            self.memory_manager = MemoryManager()
        
        # Advanced analysis components
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')
        
        # Viral moment detection thresholds
        self.motion_threshold = 30.0
        self.volume_spike_threshold = 2.0
        self.sentiment_threshold = 0.5
        self.face_detection_confidence = 0.6
        
        # Performance optimization settings
        self.enable_caching = True
        self.compression_quality = 'medium'
        self.thumbnail_count = 5
        
        # Initialize speech recognition models for comprehensive fallback system
        self.whisper_model = None
        self.vosk_model = None
        self.vosk_recognizer = None
        
        # Initialize Whisper model
        if WHISPER_AVAILABLE:
            try:
                self.whisper_model = whisper.load_model("base")
                speech_logger.info("Whisper model loaded successfully for fallback speech recognition")
            except Exception as e:
                speech_logger.warning(f"Failed to load Whisper model: {e}")
                self.whisper_model = None
        
        # Initialize Vosk model for offline speech recognition with multiple fallback paths
        if VOSK_AVAILABLE:
            try:
                # Try multiple model paths in order of preference
                vosk_model_paths = [
                    "vosk-model-small-en-us-0.15",
                    "vosk-model-en-us-0.22",
                    "vosk-model-en-us-0.21",
                    "models/vosk-model-small-en-us-0.15",
                    os.path.expanduser("~/vosk-models/vosk-model-small-en-us-0.15"),
                    "/usr/local/share/vosk-models/vosk-model-small-en-us-0.15"
                ]
                
                model_loaded = False
                for vosk_model_path in vosk_model_paths:
                    if os.path.exists(vosk_model_path):
                        try:
                            self.vosk_model = vosk.Model(vosk_model_path)
                            self.vosk_recognizer = vosk.KaldiRecognizer(self.vosk_model, 16000)
                            speech_logger.info(f"Vosk offline speech recognition model loaded from {vosk_model_path}")
                            model_loaded = True
                            break
                        except Exception as model_error:
                            speech_logger.debug(f"Failed to load Vosk model from {vosk_model_path}: {model_error}")
                            continue
                
                if not model_loaded:
                    speech_logger.warning("No Vosk model found. Download from https://alphacephei.com/vosk/models and place in project root")
                    self.vosk_model = None
                    self.vosk_recognizer = None
                    
            except Exception as e:
                speech_logger.warning(f"Failed to initialize Vosk: {e}")
                self.vosk_model = None
                self.vosk_recognizer = None
        
        # Log available speech recognition methods
        available_methods = []
        if self.whisper_model:
            available_methods.append("Whisper (offline)")
        if self.recognizer:
            available_methods.append("Google Speech API")
        if self.vosk_model:
            available_methods.append("Vosk (offline)")
        
        speech_logger.info(f"Available speech recognition methods: {', '.join(available_methods) if available_methods else 'None'}")
        
        # Initialize transcription method priority queue
        self._transcription_methods = self._initialize_transcription_priority()
        
    def _initialize_transcription_priority(self) -> List[TranscriptionMethod]:
        """Initialize transcription methods in priority order based on availability"""
        methods = []
        
        # Prioritize Whisper for better accuracy and reliability
        if self.whisper_model:
            methods.append(TranscriptionMethod.WHISPER_BASE)
        
        # Google Speech API as secondary option (prone to timeouts)
        if self.recognizer:
            methods.append(TranscriptionMethod.GOOGLE_SPEECH)
            
        # Vosk as offline fallback
        if self.vosk_model:
            methods.append(TranscriptionMethod.VOSK_OFFLINE)
            
        # Always have fallback method
        methods.append(TranscriptionMethod.FALLBACK)
        
        transcription_logger.info(f"Transcription priority order: {[m.value for m in methods]}")
        return methods
    
    async def _transcribe_with_method(self, audio_file_path: str, method: TranscriptionMethod, language: str) -> TranscriptionResult:
        """Transcribe audio using a specific method with retry and timeout handling"""
        start_time = time.time()
        
        try:
            if method == TranscriptionMethod.WHISPER_BASE and self.whisper_model:
                return await self._transcribe_with_whisper_v3(audio_file_path, language)
            elif method == TranscriptionMethod.GOOGLE_SPEECH and self.recognizer:
                return await self._transcribe_with_google_enhanced(audio_file_path, language)
            elif method == TranscriptionMethod.VOSK_OFFLINE and self.vosk_model:
                return await self._transcribe_with_vosk_enhanced(audio_file_path, language)
            elif method == TranscriptionMethod.FALLBACK:
                return TranscriptionResult(
                    text="[Transcription unavailable - all methods failed]",
                    confidence=0.0,
                    method=method,
                    processing_time=time.time() - start_time,
                    error="All transcription methods exhausted"
                )
            else:
                raise ValueError(f"Unsupported transcription method: {method}")
                
        except Exception as e:
            return TranscriptionResult(
                text="",
                confidence=0.0,
                method=method,
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    async def _transcribe_with_whisper_v3(self, audio_file_path: str, language: str) -> TranscriptionResult:
        """Enhanced Whisper transcription with v3 optimizations"""
        start_time = time.time()
        
        try:
            # Preprocess audio for optimal Whisper performance
            processed_audio_path = await self._preprocess_audio_for_whisper(audio_file_path)
            
            # Use Whisper with enhanced parameters
            result = self.whisper_model.transcribe(
                processed_audio_path,
                language=language.split('-')[0] if language else None,
                task="transcribe",
                fp16=False,  # Better compatibility
                temperature=0.0,  # Deterministic output
                compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=False,
                word_timestamps=True,
                verbose=False
            )
            
            # Calculate confidence based on Whisper's internal metrics
            confidence = self._calculate_whisper_confidence(result)
            
            return TranscriptionResult(
                text=result['text'].strip(),
                confidence=confidence,
                method=TranscriptionMethod.WHISPER_BASE,
                processing_time=time.time() - start_time,
                segments=result.get('segments', []),
                language_detected=result.get('language', 'unknown')
            )
            
        except Exception as e:
            transcription_logger.error(f"Whisper transcription failed: {e}")
            raise
        finally:
            # Cleanup processed audio file
            if 'processed_audio_path' in locals() and processed_audio_path != audio_file_path:
                try:
                    os.unlink(processed_audio_path)
                except Exception:
                    pass
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((Exception,))
    )
    async def _transcribe_with_google_enhanced(self, audio_file_path: str, language: str) -> TranscriptionResult:
        """Enhanced Google Speech API with timeout and retry handling"""
        start_time = time.time()
        
        try:
            # Set timeout for Google Speech API
            timeout = self.config.google_speech_timeout
            
            with sr.AudioFile(audio_file_path) as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = self.recognizer.record(source)
            
            # Use asyncio timeout for the blocking call
            text = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.recognizer.recognize_google(
                        audio_data,
                        language=language,
                        show_all=False
                    )
                ),
                timeout=timeout
            )
            
            # Google Speech API doesn't provide confidence scores in free tier
            confidence = 0.8 if text and len(text.strip()) > 3 else 0.3
            
            return TranscriptionResult(
                text=text.strip() if text else "",
                confidence=confidence,
                method=TranscriptionMethod.GOOGLE_SPEECH,
                processing_time=time.time() - start_time
            )
            
        except asyncio.TimeoutError:
            error_msg = f"Google Speech API timeout after {timeout}s"
            transcription_logger.warning(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            transcription_logger.error(f"Google Speech API failed: {e}")
            raise
    
    async def _transcribe_with_vosk_enhanced(self, audio_file_path: str, language: str) -> TranscriptionResult:
        """Enhanced Vosk transcription with better error handling"""
        start_time = time.time()
        
        try:
            # Implementation would depend on Vosk model availability
            # For now, return a placeholder
            return TranscriptionResult(
                text="[Vosk transcription not implemented]",
                confidence=0.1,
                method=TranscriptionMethod.VOSK_OFFLINE,
                processing_time=time.time() - start_time,
                error="Vosk implementation pending"
            )
            
        except Exception as e:
            transcription_logger.error(f"Vosk transcription failed: {e}")
            raise
    
    async def _preprocess_audio_for_whisper(self, audio_file_path: str) -> str:
        """Preprocess audio for optimal Whisper performance"""
        try:
            # Load audio
            audio = AudioSegment.from_file(audio_file_path)
            
            # Optimize for Whisper: 16kHz mono
            audio = audio.set_frame_rate(16000).set_channels(1)
            
            # Normalize audio levels
            audio = audio.normalize()
            
            # Apply noise reduction if needed
            if len(audio) > 1000:  # Only for audio longer than 1 second
                # Simple noise gate
                audio = audio.apply_gain_db(-3)  # Slight reduction to prevent clipping
            
            # Export to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=self.temp_dir) as temp_file:
                audio.export(temp_file.name, format="wav")
                self._temp_files.append(temp_file.name)
                return temp_file.name
                
        except Exception as e:
            transcription_logger.warning(f"Audio preprocessing failed, using original: {e}")
            return audio_file_path
    
    def _calculate_whisper_confidence(self, whisper_result: dict) -> float:
        """Calculate confidence score from Whisper result"""
        try:
            # Use average log probability if available
            if 'segments' in whisper_result and whisper_result['segments']:
                avg_logprob = sum(seg.get('avg_logprob', -1.0) for seg in whisper_result['segments']) / len(whisper_result['segments'])
                # Convert log probability to confidence (0-1)
                confidence = max(0.0, min(1.0, (avg_logprob + 1.0) / 1.0))
                return confidence
            
            # Fallback: estimate based on text length and content
            text = whisper_result.get('text', '')
            if not text or len(text.strip()) < 3:
                return 0.1
            elif len(text.strip()) < 10:
                return 0.5
            else:
                return 0.8
                
        except Exception:
            return 0.5  # Default confidence
         
    def __del__(self):
        """Clean up temporary directory and resources"""
        self.cleanup_resources()
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
    
    def cleanup_resources(self, force: bool = False):
        """Enhanced cleanup of all tracked resources with better monitoring"""
        cleanup_results = {
            "temp_files_removed": 0,
            "video_clips_closed": 0,
            "memory_freed_mb": 0,
            "whisper_unloaded": False,
            "errors": [],
            "success": False
        }
        
        try:
            # Get memory usage before cleanup
            try:
                memory_before = self.memory_manager.get_memory_usage()
            except Exception as mem_error:
                logger.debug(f"Could not get memory usage before cleanup: {mem_error}")
                memory_before = {"rss_mb": 0}
            
            # Clean up temporary files with retry logic
            temp_files_copy = list(self._temp_files)
            for temp_file in temp_files_copy:
                try:
                    if os.path.exists(temp_file):
                        # Try to remove file with retries for locked files
                        for attempt in range(3):
                            try:
                                os.remove(temp_file)
                                cleanup_results["temp_files_removed"] += 1
                                logger.debug(f"Removed temp file: {temp_file}")
                                break
                            except (PermissionError, OSError) as e:
                                if attempt < 2:
                                    time.sleep(0.1)  # Brief wait before retry
                                    continue
                                else:
                                    raise e
                    
                    # Remove from tracking list
                    if temp_file in self._temp_files:
                        self._temp_files.remove(temp_file)
                        
                except Exception as e:
                    error_msg = f"Failed to remove temp file {temp_file}: {e}"
                    cleanup_results["errors"].append(error_msg)
                    logger.warning(error_msg)
            
            # Clean up orphaned temp files (older than 1 hour)
            try:
                current_time = time.time()
                for filename in os.listdir(self.temp_dir):
                    file_path = os.path.join(self.temp_dir, filename)
                    try:
                        if os.path.isfile(file_path):
                            file_age = current_time - os.path.getmtime(file_path)
                            if file_age > 3600:  # 1 hour
                                os.remove(file_path)
                                cleanup_results["temp_files_removed"] += 1
                                logger.debug(f"Removed orphaned temp file: {file_path}")
                    except Exception as e:
                        logger.debug(f"Could not remove orphaned file {file_path}: {e}")
            except Exception as e:
                cleanup_results["errors"].append(f"Orphaned file cleanup failed: {e}")
            
            # Clean up video clips with enhanced error handling
            video_clips_copy = list(self._video_clips)
            for clip in video_clips_copy:
                try:
                    # Close all clip components
                    if hasattr(clip, 'audio') and clip.audio:
                        try:
                            clip.audio.close()
                        except Exception as e:
                            logger.debug(f"Error closing audio: {e}")
                    
                    if hasattr(clip, 'reader') and clip.reader:
                        try:
                            clip.reader.close()
                        except Exception as e:
                            logger.debug(f"Error closing reader: {e}")
                    
                    if hasattr(clip, 'close'):
                        clip.close()
                    
                    cleanup_results["video_clips_closed"] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to close video clip: {e}"
                    cleanup_results["errors"].append(error_msg)
                    logger.warning(error_msg)
            
            self._video_clips.clear()
            
            # Clean up audio processing resources
            if hasattr(self, 'recognizer'):
                try:
                    # Reset recognizer to free any cached data
                    self.recognizer = sr.Recognizer()
                    # Configure recognizer with enhanced optimal settings
                    self.recognizer.energy_threshold = 300
                    self.recognizer.dynamic_energy_threshold = True
                    self.recognizer.dynamic_energy_adjustment_damping = 0.15
                    self.recognizer.dynamic_energy_ratio = 1.5
                    self.recognizer.pause_threshold = 0.8
                    self.recognizer.operation_timeout = None
                    self.recognizer.phrase_threshold = 0.3
                    self.recognizer.non_speaking_duration = 0.8
                except Exception as e:
                    error_msg = f"Error resetting recognizer: {e}"
                    cleanup_results["errors"].append(error_msg)
                    logger.debug(error_msg)
            
            # Clean up Whisper model based on memory conditions
            should_unload_whisper = (
                force or 
                self.memory_manager.is_memory_critical() or
                (hasattr(self, 'whisper_model') and self.whisper_model and 
                 self.memory_manager.is_memory_warning())
            )
            
            if should_unload_whisper and hasattr(self, 'whisper_model') and self.whisper_model:
                try:
                    # Clear CUDA cache if using GPU
                    if hasattr(self.whisper_model, 'device') and 'cuda' in str(self.whisper_model.device):
                        try:
                            import torch
                            torch.cuda.empty_cache()
                        except Exception:
                            pass
                    
                    del self.whisper_model
                    self.whisper_model = None
                    cleanup_results["whisper_unloaded"] = True
                    logger.info("Unloaded Whisper model to free memory")
                    
                except Exception as e:
                    error_msg = f"Error unloading Whisper model: {e}"
                    cleanup_results["errors"].append(error_msg)
                    logger.debug(error_msg)
            
            # Clear any cached data
            try:
                if hasattr(self, 'cache') and self.cache:
                    cache_size = len(self.cache)
                    self.cache.clear()
                    logger.debug(f"Cleared {cache_size} cache entries")
            except Exception as e:
                cleanup_results["errors"].append(f"Cache clear failed: {e}")
            
            # Force garbage collection if needed
            if force or self.memory_manager.is_memory_warning():
                gc_results = self.memory_manager.force_garbage_collection()
                logger.debug(f"Garbage collection results: {gc_results}")
            
            # Calculate memory freed
            memory_after = self.memory_manager.get_memory_usage()
            cleanup_results["memory_freed_mb"] = (
                memory_before.get("rss_mb", 0) - memory_after.get("rss_mb", 0)
            )
            
            cleanup_results["success"] = True
            logger.info(f"Resource cleanup completed: {cleanup_results}")
            
        except Exception as e:
            error_msg = f"Error during resource cleanup: {e}"
            cleanup_results["errors"].append(error_msg)
            logger.error(error_msg)
        
        return cleanup_results
    
    @contextmanager
    def managed_video_clip(self, video_path: str):
        """Context manager for video clips with automatic cleanup"""
        clip = None
        try:
            clip = VideoFileClip(video_path)
            self._video_clips.add(clip)
            yield clip
        finally:
            if clip:
                try:
                    clip.close()
                    if clip in self._video_clips:
                        self._video_clips.discard(clip)
                except Exception as e:
                    logger.warning(f"Error closing video clip: {e}")
    
    @contextmanager
    def managed_temp_file(self, suffix="", prefix="temp_"):
        """Context manager for temporary files with automatic cleanup"""
        temp_file = None
        try:
            fd, temp_file = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=self.temp_dir)
            os.close(fd)
            self._temp_files.append(temp_file)
            yield temp_file
        finally:
            if temp_file and temp_file in self._temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    self._temp_files.remove(temp_file)
                except Exception as e:
                    logger.warning(f"Error removing temp file {temp_file}: {e}")
    
    def force_memory_cleanup(self, emergency: bool = False):
        """Enhanced memory cleanup with comprehensive monitoring and emergency mode"""
        cleanup_summary = {
            "initial_memory": {},
            "final_memory": {},
            "memory_freed_mb": 0,
            "cleanup_results": {},
            "cache_cleared": 0,
            "gc_results": {},
            "emergency_mode": emergency,
            "success": False,
            "errors": []
        }
        
        try:
            # Get initial memory state
            cleanup_summary["initial_memory"] = self.memory_manager.get_memory_usage()
            memory_trend = self.memory_manager.get_memory_trend()
            
            logger.info(
                f"Starting {'emergency ' if emergency else ''}memory cleanup - "
                f"Current usage: {cleanup_summary['initial_memory'].get('rss_mb', 0):.1f}MB "
                f"({cleanup_summary['initial_memory'].get('percent', 0):.1f}% process), "
                f"Trend: {memory_trend.get('trend', 'unknown')}"
            )
            
            # Perform resource cleanup with force flag if emergency
            cleanup_summary["cleanup_results"] = self.cleanup_resources(force=emergency)
            
            # Clear caches aggressively
            try:
                if hasattr(self, 'cache_manager'):
                    if emergency:
                        cleanup_summary["cache_cleared"] = self.cache_manager.clear_all()
                    else:
                        cleanup_summary["cache_cleared"] = self.cache_manager.clear_expired()
                
                # Clear any additional caches
                if hasattr(cache_manager, 'clear_expired'):
                    cache_manager.clear_expired()
                    
            except Exception as e:
                error_msg = f"Cache clearing failed: {e}"
                cleanup_summary["errors"].append(error_msg)
                logger.warning(error_msg)
            
            # Perform garbage collection with enhanced monitoring
            if emergency:
                # Emergency mode: aggressive cleanup
                cleanup_summary["gc_results"] = self.memory_manager.emergency_cleanup()
            else:
                # Normal mode: standard garbage collection
                cleanup_summary["gc_results"] = self.memory_manager.force_garbage_collection()
            
            # Additional emergency measures
            if emergency and self.memory_manager.is_memory_critical():
                try:
                    # Clear any remaining large objects
                    import sys
                    
                    # Clear module caches
                    if hasattr(sys, 'modules'):
                        for module_name in list(sys.modules.keys()):
                            if module_name.startswith('__pycache__'):
                                try:
                                    del sys.modules[module_name]
                                except Exception:
                                    pass
                    
                    # Force additional cleanup rounds
                    for i in range(5):
                        collected = gc.collect()
                        if collected == 0:
                            break
                        logger.debug(f"Emergency GC round {i+1}: collected {collected} objects")
                    
                except Exception as e:
                    cleanup_summary["errors"].append(f"Emergency measures failed: {e}")
            
            # Get final memory state
            cleanup_summary["final_memory"] = self.memory_manager.get_memory_usage()
            cleanup_summary["memory_freed_mb"] = (
                cleanup_summary["initial_memory"].get("rss_mb", 0) - 
                cleanup_summary["final_memory"].get("rss_mb", 0)
            )
            
            cleanup_summary["success"] = True
            
            # Log comprehensive results
            logger.info(
                f"Memory cleanup completed - "
                f"Final usage: {cleanup_summary['final_memory'].get('rss_mb', 0):.1f}MB "
                f"({cleanup_summary['final_memory'].get('percent', 0):.1f}% process), "
                f"Freed: {cleanup_summary['memory_freed_mb']:.1f}MB, "
                f"Files removed: {cleanup_summary['cleanup_results'].get('temp_files_removed', 0)}, "
                f"Clips closed: {cleanup_summary['cleanup_results'].get('video_clips_closed', 0)}, "
                f"Cache cleared: {cleanup_summary['cache_cleared']} entries"
            )
            
            # Check if cleanup was effective
            if cleanup_summary["memory_freed_mb"] < 10 and emergency:
                logger.warning("Emergency cleanup freed less than 10MB - memory pressure may persist")
            
            return cleanup_summary["memory_freed_mb"]
            
        except Exception as e:
            error_msg = f"Error during forced memory cleanup: {e}"
            cleanup_summary["errors"].append(error_msg)
            logger.error(error_msg)
            return 0
            
    def get_memory_usage(self):
        """Get comprehensive memory usage statistics with enhanced monitoring"""
        try:
            # Use enhanced MemoryManager for detailed stats
            memory_stats = self.memory_manager.get_memory_usage()
            
            # Add video processor specific information
            additional_stats = {
                'temp_files_count': len(self.temp_files),
                'video_clips_active': len([clip for clip in [self.video_clip, self.audio_clip] if clip is not None]),
                'cache_size_mb': 0,
                'whisper_model_loaded': hasattr(self, 'whisper_model') and self.whisper_model is not None
            }
            
            # Get cache size if available
            try:
                if hasattr(self, 'cache_manager'):
                    cache_stats = self.cache_manager.get_cache_stats()
                    additional_stats['cache_size_mb'] = cache_stats.get('total_size_mb', 0)
                    additional_stats['cache_entries'] = cache_stats.get('total_entries', 0)
            except Exception as e:
                logger.debug(f"Could not get cache stats: {e}")
            
            # Combine stats
            combined_stats = {**memory_stats, **additional_stats}
            
            # Add memory trend information
            try:
                memory_trend = self.memory_manager.get_memory_trend()
                combined_stats['memory_trend'] = memory_trend.get('trend', 'stable')
                combined_stats['trend_direction'] = memory_trend.get('direction', 'none')
            except Exception as e:
                logger.debug(f"Could not get memory trend: {e}")
                combined_stats['memory_trend'] = 'unknown'
                combined_stats['trend_direction'] = 'none'
            
            # Check if memory is critical
            combined_stats['is_memory_critical'] = self.memory_manager.is_memory_critical()
            combined_stats['memory_warning'] = self.memory_manager.is_memory_critical(threshold=0.7)  # Warning at 70%
            
            return combined_stats
            
        except Exception as e:
            logger.error(f"Error getting enhanced memory usage: {e}")
            # Fallback to basic stats
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                system_memory = psutil.virtual_memory()
                
                return {
                    "rss_mb": memory_info.rss / 1024 / 1024,
                    "percent": process.memory_percent(),
                    "vms_mb": memory_info.vms / 1024 / 1024,
                    "available_mb": system_memory.available / 1024 / 1024,
                    'temp_files_count': len(self.temp_files) if hasattr(self, 'temp_files') else 0,
                    'is_memory_critical': False,
                    'memory_warning': False,
                    'memory_trend': 'unknown',
                    'trend_direction': 'none'
                }
            except Exception as fallback_error:
                logger.error(f"Fallback memory usage failed: {fallback_error}")
                return {
                    "rss_mb": 0,
                    "percent": 0,
                    "vms_mb": 0,
                    "available_mb": 0,
                    'temp_files_count': 0,
                    'is_memory_critical': False,
                    'memory_warning': False,
                    'memory_trend': 'unknown',
                    'trend_direction': 'none'
                }
        
    def should_process_in_chunks(self, video_path: str) -> bool:
        """Determine if video should be processed in chunks based on size, duration, and memory"""
        try:
            # Check current memory usage
            memory_stats = self.get_memory_usage()
            if memory_stats.get('percent', 0) > 70:  # High memory usage
                logger.info("High memory usage detected, enabling chunked processing")
                return True
            
            # Check file size (>1GB for safety)
            file_size = os.path.getsize(video_path)
            if file_size > 1024 * 1024 * 1024:  # 1GB
                logger.info(f"Large file detected ({file_size / 1024 / 1024 / 1024:.1f}GB), enabling chunked processing")
                return True
                
            # Check video duration (>3 minutes for safety)
            with self.managed_video_clip(video_path) as video:
                duration = video.duration
                if duration > 180:  # 3 minutes
                    logger.info(f"Long video detected ({duration:.1f}s), enabling chunked processing")
                    return True
                    
            return False
        except Exception as e:
            logger.warning(f"Could not determine video properties: {e}")
            return True  # Default to chunked processing for safety
    
    def _generate_cache_key(self, video_path: str, operation: str) -> str:
        """Generate a unique cache key for video operations"""
        try:
            # Get file stats for cache invalidation
            stat = os.stat(video_path)
            file_info = f"{video_path}_{stat.st_size}_{stat.st_mtime}_{operation}"
            return hashlib.md5(file_info.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Could not generate cache key: {e}")
            return hashlib.md5(f"{video_path}_{operation}".encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str):
        """Get cached result if available"""
        if not self.enable_caching:
            return None
        return cache_manager.get(cache_key)
    
    def _cache_result(self, cache_key: str, result: Any):
        """Cache operation result"""
        if not self.enable_caching:
            return
        cache_manager.set(cache_key, result)
    
    async def compress_video_async(self, video_path: str, output_path: str = None, 
                                 quality: str = None) -> str:
        """Compress video asynchronously"""
        quality = quality or self.compression_quality
        return await async_compress_video(video_path, output_path, quality)
    
    async def generate_thumbnails_async(self, video_path: str, count: int = None) -> List[str]:
        """Generate multiple thumbnails asynchronously"""
        count = count or self.thumbnail_count
        return await async_generate_multiple_thumbnails(video_path, count)
        
    @memory_manager.memory_monitor
    def extract_audio(self, video_path: str) -> str:
        """Extract audio from video file with memory management and caching"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(video_path, "audio_extraction")
            cached_result = self._get_cached_result(cache_key)
            if cached_result and os.path.exists(cached_result):
                logger.info("Using cached audio extraction result")
                return cached_result
            
            # Check memory usage before processing
            memory_stats = self.get_memory_usage()
            if memory_stats.get('percent', 0) > self.max_memory_usage:
                logger.warning("High memory usage detected, performing cleanup")
                self.force_memory_cleanup()
            
            with self.managed_temp_file(suffix=".wav", prefix="audio_") as audio_path:
                # Use managed video clip for automatic cleanup
                with self.managed_video_clip(video_path) as video:
                    if video.audio is None:
                        logger.warning("Video has no audio track, creating silent audio placeholder")
                        # Create a silent audio file as placeholder
                        from moviepy.audio.AudioClip import AudioClip
                        duration = video.duration
                        silent_audio = AudioClip(lambda t: [0, 0], duration=duration, fps=22050)
                        silent_audio.write_audiofile(audio_path, verbose=False, logger=None)
                        silent_audio.close()
                    else:
                        audio = video.audio
                        audio.write_audiofile(audio_path, verbose=False, logger=None)
                        audio.close()
                
                # Return a copy of the audio file that won't be auto-deleted
                permanent_audio_path = os.path.join(self.temp_dir, "extracted_audio.wav")
                import shutil
                shutil.copy2(audio_path, permanent_audio_path)
                self._temp_files.append(permanent_audio_path)
                
                # Cache the result
                self._cache_result(cache_key, permanent_audio_path)
                
                return permanent_audio_path
            
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            # Force cleanup on error
            self.force_memory_cleanup()
            raise
    
    def _preprocess_audio(self, audio: AudioSegment) -> AudioSegment:
        """Enhanced audio preprocessing for better speech recognition"""
        try:
            logger.debug(f"Starting audio preprocessing - Original: {len(audio)}ms, {audio.frame_rate}Hz, {audio.channels} channels")
            
            # Step 1: Convert to mono first
            if audio.channels > 1:
                audio = audio.set_channels(1)
                logger.debug("Converted to mono")
            
            # Step 2: Normalize audio levels
            normalized_audio = audio.normalize()
            logger.debug(f"Normalized audio - dBFS: {normalized_audio.dBFS:.2f}")
            
            # Step 3: Apply dynamic range compression for consistent levels
            if normalized_audio.dBFS < -25:
                # Audio is very quiet, amplify more aggressively
                gain_needed = abs(normalized_audio.dBFS) - 15  # Target -15 dBFS
                normalized_audio = normalized_audio + min(gain_needed, 20)  # Cap gain at 20dB
                logger.debug(f"Applied gain: {min(gain_needed, 20):.1f}dB")
            elif normalized_audio.dBFS > -5:
                # Audio is too loud, reduce it
                reduction_needed = normalized_audio.dBFS + 10  # Target -10 dBFS
                normalized_audio = normalized_audio - reduction_needed
                logger.debug(f"Applied reduction: {reduction_needed:.1f}dB")
            
            # Step 4: Apply high-pass filter to remove low-frequency noise
            # This helps remove rumble and background noise
            try:
                # Simple high-pass filter using pydub
                if hasattr(normalized_audio, 'high_pass_filter'):
                    normalized_audio = normalized_audio.high_pass_filter(80)  # Remove below 80Hz
                    logger.debug("Applied high-pass filter (80Hz)")
            except Exception as filter_error:
                logger.debug(f"High-pass filter not available: {filter_error}")
            
            # Step 5: Set optimal sample rate for speech recognition
            target_frame_rate = 16000  # Optimal for most speech recognition systems
            if normalized_audio.frame_rate != target_frame_rate:
                normalized_audio = normalized_audio.set_frame_rate(target_frame_rate)
                logger.debug(f"Resampled to {target_frame_rate}Hz")
            
            # Step 6: Apply gentle compression to even out volume levels
            try:
                # Simple compression by reducing dynamic range
                if normalized_audio.max_dBFS - normalized_audio.dBFS > 20:
                    # Large dynamic range, apply gentle compression
                    compressed = normalized_audio.compress_dynamic_range(threshold=-20.0, ratio=3.0, attack=5.0, release=50.0)
                    normalized_audio = compressed
                    logger.debug("Applied dynamic range compression")
            except Exception as comp_error:
                logger.debug(f"Dynamic range compression not available: {comp_error}")
            
            # Step 7: Ensure minimum duration for processing
            if len(normalized_audio) < 500:  # Less than 0.5 seconds
                logger.warning(f"Audio segment too short ({len(normalized_audio)}ms), padding")
                # Pad with silence to minimum duration
                silence_needed = 500 - len(normalized_audio)
                silence = AudioSegment.silent(duration=silence_needed)
                normalized_audio = normalized_audio + silence
            
            logger.debug(f"Audio preprocessing completed - Final: {len(normalized_audio)}ms, {normalized_audio.frame_rate}Hz, {normalized_audio.dBFS:.2f}dBFS")
            return normalized_audio
            
        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            # Return original audio if preprocessing fails
            try:
                # At minimum, ensure mono and reasonable sample rate
                fallback_audio = audio.set_channels(1).set_frame_rate(16000)
                logger.warning("Using fallback audio preprocessing")
                return fallback_audio
            except Exception as fallback_error:
                logger.error(f"Fallback preprocessing also failed: {fallback_error}")
                return audio
    
    def _transcribe_with_google(self, audio_data, chunk_index: int) -> str:
        """Transcribe audio using Google Speech Recognition with enhanced retry logic"""
        max_retries = 3
        retry_delays = [1, 2, 4]  # Progressive backoff
        
        for attempt in range(max_retries):
            try:
                # Use different recognition strategies based on attempt
                if attempt == 0:
                    # Standard recognition with enhanced parameters
                    timeout = 15
                    try:
                        text = self.recognizer.recognize_google(
                            audio_data, 
                            language='en-US', 
                            show_all=False,
                            with_confidence=False
                        )
                        if text and text.strip():
                            logger.info(f"Google Speech Recognition succeeded for chunk {chunk_index+1} on attempt {attempt+1}")
                            return text
                    except Exception:
                        pass
                elif attempt == 1:
                    # Try with different language hints and broader recognition
                    timeout = 20
                    try:
                        # Try with show_all=True for alternative results
                        result = self.recognizer.recognize_google(
                            audio_data, 
                            language='en-US', 
                            show_all=True
                        )
                        if isinstance(result, dict) and 'alternative' in result:
                            alternatives = result['alternative']
                            if alternatives and len(alternatives) > 0:
                                text = alternatives[0].get('transcript', '')
                                if text and text.strip():
                                    logger.info(f"Google Speech Recognition succeeded for chunk {chunk_index+1} on attempt {attempt+1} (alternative)")
                                    return text
                        elif isinstance(result, str) and result.strip():
                            logger.info(f"Google Speech Recognition succeeded for chunk {chunk_index+1} on attempt {attempt+1}")
                            return result
                    except Exception:
                        pass
                else:
                    # Final attempt with extended timeout and fallback language
                    timeout = 30
                
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.recognizer.recognize_google, audio_data)
                    try:
                        text = future.result(timeout=timeout)
                        if text and text.strip():
                            logger.info(f"Google Speech Recognition succeeded for chunk {chunk_index+1} on attempt {attempt+1}")
                            return text
                    except FutureTimeoutError:
                        logger.warning(f"Google Speech Recognition timeout for chunk {chunk_index+1}, attempt {attempt+1} (timeout: {timeout}s)")
                        future.cancel()
                        if attempt < max_retries - 1:
                            time.sleep(retry_delays[attempt])
                        continue
                        
            except sr.UnknownValueError:
                logger.debug(f"Google could not understand audio in chunk {chunk_index+1}, attempt {attempt+1}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
                break  # Final attempt failed
            except sr.RequestError as e:
                logger.warning(f"Google Speech Recognition request failed for chunk {chunk_index+1}, attempt {attempt+1}: {e}")
                if "quota" in str(e).lower() or "limit" in str(e).lower():
                    logger.error(f"Google API quota/limit reached for chunk {chunk_index+1}")
                    break  # Don't retry quota errors
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                continue
            except Exception as e:
                logger.error(f"Unexpected error in Google recognition for chunk {chunk_index+1}, attempt {attempt+1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                    continue
                break
        
        logger.warning(f"Google Speech Recognition failed for chunk {chunk_index+1} after {max_retries} attempts")
        return None
    
    def _preprocess_audio_for_speech(self, audio_chunk: AudioSegment) -> AudioSegment:
        """Enhanced audio preprocessing for better speech recognition accuracy"""
        try:
            # Start with the original audio
            processed = audio_chunk
            
            # 1. Normalize audio levels
            target_dBFS = -20.0
            change_in_dBFS = target_dBFS - processed.dBFS
            processed = processed.apply_gain(change_in_dBFS)
            
            # 2. Convert to mono if stereo (speech recognition works better with mono)
            if processed.channels > 1:
                processed = processed.set_channels(1)
            
            # 3. Ensure optimal sample rate for speech recognition (16kHz)
            if processed.frame_rate != 16000:
                processed = processed.set_frame_rate(16000)
            
            # 4. Apply high-pass filter to remove low-frequency noise
            # Remove frequencies below 80Hz (typical for speech)
            processed = processed.high_pass_filter(80)
            
            # 5. Apply low-pass filter to remove high-frequency noise
            # Keep frequencies below 8kHz (sufficient for speech)
            processed = processed.low_pass_filter(8000)
            
            # 6. Dynamic range compression for consistent volume
            # Compress dynamic range to make quiet parts louder
            processed = processed.compress_dynamic_range(threshold=-25.0, ratio=4.0, attack=5.0, release=50.0)
            
            # 7. Noise reduction using spectral gating (simple implementation)
            # Split into small segments and analyze
            segment_length = 100  # 100ms segments
            segments = []
            
            for i in range(0, len(processed), segment_length):
                segment = processed[i:i + segment_length]
                if len(segment) < 50:  # Skip very short segments
                    continue
                    
                # Simple noise gate: if segment is too quiet, reduce its volume further
                if segment.dBFS < -40:  # Very quiet segment, likely noise
                    segment = segment.apply_gain(-10)  # Make it even quieter
                elif segment.dBFS > -10:  # Very loud segment, might be clipping
                    segment = segment.apply_gain(-5)  # Reduce slightly
                    
                segments.append(segment)
            
            if segments:
                processed = sum(segments)
            
            # 8. Final normalization to ensure consistent levels
            if processed.dBFS < -30:
                processed = processed.apply_gain(-25 - processed.dBFS)
            elif processed.dBFS > -10:
                processed = processed.apply_gain(-15 - processed.dBFS)
            
            speech_logger.debug(f"Audio preprocessing completed: {audio_chunk.dBFS:.2f}dBFS -> {processed.dBFS:.2f}dBFS")
            return processed
            
        except Exception as e:
            speech_logger.warning(f"Audio preprocessing failed, using original: {e}")
            return audio_chunk
    
    def _transcribe_with_whisper(self, chunk_path: str, chunk_index: int) -> str:
        """Transcribe audio using Whisper as fallback with enhanced options"""
        if not self.whisper_model:
            logger.debug(f"Whisper model not available for chunk {chunk_index+1}")
            return None
        
        try:
            logger.info(f"Using Whisper fallback for chunk {chunk_index+1}")
            
            # Enhanced Whisper options for better accuracy
            result = self.whisper_model.transcribe(
                chunk_path,
                language='en',  # Specify language for better performance
                task='transcribe',
                temperature=0.0,  # More deterministic output
                best_of=2,  # Try multiple decodings
                beam_size=5,  # Use beam search for better accuracy
                patience=1.0,
                suppress_tokens=[-1],  # Suppress common noise tokens
                initial_prompt="This is a clear speech recording.",  # Help with context
                condition_on_previous_text=False  # Don't rely on previous context
            )
            
            text = result.get('text', '').strip()
            confidence = result.get('avg_logprob', -1.0)
            
            # Filter out low-confidence results
            if text and confidence > -1.0:  # Reasonable confidence threshold
                logger.info(f"Whisper successfully transcribed chunk {chunk_index+1} (confidence: {confidence:.3f})")
                return text
            elif text:
                logger.warning(f"Whisper transcribed chunk {chunk_index+1} but with low confidence ({confidence:.3f}): '{text[:50]}...'")
                return text  # Still return it as it might be useful
            else:
                logger.warning(f"Whisper returned empty transcription for chunk {chunk_index+1}")
                
        except Exception as e:
            logger.error(f"Whisper transcription failed for chunk {chunk_index+1}: {e}")
            # Try to reload Whisper model if it failed
            try:
                if WHISPER_AVAILABLE:
                    logger.info("Attempting to reload Whisper model...")
                    self.whisper_model = whisper.load_model("base")
                    # Retry once with reloaded model
                    result = self.whisper_model.transcribe(chunk_path, language='en')
                    text = result.get('text', '').strip()
                    if text:
                        logger.info(f"Whisper retry succeeded for chunk {chunk_index+1}")
                        return text
            except Exception as retry_error:
                logger.error(f"Whisper model reload failed: {retry_error}")
        
        return None
    
    def _transcribe_with_vosk(self, audio_data, chunk_index: int) -> str:
        """Transcribe audio using Vosk offline speech recognition"""
        if not self.vosk_model or not self.vosk_recognizer:
            speech_logger.debug(f"Vosk model not available for chunk {chunk_index+1}")
            return None
        
        try:
            speech_logger.info(f"Using Vosk offline recognition for chunk {chunk_index+1}")
            
            # Convert audio data to the format expected by Vosk (16kHz, mono, 16-bit)
            # Get raw audio data
            raw_data = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
            
            # Reset recognizer for new audio
            self.vosk_recognizer.Reset()
            
            # Process audio in chunks for better performance
            chunk_size = 4000  # Process in 4KB chunks
            results = []
            
            for i in range(0, len(raw_data), chunk_size):
                chunk = raw_data[i:i + chunk_size]
                if self.vosk_recognizer.AcceptWaveform(chunk):
                    result = vosk_json.loads(self.vosk_recognizer.Result())
                    if result.get('text'):
                        results.append(result['text'])
            
            # Get final result
            final_result = vosk_json.loads(self.vosk_recognizer.FinalResult())
            if final_result.get('text'):
                results.append(final_result['text'])
            
            # Combine all results
            full_text = ' '.join(results).strip()
            
            if full_text:
                speech_logger.info(f"Vosk successfully transcribed chunk {chunk_index+1}: '{full_text[:50]}...'")
                return full_text
            else:
                speech_logger.warning(f"Vosk returned empty transcription for chunk {chunk_index+1}")
                return None
                
        except Exception as e:
            speech_logger.error(f"Vosk transcription failed for chunk {chunk_index+1}: {e}")
            return None
    
    def _create_smart_chunks(self, audio: AudioSegment) -> List[AudioSegment]:
        """Create audio chunks with advanced speech boundary preservation and adaptive strategies"""
        try:
            audio_logger.debug(f"Creating smart chunks for audio: {len(audio)}ms, {audio.dBFS:.2f}dBFS")
            
            # Analyze audio characteristics for adaptive chunking
            audio_stats = self._analyze_audio_characteristics(audio)
            audio_logger.debug(f"Audio characteristics: {audio_stats}")
            
            # Strategy 1: Enhanced silence-based splitting with adaptive thresholds
            chunks = None
            
            # Adaptive silence strategies based on audio characteristics
            if audio_stats['is_noisy']:
                # Noisy audio needs more aggressive silence detection
                silence_strategies = [
                    {"min_silence_len": 600, "thresh_offset": -8, "keep_silence": 400, "name": "noisy_conservative"},
                    {"min_silence_len": 400, "thresh_offset": -6, "keep_silence": 300, "name": "noisy_moderate"},
                    {"min_silence_len": 300, "thresh_offset": -4, "keep_silence": 200, "name": "noisy_aggressive"}
                ]
            elif audio_stats['is_quiet']:
                # Quiet audio needs sensitive silence detection
                silence_strategies = [
                    {"min_silence_len": 200, "thresh_offset": -20, "keep_silence": 150, "name": "quiet_sensitive"},
                    {"min_silence_len": 150, "thresh_offset": -18, "keep_silence": 100, "name": "quiet_moderate"},
                    {"min_silence_len": 100, "thresh_offset": -15, "keep_silence": 75, "name": "quiet_aggressive"}
                ]
            else:
                # Normal audio uses standard strategies
                silence_strategies = [
                    {"min_silence_len": 400, "thresh_offset": -14, "keep_silence": 300, "name": "standard_conservative"},
                    {"min_silence_len": 300, "thresh_offset": -12, "keep_silence": 250, "name": "standard_moderate"},
                    {"min_silence_len": 200, "thresh_offset": -10, "keep_silence": 200, "name": "standard_aggressive"},
                    {"min_silence_len": 150, "thresh_offset": -8, "keep_silence": 150, "name": "standard_very_aggressive"}
                ]
            
            for strategy in silence_strategies:
                try:
                    silence_thresh = audio.dBFS + strategy["thresh_offset"]
                    audio_logger.debug(f"Trying {strategy['name']} silence detection: thresh={silence_thresh:.1f}dBFS, min_len={strategy['min_silence_len']}ms")
                    
                    # Split on silence with enhanced parameters
                    test_chunks = split_on_silence(
                        audio,
                        min_silence_len=strategy["min_silence_len"],
                        silence_thresh=silence_thresh,
                        keep_silence=strategy["keep_silence"],
                        seek_step=10  # More precise silence detection
                    )
                    
                    # Enhanced chunk validation
                    valid_chunks = []
                    for chunk in test_chunks:
                        # Filter by duration and quality
                        if len(chunk) >= 800:  # At least 0.8 seconds
                            # Check if chunk has meaningful audio content
                            if chunk.dBFS > -50:  # Not just silence
                                valid_chunks.append(chunk)
                            else:
                                audio_logger.debug(f"Skipping very quiet chunk ({chunk.dBFS:.1f}dBFS)")
                        else:
                            audio_logger.debug(f"Skipping short chunk ({len(chunk)}ms)")
                    
                    # Adaptive chunk count validation based on audio length
                    audio_minutes = len(audio) / 60000
                    max_chunks = max(3, min(25, int(audio_minutes * 8)))  # 3-25 chunks, ~8 per minute
                    min_chunks = max(1, int(audio_minutes * 0.5))  # At least 0.5 chunks per minute
                    
                    if len(valid_chunks) >= min_chunks and len(valid_chunks) <= max_chunks:
                        chunks = valid_chunks
                        audio_logger.info(f"Silence-based chunking succeeded with {strategy['name']} strategy: {len(chunks)} chunks for {audio_minutes:.1f}min audio")
                        break
                    elif len(valid_chunks) > max_chunks:
                        audio_logger.debug(f"Strategy {strategy['name']} produced too many chunks ({len(valid_chunks)}>{max_chunks}), trying next")
                    else:
                        audio_logger.debug(f"Strategy {strategy['name']} produced too few chunks ({len(valid_chunks)}<{min_chunks}), trying next")
                        
                except Exception as strategy_error:
                    audio_logger.debug(f"Silence strategy {strategy['name']} failed: {strategy_error}")
                    continue
            
            # Strategy 2: If silence-based splitting failed, use intelligent fixed-duration chunking
            if not chunks or len(chunks) < 2:
                audio_logger.info("Silence-based chunking failed, using intelligent fixed-duration chunking")
                
                total_duration = len(audio)
                audio_minutes = total_duration / 60000
                
                # Enhanced adaptive chunk duration with speech pattern consideration
                if audio_stats['has_speech_patterns']:
                    # Speech-heavy content benefits from shorter chunks
                    if total_duration <= 30000:  # 30 seconds or less
                        chunk_duration = 8000   # 8 second chunks for speech
                    elif total_duration <= 60000:  # 1 minute or less
                        chunk_duration = 12000  # 12 second chunks
                    elif total_duration <= 120000:  # 2 minutes or less
                        chunk_duration = 18000  # 18 second chunks
                    elif total_duration <= 300000:  # 5 minutes or less
                        chunk_duration = 25000  # 25 second chunks
                    else:
                        chunk_duration = 35000  # 35 second chunks for very long speech
                else:
                    # Non-speech content can use longer chunks
                    if total_duration <= 30000:
                        chunk_duration = 15000  # 15 second chunks
                    elif total_duration <= 60000:
                        chunk_duration = 20000  # 20 second chunks
                    elif total_duration <= 120000:
                        chunk_duration = 30000  # 30 second chunks
                    elif total_duration <= 300000:
                        chunk_duration = 40000  # 40 second chunks
                    else:
                        chunk_duration = 50000  # 50 second chunks
                
                # Adaptive overlap based on content type
                if audio_stats['has_speech_patterns']:
                    overlap = 3000  # 3 second overlap for speech to preserve words
                else:
                    overlap = 1500  # 1.5 second overlap for non-speech
                
                chunks = []
                for i in range(0, len(audio), chunk_duration - overlap):
                    chunk_end = min(i + chunk_duration, len(audio))
                    chunk = audio[i:chunk_end]
                    
                    # Enhanced chunk validation
                    if len(chunk) >= 3000:  # At least 3 seconds
                        # Check for meaningful audio content
                        if chunk.dBFS > -55:  # Not just silence
                            chunks.append(chunk)
                        else:
                            audio_logger.debug(f"Skipping silent chunk at {i/1000:.1f}s")
                    elif i == 0:  # First chunk, even if short
                        chunks.append(chunk)
                    else:
                        audio_logger.debug(f"Skipping short chunk at {i/1000:.1f}s ({len(chunk)}ms)")
                
                audio_logger.info(f"Created {len(chunks)} fixed-duration chunks (avg {chunk_duration/1000:.1f}s each)")
            
            # Strategy 3: Final validation and optimization
            if chunks:
                # Merge very short chunks with adjacent ones
                optimized_chunks = []
                i = 0
                while i < len(chunks):
                    current_chunk = chunks[i]
                    
                    # If current chunk is very short, try to merge with next
                    if len(current_chunk) < 2000 and i < len(chunks) - 1:
                        next_chunk = chunks[i + 1]
                        merged = current_chunk + next_chunk
                        if len(merged) <= 60000:  # Don't create chunks longer than 1 minute
                            optimized_chunks.append(merged)
                            i += 2  # Skip next chunk as it's been merged
                            logger.debug(f"Merged short chunk {i-1} with chunk {i}")
                            continue
                    
                    optimized_chunks.append(current_chunk)
                    i += 1
                
                chunks = optimized_chunks
                
                # Log chunk statistics
                chunk_lengths = [len(chunk) / 1000 for chunk in chunks]  # Convert to seconds
                avg_length = sum(chunk_lengths) / len(chunk_lengths)
                min_length = min(chunk_lengths)
                max_length = max(chunk_lengths)
                
                logger.info(f"Final chunking result: {len(chunks)} chunks, avg: {avg_length:.1f}s, range: {min_length:.1f}s-{max_length:.1f}s")
                
                return chunks
            
            # Strategy 4: Ultimate fallback - return entire audio as single chunk
            audio_logger.warning("All chunking strategies failed, using entire audio as single chunk")
            return [audio]
            
        except Exception as e:
            audio_logger.error(f"Error creating audio chunks: {e}")
            # Ultimate fallback: return the entire audio as one chunk
            return [audio]
    
    def _analyze_audio_characteristics(self, audio: AudioSegment) -> Dict[str, Any]:
        """Analyze audio characteristics to guide chunking strategy"""
        try:
            # Basic characteristics
            duration_s = len(audio) / 1000
            volume_db = audio.dBFS
            
            # Analyze volume distribution
            samples = audio.get_array_of_samples()
            if len(samples) > 0:
                import numpy as np
                samples_array = np.array(samples)
                volume_variance = np.var(samples_array)
                volume_std = np.std(samples_array)
                
                # Analyze dynamic range
                max_amplitude = np.max(np.abs(samples_array))
                min_amplitude = np.min(np.abs(samples_array))
                dynamic_range = max_amplitude - min_amplitude if max_amplitude > 0 else 0
            else:
                volume_variance = 0
                volume_std = 0
                dynamic_range = 0
            
            # Determine characteristics
            is_quiet = volume_db < -30
            is_noisy = volume_variance > 1000000 or dynamic_range > 20000  # High variance/range indicates noise
            has_speech_patterns = (
                volume_std > 500 and 
                not is_quiet and 
                dynamic_range > 1000 and 
                volume_db > -40
            )  # Moderate variance with good volume suggests speech
            
            audio_logger.debug(
                f"Audio analysis: duration={duration_s:.1f}s, volume={volume_db:.1f}dB, "
                f"variance={volume_variance:.0f}, std={volume_std:.0f}, range={dynamic_range:.0f}"
            )
            
            return {
                'duration_s': duration_s,
                'volume_db': volume_db,
                'volume_variance': volume_variance,
                'volume_std': volume_std,
                'dynamic_range': dynamic_range,
                'is_quiet': is_quiet,
                'is_noisy': is_noisy,
                'has_speech_patterns': has_speech_patterns
            }
        except Exception as e:
            audio_logger.debug(f"Audio characteristics analysis failed: {e}")
            return {
                'duration_s': len(audio) / 1000,
                'volume_db': audio.dBFS,
                'volume_variance': 0,
                'volume_std': 0,
                'dynamic_range': 0,
                'is_quiet': False,
                'is_noisy': False,
                'has_speech_patterns': True  # Default assumption
            }
    
    @memory_manager.memory_monitor
    async def transcribe_audio(self, audio_path: str, progress_callback=None) -> TranscriptionResult:
        """Industry-standard async transcription with Whisper v3, enhanced error handling, and fallback system"""
        start_time = time.time()
        
        try:
            # Update processing status
            self.processing_status = ProcessingStatus.TRANSCRIBING
            
            # Check cache first
            cache_key = self._generate_cache_key(audio_path, "transcription_v3")
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                transcription_logger.info("Using cached transcription result")
                if progress_callback:
                    progress_callback("Using cached transcription...")
                return TranscriptionResult(
                    text=cached_result,
                    confidence=0.95,  # Cached results assumed high confidence
                    method=TranscriptionMethod.CACHED,
                    processing_time=time.time() - start_time,
                    success=True
                )
            
            if progress_callback:
                progress_callback("Loading and preprocessing audio...")
            
            # Enhanced audio loading with multiple format support
            audio = None
            audio_formats = ['wav', 'mp3', 'mp4', 'flac', 'ogg', 'm4a', 'aac']
            
            for fmt in audio_formats:
                try:
                    audio = AudioSegment.from_file(audio_path, format=fmt)
                    transcription_logger.debug(f"Successfully loaded audio using format: {fmt}")
                    break
                except Exception as e:
                    transcription_logger.debug(f"Failed to load audio with format {fmt}: {e}")
                    continue
            
            if audio is None:
                try:
                    # Final attempt without specifying format
                    audio = AudioSegment.from_file(audio_path)
                    transcription_logger.debug("Successfully loaded audio without format specification")
                except Exception as e:
                    transcription_logger.error(f"Failed to load audio file {audio_path} with all formats: {e}")
                    return TranscriptionResult(
                        text="[Audio file could not be loaded - unsupported format or corrupted file]",
                        confidence=0.0,
                        method=TranscriptionMethod.FALLBACK,
                        processing_time=time.time() - start_time,
                        success=False,
                        error=str(e)
                    )

            # Validate audio properties with industry standards
            if len(audio) < 500:  # Less than 0.5 seconds
                transcription_logger.warning(f"Audio file too short: {len(audio)}ms")
                return TranscriptionResult(
                    text="[Audio file too short for transcription]",
                    confidence=0.0,
                    method=TranscriptionMethod.FALLBACK,
                    processing_time=time.time() - start_time,
                    success=False,
                    error="Audio duration too short"
                )
            
            # Enhanced audio quality validation
            if audio.frame_rate < 8000:
                transcription_logger.warning(f"Audio sample rate too low: {audio.frame_rate}Hz")
                try:
                    audio = audio.set_frame_rate(16000)
                    transcription_logger.info("Resampled audio to 16kHz")
                except Exception as e:
                    transcription_logger.error(f"Failed to resample audio: {e}")
                    return TranscriptionResult(
                        text="[Audio quality too low for transcription]",
                        confidence=0.0,
                        method=TranscriptionMethod.FALLBACK,
                        processing_time=time.time() - start_time,
                        success=False,
                        error=str(e)
                    )

            # Industry-standard audio preprocessing
            if progress_callback:
                progress_callback("Applying industry-standard audio preprocessing...")
            
            try:
                audio = self._preprocess_audio(audio)
            except Exception as e:
                transcription_logger.warning(f"Audio preprocessing failed, using original: {e}")
                # Continue with original audio if preprocessing fails
            
            # Try each transcription method in priority order
            for method in self.transcription_priority:
                if progress_callback:
                    progress_callback(f"Attempting transcription with {method.value}...")
                
                try:
                    result = await self._transcribe_with_method(audio, method, progress_callback)
                    if result.success and result.confidence > 0.3:  # Minimum confidence threshold
                        # Cache successful result
                        try:
                            self._cache_result(cache_key, result.text)
                        except Exception as cache_error:
                            transcription_logger.warning(f"Failed to cache result: {cache_error}")
                        
                        result.processing_time = time.time() - start_time
                        transcription_logger.info(f"Transcription successful with {method.value} (confidence: {result.confidence:.2f})")
                        return result
                    else:
                        transcription_logger.warning(f"Low confidence result from {method.value}: {result.confidence:.2f}")
                        
                except Exception as e:
                    transcription_logger.error(f"Transcription failed with {method.value}: {e}")
                    continue
            
            # All methods failed - return fallback result
            transcription_logger.error("All transcription methods failed")
            return TranscriptionResult(
                text="[Transcription unavailable - all methods failed]",
                confidence=0.0,
                method=TranscriptionMethod.FALLBACK,
                processing_time=time.time() - start_time,
                success=False,
                error="All transcription methods failed"
            )
            
        except Exception as e:
            transcription_logger.error(f"Critical error in transcribe_audio: {str(e)}")
            import traceback
            transcription_logger.error(f"Traceback: {traceback.format_exc()}")
            if progress_callback:
                progress_callback(f"Transcription failed: {str(e)}")
            return TranscriptionResult(
                text="[Transcription failed - critical audio processing error]",
                confidence=0.0,
                method=TranscriptionMethod.FALLBACK,
                processing_time=time.time() - start_time,
                success=False,
                error=str(e)
            )
        finally:
            self.processing_status = ProcessingStatus.IDLE
    
    async def _transcribe_with_method(self, audio: AudioSegment, method: TranscriptionMethod, progress_callback=None) -> TranscriptionResult:
        """Industry-standard transcription with specific method and retry logic"""
        start_time = time.time()
        
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type((Exception,)),
            reraise=True
        )
        async def _transcribe_with_retry():
            if method == TranscriptionMethod.WHISPER:
                return await self._transcribe_with_whisper_v3(audio, progress_callback)
            elif method == TranscriptionMethod.GOOGLE:
                return await self._transcribe_with_google_enhanced(audio, progress_callback)
            elif method == TranscriptionMethod.VOSK:
                return await self._transcribe_with_vosk_enhanced(audio, progress_callback)
            else:
                raise ValueError(f"Unsupported transcription method: {method}")
        
        try:
            # Apply timeout for the entire transcription process
            result = await asyncio.wait_for(_transcribe_with_retry(), timeout=300)  # 5 minutes max
            result.processing_time = time.time() - start_time
            return result
        except asyncio.TimeoutError:
            transcription_logger.error(f"Transcription timeout with {method.value}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                method=method,
                processing_time=time.time() - start_time,
                success=False,
                error="Transcription timeout"
            )
        except Exception as e:
            transcription_logger.error(f"Transcription failed with {method.value}: {e}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                method=method,
                processing_time=time.time() - start_time,
                success=False,
                error=str(e)
            )
    
    async def _transcribe_with_whisper_v3(self, audio: AudioSegment, progress_callback=None) -> TranscriptionResult:
        """Enhanced Whisper v3 transcription with preprocessing and confidence calculation"""
        if not self.whisper_model:
            return TranscriptionResult(
                text="",
                confidence=0.0,
                method=TranscriptionMethod.WHISPER,
                processing_time=0.0,
                success=False,
                error="Whisper model not available"
            )
        
        try:
            # Preprocess audio for optimal Whisper performance
            processed_audio = await self._preprocess_audio_for_whisper(audio)
            
            # Export to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                processed_audio.export(
                    temp_file.name,
                    format="wav",
                    parameters=["-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le"]
                )
                
                if progress_callback:
                    progress_callback("Running Whisper v3 transcription...")
                
                # Run Whisper transcription
                result = self.whisper_model.transcribe(
                    temp_file.name,
                    language=None,  # Auto-detect
                    task="transcribe",
                    verbose=False,
                    word_timestamps=True,
                    temperature=0.0,  # Deterministic output
                    compression_ratio_threshold=2.4,
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.6
                )
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
                # Extract text and calculate confidence
                text = result.get("text", "").strip()
                confidence = self._calculate_whisper_confidence(result)
                
                return TranscriptionResult(
                    text=text,
                    confidence=confidence,
                    method=TranscriptionMethod.WHISPER,
                    processing_time=0.0,  # Will be set by caller
                    success=bool(text),
                    segments=result.get("segments", [])
                )
                
        except Exception as e:
            transcription_logger.error(f"Whisper v3 transcription failed: {e}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                method=TranscriptionMethod.WHISPER,
                processing_time=0.0,
                success=False,
                error=str(e)
            )
    
    async def _transcribe_with_google_enhanced(self, audio: AudioSegment, progress_callback=None) -> TranscriptionResult:
        """Enhanced Google Speech Recognition with async timeout handling"""
        if not self.recognizer:
            return TranscriptionResult(
                text="",
                confidence=0.0,
                method=TranscriptionMethod.GOOGLE,
                processing_time=0.0,
                success=False,
                error="Google Speech recognizer not available"
            )
        
        try:
            # Export audio for Google Speech
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                audio.export(
                    temp_file.name,
                    format="wav",
                    parameters=["-ac", "1", "-ar", "16000"]
                )
                
                if progress_callback:
                    progress_callback("Running Google Speech Recognition...")
                
                # Use asyncio to handle blocking Google Speech API call
                def _google_transcribe():
                    with sr.AudioFile(temp_file.name) as source:
                        # Adjust for ambient noise
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        audio_data = self.recognizer.record(source)
                        
                        # Recognize with enhanced settings
                        return self.recognizer.recognize_google(
                            audio_data,
                            language="en-US",
                            show_all=True  # Get confidence scores
                        )
                
                # Run with timeout
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, _google_transcribe),
                    timeout=60  # 1 minute timeout
                )
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
                # Process result
                if isinstance(result, dict) and "alternative" in result:
                    alternatives = result["alternative"]
                    if alternatives:
                        best_alternative = alternatives[0]
                        text = best_alternative.get("transcript", "").strip()
                        confidence = best_alternative.get("confidence", 0.5)
                        
                        return TranscriptionResult(
                            text=text,
                            confidence=confidence,
                            method=TranscriptionMethod.GOOGLE,
                            processing_time=0.0,
                            success=bool(text)
                        )
                elif isinstance(result, str):
                    # Simple string result
                    return TranscriptionResult(
                        text=result.strip(),
                        confidence=0.7,  # Default confidence for string results
                        method=TranscriptionMethod.GOOGLE,
                        processing_time=0.0,
                        success=bool(result.strip())
                    )
                
                return TranscriptionResult(
                    text="",
                    confidence=0.0,
                    method=TranscriptionMethod.GOOGLE,
                    processing_time=0.0,
                    success=False,
                    error="No transcription result"
                )
                
        except asyncio.TimeoutError:
            transcription_logger.error("Google Speech Recognition timeout")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                method=TranscriptionMethod.GOOGLE,
                processing_time=0.0,
                success=False,
                error="Google Speech timeout"
            )
        except Exception as e:
            transcription_logger.error(f"Google Speech Recognition failed: {e}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                method=TranscriptionMethod.GOOGLE,
                processing_time=0.0,
                success=False,
                error=str(e)
            )
    
    async def _transcribe_with_vosk_enhanced(self, audio: AudioSegment, progress_callback=None) -> TranscriptionResult:
        """Enhanced Vosk transcription - placeholder for future implementation"""
        # TODO: Implement enhanced Vosk transcription
        return TranscriptionResult(
            text="",
            confidence=0.0,
            method=TranscriptionMethod.VOSK,
            processing_time=0.0,
            success=False,
            error="Vosk enhanced transcription not yet implemented"
        )
    
    async def _preprocess_audio_for_whisper(self, audio: AudioSegment) -> AudioSegment:
        """Preprocess audio for optimal Whisper performance"""
        try:
            # Normalize audio levels
            normalized_audio = audio.normalize()
            
            # Ensure mono channel
            if normalized_audio.channels > 1:
                normalized_audio = normalized_audio.set_channels(1)
            
            # Set optimal sample rate for Whisper (16kHz)
            if normalized_audio.frame_rate != 16000:
                normalized_audio = normalized_audio.set_frame_rate(16000)
            
            # Apply noise reduction if audio is very quiet
            if normalized_audio.dBFS < -30:
                # Boost quiet audio
                normalized_audio = normalized_audio + (abs(normalized_audio.dBFS) - 20)
            
            return normalized_audio
            
        except Exception as e:
            transcription_logger.warning(f"Audio preprocessing failed: {e}")
            return audio  # Return original if preprocessing fails
    
    def _calculate_whisper_confidence(self, whisper_result: dict) -> float:
        """Calculate confidence score from Whisper result"""
        try:
            segments = whisper_result.get("segments", [])
            if not segments:
                return 0.5  # Default confidence
            
            # Calculate average confidence from segments
            total_confidence = 0.0
            total_duration = 0.0
            
            for segment in segments:
                duration = segment.get("end", 0) - segment.get("start", 0)
                if duration > 0:
                    # Use average log probability as confidence indicator
                    avg_logprob = segment.get("avg_logprob", -1.0)
                    # Convert log probability to confidence (0-1)
                    confidence = max(0.0, min(1.0, (avg_logprob + 1.0)))
                    
                    total_confidence += confidence * duration
                    total_duration += duration
            
            if total_duration > 0:
                return total_confidence / total_duration
            else:
                return 0.5
                
        except Exception as e:
            transcription_logger.warning(f"Confidence calculation failed: {e}")
            return 0.5  # Default confidence

    @memory_manager.memory_monitor
    def process_video_chunk(self, video_path: str, start_time: float, end_time: float, progress_callback=None) -> Dict[str, Any]:
        """Process a chunk of video for analysis with memory management"""
        try:
            # Check memory usage before processing
            memory_stats = self.get_memory_usage()
            if memory_stats.get('system_memory_percent', 0) > self.max_memory_usage:
                logger.warning(f"High memory usage before chunk processing: {memory_stats['rss_mb']:.1f}MB")
                self.force_memory_cleanup()
            
            with self.managed_temp_file(suffix=".mp4", prefix=f"chunk_{start_time}_{end_time}_") as temp_chunk_path:
                # Extract chunk using managed video clip
                with self.managed_video_clip(video_path) as video:
                    chunk = video.subclip(start_time, end_time)
                    chunk.write_videofile(temp_chunk_path, verbose=False, logger=None)
                    chunk.close()
                
                # Analyze the chunk
                chunk_features = self._analyze_chunk_features(temp_chunk_path, progress_callback)
                
                # Force cleanup after chunk processing
                gc.collect()
                
                return chunk_features
            
        except Exception as e:
            logger.error(f"Error processing video chunk {start_time}-{end_time}: {e}")
            # Force cleanup on error
            self.force_memory_cleanup()
            return {"motion_scores": [], "brightness_scores": [], "color_variance_scores": []}
    
    def _analyze_chunk_features(self, video_path: str, progress_callback=None) -> Dict[str, Any]:
        """Analyze features for a video chunk"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Could not open video file: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            motion_scores = []
            brightness_scores = []
            color_variance_scores = []
            
            prev_frame = None
            sample_rate = max(1, int(fps * 2))  # Sample every 2 seconds
            total_samples = frame_count // sample_rate
            processed_samples = 0
            
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % sample_rate == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    if prev_frame is not None:
                        diff = cv2.absdiff(prev_frame, gray)
                        motion_score = np.mean(diff)
                        motion_scores.append(motion_score)
                    
                    brightness = np.mean(gray)
                    brightness_scores.append(brightness)
                    
                    color_variance = np.var(frame)
                    color_variance_scores.append(color_variance)
                    
                    prev_frame = gray
                    processed_samples += 1
                    
                    if progress_callback and total_samples > 0:
                        progress = (processed_samples / total_samples) * 100
                        progress_callback(f"Analyzing chunk features: {progress:.1f}%")
                
                frame_idx += 1
            
            cap.release()
            
            return {
                "motion_scores": motion_scores,
                "brightness_scores": brightness_scores,
                "color_variance_scores": color_variance_scores
            }
            
        except Exception as e:
            logger.error(f"Error analyzing chunk features: {e}")
            return {"motion_scores": [], "brightness_scores": [], "color_variance_scores": []}
    
    def analyze_video_features(self, video_path: str, progress_callback=None) -> Dict[str, Any]:
        """Analyze video features for virality potential"""
        try:
            # Check if we should process in chunks
            if self.should_process_in_chunks(video_path):
                return self._analyze_video_features_chunked(video_path, progress_callback)
            else:
                return self._analyze_video_features_direct(video_path, progress_callback)
                
        except Exception as e:
            logger.error(f"Error analyzing video features: {e}")
            return {
                "motion_scores": [],
                "brightness_scores": [],
                "color_variance_scores": [],
                "avg_motion": 0,
                "avg_brightness": 0,
                "avg_color_variance": 0,
                "duration": 0
            }
    
    def _analyze_video_features_chunked(self, video_path: str, progress_callback=None) -> Dict[str, Any]:
        """Analyze video features using chunked processing for large videos"""
        try:
            if progress_callback:
                progress_callback("Processing large video in chunks...")
            
            # Get video duration using managed clip
            with self.managed_video_clip(video_path) as video:
                duration = video.duration
            
            # Calculate chunks
            num_chunks = int(np.ceil(duration / self.chunk_duration))
            all_motion_scores = []
            all_brightness_scores = []
            all_color_variance_scores = []
            
            logger.info(f"Processing {num_chunks} chunks for video of {duration:.1f}s duration")
            
            for i in range(num_chunks):
                start_time = i * self.chunk_duration
                end_time = min((i + 1) * self.chunk_duration, duration)
                
                if progress_callback:
                    progress_callback(f"Processing chunk {i+1}/{num_chunks} ({start_time:.1f}s-{end_time:.1f}s)")
                
                # Check memory usage before processing chunk
                memory_usage = self.get_memory_usage()
                if memory_usage.get('system_memory_percent', 0) > self.max_memory_usage:
                    logger.warning(f"Memory usage high ({memory_usage['rss_mb']:.1f}MB), forcing cleanup")
                    self.force_memory_cleanup()
                
                chunk_features = self.process_video_chunk(video_path, start_time, end_time, progress_callback)
                
                # Aggregate results
                all_motion_scores.extend(chunk_features.get("motion_scores", []))
                all_brightness_scores.extend(chunk_features.get("brightness_scores", []))
                all_color_variance_scores.extend(chunk_features.get("color_variance_scores", []))
                
                # Periodic cleanup every 5 chunks
                if (i + 1) % 5 == 0:
                    logger.info(f"Periodic cleanup after chunk {i+1}")
                    gc.collect()
            
            # Final cleanup
            self.cleanup_resources()
            
            return self._compile_video_features(all_motion_scores, all_brightness_scores, all_color_variance_scores, duration)
            
        except Exception as e:
            logger.error(f"Error in chunked video analysis: {e}")
            # Force cleanup on error
            self.force_memory_cleanup()
            return {"motion_scores": [], "brightness_scores": [], "color_variance_scores": [], "avg_motion": 0, "avg_brightness": 0, "avg_color_variance": 0, "duration": 0}
    
    def detect_scene_changes(self, video_path: str, threshold: float = 0.3) -> List[float]:
        """Detect scene changes in video using histogram comparison"""
        try:
            cap = cv2.VideoCapture(video_path)
            scene_changes = []
            prev_hist = None
            frame_count = 0
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Calculate histogram
                hist = cv2.calcHist([frame], [0, 1, 2], None, [50, 50, 50], [0, 256, 0, 256, 0, 256])
                
                if prev_hist is not None:
                    # Compare histograms
                    correlation = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                    
                    # If correlation is low, it's likely a scene change
                    if correlation < threshold:
                        timestamp = frame_count / fps
                        scene_changes.append(timestamp)
                
                prev_hist = hist
                frame_count += 1
            
            cap.release()
            return scene_changes
            
        except Exception as e:
            logger.error(f"Error detecting scene changes: {e}")
            return []
    
    def detect_faces_and_emotions(self, video_path: str, sample_rate: int = 30) -> Dict[str, List]:
        """Detect faces and emotional expressions in video"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            face_detections = []
            smile_detections = []
            face_count_timeline = []
            
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % sample_rate == 0:
                    timestamp = frame_idx / fps
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # Detect faces
                    faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
                    face_count = len(faces)
                    face_count_timeline.append((timestamp, face_count))
                    
                    if face_count > 0:
                        face_detections.append(timestamp)
                        
                        # Detect smiles in face regions
                        for (x, y, w, h) in faces:
                            roi_gray = gray[y:y+h, x:x+w]
                            smiles = self.smile_cascade.detectMultiScale(roi_gray, 1.8, 20)
                            if len(smiles) > 0:
                                smile_detections.append(timestamp)
                                break
                
                frame_idx += 1
            
            cap.release()
            
            return {
                "face_detections": face_detections,
                "smile_detections": smile_detections,
                "face_count_timeline": face_count_timeline
            }
            
        except Exception as e:
            logger.error(f"Error detecting faces and emotions: {e}")
            return {"face_detections": [], "smile_detections": [], "face_count_timeline": []}
    
    def analyze_motion_intensity(self, video_path: str) -> Dict[str, Any]:
        """Analyze motion intensity with peak detection"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            motion_timeline = []
            prev_frame = None
            frame_idx = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                timestamp = frame_idx / fps
                
                if prev_frame is not None:
                    # Calculate optical flow
                    flow = cv2.calcOpticalFlowPyrLK(
                        prev_frame, gray, 
                        np.array([[100, 100]], dtype=np.float32).reshape(-1, 1, 2),
                        None
                    )[0]
                    
                    # Calculate motion magnitude
                    if flow is not None and len(flow) > 0:
                        motion_magnitude = np.linalg.norm(flow[0][0])
                    else:
                        motion_magnitude = 0
                    
                    motion_timeline.append((timestamp, motion_magnitude))
                
                prev_frame = gray
                frame_idx += 1
            
            cap.release()
            
            # Find motion peaks
            if motion_timeline:
                timestamps, magnitudes = zip(*motion_timeline)
                peaks, _ = scipy.signal.find_peaks(magnitudes, height=self.motion_threshold)
                motion_peaks = [timestamps[i] for i in peaks]
            else:
                motion_peaks = []
            
            return {
                "motion_timeline": motion_timeline,
                "motion_peaks": motion_peaks,
                "avg_motion": np.mean([m[1] for m in motion_timeline]) if motion_timeline else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing motion intensity: {e}")
            return {"motion_timeline": [], "motion_peaks": [], "avg_motion": 0}
    
    def analyze_audio_features(self, audio_path: str) -> Dict[str, Any]:
        """Advanced audio analysis for viral moment detection"""
        try:
            # Load audio with librosa
            y, sr = librosa.load(audio_path, sr=None)
            
            # Volume analysis
            volume_timeline = self._analyze_volume_spikes(y, sr)
            
            # Spectral analysis for laughter/applause detection
            spectral_features = self._analyze_spectral_features(y, sr)
            
            # Tempo and rhythm analysis
            tempo_features = self._analyze_tempo_features(y, sr)
            
            return {
                "volume_timeline": volume_timeline["timeline"],
                "volume_spikes": volume_timeline["spikes"],
                "spectral_features": spectral_features,
                "tempo_features": tempo_features,
                "duration": len(y) / sr
            }
            
        except Exception as e:
            logger.error(f"Error analyzing audio features: {e}")
            return {
                "volume_timeline": [],
                "volume_spikes": [],
                "spectral_features": {},
                "tempo_features": {},
                "duration": 0
            }
    
    def _analyze_volume_spikes(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Detect volume spikes that might indicate exciting moments"""
        try:
            # Calculate RMS energy in windows
            hop_length = 512
            frame_length = 2048
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            
            # Convert to dB
            rms_db = librosa.amplitude_to_db(rms)
            
            # Create timeline
            times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
            volume_timeline = list(zip(times, rms_db))
            
            # Find volume spikes
            mean_volume = np.mean(rms_db)
            std_volume = np.std(rms_db)
            spike_threshold = mean_volume + (self.volume_spike_threshold * std_volume)
            
            spikes = []
            for i, (time, volume) in enumerate(volume_timeline):
                if volume > spike_threshold:
                    spikes.append(time)
            
            return {
                "timeline": volume_timeline,
                "spikes": spikes,
                "mean_volume": float(mean_volume),
                "spike_threshold": float(spike_threshold)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volume spikes: {e}")
            return {"timeline": [], "spikes": [], "mean_volume": 0, "spike_threshold": 0}
    
    def _analyze_spectral_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze spectral features to detect laughter, applause, music"""
        try:
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y)[0]
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            
            # Detect potential laughter (high frequency content with irregular patterns)
            laughter_indicators = []
            applause_indicators = []
            
            hop_length = 512
            times = librosa.frames_to_time(np.arange(len(spectral_centroids)), sr=sr, hop_length=hop_length)
            
            for i, time in enumerate(times):
                # Laughter detection heuristics
                if (spectral_centroids[i] > np.mean(spectral_centroids) + np.std(spectral_centroids) and
                    zero_crossing_rate[i] > np.mean(zero_crossing_rate) + np.std(zero_crossing_rate)):
                    laughter_indicators.append(time)
                
                # Applause detection (broad spectrum, high energy)
                if (spectral_rolloff[i] > np.mean(spectral_rolloff) + np.std(spectral_rolloff) and
                    zero_crossing_rate[i] > np.mean(zero_crossing_rate)):
                    applause_indicators.append(time)
            
            return {
                "spectral_centroids": spectral_centroids.tolist(),
                "spectral_rolloff": spectral_rolloff.tolist(),
                "zero_crossing_rate": zero_crossing_rate.tolist(),
                "mfccs": mfccs.tolist(),
                "laughter_indicators": laughter_indicators,
                "applause_indicators": applause_indicators
            }
            
        except Exception as e:
            logger.error(f"Error analyzing spectral features: {e}")
            return {
                "spectral_centroids": [],
                "spectral_rolloff": [],
                "zero_crossing_rate": [],
                "mfccs": [],
                "laughter_indicators": [],
                "applause_indicators": []
            }
    
    def _analyze_tempo_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze tempo and rhythm for music/beat detection"""
        try:
            # Tempo estimation
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beats, sr=sr)
            
            # Onset detection
            onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
            onset_times = librosa.frames_to_time(onset_frames, sr=sr)
            
            return {
                "tempo": float(tempo),
                "beat_times": beat_times.tolist(),
                "onset_times": onset_times.tolist(),
                "rhythm_regularity": self._calculate_rhythm_regularity(beat_times)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing tempo features: {e}")
            return {"tempo": 0, "beat_times": [], "onset_times": [], "rhythm_regularity": 0}
    
    def _calculate_rhythm_regularity(self, beat_times: np.ndarray) -> float:
        """Calculate how regular the rhythm is (0-1, higher = more regular)"""
        try:
            if len(beat_times) < 3:
                return 0.0
            
            intervals = np.diff(beat_times)
            regularity = 1.0 - (np.std(intervals) / np.mean(intervals))
            return max(0.0, min(1.0, regularity))
            
        except Exception as e:
            logger.error(f"Error calculating rhythm regularity: {e}")
            return 0.0
    
    def analyze_transcript_sentiment(self, transcript: str) -> Dict[str, Any]:
        """Analyze sentiment and emotional peaks in transcript"""
        try:
            # Split transcript into sentences
            blob = TextBlob(transcript)
            sentences = blob.sentences
            
            sentiment_timeline = []
            emotional_peaks = []
            engaging_moments = []
            
            for i, sentence in enumerate(sentences):
                sentence_text = str(sentence)
                
                # VADER sentiment analysis
                vader_scores = self.sentiment_analyzer.polarity_scores(sentence_text)
                
                # TextBlob sentiment
                textblob_polarity = sentence.sentiment.polarity
                textblob_subjectivity = sentence.sentiment.subjectivity
                
                # Combine scores
                combined_sentiment = {
                    "sentence_index": i,
                    "text": sentence_text,
                    "vader_compound": vader_scores['compound'],
                    "vader_positive": vader_scores['pos'],
                    "vader_negative": vader_scores['neg'],
                    "vader_neutral": vader_scores['neu'],
                    "textblob_polarity": textblob_polarity,
                    "textblob_subjectivity": textblob_subjectivity
                }
                
                sentiment_timeline.append(combined_sentiment)
                
                # Detect emotional peaks
                if (abs(vader_scores['compound']) > self.sentiment_threshold or
                    abs(textblob_polarity) > self.sentiment_threshold):
                    emotional_peaks.append(i)
                
                # Detect engaging content
                if self._is_engaging_content(sentence_text):
                    engaging_moments.append(i)
            
            return {
                "sentiment_timeline": sentiment_timeline,
                "emotional_peaks": emotional_peaks,
                "engaging_moments": engaging_moments,
                "overall_sentiment": np.mean([s['vader_compound'] for s in sentiment_timeline]),
                "sentiment_variance": np.var([s['vader_compound'] for s in sentiment_timeline])
            }
            
        except Exception as e:
            logger.error(f"Error analyzing transcript sentiment: {e}")
            return {
                "sentiment_timeline": [],
                "emotional_peaks": [],
                "engaging_moments": [],
                "overall_sentiment": 0,
                "sentiment_variance": 0
            }
    
    def _is_engaging_content(self, text: str) -> bool:
        """Enhanced engaging content detection"""
        engaging_patterns = [
            # Emotional expressions
            r'\b(amazing|incredible|wow|unbelievable|shocking|surprising)\b',
            r'\b(funny|hilarious|crazy|insane|epic|awesome|fantastic)\b',
            r'\b(love|hate|excited|thrilled|devastated|furious)\b',
            
            # Action words
            r'\b(watch|look|see|check|discover|reveal|expose)\b',
            r'\b(secret|trick|hack|tip|method|technique)\b',
            
            # Question words (engagement)
            r'\b(how|why|what|when|where|which)\b',
            r'\?',
            
            # Superlatives
            r'\b(best|worst|most|least|biggest|smallest|fastest|slowest)\b',
            
            # Numbers and statistics
            r'\b\d+%\b',
            r'\b(million|billion|thousand)\b',
            
            # Call to action
            r'\b(subscribe|like|comment|share|follow)\b'
        ]
        
        text_lower = text.lower()
        for pattern in engaging_patterns:
            if len(re.findall(pattern, text_lower)) > 0:
                return True
        
        return False
    
    def _analyze_video_features_direct(self, video_path: str, progress_callback=None) -> Dict[str, Any]:
        """Analyze video features directly for smaller videos"""
        try:
            cap = cv2.VideoCapture(video_path)
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Analyze frames for motion, brightness, and color
            motion_scores = []
            brightness_scores = []
            color_variance_scores = []
            
            prev_frame = None
            # Optimize sampling rate: sample every 2 seconds for better performance
            sample_rate = max(1, int(fps * 2))  # Sample every 2 seconds instead of 0.5
            total_samples = frame_count // sample_rate
            processed_samples = 0
            
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % sample_rate == 0:
                    # Convert to grayscale for motion analysis
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # Calculate motion if we have a previous frame
                    if prev_frame is not None:
                        diff = cv2.absdiff(prev_frame, gray)
                        motion_score = np.mean(diff)
                        motion_scores.append(motion_score)
                    
                    # Calculate brightness
                    brightness = np.mean(gray)
                    brightness_scores.append(brightness)
                    
                    # Calculate color variance
                    color_variance = np.var(frame)
                    color_variance_scores.append(color_variance)
                    
                    prev_frame = gray
                    processed_samples += 1
                    
                    # Report progress if callback provided
                    if progress_callback and total_samples > 0:
                        progress = (processed_samples / total_samples) * 100
                        progress_callback(f"Analyzing video features: {progress:.1f}%")
                
                frame_idx += 1
            
            cap.release()
            
            return self._compile_video_features(motion_scores, brightness_scores, color_variance_scores, duration)
            
        except Exception as e:
            logger.error(f"Error in direct video analysis: {e}")
            return {"motion_scores": [], "brightness_scores": [], "color_variance_scores": [], "avg_motion": 0, "avg_brightness": 0, "avg_color_variance": 0, "duration": 0}
    
    def _compile_video_features(self, motion_scores: List[float], brightness_scores: List[float], color_variance_scores: List[float], duration: float) -> Dict[str, Any]:
        """Compile video features from analysis results"""
        try:
            # Calculate average scores
            avg_motion = np.mean(motion_scores) if motion_scores else 0
            avg_brightness = np.mean(brightness_scores) if brightness_scores else 0
            avg_color_variance = np.mean(color_variance_scores) if color_variance_scores else 0
            
            return {
                "duration": duration,
                "motion_score": float(avg_motion),
                "brightness_score": float(avg_brightness),
                "color_variance_score": float(avg_color_variance),
                "motion_scores": motion_scores,
                "brightness_scores": brightness_scores,
                "color_variance_scores": color_variance_scores
            }
            
        except Exception as e:
            logger.error(f"Error compiling video features: {e}")
            return {"motion_scores": [], "brightness_scores": [], "color_variance_scores": [], "avg_motion": 0, "avg_brightness": 0, "avg_color_variance": 0, "duration": 0}
    
    def find_best_segments(self, transcript: str, video_features: Dict[str, Any], 
                           duration: float, num_clips: int = 3, video_path: str = None, 
                           audio_path: str = None) -> List[Dict[str, Any]]:
        """Find the best segments for viral clips using advanced multi-modal analysis"""
        try:
            # Perform comprehensive analysis
            analysis_results = self._perform_comprehensive_analysis(
                transcript, video_features, video_path, audio_path, duration
            )
            
            # Generate candidate segments
            candidate_segments = self._generate_candidate_segments(
                analysis_results, duration, num_clips * 2  # Generate more candidates
            )
            
            # Score and rank segments
            scored_segments = self._score_viral_segments(candidate_segments, analysis_results)
            
            # Select best segments with diversity
            best_segments = self._select_diverse_segments(scored_segments, num_clips)
            
            return best_segments
            
        except Exception as e:
            logger.error(f"Error finding best segments: {e}")
            return self._fallback_segment_detection(transcript, duration, num_clips)
    
    def _perform_comprehensive_analysis(self, transcript: str, video_features: Dict[str, Any],
                                      video_path: str, audio_path: str, duration: float) -> Dict[str, Any]:
        """Perform comprehensive multi-modal analysis"""
        analysis = {
            "transcript_analysis": {},
            "audio_analysis": {},
            "visual_analysis": video_features,
            "duration": duration
        }
        
        # Transcript sentiment analysis
        if transcript:
            analysis["transcript_analysis"] = self.analyze_transcript_sentiment(transcript)
        
        # Audio analysis
        if audio_path and os.path.exists(audio_path):
            analysis["audio_analysis"] = self.analyze_audio_features(audio_path)
        
        # Additional visual analysis if video path provided
        if video_path and os.path.exists(video_path):
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    # Scene change detection
                    scene_changes = self.detect_scene_changes(video_path)
                    analysis["visual_analysis"]["scene_changes"] = scene_changes
                    
                    # Face detection analysis
                    face_analysis = self.detect_faces_and_emotions(video_path)
                    analysis["visual_analysis"]["face_analysis"] = face_analysis
                    
                    # Motion analysis
                    motion_analysis = self.analyze_motion_intensity(video_path)
                    analysis["visual_analysis"]["motion_analysis"] = motion_analysis
                    
                cap.release()
            except Exception as e:
                logger.error(f"Error in additional visual analysis: {e}")
        
        return analysis
    
    def _generate_candidate_segments(self, analysis: Dict[str, Any], duration: float, 
                                   num_candidates: int) -> List[Dict[str, Any]]:
        """Generate candidate segments based on analysis results"""
        candidates = []
        
        # Base segment duration (adjust for short videos)
        min_duration = min(15, max(3, duration * 0.3))  # At least 3 seconds or 30% of video
        max_duration = min(60, duration)  # Don't exceed video duration
        
        # Generate segments based on different criteria
        
        # 1. Emotional peaks from transcript
        if "emotional_peaks" in analysis.get("transcript_analysis", {}):
            for peak_idx in analysis["transcript_analysis"]["emotional_peaks"]:
                # Estimate time based on sentence index (rough approximation)
                estimated_time = (peak_idx / len(analysis["transcript_analysis"]["sentiment_timeline"])) * duration
                
                for seg_duration in [15, 30, 45, 60]:
                    start_time = max(0, estimated_time - seg_duration/2)
                    end_time = min(duration, start_time + seg_duration)
                    
                    if end_time - start_time >= min_duration:
                        candidates.append({
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": end_time - start_time,
                            "source": "emotional_peak",
                            "peak_index": peak_idx
                        })
        
        # 2. Audio volume spikes
        if "volume_spikes" in analysis.get("audio_analysis", {}):
            for spike_time in analysis["audio_analysis"]["volume_spikes"]:
                for seg_duration in [15, 30, 45]:
                    start_time = max(0, spike_time - seg_duration/2)
                    end_time = min(duration, start_time + seg_duration)
                    
                    if end_time - start_time >= min_duration:
                        candidates.append({
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": end_time - start_time,
                            "source": "volume_spike",
                            "spike_time": spike_time
                        })
        
        # 3. Scene changes
        if "scene_changes" in analysis.get("visual_analysis", {}):
            for change_time in analysis["visual_analysis"]["scene_changes"]:
                for seg_duration in [20, 35, 50]:
                    start_time = max(0, change_time - 5)  # Start slightly before scene change
                    end_time = min(duration, start_time + seg_duration)
                    
                    if end_time - start_time >= min_duration:
                        candidates.append({
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": end_time - start_time,
                            "source": "scene_change",
                            "change_time": change_time
                        })
        
        # 4. Motion peaks
        if "motion_peaks" in analysis.get("visual_analysis", {}).get("motion_analysis", {}):
            for peak_time in analysis["visual_analysis"]["motion_analysis"]["motion_peaks"]:
                for seg_duration in [20, 40]:
                    start_time = max(0, peak_time - seg_duration/3)
                    end_time = min(duration, start_time + seg_duration)
                    
                    if end_time - start_time >= min_duration:
                        candidates.append({
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": end_time - start_time,
                            "source": "motion_peak",
                            "peak_time": peak_time
                        })
        
        # 5. Laughter/applause indicators
        audio_analysis = analysis.get("audio_analysis", {})
        spectral_features = audio_analysis.get("spectral_features", {})
        
        for indicator_type in ["laughter_indicators", "applause_indicators"]:
            if indicator_type in spectral_features:
                for indicator_time in spectral_features[indicator_type]:
                    for seg_duration in [15, 30]:
                        start_time = max(0, indicator_time - 5)
                        end_time = min(duration, start_time + seg_duration)
                        
                        if end_time - start_time >= min_duration:
                            candidates.append({
                                "start_time": start_time,
                                "end_time": end_time,
                                "duration": end_time - start_time,
                                "source": indicator_type,
                                "indicator_time": indicator_time
                            })
        
        # 6. Regular intervals as fallback
        if len(candidates) < num_candidates:
            # For short videos, create a single segment covering most of the video
            if duration <= min_duration:
                candidates.append({
                    "start_time": 0,
                    "end_time": duration,
                    "duration": duration,
                    "source": "full_video",
                    "interval_index": 0
                })
            else:
                interval = duration / (num_candidates - len(candidates) + 1)
                for i in range(num_candidates - len(candidates)):
                    start_time = i * interval
                    segment_duration = min(max_duration, duration - start_time)
                    end_time = min(duration, start_time + segment_duration)
                    
                    if end_time - start_time >= min_duration:
                        candidates.append({
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": end_time - start_time,
                            "source": "regular_interval",
                            "interval_index": i
                        })
        
        return candidates
    
    def _score_viral_segments(self, candidates: List[Dict[str, Any]], 
                            analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Score segments based on viral potential"""
        scored_segments = []
        
        for candidate in candidates:
            score = self._calculate_viral_score(candidate, analysis)
            candidate["viral_score"] = score
            candidate["score_breakdown"] = score["breakdown"]
            candidate["total_score"] = score["total"]
            scored_segments.append(candidate)
        
        # Sort by total score
        scored_segments.sort(key=lambda x: x["total_score"], reverse=True)
        
        return scored_segments
    
    def _calculate_viral_score(self, segment: Dict[str, Any], 
                             analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive viral score for a segment"""
        start_time = segment["start_time"]
        end_time = segment["end_time"]
        duration = end_time - start_time
        
        scores = {
            "emotional_intensity": 0,
            "audio_engagement": 0,
            "visual_interest": 0,
            "content_quality": 0,
            "source_bonus": 0
        }
        
        # 1. Emotional intensity from transcript
        transcript_analysis = analysis.get("transcript_analysis", {})
        if "sentiment_timeline" in transcript_analysis:
            # Find sentences within this time segment (rough approximation)
            total_sentences = len(transcript_analysis["sentiment_timeline"])
            video_duration = analysis["duration"]
            
            start_sentence_idx = int((start_time / video_duration) * total_sentences)
            end_sentence_idx = int((end_time / video_duration) * total_sentences)
            
            segment_sentiments = transcript_analysis["sentiment_timeline"][start_sentence_idx:end_sentence_idx]
            
            if segment_sentiments:
                avg_intensity = np.mean([abs(s["vader_compound"]) for s in segment_sentiments])
                scores["emotional_intensity"] = min(1.0, avg_intensity * 2)  # Scale to 0-1
        
        # 2. Audio engagement
        audio_analysis = analysis.get("audio_analysis", {})
        if "volume_spikes" in audio_analysis:
            spikes_in_segment = [s for s in audio_analysis["volume_spikes"] 
                               if start_time <= s <= end_time]
            scores["audio_engagement"] += min(1.0, len(spikes_in_segment) / 3)  # Max 3 spikes = 1.0
        
        if "spectral_features" in audio_analysis:
            spectral = audio_analysis["spectral_features"]
            for feature in ["laughter_indicators", "applause_indicators"]:
                if feature in spectral:
                    indicators_in_segment = [i for i in spectral[feature] 
                                           if start_time <= i <= end_time]
                    scores["audio_engagement"] += min(0.5, len(indicators_in_segment) / 2)
        
        scores["audio_engagement"] = min(1.0, scores["audio_engagement"])
        
        # 3. Visual interest
        visual_analysis = analysis.get("visual_analysis", {})
        
        # Scene changes
        if "scene_changes" in visual_analysis:
            changes_in_segment = [c for c in visual_analysis["scene_changes"] 
                                if start_time <= c <= end_time]
            scores["visual_interest"] += min(0.4, len(changes_in_segment) / 2)
        
        # Motion analysis
        if "motion_analysis" in visual_analysis and "motion_peaks" in visual_analysis["motion_analysis"]:
            motion_peaks = [p for p in visual_analysis["motion_analysis"]["motion_peaks"] 
                          if start_time <= p <= end_time]
            scores["visual_interest"] += min(0.3, len(motion_peaks) / 3)
        
        # Face detection
        if "face_analysis" in visual_analysis and "face_timeline" in visual_analysis["face_analysis"]:
            face_timeline = visual_analysis["face_analysis"]["face_timeline"]
            faces_in_segment = [f for f in face_timeline 
                              if start_time <= f["timestamp"] <= end_time]
            if faces_in_segment:
                avg_faces = np.mean([f["face_count"] for f in faces_in_segment])
                scores["visual_interest"] += min(0.3, avg_faces / 5)  # Max 5 faces = 0.3
        
        scores["visual_interest"] = min(1.0, scores["visual_interest"])
        
        # 4. Content quality (duration and source)
        # Optimal duration bonus (20-40 seconds gets highest score)
        if 20 <= duration <= 40:
            scores["content_quality"] = 1.0
        elif 15 <= duration < 20 or 40 < duration <= 60:
            scores["content_quality"] = 0.7
        else:
            scores["content_quality"] = 0.3
        
        # 5. Source bonus
        source_bonuses = {
            "emotional_peak": 0.2,
            "volume_spike": 0.15,
            "laughter_indicators": 0.25,
            "applause_indicators": 0.2,
            "scene_change": 0.1,
            "motion_peak": 0.1,
            "regular_interval": 0.0
        }
        scores["source_bonus"] = source_bonuses.get(segment["source"], 0.0)
        
        # Calculate weighted total score
        weights = {
            "emotional_intensity": 0.3,
            "audio_engagement": 0.25,
            "visual_interest": 0.25,
            "content_quality": 0.15,
            "source_bonus": 0.05
        }
        
        total_score = sum(scores[key] * weights[key] for key in scores.keys())
        
        return {
            "breakdown": scores,
            "weights": weights,
            "total": total_score
        }
    
    def _select_diverse_segments(self, scored_segments: List[Dict[str, Any]], 
                               num_clips: int) -> List[Dict[str, Any]]:
        """Select diverse segments to avoid overlap and ensure variety"""
        selected = []
        min_gap = 10  # Minimum 10 seconds between segments
        
        for segment in scored_segments:
            if len(selected) >= num_clips:
                break
            
            # Check for overlap with already selected segments
            overlap = False
            for selected_segment in selected:
                if (segment["start_time"] < selected_segment["end_time"] + min_gap and
                    segment["end_time"] > selected_segment["start_time"] - min_gap):
                    overlap = True
                    break
            
            if not overlap:
                selected.append(segment)
        
        # If we don't have enough segments, fill with best remaining
        if len(selected) < num_clips:
            for segment in scored_segments:
                if len(selected) >= num_clips:
                    break
                if segment not in selected:
                    selected.append(segment)
        
        return selected[:num_clips]
    
    def _fallback_segment_detection(self, transcript: str, duration: float, 
                                  num_clips: int) -> List[Dict[str, Any]]:
        """Fallback method using simple keyword-based detection"""
        try:
            words = transcript.split()
            word_density = len(words) / duration if duration > 0 else 0
            
            engaging_words = [
                'amazing', 'incredible', 'wow', 'unbelievable', 'shocking', 'surprising',
                'funny', 'hilarious', 'crazy', 'insane', 'epic', 'awesome', 'fantastic',
                'secret', 'trick', 'hack', 'tip', 'method', 'technique',
                'watch', 'look', 'see', 'check', 'discover', 'reveal', 'expose'
            ]
            
            engagement_score = sum(1 for word in words if word.lower() in engaging_words)
            engagement_score = engagement_score / len(words) if words else 0
            
            segment_duration = min(60, duration / num_clips)
            segments = []
            
            for i in range(num_clips):
                start_time = i * segment_duration
                end_time = min(start_time + segment_duration, duration)
                
                if start_time < duration:
                    segments.append({
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': end_time - start_time,
                        'engagement_score': engagement_score,
                        'word_density': word_density,
                        'viral_score': {'total': engagement_score * 0.7 + word_density * 0.3},
                        'total_score': engagement_score * 0.7 + word_density * 0.3,
                        'source': 'fallback'
                    })
            
            segments.sort(key=lambda x: x['total_score'], reverse=True)
            return segments[:num_clips]
            
        except Exception as e:
            logger.error(f"Error in fallback segment detection: {e}")
            return []
    
    def extract_clip(self, video_path: str, start_time: int, duration: int, output_path: str) -> bool:
        """Extract a clip from the video using MoviePy"""
        try:
            return self._extract_clip_moviepy(video_path, start_time, duration, output_path)
        except Exception as e:
            logger.error(f"Error extracting clip: {str(e)}")
            return False
    
    def _extract_clip_moviepy(self, video_path: str, start_time: int, duration: int, output_path: str) -> bool:
        """Fallback method using MoviePy"""
        try:
            video = VideoFileClip(video_path)
            clip = video.subclip(start_time, start_time + duration)
            clip.write_videofile(output_path, verbose=False, logger=None)
            video.close()
            clip.close()
            return True
        except Exception as e:
            logger.error(f"MoviePy extraction error: {str(e)}")
            return False
    
    def process_video(self, video_path: str, output_dir: str, progress_callback=None) -> Dict[str, Any]:
        """Complete video processing pipeline with chunked processing for large files"""
        try:
            logger.info(f"Starting video processing for: {video_path}")
            
            # Check file size for chunked processing
            file_size = os.path.getsize(video_path)
            use_chunked_processing = file_size > 100 * 1024 * 1024  # 100MB threshold
            
            if progress_callback:
                progress_callback(5, "Initializing video processing")
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            if use_chunked_processing:
                logger.info(f"Using chunked processing for large file ({file_size / (1024*1024):.1f}MB)")
                return self._process_video_chunked(video_path, output_dir, progress_callback)
            
            # Standard processing for smaller files
            if progress_callback:
                progress_callback(10, "Extracting audio")
            
            # Extract audio and transcribe
            logger.info("Extracting audio...")
            audio_path = self.extract_audio(video_path)
            
            if progress_callback:
                progress_callback(30, "Transcribing audio")
            
            logger.info("Transcribing audio...")
            transcript = self.transcribe_audio(audio_path)
            
            # Clean up audio file
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            if progress_callback:
                progress_callback(60, "Analyzing video features")
            
            # Analyze video features
            logger.info("Analyzing video features...")
            video_features = self.analyze_video_features(video_path)
            
            if progress_callback:
                progress_callback(80, "Finding best segments")
            
            # Find best segments
            logger.info("Finding best segments...")
            duration = video_features.get('duration', 0)
            logger.info(f"Video duration: {duration} seconds")
            segments = self.find_best_segments(transcript, video_features, duration, video_path=video_path)
            logger.info(f"Generated {len(segments)} segments")
            
            if progress_callback:
                progress_callback(90, "Extracting best clip")
            
            # Extract the best clip
            if segments:
                best_segment = segments[0]
                logger.info(f"Best segment: start={best_segment['start_time']}, duration={best_segment['duration']}")
                clip_filename = f"clip_{best_segment['start_time']}_{best_segment['duration']}.mp4"
                clip_path = os.path.join(output_dir, clip_filename)
                
                logger.info(f"Extracting clip: {clip_filename}")
                success = self.extract_clip(
                    video_path,
                    best_segment["start_time"],
                    best_segment["duration"],
                    clip_path
                )
                
                if success:
                    if progress_callback:
                        progress_callback(100, "Video processing completed")
                    return {
                        "success": True,
                        "clip_path": clip_path,
                        "transcript": transcript,
                        "video_features": video_features,
                        "segment_info": best_segment,
                        "all_segments": segments,
                        "processing_method": "standard"
                    }
                else:
                    logger.error(f"Failed to extract clip from segment: {best_segment}")
            else:
                logger.error("No segments generated for video processing")
            
            return {
                "success": False,
                "error": "Failed to extract clip",
                "transcript": transcript,
                "video_features": video_features
            }
            
        except Exception as e:
            logger.error(f"Video processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_video_optimized(self, video_path: str, output_dir: str, 
                                    compress_output: bool = True, 
                                    generate_thumbnails: bool = True) -> Dict[str, Any]:
        """Optimized video processing with compression, thumbnails, and caching"""
        try:
            logger.info(f"Starting optimized video processing for: {video_path}")
            
            # Check cache for complete processing result
            cache_key = self._generate_cache_key(video_path, "complete_processing")
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                logger.info("Using cached processing result")
                return cached_result
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Memory management
            memory_manager.cleanup_if_needed()
            
            # Process video with standard pipeline
            result = self.process_video(video_path, output_dir)
            
            if result["success"]:
                clip_path = result["clip_path"]
                
                # Generate thumbnails if requested
                if generate_thumbnails:
                    try:
                        logger.info("Generating thumbnails...")
                        thumbnails = await self.generate_thumbnails_async(clip_path)
                        result["thumbnails"] = thumbnails
                    except Exception as e:
                        logger.warning(f"Thumbnail generation failed: {e}")
                        result["thumbnails"] = []
                
                # Compress video if requested
                if compress_output:
                    try:
                        logger.info("Compressing video...")
                        compressed_path = clip_path.replace(".mp4", "_compressed.mp4")
                        compressed_clip = await self.compress_video_async(clip_path, compressed_path)
                        result["compressed_clip"] = compressed_clip
                        
                        # Get file size comparison
                        original_size = os.path.getsize(clip_path)
                        compressed_size = os.path.getsize(compressed_clip)
                        compression_ratio = (original_size - compressed_size) / original_size * 100
                        result["compression_info"] = {
                            "original_size": original_size,
                            "compressed_size": compressed_size,
                            "compression_ratio": compression_ratio
                        }
                        
                    except Exception as e:
                        logger.warning(f"Video compression failed: {e}")
                        result["compressed_clip"] = None
                        result["compression_info"] = None
                
                # Add performance metrics
                result["performance_metrics"] = {
                    "memory_usage": memory_manager.get_memory_usage(),
                    "cache_enabled": self.enable_caching,
                    "processing_optimized": True
                }
                
                # Cache the complete result
                self._cache_result(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Optimized video processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "performance_metrics": {
                    "memory_usage": memory_manager.get_memory_usage(),
                    "cache_enabled": self.enable_caching,
                    "processing_optimized": False
                }
            }
        finally:
            # Final cleanup
            memory_manager.cleanup_if_needed()
    
    def _process_video_chunked(self, video_path: str, output_dir: str, progress_callback=None) -> Dict[str, Any]:
        """Process large video files in chunks to avoid memory issues"""
        try:
            logger.info(f"Starting chunked video processing for: {video_path}")
            
            if progress_callback:
                progress_callback(10, "Analyzing video metadata")
            
            # Get video metadata first
            video_features = self.analyze_video_features(video_path)
            duration = video_features.get('duration', 0)
            
            if duration == 0:
                raise ValueError("Could not determine video duration")
            
            # Define chunk size based on file size (process in 5-minute chunks for large files)
            chunk_duration = min(300, duration / 4)  # 5 minutes or 1/4 of video, whichever is smaller
            num_chunks = max(1, int(duration / chunk_duration))
            
            logger.info(f"Processing {duration}s video in {num_chunks} chunks of {chunk_duration}s each")
            
            if progress_callback:
                progress_callback(20, f"Processing video in {num_chunks} chunks")
            
            # Extract audio once for the entire video
            logger.info("Extracting audio for entire video...")
            audio_path = self.extract_audio(video_path)
            
            if progress_callback:
                progress_callback(40, "Transcribing audio")
            
            # Transcribe the entire audio
            logger.info("Transcribing complete audio...")
            transcript = self.transcribe_audio(audio_path)
            
            # Clean up audio file
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            if progress_callback:
                progress_callback(60, "Analyzing video segments")
            
            # Process video in chunks to find best segments
            all_segments = []
            chunk_progress_step = 30 / num_chunks  # Allocate 30% progress for chunk processing
            
            for i in range(num_chunks):
                start_time = i * chunk_duration
                end_time = min((i + 1) * chunk_duration, duration)
                chunk_duration_actual = end_time - start_time
                
                logger.info(f"Processing chunk {i+1}/{num_chunks}: {start_time:.1f}s - {end_time:.1f}s")
                
                try:
                    # Find segments for this chunk
                    chunk_segments = self.find_best_segments(
                        transcript, 
                        video_features, 
                        chunk_duration_actual, 
                        video_path=video_path,
                        start_offset=start_time
                    )
                    
                    # Adjust segment timestamps to global timeline
                    for segment in chunk_segments:
                        segment['start_time'] += start_time
                        segment['chunk_id'] = i + 1
                    
                    all_segments.extend(chunk_segments)
                    
                    # Update progress
                    chunk_progress = 60 + (i + 1) * chunk_progress_step
                    if progress_callback:
                        progress_callback(int(chunk_progress), f"Processed chunk {i+1}/{num_chunks}")
                    
                    # Memory cleanup after each chunk
                    memory_manager.cleanup_if_needed()
                    
                except Exception as chunk_error:
                    logger.warning(f"Error processing chunk {i+1}: {chunk_error}")
                    continue
            
            if progress_callback:
                progress_callback(90, "Selecting best segment and extracting clip")
            
            # Sort all segments by score and select the best one
            if all_segments:
                all_segments.sort(key=lambda x: x.get('total_score', 0), reverse=True)
                best_segment = all_segments[0]
                
                logger.info(f"Best segment from chunked processing: start={best_segment['start_time']}, duration={best_segment['duration']}, chunk={best_segment.get('chunk_id', 'unknown')}")
                
                # Extract the best clip
                clip_filename = f"clip_{int(best_segment['start_time'])}_{int(best_segment['duration'])}.mp4"
                clip_path = os.path.join(output_dir, clip_filename)
                
                logger.info(f"Extracting clip: {clip_filename}")
                success = self.extract_clip(
                    video_path,
                    int(best_segment["start_time"]),
                    int(best_segment["duration"]),
                    clip_path
                )
                
                if success:
                    if progress_callback:
                        progress_callback(100, "Chunked video processing completed")
                    
                    return {
                        "success": True,
                        "clip_path": clip_path,
                        "transcript": transcript,
                        "video_features": video_features,
                        "segment_info": best_segment,
                        "all_segments": all_segments,
                        "processing_method": "chunked",
                        "chunks_processed": num_chunks,
                        "total_segments_found": len(all_segments)
                    }
                else:
                    logger.error(f"Failed to extract clip from best segment: {best_segment}")
            else:
                logger.error("No segments found in any chunk")
            
            return {
                "success": False,
                "error": "Failed to find viable segments in chunked processing",
                "transcript": transcript,
                "video_features": video_features,
                "processing_method": "chunked",
                "chunks_processed": num_chunks
            }
            
        except Exception as e:
            logger.error(f"Chunked video processing failed: {str(e)}")
            return {
                "success": False,
                "error": f"Chunked processing error: {str(e)}",
                "processing_method": "chunked"
            }
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics and performance metrics"""
        return {
            "memory_usage": memory_manager.get_memory_usage(),
            "cache_stats": cache_manager.get_stats(),
            "temp_files_count": len(self._temp_files),
            "active_clips_count": len(self._video_clips),
            "performance_settings": {
                "caching_enabled": self.enable_caching,
                "compression_quality": self.compression_quality,
                "thumbnail_count": self.thumbnail_count,
                "max_memory_usage": self.max_memory_usage,
                "chunk_duration": self.chunk_duration
            }
        }