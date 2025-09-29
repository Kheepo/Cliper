"""
Unified Video Processing Service for Cliper
Consolidates all video processing functionality
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import shutil
import psutil
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class GPUAcceleration(Enum):
    NONE = "none"
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"


@dataclass
class VideoMetadata:
    """Video metadata information."""
    duration: float
    width: int
    height: int
    fps: float
    bitrate: int
    codec: str
    format: str
    size: int
    has_audio: bool
    audio_codec: Optional[str] = None
    audio_bitrate: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'duration': self.duration,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'bitrate': self.bitrate,
            'codec': self.codec,
            'format': self.format,
            'size': self.size,
            'has_audio': self.has_audio,
            'audio_codec': self.audio_codec,
            'audio_bitrate': self.audio_bitrate
        }


@dataclass
class ProcessingConfig:
    """Video processing configuration."""
    output_format: str = "mp4"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    bitrate: int = 2000  # kbps
    audio_bitrate: int = 128  # kbps
    fps: int = 30
    width: Optional[int] = None
    height: Optional[int] = None
    preset: str = "medium"
    crf: int = 23
    gpu_acceleration: bool = False


@dataclass
class ProcessingResult:
    """Result of video processing operation."""
    success: bool
    output_path: Optional[str] = None
    duration: Optional[float] = None
    size: Optional[int] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None
    metadata: Optional[VideoMetadata] = None


class UnifiedVideoProcessor:
    """Unified video processor with comprehensive functionality."""

    def __init__(self):
        """Initialize the video processor."""
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self.gpu_acceleration = GPUAcceleration.NONE
        self.max_concurrent_processes = 4
        self.processing_timeout = 600  # 10 minutes
        self._ffmpeg_checked = False
        
        logger.info("Video processor initialized (FFmpeg will be checked on first use)")

    def _ensure_ffmpeg_available(self):
        """Ensure FFmpeg is available and paths are set."""
        if self._ffmpeg_checked:
            return
        
        try:
            self.ffmpeg_path = self._get_ffmpeg_path()
            self.ffprobe_path = self._get_ffprobe_path()
            self.gpu_acceleration = self._detect_gpu_acceleration()
            self._ffmpeg_checked = True
            logger.info(f"FFmpeg initialized with GPU: {self.gpu_acceleration.value}")
        except Exception as e:
            logger.error(f"FFmpeg initialization failed: {e}")
            raise Exception(f"FFmpeg is required for video processing but not available: {e}")

    def _get_ffmpeg_path(self) -> str:
        """Get FFmpeg executable path."""
        # Check for FFmpeg in PATH
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return 'ffmpeg'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check common installation paths
        common_paths = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',
            'C:\\ffmpeg\\bin\\ffmpeg.exe'
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        raise Exception("FFmpeg not found. Please install FFmpeg and ensure it's in your PATH.")

    def _get_ffprobe_path(self) -> str:
        """Get FFprobe executable path."""
        # Similar to FFmpeg path detection
        try:
            result = subprocess.run(
                ['ffprobe', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return 'ffprobe'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check common installation paths
        common_paths = [
            '/usr/bin/ffprobe',
            '/usr/local/bin/ffprobe',
            '/opt/homebrew/bin/ffprobe',
            'C:\\ffmpeg\\bin\\ffprobe.exe'
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        raise Exception("FFprobe not found. Please install FFmpeg and ensure it's in your PATH.")

    def _detect_gpu_acceleration(self) -> GPUAcceleration:
        """Detect available GPU acceleration."""
        try:
            # Check for NVIDIA GPU
            result = subprocess.run(
                [self.ffmpeg_path, '-hide_banner', '-encoders'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if 'h264_nvenc' in result.stdout:
                return GPUAcceleration.NVIDIA
            elif 'h264_amf' in result.stdout:
                return GPUAcceleration.AMD
            elif 'h264_qsv' in result.stdout:
                return GPUAcceleration.INTEL
            
            return GPUAcceleration.NONE
            
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
            return GPUAcceleration.NONE

    async def get_video_metadata(self, video_path: str) -> VideoMetadata:
        """Get video metadata using FFprobe."""
        self._ensure_ffmpeg_available()
        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"FFprobe failed: {stderr.decode()}")
            
            import json
            data = json.loads(stdout.decode())
            
            # Find video stream
            video_stream = None
            audio_stream = None
            
            for stream in data['streams']:
                if stream['codec_type'] == 'video' and video_stream is None:
                    video_stream = stream
                elif stream['codec_type'] == 'audio' and audio_stream is None:
                    audio_stream = stream
            
            if not video_stream:
                raise Exception("No video stream found")
            
            # Extract metadata
            duration = float(data['format'].get('duration', 0))
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            
            # Parse frame rate
            fps_str = video_stream.get('r_frame_rate', '30/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den) if float(den) != 0 else 30.0
            else:
                fps = float(fps_str)
            
            bitrate = int(data['format'].get('bit_rate', 0)) // 1000  # Convert to kbps
            codec = video_stream.get('codec_name', 'unknown')
            format_name = data['format'].get('format_name', 'unknown')
            size = int(data['format'].get('size', 0))
            
            has_audio = audio_stream is not None
            audio_codec = audio_stream.get('codec_name') if audio_stream else None
            audio_bitrate = None
            if audio_stream and 'bit_rate' in audio_stream:
                audio_bitrate = int(audio_stream['bit_rate']) // 1000  # Convert to kbps
            
            return VideoMetadata(
                duration=duration,
                width=width,
                height=height,
                fps=fps,
                bitrate=bitrate,
                codec=codec,
                format=format_name,
                size=size,
                has_audio=has_audio,
                audio_codec=audio_codec,
                audio_bitrate=audio_bitrate
            )
            
        except Exception as e:
            logger.error(f"Failed to get video metadata: {e}")
            raise

    async def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> str:
        """Extract audio from video."""
        self._ensure_ffmpeg_available()
        if output_path is None:
            output_path = tempfile.mktemp(suffix='.wav')
        
        try:
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # PCM 16-bit
                '-ar', '16000',  # 16kHz sample rate
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
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to extract audio: {e}")
            raise

    async def create_clip(
        self,
        video_path: str,
        start_time: float,
        duration: float,
        output_path: str,
        config: ProcessingConfig,
        platform: str = "general"
    ) -> ProcessingResult:
        """Create a video clip with platform optimization."""
        self._ensure_ffmpeg_available()
        
        start_processing = time.time()
        
        try:
            # Get platform-specific configuration
            platform_config = self._get_platform_config(platform, config)
            
            # Build FFmpeg command
            cmd = self._build_clip_command(
                video_path, start_time, duration, output_path, platform_config
            )
            
            logger.info(f"Creating clip: {start_time}s-{start_time + duration}s -> {output_path}")
            
            # Execute FFmpeg command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"FFmpeg failed: {error_msg}")
                return ProcessingResult(
                    success=False,
                    error=f"Video processing failed: {error_msg}"
                )
            
            # Verify output file
            if not os.path.exists(output_path):
                return ProcessingResult(
                    success=False,
                    error="Output file was not created"
                )
            
            # Get output metadata
            output_metadata = await self.get_video_metadata(output_path)
            
            processing_time = time.time() - start_processing
            
            logger.info(f"Clip created successfully in {processing_time:.2f}s")
            
            return ProcessingResult(
                success=True,
                output_path=output_path,
                duration=output_metadata.duration,
                size=output_metadata.size,
                processing_time=processing_time,
                metadata=output_metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to create clip: {e}")
            return ProcessingResult(
                success=False,
                error=str(e),
                processing_time=time.time() - start_processing
            )

    def _get_platform_config(self, platform: str, base_config: ProcessingConfig) -> Dict[str, Any]:
        """Get platform-specific configuration."""
        platform_specs = {
            'tiktok': {
                'width': 1080,
                'height': 1920,
                'aspect_ratio': '9:16',
                'fps': 30,
                'bitrate': 2500,
                'preset': 'medium',
                'filters': ['scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2']
            },
            'youtube': {
                'width': 1920,
                'height': 1080,
                'aspect_ratio': '16:9',
                'fps': 30,
                'bitrate': 5000,
                'preset': 'medium',
                'filters': ['scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2']
            },
            'instagram': {
                'width': 1080,
                'height': 1920,
                'aspect_ratio': '9:16',
                'fps': 30,
                'bitrate': 3000,
                'preset': 'medium',
                'filters': ['scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2']
            },
            'twitter': {
                'width': 1280,
                'height': 720,
                'aspect_ratio': '16:9',
                'fps': 30,
                'bitrate': 2000,
                'preset': 'fast',
                'filters': ['scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2']
            }
        }
        
        spec = platform_specs.get(platform, {})
        
        return {
            'width': spec.get('width', base_config.width),
            'height': spec.get('height', base_config.height),
            'fps': spec.get('fps', base_config.fps),
            'bitrate': spec.get('bitrate', base_config.bitrate),
            'preset': spec.get('preset', base_config.preset),
            'filters': spec.get('filters', []),
            'video_codec': base_config.video_codec,
            'audio_codec': base_config.audio_codec,
            'audio_bitrate': base_config.audio_bitrate,
            'crf': base_config.crf
        }

    def _build_clip_command(
        self,
        video_path: str,
        start_time: float,
        duration: float,
        output_path: str,
        config: Dict[str, Any]
    ) -> List[str]:
        """Build FFmpeg command for clip creation."""
        
        cmd = [
            self.ffmpeg_path,
            '-y',  # Overwrite output
            '-hide_banner',
            '-loglevel', 'error'
        ]
        
        # GPU acceleration
        if self.gpu_acceleration == GPUAcceleration.NVIDIA and config.get('gpu_acceleration', True):
            cmd.extend(['-hwaccel', 'cuda'])
        
        # Input seeking for better performance
        cmd.extend(['-ss', str(start_time)])
        cmd.extend(['-i', video_path])
        cmd.extend(['-t', str(duration)])
        
        # Video encoding
        if self.gpu_acceleration == GPUAcceleration.NVIDIA and config.get('gpu_acceleration', True):
            cmd.extend([
                '-c:v', 'h264_nvenc',
                '-preset', config['preset'],
                '-rc', 'vbr',
                '-cq', str(config['crf']),
                '-b:v', f"{config['bitrate']}k",
                '-maxrate', f"{int(config['bitrate'] * 1.5)}k",
                '-bufsize', f"{int(config['bitrate'] * 2)}k"
            ])
        else:
            cmd.extend([
                '-c:v', config['video_codec'],
                '-preset', config['preset'],
                '-crf', str(config['crf']),
                '-b:v', f"{config['bitrate']}k"
            ])
        
        # Audio encoding
        cmd.extend([
            '-c:a', config['audio_codec'],
            '-b:a', f"{config['audio_bitrate']}k",
            '-ar', '44100'
        ])
        
        # Video filters
        if config.get('filters'):
            filter_str = ','.join(config['filters'])
            cmd.extend(['-vf', filter_str])
        
        # Frame rate
        if config.get('fps'):
            cmd.extend(['-r', str(config['fps'])])
        
        # Output optimizations
        cmd.extend([
            '-movflags', '+faststart',  # Web optimization
            '-fflags', '+genpts',  # Generate presentation timestamps
            output_path
        ])
        
        return cmd

    async def create_thumbnail(
        self,
        video_path: str,
        timestamp: float,
        output_path: str,
        width: int = 320,
        height: int = 240
    ) -> ProcessingResult:
        """Create a thumbnail from video at specified timestamp."""
        self._ensure_ffmpeg_available()
        
        start_processing = time.time()
        
        try:
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-ss', str(timestamp),
                '-i', video_path,
                '-vframes', '1',
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                '-f', 'image2',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"Thumbnail creation failed: {error_msg}")
                return ProcessingResult(
                    success=False,
                    error=f"Thumbnail creation failed: {error_msg}"
                )
            
            if not os.path.exists(output_path):
                return ProcessingResult(
                    success=False,
                    error="Thumbnail file was not created"
                )
            
            processing_time = time.time() - start_processing
            
            return ProcessingResult(
                success=True,
                output_path=output_path,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Failed to create thumbnail: {e}")
            return ProcessingResult(
                success=False,
                error=str(e),
                processing_time=time.time() - start_processing
            )

    async def validate_video_file(self, video_path: str) -> Tuple[bool, str]:
        """Validate video file format and accessibility."""
        self._ensure_ffmpeg_available()
        try:
            if not os.path.exists(video_path):
                return False, "File does not exist"
            
            # Check file size
            file_size = os.path.getsize(video_path)
            if file_size == 0:
                return False, "File is empty"
            
            # Check if it's a valid video file using FFprobe
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                video_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return False, f"Invalid video file: {stderr.decode()}"
            
            return True, "Valid video file"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def get_system_resources(self) -> Dict[str, Any]:
        """Get current system resource usage."""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used
                },
                'disk': {
                    'total': disk.total,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100,
                    'used': disk.used
                },
                'cpu': {
                    'percent': cpu_percent,
                    'count': psutil.cpu_count()
                },
                'gpu_acceleration': self.gpu_acceleration.value
            }
            
        except Exception as e:
            logger.error(f"Failed to get system resources: {e}")
            return {
                'error': str(e),
                'gpu_acceleration': self.gpu_acceleration.value
            }

    async def health_check(self) -> Dict[str, Any]:
        """Check video processor health."""
        try:
            self._ensure_ffmpeg_available()
            # Test FFmpeg
            ffmpeg_result = subprocess.run(
                [self.ffmpeg_path, '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Test FFprobe
            ffprobe_result = subprocess.run(
                [self.ffprobe_path, '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return {
                'status': 'healthy',
                'ffmpeg_available': ffmpeg_result.returncode == 0,
                'ffprobe_available': ffprobe_result.returncode == 0,
                'gpu_acceleration': self.gpu_acceleration.value,
                'system_resources': self.get_system_resources()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'gpu_acceleration': self.gpu_acceleration.value
            }


# Global video processor instance
unified_video_processor = UnifiedVideoProcessor()

