import pytest
import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from api.main import app

class TestUserSettingsWorkflow:
    """Test complete user settings workflow integration."""
    
    @patch('api.services.supabase_service.supabase_service')
    def test_complete_settings_lifecycle_workflow(self, mock_supabase, client, auth_headers):
        """Test complete user settings lifecycle from creation to deletion."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        
        # Mock user authentication
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock default settings
        default_settings = {
            "user_id": "user-123",
            "video_quality": "high",
            "auto_generate_clips": True,
            "min_clip_score": 0.8,
            "max_clips_per_video": 10,
            "notification_preferences": {
                "email_notifications": True,
                "push_notifications": False,
                "processing_complete": True,
                "weekly_summary": True
            },
            "privacy_settings": {
                "public_profile": False,
                "share_analytics": False,
                "data_retention_days": 365
            },
            "processing_preferences": {
                "preferred_language": "en",
                "transcription_accuracy": "high",
                "content_filtering": True,
                "auto_thumbnail": True
            },
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        # Mock updated settings
        updated_settings = {
            **default_settings,
            "video_quality": "medium",
            "min_clip_score": 0.75,
            "max_clips_per_video": 15,
            "notification_preferences": {
                "email_notifications": False,
                "push_notifications": True,
                "processing_complete": True,
                "weekly_summary": False
            },
            "updated_at": "2024-03-15T10:30:00Z"
        }
        
        mock_supabase_instance.get_user_settings.return_value = default_settings
        mock_supabase_instance.update_user_settings.return_value = updated_settings
        mock_supabase_instance.create_default_settings.return_value = default_settings
        mock_supabase_instance.reset_user_settings.return_value = default_settings
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Get initial user settings (should return defaults)
            get_response = client.get(
                "/api/users/settings",
                headers=auth_headers
            )
            
            assert get_response.status_code == 200
            settings = get_response.json()
            assert settings["video_quality"] == "high"
            assert settings["auto_generate_clips"] is True
            assert settings["min_clip_score"] == 0.8
            assert settings["notification_preferences"]["email_notifications"] is True
            
            # Step 2: Update user settings
            update_response = client.put(
                "/api/users/settings",
                json={
                    "video_quality": "medium",
                    "min_clip_score": 0.75,
                    "max_clips_per_video": 15,
                    "notification_preferences": {
                        "email_notifications": False,
                        "push_notifications": True,
                        "processing_complete": True,
                        "weekly_summary": False
                    }
                },
                headers=auth_headers
            )
            
            assert update_response.status_code == 200
            updated = update_response.json()
            assert updated["video_quality"] == "medium"
            assert updated["min_clip_score"] == 0.75
            assert updated["max_clips_per_video"] == 15
            assert updated["notification_preferences"]["email_notifications"] is False
            assert updated["notification_preferences"]["push_notifications"] is True
            
            # Step 3: Get updated settings to verify persistence
            mock_supabase_instance.get_user_settings.return_value = updated_settings
            
            verify_response = client.get(
                "/api/users/settings",
                headers=auth_headers
            )
            
            assert verify_response.status_code == 200
            verified = verify_response.json()
            assert verified["video_quality"] == "medium"
            assert verified["min_clip_score"] == 0.75
            
            # Step 4: Reset settings to defaults
            reset_response = client.post(
                "/api/users/settings/reset",
                headers=auth_headers
            )
            
            assert reset_response.status_code == 200
            reset_data = reset_response.json()
            assert reset_data["message"] == "Settings reset to defaults"
            
            # Step 5: Verify settings were reset
            mock_supabase_instance.get_user_settings.return_value = default_settings
            
            final_response = client.get(
                "/api/users/settings",
                headers=auth_headers
            )
            
            assert final_response.status_code == 200
            final_settings = final_response.json()
            assert final_settings["video_quality"] == "high"
            assert final_settings["min_clip_score"] == 0.8
    
    @patch('api.services.supabase_service.supabase_service')
    def test_notification_preferences_workflow(self, mock_supabase, client, auth_headers):
        """Test notification preferences management workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock notification settings
        notification_settings = {
            "user_id": "user-123",
            "email_notifications": True,
            "push_notifications": False,
            "processing_complete": True,
            "weekly_summary": True,
            "monthly_report": False,
            "system_updates": True,
            "marketing_emails": False
        }
        
        mock_supabase_instance.get_notification_preferences.return_value = notification_settings
        mock_supabase_instance.update_notification_preferences.return_value = {
            **notification_settings,
            "push_notifications": True,
            "weekly_summary": False
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Get current notification preferences
            get_response = client.get(
                "/api/users/settings/notifications",
                headers=auth_headers
            )
            
            assert get_response.status_code == 200
            prefs = get_response.json()
            assert prefs["email_notifications"] is True
            assert prefs["push_notifications"] is False
            assert prefs["processing_complete"] is True
            
            # Step 2: Update specific notification preferences
            update_response = client.patch(
                "/api/users/settings/notifications",
                json={
                    "push_notifications": True,
                    "weekly_summary": False
                },
                headers=auth_headers
            )
            
            assert update_response.status_code == 200
            updated_prefs = update_response.json()
            assert updated_prefs["push_notifications"] is True
            assert updated_prefs["weekly_summary"] is False
            assert updated_prefs["email_notifications"] is True  # Should remain unchanged
    
    @patch('api.services.supabase_service.supabase_service')
    def test_privacy_settings_workflow(self, mock_supabase, client, auth_headers):
        """Test privacy settings management workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock privacy settings
        privacy_settings = {
            "user_id": "user-123",
            "public_profile": False,
            "share_analytics": False,
            "data_retention_days": 365,
            "allow_data_export": True,
            "third_party_sharing": False,
            "analytics_tracking": True
        }
        
        mock_supabase_instance.get_privacy_settings.return_value = privacy_settings
        mock_supabase_instance.update_privacy_settings.return_value = {
            **privacy_settings,
            "public_profile": True,
            "data_retention_days": 180
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Get current privacy settings
            get_response = client.get(
                "/api/users/settings/privacy",
                headers=auth_headers
            )
            
            assert get_response.status_code == 200
            privacy = get_response.json()
            assert privacy["public_profile"] is False
            assert privacy["share_analytics"] is False
            assert privacy["data_retention_days"] == 365
            
            # Step 2: Update privacy settings
            update_response = client.put(
                "/api/users/settings/privacy",
                json={
                    "public_profile": True,
                    "data_retention_days": 180
                },
                headers=auth_headers
            )
            
            assert update_response.status_code == 200
            updated_privacy = update_response.json()
            assert updated_privacy["public_profile"] is True
            assert updated_privacy["data_retention_days"] == 180
    
    @patch('api.services.supabase_service.supabase_service')
    def test_processing_preferences_workflow(self, mock_supabase, client, auth_headers):
        """Test processing preferences management workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock processing preferences
        processing_prefs = {
            "user_id": "user-123",
            "preferred_language": "en",
            "transcription_accuracy": "high",
            "content_filtering": True,
            "auto_thumbnail": True,
            "video_quality": "high",
            "audio_enhancement": False,
            "subtitle_generation": True
        }
        
        mock_supabase_instance.get_processing_preferences.return_value = processing_prefs
        mock_supabase_instance.update_processing_preferences.return_value = {
            **processing_prefs,
            "preferred_language": "es",
            "transcription_accuracy": "medium",
            "audio_enhancement": True
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Get current processing preferences
            get_response = client.get(
                "/api/users/settings/processing",
                headers=auth_headers
            )
            
            assert get_response.status_code == 200
            prefs = get_response.json()
            assert prefs["preferred_language"] == "en"
            assert prefs["transcription_accuracy"] == "high"
            assert prefs["audio_enhancement"] is False
            
            # Step 2: Update processing preferences
            update_response = client.put(
                "/api/users/settings/processing",
                json={
                    "preferred_language": "es",
                    "transcription_accuracy": "medium",
                    "audio_enhancement": True
                },
                headers=auth_headers
            )
            
            assert update_response.status_code == 200
            updated_prefs = update_response.json()
            assert updated_prefs["preferred_language"] == "es"
            assert updated_prefs["transcription_accuracy"] == "medium"
            assert updated_prefs["audio_enhancement"] is True
    
    @patch('api.services.supabase_service.supabase_service')
    def test_settings_validation_workflow(self, mock_supabase, client, auth_headers):
        """Test settings validation and error handling."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Test invalid video quality
            invalid_quality_response = client.put(
                "/api/users/settings",
                json={
                    "video_quality": "invalid_quality"
                },
                headers=auth_headers
            )
            assert invalid_quality_response.status_code == 422
            
            # Test invalid clip score range
            invalid_score_response = client.put(
                "/api/users/settings",
                json={
                    "min_clip_score": 1.5  # Should be between 0 and 1
                },
                headers=auth_headers
            )
            assert invalid_score_response.status_code == 422
            
            # Test invalid max clips (negative number)
            invalid_clips_response = client.put(
                "/api/users/settings",
                json={
                    "max_clips_per_video": -5
                },
                headers=auth_headers
            )
            assert invalid_clips_response.status_code == 422
            
            # Test invalid data retention days
            invalid_retention_response = client.put(
                "/api/users/settings/privacy",
                json={
                    "data_retention_days": 0  # Should be positive
                },
                headers=auth_headers
            )
            assert invalid_retention_response.status_code == 422
    
    @patch('api.services.supabase_service.supabase_service')
    def test_settings_export_import_workflow(self, mock_supabase, client, auth_headers):
        """Test settings export and import workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        
        # Mock complete settings for export
        complete_settings = {
            "user_id": "user-123",
            "video_quality": "high",
            "auto_generate_clips": True,
            "min_clip_score": 0.8,
            "max_clips_per_video": 10,
            "notification_preferences": {
                "email_notifications": True,
                "push_notifications": False,
                "processing_complete": True,
                "weekly_summary": True
            },
            "privacy_settings": {
                "public_profile": False,
                "share_analytics": False,
                "data_retention_days": 365
            },
            "processing_preferences": {
                "preferred_language": "en",
                "transcription_accuracy": "high",
                "content_filtering": True,
                "auto_thumbnail": True
            }
        }
        
        mock_supabase_instance.get_user_settings.return_value = complete_settings
        mock_supabase_instance.import_user_settings.return_value = complete_settings
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Export current settings
            export_response = client.get(
                "/api/users/settings/export",
                headers=auth_headers
            )
            
            assert export_response.status_code == 200
            exported_settings = export_response.json()
            assert exported_settings["video_quality"] == "high"
            assert "notification_preferences" in exported_settings
            assert "privacy_settings" in exported_settings
            assert "processing_preferences" in exported_settings
            
            # Step 2: Import settings (simulate restoring from backup)
            import_response = client.post(
                "/api/users/settings/import",
                json=exported_settings,
                headers=auth_headers
            )
            
            assert import_response.status_code == 200
            import_result = import_response.json()
            assert import_result["message"] == "Settings imported successfully"
            assert import_result["settings_count"] > 0

class TestUserSettingsErrorHandling:
    """Test user settings error handling scenarios."""
    
    def test_settings_unauthorized_access(self, client):
        """Test settings access without authentication."""
        # No auth headers provided
        response = client.get("/api/users/settings")
        assert response.status_code == 403
        
        # Invalid token
        response = client.get(
            "/api/users/settings",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401
    
    @patch('api.services.supabase_service.supabase_service')
    def test_settings_database_error(self, mock_supabase, client, auth_headers):
        """Test settings handling with database errors."""
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase_instance.get_user_settings.side_effect = Exception("Database connection failed")
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            response = client.get(
                "/api/users/settings",
                headers=auth_headers
            )
            
            assert response.status_code == 500
    
    @patch('api.services.supabase_service.supabase_service')
    def test_settings_partial_update_error(self, mock_supabase, client, auth_headers):
        """Test handling of partial update errors."""
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase_instance.update_user_settings.side_effect = Exception("Update failed")
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            response = client.put(
                "/api/users/settings",
                json={
                    "video_quality": "medium"
                },
                headers=auth_headers
            )
            
            assert response.status_code == 500
    
    @patch('api.services.supabase_service.supabase_service')
    def test_settings_import_validation_error(self, mock_supabase, client, auth_headers):
        """Test settings import with invalid data."""
        mock_supabase_instance = Mock()
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Import with invalid structure
            response = client.post(
                "/api/users/settings/import",
                json={
                    "invalid_field": "invalid_value",
                    "video_quality": "invalid_quality"
                },
                headers=auth_headers
            )
            
            assert response.status_code == 422