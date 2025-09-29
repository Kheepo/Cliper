#!/usr/bin/env python3
"""
Security manager module for comprehensive security enhancements.
Provides input validation, file security checks, user permission verification, and rate limiting.
"""

import os
import re
import hashlib
import hmac
import secrets
import mimetypes
import magic
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
import time
import json
import base64
from urllib.parse import urlparse, quote, unquote
from ipaddress import ip_address, ip_network, AddressValueError

from fastapi import HTTPException, Request, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
import bleach
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.utils.structured_logger import get_logger, LogCategory
from api.database.models import User


class SecurityLevel(Enum):
    """Security level enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(Enum):
    """Threat type enumeration."""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    PATH_TRAVERSAL = "path_traversal"
    FILE_UPLOAD = "file_upload"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INPUT_VALIDATION = "input_validation"
    MALWARE = "malware"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class SecurityConfig:
    """Security configuration."""
    # Rate limiting
    rate_limit_requests_per_minute: int = 60
    rate_limit_requests_per_hour: int = 1000
    rate_limit_burst_size: int = 10
    
    # File upload security
    max_file_size_mb: int = 100
    allowed_file_extensions: Set[str] = field(default_factory=lambda: {
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
        '.txt', '.json', '.csv', '.xml'
    })
    allowed_mime_types: Set[str] = field(default_factory=lambda: {
        'video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo',
        'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
        'text/plain', 'application/json', 'text/csv', 'application/xml'
    })
    
    # Input validation
    max_string_length: int = 10000
    max_array_length: int = 1000
    max_object_depth: int = 10
    
    # Authentication
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    password_min_length: int = 8
    
    # IP filtering
    blocked_ip_ranges: List[str] = field(default_factory=list)
    allowed_ip_ranges: List[str] = field(default_factory=list)
    
    # Content filtering
    enable_content_filtering: bool = True
    blocked_keywords: Set[str] = field(default_factory=set)
    
    # Security headers
    enable_security_headers: bool = True
    csp_policy: str = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"


@dataclass
class SecurityThreat:
    """Security threat information."""
    threat_type: ThreatType
    severity: SecurityLevel
    description: str
    source_ip: Optional[str]
    user_id: Optional[str]
    request_path: Optional[str]
    payload: Optional[str]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitInfo:
    """Rate limit tracking information."""
    requests_count: int = 0
    first_request_time: datetime = field(default_factory=datetime.now)
    last_request_time: datetime = field(default_factory=datetime.now)
    blocked_until: Optional[datetime] = None


class InputValidator:
    """Input validation utilities."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = get_logger(__name__)
        
        # SQL injection patterns
        self.sql_patterns = [
            r"('|(\-\-)|(;)|(\||\|)|(\*|\*))",
            r"(union|select|insert|delete|update|drop|create|alter|exec|execute)",
            r"(script|javascript|vbscript|onload|onerror|onclick)",
            r"(\<|\>|\&|\#)"
        ]
        
        # XSS patterns
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>.*?</iframe>",
            r"<object[^>]*>.*?</object>",
            r"<embed[^>]*>.*?</embed>"
        ]
        
        # Path traversal patterns
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"\.\.%2f",
            r"\.\.%5c"
        ]
    
    def validate_string(self, value: str, field_name: str = "input") -> str:
        """Validate string input."""
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        
        if len(value) > self.config.max_string_length:
            raise ValueError(f"{field_name} exceeds maximum length of {self.config.max_string_length}")
        
        # Check for SQL injection
        for pattern in self.sql_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                self.logger.warning(
                    f"Potential SQL injection detected in {field_name}",
                    category=LogCategory.SECURITY,
                    field_name=field_name,
                    pattern=pattern,
                    tags=['sql_injection', 'security_threat']
                )
                raise ValueError(f"Invalid characters detected in {field_name}")
        
        # Check for XSS
        for pattern in self.xss_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                self.logger.warning(
                    f"Potential XSS detected in {field_name}",
                    category=LogCategory.SECURITY,
                    field_name=field_name,
                    pattern=pattern,
                    tags=['xss', 'security_threat']
                )
                raise ValueError(f"Invalid content detected in {field_name}")
        
        # Check for path traversal
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                self.logger.warning(
                    f"Potential path traversal detected in {field_name}",
                    category=LogCategory.SECURITY,
                    field_name=field_name,
                    pattern=pattern,
                    tags=['path_traversal', 'security_threat']
                )
                raise ValueError(f"Invalid path detected in {field_name}")
        
        # Check for blocked keywords
        if self.config.blocked_keywords:
            for keyword in self.config.blocked_keywords:
                if keyword.lower() in value.lower():
                    self.logger.warning(
                        f"Blocked keyword detected in {field_name}",
                        category=LogCategory.SECURITY,
                        field_name=field_name,
                        keyword=keyword,
                        tags=['blocked_content', 'security_threat']
                    )
                    raise ValueError(f"Content not allowed in {field_name}")
        
        return value
    
    def validate_email(self, email: str) -> str:
        """Validate email address."""
        email = self.validate_string(email, "email")
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")
        
        return email.lower()
    
    def validate_url(self, url: str) -> str:
        """Validate URL."""
        url = self.validate_string(url, "url")
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            
            # Check for allowed schemes
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Only HTTP and HTTPS URLs are allowed")
            
            return url
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
    
    def validate_json(self, data: Any, max_depth: Optional[int] = None) -> Any:
        """Validate JSON data structure."""
        max_depth = max_depth or self.config.max_object_depth
        
        def _validate_recursive(obj, depth=0):
            if depth > max_depth:
                raise ValueError(f"JSON object depth exceeds maximum of {max_depth}")
            
            if isinstance(obj, dict):
                if len(obj) > self.config.max_array_length:
                    raise ValueError(f"Object has too many keys (max: {self.config.max_array_length})")
                
                for key, value in obj.items():
                    if isinstance(key, str):
                        self.validate_string(key, "object_key")
                    _validate_recursive(value, depth + 1)
            
            elif isinstance(obj, list):
                if len(obj) > self.config.max_array_length:
                    raise ValueError(f"Array exceeds maximum length of {self.config.max_array_length}")
                
                for item in obj:
                    _validate_recursive(item, depth + 1)
            
            elif isinstance(obj, str):
                self.validate_string(obj, "string_value")
        
        _validate_recursive(data)
        return data
    
    def sanitize_html(self, html: str) -> str:
        """Sanitize HTML content."""
        # Allow only safe tags and attributes
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        allowed_attributes = {'*': ['class'], 'a': ['href', 'title'], 'img': ['src', 'alt']}
        
        return bleach.clean(html, tags=allowed_tags, attributes=allowed_attributes, strip=True)


class FileSecurityChecker:
    """File security validation."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = get_logger(__name__)
        
        # Malware signatures (simplified)
        self.malware_signatures = [
            b'\x4d\x5a\x90\x00',  # PE executable
            b'\x7f\x45\x4c\x46',  # ELF executable
            b'\xca\xfe\xba\xbe',  # Mach-O executable
            b'\xfe\xed\xfa\xce',  # Mach-O executable (reverse)
        ]
    
    async def validate_file(self, file: UploadFile) -> bool:
        """Validate uploaded file."""
        try:
            # Check file size
            if file.size and file.size > self.config.max_file_size_mb * 1024 * 1024:
                raise ValueError(f"File size exceeds maximum of {self.config.max_file_size_mb}MB")
            
            # Check file extension
            if file.filename:
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in self.config.allowed_file_extensions:
                    raise ValueError(f"File extension {file_ext} not allowed")
            
            # Read file content for validation
            content = await file.read()
            await file.seek(0)  # Reset file pointer
            
            # Check MIME type
            mime_type = magic.from_buffer(content, mime=True)
            if mime_type not in self.config.allowed_mime_types:
                self.logger.warning(
                    f"File MIME type {mime_type} not allowed",
                    category=LogCategory.SECURITY,
                    filename=file.filename,
                    mime_type=mime_type,
                    tags=['file_upload', 'security_threat']
                )
                raise ValueError(f"File type {mime_type} not allowed")
            
            # Check for malware signatures
            for signature in self.malware_signatures:
                if signature in content:
                    self.logger.critical(
                        "Potential malware detected in uploaded file",
                        category=LogCategory.SECURITY,
                        filename=file.filename,
                        tags=['malware', 'security_threat']
                    )
                    raise ValueError("File contains suspicious content")
            
            # Check for embedded scripts in images
            if mime_type.startswith('image/'):
                if b'<script' in content.lower() or b'javascript:' in content.lower():
                    self.logger.warning(
                        "Script content detected in image file",
                        category=LogCategory.SECURITY,
                        filename=file.filename,
                        tags=['xss', 'file_upload', 'security_threat']
                    )
                    raise ValueError("Image contains suspicious content")
            
            # Additional checks for video files
            if mime_type.startswith('video/'):
                # Check for reasonable file size vs duration ratio
                # This is a basic check - in production, you might use ffprobe
                if len(content) < 1000:  # Too small for a real video
                    raise ValueError("Video file appears to be invalid")
            
            return True
            
        except Exception as e:
            self.logger.error(
                f"File validation failed: {e}",
                category=LogCategory.SECURITY,
                filename=file.filename,
                error=str(e),
                tags=['file_validation', 'security_error']
            )
            raise
    
    def validate_file_path(self, file_path: str) -> str:
        """Validate file path for security."""
        # Normalize path
        normalized_path = os.path.normpath(file_path)
        
        # Check for path traversal
        if '..' in normalized_path or normalized_path.startswith('/'):
            raise ValueError("Invalid file path")
        
        # Ensure path is within allowed directory
        allowed_base = os.path.abspath('uploads')
        full_path = os.path.abspath(os.path.join(allowed_base, normalized_path))
        
        if not full_path.startswith(allowed_base):
            raise ValueError("File path outside allowed directory")
        
        return normalized_path


class RateLimiter:
    """Rate limiting implementation."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = get_logger(__name__)
        
        # In-memory storage for rate limiting
        # In production, use Redis or similar
        self._rate_limits: Dict[str, RateLimitInfo] = {}
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def _cleanup_old_entries(self):
        """Clean up old rate limit entries."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff_time = datetime.now() - timedelta(hours=1)
        keys_to_remove = []
        
        for key, info in self._rate_limits.items():
            if info.last_request_time < cutoff_time:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._rate_limits[key]
        
        self._last_cleanup = current_time
    
    def check_rate_limit(self, identifier: str, request_path: str = "") -> bool:
        """Check if request is within rate limits."""
        self._cleanup_old_entries()
        
        current_time = datetime.now()
        
        if identifier not in self._rate_limits:
            self._rate_limits[identifier] = RateLimitInfo(
                requests_count=1,
                first_request_time=current_time,
                last_request_time=current_time
            )
            return True
        
        info = self._rate_limits[identifier]
        
        # Check if currently blocked
        if info.blocked_until and current_time < info.blocked_until:
            self.logger.warning(
                f"Rate limit exceeded for {identifier}",
                category=LogCategory.SECURITY,
                identifier=identifier,
                request_path=request_path,
                blocked_until=info.blocked_until.isoformat(),
                tags=['rate_limit', 'security_threat']
            )
            return False
        
        # Reset block if expired
        if info.blocked_until and current_time >= info.blocked_until:
            info.blocked_until = None
            info.requests_count = 0
            info.first_request_time = current_time
        
        # Check minute-based rate limit
        minute_ago = current_time - timedelta(minutes=1)
        if info.last_request_time >= minute_ago:
            if info.requests_count >= self.config.rate_limit_requests_per_minute:
                # Block for 1 minute
                info.blocked_until = current_time + timedelta(minutes=1)
                self.logger.warning(
                    f"Rate limit exceeded (per minute) for {identifier}",
                    category=LogCategory.SECURITY,
                    identifier=identifier,
                    request_path=request_path,
                    requests_count=info.requests_count,
                    tags=['rate_limit', 'security_threat']
                )
                return False
        else:
            # Reset minute counter
            info.requests_count = 0
            info.first_request_time = current_time
        
        # Check hour-based rate limit
        hour_ago = current_time - timedelta(hours=1)
        if info.first_request_time >= hour_ago:
            if info.requests_count >= self.config.rate_limit_requests_per_hour:
                # Block for 1 hour
                info.blocked_until = current_time + timedelta(hours=1)
                self.logger.warning(
                    f"Rate limit exceeded (per hour) for {identifier}",
                    category=LogCategory.SECURITY,
                    identifier=identifier,
                    request_path=request_path,
                    requests_count=info.requests_count,
                    tags=['rate_limit', 'security_threat']
                )
                return False
        
        # Update counters
        info.requests_count += 1
        info.last_request_time = current_time
        
        return True
    
    def get_rate_limit_info(self, identifier: str) -> Optional[RateLimitInfo]:
        """Get rate limit information for identifier."""
        return self._rate_limits.get(identifier)


class IPFilter:
    """IP address filtering."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = get_logger(__name__)
        
        # Parse IP ranges
        self.blocked_networks = []
        self.allowed_networks = []
        
        for ip_range in config.blocked_ip_ranges:
            try:
                self.blocked_networks.append(ip_network(ip_range, strict=False))
            except AddressValueError:
                self.logger.warning(f"Invalid blocked IP range: {ip_range}", 
                                  category=LogCategory.SECURITY)
        
        for ip_range in config.allowed_ip_ranges:
            try:
                self.allowed_networks.append(ip_network(ip_range, strict=False))
            except AddressValueError:
                self.logger.warning(f"Invalid allowed IP range: {ip_range}", 
                                  category=LogCategory.SECURITY)
    
    def is_ip_allowed(self, ip_str: str) -> bool:
        """Check if IP address is allowed."""
        try:
            ip = ip_address(ip_str)
            
            # Check blocked networks first
            for network in self.blocked_networks:
                if ip in network:
                    self.logger.warning(
                        f"Blocked IP address: {ip_str}",
                        category=LogCategory.SECURITY,
                        ip_address=ip_str,
                        tags=['ip_filter', 'security_threat']
                    )
                    return False
            
            # If allowed networks are specified, check them
            if self.allowed_networks:
                for network in self.allowed_networks:
                    if ip in network:
                        return True
                
                # IP not in any allowed network
                self.logger.warning(
                    f"IP address not in allowed ranges: {ip_str}",
                    category=LogCategory.SECURITY,
                    ip_address=ip_str,
                    tags=['ip_filter', 'security_threat']
                )
                return False
            
            return True
            
        except AddressValueError:
            self.logger.warning(
                f"Invalid IP address: {ip_str}",
                category=LogCategory.SECURITY,
                ip_address=ip_str,
                tags=['ip_filter', 'security_error']
            )
            return False


class AuthenticationManager:
    """Authentication and authorization management."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        
        # Password hashing
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # JWT configuration
        self.jwt_secret = config.jwt_secret_key or self.settings.secret_key
        self.jwt_algorithm = config.jwt_algorithm
        
        # Security bearer
        self.security = HTTPBearer()
    
    def hash_password(self, password: str) -> str:
        """Hash password."""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password."""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def validate_password_strength(self, password: str) -> bool:
        """Validate password strength."""
        if len(password) < self.config.password_min_length:
            raise ValueError(f"Password must be at least {self.config.password_min_length} characters")
        
        # Check for at least one uppercase, lowercase, digit, and special character
        if not re.search(r'[A-Z]', password):
            raise ValueError("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            raise ValueError("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            raise ValueError("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValueError("Password must contain at least one special character")
        
        return True
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.config.jwt_expiration_minutes)
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, self.jwt_secret, algorithm=self.jwt_algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except JWTError as e:
            self.logger.warning(
                f"Invalid JWT token: {e}",
                category=LogCategory.SECURITY,
                tags=['authentication', 'security_threat']
            )
            raise HTTPException(status_code=401, detail="Invalid token")
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials, db: Session) -> User:
        """Get current authenticated user."""
        try:
            payload = self.verify_token(credentials.credentials)
            user_id = payload.get("sub")
            
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            user = db.query(User).filter(User.id == user_id).first()
            if user is None:
                raise HTTPException(status_code=401, detail="User not found")
            
            return user
            
        except Exception as e:
            self.logger.error(
                f"Authentication failed: {e}",
                category=LogCategory.SECURITY,
                error=str(e),
                tags=['authentication', 'security_error']
            )
            raise HTTPException(status_code=401, detail="Authentication failed")


class SecurityManager:
    """Main security manager."""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.input_validator = InputValidator(self.config)
        self.file_checker = FileSecurityChecker(self.config)
        self.rate_limiter = RateLimiter(self.config)
        self.ip_filter = IPFilter(self.config)
        self.auth_manager = AuthenticationManager(self.config)
        
        # Threat tracking
        self._threats: List[SecurityThreat] = []
        self._max_threats_history = 1000
    
    def log_threat(self, threat: SecurityThreat):
        """Log security threat."""
        self._threats.append(threat)
        if len(self._threats) > self._max_threats_history:
            self._threats.pop(0)
        
        # Log threat
        log_level = {
            SecurityLevel.LOW: 'info',
            SecurityLevel.MEDIUM: 'warning',
            SecurityLevel.HIGH: 'error',
            SecurityLevel.CRITICAL: 'critical'
        }[threat.severity]
        
        getattr(self.logger, log_level)(
            f"Security threat detected: {threat.description}",
            category=LogCategory.SECURITY,
            threat_type=threat.threat_type.value,
            severity=threat.severity.value,
            source_ip=threat.source_ip,
            user_id=threat.user_id,
            request_path=threat.request_path,
            tags=['security_threat', threat.threat_type.value]
        )