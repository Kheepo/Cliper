from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, validator, Field
from fastapi import HTTPException
import re
import uuid
from datetime import datetime
from enum import Enum

# Common validation patterns
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
PASSWORD_PATTERN = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,20}$')
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)

class ValidationError(Exception):
    """Custom validation error."""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)

def validate_email(email: str) -> str:
    """Validate email format."""
    if not email or not isinstance(email, str):
        raise ValidationError("Email is required", "email")
    
    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValidationError("Invalid email format", "email")
    
    if len(email) > 254:  # RFC 5321 limit
        raise ValidationError("Email address too long", "email")
    
    return email

def validate_password(password: str) -> str:
    """Validate password strength."""
    if not password or not isinstance(password, str):
        raise ValidationError("Password is required", "password")
    
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long", "password")
    
    if len(password) > 128:
        raise ValidationError("Password too long", "password")
    
    if not re.search(r'[a-z]', password):
        raise ValidationError("Password must contain at least one lowercase letter", "password")
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError("Password must contain at least one uppercase letter", "password")
    
    if not re.search(r'\d', password):
        raise ValidationError("Password must contain at least one digit", "password")
    
    if not re.search(r'[@$!%*?&]', password):
        raise ValidationError("Password must contain at least one special character (@$!%*?&)", "password")
    
    return password

def validate_username(username: str) -> str:
    """Validate username format."""
    if not username or not isinstance(username, str):
        raise ValidationError("Username is required", "username")
    
    username = username.strip()
    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "Username must be 3-20 characters long and contain only letters, numbers, hyphens, and underscores",
            "username"
        )
    
    return username

def validate_uuid(value: Union[str, uuid.UUID], field_name: str = "id") -> str:
    """Validate UUID format."""
    if isinstance(value, uuid.UUID):
        return str(value)
    
    if not value or not isinstance(value, str):
        raise ValidationError(f"{field_name} is required", field_name)
    
    value = value.strip()
    if not UUID_PATTERN.match(value):
        raise ValidationError(f"Invalid {field_name} format", field_name)
    
    return value

def validate_file_size(file_size: int, max_size: int = 100 * 1024 * 1024) -> int:  # 100MB default
    """Validate file size."""
    if file_size <= 0:
        raise ValidationError("File size must be greater than 0", "file_size")
    
    if file_size > max_size:
        raise ValidationError(f"File size exceeds maximum allowed size of {max_size} bytes", "file_size")
    
    return file_size

def validate_file_type(filename: str, allowed_types: List[str]) -> str:
    """Validate file type by extension."""
    if not filename or not isinstance(filename, str):
        raise ValidationError("Filename is required", "filename")
    
    filename = filename.strip().lower()
    if '.' not in filename:
        raise ValidationError("File must have an extension", "filename")
    
    extension = filename.split('.')[-1]
    if extension not in [t.lower() for t in allowed_types]:
        raise ValidationError(
            f"File type '{extension}' not allowed. Allowed types: {', '.join(allowed_types)}",
            "filename"
        )
    
    return filename

def validate_url(url: str, field_name: str = "url") -> str:
    """Validate URL format."""
    if not url or not isinstance(url, str):
        raise ValidationError(f"{field_name} is required", field_name)
    
    url = url.strip()
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain...
        r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # host...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        raise ValidationError(f"Invalid {field_name} format", field_name)
    
    return url

def validate_text_length(text: str, min_length: int = 0, max_length: int = 1000, field_name: str = "text") -> str:
    """Validate text length."""
    if text is None:
        if min_length > 0:
            raise ValidationError(f"{field_name} is required", field_name)
        return ""
    
    if not isinstance(text, str):
        raise ValidationError(f"{field_name} must be a string", field_name)
    
    text = text.strip()
    
    if len(text) < min_length:
        raise ValidationError(f"{field_name} must be at least {min_length} characters long", field_name)
    
    if len(text) > max_length:
        raise ValidationError(f"{field_name} must be no more than {max_length} characters long", field_name)
    
    return text

def validate_positive_integer(value: Any, field_name: str = "value") -> int:
    """Validate positive integer."""
    if value is None:
        raise ValidationError(f"{field_name} is required", field_name)
    
    try:
        value = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be an integer", field_name)
    
    if value <= 0:
        raise ValidationError(f"{field_name} must be a positive integer", field_name)
    
    return value

def validate_non_negative_integer(value: Any, field_name: str = "value") -> int:
    """Validate non-negative integer."""
    if value is None:
        raise ValidationError(f"{field_name} is required", field_name)
    
    try:
        value = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be an integer", field_name)
    
    if value < 0:
        raise ValidationError(f"{field_name} must be non-negative", field_name)
    
    return value

def validate_enum_value(value: Any, enum_class: type, field_name: str = "value") -> Any:
    """Validate enum value."""
    if value is None:
        raise ValidationError(f"{field_name} is required", field_name)
    
    if isinstance(value, enum_class):
        return value
    
    # Try to convert string to enum
    if isinstance(value, str):
        try:
            return enum_class(value)
        except ValueError:
            valid_values = [e.value for e in enum_class]
            raise ValidationError(
                f"Invalid {field_name}. Valid values: {', '.join(map(str, valid_values))}",
                field_name
            )
    
    raise ValidationError(f"Invalid {field_name} type", field_name)

def validate_datetime_string(value: str, field_name: str = "datetime") -> datetime:
    """Validate datetime string in ISO format."""
    if not value or not isinstance(value, str):
        raise ValidationError(f"{field_name} is required", field_name)
    
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValidationError(f"Invalid {field_name} format. Use ISO format (YYYY-MM-DDTHH:MM:SS)", field_name)

def sanitize_html(text: str) -> str:
    """Basic HTML sanitization - remove potentially dangerous tags."""
    if not text:
        return text
    
    # Remove script tags and their content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove dangerous attributes
    text = re.sub(r'\s*on\w+\s*=\s*["\'][^"\'>]*["\']', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*javascript\s*:', '', text, flags=re.IGNORECASE)
    
    return text

class BaseValidator:
    """Base class for custom validators."""
    
    @staticmethod
    def validate_request_data(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """Validate that all required fields are present."""
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        
        return data
    
    @staticmethod
    def validate_pagination(page: int = 1, limit: int = 10, max_limit: int = 100) -> tuple[int, int]:
        """Validate pagination parameters."""
        page = validate_positive_integer(page, "page")
        limit = validate_positive_integer(limit, "limit")
        
        if limit > max_limit:
            raise ValidationError(f"Limit cannot exceed {max_limit}", "limit")
        
        return page, limit

# Pydantic models for common validation scenarios
class EmailValidation(BaseModel):
    email: str
    
    @validator('email')
    def validate_email_field(cls, v):
        return validate_email(v)

class PasswordValidation(BaseModel):
    password: str
    
    @validator('password')
    def validate_password_field(cls, v):
        return validate_password(v)

class UUIDValidation(BaseModel):
    id: str
    
    @validator('id')
    def validate_id_field(cls, v):
        return validate_uuid(v)

class PaginationValidation(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)