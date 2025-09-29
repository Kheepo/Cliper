"""
Unified Task Processor for Cliper
Integrates AI analysis, video processing, and clip generation
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import json

from .unified_ai_service import unified_ai_service, TranscriptionSegment, ViralityScore, ClipSegment
from .unified_video_processor import unified_video_processor, VideoMetadata, ProcessingConfig, ProcessingResult
from .viral_scoring import ViralScoringService, PlatformEnum
from ..services.supabase_service import supabase_service

logger = logging.getLogger(__name__)


@dataclass
class ProcessingOptions:
    """Processing options for video analysis."""
    target_platforms: List[str] = None
    max_clips: int = 5
    min_virality_score: float = 70.0
    clip_duration_range: tuple = (15, 60)  # min, max seconds
    generate_thumbnails: bool = True
    generate_hashtags: bool = True
    language: Optional[str] = None
    
    def __post_init__(self):
        if self.target_platforms is None:
            self.target_platforms = ['tiktok', 'youtube', 'instagram']


@dataclass
class ProcessingProgress:
    """Processing progress information."""
    job_id: str
    status: str
    progress: int
    current_step: str
    estimated_remaining: float
    start_time: datetime
    last_update: datetime


class UnifiedTaskProcessor:
    """Unified task processor that orchestrates the entire video processing pipeline."""

    def __init__(self):
        """Initialize the unified task processor."""
        self.ai_service = unified_ai_service
        self.video_processor = unified_video_processor
        self.viral_scoring = ViralScoringService()
        self.supabase = supabase_service
        
        # Processing statistics
        self.stats = {
            'total_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'average_processing_time': 0.0
        }

    async def process_video_task(
        self,
        job_id: str,
        video_path: str,
        original_filename: str,
        file_size: int,
        processing_options: Optional[ProcessingOptions] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process a video file through the complete pipeline."""
        
        if processing_options is None:
            processing_options = ProcessingOptions()
        
        start_time = time.time()
        progress = ProcessingProgress(
            job_id=job_id,
            status="starting",
            progress=0,
            current_step="Initializing processing",
            estimated_remaining=300.0,  # 5 minutes default
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        try:
            # Update job status
            await self._update_progress(progress, "Validating video file", 5)
            await self._call_progress_callback(progress, progress_callback)
            
            # Validate video file
            is_valid, validation_message = await self.video_processor.validate_video_file(video_path)
            if not is_valid:
                raise Exception(f"Video validation failed: {validation_message}")
            
            # Get video metadata
            await self._update_progress(progress, "Analyzing video metadata", 10)
            await self._call_progress_callback(progress, progress_callback)
            
            video_metadata = await self.video_processor.get_video_metadata(video_path)
            logger.info(f"Video metadata: {video_metadata.to_dict()}")
            
            # Extract audio for transcription
            await self._update_progress(progress, "Extracting audio", 15)
            await self._call_progress_callback(progress, progress_callback)
            
            audio_path = await self.video_processor.extract_audio(video_path)
            
            try:
                # Transcribe audio
                await self._update_progress(progress, "Transcribing audio", 25)
                await self._call_progress_callback(progress, progress_callback)
                
                transcription_segments = await self.ai_service.transcribe_audio(
                    audio_path, processing_options.language
                )
                logger.info(f"Transcribed {len(transcription_segments)} segments")
                
                # Analyze virality using comprehensive viral scoring
                await self._update_progress(progress, "Analyzing content for virality", 40)
                await self._call_progress_callback(progress, progress_callback)
                
                # Convert platform names to enums
                target_platform_enums = []
                for platform_name in processing_options.target_platforms:
                    try:
                        platform_enum = PlatformEnum(platform_name.lower())
                        target_platform_enums.append(platform_enum)
                    except ValueError:
                        logger.warning(f"Unknown platform: {platform_name}, skipping")
                
                # Prepare transcription data for viral scoring
                transcription_data = {
                    'segments': [seg.to_dict() for seg in transcription_segments]
                }
                
                # Perform comprehensive viral analysis
                viral_analysis = await self.viral_scoring.analyze_viral_potential(
                    transcription=transcription_data,
                    video_metadata=video_metadata.to_dict(),
                    target_platforms=target_platform_enums
                )
                
                logger.info(f"Viral analysis completed with overall score: {viral_analysis.overall_viral_score:.2f}")
                
                # Convert viral analysis to legacy format for compatibility
                virality_scores = []
                for moment in viral_analysis.viral_moments:
                    if moment.viral_score >= processing_options.min_virality_score / 100.0:
                        # Create a ViralityScore object for compatibility
                        virality_score = ViralityScore(
                            start_time=moment.start_time,
                            end_time=moment.end_time,
                            overall_score=moment.viral_score * 100,  # Convert to 0-100 scale
                            platform_scores={
                                platform: score * 100 
                                for platform, score in moment.platform_suitability.items()
                            },
                            confidence=moment.confidence,
                            reasoning=moment.description
                        )
                        virality_scores.append(virality_score)
                
                # If no high-scoring moments found, use top viral factors
                if not virality_scores:
                    logger.warning("No high-potential viral moments found, using top viral factors")
                    for factor in viral_analysis.viral_factors[:processing_options.max_clips]:
                        if factor.timestamp_relevance:
                            start_time, end_time = factor.timestamp_relevance
                            virality_score = ViralityScore(
                                start_time=start_time,
                                end_time=end_time,
                                overall_score=factor.score * 100,
                                platform_scores={
                                    platform: viral_analysis.platform_scores.get(platform, {}).get('score', 50) 
                                    for platform in processing_options.target_platforms
                                },
                                confidence=factor.confidence,
                                reasoning=factor.reasoning
                            )
                            virality_scores.append(virality_score)
                
                logger.info(f"Generated {len(virality_scores)} virality scores")
                
                # Filter high-potential segments
                high_potential_scores = [
                    score for score in virality_scores
                    if score.overall_score >= processing_options.min_virality_score
                ]
                
                if not high_potential_scores:
                    logger.warning("No high-potential segments found, using top scores")
                    high_potential_scores = sorted(
                        virality_scores, key=lambda x: x.overall_score, reverse=True
                    )[:processing_options.max_clips]
                
                # Generate clip segments
                await self._update_progress(progress, "Generating clip recommendations", 55)
                await self._call_progress_callback(progress, progress_callback)
                
                clip_segments = await self.ai_service.generate_clip_segments(
                    transcription_segments,
                    high_potential_scores,
                    video_metadata.to_dict(),
                    processing_options.target_platforms,
                    processing_options.max_clips
                )
                logger.info(f"Generated {len(clip_segments)} clip segments")
                
                # Process clips
                await self._update_progress(progress, "Processing video clips", 70)
                await self._call_progress_callback(progress, progress_callback)
                
                processed_clips = []
                for i, clip_segment in enumerate(clip_segments):
                    clip_progress = 70 + (i / len(clip_segments)) * 25
                    await self._update_progress(
                        progress, f"Processing clip {i+1}/{len(clip_segments)}", int(clip_progress)
                    )
                    await self._call_progress_callback(progress, progress_callback)
                    
                    # Create output directory
                    output_dir = os.path.join("uploads", "clips", job_id)
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # Generate clip
                    clip_filename = f"clip_{i+1}_{clip_segment.start_time:.0f}s_{clip_segment.end_time:.0f}s.mp4"
                    clip_path = os.path.join(output_dir, clip_filename)
                    
                    # Get platform-specific config
                    primary_platform = processing_options.target_platforms[0]
                    platform_config = self.video_processor._get_platform_config(
                        primary_platform, ProcessingConfig()
                    )
                    
                    processing_config = ProcessingConfig(
                        output_format="mp4",
                        video_codec="libx264",
                        audio_codec="aac",
                        bitrate=platform_config['bitrate'],
                        fps=platform_config['fps'],
                        width=platform_config.get('width'),
                        height=platform_config.get('height'),
                        preset=platform_config['preset']
                    )
                    
                    # Create clip
                    clip_result = await self.video_processor.create_clip(
                        video_path,
                        clip_segment.start_time,
                        clip_segment.duration,
                        clip_path,
                        processing_config,
                        primary_platform
                    )
                    
                    if clip_result.success:
                        # Generate thumbnail if requested
                        thumbnail_path = None
                        if processing_options.generate_thumbnails:
                            thumbnail_filename = f"thumbnail_{i+1}.jpg"
                            thumbnail_path = os.path.join(output_dir, thumbnail_filename)
                            
                            thumbnail_result = await self.video_processor.create_thumbnail(
                                clip_path,
                                clip_segment.duration / 2,  # Middle of clip
                                thumbnail_path
                            )
                            
                            if thumbnail_result.success:
                                thumbnail_path = thumbnail_result.output_path
                        
                        # Generate hashtags if requested
                        hashtags = []
                        if processing_options.generate_hashtags:
                            hashtags = await self.ai_service.generate_hashtags(
                                clip_segment.description,
                                primary_platform
                            )
                        
                        # Create clip data
                        clip_data = {
                            'job_id': job_id,
                            'clip_index': i + 1,
                            'start_time': clip_segment.start_time,
                            'end_time': clip_segment.end_time,
                            'duration': clip_segment.duration,
                            'file_path': clip_path,
                            'thumbnail_path': thumbnail_path,
                            'virality_score': clip_segment.virality_score.to_dict(),
                            'title_suggestions': clip_segment.title_suggestions,
                            'hashtags': hashtags,
                            'description': clip_segment.description,
                            'platform_optimizations': clip_segment.platform_optimizations,
                            'file_size': clip_result.size,
                            'processing_time': clip_result.processing_time
                        }
                        
                        processed_clips.append(clip_data)
                        
                        # Save to database
                        await self.supabase.create_clip(clip_data)
                        
                        logger.info(f"Successfully processed clip {i+1}")
                    else:
                        logger.error(f"Failed to process clip {i+1}: {clip_result.error}")
                
                # Finalize results
                await self._update_progress(progress, "Finalizing results", 95)
                await self._call_progress_callback(progress, progress_callback)
                
                # Save job results
                job_results = {
                    'job_id': job_id,
                    'original_filename': original_filename,
                    'file_size': file_size,
                    'video_metadata': video_metadata.to_dict(),
                    'transcription_segments': [seg.to_dict() for seg in transcription_segments],
                    'virality_scores': [score.to_dict() for score in virality_scores],
                    'processed_clips': processed_clips,
                    'processing_options': {
                        'target_platforms': processing_options.target_platforms,
                        'max_clips': processing_options.max_clips,
                        'min_virality_score': processing_options.min_virality_score
                    },
                    'processing_time': time.time() - start_time,
                    'status': 'completed'
                }
                
                # Save results to database
                await self.supabase.create_job_result(job_results)
                
                # Update final progress
                await self._update_progress(progress, "Completed successfully", 100)
                await self._call_progress_callback(progress, progress_callback)
                
                # Update statistics
                self.stats['completed_jobs'] += 1
                self.stats['average_processing_time'] = (
                    (self.stats['average_processing_time'] * (self.stats['completed_jobs'] - 1) + 
                     job_results['processing_time']) / self.stats['completed_jobs']
                )
                
                logger.info(f"Successfully processed job {job_id} in {job_results['processing_time']:.2f}s")
                
                return {
                    'success': True,
                    'job_id': job_id,
                    'results': job_results,
                    'message': f"Successfully generated {len(processed_clips)} clips"
                }
                
            finally:
                # Cleanup audio file
                if os.path.exists(audio_path):
                    try:
                        os.unlink(audio_path)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup audio file: {e}")
                
        except Exception as e:
            logger.error(f"Failed to process job {job_id}: {e}")
            
            # Update statistics
            self.stats['failed_jobs'] += 1
            
            # Update progress with error
            progress.status = "failed"
            progress.current_step = f"Error: {str(e)}"
            await self._update_progress(progress, f"Processing failed: {str(e)}", 0)
            await self._call_progress_callback(progress, progress_callback)
            
            # Save error to database
            error_data = {
                'job_id': job_id,
                'error': str(e),
                'processing_time': time.time() - start_time,
                'status': 'failed'
            }
            await self.supabase.create_job_result(error_data)
            
            return {
                'success': False,
                'job_id': job_id,
                'error': str(e),
                'message': f"Processing failed: {str(e)}"
            }
        
        finally:
            self.stats['total_jobs'] += 1

    async def _update_progress(
        self,
        progress: ProcessingProgress,
        current_step: str,
        progress_percent: int
    ):
        """Update processing progress."""
        progress.current_step = current_step
        progress.progress = progress_percent
        progress.last_update = datetime.now()
        
        # Update database
        await self.supabase.update_job_status(
            progress.job_id,
            status=progress.status,
            progress=progress_percent,
            current_step=current_step
        )

    async def _call_progress_callback(
        self,
        progress: ProcessingProgress,
        callback: Optional[Callable]
    ):
        """Call progress callback if provided."""
        if callback:
            try:
                await callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    async def process_url_task(
        self,
        job_id: str,
        video_url: str,
        processing_options: Optional[ProcessingOptions] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process a video from URL."""
        
        if processing_options is None:
            processing_options = ProcessingOptions()
        
        start_time = time.time()
        progress = ProcessingProgress(
            job_id=job_id,
            status="starting",
            progress=0,
            current_step="Downloading video from URL",
            estimated_remaining=600.0,  # 10 minutes default
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        try:
            # Update progress
            await self._update_progress(progress, "Downloading video", 10)
            await self._call_progress_callback(progress, progress_callback)
            
            # Download video (this would need to be implemented)
            # For now, we'll assume the video is already downloaded
            video_path = await self._download_video_from_url(video_url, job_id)
            
            # Process the downloaded video
            return await self.process_video_task(
                job_id,
                video_path,
                os.path.basename(video_url),
                0,  # Unknown file size
                processing_options,
                progress_callback
            )
            
        except Exception as e:
            logger.error(f"Failed to process URL job {job_id}: {e}")
            
            # Update progress with error
            progress.status = "failed"
            progress.current_step = f"Error: {str(e)}"
            await self._update_progress(progress, f"URL processing failed: {str(e)}", 0)
            await self._call_progress_callback(progress, progress_callback)
            
            return {
                'success': False,
                'job_id': job_id,
                'error': str(e),
                'message': f"URL processing failed: {str(e)}"
            }

    async def _download_video_from_url(self, url: str, job_id: str) -> str:
        """Download video from URL (placeholder implementation)."""
        # This is a placeholder - in a real implementation, you would:
        # 1. Use yt-dlp or similar to download from various platforms
        # 2. Handle different video formats and qualities
        # 3. Implement proper error handling and retries
        
        output_dir = os.path.join("uploads", "downloaded", job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # For now, raise an error indicating this needs implementation
        raise NotImplementedError("URL video download not yet implemented. Please upload video files directly.")

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            'stats': self.stats,
            'ai_service_status': self.ai_service.enabled,
            'video_processor_status': True,  # Assuming it's always available if initialized
            'timestamp': datetime.now().isoformat()
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check the health of all components."""
        ai_health = await self.ai_service.health_check()
        video_health = await self.video_processor.health_check()
        
        return {
            'status': 'healthy' if ai_health.get('status') != 'error' and video_health.get('status') != 'error' else 'degraded',
            'ai_service': ai_health,
            'video_processor': video_health,
            'processing_stats': self.stats,
            'timestamp': datetime.now().isoformat()
        }


# Global task processor instance
unified_task_processor = UnifiedTaskProcessor()

