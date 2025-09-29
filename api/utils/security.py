"""Security and validation utilities for clip generation system.

This module provides:
- Input validation and sanitization
- File security checks and validation
- User permission verification
- Rate limiting and abuse prevention
- Security headers and CORS handling
- File upload security
"""

import os
import re
import hashlib
import mimetypes
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time
import json
import magic
from urllib.parse import urlparse, unquote

from .logging_config import get_logger

logger = get_logger('security')


# Security constants
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
MAX_FILENAME_LENGTH = 255
MAX_PATH_LENGTH = 4096
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
ALLOWED_MIME_TYPES = {
    'video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo',
    'video/webm', 'video/x-flv', 'video/x-ms-wmv', 'video/x-matroska',
    'audio/mpeg', 'audio/wav', 'audio/aac', 'audio/flac', 'audio/ogg',
    'audio/mp4', 'audio/x-ms-wma',
    'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp', 'image/tiff'
}

# Dangerous file patterns
DANGEROUS_PATTERNS = [
    r'\.\.[\\/]',  # Path traversal
    r'[<>:"|?*]',   # Invalid filename characters
    r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$',  # Windows reserved names
    r'\x00',        # Null bytes
    r'[\x01-\x1f]', # Control characters
]

# SQL injection patterns
SQL_INJECTION_PATTERNS = [
    r"('|(\-\-)|(;)|(\|)|(\*)|(%27)|(')|(\+))",
    r"((%3D)|(=))[^\n]*((%27)|(')|((%3B)|(;)))",
    r"w*((%27)|('))\s*((%6F)|o|(%4F))((%72)|r|(%52))",
    r"((%27)|('))\s*union",
    r"exec(\s|\+)+(s|x)p\w+"
]

# XSS patterns
XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>"
]


@dataclass
class ValidationResult:
    """Result of validation check."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    sanitized_value: Optional[Any] = None
    
    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add a warning message."""
        self.warnings.append(warning)


@dataclass
class FileSecurityInfo:
    """File security analysis result."""
    is_safe: bool
    file_type: str
    mime_type: str
    size: int
    hash_md5: str
    hash_sha256: str
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]


class RateLimiter:
    """Rate limiting for API endpoints and user actions."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)
        self.blocked_until = defaultdict(float)
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Optional[float]]:
        """Check if request is allowed for identifier.
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.time()
        
        # Check if currently blocked
        if identifier in self.blocked_until:
            if now < self.blocked_until[identifier]:
                return False, self.blocked_until[identifier] - now
            else:
                del self.blocked_until[identifier]
        
        # Clean old requests
        cutoff = now - self.window_seconds
        request_times = self.requests[identifier]
        
        while request_times and request_times[0] < cutoff:
            request_times.popleft()
        
        # Check rate limit
        if len(request_times) >= self.max_requests:
            # Block for remaining window time
            self.blocked_until[identifier] = request_times[0] + self.window_seconds
            return False, self.blocked_until[identifier] - now
        
        # Allow request
        request_times.append(now)
        return True, None
    
    def reset(self, identifier: str):
        """Reset rate limit for identifier."""
        self.requests.pop(identifier, None)
        self.blocked_until.pop(identifier, None)


class InputValidator:
    """Input validation and sanitization."""
    
    @staticmethod
    def validate_string(value: str, min_length: int = 0, max_length: int = 1000, 
                       allow_empty: bool = True, pattern: Optional[str] = None) -> ValidationResult:
        """Validate string input."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(value, str):
            result.add_error("Value must be a string")
            return result
        
        # Check empty
        if not value and not allow_empty:
            result.add_error("Value cannot be empty")
            return result
        
        # Check length
        if len(value) < min_length:
            result.add_error(f"Value must be at least {min_length} characters")
        
        if len(value) > max_length:
            result.add_error(f"Value must be at most {max_length} characters")
        
        # Check pattern
        if pattern and not re.match(pattern, value):
            result.add_error(f"Value does not match required pattern")
        
        # Check for dangerous patterns
        for dangerous_pattern in DANGEROUS_PATTERNS:
            if re.search(dangerous_pattern, value, re.IGNORECASE):
                result.add_error(f"Value contains dangerous characters")
                break
        
        # Check for SQL injection
        for sql_pattern in SQL_INJECTION_PATTERNS:
            if re.search(sql_pattern, value, re.IGNORECASE):
                result.add_error("Value contains potential SQL injection")
                break
        
        # Check for XSS
        for xss_pattern in XSS_PATTERNS:
            if re.search(xss_pattern, value, re.IGNORECASE):
                result.add_error("Value contains potential XSS")
                break
        
        # Sanitize if valid
        if result.is_valid:
            sanitized = value.strip()
            # Remove null bytes and control characters
            sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
            result.sanitized_value = sanitized
        
        return result
    
    @staticmethod
    def validate_integer(value: Any, min_value: Optional[int] = None, 
                        max_value: Optional[int] = None) -> ValidationResult:
        """Validate integer input."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            result.add_error("Value must be an integer")
            return result
        
        if min_value is not None and int_value < min_value:
            result.add_error(f"Value must be at least {min_value}")
        
        if max_value is not None and int_value > max_value:
            result.add_error(f"Value must be at most {max_value}")
        
        if result.is_valid:
            result.sanitized_value = int_value
        
        return result
    
    @staticmethod
    def validate_float(value: Any, min_value: Optional[float] = None, 
                      max_value: Optional[float] = None) -> ValidationResult:
        """Validate float input."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            result.add_error("Value must be a number")
            return result
        
        if min_value is not None and float_value < min_value:
            result.add_error(f"Value must be at least {min_value}")
        
        if max_value is not None and float_value > max_value:
            result.add_error(f"Value must be at most {max_value}")
        
        if result.is_valid:
            result.sanitized_value = float_value
        
        return result
    
    @staticmethod
    def validate_email(email: str) -> ValidationResult:
        """Validate email address."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(email, str):
            result.add_error("Email must be a string")
            return result
        
        email = email.strip().lower()
        
        # Basic email pattern
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            result.add_error("Invalid email format")
        
        if len(email) > 254:  # RFC 5321 limit
            result.add_error("Email address too long")
        
        if result.is_valid:
            result.sanitized_value = email
        
        return result
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> ValidationResult:
        """Validate URL."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(url, str):
            result.add_error("URL must be a string")
            return result
        
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        try:
            parsed = urlparse(url)
        except Exception:
            result.add_error("Invalid URL format")
            return result
        
        if not parsed.scheme:
            result.add_error("URL must have a scheme")
        elif parsed.scheme.lower() not in allowed_schemes:
            result.add_error(f"URL scheme must be one of: {', '.join(allowed_schemes)}")
        
        if not parsed.netloc:
            result.add_error("URL must have a domain")
        
        if result.is_valid:
            result.sanitized_value = url
        
        return result
    
    @staticmethod
    def validate_json(value: str, max_size: int = 10240) -> ValidationResult:
        """Validate JSON string."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(value, str):
            result.add_error("JSON must be a string")
            return result
        
        if len(value) > max_size:
            result.add_error(f"JSON too large (max {max_size} bytes)")
            return result
        
        try:
            parsed = json.loads(value)
            result.sanitized_value = parsed
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {e}")
        
        return result


class FileValidator:
    """File validation and security checks."""
    
    @staticmethod
    def validate_filename(filename: str) -> ValidationResult:
        """Validate filename for security."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(filename, str):
            result.add_error("Filename must be a string")
            return result
        
        # Basic checks
        if not filename:
            result.add_error("Filename cannot be empty")
            return result
        
        if len(filename) > MAX_FILENAME_LENGTH:
            result.add_error(f"Filename too long (max {MAX_FILENAME_LENGTH} characters)")
        
        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                result.add_error("Filename contains dangerous characters")
                break
        
        # Check for reserved names (Windows)
        name_without_ext = os.path.splitext(filename)[0].upper()
        reserved_names = {'CON', 'PRN', 'AUX', 'NUL'}
        reserved_names.update({f'COM{i}' for i in range(1, 10)})
        reserved_names.update({f'LPT{i}' for i in range(1, 10)})
        
        if name_without_ext in reserved_names:
            result.add_error("Filename uses reserved name")
        
        # Sanitize filename
        if result.is_valid:
            # Remove dangerous characters
            sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '', filename)
            # Remove leading/trailing dots and spaces
            sanitized = sanitized.strip('. ')
            # Ensure it's not empty after sanitization
            if not sanitized:
                sanitized = 'file'
            
            result.sanitized_value = sanitized
        
        return result
    
    @staticmethod
    def validate_file_path(file_path: str, base_path: Optional[str] = None) -> ValidationResult:
        """Validate file path for security."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(file_path, str):
            result.add_error("File path must be a string")
            return result
        
        if len(file_path) > MAX_PATH_LENGTH:
            result.add_error(f"File path too long (max {MAX_PATH_LENGTH} characters)")
        
        try:
            # Normalize path
            normalized_path = os.path.normpath(file_path)
            
            # Check for path traversal
            if '..' in normalized_path:
                result.add_error("Path traversal detected")
            
            # Check if within base path
            if base_path:
                base_abs = os.path.abspath(base_path)
                file_abs = os.path.abspath(normalized_path)
                
                if not file_abs.startswith(base_abs):
                    result.add_error("Path outside allowed directory")
            
            if result.is_valid:
                result.sanitized_value = normalized_path
        
        except Exception as e:
            result.add_error(f"Invalid file path: {e}")
        
        return result
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: Optional[set] = None) -> ValidationResult:
        """Validate file extension."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if allowed_extensions is None:
            allowed_extensions = ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS
        
        _, ext = os.path.splitext(filename.lower())
        
        if not ext:
            result.add_error("File must have an extension")
        elif ext not in allowed_extensions:
            result.add_error(f"File extension '{ext}' not allowed")
        
        return result
    
    @staticmethod
    def analyze_file_security(file_path: str) -> FileSecurityInfo:
        """Perform comprehensive file security analysis."""
        errors = []
        warnings = []
        metadata = {}
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                errors.append("File does not exist")
                return FileSecurityInfo(
                    is_safe=False,
                    file_type='unknown',
                    mime_type='unknown',
                    size=0,
                    hash_md5='',
                    hash_sha256='',
                    errors=errors,
                    warnings=warnings,
                    metadata=metadata
                )
            
            # Get file stats
            stat = os.stat(file_path)
            file_size = stat.st_size
            
            # Check file size
            if file_size > MAX_FILE_SIZE:
                errors.append(f"File too large ({file_size} bytes, max {MAX_FILE_SIZE})")
            
            if file_size == 0:
                warnings.append("File is empty")
            
            # Get MIME type
            mime_type = mimetypes.guess_type(file_path)[0] or 'unknown'
            
            # Use python-magic for more accurate detection if available
            try:
                mime_type = magic.from_file(file_path, mime=True)
            except Exception:
                pass  # Fall back to mimetypes
            
            # Validate MIME type
            if mime_type not in ALLOWED_MIME_TYPES and mime_type != 'unknown':
                errors.append(f"MIME type '{mime_type}' not allowed")
            
            # Calculate hashes
            hash_md5 = ''
            hash_sha256 = ''
            
            if file_size > 0 and file_size <= MAX_FILE_SIZE:
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                        hash_md5 = hashlib.md5(content).hexdigest()
                        hash_sha256 = hashlib.sha256(content).hexdigest()
                except Exception as e:
                    warnings.append(f"Could not calculate hashes: {e}")
            
            # Determine file type
            file_type = 'unknown'
            if mime_type.startswith('video/'):
                file_type = 'video'
            elif mime_type.startswith('audio/'):
                file_type = 'audio'
            elif mime_type.startswith('image/'):
                file_type = 'image'
            
            # Additional metadata
            metadata.update({
                'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'permissions': oct(stat.st_mode)[-3:],
            })
            
            return FileSecurityInfo(
                is_safe=len(errors) == 0,
                file_type=file_type,
                mime_type=mime_type,
                size=file_size,
                hash_md5=hash_md5,
                hash_sha256=hash_sha256,
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )
        
        except Exception as e:
            errors.append(f"File analysis failed: {e}")
            return FileSecurityInfo(
                is_safe=False,
                file_type='unknown',
                mime_type='unknown',
                size=0,
                hash_md5='',
                hash_sha256='',
                errors=errors,
                warnings=warnings,
                metadata=metadata
            )


class PermissionValidator:
    """User permission validation."""
    
    @staticmethod
    def can_access_job(user_id: str, job_id: str, supabase_service) -> Tuple[bool, Optional[str]]:
        """Check if user can access a job.
        
        Returns:
            Tuple of (can_access, error_message)
        """
        try:
            job = supabase_service.get_job(job_id)
            if not job:
                return False, "Job not found"
            
            if job.get('user_id') != user_id:
                return False, "Access denied"
            
            return True, None
        
        except Exception as e:
            logger.logger.error(f"Error checking job access: {e}", exc_info=True)
            return False, "Permission check failed"
    
    @staticmethod
    def can_generate_clips(user_id: str, supabase_service) -> Tuple[bool, Optional[str]]:
        """Check if user can generate clips.
        
        Returns:
            Tuple of (can_generate, error_message)
        """
        try:
            # Check user exists and is active
            user = supabase_service.get_user(user_id)
            if not user:
                return False, "User not found"
            
            # Check if user is active
            if not user.get('is_active', True):
                return False, "User account is inactive"
            
            # Check rate limits (example: max 10 jobs per hour)
            recent_jobs = supabase_service.get_recent_jobs(
                user_id=user_id,
                hours=1,
                limit=10
            )
            
            if len(recent_jobs) >= 10:
                return False, "Rate limit exceeded (max 10 jobs per hour)"
            
            return True, None
        
        except Exception as e:
            logger.logger.error(f"Error checking clip generation permission: {e}", exc_info=True)
            return False, "Permission check failed"
    
    @staticmethod
    def can_access_file(user_id: str, file_path: str, supabase_service) -> Tuple[bool, Optional[str]]:
        """Check if user can access a file.
        
        Returns:
            Tuple of (can_access, error_message)
        """
        try:
            # Validate file path
            path_result = FileValidator.validate_file_path(file_path)
            if not path_result.is_valid:
                return False, f"Invalid file path: {'; '.join(path_result.errors)}"
            
            # Check if file exists
            if not os.path.exists(file_path):
                return False, "File not found"
            
            # Check if file belongs to user (simplified check)
            # In a real implementation, you'd check file ownership in database
            if user_id not in file_path:
                return False, "Access denied"
            
            return True, None
        
        except Exception as e:
            logger.logger.error(f"Error checking file access: {e}", exc_info=True)
            return False, "Permission check failed"


class SecurityManager:
    """Main security manager class."""
    
    def __init__(self):
        self.rate_limiters = {
            'api': RateLimiter(max_requests=1000, window_seconds=3600),  # 1000 requests per hour
            'upload': RateLimiter(max_requests=10, window_seconds=3600),  # 10 uploads per hour
            'generation': RateLimiter(max_requests=5, window_seconds=3600),  # 5 generations per hour
        }
        self.input_validator = InputValidator()
        self.file_validator = FileValidator()
        self.permission_validator = PermissionValidator()
    
    def check_rate_limit(self, limiter_name: str, identifier: str) -> Tuple[bool, Optional[float]]:
        """Check rate limit for an identifier."""
        if limiter_name not in self.rate_limiters:
            return True, None
        
        return self.rate_limiters[limiter_name].is_allowed(identifier)
    
    def validate_clip_generation_request(self, user_id: str, video_path: str, 
                                       segments: List[Dict], supabase_service) -> ValidationResult:
        """Validate a clip generation request."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Validate user ID
        user_result = self.input_validator.validate_string(
            user_id, min_length=1, max_length=100, allow_empty=False
        )
        if not user_result.is_valid:
            result.errors.extend([f"User ID: {e}" for e in user_result.errors])
        
        # Validate video path
        path_result = self.file_validator.validate_file_path(video_path)
        if not path_result.is_valid:
            result.errors.extend([f"Video path: {e}" for e in path_result.errors])
        
        # Check file security
        if path_result.is_valid and os.path.exists(video_path):
            file_security = self.file_validator.analyze_file_security(video_path)
            if not file_security.is_safe:
                result.errors.extend([f"Video file: {e}" for e in file_security.errors])
            
            if file_security.file_type != 'video':
                result.add_error("File is not a video")
        
        # Validate segments
        if not isinstance(segments, list):
            result.add_error("Segments must be a list")
        elif len(segments) == 0:
            result.add_error("At least one segment is required")
        elif len(segments) > 50:  # Reasonable limit
            result.add_error("Too many segments (max 50)")
        else:
            for i, segment in enumerate(segments):
                if not isinstance(segment, dict):
                    result.add_error(f"Segment {i}: must be an object")
                    continue
                
                # Validate start_time
                if 'start_time' not in segment:
                    result.add_error(f"Segment {i}: missing start_time")
                else:
                    start_result = self.input_validator.validate_float(
                        segment['start_time'], min_value=0
                    )
                    if not start_result.is_valid:
                        result.errors.extend([f"Segment {i} start_time: {e}" for e in start_result.errors])
                
                # Validate end_time
                if 'end_time' not in segment:
                    result.add_error(f"Segment {i}: missing end_time")
                else:
                    end_result = self.input_validator.validate_float(
                        segment['end_time'], min_value=0
                    )
                    if not end_result.is_valid:
                        result.errors.extend([f"Segment {i} end_time: {e}" for e in end_result.errors])
                
                # Check time order
                if ('start_time' in segment and 'end_time' in segment and 
                    isinstance(segment['start_time'], (int, float)) and 
                    isinstance(segment['end_time'], (int, float))):
                    if segment['start_time'] >= segment['end_time']:
                        result.add_error(f"Segment {i}: start_time must be less than end_time")
        
        # Check permissions
        can_generate, perm_error = self.permission_validator.can_generate_clips(user_id, supabase_service)
        if not can_generate:
            result.add_error(f"Permission denied: {perm_error}")
        
        # Check rate limits
        is_allowed, retry_after = self.check_rate_limit('generation', user_id)
        if not is_allowed:
            result.add_error(f"Rate limit exceeded. Try again in {retry_after:.0f} seconds")
        
        result.is_valid = len(result.errors) == 0
        return result
    
    def sanitize_output_filename(self, filename: str) -> str:
        """Sanitize filename for output."""
        result = self.file_validator.validate_filename(filename)
        return result.sanitized_value or 'output'
    
    def get_safe_temp_path(self, base_dir: str, filename: str) -> str:
        """Get a safe temporary file path."""
        safe_filename = self.sanitize_output_filename(filename)
        
        # Add timestamp to avoid conflicts
        timestamp = int(time.time() * 1000)
        name, ext = os.path.splitext(safe_filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        
        return os.path.join(base_dir, unique_filename)


# Global security manager instance
security_manager = SecurityManager()


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance."""
    return security_manager


# Convenience functions
def validate_user_input(value: str, input_type: str = 'string', **kwargs) -> ValidationResult:
    """Validate user input with appropriate validator."""
    validator = security_manager.input_validator
    
    if input_type == 'string':
        return validator.validate_string(value, **kwargs)
    elif input_type == 'integer':
        return validator.validate_integer(value, **kwargs)
    elif input_type == 'float':
        return validator.validate_float(value, **kwargs)
    elif input_type == 'email':
        return validator.validate_email(value)
    elif input_type == 'url':
        return validator.validate_url(value, **kwargs)
    elif input_type == 'json':
        return validator.validate_json(value, **kwargs)
    else:
        result = ValidationResult(is_valid=False, errors=[], warnings=[])
        result.add_error(f"Unknown input type: {input_type}")
        return result


def check_file_security(file_path: str) -> FileSecurityInfo:
    """Check file security."""
    return security_manager.file_validator.analyze_file_security(file_path)


def check_user_permission(user_id: str, action: str, resource_id: str, supabase_service) -> Tuple[bool, Optional[str]]:
    """Check user permission for an action."""
    validator = security_manager.permission_validator
    
    if action == 'access_job':
        return validator.can_access_job(user_id, resource_id, supabase_service)
    elif action == 'generate_clips':
        return validator.can_generate_clips(user_id, supabase_service)
    elif action == 'access_file':
        return validator.can_access_file(user_id, resource_id, supabase_service)
    else:
        return False, f"Unknown action: {action}"