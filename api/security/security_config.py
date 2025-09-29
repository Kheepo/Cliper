"""Comprehensive security configuration and hardening."""

import os
import re
import hashlib
import secrets
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from functools import wraps
from ipaddress import ip_address, ip_network

from fastapi import HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
import redis
import bcrypt
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class SecurityConfig:
    """Security configuration settings."""
    
    # Rate limiting settings
    RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))
    RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '3600'))  # 1 hour
    RATE_LIMIT_BURST = int(os.getenv('RATE_LIMIT_BURST', '20'))
    
    # Authentication settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_urlsafe(32))
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))
    
    # Password security
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_NUMBERS = True
    PASSWORD_REQUIRE_SPECIAL = True
    
    # HTTPS enforcement
    FORCE_HTTPS = os.getenv('FORCE_HTTPS', 'false').lower() == 'true'
    HSTS_MAX_AGE = int(os.getenv('HSTS_MAX_AGE', '31536000'))  # 1 year
    
    # Content Security Policy
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' https:; "
        "connect-src 'self' wss: https:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    
    # IP whitelist/blacklist
    IP_WHITELIST: List[str] = os.getenv('IP_WHITELIST', '').split(',') if os.getenv('IP_WHITELIST') else []
    IP_BLACKLIST: List[str] = os.getenv('IP_BLACKLIST', '').split(',') if os.getenv('IP_BLACKLIST') else []
    
    # File upload security
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '524288000'))  # 500MB
    ALLOWED_FILE_TYPES = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv']
    UPLOAD_SCAN_ENABLED = os.getenv('UPLOAD_SCAN_ENABLED', 'true').lower() == 'true'


class InputValidator:
    """Input validation and sanitization."""
    
    # Common regex patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,20}$')
    FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
        r'(--|#|/\*|\*/)',
        r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
        r'(\b(OR|AND)\s+[\'"]\w+[\'"]\s*=\s*[\'"]\w+[\'"])',
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>.*?</iframe>',
        r'<object[^>]*>.*?</object>',
        r'<embed[^>]*>.*?</embed>',
    ]
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format."""
        return bool(cls.EMAIL_PATTERN.match(email))
    
    @classmethod
    def validate_username(cls, username: str) -> bool:
        """Validate username format."""
        return bool(cls.USERNAME_PATTERN.match(username))
    
    @classmethod
    def validate_filename(cls, filename: str) -> bool:
        """Validate filename format."""
        return bool(cls.FILENAME_PATTERN.match(filename))
    
    @classmethod
    def check_sql_injection(cls, text: str) -> bool:
        """Check for SQL injection patterns."""
        text_upper = text.upper()
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text_upper, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def check_xss(cls, text: str) -> bool:
        """Check for XSS patterns."""
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """Sanitize user input."""
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # HTML encode special characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')
        
        return text.strip()
    
    @classmethod
    def validate_password(cls, password: str) -> Dict[str, Any]:
        """Validate password strength."""
        errors = []
        
        if len(password) < SecurityConfig.PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {SecurityConfig.PASSWORD_MIN_LENGTH} characters long")
        
        if SecurityConfig.PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if SecurityConfig.PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if SecurityConfig.PASSWORD_REQUIRE_NUMBERS and not re.search(r'\d', password):
            errors.append("Password must contain at least one number")
        
        if SecurityConfig.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'strength': cls._calculate_password_strength(password)
        }
    
    @classmethod
    def _calculate_password_strength(cls, password: str) -> str:
        """Calculate password strength score."""
        score = 0
        
        # Length bonus
        score += min(len(password) * 2, 20)
        
        # Character variety bonus
        if re.search(r'[a-z]', password):
            score += 5
        if re.search(r'[A-Z]', password):
            score += 5
        if re.search(r'\d', password):
            score += 5
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 10
        
        # Penalty for common patterns
        if re.search(r'(.)\1{2,}', password):  # Repeated characters
            score -= 10
        if re.search(r'(012|123|234|345|456|567|678|789|890)', password):  # Sequential numbers
            score -= 10
        if re.search(r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)', password.lower()):
            score -= 10
        
        if score >= 50:
            return 'strong'
        elif score >= 30:
            return 'medium'
        else:
            return 'weak'


class RateLimiter:
    """Rate limiting implementation."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def is_allowed(self, key: str, limit: int = None, window: int = None) -> Dict[str, Any]:
        """Check if request is allowed based on rate limits."""
        limit = limit or SecurityConfig.RATE_LIMIT_REQUESTS
        window = window or SecurityConfig.RATE_LIMIT_WINDOW
        
        current_time = int(datetime.now().timestamp())
        window_start = current_time - window
        
        # Clean old entries
        self.redis.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        current_requests = self.redis.zcard(key)
        
        if current_requests >= limit:
            # Get time until reset
            oldest_request = self.redis.zrange(key, 0, 0, withscores=True)
            reset_time = int(oldest_request[0][1]) + window if oldest_request else current_time + window
            
            return {
                'allowed': False,
                'limit': limit,
                'remaining': 0,
                'reset_time': reset_time,
                'retry_after': reset_time - current_time
            }
        
        # Add current request
        self.redis.zadd(key, {str(current_time): current_time})
        self.redis.expire(key, window)
        
        return {
            'allowed': True,
            'limit': limit,
            'remaining': limit - current_requests - 1,
            'reset_time': current_time + window,
            'retry_after': 0
        }


class SecurityHeaders:
    """Security headers middleware."""
    
    @staticmethod
    def add_security_headers(response: Response) -> Response:
        """Add security headers to response."""
        # HTTPS enforcement
        if SecurityConfig.FORCE_HTTPS:
            response.headers['Strict-Transport-Security'] = f'max-age={SecurityConfig.HSTS_MAX_AGE}; includeSubDomains; preload'
        
        # Content Security Policy
        response.headers['Content-Security-Policy'] = SecurityConfig.CSP_POLICY
        
        # Other security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Remove server information
        if 'Server' in response.headers:
            del response.headers['Server']
        
        return response


class IPFilter:
    """IP address filtering."""
    
    @staticmethod
    def is_allowed_ip(ip: str) -> bool:
        """Check if IP address is allowed."""
        try:
            client_ip = ip_address(ip)
            
            # Check blacklist first
            for blocked_ip in SecurityConfig.IP_BLACKLIST:
                if blocked_ip and (client_ip == ip_address(blocked_ip) or 
                                 client_ip in ip_network(blocked_ip, strict=False)):
                    return False
            
            # If whitelist is configured, check it
            if SecurityConfig.IP_WHITELIST:
                for allowed_ip in SecurityConfig.IP_WHITELIST:
                    if allowed_ip and (client_ip == ip_address(allowed_ip) or 
                                     client_ip in ip_network(allowed_ip, strict=False)):
                        return True
                return False  # Not in whitelist
            
            return True  # No whitelist configured, allow by default
            
        except ValueError:
            return False  # Invalid IP address


class PasswordManager:
    """Password hashing and verification."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


class TokenManager:
    """JWT token management."""
    
    @staticmethod
    def create_token(payload: Dict[str, Any]) -> str:
        """Create JWT token."""
        payload['exp'] = datetime.utcnow() + timedelta(hours=SecurityConfig.JWT_EXPIRATION_HOURS)
        payload['iat'] = datetime.utcnow()
        payload['jti'] = secrets.token_urlsafe(16)  # Unique token ID
        
        return jwt.encode(payload, SecurityConfig.JWT_SECRET_KEY, algorithm=SecurityConfig.JWT_ALGORITHM)
    
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, SecurityConfig.JWT_SECRET_KEY, algorithms=[SecurityConfig.JWT_ALGORITHM])
            return {'valid': True, 'payload': payload}
        except jwt.ExpiredSignatureError:
            return {'valid': False, 'error': 'Token expired'}
        except jwt.InvalidTokenError:
            return {'valid': False, 'error': 'Invalid token'}


class EncryptionManager:
    """Data encryption and decryption."""
    
    def __init__(self, key: Optional[str] = None):
        if key:
            self.key = key.encode()
        else:
            self.key = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode()).encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'salt_',  # In production, use a proper salt
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.key))
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        return self.cipher.decrypt(encrypted_data.encode()).decode()


class FileSecurityScanner:
    """File security scanning."""
    
    MALICIOUS_SIGNATURES = [
        b'\x4d\x5a',  # PE executable
        b'\x7f\x45\x4c\x46',  # ELF executable
        b'\xca\xfe\xba\xbe',  # Mach-O executable
        b'<script',  # JavaScript
        b'javascript:',  # JavaScript URL
        b'vbscript:',  # VBScript URL
    ]
    
    @classmethod
    def scan_file(cls, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Scan file for security threats."""
        threats = []
        
        # Check file extension
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if file_ext not in SecurityConfig.ALLOWED_FILE_TYPES:
            threats.append(f"File type '{file_ext}' not allowed")
        
        # Check file size
        if len(file_content) > SecurityConfig.MAX_FILE_SIZE:
            threats.append(f"File size exceeds limit of {SecurityConfig.MAX_FILE_SIZE} bytes")
        
        # Check for malicious signatures
        for signature in cls.MALICIOUS_SIGNATURES:
            if signature in file_content[:1024]:  # Check first 1KB
                threats.append("Potentially malicious file signature detected")
                break
        
        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        return {
            'safe': len(threats) == 0,
            'threats': threats,
            'file_hash': file_hash,
            'file_size': len(file_content)
        }


# Security middleware decorator
def security_middleware(rate_limit: Optional[int] = None, require_auth: bool = False):
    """Security middleware decorator."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # IP filtering
            client_ip = request.client.host
            if not IPFilter.is_allowed_ip(client_ip):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied from this IP address"
                )
            
            # Rate limiting
            if rate_limit:
                # This would need Redis instance - implement in actual middleware
                pass
            
            # HTTPS enforcement
            if SecurityConfig.FORCE_HTTPS and request.url.scheme != 'https':
                raise HTTPException(
                    status_code=status.HTTP_426_UPGRADE_REQUIRED,
                    detail="HTTPS required"
                )
            
            # Authentication check
            if require_auth:
                auth_header = request.headers.get('Authorization')
                if not auth_header or not auth_header.startswith('Bearer '):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                token = auth_header.split(' ')[1]
                token_result = TokenManager.verify_token(token)
                if not token_result['valid']:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=token_result.get('error', 'Invalid token')
                    )
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator