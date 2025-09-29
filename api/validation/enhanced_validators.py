from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, validator, Field
import re
import bleach
import html
import urllib.parse
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SecurityValidationError(Exception):
    """Custom exception for security validation errors"""
    pass

class EnhancedInputValidator:
    """Enhanced input validation and sanitization utilities"""
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"('|(\-\-)|(;)|(\||\|)|(\*|\*))",
        r"\b(union|select|insert|delete|update|drop|create|alter|exec|execute)\b",
        r"(\<script|\<\/script|javascript:|vbscript:|onload\s*=|onerror\s*=|onclick\s*=)",
        r"(\<|\>|\&|\#)"
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on(load|error|click|focus|blur|submit|change|keyup|keydown|mouseover|mouseout)\s*=",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>"
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
        r"%2e%2e%5c",
        r"\.\.\\x2f",
        r"\.\.\\x5c"
    ]
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Comprehensive string sanitization"""
        if not isinstance(value, str):
            return str(value)
        
        # Remove null bytes and control characters
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        # Normalize unicode
        value = value.encode('utf-8', 'ignore').decode('utf-8')
        
        # Strip whitespace
        value = value.strip()
        
        # Limit length
        if len(value) > max_length:
            value = value[:max_length]
            logger.warning(f"String truncated to {max_length} characters")
        
        return value
    
    @staticmethod
    def sanitize_html(content: str, allowed_tags: List[str] = None) -> str:
        """Enhanced HTML sanitization"""
        if allowed_tags is None:
            allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'a']
        
        allowed_attributes = {
            'a': ['href', 'title'],
            '*': ['class']
        }
        
        # First pass: basic HTML escaping
        content = html.escape(content)
        
        # Second pass: selective unescaping for allowed tags
        content = bleach.clean(
            content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True,
            strip_comments=True
        )
        
        return content
    
    @staticmethod
    def check_sql_injection(value: str) -> bool:
        """Check for SQL injection patterns"""
        value_lower = value.lower()
        for pattern in EnhancedInputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def check_xss(value: str) -> bool:
        """Check for XSS patterns"""
        value_lower = value.lower()
        for pattern in EnhancedInputValidator.XSS_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def check_path_traversal(value: str) -> bool:
        """Check for path traversal patterns"""
        value_lower = value.lower()
        for pattern in EnhancedInputValidator.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """Enhanced filename validation"""
        if not filename or len(filename) > 255:
            return False
        
        # Check for path traversal
        if EnhancedInputValidator.check_path_traversal(filename):
            return False
        
        # Check for dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        if any(char in filename for char in dangerous_chars):
            return False
        
        # Check for dangerous extensions
        dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
            '.jar', '.php', '.asp', '.aspx', '.jsp', '.sh', '.ps1', '.msi',
            '.dll', '.sys', '.scf', '.lnk', '.hta', '.reg'
        ]
        
        filename_lower = filename.lower()
        for ext in dangerous_extensions:
            if filename_lower.endswith(ext):
                return False
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Enhanced email validation"""
        if not email or len(email) > 254:
            return False
        
        # RFC 5322 compliant regex (simplified)
        pattern = r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        
        if not re.match(pattern, email):
            return False
        
        # Check for suspicious patterns
        if EnhancedInputValidator.check_xss(email) or EnhancedInputValidator.check_sql_injection(email):
            return False
        
        return True
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Enhanced URL validation with SSRF protection"""
        if not url or len(url) > 2048:
            return False
        
        # Basic URL format validation
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Only allow HTTP/HTTPS
            if parsed.scheme not in ['http', 'https']:
                return False
            
        except Exception:
            return False
        
        # SSRF protection - block internal networks
        forbidden_patterns = [
            r'localhost',
            r'127\.\d+\.\d+\.\d+',
            r'0\.0\.0\.0',
            r'10\.\d+\.\d+\.\d+',
            r'172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+',
            r'192\.168\.\d+\.\d+',
            r'169\.254\.\d+\.\d+',
            r'\[::1\]',
            r'\[::ffff:',
        ]
        
        url_lower = url.lower()
        for pattern in forbidden_patterns:
            if re.search(pattern, url_lower):
                return False
        
        # Check for XSS in URL
        if EnhancedInputValidator.check_xss(url):
            return False
        
        return True
    
    @staticmethod
    def validate_json_structure(data: Dict[str, Any], max_depth: int = 10, max_keys: int = 100) -> bool:
        """Validate JSON structure to prevent DoS attacks"""
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                return False
            
            if isinstance(obj, dict):
                if len(obj) > max_keys:
                    return False
                for value in obj.values():
                    if not check_depth(value, current_depth + 1):
                        return False
            elif isinstance(obj, list):
                if len(obj) > max_keys:
                    return False
                for item in obj:
                    if not check_depth(item, current_depth + 1):
                        return False
            
            return True
        
        return check_depth(data)

class SecureBaseModel(BaseModel):
    """Base model with enhanced security validation"""
    
    class Config:
        validate_assignment = True
        str_strip_whitespace = True
        anystr_lower = False
        max_anystr_length = 10000
    
    @validator('*', pre=True)
    def sanitize_input(cls, v):
        """Pre-validation sanitization"""
        if isinstance(v, str):
            # Basic sanitization
            v = EnhancedInputValidator.sanitize_string(v)
            
            # Security checks
            if EnhancedInputValidator.check_sql_injection(v):
                raise SecurityValidationError("Potential SQL injection detected")
            
            if EnhancedInputValidator.check_xss(v):
                raise SecurityValidationError("Potential XSS attack detected")
            
            if EnhancedInputValidator.check_path_traversal(v):
                raise SecurityValidationError("Path traversal attempt detected")
        
        return v

class SecureStringField(str):
    """Custom string field with security validation"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')
        
        # Sanitize
        v = EnhancedInputValidator.sanitize_string(v)
        
        # Security validation
        if EnhancedInputValidator.check_sql_injection(v):
            raise ValueError('Invalid input: potential security threat')
        
        if EnhancedInputValidator.check_xss(v):
            raise ValueError('Invalid input: potential security threat')
        
        return cls(v)

class SecureEmailField(str):
    """Custom email field with enhanced validation"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')
        
        if not EnhancedInputValidator.validate_email(v):
            raise ValueError('Invalid email format')
        
        return cls(v)

class SecureURLField(str):
    """Custom URL field with SSRF protection"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')
        
        if not EnhancedInputValidator.validate_url(v):
            raise ValueError('Invalid or unsafe URL')
        
        return cls(v)

class SecureFilenameField(str):
    """Custom filename field with security validation"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')
        
        if not EnhancedInputValidator.validate_filename(v):
            raise ValueError('Invalid or unsafe filename')
        
        return cls(v)

# Example usage models
class UserRegistrationModel(SecureBaseModel):
    """Example secure user registration model"""
    username: SecureStringField = Field(..., min_length=3, max_length=50)
    email: SecureEmailField = Field(...)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[SecureStringField] = Field(None, max_length=100)
    
    @validator('password')
    def validate_password(cls, v):
        """Enhanced password validation"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        # Check for common patterns
        if v.lower() in ['password', '12345678', 'qwerty123']:
            raise ValueError('Password is too common')
        
        # Require complexity
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        return v

class FileUploadModel(SecureBaseModel):
    """Example secure file upload model"""
    filename: SecureFilenameField = Field(...)
    content_type: str = Field(...)
    size: int = Field(..., gt=0, le=2*1024*1024*1024)  # Max 2GB
    
    @validator('content_type')
    def validate_content_type(cls, v):
        """Validate content type"""
        allowed_types = [
            'video/mp4', 'video/avi', 'video/mov', 'video/wmv',
            'audio/mp3', 'audio/wav', 'audio/aac',
            'image/jpeg', 'image/png', 'image/gif',
            'application/pdf', 'text/plain'
        ]
        
        if v not in allowed_types:
            raise ValueError(f'Content type {v} not allowed')
        
        return v

class APIRequestModel(SecureBaseModel):
    """Example secure API request model"""
    action: SecureStringField = Field(..., max_length=50)
    parameters: Optional[Dict[str, Any]] = Field(None)
    
    @validator('parameters')
    def validate_parameters(cls, v):
        """Validate parameters structure"""
        if v is not None:
            if not EnhancedInputValidator.validate_json_structure(v, max_depth=5, max_keys=50):
                raise ValueError('Invalid parameters structure')
        
        return v