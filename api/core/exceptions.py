"""Custom exceptions for video processing pipeline.

This module defines specialized exceptions for different types of errors
that can occur during video processing operations.
"""

class BaseAPIException(Exception):
    """Base exception for all API-related errors."""
    
    def __init__(self, message: str, status_code: int = 500, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'status_code': self.status_code,
            'error_code': self.error_code,
            'details': self.details
        }


class VideoProcessingError(BaseAPIException):
    """Base exception for video processing errors."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        self.message = message

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details
        }


class ResourceExhaustionError(VideoProcessingError):
    """Raised when system resources are exhausted."""
    pass


class TranscriptionError(VideoProcessingError):
    """Raised when audio transcription fails."""
    pass


class SegmentationError(VideoProcessingError):
    """Raised when video segmentation fails."""
    pass


class EncodingError(VideoProcessingError):
    """Raised when video encoding fails."""
    pass


class ValidationError(VideoProcessingError):
    """Raised when input validation fails."""
    pass


class TimeoutError(VideoProcessingError):
    """Raised when operations timeout."""
    pass


class GPUError(VideoProcessingError):
    """Raised when GPU acceleration fails."""
    pass


class StorageError(VideoProcessingError):
    """Raised when storage operations fail."""
    pass


class EmailError(BaseAPIException):
    """Raised when email operations fail."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=500, error_code=error_code, details=details)


class ConfigurationError(BaseAPIException):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=500, error_code=error_code, details=details)


class AuthenticationError(BaseAPIException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=401, error_code=error_code, details=details)


class AuthorizationError(BaseAPIException):
    """Raised when authorization fails."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=403, error_code=error_code, details=details)


class NotFoundError(BaseAPIException):
    """Raised when a resource is not found."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=404, error_code=error_code, details=details)


class RateLimitError(BaseAPIException):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=429, error_code=error_code, details=details)


class ExternalServiceError(BaseAPIException):
    """Raised when external service calls fail."""
    
    def __init__(self, message: str, service_name: str = None, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=502, error_code=error_code, details=details)
        self.service_name = service_name


class DatabaseError(BaseAPIException):
    """Raised when database operations fail."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=500, error_code=error_code, details=details)


class FileProcessingError(BaseAPIException):
    """Raised when file processing operations fail."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message, status_code=500, error_code=error_code, details=details)


# Response models for API errors
class ErrorResponse:
    """Standard error response model."""
    
    def __init__(self, error: str, message: str, status_code: int = 500, details: dict = None):
        self.error = error
        self.message = message
        self.status_code = status_code
        self.details = details or {}
    
    def to_dict(self) -> dict:
        return {
            'error': self.error,
            'message': self.message,
            'status_code': self.status_code,
            'details': self.details
        }


class ValidationErrorResponse(ErrorResponse):
    """Validation error response model."""
    
    def __init__(self, message: str, field_errors: dict = None):
        super().__init__('ValidationError', message, 400, {'field_errors': field_errors or {}})


class AuthErrorResponse(ErrorResponse):
    """Authentication error response model."""
    
    def __init__(self, message: str = 'Authentication required'):
        super().__init__('AuthenticationError', message, 401)


class RateLimitErrorResponse(ErrorResponse):
    """Rate limit error response model."""
    
    def __init__(self, message: str = 'Rate limit exceeded', retry_after: int = None):
        details = {'retry_after': retry_after} if retry_after else {}
        super().__init__('RateLimitError', message, 429, details)


class ServiceErrorResponse(ErrorResponse):
    """Service error response model."""
    
    def __init__(self, message: str, service_name: str = None):
        details = {'service_name': service_name} if service_name else {}
        super().__init__('ServiceError', message, 502, details)


def convert_to_http_exception(exception: BaseAPIException) -> dict:
    """Convert a BaseAPIException to HTTP response format."""
    return {
        'status_code': exception.status_code,
        'detail': {
            'error': exception.__class__.__name__,
            'message': exception.message,
            'error_code': exception.error_code,
            'details': exception.details
        }
    }