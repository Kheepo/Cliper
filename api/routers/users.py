from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.pydantic_models import (
    UserSettingsResponse, UserSettingsUpdate, UserStatsResponse, UserHistory, UserProfileResponse, UserProfileUpdate
)
from ..utils.supabase_client import get_supabase_admin_client
from ..middleware.auth import get_supabase_token_info_from_auth_middleware as get_supabase_token_info

router = APIRouter(tags=["users"])

@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get current user's settings"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Get user settings
        settings_result = supabase.table('user_settings').select('*').eq('user_id', user_id).execute()
        
        if not settings_result.data:
            # Create default settings if they don't exist
            from datetime import datetime
            default_settings = {
                'user_id': user_id,
                'preferred_language': 'en',
                'timezone': 'UTC',
                'email_notifications': True,
                'push_notifications': True,
                'auto_process_uploads': False,
                'max_concurrent_jobs': 3,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            insert_result = supabase.table('user_settings').insert(default_settings).execute()
            return UserSettingsResponse(**insert_result.data[0])
        
        return UserSettingsResponse(**settings_result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user settings: {str(e)}"
        )

@router.put("/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    settings_update: UserSettingsUpdate,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Update current user's settings"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Check if settings exist
        settings_result = supabase.table('user_settings').select('*').eq('user_id', user_id).execute()
        
        if not settings_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User settings not found"
            )
        
        # Update fields that are provided
        update_data = settings_update.model_dump(exclude_unset=True)
        if update_data:
            from datetime import datetime
            update_data['updated_at'] = datetime.utcnow().isoformat()
            
            updated_result = supabase.table('user_settings').update(update_data).eq('user_id', user_id).execute()
            return UserSettingsResponse(**updated_result.data[0])
        
        # If no updates, return current settings
        return UserSettingsResponse(**settings_result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user settings: {str(e)}"
        )

@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get current user's profile information"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user profile from database
        user_result = supabase.table('users').select(
            'id, email, display_name, photo_url, is_active, email_verified, role, created_at, updated_at, last_login'
        ).eq('auth_id', auth_id).execute()
        
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        user_data = user_result.data[0]
        
        return UserProfileResponse(
            id=str(user_data['id']),
            email=user_data['email'],
            display_name=user_data.get('display_name'),
            photo_url=user_data.get('photo_url'),
            is_active=user_data.get('is_active', True),
            email_verified=user_data.get('email_verified', False),
            role=user_data.get('role', 'user'),
            created_at=datetime.fromisoformat(user_data['created_at'].replace('Z', '+00:00')) if user_data.get('created_at') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(user_data['updated_at'].replace('Z', '+00:00')) if user_data.get('updated_at') else datetime.utcnow(),
            last_login=datetime.fromisoformat(user_data['last_login'].replace('Z', '+00:00')) if user_data.get('last_login') else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user profile: {str(e)}"
        )

@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Update current user's profile information"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Check if user exists
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prepare update data (only include non-None values)
        update_data = {}
        if profile_update.display_name is not None:
            update_data['display_name'] = profile_update.display_name
        if profile_update.photo_url is not None:
            update_data['photo_url'] = profile_update.photo_url
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields provided for update"
            )
        
        # Add updated timestamp
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Update user profile
        result = supabase.table('users').update(update_data).eq('auth_id', auth_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user profile"
            )
        
        # Return updated profile
        updated_user = result.data[0]
        
        return UserProfileResponse(
            id=str(updated_user['id']),
            email=updated_user['email'],
            display_name=updated_user.get('display_name'),
            photo_url=updated_user.get('photo_url'),
            is_active=updated_user.get('is_active', True),
            email_verified=updated_user.get('email_verified', False),
            role=updated_user.get('role', 'user'),
            created_at=datetime.fromisoformat(updated_user['created_at'].replace('Z', '+00:00')) if updated_user.get('created_at') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(updated_user['updated_at'].replace('Z', '+00:00')) if updated_user.get('updated_at') else datetime.utcnow(),
            last_login=datetime.fromisoformat(updated_user['last_login'].replace('Z', '+00:00')) if updated_user.get('last_login') else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user profile: {str(e)}"
        )

@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get current user's statistics"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Get all jobs for the user
        jobs_result = supabase.table('jobs').select('id, status').eq('user_id', user_id).execute()
        jobs = jobs_result.data
        
        # Calculate job statistics
        total_jobs = len(jobs)
        completed_jobs = len([j for j in jobs if j['status'] == 'completed'])
        failed_jobs = len([j for j in jobs if j['status'] == 'failed'])
        pending_jobs = len([j for j in jobs if j['status'] == 'pending'])
        processing_jobs = len([j for j in jobs if j['status'] == 'processing'])
        
        # Get processing time and virality statistics from job results
        job_results = supabase.table('job_results').select('processing_time_seconds, virality_score').in_('job_id', [j['id'] for j in jobs]).execute()
        
        total_processing_time = sum(r.get('processing_time_seconds', 0) or 0 for r in job_results.data)
        virality_scores = [r.get('virality_score') for r in job_results.data if r.get('virality_score') is not None]
        average_virality_score = sum(virality_scores) / len(virality_scores) if virality_scores else None
        
        return UserStatsResponse(
            total_jobs=total_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            pending_jobs=pending_jobs,
            processing_jobs=processing_jobs,
            total_processing_time=total_processing_time,
            average_virality_score=average_virality_score
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user statistics: {str(e)}"
        )

@router.get("/activity")
async def get_user_activity(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    limit: int = 10
):
    """Get recent user activity (jobs and logs)"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Get recent jobs
        recent_jobs_result = supabase.table('jobs').select('id, job_type, status, title, created_at, updated_at').eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
        
        # Get recent logs
        recent_logs_result = supabase.table('job_logs').select('id, job_id, level, message, created_at').eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
        
        return {
            "recent_jobs": [
                {
                    "id": job["id"],
                    "type": job["job_type"],
                    "status": job["status"],
                    "title": job["title"],
                    "created_at": job["created_at"],
                    "updated_at": job["updated_at"]
                }
                for job in recent_jobs_result.data
            ],
            "recent_logs": [
                {
                    "id": log["id"],
                    "job_id": log["job_id"],
                    "level": log["level"],
                    "message": log["message"],
                    "created_at": log["created_at"]
                }
                for log in recent_logs_result.data
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user activity: {str(e)}"
        )

@router.get("/history", response_model=UserHistory)
async def get_user_history(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info),
    limit: int = 50,
    offset: int = 0
):
    """Get user's processing history with jobs and results"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Get total count of jobs for pagination
        total_count_result = supabase.table('jobs').select('id', count='exact').eq('user_id', user_id).execute()
        total_jobs = total_count_result.count or 0
        
        # Get jobs with their results
        jobs_result = supabase.table('jobs').select(
            'id, job_type, status, title, video_url, created_at, updated_at'
        ).eq('user_id', user_id).order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        
        jobs_with_results = []
        for job in jobs_result.data:
            job_data = {
                'id': job['id'],
                'job_type': job['job_type'],
                'status': job['status'],
                'title': job['title'],
                'video_url': job['video_url'],
                'created_at': job['created_at'],
                'updated_at': job['updated_at'],
                'result': None
            }
            
            # Get job result if exists
            result_query = supabase.table('job_results').select(
                'processing_time_seconds, virality_score, best_clips, hashtags, posting_recommendations'
            ).eq('job_id', job['id']).execute()
            
            if result_query.data:
                job_data['result'] = result_query.data[0]
            
            jobs_with_results.append(job_data)
        
        return UserHistory(
            jobs=jobs_with_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user history: {str(e)}"
        )

@router.get("/preferences")
async def get_user_preferences(
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Get current user's preferences
    
    Retrieves user-specific preferences like theme, language, notifications, etc.
    """
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Get user preferences
        prefs_result = supabase.table('user_preferences').select('*').eq('user_id', user_id).execute()
        
        if not prefs_result.data:
            # Create default preferences if they don't exist
            default_preferences = {
                'user_id': user_id,
                'theme': 'light',
                'language': 'en',
                'timezone': 'UTC',
                'email_notifications': True,
                'push_notifications': True,
                'marketing_emails': False,
                'auto_save': True,
                'default_privacy': 'private',
                'analytics_enabled': True,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            insert_result = supabase.table('user_preferences').insert(default_preferences).execute()
            return {
                "success": True,
                "message": "User preferences retrieved successfully",
                "data": insert_result.data[0]
            }
        
        return {
            "success": True,
            "message": "User preferences retrieved successfully",
            "data": prefs_result.data[0]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user preferences: {str(e)}"
        )

@router.put("/preferences")
async def update_user_preferences(
    preferences_update: Dict[str, Any],
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Update current user's preferences
    
    Updates user-specific preferences like theme, language, notifications, etc.
    """
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Check if preferences exist
        prefs_result = supabase.table('user_preferences').select('*').eq('user_id', user_id).execute()
        
        if not prefs_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User preferences not found. Please get preferences first to initialize them."
            )
        
        # Validate and filter allowed preference fields
        allowed_fields = {
            'theme', 'language', 'timezone', 'email_notifications', 
            'push_notifications', 'marketing_emails', 'auto_save', 
            'default_privacy', 'analytics_enabled'
        }
        
        update_data = {k: v for k, v in preferences_update.items() if k in allowed_fields}
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid preference fields provided for update"
            )
        
        # Add updated timestamp
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Update preferences
        updated_result = supabase.table('user_preferences').update(update_data).eq('user_id', user_id).execute()
        
        if not updated_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user preferences"
            )
        
        return {
            "success": True,
            "message": "User preferences updated successfully",
            "data": updated_result.data[0]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user preferences: {str(e)}"
        )

@router.put("/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    settings_update: UserSettingsUpdate,
    token_info: Dict[str, Any] = Depends(get_supabase_token_info)
):
    """Update user settings"""
    try:
        supabase = get_supabase_admin_client()
        auth_id = token_info.get('uid')
        
        if not auth_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token: missing uid"
            )
        
        # Get user from database
        user_result = supabase.table('users').select('id').eq('auth_id', auth_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_result.data[0]['id']
        
        # Prepare update data (only include non-None values)
        update_data = {}
        if settings_update.default_clip_duration is not None:
            update_data['default_clip_duration'] = settings_update.default_clip_duration
        if settings_update.preferred_quality is not None:
            update_data['preferred_quality'] = settings_update.preferred_quality
        if settings_update.auto_generate_hashtags is not None:
            update_data['auto_generate_hashtags'] = settings_update.auto_generate_hashtags
        if settings_update.notification_preferences is not None:
            update_data['notification_preferences'] = settings_update.notification_preferences
        if settings_update.export_settings is not None:
            update_data['export_settings'] = settings_update.export_settings
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields provided for update"
            )
        
        # Update user settings
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Try to update existing settings first
        existing_settings = supabase.table('user_settings').select('*').eq('user_id', user_id).execute()
        
        if existing_settings.data:
            # Update existing settings
            result = supabase.table('user_settings').update(update_data).eq('user_id', user_id).execute()
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update user settings"
                )
            updated_settings = result.data[0]
        else:
            # Create new settings record
            create_data = {
                'user_id': user_id,
                'default_clip_duration': settings_update.default_clip_duration or 30,
                'preferred_quality': settings_update.preferred_quality or 'high',
                'auto_generate_hashtags': settings_update.auto_generate_hashtags if settings_update.auto_generate_hashtags is not None else True,
                'notification_preferences': settings_update.notification_preferences or {},
                'export_settings': settings_update.export_settings or {},
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = supabase.table('user_settings').insert(create_data).execute()
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user settings"
                )
            updated_settings = result.data[0]
        
        return UserSettingsResponse(
            id=updated_settings['id'],
            user_id=updated_settings['user_id'],
            default_clip_duration=updated_settings['default_clip_duration'],
            preferred_quality=updated_settings['preferred_quality'],
            auto_generate_hashtags=updated_settings['auto_generate_hashtags'],
            notification_preferences=updated_settings['notification_preferences'],
            export_settings=updated_settings['export_settings'],
            created_at=updated_settings['created_at'],
            updated_at=updated_settings['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user settings: {str(e)}"
        )