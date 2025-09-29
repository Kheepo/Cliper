from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ..utils.supabase_client import get_supabase_admin_client
from supabase import Client

class SupabaseService:
    """
    Supabase service layer for handling database operations.
    Replaces Firebase Firestore operations with Supabase database operations.
    """
    
    def __init__(self):
        self.client: Client = get_supabase_admin_client()
        
        # Check if Supabase client is available
        self.supabase_available = self.client is not None
        
        if not self.supabase_available:
            logger.warning("Supabase client is not available - some features will be disabled")
    
    def _check_supabase_available(self):
        """Check if Supabase client is available and raise exception if not"""
        if not self.supabase_available:
            raise Exception("Supabase client is not available. Please check your Supabase configuration.")
    
    # User Management
    async def create_user(self, user_data: Dict[str, Any]) -> str:
        """
        Create a new user in Supabase.
        """
        self._check_supabase_available()
        try:
            current_time = datetime.utcnow().isoformat()
            user_data['created_at'] = current_time
            user_data['updated_at'] = current_time
            
            result = self.client.table('users').insert(user_data).execute()
            
            if result.data:
                user_id = result.data[0]['id']
                logger.info(f"User created with ID: {user_id}")
                return str(user_id)
            else:
                raise Exception("Failed to create user")
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID.
        """
        try:
            result = self.client.table('users').select('*').eq('id', user_id).execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            raise
    
    async def get_user_by_auth_id(self, auth_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by auth_id (Supabase Auth user ID).
        """
        try:
            result = self.client.table('users').select('*').eq('auth_id', auth_id).execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting user by auth_id {auth_id}: {str(e)}")
            raise
    
    async def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """
        Update user data.
        """
        try:
            user_data['updated_at'] = datetime.utcnow().isoformat()
            
            result = self.client.table('users').update(user_data).eq('id', user_id).execute()
            
            logger.info(f"User {user_id} updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            raise
    
    async def delete_user(self, user_id: str) -> bool:
        """
        Delete user from Supabase.
        """
        try:
            result = self.client.table('users').delete().eq('id', user_id).execute()
            
            logger.info(f"User {user_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            raise
    
    # Job Management
    async def create_job(self, job_data: Dict[str, Any]) -> str:
        """
        Create a new processing job in Supabase.
        """
        try:
            current_time = datetime.utcnow().isoformat()
            job_data['created_at'] = current_time
            job_data['updated_at'] = current_time
            job_data['status'] = job_data.get('status', 'pending')
            
            result = self.client.table('jobs').insert(job_data).execute()
            
            if result.data:
                job_id = result.data[0]['id']
                logger.info(f"Job created with ID: {job_id}")
                return str(job_id)
            else:
                raise Exception("Failed to create job")
        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            raise
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job by ID.
        """
        try:
            result = self.client.table('jobs').select('*').eq('id', job_id).execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {str(e)}")
            raise
    
    async def update_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """
        Update job data.
        """
        try:
            job_data['updated_at'] = datetime.utcnow().isoformat()
            
            result = self.client.table('jobs').update(job_data).eq('id', job_id).execute()
            
            logger.info(f"Job {job_id} updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating job {job_id}: {str(e)}")
            raise
    
    async def update_job_status(self, job_id: str, status: str, progress: Optional[int] = None, current_step: Optional[str] = None) -> bool:
        """
        Update job status, progress, and current step.
        """
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if progress is not None:
                update_data['progress'] = progress
                
            if current_step is not None:
                update_data['current_step'] = current_step
            
            result = self.client.table('jobs').update(update_data).eq('id', job_id).execute()
            
            logger.info(f"Job {job_id} status updated to {status}" + (f" - {current_step}" if current_step else ""))
            return True
        except Exception as e:
            logger.error(f"Error updating job {job_id}: {str(e)}")
            raise
    
    async def get_user_jobs(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all jobs for a specific user.
        """
        try:
            result = self.client.table('jobs').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting jobs for user {user_id}: {str(e)}")
            raise
    
    # Clip Management
    async def create_clip(self, clip_data: Dict[str, Any]) -> str:
        """
        Create a new video clip record in Supabase.
        """
        try:
            current_time = datetime.utcnow().isoformat()
            clip_data['created_at'] = current_time
            clip_data['updated_at'] = current_time
            
            result = self.client.table('clips').insert(clip_data).execute()
            
            if result.data:
                clip_id = result.data[0]['id']
                logger.info(f"Clip created with ID: {clip_id}")
                return str(clip_id)
            else:
                raise Exception("Failed to create clip")
        except Exception as e:
            logger.error(f"Error creating clip: {str(e)}")
            raise
    
    async def get_clip(self, clip_id: str) -> Optional[Dict[str, Any]]:
        """
        Get clip by ID.
        """
        try:
            result = self.client.table('clips').select('*').eq('id', clip_id).execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting clip {clip_id}: {str(e)}")
            raise
    
    async def get_job_clips(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all clips for a specific job.
        """
        try:
            result = self.client.table('clips').select('*').eq('job_id', job_id).order('start_time').execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting clips for job {job_id}: {str(e)}")
            raise
    
    async def update_clip(self, clip_id: str, clip_data: Dict[str, Any]) -> bool:
        """
        Update clip data.
        """
        try:
            clip_data['updated_at'] = datetime.utcnow().isoformat()
            
            result = self.client.table('clips').update(clip_data).eq('id', clip_id).execute()
            
            logger.info(f"Clip {clip_id} updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating clip {clip_id}: {str(e)}")
            raise
    
    # Additional methods for main.py compatibility
    async def get_recent_jobs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent jobs within specified hours."""
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            result = self.client.table('jobs').select('*').gte('created_at', cutoff_time).order('created_at', desc=True).execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting recent jobs: {str(e)}")
            return []
    
    async def get_stuck_jobs(self, hours: int = 2) -> List[Dict[str, Any]]:
        """Get jobs that might be stuck."""
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            result = self.client.table('jobs').select('*').in_('status', ['processing', 'uploading', 'pending', 'analyzing']).lte('created_at', cutoff_time).execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting stuck jobs: {str(e)}")
            return []
    
    async def create_video(self, video_data: Dict[str, Any]) -> str:
        """Create a video record."""
        try:
            current_time = datetime.utcnow().isoformat()
            video_data['created_at'] = current_time
            video_data['updated_at'] = current_time
            
            result = self.client.table('videos').insert(video_data).execute()
            
            if result.data:
                video_id = result.data[0]['id']
                logger.info(f"Video created with ID: {video_id}")
                return str(video_id)
            else:
                raise Exception("Failed to create video")
        except Exception as e:
            logger.error(f"Error creating video: {str(e)}")
            raise
    
    async def get_video_by_job_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get video by job ID."""
        try:
            result = self.client.table('videos').select('*').eq('job_id', job_id).limit(1).execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting video by job ID {job_id}: {str(e)}")
            return None
    
    async def get_clips_by_job_id(self, job_id: str) -> List[Dict[str, Any]]:
        """Get clips by job ID."""
        try:
            result = self.client.table('clips').select('*').eq('job_id', job_id).order('start_time').execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting clips by job ID {job_id}: {str(e)}")
            return []
    
    async def save_virality_scores(self, clip_id: str, virality_scores: List[Dict[str, Any]]) -> bool:
        """Save virality scores for a clip."""
        try:
            # Delete existing scores for this clip first
            self.client.table('virality_scores').delete().eq('clip_id', clip_id).execute()
            
            # Save new scores
            scores_to_insert = []
            for score_data in virality_scores:
                score_doc = {
                    'clip_id': clip_id,
                    'niche': score_data.get('niche'),
                    'score': score_data.get('score'),
                    'explanation': score_data.get('explanation'),
                    'created_at': datetime.utcnow().isoformat()
                }
                scores_to_insert.append(score_doc)
            
            if scores_to_insert:
                self.client.table('virality_scores').insert(scores_to_insert).execute()
            
            logger.info(f"Saved {len(virality_scores)} virality scores for clip {clip_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving virality scores for clip {clip_id}: {str(e)}")
            return False
    
    async def get_virality_scores_by_clip_id(self, clip_id: str) -> Dict[str, Dict[str, Any]]:
        """Get virality scores by clip ID."""
        try:
            result = self.client.table('virality_scores').select('*').eq('clip_id', clip_id).execute()
            
            scores = {}
            for score_data in result.data or []:
                niche = score_data.get('niche')
                if niche:
                    scores[niche] = {
                        'score': score_data.get('score'),
                        'explanation': score_data.get('explanation')
                    }
            
            return scores
        except Exception as e:
            logger.error(f"Error getting virality scores by clip ID {clip_id}: {str(e)}")
            return {}
    
    async def get_hashtags_by_clip_id(self, clip_id: str) -> List[str]:
        """Get hashtags by clip ID."""
        try:
            result = self.client.table('hashtags').select('*').eq('clip_id', clip_id).execute()
            
            hashtags = []
            for hashtag_data in result.data or []:
                tag = hashtag_data.get('tag')
                if tag:
                    hashtags.append(tag)
            
            return hashtags
        except Exception as e:
            logger.error(f"Error getting hashtags by clip ID {clip_id}: {str(e)}")
            return []
    
    async def get_posting_recommendations_by_clip_id(self, clip_id: str) -> Dict[str, Dict[str, Any]]:
        """Get posting recommendations by clip ID."""
        try:
            result = self.client.table('posting_recommendations').select('*').eq('clip_id', clip_id).execute()
            
            recommendations = {}
            for rec_data in result.data or []:
                platform = rec_data.get('platform')
                if platform:
                    recommendations[platform] = {
                        'optimal_times': rec_data.get('optimal_times'),
                        'format_suggestions': rec_data.get('format_suggestions')
                    }
            
            return recommendations
        except Exception as e:
            logger.error(f"Error getting posting recommendations by clip ID {clip_id}: {str(e)}")
            return {}
    
    async def update_clip_status(self, clip_id: str, status: str, error_message: str = None) -> bool:
        """Update clip status and optionally error message."""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if error_message:
                update_data['error_message'] = error_message
            
            result = self.client.table('clips').update(update_data).eq('id', clip_id).execute()
            
            logger.info(f"Clip {clip_id} status updated to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating clip status {clip_id}: {str(e)}")
            return False
    
    async def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video information by video ID."""
        try:
            result = self.client.table('videos').select('*').eq('id', video_id).limit(1).execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting video info {video_id}: {str(e)}")
            return None
    
    async def get_analysis_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis results for a job."""
        try:
            # First try to get from analysis_results table
            result = self.client.table('analysis_results').select('*').eq('job_id', job_id).limit(1).execute()
            
            if result.data:
                return result.data[0]
            
            # Fallback: check if results are stored in jobs table
            job_result = self.client.table('jobs').select('analysis_results').eq('id', job_id).limit(1).execute()
            
            if job_result.data and job_result.data[0].get('analysis_results'):
                return job_result.data[0]['analysis_results']
            
            return None
        except Exception as e:
            logger.error(f"Error getting analysis results for job {job_id}: {str(e)}")
            return None
    
    async def update_clip_data(self, clip_id: str, **kwargs) -> bool:
        """Update clip data with flexible field updates."""
        try:
            update_data = kwargs.copy()
            update_data['updated_at'] = datetime.utcnow().isoformat()
            
            result = self.client.table('clips').update(update_data).eq('id', clip_id).execute()
            
            logger.info(f"Clip {clip_id} data updated with fields: {list(kwargs.keys())}")
            return True
        except Exception as e:
            logger.error(f"Error updating clip data {clip_id}: {str(e)}")
            return False
    
    # Generated Clips Management
    async def create_generated_clip(self, clip_data: Dict[str, Any]) -> str:
        """Create a new generated clip record."""
        try:
            current_time = datetime.utcnow().isoformat()
            clip_data['created_at'] = current_time
            clip_data['updated_at'] = current_time
            clip_data['status'] = clip_data.get('status', 'pending')
            clip_data['retry_count'] = clip_data.get('retry_count', 0)
            
            result = self.client.table('generated_clips').insert(clip_data).execute()
            
            if result.data:
                clip_id = result.data[0]['id']
                logger.info(f"Generated clip created with ID: {clip_id}")
                return str(clip_id)
            else:
                raise Exception("Failed to create generated clip")
        except Exception as e:
            logger.error(f"Error creating generated clip: {str(e)}")
            raise
    
    async def get_generated_clip(self, clip_id: str) -> Optional[Dict[str, Any]]:
        """Get generated clip by ID."""
        try:
            result = self.client.table('generated_clips').select('*').eq('id', clip_id).execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting generated clip {clip_id}: {str(e)}")
            raise
    
    async def update_generated_clip_status(self, clip_id: str, status: str, error_message: str = None) -> bool:
        """Update generated clip status and optionally error message."""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if error_message:
                update_data['error_message'] = error_message
                update_data['last_error_at'] = datetime.utcnow().isoformat()
            
            if status == 'failed':
                # Increment retry count for failed clips
                current_clip = await self.get_generated_clip(clip_id)
                if current_clip:
                    update_data['retry_count'] = current_clip.get('retry_count', 0) + 1
            
            result = self.client.table('generated_clips').update(update_data).eq('id', clip_id).execute()
            
            logger.info(f"Generated clip {clip_id} status updated to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating generated clip status {clip_id}: {str(e)}")
            return False
    
    async def update_generated_clip_data(self, clip_id: str, **kwargs) -> bool:
        """Update generated clip data with flexible field updates."""
        try:
            update_data = kwargs.copy()
            update_data['updated_at'] = datetime.utcnow().isoformat()
            
            result = self.client.table('generated_clips').update(update_data).eq('id', clip_id).execute()
            
            logger.info(f"Generated clip {clip_id} data updated with fields: {list(kwargs.keys())}")
            return True
        except Exception as e:
            logger.error(f"Error updating generated clip data {clip_id}: {str(e)}")
            return False
    
    async def get_generated_clips_by_video(self, video_id: str) -> List[Dict[str, Any]]:
        """Get all generated clips for a specific video."""
        try:
            result = self.client.table('generated_clips').select('*').eq('original_video_id', video_id).order('created_at', desc=True).execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting generated clips for video {video_id}: {str(e)}")
            return []
    
    async def get_generated_clips_by_user(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all generated clips for a specific user."""
        try:
            result = self.client.table('generated_clips').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting generated clips for user {user_id}: {str(e)}")
            return []
    
    async def get_failed_generated_clips(self, max_retries: int = 3) -> List[Dict[str, Any]]:
        """Get failed generated clips that can be retried."""
        try:
            result = self.client.table('generated_clips').select('*').eq('status', 'failed').lt('retry_count', max_retries).order('last_error_at', desc=True).execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting failed generated clips: {str(e)}")
            return []
    
    async def delete_generated_clip(self, clip_id: str) -> bool:
        """Delete a generated clip record."""
        try:
            result = self.client.table('generated_clips').delete().eq('id', clip_id).execute()
            
            logger.info(f"Generated clip {clip_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting generated clip {clip_id}: {str(e)}")
            return False

# Global service instance
_supabase_service_instance = None

def get_supabase_service() -> Optional[SupabaseService]:
    """Get Supabase service instance with lazy initialization.
    
    Returns:
        SupabaseService instance if Supabase is properly configured, None otherwise
    """
    global _supabase_service_instance
    
    if _supabase_service_instance is None:
        try:
            _supabase_service_instance = SupabaseService()
            # Check if Supabase is actually available
            if not _supabase_service_instance.supabase_available:
                logger.warning("Supabase service is not available - returning None")
                return None
        except Exception as e:
            logger.error(f"Failed to initialize Supabase service: {str(e)}")
            return None
    
    return _supabase_service_instance if _supabase_service_instance.supabase_available else None

# Global instance for backward compatibility
supabase_service = get_supabase_service()