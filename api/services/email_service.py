"""Email service for sending emails and managing email templates."""

import os
import smtplib
import asyncio
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import logging
import re
from jinja2 import Environment, FileSystemLoader, Template
import aiosmtplib
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

from api.core.exceptions import EmailError, ConfigurationError
from api.core.config import get_settings

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
settings = get_settings()

class EmailPriority(Enum):
    """Email priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

@dataclass
class EmailConfig:
    """Email configuration."""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False
    from_email: str = ""
    from_name: str = ""
    timeout: int = 30

@dataclass
class EmailTemplate:
    """Email template data."""
    name: str
    subject: str
    html_content: str
    text_content: str
    variables: List[str]

class EmailService:
    """Service for sending emails and managing templates."""
    
    def __init__(self, config: Optional[EmailConfig] = None):
        """Initialize email service."""
        self.config = config or self._load_config_from_env()
        self.template_env = self._setup_template_environment()
        self._templates = self._load_templates()
        
    @property
    def configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(
            self.config.smtp_server and
            self.config.smtp_port and
            self.config.username and
            self.config.password and
            self.config.from_email
        )
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """Get email service configuration status."""
        return {
            'configured': self.configured,
            'smtp_server': self.config.smtp_server,
            'smtp_port': self.config.smtp_port,
            'from_email': self.config.from_email,
            'from_name': self.config.from_name,
            'username_configured': bool(self.config.username),
            'password_configured': bool(self.config.password)
        }
        
    def _load_config_from_env(self) -> EmailConfig:
        """Load email configuration from environment variables."""
        return EmailConfig(
            smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            username=os.getenv('SMTP_USERNAME', ''),
            password=os.getenv('SMTP_PASSWORD', ''),
            use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            use_ssl=os.getenv('SMTP_USE_SSL', 'false').lower() == 'true',
            from_email=os.getenv('FROM_EMAIL', ''),
            from_name=os.getenv('FROM_NAME', 'Cliper App'),
            timeout=int(os.getenv('SMTP_TIMEOUT', '30'))
        )
    
    def _setup_template_environment(self) -> Environment:
        """Setup Jinja2 template environment."""
        template_dir = Path(__file__).parent.parent / 'templates' / 'email'
        if template_dir.exists():
            return Environment(loader=FileSystemLoader(str(template_dir)))
        else:
            # Create in-memory templates if directory doesn't exist
            return Environment(loader=FileSystemLoader('/'))
    
    def _load_templates(self) -> Dict[str, EmailTemplate]:
        """Load email templates."""
        templates = {}
        
        # Password reset template
        templates['password_reset'] = EmailTemplate(
            name='password_reset',
            subject='Password Reset Request - {{ app_name }}',
            html_content='''
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Password Reset Request</h2>
                    <p>Hello {{ user_name }},</p>
                    <p>We received a request to reset your password for your {{ app_name }} account.</p>
                    <p>Click the button below to reset your password:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{ reset_link }}" style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
                    </div>
                    <p>This link will expire in {{ expiry_hours }} hours.</p>
                    <p>If you didn't request this password reset, please ignore this email or contact support if you have concerns.</p>
                    <p>Best regards,<br>The {{ app_name }} Team</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    <p style="font-size: 12px; color: #666;">If you're having trouble clicking the button, copy and paste this URL into your browser: {{ reset_link }}</p>
                </div>
            </body>
            </html>
            ''',
            text_content='''
            Password Reset Request
            
            Hello {{ user_name }},
            
            We received a request to reset your password for your {{ app_name }} account.
            
            Visit this link to reset your password:
            {{ reset_link }}
            
            This link will expire in {{ expiry_hours }} hours.
            
            If you didn't request this password reset, please ignore this email.
            
            Best regards,
            The {{ app_name }} Team
            ''',
            variables=['user_name', 'app_name', 'reset_link', 'expiry_hours']
        )
        
        # Welcome email template
        templates['welcome'] = EmailTemplate(
            name='welcome',
            subject='Welcome to {{ app_name }}!',
            html_content='''
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Welcome to {{ app_name }}!</h2>
                    <p>Hello {{ user_name }},</p>
                    <p>Welcome to {{ app_name }}! We're excited to have you on board.</p>
                    <p>You can now start using our platform to create amazing video clips.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{ login_url }}" style="background-color: #27ae60; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Get Started</a>
                    </div>
                    <p>If you have any questions, feel free to contact our support team at {{ support_email }}.</p>
                    <p>Best regards,<br>The {{ app_name }} Team</p>
                </div>
            </body>
            </html>
            ''',
            text_content='''
            Welcome to {{ app_name }}!
            
            Hello {{ user_name }},
            
            Welcome to {{ app_name }}! We're excited to have you on board.
            
            You can now start using our platform to create amazing video clips.
            
            Visit: {{ login_url }}
            
            If you have any questions, contact us at {{ support_email }}.
            
            Best regards,
            The {{ app_name }} Team
            ''',
            variables=['user_name', 'app_name', 'login_url', 'support_email']
        )
        
        # Email verification template
        templates['email_verification'] = EmailTemplate(
            name='email_verification',
            subject='Verify your email address - {{ app_name }}',
            html_content='''
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Verify Your Email Address</h2>
                    <p>Hello {{ user_name }},</p>
                    <p>Thank you for signing up for {{ app_name }}! Please verify your email address to complete your registration.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{ verification_link }}" style="background-color: #e74c3c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Verify Email</a>
                    </div>
                    <p>This verification link will expire in 24 hours.</p>
                    <p>If you didn't create an account with us, please ignore this email.</p>
                    <p>Best regards,<br>The {{ app_name }} Team</p>
                </div>
            </body>
            </html>
            ''',
            text_content='''
            Verify Your Email Address
            
            Hello {{ user_name }},
            
            Thank you for signing up for {{ app_name }}! Please verify your email address to complete your registration.
            
            Visit this link to verify: {{ verification_link }}
            
            This verification link will expire in 24 hours.
            
            If you didn't create an account with us, please ignore this email.
            
            Best regards,
            The {{ app_name }} Team
            ''',
            variables=['user_name', 'app_name', 'verification_link']
        )
        
        return templates
    
    def validate_email_address(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def render_template(self, template_name: str, data: Dict[str, Any]) -> Dict[str, str]:
        """Render email template with data."""
        if template_name not in self._templates:
            raise EmailError(f"Template '{template_name}' not found")
        
        template = self._templates[template_name]
        
        try:
            # Render subject
            subject_template = Template(template.subject)
            subject = subject_template.render(**data)
            
            # Render HTML content
            html_template = Template(template.html_content)
            html = html_template.render(**data)
            
            # Render text content
            text_template = Template(template.text_content)
            text = text_template.render(**data)
            
            return {
                'subject': subject,
                'html': html,
                'text': text
            }
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {str(e)}")
            raise EmailError(f"Failed to render template: {str(e)}")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        priority: EmailPriority = EmailPriority.NORMAL
    ) -> Dict[str, Any]:
        """Send email."""
        if not self.validate_email_address(to_email):
            raise EmailError(f"Invalid email address: {to_email}")
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.config.from_name} <{self.config.from_email}>"
            msg['To'] = to_email
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            
            # Add priority header
            if priority == EmailPriority.HIGH:
                msg['X-Priority'] = '2'
            elif priority == EmailPriority.URGENT:
                msg['X-Priority'] = '1'
            
            # Add text part
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    self._add_attachment(msg, attachment)
            
            # Send email
            await self._send_message(msg, to_email)
            
            message_id = msg.get('Message-ID', f"msg_{datetime.now().timestamp()}")
            
            logger.info(f"Email sent successfully to {to_email}")
            return {
                'success': True,
                'message_id': message_id,
                'timestamp': datetime.now(),
                'to_email': to_email
            }
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            raise EmailError(f"Failed to send email: {str(e)}")
    
    async def _send_message(self, msg: MIMEMultipart, to_email: str):
        """Send email message using SMTP."""
        # Check if we're in development mode and SMTP is not properly configured
        development_mode = os.getenv('DEVELOPMENT_MODE', 'False').lower() == 'true'
        
        if development_mode and not self.configured:
            # In development mode with invalid SMTP, log the email instead of failing
            logger.info(f"[DEVELOPMENT MODE] Email would be sent to: {to_email}")
            logger.info(f"[DEVELOPMENT MODE] Subject: {msg.get('Subject', 'No Subject')}")
            logger.info(f"[DEVELOPMENT MODE] From: {msg.get('From', 'No Sender')}")
            logger.info(f"[DEVELOPMENT MODE] Email content logged instead of sent due to invalid SMTP configuration")
            return
        
        try:
            if self.config.use_ssl:
                # Use SSL connection
                await aiosmtplib.send(
                    msg,
                    hostname=self.config.smtp_server,
                    port=self.config.smtp_port,
                    username=self.config.username,
                    password=self.config.password,
                    use_tls=False,
                    start_tls=False,
                    timeout=self.config.timeout
                )
            else:
                # Use TLS connection
                await aiosmtplib.send(
                    msg,
                    hostname=self.config.smtp_server,
                    port=self.config.smtp_port,
                    username=self.config.username,
                    password=self.config.password,
                    use_tls=self.config.use_tls,
                    start_tls=self.config.use_tls,
                    timeout=self.config.timeout
                )
        except Exception as e:
            # In development mode, log the error but don't fail completely
            if development_mode:
                logger.warning(f"[DEVELOPMENT MODE] SMTP error (email logged instead): {str(e)}")
                logger.info(f"[DEVELOPMENT MODE] Email would be sent to: {to_email}")
                logger.info(f"[DEVELOPMENT MODE] Subject: {msg.get('Subject', 'No Subject')}")
                return
            else:
                raise EmailError(f"SMTP error: {str(e)}")
    
    def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Add attachment to email message."""
        try:
            filename = attachment.get('filename', 'attachment')
            content = attachment.get('content', b'')
            content_type = attachment.get('content_type', 'application/octet-stream')
            
            part = MIMEBase(*content_type.split('/'))
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            msg.attach(part)
        except Exception as e:
            logger.error(f"Failed to add attachment {attachment.get('filename', 'unknown')}: {str(e)}")
    
    async def async_send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_link: str,
        expiry_hours: int = 24,
        app_name: str = "Cliper"
    ) -> Dict[str, Any]:
        """Send password reset email."""
        template_data = {
            'user_name': user_name,
            'reset_link': reset_link,
            'expiry_hours': expiry_hours,
            'app_name': app_name
        }
        
        rendered = self.render_template('password_reset', template_data)
        
        result = await self.send_email(
            to_email=to_email,
            subject=rendered['subject'],
            body=rendered['text'],
            html_body=rendered['html'],
            priority=EmailPriority.HIGH
        )
        
        result['template'] = 'password_reset'
        return result
    
    def send_password_reset_email_sync(self, to_email: str, reset_token: str, user_name: str) -> bool:
        """Send password reset email (sync version)."""
        try:
            reset_link = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={reset_token}"
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.async_send_password_reset_email(
                    to_email=to_email,
                    user_name=user_name,
                    reset_link=reset_link
                )
            )
            loop.close()
            return result.get('success', False)
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            return False
    
    def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """Send welcome email (sync version)."""
        try:
            login_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/login"
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.async_send_welcome_email(
                    to_email=to_email,
                    user_name=user_name,
                    login_url=login_url
                )
            )
            loop.close()
            return result.get('success', False)
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")
            return False
    
    async def async_send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        login_url: str,
        app_name: str = "Cliper",
        support_email: str = "support@cliper.app"
    ) -> Dict[str, Any]:
        """Send welcome email."""
        template_data = {
            'user_name': user_name,
            'login_url': login_url,
            'app_name': app_name,
            'support_email': support_email
        }
        
        rendered = self.render_template('welcome', template_data)
        
        result = await self.send_email(
            to_email=to_email,
            subject=rendered['subject'],
            body=rendered['text'],
            html_body=rendered['html']
        )
        
        result['template'] = 'welcome'
        return result
    
    async def send_verification_email(
        self,
        to_email: str,
        user_name: str,
        verification_link: str,
        app_name: str = "Cliper"
    ) -> Dict[str, Any]:
        """Send email verification email."""
        template_data = {
            'user_name': user_name,
            'verification_link': verification_link,
            'app_name': app_name
        }
        
        rendered = self.render_template('email_verification', template_data)
        
        result = await self.send_email(
            to_email=to_email,
            subject=rendered['subject'],
            body=rendered['text'],
            html_body=rendered['html'],
            priority=EmailPriority.HIGH
        )
        
        result['template'] = 'email_verification'
        return result
    
    async def send_bulk_emails(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """Send bulk emails."""
        results = []
        success_count = 0
        failed_count = 0
        
        # Process in batches to avoid overwhelming SMTP server
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            batch_tasks = []
            
            for email in batch:
                task = self.send_email(
                    to_email=email,
                    subject=subject,
                    body=body,
                    html_body=html_body
                )
                batch_tasks.append(task)
            
            # Execute batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for email, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results.append({
                        'email': email,
                        'success': False,
                        'error': str(result)
                    })
                    failed_count += 1
                else:
                    results.append({
                        'email': email,
                        'success': True,
                        'message_id': result.get('message_id')
                    })
                    success_count += 1
            
            # Small delay between batches
            if i + batch_size < len(recipients):
                await asyncio.sleep(1)
        
        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'total_count': len(recipients),
            'results': results
        }
    
    async def queue_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        priority: EmailPriority = EmailPriority.NORMAL,
        scheduled_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Queue email for later sending."""
        # This is a simplified implementation
        # In production, you'd use a proper queue like Celery or Redis Queue
        queue_id = f"queue_{datetime.now().timestamp()}"
        
        # For now, just send immediately if no schedule time
        if not scheduled_at or scheduled_at <= datetime.now():
            result = await self.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                html_body=html_body,
                priority=priority
            )
            return {
                'success': True,
                'queue_id': queue_id,
                'sent_immediately': True,
                'message_id': result.get('message_id')
            }
        
        return {
            'success': True,
            'queue_id': queue_id,
            'scheduled_at': scheduled_at,
            'sent_immediately': False
        }
    
    async def process_email_queue(self, batch_size: int = 10) -> Dict[str, Any]:
        """Process queued emails."""
        # Simplified implementation
        return {
            'processed_count': 0,
            'failed_count': 0,
            'remaining_count': 0
        }
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get email queue status."""
        # Simplified implementation
        return {
            'total_queued': 0,
            'pending': 0,
            'processing': 0,
            'failed': 0,
            'completed': 0
        }
    
    def validate_smtp_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SMTP configuration."""
        errors = []
        
        required_fields = ['smtp_server', 'smtp_port', 'username', 'password']
        for field in required_fields:
            if not config.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate port
        try:
            port = int(config.get('smtp_port', 0))
            if port <= 0 or port > 65535:
                errors.append("Invalid SMTP port")
        except (ValueError, TypeError):
            errors.append("SMTP port must be a valid integer")
        
        # Validate email format
        username = config.get('username', '')
        if username and not self.validate_email_address(username):
            errors.append("Username must be a valid email address")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    async def test_smtp_connection(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test SMTP connection."""
        test_config = config or self.config.__dict__
        
        try:
            start_time = datetime.now()
            
            # Test connection
            if test_config.get('use_ssl', False):
                server = smtplib.SMTP_SSL(
                    test_config['smtp_server'],
                    test_config['smtp_port'],
                    timeout=test_config.get('timeout', 30)
                )
            else:
                server = smtplib.SMTP(
                    test_config['smtp_server'],
                    test_config['smtp_port'],
                    timeout=test_config.get('timeout', 30)
                )
                
                if test_config.get('use_tls', True):
                    server.starttls()
            
            # Test authentication
            server.login(test_config['username'], test_config['password'])
            server.quit()
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000
            
            return {
                'success': True,
                'message': 'SMTP connection successful',
                'response_time_ms': round(response_time, 2)
            }
            
        except Exception as e:
            error_msg = str(e)
            error_code = 'SMTP_ERROR'
            
            if 'timeout' in error_msg.lower():
                error_code = 'SMTP_TIMEOUT'
            elif 'authentication' in error_msg.lower() or 'login' in error_msg.lower():
                error_code = 'SMTP_AUTH_FAILED'
            elif 'connection' in error_msg.lower():
                error_code = 'SMTP_CONNECTION_FAILED'
            
            return {
                'success': False,
                'error': error_msg,
                'error_code': error_code
            }

# Note: Create EmailService instances as needed rather than using a global instance
# to avoid initialization issues during module import