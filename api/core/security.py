#!/usr/bin/env python3
"""
Comprehensive security module for production environments.
Handles input validation, file security checks, user permission verification, and rate limiting.
"""

import asyncio
import hashlib
import hmac
import secrets
import time
import re
import mimetypes
import magic
from typing import Dict, Any, Optional, List, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import ipaddress
from urllib.parse import urlparse
import bleach
from email_validator import validate_email, EmailNotValidError
from passlib.context import CryptContext
from passlib.hash import bcrypt
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from functools import wraps
from collections import defaultdict, deque
from redis import Redis

from fastapi import HTTPException
from .config import get_settings
from .logging_config import get_logger
from ..services.redis_service import get_redis
from ..database.models import User
from sqlalchemy.orm import Session


class SecurityLevel(Enum):
    """Security level enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(Enum):
    """Threat type enumeration."""
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    FILE_UPLOAD = "file_upload"
    RATE_LIMIT = "rate_limit"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    MALICIOUS_FILE = "malicious_file"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class ActionType(Enum):
    """Action type enumeration for permissions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class SecurityEvent:
    """Security event information."""
    event_type: ThreatType
    severity: SecurityLevel
    source_ip: str
    user_id: Optional[str]
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    blocked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_limit: int = 0
    window_size_seconds: int = 60
    enabled: bool = True


@dataclass
class FileSecurityConfig:
    """File security configuration."""
    allowed_extensions: Set[str]
    allowed_mime_types: Set[str]
    max_file_size_mb: int
    scan_for_malware: bool = True
    check_file_headers: bool = True
    quarantine_suspicious: bool = True


class InputValidator:
    """Comprehensive input validation."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Common regex patterns
        self.patterns = {
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'phone': re.compile(r'^\+?1?\d{9,15}$'),
            'alphanumeric': re.compile(r'^[a-zA-Z0-9]+$'),
            'username': re.compile(r'^[a-zA-Z0-9_-]{3,30}$'),
            'password': re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'),
            'url': re.compile(r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'),
            'uuid': re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.I),
            'sql_injection': re.compile(r"(union|select|insert|update|delete|drop|create|alter|exec|execute|script|javascript|vbscript|onload|onerror|onclick)", re.I),
            'xss': re.compile(r'<script[^>]*>.*?</script>|javascript:|vbscript:|onload=|onerror=|onclick=', re.I)
        }
        
        # Dangerous file extensions
        self.dangerous_extensions = {
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
            '.jar', '.app', '.deb', '.pkg', '.dmg', '.iso', '.msi', '.dll',
            '.so', '.dylib', '.php', '.asp', '.aspx', '.jsp', '.py', '.rb',
            '.pl', '.sh', '.ps1', '.psm1'
        }
        
        # Safe MIME types for uploads
        self.safe_mime_types = {
            'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
            'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo',
            'audio/mpeg', 'audio/wav', 'audio/ogg',
            'text/plain', 'text/csv',
            'application/pdf', 'application/json',
            'application/zip', 'application/x-zip-compressed'
        }
    
    def validate_email(self, email: str) -> Tuple[bool, str]:
        """Validate email address."""
        try:
            if not email or len(email) > 254:
                return False, "Email too long or empty"
            
            # Basic pattern check
            if not self.patterns['email'].match(email):
                return False, "Invalid email format"
            
            # Use email-validator for comprehensive validation
            validated_email = validate_email(email)
            return True, validated_email.email
            
        except EmailNotValidError as e:
            return False, str(e)
        except Exception as e:
            self.logger.error(f"Email validation error: {e}")
            return False, "Email validation failed"
    
    def validate_password(self, password: str) -> Tuple[bool, List[str]]:
        """Validate password strength."""
        errors = []
        
        if not password:
            errors.append("Password is required")
            return False, errors
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if len(password) > 128:
            errors.append("Password must be less than 128 characters")
        
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if not re.search(r'[@$!%*?&]', password):
            errors.append("Password must contain at least one special character (@$!%*?&)")
        
        # Check for common patterns
        common_patterns = ['123456', 'password', 'qwerty', 'abc123', 'admin']
        if any(pattern in password.lower() for pattern in common_patterns):
            errors.append("Password contains common patterns")
        
        return len(errors) == 0, errors
    
    def validate_username(self, username: str) -> Tuple[bool, str]:
        """Validate username."""
        if not username:
            return False, "Username is required"
        
        if len(username) < 3 or len(username) > 30:
            return False, "Username must be between 3 and 30 characters"
        
        if not self.patterns['username'].match(username):
            return False, "Username can only contain letters, numbers, hyphens, and underscores"
        
        # Check for reserved usernames
        reserved = {'admin', 'root', 'system', 'api', 'www', 'mail', 'ftp'}
        if username.lower() in reserved:
            return False, "Username is reserved"
        
        return True, username
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate URL."""
        if not url:
            return False, "URL is required"
        
        try:
            parsed = urlparse(url)
            
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format"
            
            if parsed.scheme not in ['http', 'https']:
                return False, "URL must use HTTP or HTTPS"
            
            # Check for suspicious patterns
            if any(pattern in url.lower() for pattern in ['javascript:', 'data:', 'vbscript:']):
                return False, "URL contains suspicious protocol"
            
            return True, url
            
        except Exception as e:
            return False, f"URL validation failed: {e}"
    
    def sanitize_html(self, content: str, allowed_tags: List[str] = None) -> str:
        """Sanitize HTML content to prevent XSS."""
        if not content:
            return ""
        
        # Default allowed tags for basic formatting
        if allowed_tags is None:
            allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        
        # Allowed attributes
        allowed_attributes = {
            '*': ['class'],
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'width', 'height']
        }
        
        return bleach.clean(
            content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
    
    def detect_sql_injection(self, input_string: str) -> bool:
        """Detect potential SQL injection attempts."""
        if not input_string:
            return False
        
        # Check for SQL injection patterns
        if self.patterns['sql_injection'].search(input_string):
            return True
        
        # Check for common SQL injection indicators
        indicators = [
            "'", '"', ';', '--', '/*', '*/', 'xp_', 'sp_',
            'union all', 'union select', 'drop table', 'drop database'
        ]
        
        input_lower = input_string.lower()
        return any(indicator in input_lower for indicator in indicators)
    
    def detect_xss(self, input_string: str) -> bool:
        """Detect potential XSS attempts."""
        if not input_string:
            return False
        
        return bool(self.patterns['xss'].search(input_string))
    
    def validate_file_upload(self, filename: str, content: bytes, 
                           config: FileSecurityConfig) -> Tuple[bool, List[str]]:
        """Validate file upload security."""
        errors = []
        
        if not filename:
            errors.append("Filename is required")
            return False, errors
        
        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext in self.dangerous_extensions:
            errors.append(f"File extension {file_ext} is not allowed")
        
        if config.allowed_extensions and file_ext not in config.allowed_extensions:
            errors.append(f"File extension {file_ext} is not in allowed list")
        
        # Check file size
        if len(content) > config.max_file_size_mb * 1024 * 1024:
            errors.append(f"File size exceeds {config.max_file_size_mb}MB limit")
        
        # Check MIME type
        try:
            mime_type = magic.from_buffer(content, mime=True)
            if config.allowed_mime_types and mime_type not in config.allowed_mime_types:
                errors.append(f"MIME type {mime_type} is not allowed")
            
            # Verify MIME type matches extension
            expected_mime = mimetypes.guess_type(filename)[0]
            if expected_mime and mime_type != expected_mime:
                errors.append("File extension doesn't match content type")
                
        except Exception as e:
            errors.append(f"Could not determine file type: {e}")
        
        # Check for malicious content
        if config.scan_for_malware:
            if self._scan_for_malware(content):
                errors.append("File contains suspicious content")
        
        return len(errors) == 0, errors
    
    def _scan_for_malware(self, content: bytes) -> bool:
        """Basic malware scanning."""
        # Check for suspicious patterns in file content
        suspicious_patterns = [
            b'<script', b'javascript:', b'vbscript:', b'onload=',
            b'eval(', b'exec(', b'system(', b'shell_exec(',
            b'<?php', b'<%', b'<script', b'</script>'
        ]
        
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in suspicious_patterns)


class RateLimiter:
    """Advanced rate limiting with multiple strategies."""
    
    def __init__(self, redis_client: Redis = None):
        self.logger = get_logger(__name__)
        self.redis = redis_client or get_redis()
        self.local_cache = defaultdict(lambda: defaultdict(deque))
        self.rules = {}
        
        # Default rate limit rules
        self.default_rules = {
            'api_general': RateLimitRule(60, 1000, 10000, 10),
            'api_auth': RateLimitRule(5, 50, 200, 2),
            'api_upload': RateLimitRule(10, 100, 500, 3),
            'api_admin': RateLimitRule(30, 300, 1000, 5)
        }
    
    def set_rule(self, key: str, rule: RateLimitRule):
        """Set rate limiting rule."""
        self.rules[key] = rule
        self.logger.info(f"Rate limit rule set for {key}", rule=rule.__dict__)
    
    def get_rule(self, key: str) -> RateLimitRule:
        """Get rate limiting rule."""
        return self.rules.get(key, self.default_rules.get(key, self.default_rules['api_general']))
    
    async def check_rate_limit(self, key: str, identifier: str, 
                              rule_key: str = 'api_general') -> Tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limits."""
        rule = self.get_rule(rule_key)
        if not rule.enabled:
            return True, {}
        
        current_time = time.time()
        cache_key = f"rate_limit:{key}:{identifier}"
        
        try:
            # Use Redis for distributed rate limiting
            return await self._check_redis_rate_limit(cache_key, rule, current_time)
        except Exception as e:
            self.logger.error(f"Redis rate limit check failed: {e}")
            # Fallback to local cache
            return self._check_local_rate_limit(cache_key, rule, current_time)
    
    async def _check_redis_rate_limit(self, cache_key: str, rule: RateLimitRule, 
                                     current_time: float) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit using Redis."""
        pipe = self.redis.pipeline()
        
        # Check different time windows
        minute_key = f"{cache_key}:minute:{int(current_time // 60)}"
        hour_key = f"{cache_key}:hour:{int(current_time // 3600)}"
        day_key = f"{cache_key}:day:{int(current_time // 86400)}"
        
        # Get current counts
        pipe.get(minute_key)
        pipe.get(hour_key)
        pipe.get(day_key)
        
        results = await pipe.execute()
        
        minute_count = int(results[0] or 0)
        hour_count = int(results[1] or 0)
        day_count = int(results[2] or 0)
        
        # Check limits
        if minute_count >= rule.requests_per_minute:
            return False, {
                'error': 'Rate limit exceeded',
                'limit_type': 'per_minute',
                'current': minute_count,
                'limit': rule.requests_per_minute,
                'reset_time': (int(current_time // 60) + 1) * 60
            }
        
        if hour_count >= rule.requests_per_hour:
            return False, {
                'error': 'Rate limit exceeded',
                'limit_type': 'per_hour',
                'current': hour_count,
                'limit': rule.requests_per_hour,
                'reset_time': (int(current_time // 3600) + 1) * 3600
            }
        
        if day_count >= rule.requests_per_day:
            return False, {
                'error': 'Rate limit exceeded',
                'limit_type': 'per_day',
                'current': day_count,
                'limit': rule.requests_per_day,
                'reset_time': (int(current_time // 86400) + 1) * 86400
            }
        
        # Increment counters
        pipe = self.redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 120)  # Keep for 2 minutes
        pipe.incr(hour_key)
        pipe.expire(hour_key, 7200)  # Keep for 2 hours
        pipe.incr(day_key)
        pipe.expire(day_key, 172800)  # Keep for 2 days
        
        await pipe.execute()
        
        return True, {
            'remaining_minute': rule.requests_per_minute - minute_count - 1,
            'remaining_hour': rule.requests_per_hour - hour_count - 1,
            'remaining_day': rule.requests_per_day - day_count - 1
        }
    
    def _check_local_rate_limit(self, cache_key: str, rule: RateLimitRule, 
                               current_time: float) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit using local cache (fallback)."""
        # Clean old entries
        self._cleanup_local_cache(cache_key, current_time)
        
        requests = self.local_cache[cache_key]['requests']
        
        # Count requests in different time windows
        minute_count = sum(1 for t in requests if current_time - t <= 60)
        hour_count = sum(1 for t in requests if current_time - t <= 3600)
        day_count = sum(1 for t in requests if current_time - t <= 86400)
        
        # Check limits
        if minute_count >= rule.requests_per_minute:
            return False, {
                'error': 'Rate limit exceeded',
                'limit_type': 'per_minute',
                'current': minute_count,
                'limit': rule.requests_per_minute
            }
        
        if hour_count >= rule.requests_per_hour:
            return False, {
                'error': 'Rate limit exceeded',
                'limit_type': 'per_hour',
                'current': hour_count,
                'limit': rule.requests_per_hour
            }
        
        if day_count >= rule.requests_per_day:
            return False, {
                'error': 'Rate limit exceeded',
                'limit_type': 'per_day',
                'current': day_count,
                'limit': rule.requests_per_day
            }
        
        # Add current request
        requests.append(current_time)
        
        return True, {
            'remaining_minute': rule.requests_per_minute - minute_count - 1,
            'remaining_hour': rule.requests_per_hour - hour_count - 1,
            'remaining_day': rule.requests_per_day - day_count - 1
        }
    
    def _cleanup_local_cache(self, cache_key: str, current_time: float):
        """Clean up old entries from local cache."""
        requests = self.local_cache[cache_key]['requests']
        
        # Remove requests older than 1 day
        cutoff_time = current_time - 86400
        while requests and requests[0] < cutoff_time:
            requests.popleft()


class PermissionManager:
    """User permission management."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        
        # Role-based permissions
        self.role_permissions = {
            'admin': {ActionType.READ, ActionType.WRITE, ActionType.DELETE, ActionType.EXECUTE, ActionType.ADMIN},
            'moderator': {ActionType.READ, ActionType.WRITE, ActionType.DELETE},
            'user': {ActionType.READ, ActionType.WRITE},
            'free': {ActionType.READ},  # Free users can read their own data
            'viewer': {ActionType.READ}
        }
    
    def check_permission(self, user, resource: str, action: ActionType) -> bool:
        """Check if user has permission for action on resource."""
        if not user:
            return False
        
        # Handle both User objects and dict objects from auth middleware
        if isinstance(user, dict):
            user_role = user.get('role', 'free')
            user_id = user.get('id') or user.get('uid')
            is_superuser = user.get('is_superuser', False) or user_role == 'admin'
        else:
            # User model object
            user_role = user.role
            user_id = user.id
            is_superuser = user.is_superuser
        
        # Super admin bypass
        if is_superuser:
            return True
        
        # Check role-based permissions
        user_permissions = self.role_permissions.get(user_role, set())
        if action not in user_permissions:
            return False
        
        # Check resource-specific permissions
        return self._check_resource_permission(user, resource, action, user_id, user_role)
    
    def _check_resource_permission(self, user, resource: str, action: ActionType, user_id: str = None, user_role: str = None) -> bool:
        """Check resource-specific permissions."""
        # Handle both User objects and dict objects
        if isinstance(user, dict):
            actual_user_id = user_id or user.get('id') or user.get('uid')
            actual_user_role = user_role or user.get('role', 'free')
        else:
            actual_user_id = user_id or user.id
            actual_user_role = user_role or user.role
        
        # Implement resource-specific logic here
        # For example, users can only modify their own clips
        if resource.startswith('clip:'):
            clip_id = resource.split(':')[1]
            # Check if user owns the clip or has admin rights
            return actual_user_role in ['admin', 'moderator'] or self._user_owns_clip(actual_user_id, clip_id)
        
        # Analytics permissions - allow users to view their own analytics
        if resource.startswith('analytics:'):
            # Users can read their own analytics, admins can read all
            if action == ActionType.READ:
                return actual_user_role in ['admin', 'moderator', 'user']
            # Only admins can write/delete analytics
            return actual_user_role in ['admin', 'moderator']
        
        return True
    
    def _user_owns_clip(self, user_id: str, clip_id: str) -> bool:
        """Check if user owns the clip."""
        # This would query the database to check ownership
        # Placeholder implementation
        return True


class SecurityManager:
    """Comprehensive security management."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.redis = get_redis()
        
        # Initialize components
        self.validator = InputValidator()
        self.rate_limiter = RateLimiter(self.redis)
        self.permission_manager = PermissionManager()
        
        # Security configuration
        self.password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Security monitoring
        self.security_events = deque(maxlen=10000)
        self.blocked_ips = set()
        self.suspicious_ips = defaultdict(int)
        
        # JWT configuration
        self.jwt_secret = self.settings.secret_key
        self.jwt_algorithm = "HS256"
        self.jwt_expiration = timedelta(hours=24)
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key."""
        key_file = Path("encryption.key")
        
        if key_file.exists():
            return key_file.read_bytes()
        
        # Generate new key
        key = Fernet.generate_key()
        key_file.write_bytes(key)
        key_file.chmod(0o600)  # Restrict permissions
        
        return key
    
    def hash_password(self, password: str) -> str:
        """Hash password securely."""
        return self.password_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return self.password_context.verify(plain_password, hashed_password)
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
    
    def generate_token(self, user_id: str, additional_claims: Dict[str, Any] = None) -> str:
        """Generate JWT token."""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + self.jwt_expiration,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(32)  # JWT ID for revocation
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Check if token is revoked
            jti = payload.get("jti")
            if jti and self._is_token_revoked(jti):
                return False, None
            
            return True, payload
            
        except jwt.ExpiredSignatureError:
            return False, None
        except jwt.InvalidTokenError:
            return False, None
    
    def revoke_token(self, token: str):
        """Revoke JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm], options={"verify_exp": False})
            jti = payload.get("jti")
            
            if jti:
                # Store revoked token ID in Redis with expiration
                exp = payload.get("exp", time.time() + 86400)
                ttl = max(0, int(exp - time.time()))
                self.redis.setex(f"revoked_token:{jti}", ttl, "1")
                
        except Exception as e:
            self.logger.error(f"Token revocation failed: {e}")
    
    def _is_token_revoked(self, jti: str) -> bool:
        """Check if token is revoked."""
        return bool(self.redis.get(f"revoked_token:{jti}"))
    
    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token."""
        timestamp = str(int(time.time()))
        message = f"{session_id}:{timestamp}"
        signature = hmac.new(
            self.jwt_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{timestamp}:{signature}"
    
    def verify_csrf_token(self, token: str, session_id: str, max_age: int = 3600) -> bool:
        """Verify CSRF token."""
        try:
            timestamp_str, signature = token.split(":", 1)
            timestamp = int(timestamp_str)
            
            # Check token age
            if time.time() - timestamp > max_age:
                return False
            
            # Verify signature
            message = f"{session_id}:{timestamp_str}"
            expected_signature = hmac.new(
                self.jwt_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except (ValueError, TypeError):
            return False
    
    def log_security_event(self, event: SecurityEvent):
        """Log security event."""
        self.security_events.append(event)
        
        # Log to structured logger
        self.logger.warning(
            f"Security event: {event.event_type.value}",
            event_type=event.event_type.value,
            severity=event.severity.value,
            source_ip=event.source_ip,
            user_id=event.user_id,
            description=event.description,
            blocked=event.blocked,
            metadata=event.metadata
        )
        
        # Handle high-severity events
        if event.severity in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
            self._handle_high_severity_event(event)
    
    def _handle_high_severity_event(self, event: SecurityEvent):
        """Handle high-severity security events."""
        # Increment suspicious activity counter
        self.suspicious_ips[event.source_ip] += 1
        
        # Auto-block IPs with too many suspicious activities
        if self.suspicious_ips[event.source_ip] >= 5:
            self.block_ip(event.source_ip, "Automatic block due to suspicious activity")
        
        # Send alerts for critical events
        if event.severity == SecurityLevel.CRITICAL:
            self._send_security_alert(event)
    
    def block_ip(self, ip_address: str, reason: str, duration_hours: int = 24):
        """Block IP address."""
        self.blocked_ips.add(ip_address)
        
        # Store in Redis with expiration
        self.redis.setex(
            f"blocked_ip:{ip_address}",
            duration_hours * 3600,
            reason
        )
        
        self.logger.warning(
            f"IP blocked: {ip_address}",
            ip_address=ip_address,
            reason=reason,
            duration_hours=duration_hours
        )
    
    def is_ip_blocked(self, ip_address: str) -> Tuple[bool, Optional[str]]:
        """Check if IP is blocked."""
        reason = self.redis.get(f"blocked_ip:{ip_address}")
        if reason:
            return True, reason.decode() if isinstance(reason, bytes) else reason
        
        return ip_address in self.blocked_ips, None
    
    def unblock_ip(self, ip_address: str):
        """Unblock IP address."""
        self.blocked_ips.discard(ip_address)
        self.redis.delete(f"blocked_ip:{ip_address}")
        
        self.logger.info(f"IP unblocked: {ip_address}", ip_address=ip_address)
    
    def _send_security_alert(self, event: SecurityEvent):
        """Send security alert (placeholder for notification system)."""
        # This would integrate with your notification system
        # (email, Slack, PagerDuty, etc.)
        self.logger.critical(
            f"SECURITY ALERT: {event.description}",
            event_type=event.event_type.value,
            source_ip=event.source_ip,
            user_id=event.user_id,
            metadata=event.metadata
        )
    
    def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get security summary for the last N hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_events = [
            event for event in self.security_events
            if event.timestamp >= cutoff_time
        ]
        
        # Count events by type and severity
        event_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for event in recent_events:
            event_counts[event.event_type.value] += 1
            severity_counts[event.severity.value] += 1
        
        return {
            "total_events": len(recent_events),
            "event_types": dict(event_counts),
            "severity_levels": dict(severity_counts),
            "blocked_ips": len(self.blocked_ips),
            "suspicious_ips": len(self.suspicious_ips),
            "time_range_hours": hours
        }


# Security decorators
def require_permission(resource: str, action: ActionType):
    """Decorator to require specific permission."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from request context or deps
            user = kwargs.get('current_user')
            
            # If not found in kwargs, check deps (for analytics endpoints)
            if not user:
                deps = kwargs.get('deps')
                if deps and isinstance(deps, dict):
                    user = deps.get('current_user')
            
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            security_manager = get_security_manager()
            if not security_manager.permission_manager.check_permission(user, resource, action):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(rule_key: str = 'api_general'):
    """Decorator for rate limiting."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request info
            request = kwargs.get('request')
            if not request:
                return await func(*args, **kwargs)
            
            client_ip = request.client.host
            user_id = getattr(request.state, 'user_id', None)
            identifier = user_id or client_ip
            
            security_manager = get_security_manager()
            
            # Check if IP is blocked
            is_blocked, block_reason = security_manager.is_ip_blocked(client_ip)
            if is_blocked:
                raise HTTPException(
                    status_code=429,
                    detail=f"IP blocked: {block_reason}"
                )
            
            # Check rate limit
            allowed, info = await security_manager.rate_limiter.check_rate_limit(
                func.__name__, identifier, rule_key
            )
            
            if not allowed:
                # Log security event
                event = SecurityEvent(
                    event_type=ThreatType.RATE_LIMIT,
                    severity=SecurityLevel.MEDIUM,
                    source_ip=client_ip,
                    user_id=user_id,
                    description=f"Rate limit exceeded for {func.__name__}",
                    blocked=True,
                    metadata=info
                )
                security_manager.log_security_event(event)
                
                raise HTTPException(
                    status_code=429,
                    detail=info.get('error', 'Rate limit exceeded'),
                    headers={
                        'X-RateLimit-Limit': str(info.get('limit', 0)),
                        'X-RateLimit-Remaining': '0',
                        'X-RateLimit-Reset': str(info.get('reset_time', 0))
                    }
                )
            
            # Add rate limit headers
            response = await func(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Remaining-Minute'] = str(info.get('remaining_minute', 0))
                response.headers['X-RateLimit-Remaining-Hour'] = str(info.get('remaining_hour', 0))
                response.headers['X-RateLimit-Remaining-Day'] = str(info.get('remaining_day', 0))
            
            return response
        return wrapper
    return decorator


def validate_input(**validation_rules):
    """Decorator for input validation."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            security_manager = get_security_manager()
            validator = security_manager.validator
            
            # Validate inputs based on rules
            for field_name, rule in validation_rules.items():
                value = kwargs.get(field_name)
                if value is None:
                    continue
                
                if rule == 'email':
                    valid, result = validator.validate_email(value)
                    if not valid:
                        raise HTTPException(status_code=400, detail=f"Invalid email: {result}")
                
                elif rule == 'password':
                    valid, errors = validator.validate_password(value)
                    if not valid:
                        raise HTTPException(status_code=400, detail=f"Invalid password: {', '.join(errors)}")
                
                elif rule == 'username':
                    valid, result = validator.validate_username(value)
                    if not valid:
                        raise HTTPException(status_code=400, detail=f"Invalid username: {result}")
                
                elif rule == 'url':
                    valid, result = validator.validate_url(value)
                    if not valid:
                        raise HTTPException(status_code=400, detail=f"Invalid URL: {result}")
                
                elif rule == 'no_sql_injection':
                    if validator.detect_sql_injection(str(value)):
                        # Log security event
                        request = kwargs.get('request')
                        client_ip = request.client.host if request else 'unknown'
                        
                        event = SecurityEvent(
                            event_type=ThreatType.SQL_INJECTION,
                            severity=SecurityLevel.HIGH,
                            source_ip=client_ip,
                            user_id=getattr(request.state, 'user_id', None) if request else None,
                            description=f"SQL injection attempt in field {field_name}",
                            blocked=True,
                            metadata={'field': field_name, 'value': str(value)[:100]}
                        )
                        security_manager.log_security_event(event)
                        
                        raise HTTPException(status_code=400, detail="Invalid input detected")
                
                elif rule == 'no_xss':
                    if validator.detect_xss(str(value)):
                        # Log security event
                        request = kwargs.get('request')
                        client_ip = request.client.host if request else 'unknown'
                        
                        event = SecurityEvent(
                            event_type=ThreatType.XSS,
                            severity=SecurityLevel.HIGH,
                            source_ip=client_ip,
                            user_id=getattr(request.state, 'user_id', None) if request else None,
                            description=f"XSS attempt in field {field_name}",
                            blocked=True,
                            metadata={'field': field_name, 'value': str(value)[:100]}
                        )
                        security_manager.log_security_event(event)
                        
                        raise HTTPException(status_code=400, detail="Invalid input detected")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Global security manager instance
_security_manager = None


def get_security_manager() -> SecurityManager:
    """Get global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


# Security middleware for FastAPI
class SecurityMiddleware:
    """Security middleware for FastAPI."""
    
    def __init__(self, app):
        self.app = app
        self.security_manager = get_security_manager()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract client IP
        client_ip = None
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"x-forwarded-for":
                client_ip = header_value.decode().split(",")[0].strip()
                break
            elif header_name == b"x-real-ip":
                client_ip = header_value.decode().strip()
                break
        
        if not client_ip:
            client_ip = scope.get("client", [None])[0]
        
        # Check if IP is blocked
        if client_ip:
            is_blocked, block_reason = self.security_manager.is_ip_blocked(client_ip)
            if is_blocked:
                response = {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", b"45"]
                    ]
                }
                await send(response)
                
                body = {"type": "http.response.body", "body": b'{"detail": "IP address blocked"}'}
                await send(body)
                return
        
        await self.app(scope, receive, send)


# File security configurations
IMAGE_SECURITY_CONFIG = FileSecurityConfig(
    allowed_extensions={'.jpg', '.jpeg', '.png', '.gif', '.webp'},
    allowed_mime_types={'image/jpeg', 'image/png', 'image/gif', 'image/webp'},
    max_file_size_mb=10,
    scan_for_malware=True,
    check_file_headers=True
)

VIDEO_SECURITY_CONFIG = FileSecurityConfig(
    allowed_extensions={'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'},
    allowed_mime_types={'video/mp4', 'video/avi', 'video/quicktime', 'video/x-ms-wmv', 'video/x-flv', 'video/webm'},
    max_file_size_mb=500,
    scan_for_malware=True,
    check_file_headers=True
)

DOCUMENT_SECURITY_CONFIG = FileSecurityConfig(
    allowed_extensions={'.pdf', '.txt', '.doc', '.docx', '.csv'},
    allowed_mime_types={'application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/csv'},
    max_file_size_mb=50,
    scan_for_malware=True,
    check_file_headers=True
)


# Export main components
__all__ = [
    'SecurityManager',
    'InputValidator',
    'RateLimiter',
    'PermissionManager',
    'SecurityEvent',
    'SecurityLevel',
    'ThreatType',
    'ActionType',
    'RateLimitRule',
    'FileSecurityConfig',
    'get_security_manager',
    'require_permission',
    'rate_limit',
    'validate_input',
    'SecurityMiddleware',
    'IMAGE_SECURITY_CONFIG',
    'VIDEO_SECURITY_CONFIG',
    'DOCUMENT_SECURITY_CONFIG'
]