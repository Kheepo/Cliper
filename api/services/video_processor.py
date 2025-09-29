import asyncio
import os
import subprocess
import tempfile
import logging
import json
from typing import Dict, List, Any, Optional, Callable
import whisper
import torch
import gc
import psutil
from datetime import datetime
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Enhanced video processor with Whisper v3, GPU acceleration, and optimized transcription.
    """
    
    def __init__(self):
        """
        Initialize VideoProcessor with GPU detection and model loading.
        """
        self.device = self._detect_device()
        self.whisper_model = None
        self.model_size = 'base'  # Default model size
        self.transcription_priority = 'balanced'  # speed, accuracy, balanced
        
        # Initialize transcription priority methods
        self._transcription_methods = self._initialize_transcription_priority()
        
        logger.info(f"VideoProcessor initialized with device: {self.device}")
    
    def _detect_device(self) -> str:
        """
        Detect the best available device for processing.
        
        Returns:
            Device string ('cuda', 'mps', or 'cpu')
        """
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"CUDA available: {gpu_count} GPU(s), {gpu_memory:.1f}GB memory")
            return 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            logger.info("MPS (Apple Silicon) available")
            return 'mps'
        else:
            logger.info("Using CPU for processing")
            return 'cpu'
    
    def _get_optimal_model_size(self, priority: str, video_duration: float) -> str:
        """
        Determine optimal Whisper model size based on priority and video duration.
        
        Args:
            priority: 'speed', 'accuracy', or 'balanced'
            video_duration: Video duration in seconds
            
        Returns:
            Model size string
        """
        if priority == 'speed':
            return 'tiny' if video_duration > 1800 else 'base'  # 30+ minutes use tiny
        elif priority == 'accuracy':
            if self.device == 'cuda':
                return 'large-v3' if video_duration < 3600 else 'medium'  # 1+ hour use medium
            else:
                return 'medium' if video_duration < 1800 else 'base'
        else:  # balanced
            if video_duration > 3600:  # 1+ hour
                return 'base'
            elif video_duration > 1800:  # 30+ minutes
                return 'small'
            else:
                return 'medium' if self.device == 'cuda' else 'base'
    
    async def _load_whisper_model(self, model_size: str) -> bool:
        """
        Load Whisper model with memory management.
        
        Args:
            model_size: Size of the model to load
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear existing model if different size
            if self.whisper_model is not None and self.model_size != model_size:
                del self.whisper_model
                self.whisper_model = None
                gc.collect()
                if self.device == 'cuda':
                    torch.cuda.empty_cache()
            
            # Load new model if needed
            if self.whisper_model is None or self.model_size != model_size:
                logger.info(f"Loading Whisper model: {model_size} on {self.device}")
                
                # Check available memory
                if self.device == 'cuda':
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory
                    available_memory = gpu_memory - torch.cuda.memory_allocated()
                    logger.info(f"Available GPU memory: {available_memory / 1024**3:.1f}GB")
                
                self.whisper_model = whisper.load_model(
                    model_size, 
                    device=self.device,
                    download_root=os.path.join(os.getcwd(), 'models')
                )
                self.model_size = model_size
                
                logger.info(f"Successfully loaded Whisper model: {model_size}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model {model_size}: {e}")
            return False
    
    async def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Get comprehensive video information using ffprobe.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video information
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"ffprobe failed: {stderr.decode()}")
            
            info = json.loads(stdout.decode())
            
            # Extract relevant information
            video_stream = next(
                (s for s in info['streams'] if s['codec_type'] == 'video'), 
                None
            )
            audio_stream = next(
                (s for s in info['streams'] if s['codec_type'] == 'audio'), 
                None
            )
            
            return {
                'duration': float(info['format'].get('duration', 0)),
                'size': int(info['format'].get('size', 0)),
                'bitrate': int(info['format'].get('bit_rate', 0)),
                'video': {
                    'codec': video_stream.get('codec_name') if video_stream else None,
                    'width': int(video_stream.get('width', 0)) if video_stream else 0,
                    'height': int(video_stream.get('height', 0)) if video_stream else 0,
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0
                },
                'audio': {
                    'codec': audio_stream.get('codec_name') if audio_stream else None,
                    'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream else 0,
                    'channels': int(audio_stream.get('channels', 0)) if audio_stream else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting video info for {video_path}: {e}")
            return {}
    
    async def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        Extract audio from video with optimal settings for transcription.
        
        Args:
            video_path: Path to input video
            output_path: Path for output audio file
            
        Returns:
            Path to extracted audio file
        """
        try:
            if output_path is None:
                output_path = os.path.join(
                    tempfile.gettempdir(),
                    f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                )
            
            # Optimal settings for Whisper
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-ar', '16000',  # 16kHz sample rate (Whisper's native)
                '-ac', '1',  # Mono
                '-y',  # Overwrite output
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Audio extraction failed: {stderr.decode()}")
            
            if not os.path.exists(output_path):
                raise Exception("Audio file was not created")
            
            logger.info(f"Audio extracted to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error extracting audio from {video_path}: {e}")
            raise
    
    async def transcribe_audio(
        self,
        video_path: str,
        priority: str = 'balanced',
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        Transcribe video audio using Whisper v3 with enhanced accuracy.
        
        Args:
            video_path: Path to video file
            priority: 'speed', 'accuracy', or 'balanced'
            language: Language code (auto-detect if None)
            progress_callback: Optional progress callback function
            
        Returns:
            Transcription result with segments and metadata
        """
        start_time = datetime.now()
        audio_path = None
        
        try:
            if progress_callback:
                progress_callback(5)
            
            # Get video info
            video_info = await self.get_video_info(video_path)
            duration = video_info.get('duration', 0)
            
            if duration == 0:
                raise Exception("Could not determine video duration")
            
            # Determine optimal model size
            model_size = self._get_optimal_model_size(priority, duration)
            
            if progress_callback:
                progress_callback(10)
            
            # Load Whisper model
            if not await self._load_whisper_model(model_size):
                raise Exception(f"Failed to load Whisper model: {model_size}")
            
            if progress_callback:
                progress_callback(20)
            
            # Extract audio
            audio_path = await self.extract_audio(video_path)
            
            if progress_callback:
                progress_callback(30)
            
            # Transcription options based on priority
            transcribe_options = {
                'language': language,
                'task': 'transcribe',
                'verbose': False,
                'word_timestamps': True,  # Enable word-level timestamps
                'condition_on_previous_text': True,
                'compression_ratio_threshold': 2.4,
                'logprob_threshold': -1.0,
                'no_speech_threshold': 0.6
            }
            
            if priority == 'accuracy':
                transcribe_options.update({
                    'beam_size': 5,
                    'best_of': 5,
                    'temperature': 0.0,
                    'compression_ratio_threshold': 2.2,
                    'logprob_threshold': -0.8
                })
            elif priority == 'speed':
                transcribe_options.update({
                    'beam_size': 1,
                    'best_of': 1,
                    'temperature': 0.2,
                    'fp16': self.device == 'cuda'
                })
            else:  # balanced
                transcribe_options.update({
                    'beam_size': 3,
                    'best_of': 3,
                    'temperature': 0.1,
                    'fp16': self.device == 'cuda'
                })
            
            logger.info(f"Starting transcription with model {model_size}, priority: {priority}")
            
            # Perform transcription
            result = self.whisper_model.transcribe(
                audio_path,
                **transcribe_options
            )
            
            if progress_callback:
                progress_callback(90)
            
            # Process and enhance results
            processed_result = self._process_transcription_result(
                result, video_info, model_size, priority
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            processed_result['processing_time'] = processing_time
            processed_result['processing_speed'] = duration / processing_time if processing_time > 0 else 0
            
            logger.info(
                f"Transcription completed in {processing_time:.1f}s "
                f"(speed: {processed_result['processing_speed']:.1f}x realtime)"
            )
            
            if progress_callback:
                progress_callback(100)
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Error transcribing {video_path}: {e}")
            raise
        
        finally:
            # Cleanup temporary audio file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception as e:
                    logger.warning(f"Could not remove temporary audio file {audio_path}: {e}")
    
    def _process_transcription_result(
        self, 
        result: Dict[str, Any], 
        video_info: Dict[str, Any],
        model_size: str,
        priority: str
    ) -> Dict[str, Any]:
        """
        Process and enhance transcription results.
        
        Args:
            result: Raw Whisper transcription result
            video_info: Video information
            model_size: Model size used
            priority: Processing priority
            
        Returns:
            Enhanced transcription result
        """
        try:
            # Calculate confidence scores
            segments = result.get('segments', [])
            total_confidence = 0
            word_count = 0
            
            enhanced_segments = []
            for segment in segments:
                # Calculate segment confidence
                words = segment.get('words', [])
                if words:
                    word_confidences = [w.get('probability', 0.5) for w in words if 'probability' in w]
                    segment_confidence = np.mean(word_confidences) if word_confidences else 0.5
                else:
                    # Fallback confidence based on avg_logprob
                    avg_logprob = segment.get('avg_logprob', -1.0)
                    segment_confidence = max(0.0, min(1.0, (avg_logprob + 1.0) / 1.0))
                
                enhanced_segment = {
                    'id': segment.get('id'),
                    'start': segment.get('start'),
                    'end': segment.get('end'),
                    'text': segment.get('text', '').strip(),
                    'confidence': segment_confidence,
                    'words': words,
                    'avg_logprob': segment.get('avg_logprob'),
                    'compression_ratio': segment.get('compression_ratio'),
                    'no_speech_prob': segment.get('no_speech_prob')
                }
                
                enhanced_segments.append(enhanced_segment)
                
                # Update totals for overall confidence
                total_confidence += segment_confidence
                word_count += len(words) if words else len(segment.get('text', '').split())
            
            overall_confidence = total_confidence / len(segments) if segments else 0.0
            
            return {
                'text': result.get('text', '').strip(),
                'segments': enhanced_segments,
                'language': result.get('language'),
                'confidence': overall_confidence,
                'word_count': word_count,
                'duration': video_info.get('duration', 0),
                'model_size': model_size,
                'priority': priority,
                'device': self.device,
                'metadata': {
                    'video_info': video_info,
                    'transcription_timestamp': datetime.now().isoformat(),
                    'whisper_version': whisper.__version__
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing transcription result: {e}")
            return {
                'text': result.get('text', ''),
                'segments': result.get('segments', []),
                'language': result.get('language'),
                'confidence': 0.5,
                'error': str(e)
            }
    
    def cleanup_models(self):
        """
        Clean up loaded models to free memory.
        """
        try:
            if self.whisper_model is not None:
                del self.whisper_model
                self.whisper_model = None
                gc.collect()
                
                if self.device == 'cuda':
                    torch.cuda.empty_cache()
                
                logger.info("Whisper model cleaned up")
                
        except Exception as e:
            logger.error(f"Error cleaning up models: {e}")
    
    def _initialize_transcription_priority(self) -> List[str]:
        """
        Initialize transcription methods in priority order based on availability.
        
        Returns:
            List of available transcription methods in priority order
        """
        methods = []
        
        # Prioritize Whisper for better accuracy and reliability
        methods.append('whisper')
        
        # Add fallback method
        methods.append('fallback')
        
        logger.info(f"Transcription priority order: {methods}")
        return methods
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get current memory usage statistics.
        
        Returns:
            Memory usage information
        """
        try:
            memory_info = {
                'system_memory': psutil.virtual_memory().percent,
                'available_memory_gb': psutil.virtual_memory().available / 1024**3
            }
            
            if self.device == 'cuda' and torch.cuda.is_available():
                memory_info.update({
                    'gpu_memory_allocated_gb': torch.cuda.memory_allocated() / 1024**3,
                    'gpu_memory_reserved_gb': torch.cuda.memory_reserved() / 1024**3,
                    'gpu_memory_total_gb': torch.cuda.get_device_properties(0).total_memory / 1024**3
                })
            
            return memory_info
            
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}