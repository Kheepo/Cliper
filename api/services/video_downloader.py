from typing import Dict, Any, Optional
import os
import uuid
import asyncio
import subprocess
from datetime import datetime
from urllib.parse import urlparse
from .supabase_storage_service import supabase_storage_service

class VideoDownloader:
    """Service for downloading videos from various platforms"""
    
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
    
    async def download_video(self, url: str, platform: str) -> Dict[str, Any]:
        """Download video from URL and return file information"""
        try:
            # Generate unique filename
            unique_id = str(uuid.uuid4())
            output_template = os.path.join(self.download_dir, f"{unique_id}.%(ext)s")
            
            # Prepare download command based on platform
            cmd = self._get_download_command(url, output_template, platform)
            
            # Execute download
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Download failed: {stderr.decode()}")
            
            # Find the downloaded file
            downloaded_file = self._find_downloaded_file(unique_id)
            
            if not downloaded_file:
                raise Exception("Downloaded file not found")
            
            # Get file information before upload
            file_info = await self._get_file_info(downloaded_file, url, platform)
            
            # Upload to Supabase Storage
            storage_filename = supabase_storage_service.generate_unique_filename(os.path.basename(downloaded_file))
            storage_path = f"videos/{storage_filename}"
            
            public_url = await supabase_storage_service.upload_file(
                file_path=downloaded_file,
                destination_path=storage_path
            )
            
            # Clean up local file after upload
            self.cleanup_file(downloaded_file)
            
            return {
                'success': True,
                'file_path': storage_path,  # Return storage path instead of local path
                'public_url': public_url,
                'file_info': file_info,
                'download_log': stdout.decode()
            }
            
        except Exception as e:
            # Clean up any local files if they exist
            if 'downloaded_file' in locals() and downloaded_file and os.path.exists(downloaded_file):
                self.cleanup_file(downloaded_file)
            
            return {
                'success': False,
                'error': str(e),
                'file_path': None,
                'file_info': None
            }
    
    def _get_download_command(self, url: str, output_template: str, platform: str) -> list:
        """Get platform-specific download command"""
        # Base command for yt-dlp (supports most platforms)
        cmd = [
            'yt-dlp',
            '--format', 'best[ext=mp4]/best',  # Prefer mp4 format
            '--output', output_template,
            '--no-playlist',  # Download single video only
            '--extract-flat', 'false',
            url
        ]
        
        # Platform-specific optimizations
        if platform in ['youtube.com']:
            cmd.extend(['--format', 'best[height<=1080][ext=mp4]/best[ext=mp4]/best'])
        elif platform in ['tiktok.com']:
            cmd.extend(['--format', 'best[ext=mp4]/best'])
        elif platform in ['instagram.com']:
            cmd.extend(['--format', 'best[ext=mp4]/best'])
        
        return cmd
    
    def _find_downloaded_file(self, unique_id: str) -> Optional[str]:
        """Find the downloaded file by unique ID"""
        for file in os.listdir(self.download_dir):
            if file.startswith(unique_id):
                return os.path.join(self.download_dir, file)
        return None
    
    async def _get_file_info(self, file_path: str, url: str, platform: str) -> Dict[str, Any]:
        """Extract file information"""
        try:
            # Get basic file stats
            stat = os.stat(file_path)
            file_size = stat.st_size
            
            # Get video metadata using ffprobe
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            metadata = {}
            if process.returncode == 0:
                import json
                probe_data = json.loads(stdout.decode())
                
                # Extract video stream info
                video_streams = [s for s in probe_data.get('streams', []) if s.get('codec_type') == 'video']
                if video_streams:
                    video_stream = video_streams[0]
                    metadata.update({
                        'width': video_stream.get('width'),
                        'height': video_stream.get('height'),
                        'duration': float(probe_data.get('format', {}).get('duration', 0)),
                        'bitrate': int(probe_data.get('format', {}).get('bit_rate', 0)),
                        'codec': video_stream.get('codec_name'),
                        'fps': eval(video_stream.get('r_frame_rate', '0/1'))
                    })
            
            return {
                'filename': os.path.basename(file_path),
                'size_bytes': file_size,
                'size_mb': round(file_size / (1024*1024), 2),
                'source_url': url,
                'platform': platform,
                'downloaded_at': datetime.utcnow().isoformat(),
                **metadata
            }
            
        except Exception as e:
            return {
                'filename': os.path.basename(file_path),
                'size_bytes': os.path.getsize(file_path),
                'size_mb': round(os.path.getsize(file_path) / (1024*1024), 2),
                'source_url': url,
                'platform': platform,
                'downloaded_at': datetime.utcnow().isoformat(),
                'metadata_error': str(e)
            }
    
    def cleanup_file(self, file_path: str) -> bool:
        """Clean up downloaded file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False

# Global downloader instance
video_downloader = VideoDownloader()