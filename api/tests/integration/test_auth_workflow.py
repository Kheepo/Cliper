import pytest
import time
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from api.main import app

class TestAuthenticationWorkflow:
    """Test complete authentication workflow integration."""
    
    @patch('api.services.supabase_service.supabase_service')
    def test_complete_user_registration_workflow(self, mock_supabase, client):
        """Test complete user registration and verification workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.create_user.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "email_confirmed_at": None,
            "created_at": "2024-01-01T00:00:00Z"
        }
        mock_supabase_instance.send_verification_email.return_value = True
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Register new user
            register_response = client.post(
                "/api/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "SecurePassword123!",
                    "confirm_password": "SecurePassword123!"
                }
            )
            
            assert register_response.status_code == 201
            register_data = register_response.json()
            assert register_data["email"] == "test@example.com"
            assert register_data["email_confirmed"] is False
            
            # Step 2: Verify email verification was sent
            mock_supabase_instance.send_verification_email.assert_called_once_with(
                "test@example.com"
            )
            
            # Step 3: Simulate email verification
            mock_supabase_instance.verify_email.return_value = {
                "id": "user-123",
                "email": "test@example.com",
                "email_confirmed_at": "2024-01-01T00:05:00Z"
            }
            
            verify_response = client.post(
                "/api/auth/verify-email",
                json={"token": "verification-token-123"}
            )
            
            assert verify_response.status_code == 200
            verify_data = verify_response.json()
            assert verify_data["email_confirmed"] is True
    
    @patch('api.services.supabase_service.supabase_service')
    def test_login_and_token_refresh_workflow(self, mock_supabase, client):
        """Test login and token refresh workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.authenticate_user.return_value = {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600,
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "email_confirmed_at": "2024-01-01T00:00:00Z"
            }
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Login
            login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "SecurePassword123!"
                }
            )
            
            assert login_response.status_code == 200
            login_data = login_response.json()
            assert "access_token" in login_data
            assert "refresh_token" in login_data
            assert login_data["user"]["email"] == "test@example.com"
            
            access_token = login_data["access_token"]
            refresh_token = login_data["refresh_token"]
            
            # Step 2: Access protected endpoint
            mock_supabase_instance.get_user_from_token.return_value = {
                "id": "user-123",
                "email": "test@example.com"
            }
            
            protected_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            assert protected_response.status_code == 200
            user_data = protected_response.json()
            assert user_data["email"] == "test@example.com"
            
            # Step 3: Refresh token
            mock_supabase_instance.refresh_token.return_value = {
                "access_token": "new-access-token-456",
                "refresh_token": "new-refresh-token-456",
                "expires_in": 3600
            }
            
            refresh_response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": refresh_token}
            )
            
            assert refresh_response.status_code == 200
            refresh_data = refresh_response.json()
            assert refresh_data["access_token"] != access_token
            assert "new-access-token-456" in refresh_data["access_token"]
    
    @patch('api.services.supabase_service.supabase_service')
    def test_password_reset_workflow(self, mock_supabase, client):
        """Test complete password reset workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.send_password_reset.return_value = True
        mock_supabase_instance.reset_password.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "updated_at": "2024-01-01T00:10:00Z"
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Request password reset
            reset_request_response = client.post(
                "/api/auth/forgot-password",
                json={"email": "test@example.com"}
            )
            
            assert reset_request_response.status_code == 200
            assert reset_request_response.json()["message"] == "Password reset email sent"
            
            # Step 2: Reset password with token
            reset_response = client.post(
                "/api/auth/reset-password",
                json={
                    "token": "reset-token-123",
                    "new_password": "NewSecurePassword456!",
                    "confirm_password": "NewSecurePassword456!"
                }
            )
            
            assert reset_response.status_code == 200
            assert reset_response.json()["message"] == "Password reset successfully"
            
            # Step 3: Verify old password no longer works
            mock_supabase_instance.authenticate_user.side_effect = Exception("Invalid credentials")
            
            old_login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "SecurePassword123!"  # Old password
                }
            )
            
            assert old_login_response.status_code == 401
            
            # Step 4: Verify new password works
            mock_supabase_instance.authenticate_user.side_effect = None
            mock_supabase_instance.authenticate_user.return_value = {
                "access_token": "new-access-token",
                "user": {"id": "user-123", "email": "test@example.com"}
            }
            
            new_login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "NewSecurePassword456!"  # New password
                }
            )
            
            assert new_login_response.status_code == 200
    
    @patch('api.services.supabase_service.supabase_service')
    def test_session_management_workflow(self, mock_supabase, client):
        """Test session management and logout workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.authenticate_user.return_value = {
            "access_token": "session-token-123",
            "refresh_token": "refresh-token-123",
            "user": {"id": "user-123", "email": "test@example.com"}
        }
        mock_supabase_instance.get_user_from_token.return_value = {
            "id": "user-123",
            "email": "test@example.com"
        }
        mock_supabase_instance.logout_user.return_value = True
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Login to create session
            login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "SecurePassword123!"
                }
            )
            
            assert login_response.status_code == 200
            access_token = login_response.json()["access_token"]
            
            # Step 2: Verify session is active
            me_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            assert me_response.status_code == 200
            
            # Step 3: Logout
            logout_response = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            assert logout_response.status_code == 200
            assert logout_response.json()["message"] == "Logged out successfully"
            
            # Step 4: Verify session is invalidated
            mock_supabase_instance.get_user_from_token.side_effect = Exception("Invalid token")
            
            invalid_session_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            assert invalid_session_response.status_code == 401

class TestAuthenticationSecurity:
    """Test authentication security workflows."""
    
    def test_brute_force_protection_workflow(self, client):
        """Test brute force protection workflow."""
        # Attempt multiple failed logins
        failed_attempts = []
        for i in range(10):
            response = client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": f"wrong-password-{i}"
                }
            )
            failed_attempts.append(response.status_code)
            time.sleep(0.1)  # Small delay between attempts
        
        # Should have rate limiting or account lockout
        rate_limited = [status for status in failed_attempts if status == 429]
        unauthorized = [status for status in failed_attempts if status == 401]
        
        # Should have both unauthorized and rate limited responses
        assert len(unauthorized) > 0
        assert len(rate_limited) > 0 or len(unauthorized) < 10  # Either rate limited or locked out
    
    @patch('api.services.supabase_service.supabase_service')
    def test_token_expiration_workflow(self, mock_supabase, client):
        """Test token expiration and renewal workflow."""
        # Mock Supabase service
        mock_supabase_instance = Mock()
        mock_supabase_instance.authenticate_user.return_value = {
            "access_token": "short-lived-token",
            "refresh_token": "refresh-token-123",
            "expires_in": 1,  # Very short expiration for testing
            "user": {"id": "user-123", "email": "test@example.com"}
        }
        mock_supabase.return_value = mock_supabase_instance
        
        with patch('api.main.supabase_service', mock_supabase_instance):
            # Step 1: Login with short-lived token
            login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "SecurePassword123!"
                }
            )
            
            assert login_response.status_code == 200
            access_token = login_response.json()["access_token"]
            refresh_token = login_response.json()["refresh_token"]
            
            # Step 2: Use token immediately (should work)
            mock_supabase_instance.get_user_from_token.return_value = {
                "id": "user-123",
                "email": "test@example.com"
            }
            
            immediate_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            assert immediate_response.status_code == 200
            
            # Step 3: Wait for token to expire
            time.sleep(2)
            
            # Step 4: Use expired token (should fail)
            mock_supabase_instance.get_user_from_token.side_effect = Exception("Token expired")
            
            expired_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            assert expired_response.status_code == 401
            
            # Step 5: Refresh token
            mock_supabase_instance.refresh_token.return_value = {
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600
            }
            
            refresh_response = client.post(
                "/api/auth/refresh",
                json={"refresh_token": refresh_token}
            )
            
            assert refresh_response.status_code == 200
            new_access_token = refresh_response.json()["access_token"]
            
            # Step 6: Use new token (should work)
            mock_supabase_instance.get_user_from_token.side_effect = None
            mock_supabase_instance.get_user_from_token.return_value = {
                "id": "user-123",
                "email": "test@example.com"
            }
            
            new_token_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {new_access_token}"}
            )
            
            assert new_token_response.status_code == 200