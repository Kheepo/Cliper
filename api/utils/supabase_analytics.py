from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from supabase import create_client, Client
import os
import logging

logger = logging.getLogger(__name__)

class SupabaseAnalytics:
    """Analytics service using Supabase client instead of SQLAlchemy."""
    
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not self.supabase_url or not self.supabase_service_key:
            raise ValueError("Missing Supabase configuration")
            
        self.client: Client = create_client(self.supabase_url, self.supabase_service_key)
    
    async def get_user_analytics(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get basic analytics data for a user using Supabase client."""
        try:
            # Get user's clips count and data
            response = self.client.table('clips').select('*').filter(
                'user_id', 'eq', user_id
            ).filter(
                'created_at', 'gte', start_date.isoformat()
            ).filter(
                'created_at', 'lte', end_date.isoformat()
            ).execute()
            
            clips = response.data
            total_clips = len(clips)
            
            if total_clips == 0:
                return {
                    'total_clips': 0,
                    'total_views': 0,
                    'total_downloads': 0,
                    'engagement_score': 0,
                    'activity_level': 'inactive',
                    'last_active': datetime.utcnow()
                }
            
            # Calculate metrics from clips
            total_views = 0
            total_downloads = 0
            
            for clip in clips:
                # Use virality and confidence scores as proxy for engagement
                virality_score = clip.get('virality_score', 0) or 0
                confidence_score = clip.get('confidence_score', 0.1) or 0.1
                
                clip_views = max(1, int(virality_score * 100))
                clip_downloads = max(0, int(clip_views * confidence_score))
                
                total_views += clip_views
                total_downloads += clip_downloads
            
            # Calculate engagement score
            engagement_score = (total_views + total_downloads * 2) / max(total_clips, 1)
            
            # Determine activity level
            activity_level = "active" if total_clips > 0 else "inactive"
            
            return {
                'total_clips': total_clips,
                'total_views': total_views,
                'total_downloads': total_downloads,
                'engagement_score': round(engagement_score, 2),
                'activity_level': activity_level,
                'last_active': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {
                'total_clips': 0,
                'total_views': 0,
                'total_downloads': 0,
                'engagement_score': 0,
                'activity_level': 'inactive',
                'last_active': datetime.utcnow()
            }
    
    async def get_user_growth_metrics(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get user growth metrics using Supabase client."""
        try:
            # Get clips created in period
            response = self.client.table('clips').select('id, created_at').filter(
                'user_id', 'eq', user_id
            ).filter(
                'created_at', 'gte', start_date.isoformat()
            ).filter(
                'created_at', 'lte', end_date.isoformat()
            ).execute()
            
            clips_created = len(response.data)
            total_days = (end_date - start_date).days or 1
            
            # Calculate growth rate
            growth_rate = (clips_created / total_days) * 30  # Monthly rate
            
            return {
                "clips_growth_rate": round(growth_rate, 2),
                "views_growth_rate": 15.5,  # Placeholder
                "followers_growth_rate": 8.2,  # Placeholder
                "engagement_growth_rate": 12.1  # Placeholder
            }
            
        except Exception as e:
            logger.error(f"Error getting user growth metrics: {e}")
            return {
                "clips_growth_rate": 0,
                "views_growth_rate": 0,
                "followers_growth_rate": 0,
                "engagement_growth_rate": 0
            }
    
    async def get_user_content_performance(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get user content performance metrics using Supabase client."""
        try:
            # Get user's clips
            response = self.client.table('clips').select('*').filter(
                'user_id', 'eq', user_id
            ).filter(
                'created_at', 'gte', start_date.isoformat()
            ).filter(
                'created_at', 'lte', end_date.isoformat()
            ).execute()
            
            clips = response.data
            
            if not clips:
                return {}
            
            # Calculate performance metrics
            total_views = 0
            total_downloads = 0
            
            for clip in clips:
                virality_score = clip.get('virality_score', 0) or 0
                confidence_score = clip.get('confidence_score', 0.1) or 0.1
                
                clip_views = max(1, int(virality_score * 100))
                clip_downloads = max(0, int(clip_views * confidence_score))
                
                total_views += clip_views
                total_downloads += clip_downloads
            
            avg_views_per_clip = total_views / len(clips)
            avg_downloads_per_clip = total_downloads / len(clips)
            
            return {
                "avg_views_per_clip": round(avg_views_per_clip, 2),
                "avg_downloads_per_clip": round(avg_downloads_per_clip, 2),
                "best_performing_clip": clips[0].get('title') if clips else None,
                "total_engagement": total_views + total_downloads
            }
            
        except Exception as e:
            logger.error(f"Error getting user content performance: {e}")
            return {}
    
    async def get_user_audience_insights(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get user audience insights using Supabase client."""
        try:
            # Get user's clips
            response = self.client.table('clips').select('*').filter(
                'user_id', 'eq', user_id
            ).filter(
                'created_at', 'gte', start_date.isoformat()
            ).filter(
                'created_at', 'lte', end_date.isoformat()
            ).execute()
            
            clips = response.data
            
            if not clips:
                return {}
            
            # Calculate audience insights (placeholder data)
            total_estimated_viewers = sum(
                max(1, int((clip.get('virality_score', 0) or 0) * 100))
                for clip in clips
            )
            
            return {
                "total_estimated_viewers": total_estimated_viewers,
                "top_demographics": {
                    "age_groups": {"18-24": 40, "25-34": 35, "35-44": 25},
                    "locations": {"US": 50, "UK": 30, "CA": 20},
                    "devices": {"mobile": 60, "desktop": 30, "tablet": 10}
                },
                "engagement_patterns": {
                    "peak_hours": ["19:00", "20:00", "21:00"],
                    "peak_days": ["Saturday", "Sunday"]
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting user audience insights: {e}")
            return {}
    
    async def get_clip_analytics(self, clip_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get basic analytics data for a clip using Supabase client."""
        try:
            # Get clip data
            response = self.client.table('clips').select('*').filter(
                'id', 'eq', clip_id
            ).execute()
            
            if not response.data:
                return {
                    'views': 0, 
                    'downloads': 0, 
                    'engagement_rate': 0, 
                    'performance_score': 0, 
                    'trending_score': 0
                }
            
            clip = response.data[0]
            
            # Use virality and confidence scores as proxy for engagement
            virality_score = clip.get('virality_score', 0) or 0
            confidence_score = clip.get('confidence_score', 0.1) or 0.1
            
            views_count = max(1, int(virality_score * 100))
            downloads_count = max(0, int(views_count * confidence_score))
            
            # Calculate engagement rate
            total_interactions = views_count + downloads_count
            engagement_rate = (total_interactions / max(views_count, 1)) * 100
            
            # Calculate performance and trending scores
            performance_score = (virality_score * 0.6) + (confidence_score * 0.4)
            trending_score = min(10, virality_score + (confidence_score * 2))
            
            return {
                'views': views_count,
                'downloads': downloads_count,
                'engagement_rate': round(engagement_rate, 2),
                'performance_score': round(performance_score, 2),
                'trending_score': round(trending_score, 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting clip analytics: {e}")
            return {
                'views': 0,
                'downloads': 0,
                'engagement_rate': 0,
                'performance_score': 0,
                'trending_score': 0
            }

# Global instance
supabase_analytics = None

def get_supabase_analytics() -> SupabaseAnalytics:
    """Get or create Supabase analytics instance."""
    global supabase_analytics
    if supabase_analytics is None:
        supabase_analytics = SupabaseAnalytics()
    return supabase_analytics