"""Security hardening utilities and middleware for the Cliper application."""

import re
import hashlib
import secrets
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
from ipaddress import ip_address, ip_network

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp
import redis
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from email_validator import validate_email, EmailNotValidError

# from ..core.database import get_db_pool  # Disabled for Firebase migration
from ..models.user import User
from ..core.config import settings

# Security configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss: https:; "
        "media-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "speaker=()"
    )
}

# Rate limiting configuration
RATE_LIMITS = {
    "auth": {"requests": 5, "window": 300},  # 5 requests per 5 minutes
    "upload": {"requests": 10, "window": 3600},  # 10 uploads per hour
    "api": {"requests": 100, "window": 60},  # 100 requests per minute
    "download": {"requests": 50, "window": 3600},  # 50 downloads per hour
    "search": {"requests": 30, "window": 60},  # 30 searches per minute
}

# Input validation patterns
VALIDATION_PATTERNS = {
    "username": re.compile(r"^[a-zA-Z0-9_]{3,30}$"),
    "filename": re.compile(r"^[a-zA-Z0-9._-]{1,255}$"),
    "video_title": re.compile(r"^[\w\s.,!?-]{1,200}$"),
    "description": re.compile(r"^[\w\s.,!?\n-]{0,2000}$"),
    "tag": re.compile(r"^[a-zA-Z0-9_-]{1,50}$"),
}

# Blocked IP ranges and user agents
BLOCKED_IP_RANGES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
]

BLOCKED_USER_AGENTS = [
    "bot", "crawler", "spider", "scraper", "scanner",
    "curl", "wget", "python-requests", "postman"
]

class SecurityHardening:
    """Security hardening utilities and configurations."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.security_bearer = HTTPBearer(auto_error=False)
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(length)
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """Validate password strength and return detailed feedback."""
        errors = []
        score = 0
        
        # Length check
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        elif len(password) >= 12:
            score += 2
        else:
            score += 1
        
        # Character variety checks
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain lowercase letters")
        else:
            score += 1
        
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain uppercase letters")
        else:
            score += 1
        
        if not re.search(r"\d", password):
            errors.append("Password must contain numbers")
        else:
            score += 1
        
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            errors.append("Password must contain special characters")
        else:
            score += 2
        
        # Common password check
        common_passwords = [
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master"
        ]
        if password.lower() in common_passwords:
            errors.append("Password is too common")
            score = max(0, score - 3)
        
        # Determine strength
        if score >= 7:
            strength = "strong"
        elif score >= 5:
            strength = "medium"
        else:
            strength = "weak"
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "strength": strength,
            "score": score
        }
    
    def validate_email_address(self, email: str) -> Dict[str, Any]:
        """Validate email address format and domain."""
        try:
            # Basic format validation
            validated_email = validate_email(email)
            email = validated_email.email
            
            # Additional security checks
            domain = email.split('@')[1].lower()
            
            # Check for disposable email domains
            disposable_domains = [
                "10minutemail.com", "tempmail.org", "guerrillamail.com",
                "mailinator.com", "throwaway.email", "temp-mail.org"
            ]
            
            if domain in disposable_domains:
                return {
                    "valid": False,
                    "error": "Disposable email addresses are not allowed"
                }
            
            # Check for suspicious patterns
            if re.search(r"[+.]{2,}", email) or email.count('+') > 1:
                return {
                    "valid": False,
                    "error": "Email format appears suspicious"
                }
            
            return {"valid": True, "email": email}
            
        except EmailNotValidError as e:
            return {"valid": False, "error": str(e)}
    
    def validate_input(self, input_type: str, value: str) -> Dict[str, Any]:
        """Validate input against predefined patterns."""
        if input_type not in VALIDATION_PATTERNS:
            return {"valid": False, "error": f"Unknown input type: {input_type}"}
        
        pattern = VALIDATION_PATTERNS[input_type]
        
        # Check for null bytes and control characters
        if '\x00' in value or any(ord(c) < 32 and c not in '\t\n\r' for c in value):
            return {"valid": False, "error": "Input contains invalid characters"}
        
        # Check against pattern
        if not pattern.match(value):
            return {"valid": False, "error": f"Invalid {input_type} format"}
        
        # Additional XSS prevention
        xss_patterns = [
            r"<script", r"javascript:", r"on\w+\s*=", r"<iframe",
            r"<object", r"<embed", r"<link", r"<meta"
        ]
        
        for xss_pattern in xss_patterns:
            if re.search(xss_pattern, value, re.IGNORECASE):
                return {"valid": False, "error": "Input contains potentially malicious content"}
        
        return {"valid": True, "value": value}
    
    def check_rate_limit(self, identifier: str, limit_type: str) -> Dict[str, Any]:
        """Check if request is within rate limits."""
        if limit_type not in RATE_LIMITS:
            return {"allowed": True}
        
        config = RATE_LIMITS[limit_type]
        key = f"rate_limit:{limit_type}:{identifier}"
        
        try:
            current = self.redis.get(key)
            if current is None:
                # First request
                self.redis.setex(key, config["window"], 1)
                return {"allowed": True, "remaining": config["requests"] - 1}
            
            current_count = int(current)
            if current_count >= config["requests"]:
                ttl = self.redis.ttl(key)
                return {
                    "allowed": False,
                    "retry_after": ttl,
                    "error": f"Rate limit exceeded for {limit_type}"
                }
            
            # Increment counter
            new_count = self.redis.incr(key)
            return {"allowed": True, "remaining": config["requests"] - new_count}
            
        except Exception as e:
            # If Redis is down, allow the request but log the error
            print(f"Rate limiting error: {e}")
            return {"allowed": True, "error": "Rate limiting unavailable"}
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP address is in blocked ranges."""
        try:
            client_ip = ip_address(ip)
            for blocked_range in BLOCKED_IP_RANGES:
                if client_ip in ip_network(blocked_range):
                    return True
            return False
        except Exception:
            return False
    
    def is_user_agent_blocked(self, user_agent: str) -> bool:
        """Check if user agent is blocked."""
        if not user_agent:
            return True
        
        user_agent_lower = user_agent.lower()
        return any(blocked in user_agent_lower for blocked in BLOCKED_USER_AGENTS)
    
    def detect_suspicious_activity(self, request: Request, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Detect suspicious activity patterns."""
        suspicious_indicators = []
        risk_score = 0
        
        # Check for rapid requests
        client_ip = request.client.host
        rapid_requests_key = f"rapid_requests:{client_ip}"
        
        try:
            request_count = self.redis.incr(rapid_requests_key)
            if request_count == 1:
                self.redis.expire(rapid_requests_key, 10)  # 10 second window
            
            if request_count > 20:  # More than 20 requests in 10 seconds
                suspicious_indicators.append("Rapid request pattern detected")
                risk_score += 3
        except Exception:
            pass
        
        # Check for unusual request patterns
        user_agent = request.headers.get("user-agent", "")
        if len(user_agent) < 10 or len(user_agent) > 500:
            suspicious_indicators.append("Unusual user agent")
            risk_score += 1
        
        # Check for missing common headers
        common_headers = ["accept", "accept-language", "accept-encoding"]
        missing_headers = [h for h in common_headers if h not in request.headers]
        if len(missing_headers) > 1:
            suspicious_indicators.append("Missing common headers")
            risk_score += 1
        
        # Check for suspicious request paths
        path = str(request.url.path)
        suspicious_paths = [
            "/admin", "/wp-admin", "/.env", "/config", "/backup",
            "/phpmyadmin", "/mysql", "/database", "/.git"
        ]
        if any(susp_path in path for susp_path in suspicious_paths):
            suspicious_indicators.append("Suspicious path access")
            risk_score += 2
        
        # Check for SQL injection patterns in query parameters
        query_string = str(request.url.query)
        sql_patterns = [
            r"union\s+select", r"drop\s+table", r"insert\s+into",
            r"delete\s+from", r"update\s+set", r"exec\s*\(",
            r"script\s*>", r"<\s*script"
        ]
        for pattern in sql_patterns:
            if re.search(pattern, query_string, re.IGNORECASE):
                suspicious_indicators.append("Potential injection attempt")
                risk_score += 4
                break
        
        return {
            "suspicious": risk_score > 2,
            "risk_score": risk_score,
            "indicators": suspicious_indicators
        }

class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for request processing."""
    
    def __init__(self, app: ASGIApp, security: SecurityHardening):
        super().__init__(app)
        self.security = security
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        start_time = time.time()
        
        # Get client information
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        # Security checks
        try:
            # Check if IP is blocked
            if self.security.is_ip_blocked(client_ip):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Access denied"}
                )
            
            # Check if user agent is blocked
            if self.security.is_user_agent_blocked(user_agent):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Access denied"}
                )
            
            # Rate limiting
            rate_limit_result = self.security.check_rate_limit(client_ip, "api")
            if not rate_limit_result["allowed"]:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after": rate_limit_result.get("retry_after", 60)
                    },
                    headers={"Retry-After": str(rate_limit_result.get("retry_after", 60))}
                )
            
            # Detect suspicious activity
            suspicious_activity = self.security.detect_suspicious_activity(request)
            if suspicious_activity["suspicious"]:
                # Log suspicious activity
                print(f"Suspicious activity detected from {client_ip}: {suspicious_activity['indicators']}")
                
                # If risk score is very high, block the request
                if suspicious_activity["risk_score"] > 5:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Suspicious activity detected"}
                    )
            
            # Process the request
            response = await call_next(request)
            
            # Add security headers
            for header, value in SECURITY_HEADERS.items():
                response.headers[header] = value
            
            # Add rate limit headers
            if "remaining" in rate_limit_result:
                response.headers["X-RateLimit-Remaining"] = str(rate_limit_result["remaining"])
                response.headers["X-RateLimit-Limit"] = str(RATE_LIMITS["api"]["requests"])
            
            # Add processing time header
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            print(f"Security middleware error: {e}")
            # Continue processing even if security checks fail
            response = await call_next(request)
            
            # Still add basic security headers
            for header, value in SECURITY_HEADERS.items():
                response.headers[header] = value
            
            return response

class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce HTTPS in production."""
    
    def __init__(self, app: ASGIApp, enforce_https: bool = True):
        super().__init__(app)
        self.enforce_https = enforce_https
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if self.enforce_https and request.url.scheme != "https":
            # Check if this is a health check or internal request
            if request.url.path in ["/health", "/metrics", "/ready"]:
                return await call_next(request)
            
            # Redirect to HTTPS
            https_url = request.url.replace(scheme="https")
            return JSONResponse(
                status_code=status.HTTP_301_MOVED_PERMANENTLY,
                headers={"Location": str(https_url)}
            )
        
        return await call_next(request)

def rate_limit(limit_type: str):
    """Decorator for rate limiting specific endpoints."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # If no request found, proceed without rate limiting
                return await func(*args, **kwargs)
            
            # Get security instance (this would be injected in practice)
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            security = SecurityHardening(redis_client)
            
            client_ip = request.client.host
            rate_limit_result = security.check_rate_limit(client_ip, limit_type)
            
            if not rate_limit_result["allowed"]:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {limit_type}",
                    headers={"Retry-After": str(rate_limit_result.get("retry_after", 60))}
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def validate_input_data(validation_rules: Dict[str, str]):
    """Decorator for input validation."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get security instance
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            security = SecurityHardening(redis_client)
            
            # Validate inputs based on rules
            for field, input_type in validation_rules.items():
                if field in kwargs:
                    value = kwargs[field]
                    if isinstance(value, str):
                        validation_result = security.validate_input(input_type, value)
                        if not validation_result["valid"]:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid {field}: {validation_result['error']}"
                            )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Security utility functions
def get_client_ip(request: Request) -> str:
    """Get the real client IP address from request."""
    # Check for forwarded headers (when behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove path separators and dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = 255 - len(ext) - 1 if ext else 255
        filename = name[:max_name_length] + ('.' + ext if ext else '')
    
    return filename

def generate_csrf_token() -> str:
    """Generate CSRF token."""
    return secrets.token_urlsafe(32)

def verify_csrf_token(token: str, session_token: str) -> bool:
    """Verify CSRF token."""
    return secrets.compare_digest(token, session_token)

# Initialize security instance
def get_security() -> SecurityHardening:
    """Get security instance with Redis connection."""
    redis_client = redis.Redis.from_url(settings.REDIS_URL)
    return SecurityHardening(redis_client)