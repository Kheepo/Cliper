from typing import Dict, Any, Optional
import asyncio
import json
from datetime import datetime
from ..utils.supabase_client import get_supabase_admin_client
from api.services.ai_analyzer import ai_analyzer

class JobProcessor:
    """Service for processing video analysis jobs"""
    
    def __init__(self):
        self.processing_jobs = set()  # Track currently processing jobs
        self.job_queue = asyncio.Queue()  # Queue for pending jobs
        self.queue_processing = False  # Flag to track if queue processing is running
    
    async def process_job(self, job_id: str) -> Dict[str, Any]:
        """Process a video analysis job"""
        if job_id in self.processing_jobs:
            return {'success': False, 'error': 'Job already being processed'}
        
        self.processing_jobs.add(job_id)
        
        try:
            # Import the WebSocket manager from main.py
            from api.main import broadcast_job_update
            
            supabase = get_supabase_admin_client()
            
            # Check if Supabase client is available
            if supabase is None:
                error_msg = "Supabase admin client is not available"
                print(f"Error processing job {job_id}: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            # Get job details
            job_result = supabase.table('jobs').select('*').eq('id', job_id).single().execute()
            
            if not job_result.data:
                return {'success': False, 'error': 'Job not found'}
            
            job = job_result.data[0]
            
            # Update progress: Starting
            await broadcast_job_update(job_id, "processing", 5, "Initializing job processing")
            
            # Update job status to processing
            await self._update_job_status(job_id, 'processing', 'Starting video analysis')
            
            # Update progress: Job status updated
            await broadcast_job_update(job_id, "processing", 10, "Job status updated to processing")
            
            # Get video file path - check multiple possible fields
            video_path = job.get('file_path') or job.get('video_filename') or job.get('video_url')
            if not video_path:
                await self._update_job_status(job_id, 'failed', 'No video file found')
                await broadcast_job_update(job_id, "failed", None, "No video file found")
                return {'success': False, 'error': 'No video file found'}
            
            # For uploaded files, construct the full path
            if job.get('video_filename') and not video_path.startswith('/'):
                video_path = f"uploads/{video_path}"
            
            # Update progress: Video path resolved
            await broadcast_job_update(job_id, "processing", 20, "Video path resolved, starting analysis")
            
            # Log processing start
            await self._log_job_event(job_id, job['user_id'], 'INFO', 
                                    'Starting AI analysis', {'video_path': video_path})
            
            # Perform AI analysis
            try:
                analysis_result = await ai_analyzer.analyze_video(video_path, job_id)
                # Update progress: Analysis completed
                await broadcast_job_update(job_id, "processing", 70, "AI analysis completed, saving results")
                
                # Save analysis results to job_results table
                result_data = {
                    'job_id': job_id,
                    'virality_score': analysis_result.viral_score.get('overall_score', 0) if isinstance(analysis_result.viral_score, dict) else analysis_result.viral_score,
                    'engagement_metrics': {
                        'transcription': analysis_result.transcription,
                        'processing_time': analysis_result.processing_time,
                        'metadata': analysis_result.metadata
                    },
                    'hashtags': analysis_result.metadata.get('suggested_hashtags', []) if analysis_result.metadata else [],
                    'suggested_clips': {
                        'scenes': [self._segment_to_dict(s) for s in analysis_result.scenes],
                        'emotions': [self._segment_to_dict(s) for s in analysis_result.emotions],
                        'faces': [self._segment_to_dict(s) for s in analysis_result.faces]
                    },
                    'analysis_summary': f'Video analysis completed with {len(analysis_result.scenes)} scenes, {len(analysis_result.emotions)} emotion segments, and {len(analysis_result.faces)} face detections.',
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Store results in database
                result_insert = supabase.table('job_results').insert(result_data).execute()
                
                # Also save detailed analysis results to analysis_results table
                detailed_results = [
                    {
                        'video_id': job_id,  # Using job_id as video_id for now
                        'user_id': job['user_id'],
                        'analysis_type': 'speech_recognition',
                        'analysis_data': {'transcription': analysis_result.transcription},
                        'confidence_score': 0.95,
                        'processing_time_ms': int(analysis_result.processing_time * 1000)
                    },
                    {
                        'video_id': job_id,
                        'user_id': job['user_id'],
                        'analysis_type': 'scene_detection',
                        'analysis_data': {'scenes': [self._segment_to_dict(s) for s in analysis_result.scenes]},
                        'confidence_score': 0.90,
                        'processing_time_ms': int(analysis_result.processing_time * 1000)
                    },
                    {
                        'video_id': job_id,
                        'user_id': job['user_id'],
                        'analysis_type': 'emotion_analysis',
                        'analysis_data': {'emotions': [self._segment_to_dict(s) for s in analysis_result.emotions]},
                        'confidence_score': 0.85,
                        'processing_time_ms': int(analysis_result.processing_time * 1000)
                    },
                    {
                        'video_id': job_id,
                        'user_id': job['user_id'],
                        'analysis_type': 'face_detection',
                        'analysis_data': {'faces': [self._segment_to_dict(s) for s in analysis_result.faces]},
                        'confidence_score': 0.92,
                        'processing_time_ms': int(analysis_result.processing_time * 1000)
                    }
                ]
                
                # Insert detailed analysis results
                for result in detailed_results:
                    supabase.table('analysis_results').insert(result).execute()
                
                if not result_insert.data:
                    raise Exception('Failed to save analysis results')
                
                # Update progress: Results stored
                await broadcast_job_update(job_id, "processing", 90, "Results stored in database")
                
                # Update job status to completed
                await self._update_job_status(job_id, 'completed', 
                                            f'Analysis completed in {analysis_result.processing_time:.1f}s')
                
                # Log successful completion
                await self._log_job_event(job_id, job['user_id'], 'INFO', 
                                        'Analysis completed successfully', {
                                            'processing_time': analysis_result.processing_time,
                                            'viral_score': analysis_result.viral_score.get('overall_score', 0)
                                        })
                
                # Complete progress tracking
                viral_score = analysis_result.viral_score.get('overall_score', 0) if isinstance(analysis_result.viral_score, dict) else analysis_result.viral_score
                
                # Update progress: Job completed
                await broadcast_job_update(job_id, "completed", 100, "Job processing completed successfully")
                
                return {
                    'success': True,
                    'job_id': job_id,
                    'result_id': result_insert.data[0]['id'],
                    'processing_time': analysis_result.processing_time,
                    'viral_score': viral_score
                }
                
            except Exception as analysis_error:
                error_msg = f'Analysis failed: {str(analysis_error)}'
                await self._update_job_status(job_id, 'failed', error_msg)
                await self._log_job_event(job_id, job['user_id'], 'ERROR', 
                                        'Analysis failed', {'error': str(analysis_error)})
                
                # Update progress with error
                await broadcast_job_update(job_id, "failed", None, error_msg)
                
                return {'success': False, 'error': error_msg}
            
        except Exception as e:
            error_msg = f'Job processing failed: {str(e)}'
            await self._update_job_status(job_id, 'failed', error_msg)
            await broadcast_job_update(job_id, "failed", None, error_msg)
            return {'success': False, 'error': error_msg}
        
        finally:
            self.processing_jobs.discard(job_id)
    
    async def _update_job_status(self, job_id: str, status: str, message: str = None):
        """Update job status in database"""
        try:
            supabase = get_supabase_admin_client()
            
            if supabase is None:
                print(f"Warning: Cannot update job status for {job_id} - Supabase client is None")
                return
            
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if message:
                update_data['status_message'] = message
            
            supabase.table('jobs').update(update_data).eq('id', job_id).execute()
            
        except Exception as e:
            print(f"Failed to update job status: {e}")
    
    async def _log_job_event(self, job_id: str, user_id: str, level: str, 
                           message: str, details: Dict[str, Any] = None):
        """Log job processing event"""
        try:
            supabase = get_supabase_admin_client()
            
            if supabase is None:
                print(f"Warning: Cannot log job event for {job_id} - Supabase client is None")
                return
            
            log_data = {
                'job_id': job_id,
                'user_id': user_id,
                'level': level,
                'message': message,
                'details': details or {},
                'created_at': datetime.utcnow().isoformat()
            }
            
            supabase.table('job_logs').insert(log_data).execute()
            
        except Exception as e:
            print(f"Failed to log job event: {e}")
    
    def _segment_to_dict(self, segment) -> Dict[str, Any]:
        """Convert AnalysisSegment to dictionary"""
        return {
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'confidence': segment.confidence,
            'data': segment.data
        }
    
    async def add_job_to_queue(self, job_id: str):
        """Add a job to the processing queue"""
        try:
            await self.job_queue.put(job_id)
            print(f"Job {job_id} added to processing queue")
            
            # Start queue processing if not already running
            if not self.queue_processing:
                asyncio.create_task(self._process_queue())
                
        except Exception as e:
            print(f"Failed to add job {job_id} to queue: {e}")
    
    async def _process_queue(self):
        """Process jobs from the queue"""
        if self.queue_processing:
            return
            
        self.queue_processing = True
        
        try:
            while True:
                try:
                    # Get job from queue with timeout
                    job_id = await asyncio.wait_for(self.job_queue.get(), timeout=1.0)
                    
                    # Process the job
                    await self.process_job(job_id)
                    
                    # Mark task as done
                    self.job_queue.task_done()
                    
                except asyncio.TimeoutError:
                    # No jobs in queue, continue checking
                    continue
                except Exception as e:
                    print(f"Error processing job from queue: {e}")
                    
        except Exception as e:
            print(f"Queue processing error: {e}")
        finally:
            self.queue_processing = False
    
    async def start_background_processing(self):
        """Start background job processing loop"""
        while True:
            try:
                await self._process_pending_jobs()
                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                print(f"Background processing error: {e}")
                await asyncio.sleep(10)  # Wait longer on error
    
    async def _process_pending_jobs(self):
        """Process all pending jobs"""
        try:
            supabase = get_supabase_admin_client()
            
            # Check if Supabase client is available
            if supabase is None:
                print("Warning: Supabase admin client is None - skipping pending job processing")
                return
            
            # Get pending jobs
            pending_jobs = supabase.table('jobs').select('id').eq('status', 'pending').limit(5).execute()
            
            if pending_jobs.data:
                # Process jobs concurrently (limit to 3 concurrent jobs)
                semaphore = asyncio.Semaphore(3)
                
                async def process_with_semaphore(job_id):
                    async with semaphore:
                        await self.process_job(job_id)
                
                tasks = [process_with_semaphore(job['id']) for job in pending_jobs.data]
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            print(f"Failed to process pending jobs: {e}")

# Global job processor instance
job_processor = JobProcessor()

# Background task starter
async def start_job_processing():
    """Start the background job processing"""
    await job_processor.start_background_processing()