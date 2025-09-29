"""Core module for API configuration and shared utilities."""

from .config import get_settings
from .database import get_db_pool, create_db_pool, close_db_pool, test_db_connection
from . import cache
from .exceptions import (
    BaseAPIException,
    ConfigurationError,
    EmailError,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    DatabaseError,
    ExternalServiceError,
    RateLimitError,
    FileProcessingError,
    VideoProcessingError,
    StorageError,
    convert_to_http_exception,
    ErrorResponse,
    ValidationErrorResponse,
    AuthErrorResponse,
    RateLimitErrorResponse,
    ServiceErrorResponse
)

__all__ = [
    'get_settings',
    'get_db_pool',
    'create_db_pool',
    'close_db_pool',
    'test_db_connection',
    'cache',
    'BaseAPIException',
    'ConfigurationError',
    'EmailError',
    'AuthenticationError',
    'AuthorizationError',
    'ValidationError',
    'DatabaseError',
    'ExternalServiceError',
    'RateLimitError',
    'FileProcessingError',
    'VideoProcessingError',
    'StorageError',
    'convert_to_http_exception',
    'ErrorResponse',
    'ValidationErrorResponse',
    'AuthErrorResponse',
    'RateLimitErrorResponse',
    'ServiceErrorResponse'
]