from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from .supabase_service import supabase_service

class FirebaseService:
    """
    Firebase service layer that delegates to Supabase service.
    This class provides backward compatibility for existing code that still references FirebaseService.
    All operations are delegated to the SupabaseService implementation.
    """
    
    def __init__(self):
        # Delegate all operations to the Supabase service
        self._supabase_service = supabase_service
        logger.info("FirebaseService initialized - delegating to SupabaseService")
    
    async def save_virality_scores(self, video_id: str, scores: Dict[str, Any]) -> bool:
        """
        Save virality scores for a video.
        Handles both video_id and clip_id based calls for backward compatibility.
        
        Args:
            video_id: The video or clip identifier
            scores: Dictionary containing virality scores and metrics
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"FirebaseService.save_virality_scores called for video/clip {video_id}")
            
            # Convert scores dict to list format expected by SupabaseService
            if isinstance(scores, dict):
                virality_scores = []
                for niche, score_data in scores.items():
                    if isinstance(score_data, dict):
                        virality_scores.append({
                            'niche': niche,
                            'score': score_data.get('score', 0),
                            'explanation': score_data.get('explanation', '')
                        })
                    else:
                        # Handle simple score values
                        virality_scores.append({
                            'niche': niche,
                            'score': score_data,
                            'explanation': ''
                        })
            else:
                virality_scores = scores
            
            # Use video_id as clip_id (they're often the same in the context)
            return await self._supabase_service.save_virality_scores(video_id, virality_scores)
        except Exception as e:
            logger.error(f"Error in FirebaseService.save_virality_scores: {e}")
            return False
    
    async def update_job_status(self, job_id: str, status: str, progress: Optional[int] = None, current_step: Optional[str] = None) -> bool:
        """
        Update job status.
        Delegates to SupabaseService implementation.
        
        Args:
            job_id: The job identifier
            status: New status
            progress: Progress percentage (0-100)
            current_step: Current processing step description
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"FirebaseService.update_job_status called for job {job_id}")
            # Delegate to SupabaseService
            return await self._supabase_service.update_job_status(job_id, status, progress, current_step)
        except Exception as e:
            logger.error(f"Error in FirebaseService.update_job_status: {e}")
            return False
    
    async def create_video(self, video_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new video record.
        Delegates to SupabaseService implementation.
        
        Args:
            video_data: Video metadata and information
            
        Returns:
            str: Video ID if successful, None otherwise
        """
        try:
            logger.info(f"FirebaseService.create_video called")
            # Delegate to SupabaseService
            return await self._supabase_service.create_video(video_data)
        except Exception as e:
            logger.error(f"Error in FirebaseService.create_video: {e}")
            return None
    
    async def create_clip(self, clip_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new clip record.
        Delegates to SupabaseService implementation.
        
        Args:
            clip_data: Clip metadata and information
            
        Returns:
            str: Clip ID if successful, None otherwise
        """
        try:
            logger.info(f"FirebaseService.create_clip called")
            # Delegate to SupabaseService
            return await self._supabase_service.create_clip(clip_data)
        except Exception as e:
            logger.error(f"Error in FirebaseService.create_clip: {e}")
            return None
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job information.
        Delegates to SupabaseService implementation.
        
        Args:
            job_id: The job identifier
            
        Returns:
            dict: Job data if found, None otherwise
        """
        try:
            logger.info(f"FirebaseService.get_job called for job {job_id}")
            # Delegate to SupabaseService
            return await self._supabase_service.get_job(job_id)
        except Exception as e:
            logger.error(f"Error in FirebaseService.get_job: {e}")
            return None
    
    async def save_analysis_result(self, video_id: str, user_id: str, analysis_data: Dict[str, Any]) -> bool:
        """
        Save analysis results.
        Creates an analysis_results record in Supabase.
        
        Args:
            video_id: The video identifier
            user_id: The user identifier
            analysis_data: Analysis results data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"FirebaseService.save_analysis_result called for video {video_id}")
            
            # Create analysis result record
            analysis_record = {
                'video_id': video_id,
                'user_id': user_id,
                'analysis_data': analysis_data,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = self._supabase_service.client.table('analysis_results').insert(analysis_record).execute()
            
            if result.data:
                logger.info(f"Analysis result saved for video {video_id}")
                return True
            else:
                logger.error(f"Failed to save analysis result for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error in FirebaseService.save_analysis_result: {e}")
            return False
    
    # Add other methods as needed for backward compatibility
    def __getattr__(self, name):
        """
        Delegate any missing method calls to the SupabaseService.
        This provides automatic backward compatibility for any methods not explicitly defined.
        """
        logger.info(f"FirebaseService delegating method '{name}' to SupabaseService")
        return getattr(self._supabase_service, name)

# Global service instance for backward compatibility
_firebase_service_instance = None

def get_firebase_service() -> FirebaseService:
    """
    Get Firebase service instance with lazy initialization.
    This provides backward compatibility for existing code.
    
    Returns:
        FirebaseService instance that delegates to SupabaseService
    """
    global _firebase_service_instance
    
    if _firebase_service_instance is None:
        _firebase_service_instance = FirebaseService()
        logger.info("FirebaseService instance created (delegating to SupabaseService)")
    
    return _firebase_service_instance

# Create global instance for backward compatibility
firebase_service = get_firebase_service()