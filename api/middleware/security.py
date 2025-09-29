from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis
import hashlib
import hmac
import time
import re
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, validator
import bleach
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Rate limiting configuration
redis_client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",
    default_limits=["1000/hour", "100/minute"]
)

class SecurityConfig:
    """Security configuration settings"""
    
    # Rate limiting
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_STORAGE = "redis://localhost:6379"
    
    # HTTPS enforcement
    FORCE_HTTPS = False  # Disabled for local development
    HSTS_MAX_AGE = 31536000  # 1 year
    
    # Input validation
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB for video uploads
    ALLOWED_CONTENT_TYPES = [
        "application/json",
        "multipart/form-data",
        "application/x-www-form-urlencoded",
        "video/mp4",
        "video/avi",
        "video/mov",
        "video/wmv",
        "audio/mp3",
        "audio/wav",
        "audio/aac"
    ]
    
    # Security headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:; "
            "connect-src 'self' https:; "
            "media-src 'self' https:; "
            "object-src 'none'; "
            "base-uri 'self';"
        ),
        "Permissions-Policy": (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=()"
        )
    }
    
    # Input sanitization
    ALLOWED_HTML_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']
    ALLOWED_HTML_ATTRIBUTES = {}

class InputValidator:
    """Input validation and sanitization utilities"""
    
    @staticmethod
    def sanitize_html(content: str) -> str:
        """Sanitize HTML content to prevent XSS"""
        return bleach.clean(
            content,
            tags=SecurityConfig.ALLOWED_HTML_TAGS,
            attributes=SecurityConfig.ALLOWED_HTML_ATTRIBUTES,
            strip=True
        )
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """Validate filename for security"""
        # Check for path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            return False
        
        # Check for dangerous extensions
        dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
            '.jar', '.php', '.asp', '.aspx', '.jsp', '.sh', '.ps1'
        ]
        
        filename_lower = filename.lower()
        for ext in dangerous_extensions:
            if filename_lower.endswith(ext):
                return False
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format and prevent SSRF"""
        # Basic URL validation
        pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
        if not re.match(pattern, url):
            return False
        
        # Prevent access to internal networks
        forbidden_hosts = [
            'localhost', '127.0.0.1', '0.0.0.0',
            '10.', '172.16.', '172.17.', '172.18.', '172.19.',
            '172.20.', '172.21.', '172.22.', '172.23.',
            '172.24.', '172.25.', '172.26.', '172.27.',
            '172.28.', '172.29.', '172.30.', '172.31.',
            '192.168.', '169.254.'
        ]
        
        for host in forbidden_hosts:
            if host in url.lower():
                return False
        
        return True

class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware"""
    
    def __init__(self, app, config: SecurityConfig = None):
        super().__init__(app)
        self.config = config or SecurityConfig()
        self.validator = InputValidator()
    
    async def dispatch(self, request: Request, call_next):
        # HTTPS enforcement
        if self.config.FORCE_HTTPS and request.url.scheme != "https":
            if request.headers.get("x-forwarded-proto") != "https":
                https_url = request.url.replace(scheme="https")
                return JSONResponse(
                    content={"message": "Redirecting to HTTPS"},
                    status_code=status.HTTP_301_MOVED_PERMANENTLY,
                    headers={"Location": str(https_url)}
                )
        
        # Content length validation
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.config.MAX_CONTENT_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request entity too large"
            )
        
        # Content type validation
        content_type = request.headers.get("content-type", "")
        if content_type and not any(
            allowed in content_type for allowed in self.config.ALLOWED_CONTENT_TYPES
        ):
            if request.method in ["POST", "PUT", "PATCH"]:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Unsupported media type"
                )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
        
        # Add security headers
        for header, value in self.config.SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Add HSTS header for HTTPS
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = f"max-age={self.config.HSTS_MAX_AGE}; includeSubDomains"
        
        return response

class CSRFProtection:
    """CSRF protection utilities"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
    
    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token"""
        timestamp = str(int(time.time()))
        message = f"{session_id}:{timestamp}"
        signature = hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{timestamp}:{signature}"
    
    def validate_token(self, token: str, session_id: str, max_age: int = 3600) -> bool:
        """Validate CSRF token"""
        try:
            timestamp_str, signature = token.split(":", 1)
            timestamp = int(timestamp_str)
            
            # Check token age
            if time.time() - timestamp > max_age:
                return False
            
            # Verify signature
            message = f"{session_id}:{timestamp_str}"
            expected_signature = hmac.new(
                self.secret_key,
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except (ValueError, TypeError):
            return False

class SecurityValidator(BaseModel):
    """Pydantic models for input validation"""
    
    class Config:
        validate_assignment = True
        str_strip_whitespace = True
    
    @validator('*', pre=True)
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            # Remove null bytes and control characters
            v = v.replace('\x00', '').replace('\r', '').replace('\n', ' ')
            # Limit string length
            if len(v) > 10000:
                raise ValueError("String too long")
        return v

class IPWhitelist:
    """IP whitelist management"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.whitelist_key = "security:ip_whitelist"
        self.blacklist_key = "security:ip_blacklist"
    
    def add_to_whitelist(self, ip: str, ttl: int = 86400):
        """Add IP to whitelist"""
        self.redis.setex(f"{self.whitelist_key}:{ip}", ttl, "1")
    
    def add_to_blacklist(self, ip: str, ttl: int = 86400):
        """Add IP to blacklist"""
        self.redis.setex(f"{self.blacklist_key}:{ip}", ttl, "1")
    
    def is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted"""
        return bool(self.redis.get(f"{self.whitelist_key}:{ip}"))
    
    def is_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted"""
        return bool(self.redis.get(f"{self.blacklist_key}:{ip}"))

# Rate limiting decorators
def rate_limit(limit: str):
    """Rate limiting decorator"""
    return limiter.limit(limit)

# Security utilities
def get_client_ip(request: Request) -> str:
    """Get client IP address considering proxies"""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"

def log_security_event(event_type: str, details: Dict[str, Any], request: Request):
    """Log security events"""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")
    
    logger.warning(
        f"Security Event: {event_type}",
        extra={
            "event_type": event_type,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "path": str(request.url.path),
            "method": request.method,
            "details": details
        }
    )