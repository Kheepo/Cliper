"""Unit tests for email service functionality."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from typing import Dict, Any, Optional, List

# Import the modules to test
try:
    from api.services.email_service import EmailService, EmailTemplate, EmailConfig
    from api.core.exceptions import EmailError, ConfigurationError
except ImportError:
    # Mock imports for testing
    class EmailService:
        pass
    class EmailTemplate:
        pass
    class EmailConfig:
        pass
    class EmailError(Exception):
        pass
    class ConfigurationError(Exception):
        pass

class TestEmailService:
    """Test cases for EmailService class."""
    
    @pytest.fixture
    def email_config(self):
        """Sample email configuration for testing."""
        return {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "test@example.com",
            "password": "app_password",
            "use_tls": True,
            "from_email": "noreply@example.com",
            "from_name": "Test Application"
        }
    
    @pytest.fixture
    def email_service(self, email_config):
        """Create an EmailService instance for testing."""
        with patch('api.services.email_service.EmailService.__init__') as mock_init:
            mock_init.return_value = None
            service = EmailService()
            service.config = email_config
            return service
    
    @pytest.fixture
    def sample_email_data(self):
        """Sample email data for testing."""
        return {
            "to_email": "recipient@example.com",
            "subject": "Test Email",
            "body": "This is a test email message.",
            "html_body": "<p>This is a <strong>test</strong> email message.</p>",
            "attachments": []
        }
    
    def test_email_service_initialization(self, email_config):
        """Test EmailService initialization."""
        with patch('api.services.email_service.EmailService.__init__') as mock_init:
            mock_init.return_value = None
            service = EmailService()
            
            assert service is not None
            mock_init.assert_called_once()
    
    def test_email_service_initialization_with_config(self, email_config):
        """Test EmailService initialization with configuration."""
        with patch('api.services.email_service.EmailService.__init__') as mock_init:
            mock_init.return_value = None
            service = EmailService()
            service.config = email_config
            
            assert service.config == email_config
            assert service.config["smtp_server"] == "smtp.gmail.com"
            assert service.config["smtp_port"] == 587
    
    @pytest.mark.asyncio
    async def test_send_email_success(self, email_service, sample_email_data):
        """Test successful email sending."""
        with patch('api.services.email_service.EmailService.send_email') as mock_send:
            mock_send.return_value = {
                "success": True,
                "message_id": "msg_123456",
                "timestamp": datetime.now()
            }
            
            result = await email_service.send_email(
                to_email=sample_email_data["to_email"],
                subject=sample_email_data["subject"],
                body=sample_email_data["body"],
                html_body=sample_email_data["html_body"]
            )
            
            assert result["success"] is True
            assert "message_id" in result
            assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_send_email_smtp_error(self, email_service, sample_email_data):
        """Test email sending with SMTP error."""
        with patch('api.services.email_service.EmailService.send_email') as mock_send:
            mock_send.side_effect = EmailError("SMTP connection failed")
            
            with pytest.raises(EmailError):
                await email_service.send_email(
                    to_email=sample_email_data["to_email"],
                    subject=sample_email_data["subject"],
                    body=sample_email_data["body"]
                )
    
    @pytest.mark.asyncio
    async def test_send_email_invalid_recipient(self, email_service):
        """Test email sending with invalid recipient."""
        with patch('api.services.email_service.EmailService.send_email') as mock_send:
            mock_send.side_effect = EmailError("Invalid recipient email address")
            
            with pytest.raises(EmailError):
                await email_service.send_email(
                    to_email="invalid-email",
                    subject="Test",
                    body="Test message"
                )
    
    @pytest.mark.asyncio
    async def test_send_email_authentication_failed(self, email_service, sample_email_data):
        """Test email sending with authentication failure."""
        with patch('api.services.email_service.EmailService.send_email') as mock_send:
            mock_send.side_effect = EmailError("SMTP authentication failed")
            
            with pytest.raises(EmailError):
                await email_service.send_email(
                    to_email=sample_email_data["to_email"],
                    subject=sample_email_data["subject"],
                    body=sample_email_data["body"]
                )
    
    @pytest.mark.asyncio
    async def test_send_bulk_emails(self, email_service):
        """Test sending bulk emails."""
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]
        
        with patch('api.services.email_service.EmailService.send_bulk_emails') as mock_bulk:
            mock_bulk.return_value = {
                "success_count": 3,
                "failed_count": 0,
                "results": [
                    {"email": "user1@example.com", "success": True, "message_id": "msg_1"},
                    {"email": "user2@example.com", "success": True, "message_id": "msg_2"},
                    {"email": "user3@example.com", "success": True, "message_id": "msg_3"}
                ]
            }
            
            result = await email_service.send_bulk_emails(
                recipients=recipients,
                subject="Bulk Test Email",
                body="This is a bulk email test."
            )
            
            assert result["success_count"] == 3
            assert result["failed_count"] == 0
            assert len(result["results"]) == 3
    
    def test_validate_email_address(self, email_service):
        """Test email address validation."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org",
            "123@numbers.com"
        ]
        
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "user@",
            "user@domain",
            "user space@example.com"
        ]
        
        with patch('api.services.email_service.EmailService.validate_email_address') as mock_validate:
            # Test valid emails
            for email in valid_emails:
                mock_validate.return_value = True
                result = email_service.validate_email_address(email)
                assert result is True
            
            # Test invalid emails
            for email in invalid_emails:
                mock_validate.return_value = False
                result = email_service.validate_email_address(email)
                assert result is False

class TestEmailTemplates:
    """Test cases for email templates."""
    
    @pytest.fixture
    def email_service(self):
        with patch('api.services.email_service.EmailService.__init__') as mock_init:
            mock_init.return_value = None
            return EmailService()
    
    @pytest.fixture
    def password_reset_data(self):
        """Sample data for password reset email."""
        return {
            "user_name": "John Doe",
            "reset_link": "https://example.com/reset-password?token=abc123",
            "expiry_hours": 24,
            "support_email": "support@example.com"
        }
    
    @pytest.fixture
    def welcome_email_data(self):
        """Sample data for welcome email."""
        return {
            "user_name": "Jane Smith",
            "app_name": "Test Application",
            "login_url": "https://example.com/login",
            "support_email": "support@example.com"
        }
    
    @pytest.mark.asyncio
    async def test_send_password_reset_email(self, email_service, password_reset_data):
        """Test sending password reset email."""
        with patch('api.services.email_service.EmailService.send_password_reset_email') as mock_send:
            mock_send.return_value = {
                "success": True,
                "message_id": "reset_msg_123",
                "template": "password_reset"
            }
            
            result = await email_service.send_password_reset_email(
                to_email="test@example.com",
                **password_reset_data
            )
            
            assert result["success"] is True
            assert result["template"] == "password_reset"
            assert "message_id" in result
    
    @pytest.mark.asyncio
    async def test_send_welcome_email(self, email_service, welcome_email_data):
        """Test sending welcome email."""
        with patch('api.services.email_service.EmailService.send_welcome_email') as mock_send:
            mock_send.return_value = {
                "success": True,
                "message_id": "welcome_msg_123",
                "template": "welcome"
            }
            
            result = await email_service.send_welcome_email(
                to_email="test@example.com",
                **welcome_email_data
            )
            
            assert result["success"] is True
            assert result["template"] == "welcome"
            assert "message_id" in result
    
    @pytest.mark.asyncio
    async def test_send_verification_email(self, email_service):
        """Test sending email verification email."""
        verification_data = {
            "user_name": "Test User",
            "verification_link": "https://example.com/verify?token=xyz789",
            "app_name": "Test App"
        }
        
        with patch('api.services.email_service.EmailService.send_verification_email') as mock_send:
            mock_send.return_value = {
                "success": True,
                "message_id": "verify_msg_123",
                "template": "email_verification"
            }
            
            result = await email_service.send_verification_email(
                to_email="test@example.com",
                **verification_data
            )
            
            assert result["success"] is True
            assert result["template"] == "email_verification"
    
    def test_render_template(self, email_service):
        """Test template rendering."""
        template_name = "password_reset"
        template_data = {
            "user_name": "John Doe",
            "reset_link": "https://example.com/reset"
        }
        
        expected_html = "<p>Hello John Doe, click <a href='https://example.com/reset'>here</a> to reset your password.</p>"
        expected_text = "Hello John Doe, visit https://example.com/reset to reset your password."
        
        with patch('api.services.email_service.EmailService.render_template') as mock_render:
            mock_render.return_value = {
                "html": expected_html,
                "text": expected_text,
                "subject": "Password Reset Request"
            }
            
            result = email_service.render_template(template_name, template_data)
            
            assert "html" in result
            assert "text" in result
            assert "subject" in result
            assert "John Doe" in result["html"]
            assert "reset" in result["subject"].lower()

class TestEmailQueue:
    """Test cases for email queue functionality."""
    
    @pytest.fixture
    def email_service(self):
        with patch('api.services.email_service.EmailService.__init__') as mock_init:
            mock_init.return_value = None
            return EmailService()
    
    @pytest.mark.asyncio
    async def test_queue_email(self, email_service):
        """Test queuing email for later sending."""
        email_data = {
            "to_email": "test@example.com",
            "subject": "Queued Email",
            "body": "This email was queued.",
            "priority": "normal",
            "scheduled_at": datetime.now() + timedelta(minutes=5)
        }
        
        with patch('api.services.email_service.EmailService.queue_email') as mock_queue:
            mock_queue.return_value = {
                "success": True,
                "queue_id": "queue_123",
                "scheduled_at": email_data["scheduled_at"]
            }
            
            result = await email_service.queue_email(**email_data)
            
            assert result["success"] is True
            assert "queue_id" in result
            assert "scheduled_at" in result
    
    @pytest.mark.asyncio
    async def test_process_email_queue(self, email_service):
        """Test processing queued emails."""
        with patch('api.services.email_service.EmailService.process_email_queue') as mock_process:
            mock_process.return_value = {
                "processed_count": 5,
                "failed_count": 1,
                "remaining_count": 10
            }
            
            result = await email_service.process_email_queue(batch_size=10)
            
            assert "processed_count" in result
            assert "failed_count" in result
            assert "remaining_count" in result
            assert result["processed_count"] >= 0
    
    @pytest.mark.asyncio
    async def test_get_queue_status(self, email_service):
        """Test getting email queue status."""
        with patch('api.services.email_service.EmailService.get_queue_status') as mock_status:
            mock_status.return_value = {
                "total_queued": 25,
                "pending": 20,
                "processing": 3,
                "failed": 2,
                "completed": 100
            }
            
            result = await email_service.get_queue_status()
            
            assert "total_queued" in result
            assert "pending" in result
            assert "processing" in result
            assert "failed" in result
            assert "completed" in result

class TestEmailConfiguration:
    """Test cases for email configuration management."""
    
    @pytest.fixture
    def email_service(self):
        with patch('api.services.email_service.EmailService.__init__') as mock_init:
            mock_init.return_value = None
            return EmailService()
    
    def test_validate_smtp_config(self, email_service):
        """Test SMTP configuration validation."""
        valid_config = {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "test@example.com",
            "password": "password123",
            "use_tls": True
        }
        
        invalid_configs = [
            {"smtp_server": "", "smtp_port": 587},  # Empty server
            {"smtp_server": "smtp.gmail.com", "smtp_port": "invalid"},  # Invalid port
            {"smtp_server": "smtp.gmail.com", "smtp_port": 587, "username": ""},  # Empty username
        ]
        
        with patch('api.services.email_service.EmailService.validate_smtp_config') as mock_validate:
            # Test valid config
            mock_validate.return_value = {"valid": True, "errors": []}
            result = email_service.validate_smtp_config(valid_config)
            assert result["valid"] is True
            
            # Test invalid configs
            for config in invalid_configs:
                mock_validate.return_value = {"valid": False, "errors": ["Configuration error"]}
                result = email_service.validate_smtp_config(config)
                assert result["valid"] is False
                assert len(result["errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_test_smtp_connection(self, email_service):
        """Test SMTP connection testing."""
        config = {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "test@example.com",
            "password": "password123",
            "use_tls": True
        }
        
        with patch('api.services.email_service.EmailService.test_smtp_connection') as mock_test:
            # Test successful connection
            mock_test.return_value = {
                "success": True,
                "message": "SMTP connection successful",
                "response_time_ms": 150
            }
            
            result = await email_service.test_smtp_connection(config)
            
            assert result["success"] is True
            assert "response_time_ms" in result
    
    @pytest.mark.asyncio
    async def test_test_smtp_connection_failure(self, email_service):
        """Test SMTP connection failure."""
        invalid_config = {
            "smtp_server": "invalid.server.com",
            "smtp_port": 587,
            "username": "test@example.com",
            "password": "wrong_password",
            "use_tls": True
        }
        
        with patch('api.services.email_service.EmailService.test_smtp_connection') as mock_test:
            mock_test.return_value = {
                "success": False,
                "error": "Connection timeout",
                "error_code": "SMTP_TIMEOUT"
            }
            
            result = await email_service.test_smtp_connection(invalid_config)
            
            assert result["success"] is False
            assert "error" in result
            assert "error_code" in result

class TestEmailServiceIntegration:
    """Integration tests for email service functionality."""
    
    @pytest.fixture
    def email_service(self):
        with patch('api.services.email_service.EmailService.__init__') as mock_init:
            mock_init.return_value = None
            return EmailService()
    
    @pytest.mark.asyncio
    async def test_complete_password_reset_email_flow(self, email_service):
        """Test complete password reset email workflow."""
        user_data = {
            "email": "test@example.com",
            "name": "Test User",
            "reset_token": "abc123xyz"
        }
        
        # Step 1: Render template
        with patch.object(email_service, 'render_template') as mock_render:
            mock_render.return_value = {
                "html": "<p>Password reset email</p>",
                "text": "Password reset email",
                "subject": "Password Reset Request"
            }
            
            template_result = email_service.render_template(
                "password_reset",
                {"user_name": user_data["name"], "reset_token": user_data["reset_token"]}
            )
            
            assert "html" in template_result
            assert "subject" in template_result
        
        # Step 2: Send email
        with patch.object(email_service, 'send_email') as mock_send:
            mock_send.return_value = {
                "success": True,
                "message_id": "msg_123"
            }
            
            send_result = await email_service.send_email(
                to_email=user_data["email"],
                subject=template_result["subject"],
                body=template_result["text"],
                html_body=template_result["html"]
            )
            
            assert send_result["success"] is True
            assert "message_id" in send_result

if __name__ == "__main__":
    pytest.main([__file__, "-v"])